#!/usr/bin/env python3
"""Patch TextBox.rowSpace LOADINT values in compiled Squirrel bytecode."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


TRAP = 0x50415254
OT_NULL = 0x01000001
OT_INTEGER = 0x05000002
OT_FLOAT = 0x05000004
OT_STRING = 0x08000010
OP_LOAD = 0x01
OP_LOADINT = 0x02


def patch(data: bytearray, target: str, old: int, new: int) -> int:
    pos = 26  # SCRP header followed by RIQS/version
    changed = 0

    def read_u32() -> int:
        nonlocal pos
        value = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        return value

    def read_value():
        nonlocal pos
        tag = read_u32()
        if tag == OT_NULL:
            return None
        if tag == OT_INTEGER:
            value = struct.unpack_from("<i", data, pos)[0]
            pos += 4
            return value
        if tag == OT_FLOAT:
            value = struct.unpack_from("<f", data, pos)[0]
            pos += 4
            return value
        if tag == OT_STRING:
            length = read_u32()
            value = bytes(data[pos : pos + length]).decode("utf-8")
            pos += length
            return value
        raise ValueError(f"unknown value tag {tag:#x} at {pos - 4:#x}")

    def expect_trap() -> None:
        at = pos
        value = read_u32()
        if value != TRAP:
            raise ValueError(f"expected TRAP at {at:#x}, got {value:#x}")

    def function() -> None:
        nonlocal pos, changed
        expect_trap()
        read_value()  # source
        read_value()  # function name
        expect_trap()
        counts = [read_u32() for _ in range(8)]
        expect_trap()
        literals = [read_value() for _ in range(counts[0])]
        expect_trap()
        for _ in range(counts[1]):
            read_value()
        expect_trap()
        for _ in range(counts[2]):
            read_u32()
            read_value()
            read_value()
        expect_trap()
        for _ in range(counts[3]):
            read_value()
            read_u32()
            read_u32()
            read_u32()
        expect_trap()
        pos += counts[4] * 8  # line info
        expect_trap()
        pos += counts[5] * 4  # default parameter indexes
        expect_trap()
        instruction_start = pos
        instruction_count = counts[6]
        target_indexes = {i for i, value in enumerate(literals) if value == target}
        for index in range(instruction_count - 1):
            current = instruction_start + index * 8
            following = current + 8
            literal, opcode = struct.unpack_from("<iB", data, current)
            immediate, next_opcode = struct.unpack_from("<iB", data, following)
            if literal in target_indexes and opcode == OP_LOAD and next_opcode == OP_LOADINT:
                if immediate != old:
                    raise ValueError(
                        f"{target} at instruction {index} has value {immediate}, expected {old}"
                    )
                struct.pack_into("<i", data, following, new)
                changed += 1
        pos += instruction_count * 8
        expect_trap()
        for _ in range(counts[7]):
            function()
        pos += 6  # function tail

    function()
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--target", default="rowSpace")
    parser.add_argument("--old", type=int, required=True)
    parser.add_argument("--new", type=int, required=True)
    parser.add_argument("--expected", type=int, required=True)
    args = parser.parse_args()
    data = bytearray(args.input.read_bytes())
    count = patch(data, args.target, args.old, args.new)
    if count != args.expected:
        raise ValueError(f"patched {count} values, expected {args.expected}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"Patched {count} {args.target} values: {args.old} -> {args.new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
