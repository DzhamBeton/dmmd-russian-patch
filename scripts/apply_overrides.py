#!/usr/bin/env python3
"""Apply reviewed visible-text overrides while retaining protected script markup."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


VOICE_RE = re.compile(r"(?ms)^(\s*//【[^\r\n]*】\s*\r?\n<voice[^>]+>)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--overrides", type=Path, default=Path("config/overrides.json"))
    args = parser.parse_args()

    overrides = json.loads(args.overrides.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in args.catalog.read_text(encoding="utf-8").splitlines()]
    applied = set()
    for row in rows:
        replacement = overrides.get(row["id"])
        if replacement is None:
            continue
        match = VOICE_RE.match(row["source"])
        row["translation"] = match.group(1) + "\n" + replacement if match else replacement
        row["status"] = "reviewed"
        applied.add(row["id"])

    missing = set(overrides) - applied
    if missing:
        raise ValueError("Override IDs not found: " + ", ".join(sorted(missing)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Applied {len(applied)} reviewed overrides; wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

