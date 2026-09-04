#!/usr/bin/env python3
"""Replace exact strings in compiled Mware NUT files without recompiling them."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


STRING_PREFIX = b"\x10\x00\x00\x08"


def replace_strings(path: Path, replacements: dict[str, str]) -> int:
    original = path.read_bytes()
    data = bytearray(original)
    found: list[tuple[int, int, bytes]] = []
    pos = 0
    while True:
        pos = original.find(STRING_PREFIX, pos)
        if pos < 0:
            break
        if pos + 8 <= len(original):
            length = struct.unpack_from("<I", original, pos + 4)[0]
            end = pos + 8 + length
            if 0 < length <= 1_000_000 and end <= len(original):
                try:
                    value = original[pos + 8 : end].decode("utf-8")
                except UnicodeDecodeError:
                    pass
                else:
                    if value in replacements:
                        found.append((pos, length, replacements[value].encode("utf-8")))
        pos += 1

    for offset, old_length, new_value in reversed(found):
        data[offset + 4 : offset + 8 + old_length] = struct.pack("<I", len(new_value)) + new_value

    if found:
        delta = len(data) - len(original)
        for header_offset in (8, 12):
            struct.pack_into("<I", data, header_offset, struct.unpack_from("<I", data, header_offset)[0] + delta)
        path.write_bytes(data)
    return len(found)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("pairs", nargs="+", metavar="OLD=NEW")
    args = parser.parse_args()
    pairs = dict(pair.split("=", 1) for pair in args.pairs)
    count = replace_strings(args.path, pairs)
    print(f"Replaced {count} string(s) in {args.path}")
    if not count:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
