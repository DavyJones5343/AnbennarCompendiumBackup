"""Extract scripted effects/triggers so mission text can be shown in plain English.

Anbennar missions call scripted effects and triggers by name
(`increase_legitimacy_medium_effect = yes`, `umbral_expansion_mission_trigger =
{ regionname = x }`). The renderer has no entry for those names, so they used
to fall through to a raw `snake_case_key: value` line — script, not English.

EU4 itself resolves them two ways, and so do we:

  1. Many definitions wrap themselves in `custom_tooltip = <loc_key>` /
     `custom_trigger_tooltip = { tooltip = <loc_key> ... }`. That loc string is
     the mod author's own English description — always the best text available.
  2. Otherwise the body can be expanded inline and rendered with the normal
     trigger/effect translator.

Output: scripted_defs.json  {name: {"tip": <english>, "body": <raw script>}}
"""
import glob
import json
import os
import re

from anb_common import EU4_PATH, MOD_PATH, read_file, normalize_text

OUTPUT = os.path.join(os.path.dirname(__file__), "scripted_defs.json")
TRIGGERS_JSON = os.path.join(os.path.dirname(__file__), "mission_triggers.json")

KINDS = ("scripted_effects", "scripted_triggers")
DEF_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\{')
TIP_RE = re.compile(r'\b(?:custom_tooltip|tooltip)\s*=\s*([a-zA-Z_][\w.]*)')
LOC_RE = re.compile(r'^\s*([^#:\s][^:]*):\d*\s+"(.*)"\s*$')

# Bodies longer than this are control-flow soup; the UI can't show them usefully
# and the tooltip (if any) is the better summary anyway.
MAX_BODY = 1200


def parse_definitions(text):
    """Return {name: body} for top-level `name = { ... }` blocks."""
    text = re.sub(r'#.*', '', text)
    defs = {}
    i, n = 0, len(text)
    while i < n:
        m = DEF_RE.search(text, i)
        if not m:
            break
        depth, j = 1, m.end()
        while j < n and depth > 0:
            ch = text[j]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            j += 1
        defs[m.group(1)] = text[m.end():j - 1].strip()
        i = j
    return defs


def load_localisation():
    """Merge base-game then mod English localisation (mod wins)."""
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
                    loc[m.group(1).strip()] = normalize_text(m.group(2))
    return loc


def referenced_names():
    """Names actually used by mission script, so we don't ship 10k unused defs.

    Returns None if mission_triggers.json isn't built yet (keep everything).
    """
    if not os.path.exists(TRIGGERS_JSON):
        return None
    with open(TRIGGERS_JSON, encoding='utf-8') as f:
        missions = json.load(f)
    word_re = re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*')
    used = set()
    for m in missions.values():
        if not isinstance(m, dict):
            continue
        for field in ('trigger_raw', 'effect_raw'):
            used.update(word_re.findall(m.get(field) or ''))
    return used


def main():
    print("Loading localisation...")
    loc = load_localisation()
    print(f"  {len(loc):,} localisation keys")

    print("Parsing scripted definitions...")
    defs = {}
    for root in (EU4_PATH, MOD_PATH):  # mod overrides base
        for kind in KINDS:
            for path in glob.glob(os.path.join(root, "common", kind, "*.txt")):
                text = read_file(path)
                if text:
                    defs.update(parse_definitions(text))
    print(f"  {len(defs):,} definitions")

    used = referenced_names()
    if used is not None:
        print(f"  filtering to the {sum(1 for n in defs if n in used):,} referenced by mission script")

    out = {}
    tipped = 0
    for name, body in defs.items():
        if used is not None and name not in used:
            continue
        entry = {}
        m = TIP_RE.search(body)
        if m:
            tip = loc.get(m.group(1))
            # A tooltip that just echoes its own key name is not English
            if tip and tip.strip() and tip.strip() != m.group(1):
                entry['tip'] = tip.strip()
                tipped += 1
        if len(body) <= MAX_BODY:
            entry['body'] = ' '.join(body.split())
        if entry:
            out[name] = entry

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, separators=(',', ':'), ensure_ascii=False)

    print(f"Wrote {len(out):,} entries ({tipped:,} with author tooltip text)")
    print(f"Output: {OUTPUT} ({os.path.getsize(OUTPUT):,} bytes)")


if __name__ == '__main__':
    main()
