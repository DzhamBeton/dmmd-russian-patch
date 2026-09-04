#!/usr/bin/env python3
"""Export translatable UTF-8 strings from compiled Mware NUT scripts."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


STRING_PREFIX = b"\x10\x00\x00\x08"


def strings_from_nut(data: bytes):
    pos = 0
    ordinal = 0
    while True:
        pos = data.find(STRING_PREFIX, pos)
        if pos < 0:
            return
        if pos + 8 <= len(data):
            length = struct.unpack_from("<I", data, pos + 4)[0]
            end = pos + 8 + length
            if 0 < length <= 1_000_000 and end <= len(data):
                raw = data[pos + 8 : end]
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    pass
                else:
                    if not any(ord(char) < 10 for char in text):
                        yield ordinal, pos, text
                        ordinal += 1
        pos += 1


def is_translatable(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped.startswith("media/script/"):
        return False
    # Engine identifiers contain no whitespace. Dialogue, narration and UI text do.
    return any(char.isspace() for char in stripped)


def export(input_dir: Path, output: Path) -> tuple[int, int]:
    files = 0
    records = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        for path in sorted(input_dir.rglob("*.nut")):
            relative = path.relative_to(input_dir).as_posix()
            selected = [item for item in strings_from_nut(path.read_bytes()) if is_translatable(item[2])]
            if not selected:
                continue
            files += 1
            for index, (_ordinal, offset, source) in enumerate(selected, 1):
                record = {
                    "id": f"{relative}:{index:04d}",
                    "file": relative,
                    "offset": offset,
                    "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                    "source": source,
                    "translation": "",
                    "status": "new",
                }
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                records += 1
    return files, records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    files, records = export(args.input_dir, args.output)
    print(f"Exported {records} records from {files} NUT files to {args.output}")


if __name__ == "__main__":
    main()
