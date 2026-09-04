#!/usr/bin/env python3
"""Inject translated JSONL records into compiled Mware NUT scripts."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path


STRING_PREFIX = b"\x10\x00\x00\x08"
PROTECTED_RE = __import__("re").compile(
    r"(?m)^[ \t]*//【[^\r\n]*(?:\r?\n)?|<[^>]+>|%(?:\d+\$)?[a-zA-Z]|\\[nrt]"
)


def protected(text: str) -> Counter[str]:
    return Counter(PROTECTED_RE.findall(text))


def patch_file(source_path: Path, output_path: Path, records: list[dict]) -> int:
    original = source_path.read_bytes()
    data = bytearray(original)
    replacements = []
    for record in records:
        translation = record.get("translation", "")
        if not translation:
            continue
        source = record["source"]
        if hashlib.sha256(source.encode("utf-8")).hexdigest() != record["source_sha256"]:
            raise ValueError(f"{record['id']}: source hash in catalog is invalid")
        if protected(source) != protected(translation):
            raise ValueError(f"{record['id']}: protected tags differ")
        offset = int(record["offset"])
        if original[offset : offset + 4] != STRING_PREFIX:
            raise ValueError(f"{record['id']}: string prefix not found at offset {offset}")
        old_length = struct.unpack_from("<I", original, offset + 4)[0]
        old_text = original[offset + 8 : offset + 8 + old_length]
        if old_text != source.encode("utf-8"):
            raise ValueError(f"{record['id']}: source bytes differ from NUT")
        replacements.append((offset, old_length, translation.encode("utf-8")))

    for offset, old_length, new_text in sorted(replacements, reverse=True):
        data[offset + 4 : offset + 8 + old_length] = struct.pack("<I", len(new_text)) + new_text

    difference = len(data) - len(original)
    if replacements:
        for header_offset in (8, 12):
            old_value = struct.unpack_from("<I", data, header_offset)[0]
            struct.pack_into("<I", data, header_offset, old_value + difference)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
    return len(replacements)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    grouped: dict[str, list[dict]] = defaultdict(list)
    for line in args.catalog.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("translation"):
            grouped[record["file"]].append(record)

    files = strings = 0
    for relative, records in sorted(grouped.items()):
        count = patch_file(args.source_dir / relative, args.output_dir / relative, records)
        if count:
            files += 1
            strings += count
    print(f"Injected {strings} translations into {files} NUT files at {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
