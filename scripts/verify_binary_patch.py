#!/usr/bin/env python3
"""Apply and verify a .dmpatch in a disposable output file."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
from pathlib import Path


def digest(path: Path) -> bytes:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            result.update(chunk)
    return result.digest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("patch", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    with args.patch.open("rb") as patch:
        if patch.read(4) != b"DMP1":
            raise SystemExit("invalid patch magic")
        source_size, target_size = struct.unpack("<QQ", patch.read(16))
        source_hash = patch.read(32)
        target_hash = patch.read(32)
        count = struct.unpack("<I", patch.read(4))[0]
        if args.source.stat().st_size != source_size or digest(args.source) != source_hash:
            raise SystemExit("source does not match")
        shutil.copyfile(args.source, args.output)
        with args.output.open("r+b") as output:
            output.truncate(target_size)
            for _ in range(count):
                offset, size = struct.unpack("<QI", patch.read(12))
                data = patch.read(size)
                if len(data) != size:
                    raise SystemExit("truncated patch")
                output.seek(offset)
                output.write(data)
    if digest(args.output) != target_hash:
        raise SystemExit("target hash does not match")
    print(f"Verified {args.patch.name}: {target_hash.hex()}")


if __name__ == "__main__":
    main()
