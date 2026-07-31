"""Build an identifier -> display-name lookup so the UI never shows raw ids.

Mission text is full of internal identifiers: `has_building = mage_tower`,
`religion = regent_court`, `primary_culture = wood_elf`, `trade_goods =
precursor_relics`. Previously the renderer just swapped underscores for spaces
("mage tower"), or left the id as-is. Both read as game files, not English.

Every one of these has a proper name in the game's own localisation — usually
under the bare id, buildings under a `building_` prefix. This walks the
definition folders to learn which identifiers exist in each namespace, then
resolves each through localisation (mod overriding base game).

Output: display_names.json  {identifier: "Display Name"}
"""
import glob
import json
import os
import re

from anb_common import EU4_PATH, MOD_PATH, read_file, normalize_text

OUTPUT = os.path.join(os.path.dirname(__file__), "display_names.json")

# (folder under common/, loc-key prefix, nesting depth of the identifiers)
#   depth 1 -> `id = { ... }` at top level          (buildings, reforms, goods)
#   depth 2 -> `group = { id = { ... } }`           (religions, cultures)
NAMESPACES = [
    ("buildings", "building_", 1),
    ("tradegoods", "", 1),
    ("government_reforms", "", 1),
    ("estates", "", 1),
    ("religions", "", 2),
    ("cultures", "", 2),
    ("institutions", "", 1),
    ("disasters", "", 1),
    ("great_projects", "", 1),
    ("policies", "", 1),
    ("ideas", "", 1),
]

DEF_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\{')
LOC_RE = re.compile(r'^\s*([^#:\s][^:]*):\d*\s+"(.*)"\s*$')

# Keys inside definition blocks that are settings, never identifiers
NOISE = {
    'color', 'country', 'province', 'trigger', 'effect', 'potential', 'allow',
    'ai_will_do', 'modifier', 'on_start', 'on_end', 'male_names', 'female_names',
    'dynasty_names', 'graphical_culture', 'country_as_secondary', 'papacy',
    'religious_reforms', 'on_convert', 'heretic', 'orthodox_icons', 'aspects',
    'blessings', 'fervor', 'personal_deity', 'harmonized_modifier', 'crusade_name',
    'build_trigger', 'can_use_trade_post', 'center_of_trade', 'manufactory',
    'bonus', 'chance', 'random_list', 'primary', 'second_names',
}


def top_level_defs(text, depth):
    """Collect definition names at the requested nesting depth."""
    text = re.sub(r'#.*', '', text)
    names, stack, i, n = set(), 0, 0, len(text)
    while i < n:
        ch = text[i]
        if ch == '}':
            stack = max(0, stack - 1)
            i += 1
            continue
        m = DEF_RE.match(text, i)
        if m:
            stack += 1
            if stack == depth and m.group(1) not in NOISE:
                names.add(m.group(1))
            i = m.end()
            continue
        if ch == '{':
            stack += 1
        i += 1
    return names


def load_localisation():
    """Base game first, then mod so mod strings win."""
    loc = {}
    for root in (EU4_PATH, MOD_PATH):
        loc_dir = os.path.join(root, "localisation")
        if not os.path.isdir(loc_dir):
            continue
        for path in glob.glob(os.path.join(loc_dir, "**", "*_l_english.yml"), recursive=True):
            text = read_file(path)
            if not text:
                continue
            for line in text.splitlines():
                if not line.strip() or line.lstrip().startswith(('#', 'l_english')):
                    continue
                m = LOC_RE.match(line)
                if m:
                    loc[m.group(1).strip()] = normalize_text(m.group(2)).strip()
    return loc


def main():
    print("Loading localisation...")
    loc = load_localisation()
    print(f"  {len(loc):,} keys")

    names = {}
    for folder, prefix, depth in NAMESPACES:
        ids = set()
        for root in (EU4_PATH, MOD_PATH):
            for path in glob.glob(os.path.join(root, "common", folder, "**", "*.txt"), recursive=True):
                text = read_file(path)
                if text:
                    ids |= top_level_defs(text, depth)

        found = 0
        for ident in ids:
            display = loc.get(prefix + ident) or loc.get(ident)
            # Skip non-answers: missing, self-referential, or leftover markup
            if not display or display == ident or '$' in display or '[' in display:
                continue
            names[ident] = display
            found += 1
        print(f"  {folder:20s} {found:5,} named / {len(ids):5,} ids")

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(names, f, separators=(',', ':'), ensure_ascii=False)

    print(f"\nWrote {len(names):,} display names")
    print(f"Output: {OUTPUT} ({os.path.getsize(OUTPUT):,} bytes)")


if __name__ == '__main__':
    main()
