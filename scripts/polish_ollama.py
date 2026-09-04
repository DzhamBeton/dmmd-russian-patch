#!/usr/bin/env python3
"""Post-edit an existing DMMD translation with a second local Ollama model."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path


PROMPT_VERSION = "dmmd-polish-v3"
PROTECTED_RE = re.compile(
    r"(?m)^[ \t]*//【[^\r\n]*(?:\r?\n)?|<[^>]+>|%(?:\d+\$)?[a-zA-Z]|\\[nrt]"
)
TOKEN_RE = re.compile(r"__DMMD_TOKEN_\d{3}__")
VOICE_PREFIX_RE = re.compile(r"(?ms)^(\s*(?://【[^\r\n]*\r?\n)?(?:<[^>]+>)*?<voice[^>]+>\s*)")
MARKUP_RE = re.compile(r"(?m)^[ \t]*//【[^\r\n]*(?:\r?\n)?|<[^>]+>")
ENGLISH_RE = re.compile(r"[A-Za-z]{2,}")


def split_prefix(text: str) -> tuple[str, str]:
    match = VOICE_PREFIX_RE.match(text)
    if match:
        return match.group(1), text[len(match.group(1)) :]
    return "", text


def protect(text: str) -> tuple[str, list[str]]:
    values: list[str] = []

    def replace(match: re.Match[str]) -> str:
        token = f"__DMMD_TOKEN_{len(values):03d}__"
        values.append(match.group(0))
        return token

    return PROTECTED_RE.sub(replace, text), values


def restore(text: str, values: list[str]) -> str:
    expected = [f"__DMMD_TOKEN_{i:03d}__" for i in range(len(values))]
    if Counter(TOKEN_RE.findall(text)) != Counter(expected):
        raise ValueError(f"protected tokens changed: expected {expected}, got {TOKEN_RE.findall(text)}")
    for token, value in zip(expected, values):
        text = text.replace(token, value)
    return text


def post_json(url: str, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def context_text(row: dict | None) -> str:
    if not row:
        return "—"
    return MARKUP_RE.sub("", row.get("translation", "")).strip() or "—"


def polish_one(api: str, model: str, row: dict, previous: dict | None, following: dict | None, timeout: int, num_ctx: int) -> str:
    prefix, source_visible = split_prefix(row["source"])
    _draft_prefix, draft_visible = split_prefix(row["translation"])
    source_core = source_visible.strip()
    leading = re.match(r"^\s*", draft_visible).group(0)
    trailing = re.search(r"\s*$", draft_visible).group(0)
    draft_core = draft_visible[len(leading) : len(draft_visible) - len(trailing) if trailing else None]
    source_protected, source_tokens = protect(source_core)
    draft_protected, draft_tokens = protect(draft_core)
    if source_tokens != draft_tokens:
        raise ValueError("source and draft protected tags differ")

    marker_rule = ""
    if draft_tokens:
        marker_rule = (
            "\nСлужебные маркеры DMMD_TOKEN в тексте обязательны. "
            "Верни каждый имеющийся маркер ровно один раз и не изменяй его.\n"
        )

    prompt = f"""Ты литературный редактор русского перевода визуальной новеллы DRAMAtical Murder.
Сверь черновой русский перевод с английским оригиналом. Исправь потерю смысла, род, обращения,
неестественные конструкции, повторы и стиль диалога. Не смягчай лексику и не добавляй новых фактов.
Если перевод уже хороший, верни его без изменений.

{marker_rule}

Предыдущая русская реплика (только контекст): {context_text(previous)}
Следующая русская реплика (только контекст): {context_text(following)}

Английский оригинал:
{source_protected.strip()}

Черновой русский перевод Qwen:
{draft_protected.strip()}

Верни только окончательный русский перевод текущей реплики, без пояснений и заголовков."""
    response = post_json(
        api.rstrip("/") + "/api/chat",
        {
            "model": model,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.1, "num_ctx": num_ctx},
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout,
    )
    content = response["message"]["content"].strip()
    return prefix + leading + restore(content, draft_tokens) + trailing


def write_catalog(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", default="translategemma:12b")
    parser.add_argument("--api", default="http://127.0.0.1:11434")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--num-ctx", type=int, default=4096)
    parser.add_argument("--checkpoint-every", type=int, default=50)
    parser.add_argument("--cache", type=Path, default=Path("work/cache/polish.sqlite3"))
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines()]
    if args.output.exists():
        existing = {r["id"]: r for r in (json.loads(line) for line in args.output.read_text(encoding="utf-8").splitlines())}
        for index, row in enumerate(rows):
            old = existing.get(row["id"])
            if (
                old
                and old.get("source_sha256") == row.get("source_sha256")
                and old.get("polish_model") == args.model
                and old.get("polish_prompt_version") == PROMPT_VERSION
            ):
                rows[index] = old

    args.cache.parent.mkdir(parents=True, exist_ok=True)
    cache = sqlite3.connect(args.cache)
    cache.execute("CREATE TABLE IF NOT EXISTS polish (cache_key TEXT PRIMARY KEY, text TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    candidates = []
    for i, row in enumerate(rows):
        if row.get("polish_status") in {"polished", "unchanged", "not-applicable"}:
            continue
        visible_source = MARKUP_RE.sub("", row.get("source", ""))
        visible_draft = MARKUP_RE.sub("", row.get("translation", ""))
        if (
            not row.get("translation")
            or row.get("file", "").startswith("_")
            or not ENGLISH_RE.search(visible_source)
            or visible_source.strip() == visible_draft.strip()
        ):
            row["polish_status"] = "not-applicable"
            row["polish_model"] = args.model
            row["polish_prompt_version"] = PROMPT_VERSION
            continue
        candidates.append(i)
    if args.limit > 0:
        candidates = candidates[: args.limit]

    started = time.monotonic()
    failures = 0
    print(f"Pending post-edit records: {len(candidates)}; model: {args.model}", flush=True)
    for completed, index in enumerate(candidates, 1):
        row = rows[index]
        if "draft_translation" not in row:
            row["draft_translation"] = row["translation"]
        material = "\0".join((PROMPT_VERSION, args.model, row["source_sha256"], hashlib.sha256(row["draft_translation"].encode("utf-8")).hexdigest()))
        key = hashlib.sha256(material.encode("utf-8")).hexdigest()
        cached = cache.execute("SELECT text FROM polish WHERE cache_key=?", (key,)).fetchone()
        try:
            if cached:
                polished = cached[0]
            else:
                previous = rows[index - 1] if index > 0 and rows[index - 1].get("file") == row.get("file") else None
                following = rows[index + 1] if index + 1 < len(rows) and rows[index + 1].get("file") == row.get("file") else None
                polished = polish_one(args.api, args.model, row, previous, following, args.timeout, args.num_ctx)
                cache.execute("INSERT OR REPLACE INTO polish(cache_key,text) VALUES(?,?)", (key, polished))
                cache.commit()
            row["translation"] = polished
            row["polish_status"] = "unchanged" if polished == row["draft_translation"] else "polished"
        except (ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError) as error:
            failures += 1
            row["translation"] = row["draft_translation"]
            row["polish_status"] = "polish-error"
            print(f"SKIP {row['id']}: {error}", file=sys.stderr, flush=True)
        row["polish_model"] = args.model
        row["polish_prompt_version"] = PROMPT_VERSION

        if completed % max(1, args.checkpoint_every) == 0 or completed == len(candidates):
            write_catalog(args.output, rows)
        elapsed = max(time.monotonic() - started, 0.001)
        rate = completed / elapsed
        eta = (len(candidates) - completed) / rate / 60 if rate else 0
        print(f"Post-edited {completed}/{len(candidates)} ({completed/len(candidates):.1%}) | {rate:.2f} records/s | ETA {eta:.1f} min", flush=True)

    write_catalog(args.output, rows)
    print(f"Wrote {args.output}; failures: {failures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
