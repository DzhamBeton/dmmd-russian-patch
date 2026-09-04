#!/usr/bin/env python3
"""Remove leading blank lines added by translation while preserving source layout."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


VOICE_RE = re.compile(r"^(\s*//【[^\r\n]*】\s*\r?\n<voice[^>]+>)")
LEADING_LINES_RE = re.compile(r"(?:[ \t]*\r?\n)*")
PAGE_LEADING_LINES_RE = re.compile(r"(<p>)[ \t]*\r?\n+")


def split_prefix(text: str) -> tuple[str, str]:
    match = VOICE_RE.match(text)
    return (match.group(1), text[match.end():]) if match else ("", text)


def leading_line_count(text: str) -> int:
    return len(re.findall(r"\r?\n", LEADING_LINES_RE.match(text).group(0)))


def trim_to_count(text: str, keep: int) -> str:
    match = LEADING_LINES_RE.match(text)
    remainder = text[match.end():]
    if not remainder:
        return text
    existing = re.findall(r"[ \t]*\r?\n", match.group(0))
    return "".join(existing[:keep]) + remainder


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--patch-source",
        action="store_true",
        help="build a sparse patch that limits existing compiled strings to one leading line",
    )
    parser.add_argument(
        "--strip-all",
        action="store_true",
        help="remove every leading visible line instead of only translator-added lines",
    )
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.catalog.read_text(encoding="utf-8").splitlines()]
    changed = 0
    for row in rows:
        if args.patch_source:
            prefix, visible = split_prefix(row.get("source", ""))
            target = 0 if args.strip_all else 1
            if row.get("file") != "_system.nut" and leading_line_count(visible) > target:
                row["translation"] = prefix + trim_to_count(visible, target)
                row["status"] = "layout-normalized"
                changed += 1
            else:
                row["translation"] = ""
            continue
        translation = row.get("translation", "")
        if not translation:
            continue
        if args.strip_all:
            translation, page_changes = PAGE_LEADING_LINES_RE.subn(r"\1", translation)
            if page_changes:
                row["translation"] = translation
                changed += 1
        _source_prefix, source_visible = split_prefix(row.get("source", ""))
        translation_prefix, translation_visible = split_prefix(translation)
        source_lines = 0 if args.strip_all else leading_line_count(source_visible)
        translation_lines = leading_line_count(translation_visible)
        if translation_lines > source_lines:
            row["translation"] = translation_prefix + trim_to_count(translation_visible, source_lines)
            changed += 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Removed excess leading blank lines from {changed} records; wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
