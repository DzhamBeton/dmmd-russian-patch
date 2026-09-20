#!/usr/bin/env python3
"""Merge the first manual-review batch into the polished DMMD catalog."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


VOICE_GAP_RE = re.compile(r"(<voice[^>]+>)[\r\n]+")
VOICE_PREFIX_RE = re.compile(r"(?ms)^((?:\s*//【[^\r\n]*】\s*\r?\n)?\s*<voice[^>]+>)")

# Obvious spelling, punctuation, grammar, and accidental-repeat fixes found during review.
# Everything not listed here is retained exactly as submitted by the human editor.
CORRECTIONS = {
    "dm0020.nut:0002": '"Ох... эм... У меня есть один вопрос."',
    "dm0020.nut:0008": '"Оу, нет... ну, эм..."',
    "dm0020.nut:0015": '"О, спасибо, очень приятно. Кстати, сэр, у меня есть предложение, которое, возможно, вас заинтересует."',
    "dm0020.nut:0019": '"И как раз сейчас мы оформляем предзаказы, но только для наших постоянных клиентов. Вас это заинтересовало?"',
    "dm0020.nut:0020": '"Похоже, они будут пользоваться особым спросом. Не удивлюсь, если их сразу же раскупят. Если вы оформите предзаказ, то точно их не упустите."',
    "dm0020.nut:0033": "Даже зная, чего они добиваются, иметь дело с клиентами, которым нужно что-то <I>помимо</I> запчастей, — это такая головная боль.",
    "dm0020.nut:0038": "Сначала я просто не обращал внимания, но со временем это начало раздражать.",
    "dm0020.nut:0040": "С тех пор мой голос помогает мне поднимать продажи. Этот звонок — хороший тому пример.\nПричём странно, что при личной встрече такого не происходит.",
    "dm0020.nut:0042": "Все они уходили, даже не догадываясь, что говорили по телефону именно со мной.",
    "dm0020.nut:0044": '«Фух... Ладно. Скоро вернётся управляющий».',
    "dm0030.nut:0009": "Потянувшись, я взглянул на цифровые часы на стойке.",
    "dm0030.nut:0014": "Койл — это что-то вроде мобильного телефона, только гораздо более продвинутое.",
    "dm0030.nut:0018": "Это какая-то новая вирусная реклама?<K>\nТипа для взрослых?",
    "dm0030.nut:0022": "Я падаю со стула, и что-то тяжёлое приземляется мне на спину.",
    "dm0030.nut:0024": '"Аоба весь открыт!"',
    "dm0030.nut:0027": '"Ах вы, мелкие...!"',
    "dm0030.nut:0033": "Нао, должно быть, заглянул в мой Койл. Остальные двое забрались мне на спину, пытаясь подсмотреть.",
    "dm0030.nut:0035": '"Слезьте с меня, придурки!"',
    "dm0030.nut:0042": '"Я знаю! Давайте арестуем Аобу за то, что он стрёмный извращенец!"',
    "dm0030.nut:0046": '"Вааааааааааааааааах!"',
    "dm0030.nut:0047": "Я вскакиваю, сбрасывая их с себя. Не собираюсь сдерживаться только потому, что они дети.",
    "dm0030.nut:0054": "Экран моего Койла привлекает моё внимание.\n<I>Скачивание завершено.</I> Что за хрень?",
    "dm0030.nut:0060": '"Фух, сегодня пришлось побегать с доставками."',
    "dm0030.nut:0061": "Это мистер Хага, владелец.",
}


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line]


def without_voice_gap(text: str) -> str:
    return VOICE_GAP_RE.sub(r"\1", text)


def replace_visible(text: str, visible: str) -> str:
    match = VOICE_PREFIX_RE.match(text)
    return (match.group(1) if match else "") + visible


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("submitted", type=Path)
    parser.add_argument("--base", type=Path, default=Path("translations/ru-polished.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("translations/ru-manual-reviewed.jsonl"))
    args = parser.parse_args()

    base_rows = read_rows(args.base)
    submitted_rows = read_rows(args.submitted)
    submitted = {row["id"]: row for row in submitted_rows}
    if len(submitted) != len(submitted_rows) or set(submitted) != {row["id"] for row in base_rows}:
        raise SystemExit("Submitted catalog IDs do not exactly match the base catalog")

    changed = 0
    for row in base_rows:
        edited = submitted[row["id"]]
        candidate = without_voice_gap(edited.get("translation", ""))
        original = without_voice_gap(row.get("translation", ""))
        if candidate == original:
            continue
        if row["id"] in CORRECTIONS:
            candidate = replace_visible(candidate, CORRECTIONS[row["id"]])
        # A proofreading correction may deliberately restore the original text.
        if candidate == row.get("translation", ""):
            continue
        row["translation"] = candidate
        row["status"] = "reviewed"
        row["manual_review"] = "friend-pass-1"
        changed += 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for row in base_rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Merged {changed} substantive edits into {args.output}")
    print(f"Applied {len(CORRECTIONS)} proofreading corrections")


if __name__ == "__main__":
    main()
