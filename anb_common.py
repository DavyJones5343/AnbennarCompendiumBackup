"""Shared constants and helpers for the Anbennar compendium extractors.

Single source of truth for the mod path, file-encoding fallback chain, and
the stand-in glyph remapping (previously duplicated across three scripts,
which had to be edited in lockstep).
"""
import re

MOD_PATH = r"C:\Program Files (x86)\Steam\steamapps\workshop\content\236850\1385440355"
EU4_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis IV"

ENCODINGS = ("utf-8-sig", "utf-8", "latin-1", "cp1252")

# Anbennar uses stand-in glyphs for Polynesian macron vowels + okina because
# EU4's built-in fonts lack them; the mod remaps via a custom font at runtime.
# We undo that mapping for web display.
# ‘ (U+2018) is deliberately NOT mapped: 2380 of its 2381 uses in loc are
# English opening-quotation marks in event prose.
STANDIN_MAP = str.maketrans({
    '€': 'ā',  # U+20AC -> a-macron
    '‹': 'ū',  # U+2039 -> u-macron
    '‡': 'ō',  # U+2021 -> o-macron
    '•': 'Ā',  # U+2022 -> A-macron (e.g. "Konei Hei Āwhina")
})

COLOR_CODE_RE = re.compile(r'§[A-Za-z!]')


def read_file(filepath):
    """Read a text file using the standard encoding-fallback chain."""
    for enc in ENCODINGS:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def normalize_text(val):
    """Strip EU4 §-color codes and remap mod stand-in glyphs to real Unicode."""
    return COLOR_CODE_RE.sub('', val).translate(STANDIN_MAP)
