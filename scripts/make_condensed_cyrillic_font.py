#!/usr/bin/env python3
"""Create a Tahoma variant with horizontally condensed Cyrillic glyphs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENDORED = ROOT / "tools" / "python-packages"
if VENDORED.exists():
    sys.path.insert(0, str(VENDORED))

from fontTools.pens.transformPen import TransformPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont


CYRILLIC_RANGES = (
    (0x0400, 0x052F),
    (0x1C80, 0x1C8F),
    (0x2DE0, 0x2DFF),
    (0xA640, 0xA69F),
)


def is_cyrillic(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in CYRILLIC_RANGES)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", type=float, default=0.90)
    parser.add_argument(
        "--line-scale",
        type=float,
        default=1.0,
        help="scale horizontal line metrics without scaling glyph outlines",
    )
    args = parser.parse_args()

    if not 0.75 <= args.scale <= 1.0:
        parser.error("--scale must be between 0.75 and 1.0")
    if not 0.10 <= args.line_scale <= 1.0:
        parser.error("--line-scale must be between 0.10 and 1.0")

    font = TTFont(args.source)
    if "CFF " not in font:
        raise SystemExit("This tool currently expects a CFF-flavoured OpenType font")

    cmap = {}
    for table in font["cmap"].tables:
        if table.isUnicode():
            cmap.update(table.cmap)
    glyph_names = sorted({name for cp, name in cmap.items() if is_cyrillic(cp)})

    top_dict = font["CFF "].cff.topDictIndex[0]
    char_strings = top_dict.CharStrings
    glyph_set = font.getGlyphSet()
    hmtx = font["hmtx"].metrics
    transformed = 0

    for glyph_name in glyph_names:
        if glyph_name not in char_strings or glyph_name not in hmtx:
            continue
        old_width, old_lsb = hmtx[glyph_name]
        new_width = max(1, round(old_width * args.scale))
        pen = T2CharStringPen(new_width, glyph_set)
        glyph_set[glyph_name].draw(TransformPen(pen, (args.scale, 0, 0, 1, 0, 0)))
        char_strings[glyph_name] = pen.getCharString(
            private=top_dict.Private,
            globalSubrs=font["CFF "].cff.GlobalSubrs,
        )
        hmtx[glyph_name] = (new_width, round(old_lsb * args.scale))
        transformed += 1

    if args.line_scale != 1.0:
        hhea = font["hhea"]
        hhea.ascent = round(hhea.ascent * args.line_scale)
        hhea.descent = round(hhea.descent * args.line_scale)
        hhea.lineGap = round(hhea.lineGap * args.line_scale)

        os2 = font["OS/2"]
        os2.sTypoAscender = round(os2.sTypoAscender * args.line_scale)
        os2.sTypoDescender = round(os2.sTypoDescender * args.line_scale)
        os2.sTypoLineGap = round(os2.sTypoLineGap * args.line_scale)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    font.save(args.output)
    print(f"Condensed {transformed} Cyrillic glyphs to {args.scale:.0%}")
    print(f"Scaled line metrics to {args.line_scale:.0%}")
    print(args.output)


if __name__ == "__main__":
    main()
