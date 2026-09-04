#!/usr/bin/env python3
"""Set a boolean in DRAMAtical Murder's compressed common/val.npf."""

from __future__ import annotations

import argparse
import io
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "python-packages"))
import zstandard


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("flag")
    parser.add_argument("value", choices=("0", "1"))
    args = parser.parse_args()

    wrapped = args.input.read_bytes()
    if wrapped[:5] != b"MWCF\0" or wrapped[9:14] != b"BLCK\0":
        raise ValueError("unsupported NPF wrapper")
    raw_size = struct.unpack_from("<I", wrapped, 5)[0]
    packed_size = struct.unpack_from("<I", wrapped, 14)[0]
    if packed_size != len(wrapped) - 22:
        raise ValueError("compressed size in header differs from file")
    with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(wrapped[22:])) as reader:
        raw = bytearray(reader.read())
    if len(raw) != raw_size or struct.unpack_from("<I", wrapped, 18)[0] != raw_size:
        raise ValueError("decompressed size differs from header")

    needle = args.flag.encode("utf-8") + b"\0"
    matches = []
    pos = 0
    while True:
        pos = raw.find(needle, pos)
        if pos < 0:
            break
        value_offset = (pos + len(needle) + 3) & ~3
        matches.append(value_offset)
        pos += len(needle)
    if len(matches) != 1:
        raise ValueError(f"expected one {args.flag!r} entry, found {len(matches)}")
    value_offset = matches[0]
    old_value = struct.unpack_from("<I", raw, value_offset)[0]
    if old_value not in (0, 1):
        raise ValueError(f"current value is not boolean: {old_value}")
    struct.pack_into("<I", raw, value_offset, int(args.value))

    packed = zstandard.ZstdCompressor().compress(bytes(raw))
    header = bytearray(wrapped[:22])
    struct.pack_into("<I", header, 14, len(packed))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(header + packed)
    print(f"{args.flag}: {old_value} -> {args.value}; wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
