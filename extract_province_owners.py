"""Extract 1444 province ownership from Anbennar mod history files.

Properly walks dated blocks and applies all owner changes with
date <= 1444.11.11, matching how EU4 actually loads the bookmark.
A previous bug stopped at the first date header and used the initial
top-level owner — so provinces with a pre-1444 transfer (like 2732
Kimanis, transferred from G61 to G47 on 1443.1.4) were credited to
the wrong tag.
"""
import os
import re
import json

MOD_PATH = r"C:\Program Files (x86)\Steam\steamapps\workshop\content\236850\1385440355"
HISTORY_DIR = os.path.join(MOD_PATH, "history", "provinces")
OUTPUT = os.path.join(os.path.dirname(__file__), "province_owners.json")

ENCODINGS = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
BOOKMARK = (1444, 11, 11)  # EU4 standard 1444 start

DATE_RE = re.compile(r'^[ \t]*(\d{1,4})\.(\d{1,2})\.(\d{1,2})\s*=\s*\{', re.MULTILINE)
OWNER_RE = re.compile(r'^[ \t]*owner\s*=\s*([A-Z][A-Z0-9]{2})\b', re.MULTILINE)


def read_file(filepath):
    for enc in ENCODINGS:
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def find_owner_at_bookmark(text, bookmark=BOOKMARK):
    """Return tag that owns this province at the bookmark date.

    Walks dated blocks `YYYY.MM.DD = { ... owner = X ... }` and applies
    the last owner change whose date is <= bookmark. Falls back to the
    top-level owner before the first dated block when no later change applies.
    """
    # 1) Initial owner from the top-level section (before any date block)
    first_date = DATE_RE.search(text)
    top = text[:first_date.start()] if first_date else text
    m = OWNER_RE.search(top)
    current_owner = m.group(1) if m else None
    if not first_date:
        return current_owner

    # 2) Walk dated blocks, tracking brace depth so nested constructs are
    #    contained within the right date. Apply each block's owner if date<=bookmark.
    pos = first_date.start()
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
        block = text[m.end():i - 1]
        if date <= bookmark:
            # Last owner = X within this block wins (rare, but be safe)
            owners_in_block = OWNER_RE.findall(block)
            if owners_in_block:
                current_owner = owners_in_block[-1]
        pos = i
    return current_owner


def main():
    province_to_owner = {}
    count = 0

    for fname in os.listdir(HISTORY_DIR):
        if not fname.endswith('.txt'):
            continue

        m = re.match(r'(\d+)', fname)
        if not m:
            continue
        prov_id = int(m.group(1))

        text = read_file(os.path.join(HISTORY_DIR, fname))
        if not text:
            continue

        owner = find_owner_at_bookmark(text)
        if owner:
            province_to_owner[prov_id] = owner
            count += 1

    # Invert: tag -> [province_ids]
    tag_to_provinces = {}
    for prov_id, tag in province_to_owner.items():
        if tag not in tag_to_provinces:
            tag_to_provinces[tag] = []
        tag_to_provinces[tag].append(prov_id)

    # Sort province lists
    for tag in tag_to_provinces:
        tag_to_provinces[tag].sort()

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(tag_to_provinces, f, separators=(',', ':'))

    print(f"Extracted {count} owned provinces across {len(tag_to_provinces)} countries")
    print(f"Output: {OUTPUT} ({os.path.getsize(OUTPUT):,} bytes)")


if __name__ == '__main__':
    main()
