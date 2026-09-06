#!/usr/bin/env python3
"""Extract one file from a DRAMAtical Murder NPK3 archive."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools" / "python-packages"))

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import zstandard

from patch_npk_file import DMMDR_STEAM_KEY, parse_table


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("internal_path")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    with args.archive.open("rb") as src:
        header = src.read(0x20)
        if header[:4] != b"NPK3":
            raise SystemExit("only NPK3 archives are supported")
        iv = header[8:24]
        table_size = struct.unpack_from("<I", header, 0x1C)[0]
        table = unpad(
            AES.new(DMMDR_STEAM_KEY, AES.MODE_CBC, iv).decrypt(src.read(table_size)),
            16,
        )
        wanted = args.internal_path.replace("\\", "/").lower()
        matches = [entry for entry in parse_table(table) if entry.path.lower() == wanted]
        if len(matches) != 1:
            raise SystemExit(f"expected one matching entry, found {len(matches)}")

        result = bytearray()
        for segment in matches[0].segments:
            src.seek(segment.offset)
            encrypted = src.read(segment.aligned_size)
            payload = unpad(AES.new(DMMDR_STEAM_KEY, AES.MODE_CBC, iv).decrypt(encrypted), 16)
            payload = payload[: segment.real_size]
            if segment.real_size != segment.decompressed_size:
                payload = zstandard.ZstdDecompressor().decompress(
                    payload, max_output_size=segment.decompressed_size
                )
            result.extend(payload)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result[: matches[0].file_size])


if __name__ == "__main__":
    main()
