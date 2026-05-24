"""
Extract formable/playable/event-spawned nation data from Anbennar EU4 mod.

Parses province history, decision files, and country tags to categorize
every country as playable, formable, both, or other.
"""

import os
import re
import json
from collections import defaultdict

MOD_PATH = r"C:\Program Files (x86)\Steam\steamapps\workshop\content\236850\1385440355"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "country_status.json")

PROVINCES_DIR = os.path.join(MOD_PATH, "history", "provinces")
DECISIONS_DIR = os.path.join(MOD_PATH, "decisions")
COUNTRY_TAGS_FILE = os.path.join(MOD_PATH, "common", "country_tags", "anb_countries.txt")


def parse_all_country_tags():
    """Parse anb_countries.txt to get all known country tags."""
    tags = {}
    with open(COUNTRY_TAGS_FILE, "r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            line = line.split("#")[0].strip()
            m = re.match(r'^([A-Z][A-Z0-9]{2})\s*=\s*"(.+)"', line)
            if m:
                tags[m.group(1)] = m.group(2)
    return tags


def parse_province_owners():
    """
    Parse all province history files to find initial owners.
    Returns dict: tag -> number of provinces owned at start.
    """
    owner_counts = defaultdict(int)
    date_re = re.compile(r'^\d+\.\d+\.\d+\s*=')
    owner_re = re.compile(r'^\s*owner\s*=\s*([A-Z][A-Z0-9]{2})')

    for fname in os.listdir(PROVINCES_DIR):
        if not fname.endswith(".txt"):
            continue
        fpath = os.path.join(PROVINCES_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8-sig", errors="replace") as f:
                initial_owner = None
                for line in f:
                    # Stop looking once we hit a date header
                    if date_re.match(line.strip()):
                        break
                    m = owner_re.match(line)
                    if m:
                        initial_owner = m.group(1)
                if initial_owner:
                    owner_counts[initial_owner] += 1
        except Exception as e:
            print(f"  Warning: could not parse {fname}: {e}")

    return dict(owner_counts)


def parse_formable_decisions():
    """
    Parse all decision files for change_tag lines.
    Returns dict: tag -> {"file": filename, "decision": decision_name}
    """
    formables = {}
    decision_name_re = re.compile(r'^\t([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\{')
    change_tag_re = re.compile(r'\bchange_tag\s*=\s*([A-Z][A-Z0-9]{2})')

    for fname in os.listdir(DECISIONS_DIR):
        if not fname.endswith(".txt"):
            continue
        fpath = os.path.join(DECISIONS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8-sig", errors="replace") as f:
                content = f.read()
        except Exception as e:
            print(f"  Warning: could not read {fname}: {e}")
            continue

        # Track which decision name we're inside
        current_decision = None
        brace_depth = 0
        in_country_decisions = False

        for line in content.splitlines():
            stripped = line.strip()

            # Skip comments
            code_part = stripped.split("#")[0].strip()

            if not in_country_decisions:
                if "country_decisions" in code_part and "=" in code_part:
                    in_country_decisions = True
                    brace_depth = code_part.count("{") - code_part.count("}")
                continue

            # Track brace depth
            opens = code_part.count("{")
            closes = code_part.count("}")

            # At depth 1 (inside country_decisions), look for decision names
            if brace_depth == 1 and opens > 0:
                m = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\{', code_part)
                if m:
                    current_decision = m.group(1)

            brace_depth += opens - closes

            # If we've left country_decisions block
            if brace_depth <= 0:
                in_country_decisions = False
                current_decision = None
                continue

            # Look for change_tag
            m = change_tag_re.search(code_part)
            if m:
                tag = m.group(1)
                # Only record the first decision that can form this tag
                if tag not in formables:
                    formables[tag] = {
                        "file": fname,
                        "decision": current_decision or "unknown",
                    }

    return formables


def parse_formable_missions():
    """
    Parse all mission files for change_tag lines.
    Returns dict: tag -> {"file": filename, "decision": mission_name}
    """
    formables = {}
    missions_dir = os.path.join(MOD_PATH, "missions")
    change_tag_re = re.compile(r'\bchange_tag\s*=\s*([A-Z][A-Z0-9]{2})')

    for fname in os.listdir(missions_dir):
        if not fname.endswith(".txt"):
            continue
        fpath = os.path.join(missions_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8-sig", errors="replace") as f:
                content = f.read()
        except Exception as e:
            print(f"  Warning: could not read {fname}: {e}")
            continue

        for m in change_tag_re.finditer(content):
            tag = m.group(1)
            if tag not in formables:
                formables[tag] = {
                    "file": fname,
                    "decision": f"mission in {fname}",
                }

    return formables


def parse_formable_events():
    """
    Parse event files for change_tag lines.
    Returns dict: tag -> {"file": filename, "decision": event_name}
    """
    formables = {}
    events_dir = os.path.join(MOD_PATH, "events")
    change_tag_re = re.compile(r'\bchange_tag\s*=\s*([A-Z][A-Z0-9]{2})')

    if not os.path.isdir(events_dir):
        return formables

    for fname in os.listdir(events_dir):
        if not fname.endswith(".txt"):
            continue
        fpath = os.path.join(events_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8-sig", errors="replace") as f:
                content = f.read()
        except Exception:
            continue

        for m in change_tag_re.finditer(content):
            tag = m.group(1)
            if tag not in formables:
                formables[tag] = {
                    "file": fname,
                    "decision": f"event in {fname}",
                }

    return formables


def main():
    print("Parsing country tags...")
    all_tags = parse_all_country_tags()
    print(f"  Found {len(all_tags)} country tags")

    print("Parsing province owners...")
    province_owners = parse_province_owners()
    print(f"  Found {len(province_owners)} countries owning provinces at start")

    print("Parsing formable decisions...")
    formables = parse_formable_decisions()
    print(f"  Found {len(formables)} formable nations (decisions)")

    print("Parsing formable missions...")
    mission_formables = parse_formable_missions()
    # Merge — decisions take priority
    for tag, info in mission_formables.items():
        if tag not in formables:
            formables[tag] = info
    print(f"  Found {len(mission_formables)} formable nations (missions), {len(formables)} total")

    # NOTE: We deliberately do NOT merge parse_formable_events() into the
    # formables set. In EU4, "formable" means *forms via a decision*. A
    # `change_tag = X` in an event is just a story-driven tag swap (e.g.
    # the Jianlin Independence event, Crown of Bera releases) — those
    # countries should fall through to status='other' and surface via the
    # Event-Spawned UI filter, not be falsely labelled "Formable".
    # Reported by a user finding Jianlin (V22) wrongly labelled formable;
    # affected ~20 nations including Eordand, Pearlsedge, Moredhal,
    # Khasa, Konolkhatep, Maakhibkhii, Salla Cenág.

    # Build output
    result = {}
    counts = defaultdict(int)

    for tag in sorted(all_tags.keys()):
        is_playable = tag in province_owners
        is_formable = tag in formables

        if is_playable and is_formable:
            status = "both"
        elif is_playable:
            status = "playable"
        elif is_formable:
            status = "formable"
        else:
            status = "other"

        counts[status] += 1

        entry = {
            "status": status,
            "provinces_owned": province_owners.get(tag, 0),
            "formable_from": formables[tag]["file"] if is_formable else None,
            "formable_decision": formables[tag]["decision"] if is_formable else None,
        }
        result[tag] = entry

    # Also note tags that own provinces but aren't in anb_countries.txt
    extra_owners = set(province_owners.keys()) - set(all_tags.keys())
    if extra_owners:
        print(f"\n  Note: {len(extra_owners)} province-owning tags not in anb_countries.txt: {sorted(extra_owners)}")

    extra_formables = set(formables.keys()) - set(all_tags.keys())
    if extra_formables:
        print(f"  Note: {len(extra_formables)} formable tags not in anb_countries.txt: {sorted(extra_formables)}")

    # Save
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to {OUTPUT_PATH}")

    # Summary
    print(f"\n=== Summary ({len(result)} total tags) ===")
    print(f"  Playable at 1444 start:  {counts['playable']}")
    print(f"  Formable (not at start): {counts['formable']}")
    print(f"  Both (playable + formable): {counts['both']}")
    print(f"  Other (event/unused):    {counts['other']}")


if __name__ == "__main__":
    main()
