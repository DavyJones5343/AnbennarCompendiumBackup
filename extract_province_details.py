"""Extract province details (development, trade goods, culture, religion) for map tooltips.

Like extract_province_owners.py, this walks dated history blocks and applies
every change with date <= 1444.11.11, matching how EU4 loads the bookmark.
(A previous version only read the top-level section, so pre-1444 transfers —
e.g. province 2732 Kimanis moving G61 -> G47 on 1443.1.4 — showed stale data
in map tooltips.)
"""
import os
import re
import json

MOD_PATH = r"C:\Program Files (x86)\Steam\steamapps\workshop\content\236850\1385440355"
HISTORY_DIR = os.path.join(MOD_PATH, "history", "provinces")
OUTPUT = os.path.join(os.path.dirname(__file__), "province_details.json")

ENCODINGS = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
BOOKMARK = (1444, 11, 11)

DATE_RE = re.compile(r'^[ \t]*(\d{1,4})\.(\d{1,2})\.(\d{1,2})\s*=\s*\{', re.MULTILINE)

# field key in output -> regex applied to a section of history text
FIELD_RES = {
    't': re.compile(r'base_tax\s*=\s*(\d+)'),
    'p': re.compile(r'base_production\s*=\s*(\d+)'),
    'm': re.compile(r'base_manpower\s*=\s*(\d+)'),
    'g': re.compile(r'trade_goods\s*=\s*(\w+)'),
    'c': re.compile(r'\bculture\s*=\s*(\w+)'),
    'r': re.compile(r'\breligion\s*=\s*(\w+)'),
    'o': re.compile(r'\bowner\s*=\s*(\w+)'),
    'n': re.compile(r'capital\s*=\s*"([^"]+)"'),
}
INT_FIELDS = {'t', 'p', 'm'}


def read_file(filepath):
    for enc in ENCODINGS:
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def apply_fields(section, info):
    """Apply any recognized scalar fields found in this section to info."""
    for key, rx in FIELD_RES.items():
        m = None
        for m in rx.finditer(section):
            pass  # last match in the section wins
        if m:
            val = m.group(1)
            info[key] = int(val) if key in INT_FIELDS else val


def dated_blocks(text):
    """Yield (date_tuple, block_text) for each top-level dated block."""
    pos = 0
    n = len(text)
    while pos < n:
        m = DATE_RE.search(text, pos)
        if not m:
            break
        date = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        depth = 1
        i = m.end()
        while i < n and depth > 0:
            ch = text[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            i += 1
        yield date, text[m.end():i - 1]
        pos = i


def main():
    details = {}
    count = 0

    for fname in os.listdir(HISTORY_DIR):
        if not fname.endswith('.txt'):
            continue

        m = re.match(r'(\d+)', fname)
        if not m:
            continue
        prov_id = m.group(1)

        text = read_file(os.path.join(HISTORY_DIR, fname))
        if not text:
            continue

        # Remove comments before any parsing
        text = re.sub(r'#.*', '', text)

        # Top-level section (before the first dated block) sets the baseline
        first_date = DATE_RE.search(text)
        top = text[:first_date.start()] if first_date else text

        info = {}
        apply_fields(top, info)

        # Then apply each dated block at or before the bookmark, in file order
        if first_date:
            for date, block in dated_blocks(text):
                if date <= BOOKMARK:
                    apply_fields(block, info)

        if info:
            details[prov_id] = info
            count += 1

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(details, f, separators=(',', ':'))

    print(f"Extracted details for {count} provinces")
    print(f"Output: {OUTPUT} ({os.path.getsize(OUTPUT):,} bytes)")


if __name__ == '__main__':
    main()
