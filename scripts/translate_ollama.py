#!/usr/bin/env python3
"""Batch-translate exported DRAMAtical Murder strings through local Ollama."""

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


PROMPT_VERSION = "dmmd-ru-v7"
PROTECTED_RE = re.compile(
    r"(?m)^[ \t]*//【[^\r\n]*(?:\r?\n)?|<[^>]+>|%(?:\d+\$)?[a-zA-Z]|\\[nrt]"
)
TOKEN_RE = re.compile(r"__DMMD_TOKEN_\d{3}__")
SPEAKER_RE = re.compile(r"<voice\s+name='([^']+)'")
VOICE_PREFIX_RE = re.compile(r"(?ms)^(\s*(?://【[^\r\n]*\r?\n)?<voice[^>]+>\s*)")


def protect(text: str) -> tuple[str, list[str]]:
    values: list[str] = []

    def replace(match: re.Match[str]) -> str:
        token = f"__DMMD_TOKEN_{len(values):03d}__"
        values.append(match.group(0))
        return token

    return PROTECTED_RE.sub(replace, text), values


def restore(text: str, values: list[str]) -> str:
    expected = [f"__DMMD_TOKEN_{i:03d}__" for i in range(len(values))]
    found = TOKEN_RE.findall(text)
    if Counter(found) != Counter(expected):
        raise ValueError(f"protected tokens changed: expected {expected}, got {found}")
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


def build_system_prompt(style: str, glossary: dict[str, str]) -> str:
    terms = "\n".join(f"- {source} → {target}" for source, target in glossary.items())
    return f"""Ты литературный переводчик визуальной новеллы DRAMAtical Murder с английского на русский.

Контекст мира: повествование обычно ведётся от первого лица Аобы. Рэн — его Оллмейт,
разумный робот-компаньон в облике синей собаки; выражения вроде "ball/lump of fur" могут
описательно обозначать Рэна, а не безымянный предмет. Coil — носимое устройство связи.
Входные блоки идут подряд из одной сцены. Осмысливай их совместно и избегай буквальных,
неестественных конструкций, но возвращай отдельный перевод для каждого ID.

Правила:
{style.strip()}

Глоссарий (соблюдай написание):
{terms}

Верни только JSON-объект вида {{"translations":[{{"id":"...","text":"..."}}]}}.
Верни ровно одну запись для каждого входного ID и сохрани порядок. Не добавляй комментариев."""


def translate_batch(
    api: str,
    model: str,
    system_prompt: str,
    records: list[dict],
    speakers: dict[str, str],
    num_ctx: int,
    timeout: int,
) -> dict[str, str]:
    protected: dict[str, tuple[str, list[str]]] = {}
    inputs = []
    for record in records:
        prefix_match = VOICE_PREFIX_RE.match(record["source"])
        prefix = prefix_match.group(1) if prefix_match else ""
        visible_source = record["source"][len(prefix) :]
        text, tokens = protect(visible_source)
        protected[record["id"]] = (prefix, tokens)
        match = SPEAKER_RE.search(record["source"])
        speaker = "рассказчик (Аоба)"
        if match:
            speaker = speakers.get(match.group(1), match.group(1))
        inputs.append({"id": record["id"], "speaker": speaker, "text": text})

    response = post_json(
        api.rstrip("/") + "/api/chat",
        {
            "model": model,
            "stream": False,
            "think": False,
            "format": "json",
            "options": {"temperature": 0.2, "num_ctx": num_ctx},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "Переведи следующие блоки:\n" + json.dumps(inputs, ensure_ascii=False),
                },
            ],
        },
        timeout,
    )
    content = response["message"]["content"]
    parsed = json.loads(content)
    items = parsed.get("translations")
    if not isinstance(items, list):
        raise ValueError("Ollama response has no translations array")
    result = {}
    for item in items:
        record_id = item.get("id")
        if record_id in protected and isinstance(item.get("text"), str):
            prefix, tokens = protected[record_id]
            result[record_id] = prefix + restore(item["text"], tokens)
    expected_ids = [record["id"] for record in records]
    if set(result) != set(expected_ids):
        raise ValueError(f"response IDs differ: expected {expected_ids}, got {list(result)}")
    return result


TRANSLATION_ERRORS = (ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError)


def translate_resilient(
    api: str,
    model: str,
    system_prompt: str,
    records: list[dict],
    speakers: dict[str, str],
    num_ctx: int,
    timeout: int,
) -> dict[str, str]:
    """Retry malformed responses, then split a troublesome batch recursively."""
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            return translate_batch(api, model, system_prompt, records, speakers, num_ctx, timeout)
        except TRANSLATION_ERRORS as error:
            last_error = error
    if len(records) == 1:
        assert last_error is not None
        raise last_error
    middle = len(records) // 2
    print(f"Retrying malformed batch as {middle}+{len(records) - middle}", flush=True)
    left = translate_resilient(
        api, model, system_prompt, records[:middle], speakers, num_ctx, timeout
    )
    right = translate_resilient(
        api, model, system_prompt, records[middle:], speakers, num_ctx, timeout
    )
    left.update(right)
    return left


def open_cache(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        """CREATE TABLE IF NOT EXISTS translations (
        cache_key TEXT PRIMARY KEY, translation TEXT NOT NULL, model TEXT NOT NULL,
        prompt_version TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    return connection


def cache_key(record: dict, model: str) -> str:
    material = "\0".join((PROMPT_VERSION, model, record["source_sha256"]))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


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
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--api", default="http://127.0.0.1:11434")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="Translate at most N pending records")
    parser.add_argument("--file", help="Only translate records from this NUT filename")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--num-ctx", type=int, default=8192)
    parser.add_argument("--checkpoint-every", type=int, default=100, help="Save output every N records")
    parser.add_argument("--cache", type=Path, default=Path("work/cache/ollama.sqlite3"))
    parser.add_argument("--glossary", type=Path, default=Path("config/glossary.json"))
    parser.add_argument("--style", type=Path, default=Path("config/style.md"))
    parser.add_argument("--speakers", type=Path, default=Path("config/speakers.json"))
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines()]
    if args.output.exists() and args.output.resolve() != args.input.resolve():
        existing = {
            row["id"]: row
            for row in (
                json.loads(line)
                for line in args.output.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        }
        resumed = 0
        for row in rows:
            old = existing.get(row["id"])
            if old and old.get("source_sha256") == row.get("source_sha256") and old.get("translation"):
                row["translation"] = old["translation"]
                row["status"] = old.get("status", "machine-translated")
                resumed += 1
        if resumed:
            print(f"Resumed {resumed} existing translations from {args.output}", flush=True)
    glossary = json.loads(args.glossary.read_text(encoding="utf-8"))
    style = args.style.read_text(encoding="utf-8")
    speakers = json.loads(args.speakers.read_text(encoding="utf-8"))
    system_prompt = build_system_prompt(style, glossary)
    connection = open_cache(args.cache)

    pending = [row for row in rows if not row.get("translation")]
    if args.file:
        pending = [row for row in pending if row["file"] == args.file]
    if args.limit > 0:
        pending = pending[: args.limit]

    completed = 0
    failures: list[str] = []
    started_at = time.monotonic()
    print(f"Pending: {len(pending)}; model: {args.model}; batch size: {args.batch_size}", flush=True)
    for start in range(0, len(pending), args.batch_size):
        batch = pending[start : start + args.batch_size]
        translations: dict[str, str] = {}
        missing = []
        for record in batch:
            key = cache_key(record, args.model)
            cached = connection.execute(
                "SELECT translation FROM translations WHERE cache_key = ?", (key,)
            ).fetchone()
            if cached:
                translations[record["id"]] = cached[0]
            else:
                missing.append(record)
        if missing:
            try:
                fresh = translate_resilient(
                    args.api, args.model, system_prompt, missing, speakers, args.num_ctx, args.timeout
                )
            except TRANSLATION_ERRORS as error:
                print(f"Batch failed at {start}; retrying records separately: {error}", file=sys.stderr)
                fresh = {}
                for record in missing:
                    try:
                        fresh.update(
                            translate_resilient(
                                args.api,
                                args.model,
                                system_prompt,
                                [record],
                                speakers,
                                args.num_ctx,
                                args.timeout,
                            )
                        )
                    except TRANSLATION_ERRORS as record_error:
                        record["status"] = "translation-error"
                        failures.append(record["id"])
                        print(f"SKIP {record['id']}: {record_error}", file=sys.stderr, flush=True)
            translations.update(fresh)
            for record in missing:
                if record["id"] not in fresh:
                    continue
                connection.execute(
                    "INSERT OR REPLACE INTO translations(cache_key,translation,model,prompt_version) VALUES(?,?,?,?)",
                    (cache_key(record, args.model), fresh[record["id"]], args.model, PROMPT_VERSION),
                )
            connection.commit()
        for record in batch:
            if record["id"] not in translations:
                continue
            record["translation"] = translations[record["id"]]
            record["status"] = "machine-translated"
        completed += len(batch)
        if completed % max(1, args.checkpoint_every) < len(batch) or completed == len(pending):
            write_catalog(args.output, rows)
        elapsed = max(time.monotonic() - started_at, 0.001)
        rate = completed / elapsed
        remaining = (len(pending) - completed) / rate if rate else 0
        print(
            f"Translated {completed}/{len(pending)} "
            f"({completed / len(pending):.1%}) | {rate:.2f} records/s | ETA {remaining / 60:.1f} min",
            flush=True,
        )

    write_catalog(args.output, rows)
    print(f"Wrote {args.output}")
    if failures:
        print(
            f"Completed with {len(failures)} skipped records. "
            "Filter status 'translation-error' in the editor or run translation again.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
