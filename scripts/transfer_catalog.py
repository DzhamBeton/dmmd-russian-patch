#!/usr/bin/env python3
"""Transfer translations to another game build by file and source occurrence."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("translated", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    candidates: dict[tuple[str, str], deque[dict]] = defaultdict(deque)
    for record in read_jsonl(args.translated):
        if record.get("translation"):
            candidates[(record["file"], record["source"])].append(record)

    target = read_jsonl(args.target)
    matched = 0
    for record in target:
        matches = candidates.get((record["file"], record["source"]))
        if matches:
            source = matches.popleft()
            record["translation"] = source["translation"]
            record["status"] = source.get("status", "transferred")
            record["transferred_from"] = source["id"]
            for key in ("draft_translation", "polish_status", "polish_model", "polish_prompt_version"):
                if key in source:
                    record[key] = source[key]
            matched += 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for record in target:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Transferred {matched}/{len(target)} records; missing {len(target) - matched}")


if __name__ == "__main__":
    main()
