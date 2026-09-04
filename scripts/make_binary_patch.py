#!/usr/bin/env python3
"""Create a simple exact-source binary patch consumed by the Windows installer."""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path


MAGIC = b"DMP1"
BLOCK_SIZE = 1024 * 1024


def sha256(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(BLOCK_SIZE):
            digest.update(chunk)
    return digest.digest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    source_size = args.source.stat().st_size
    target_size = args.target.stat().st_size
    records: list[tuple[int, bytes]] = []

    with args.source.open("rb") as source, args.target.open("rb") as target:
        offset = 0
        common_size = min(source_size, target_size)
        while offset < common_size:
            size = min(BLOCK_SIZE, common_size - offset)
            old = source.read(size)
            new = target.read(size)
            if old != new:
                records.append((offset, new))
            offset += size
        if target_size > common_size:
            target.seek(common_size)
            while chunk := target.read(BLOCK_SIZE):
                records.append((offset, chunk))
                offset += len(chunk)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as patch:
        patch.write(MAGIC)
        patch.write(struct.pack("<QQ", source_size, target_size))
        patch.write(sha256(args.source))
        patch.write(sha256(args.target))
        patch.write(struct.pack("<I", len(records)))
        for offset, data in records:
            patch.write(struct.pack("<QI", offset, len(data)))
            patch.write(data)

    changed = sum(len(data) for _, data in records)
    print(f"{args.output}: {len(records)} blocks, {changed} changed bytes")


if __name__ == "__main__":
    main()
