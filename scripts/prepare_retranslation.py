#!/usr/bin/env python3
"""Clear only missing or technically unsafe translations for a retry pass."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import Counter
from pathlib import Path


PROTECTED_RE = re.compile(
    r"(?m)^[ \t]*//【[^\r\n]*(?:\r?\n)?|<[^>]+>|%(?:\d+\$)?[a-zA-Z]|\\[nrt]"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.catalog.read_text(encoding="utf-8").splitlines()]
    missing = invalid = 0
    for row in rows:
        target = row.get("translation", "")
        if not target:
            missing += 1
            row["status"] = "translation-error"
            continue
        if Counter(PROTECTED_RE.findall(row.get("source", ""))) != Counter(
            PROTECTED_RE.findall(target)
        ):
            invalid += 1
            row["translation"] = ""
            row["status"] = "translation-error"

    args.backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.catalog, args.backup)
    temporary = args.catalog.with_suffix(args.catalog.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(args.catalog)
    print(f"Prepared retry: {missing} missing, {invalid} invalid; backup: {args.backup}")


if __name__ == "__main__":
    main()
