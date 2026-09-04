#!/usr/bin/env python3
"""Apply reviewed translations for records a local model cannot preserve safely."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


CATALOG = Path("translations/ru-machine.jsonl")
BACKUP = Path("translations/ru-machine.before-manual-tail.jsonl")

MANUAL = {
    "dm0210.nut:0031": '"Да. Похоже, часть <I>моих</I> данных тоже повреждена..."',
    "dm0250.nut:0084": '"Вот это <I>действительно</I> странно. Эта штука должна управлять Раймом, да? Она создаёт экран, ринг и всё такое."',
    "dm0380.nut:0012": 'Я <I>никогда</I> больше не забуду запереть входную дверь.',
    "dm1240h.nut:0046": 'Он <I>выглядит</I> как Кодзяку, но ведёт себя совсем как другой человек.',
    "dm1310lv.nut:0049": '"И, если честно, я боялся, что случится, если ты узнаешь. Хотя в итоге это оказалось неважно. Тебя всё равно втянули во всё это. За это мне стоит поблагодарить Рюхо."',
    "dm1530.nut:0017": 'Ощущение в волосах тоже начало угасать... вместе с <I>его</I> присутствием внутри меня.',
    "dm1550h.nut:0038": 'Это он выставляет <i>меня</i> странным.',
    "dm2192h.nut:0006": '<I>Горький?</I> И это всё?! Даже сейчас выражение его лица не изменилось.',
    "dm2270.nut:0003": 'Нужно какое-то время понаблюдать за ними и дождаться возможности проскользнуть мимо — по крайней мере, таков <I>мой</I> план. Но едва мы прибываем, Нойз бросается к воротам.',
    "dm2320lv.nut:0031": 'Он не чувствует боли. Не может <I>понять</I> боль.',
    "dm2320lv.nut:0039": 'Он даже представить себе такого не может. По его мнению, причина <I>обязательно</I> должна быть. Неудивительно, что он решил, будто мне нужно его тело или что-то в этом роде.',
    "dm2320lv.nut:0057": '"Ни за что. Мне плевать, чего ты хочешь. Я всё равно это сделаю, сколько бы ты <I>ни</I> жаловался."',
    "dm2320lv.nut:0058": '"Если тебя это раздражает, почему бы тебе хоть раз не подумать о <I>моих</I> чувствах? Тогда, может быть, и я подумаю о твоих."',
    "dm2470scr.nut:0016": '"Почему ты <I>так</I> зациклен на Райме? Я думал, люди тебя не интересуют."',
    "dm2510.nut:0037": '<I>Его</I> присутствие... тоже угасает.',
    "dm2570_vs.nut:0070": '"Ты сказал, что твоя <I>последняя</I> атака всё закончит. Но я ещё не проиграл."',
    "dm3770.nut:0028": '<I>Он</I> тоже словно угасал — то самое <I>присутствие</I>, которое усиливалось всякий раз, когда я применял Скрап.',
    "dm5550.nut:0045": '"Вероятно, свет <I>и</I> звук. Он захочет подчинить как можно больше людей."',
    "dm5580.nut:0047": '"<I>Жизнь</I> — это игра, Аоба. И не только для меня. Каждый борется с каждым за превосходство."',
}


def rebuild(source: str, visible: str) -> str:
    voice = re.match(r"(?s)^(.*?<voice[^>]+>\s*)", source)
    if voice:
        prefix = voice.group(1)
    else:
        prefix = re.match(r"^\s*", source).group(0)
    suffix = re.search(r"\s*$", source).group(0)
    return prefix + visible + suffix


def main() -> None:
    rows = [json.loads(line) for line in CATALOG.read_text(encoding="utf-8").splitlines()]
    shutil.copyfile(CATALOG, BACKUP)
    normalized = manual = 0
    for row in rows:
        target = row.get("translation", "")
        if target and ("\\n" in target or "\\r" in target):
            row["translation"] = target.replace("\\r", "\r").replace("\\n", "\n")
            normalized += 1
        if row["id"] in MANUAL:
            row["translation"] = rebuild(row["source"], MANUAL[row["id"]])
            row["status"] = "reviewed"
            manual += 1
    temporary = CATALOG.with_suffix(CATALOG.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(CATALOG)
    print(f"Normalized escapes: {normalized}; manually finalized: {manual}; backup: {BACKUP}")


if __name__ == "__main__":
    main()
