#!/usr/bin/env python3
"""Flag translated dialogue likely to overflow the Mware text box."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


VOICE_RE = re.compile(r"<voice\b")
MARKUP_RE = re.compile(r"(?m)^[ \t]*//【[^\r\n]*(?:\r?\n)?|<[^>]+>")


def units(text: str) -> float:
    # Tahoma Cyrillic capitals and wide letters consume more horizontal space.
    value = 0.0
    for char in text:
        if char in "ЖШЩФЮМW@%":
            value += 1.45
        elif char in " .,!:;'|ijlI()[]«»":
            value += 0.55
        else:
            value += 1.0
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--line-units", type=float, default=36.0)
    parser.add_argument("--max-lines", type=int, default=3)
    args = parser.parse_args()
    warnings = 0
    for raw in args.catalog.read_text(encoding="utf-8").splitlines():
        row = json.loads(raw)
        target = row.get("translation", "")
        if not target or not VOICE_RE.search(row.get("source", "")):
            continue
        visible = MARKUP_RE.sub("", target).strip()
        estimated = sum(max(1, math.ceil(units(line) / args.line_units)) for line in visible.splitlines())
        if estimated > args.max_lines:
            warnings += 1
            print(f"{row['id']}: ~{estimated} lines, {len(visible)} chars: {visible}")
    print(f"Layout warnings: {warnings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
