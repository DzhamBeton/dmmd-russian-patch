#!/usr/bin/env python3
"""Replace one uncompressed file in an NPK3 archive without rebuilding it."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "python-packages"))

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import zstandard


DMMDR_STEAM_KEY = bytes.fromhex(
    "7593FC9BA5A48319031892BC1AB17237"
    "056AAA63BAD79CD446B1F04155F870EB"
)


@dataclass
class Segment:
    table_offset: int
    offset: int
    aligned_size: int
    real_size: int
    decompressed_size: int


@dataclass
class Entry:
    path: str
    file_size: int
    file_size_offset: int
    sha_offset: int
    segments: list[Segment]


def parse_table(data: bytes) -> list[Entry]:
    entries: list[Entry] = []
    pos = 0
    while pos < len(data):
        if len(data) - pos < 3:
            if any(data[pos:]):
                raise ValueError("unexpected bytes at end of table")
            break
        pos += 1  # segmentation mode
        path_len = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        path = data[pos : pos + path_len].decode("utf-8")
        pos += path_len
        file_size_offset = pos
        file_size = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        sha_offset = pos
        pos += 32
        segment_count = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        segments = []
        for _ in range(segment_count):
            segment_table_offset = pos
            values = struct.unpack_from("<qIII", data, pos)
            pos += 20
            segments.append(Segment(segment_table_offset, *values))
        entries.append(Entry(path, file_size, file_size_offset, sha_offset, segments))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("internal_path")
    parser.add_argument("replacement", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    with args.archive.open("rb") as src:
        header = src.read(0x20)
        if header[:4] != b"NPK3":
            raise SystemExit("only NPK3 archives are supported")
        iv = header[8:24]
        table_size = struct.unpack_from("<I", header, 0x1C)[0]
        encrypted_table = src.read(table_size)

    table = bytearray(unpad(AES.new(DMMDR_STEAM_KEY, AES.MODE_CBC, iv).decrypt(encrypted_table), 16))
    wanted = args.internal_path.replace("\\", "/").lower()
    matches = [entry for entry in parse_table(table) if entry.path.lower() == wanted]
    if len(matches) != 1:
        raise SystemExit(f"expected one matching entry, found {len(matches)}")
    entry = matches[0]
    replacement = args.replacement.read_bytes()
    if len(replacement) > entry.file_size:
        raise SystemExit(
            f"replacement is {len(replacement)} bytes, original slot is {entry.file_size} bytes"
        )
    struct.pack_into("<I", table, entry.file_size_offset, len(replacement))
    table[entry.sha_offset : entry.sha_offset + 32] = hashlib.sha256(replacement).digest()

    encrypted_segments: list[tuple[Segment, bytes]] = []
    read_pos = 0
    compressor = zstandard.ZstdCompressor()
    append_offset = args.archive.stat().st_size
    for segment in entry.segments:
        chunk = replacement[read_pos : read_pos + segment.decompressed_size]
        read_pos += len(chunk)
        compressed = compressor.compress(chunk)
        payload = compressed if len(compressed) < len(chunk) else chunk
        encrypted = AES.new(DMMDR_STEAM_KEY, AES.MODE_CBC, iv).encrypt(pad(payload, 16))
        struct.pack_into("<q", table, segment.table_offset, append_offset)
        struct.pack_into("<I", table, segment.table_offset + 8, len(encrypted))
        struct.pack_into("<I", table, segment.table_offset + 12, len(payload))
        struct.pack_into("<I", table, segment.table_offset + 16, len(chunk))
        encrypted_segments.append((segment, encrypted))
        append_offset += len(encrypted)

    new_encrypted_table = AES.new(DMMDR_STEAM_KEY, AES.MODE_CBC, iv).encrypt(pad(bytes(table), 16))
    if len(new_encrypted_table) != table_size:
        raise SystemExit("encrypted table changed size")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.archive, args.output)
    with args.output.open("r+b") as out:
        out.seek(0x20)
        out.write(new_encrypted_table)
        out.seek(0, 2)
        for _segment, encrypted in encrypted_segments:
            out.write(encrypted)

    print(f"Patched {entry.path}: {entry.file_size} bytes in {len(entry.segments)} segments")
    print(args.output)


if __name__ == "__main__":
    main()
