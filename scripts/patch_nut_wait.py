#!/usr/bin/env python3
"""Change one timed method call in compiled Squirrel bytecode."""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
from pathlib import Path


def value_string(value: dict) -> str | None:
    return value.get("String") if isinstance(value, dict) else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("nut_tool", type=Path)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--function", default="ShowLogo")
    parser.add_argument("--method", default="WaitKey")
    parser.add_argument("--old", type=int, required=True)
    parser.add_argument("--new", type=int, required=True)
    parser.add_argument("--occurrence", type=int, default=1)
    args = parser.parse_args()

    json_path = args.output.with_suffix(args.output.suffix + ".json")
    subprocess.run([args.nut_tool, "disasm", args.input, json_path], check=True)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    function = next(
        item for item in data["funcs"] if value_string(item["name"]) == args.function
    )
    literal_indexes = {
        index
        for index, value in enumerate(function["literals"])
        if value_string(value) == args.method
    }
    code = bytearray(function["extra_data"])
    matches = 0
    changed = 0
    for index in range(len(code) // 8 - 1):
        offset = index * 8
        literal, opcode = struct.unpack_from("<iB", code, offset)
        immediate, next_opcode = struct.unpack_from("<iB", code, offset + 8)
        if literal in literal_indexes and opcode == 0x08 and next_opcode == 0x02:
            if immediate == args.old:
                matches += 1
                if matches == args.occurrence:
                    struct.pack_into("<i", code, offset + 8, args.new)
                    changed += 1
    if changed != 1:
        raise SystemExit(
            f"occurrence {args.occurrence} not found; saw {matches} matching calls"
        )
    function["extra_data"] = list(code)
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run([args.nut_tool, "asm", json_path, args.output], check=True)
    json_path.unlink()
    print(f"Patched {args.function}.{args.method}: {args.old} -> {args.new} ms")


if __name__ == "__main__":
    main()
