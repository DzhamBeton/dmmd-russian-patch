#!/usr/bin/env python3
"""Validate translation catalog IDs, hashes, tags, and translation coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


PROTECTED_RE = re.compile(r"(?m)^[ \t]*//【[^\r\n]*(?:\r?\n)?|<[^>]+>|%(?:\d+\$)?[a-zA-Z]|\\[nrt]")
LATIN_WORD_RE = re.compile(r"\b[A-Za-z]{3,}\b")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    args = parser.parse_args()
    errors = []
    warnings = []
    ids = set()
    translated = 0
    rows = [json.loads(line) for line in args.catalog.read_text(encoding="utf-8").splitlines()]
    for line_number, row in enumerate(rows, 1):
        label = row.get("id", f"line {line_number}")
        if label in ids:
            errors.append(f"{label}: duplicate ID")
        ids.add(label)
        source = row.get("source", "")
        expected_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if row.get("source_sha256") != expected_hash:
            errors.append(f"{label}: source hash mismatch")
        target = row.get("translation", "")
        if not target:
            continue
        translated += 1
        if Counter(PROTECTED_RE.findall(source)) != Counter(PROTECTED_RE.findall(target)):
            errors.append(f"{label}: protected tags differ")
        visible_target = PROTECTED_RE.sub("", target)
        if visible_target.strip() == PROTECTED_RE.sub("", source).strip():
            warnings.append(f"{label}: translation equals source")
        elif LATIN_WORD_RE.search(visible_target):
            warnings.append(f"{label}: contains Latin words")

    print(f"Records: {len(rows)}; translated: {translated}; errors: {len(errors)}; warnings: {len(warnings)}")
    for message in errors[:50]:
        print("ERROR", message)
    for message in warnings[:50]:
        print("WARN ", message)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
