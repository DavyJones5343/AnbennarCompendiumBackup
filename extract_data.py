"""
Extract Anbennar mod data into a JSON file for the interactive guide.
Parses country tags, names, colors, ideas, missions, lore, history,
cultures, religions, decisions, and events.
"""
import re
import os
import sys
import json
from collections import defaultdict

# Country names contain macron chars (Tākūrekōhukau); Windows consoles default
# to cp1252 and crash on print without this.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from anb_common import MOD_PATH as MOD, read_file, normalize_text

def parse_localisation(filepath):
    """Parse a .yml localisation file into a dict of key -> value."""
    loc = {}
    try:
        content = read_file(filepath)
        if not content:
            return loc
        for line in content.splitlines():
            line = line.strip()
            if line.startswith('l_english') or line.startswith('#') or not line:
                continue
            m = re.match(r'\s*([^:]+):(\d*)\s+"(.*)"', line)
            if m:
                key = m.group(1).strip()
                loc[key] = normalize_text(m.group(3))
    except Exception:
        pass
    return loc

def load_all_localisation():
    """Load all english localisation files."""
    loc_dir = os.path.join(MOD, "localisation")
    all_loc = {}
    for f in os.listdir(loc_dir):
        if f.endswith('_l_english.yml'):
            locs = parse_localisation(os.path.join(loc_dir, f))
            all_loc.update(locs)
    return all_loc

def parse_country_tags():
    """Parse country tags -> file mappings."""
    tags = {}
    tag_file = os.path.join(MOD, "common", "country_tags", "anb_countries.txt")
    with open(tag_file, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or '=' not in line:
                continue
            m = re.match(r'(\w+)\s*=\s*"countries/(.+)"', line)
            if m:
                tags[m.group(1)] = m.group(2)
    return tags

def parse_country_file(tag, filename):
    """Parse a country definition file for color and graphical culture."""
    filepath = os.path.join(MOD, "common", "countries", filename)
    info = {}
    try:
        content = read_file(filepath)
        if content is None:
            return info
        m = re.search(r'color\s*=\s*\{\s*(\d+)\s+(\d+)\s+(\d+)\s*\}', content)
        if m:
            info['color'] = [int(m.group(1)), int(m.group(2)), int(m.group(3))]
        m = re.search(r'graphical_culture\s*=\s*(\w+)', content)
        if m:
            info['graphical_culture'] = m.group(1)
    except Exception:
        pass
    return info

HISTORY_BOOKMARK = (1444, 11, 11)
HISTORY_DATE_RE = re.compile(r'^[ \t]*(\d{1,4})\.(\d{1,2})\.(\d{1,2})\s*=\s*\{', re.MULTILINE)
HISTORY_SCALAR_KEYS = ['government', 'primary_culture', 'religion', 'technology_group', 'capital', 'government_rank']

def strip_nested_blocks(section):
    """Remove nested { ... } sub-blocks (monarch, heir, queen, leader, ...) so
    their inner keys (a ruler's religion/culture) aren't mistaken for country-level ones."""
    prev = None
    while prev != section:
        prev = section
        section = re.sub(r'\{[^{}]*\}', ' ', section)
    return section

def iter_dated_blocks(text):
    """Yield (date_tuple, block_text) for each top-level dated block, brace-aware."""
    pos = 0
    n = len(text)
    while pos < n:
        m = HISTORY_DATE_RE.search(text, pos)
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

def apply_history_section(section, info):
    """Apply country-level keys found in one history section (top or dated block)."""
    section = strip_nested_blocks(section)
    for key in HISTORY_SCALAR_KEYS:
        last = None
        for last in re.finditer(rf'{key}\s*=\s*(\S+)', section):
            pass
        if last:
            info[key] = last.group(1)
    info.setdefault('government_reforms', []).extend(re.findall(r'add_government_reform\s*=\s*(\w+)', section))
    info.setdefault('accepted_cultures', []).extend(re.findall(r'add_accepted_culture\s*=\s*(\w+)', section))
    info.setdefault('historical_rivals', []).extend(re.findall(r'historical_rival\s*=\s*(\w+)', section))
    info.setdefault('historical_friends', []).extend(re.findall(r'historical_friend\s*=\s*(\w+)', section))

def parse_country_history(tag):
    """Parse country history for government, religion, culture, capital, etc.

    EU4 applies every dated history block with date <= the bookmark when
    loading 1444 — so do we. A previous version only read the top-level
    section (and fell back to the WHOLE file, post-1444 included, when the
    top was empty), missing pre-1444 changes; 422 country files have them.
    """
    history_dir = os.path.join(MOD, "history", "countries")
    info = {}
    try:
        for f in os.listdir(history_dir):
            if f.startswith(tag + ' ') or f.startswith(tag + '-') or f.startswith(tag + '_'):
                content = read_file(os.path.join(history_dir, f))
                if content is None:
                    break
                content = re.sub(r'#.*', '', content)

                first_date = HISTORY_DATE_RE.search(content)
                top = content[:first_date.start()] if first_date else content
                apply_history_section(top, info)
                if first_date:
                    for date, block in iter_dated_blocks(content):
                        if date <= HISTORY_BOOKMARK:
                            apply_history_section(block, info)

                # Dedupe (order-preserving) and drop empty list fields so the
                # output shape matches prior behavior
                for k in ('government_reforms', 'accepted_cultures', 'historical_rivals', 'historical_friends'):
                    if info.get(k):
                        info[k] = list(dict.fromkeys(info[k]))
                    else:
                        info.pop(k, None)
                break
    except Exception:
        pass
    return info

# ---- Parsing utilities ----

def find_top_level_blocks(content):
    """Find top-level named blocks: name = { ... }"""
    blocks = []
    i = 0
    while i < len(content):
        if content[i] == '#':
            while i < len(content) and content[i] != '\n':
                i += 1
            continue
        m = re.match(r'(\w+)\s*=\s*\{', content[i:])
        if m:
            name = m.group(1)
            start = i + m.end() - 1
            end = find_matching_brace(content, start)
            if end > start:
                blocks.append((name, content[start+1:end]))
                i = end + 1
                continue
        i += 1
    return blocks

def find_nested_blocks(content, skip_keys):
    """Find nested blocks within a block, skipping certain keys."""
    blocks = []
    i = 0
    while i < len(content):
        if content[i] == '#':
            while i < len(content) and content[i] != '\n':
                i += 1
            continue
        m = re.match(r'(\w+)\s*=\s*\{', content[i:])
        if m:
            name = m.group(1)
            start = i + m.end() - 1
            end = find_matching_brace(content, start)
            if end > start:
                if name not in skip_keys:
                    blocks.append((name, content[start+1:end]))
                i = end + 1
                continue
        m2 = re.match(r'(\w+)\s*=\s*(\S+)', content[i:])
        if m2:
            i += m2.end()
            continue
        i += 1
    return blocks

def extract_block(content, key):
    """Extract a named block's content."""
    pattern = rf'{key}\s*=\s*\{{'
    m = re.search(pattern, content)
    if not m:
        return None
    start = content.index('{', m.start())
    end = find_matching_brace(content, start)
    if end > start:
        return content[start+1:end]
    return None

def find_matching_brace(content, pos):
    """Find the matching closing brace."""
    depth = 0
    i = pos
    while i < len(content):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                return i
        elif content[i] == '#':
            while i < len(content) and content[i] != '\n':
                i += 1
            continue
        i += 1
    return pos

def parse_modifiers(block):
    """Parse modifier = value pairs from a block."""
    mods = []
    if not block:
        return mods
    for m in re.finditer(r'(\w+)\s*=\s*(-?[\d.]+)', block):
        mods.append({'modifier': m.group(1).lower(), 'value': float(m.group(2))})
    return mods

# ---- Ideas ----

def remove_not_blocks(text):
    """Remove NOT = { ... } blocks from text."""
    cleaned = text
    while True:
        not_match = re.search(r'NOT\s*=\s*\{', cleaned)
        if not not_match:
            break
        brace_start = cleaned.index('{', not_match.start())
        brace_end = find_matching_brace(cleaned, brace_start)
        if brace_end > brace_start:
            cleaned = cleaned[:not_match.start()] + cleaned[brace_end+1:]
        else:
            break
    return cleaned


def extract_trigger_info(block):
    """Extract trigger matching info from an idea group's trigger block.

    Returns dict with:
      'tags': list of country tags (e.g. ['Z55'])
      'culture_groups': list of culture group matches (e.g. ['hobgoblin'])
      'reforms': list of government reform matches
      'excluded_tags': tags in NOT blocks (to exclude from group matching)
    """
    trigger_block = extract_block(block, 'trigger')
    if not trigger_block:
        return {'tags': [], 'culture_groups': [], 'reforms': [], 'excluded_tags': []}

    # Extract excluded tags from NOT blocks before removing them
    excluded = []
    for nm in re.finditer(r'NOT\s*=\s*\{([^}]+)\}', trigger_block):
        excluded.extend(re.findall(r'\btag\s*=\s*([A-Z][A-Z0-9]{2})', nm.group(1)))

    cleaned = remove_not_blocks(trigger_block)

    tags = re.findall(r'\btag\s*=\s*([A-Z][A-Z0-9]{2})', cleaned)
    culture_groups = re.findall(r'\bculture_group\s*=\s*(\w+)', cleaned)
    reforms = re.findall(r'\bhas_reform\s*=\s*(\w+)', cleaned)

    return {
        'tags': tags,
        'culture_groups': culture_groups,
        'reforms': reforms,
        'excluded_tags': excluded,
    }


def parse_ideas():
    """Parse all national idea groups.

    Returns (tag_ideas, group_ideas) where:
      tag_ideas: dict tag -> idea_data (direct tag matches)
      group_ideas: list of (idea_data, trigger_info) for culture/reform groups
    """
    ideas_dir = os.path.join(MOD, "common", "ideas")
    tag_ideas = {}
    group_ideas = []

    for fname in os.listdir(ideas_dir):
        if not fname.endswith('.txt'):
            continue
        filepath = os.path.join(ideas_dir, fname)
        content = read_file(filepath)
        if content is None:
            continue

        idea_blocks = find_top_level_blocks(content)
        for name, block in idea_blocks:
            if '_ideas' not in name:
                continue

            trigger_info = extract_trigger_info(block)
            has_tags = bool(trigger_info['tags'])
            has_groups = bool(trigger_info['culture_groups'] or trigger_info['reforms'])

            if not has_tags and not has_groups:
                continue

            start_block = extract_block(block, 'start')
            start_bonuses = parse_modifiers(start_block) if start_block else []
            bonus_block = extract_block(block, 'bonus')
            completion_bonus = parse_modifiers(bonus_block) if bonus_block else []

            skip_keys = {'start', 'bonus', 'trigger', 'free'}
            ideas_list = []
            idea_entries = find_nested_blocks(block, skip_keys)
            for idea_name, idea_block in idea_entries:
                mods = parse_modifiers(idea_block)
                ideas_list.append({'name': idea_name, 'effects': mods})

            idea_data = {
                'group_name': name,
                'traditions': start_bonuses,
                'ambition': completion_bonus,
                'ideas': ideas_list
            }

            # Assign directly for tag-based triggers
            for tag in trigger_info['tags']:
                is_country_specific = name.startswith(tag)
                if tag not in tag_ideas or is_country_specific:
                    tag_ideas[tag] = idea_data

            # Store group-based triggers for later resolution
            if has_groups:
                group_ideas.append((idea_data, trigger_info))

    return tag_ideas, group_ideas

def get_idea_lore(tag, idea_group, loc):
    """Get localized names and descriptions for ideas."""
    if not idea_group:
        return idea_group

    group_name = idea_group.get('group_name', '')
    idea_group['display_name'] = loc.get(group_name, group_name)

    for idea in idea_group.get('ideas', []):
        name = idea['name']
        idea['display_name'] = loc.get(name, name)
        idea['description'] = loc.get(f'{name}_desc', '')

    idea_group['traditions_desc'] = loc.get(f'{group_name}_start', '')
    idea_group['ambition_desc'] = loc.get(f'{group_name}_bonus', '')

    return idea_group

# ---- Missions ----

def parse_missions(tag, loc):
    """Parse mission trees for a given tag."""
    missions_dir = os.path.join(MOD, "missions")
    tag_missions = []

    for fname in os.listdir(missions_dir):
        if not fname.endswith('.txt'):
            continue
        filepath = os.path.join(missions_dir, fname)
        content = read_file(filepath)
        if content is None:
            continue
        if f'tag = {tag}' not in content:
            continue

        groups = find_top_level_blocks(content)
        for group_name, group_block in groups:
            potential = extract_block(group_block, 'potential')
            if not potential or f'tag = {tag}' not in potential:
                if not potential or tag not in potential:
                    continue

            slot_m = re.search(r'slot\s*=\s*(\d+)', group_block)
            slot = int(slot_m.group(1)) if slot_m else 0

            skip = {'slot', 'generic', 'ai', 'has_country_shield', 'potential'}
            mission_blocks = find_nested_blocks(group_block, skip)

            for mission_name, mission_block in mission_blocks:
                pos_m = re.search(r'position\s*=\s*(\d+)', mission_block)
                position = int(pos_m.group(1)) if pos_m else 0
                icon_m = re.search(r'icon\s*=\s*(\w+)', mission_block)
                icon = icon_m.group(1) if icon_m else ''

                req_block = extract_block(mission_block, 'required_missions')
                required = []
                if req_block:
                    required = re.findall(r'(\w+)', req_block)

                title = loc.get(f'{mission_name}_title', loc.get(mission_name, mission_name))
                desc = loc.get(f'{mission_name}_desc', '')

                tag_missions.append({
                    'id': mission_name,
                    'title': title,
                    'desc': desc,
                    'slot': slot,
                    'position': position,
                    'icon': icon,
                    'required_missions': required,
                    'group': group_name
                })

    return tag_missions

# ---- Religions ----

def parse_religions(loc):
    """Parse all religions from religion files."""
    religions = {}
    rel_dir = os.path.join(MOD, "common", "religions")

    for fname in os.listdir(rel_dir):
        if not fname.endswith('.txt'):
            continue
        content = read_file(os.path.join(rel_dir, fname))
        if not content:
            continue

        # Religion groups (top-level blocks)
        groups = find_top_level_blocks(content)
        for group_name, group_block in groups:
            group_display = loc.get(group_name, group_name)

            # Individual religions within the group
            rel_blocks = find_top_level_blocks(group_block)
            for rel_name, rel_block in rel_blocks:
                # Skip non-religion blocks
                if rel_name in ('flags_with_emblem_percentage', 'flag_emblem_index_range',
                                'ai_will_propagate_through_trade', 'center_of_religion',
                                'can_form_personal_unions', 'defender_of_faith',
                                'crusade_name', 'on_convert', 'religious_reforms'):
                    continue

                # Check for color (indicator this is actually a religion)
                color_m = re.search(r'color\s*=\s*\{\s*(\d+)\s+(\d+)\s+(\d+)\s*\}', rel_block)
                if not color_m:
                    continue

                color = [int(color_m.group(1)), int(color_m.group(2)), int(color_m.group(3))]
                display = loc.get(rel_name, rel_name)

                # Country modifiers
                country_block = extract_block(rel_block, 'country')
                mods = parse_modifiers(country_block) if country_block else []

                # Allowed conversions
                conv_block = extract_block(rel_block, 'allowed_conversion')
                conversions = re.findall(r'(\w+)', conv_block) if conv_block else []

                # Description
                desc = loc.get(f'{rel_name}_desc', '')

                religions[rel_name] = {
                    'name': display,
                    'id': rel_name,
                    'group': group_display,
                    'group_id': group_name,
                    'color': color,
                    'modifiers': mods,
                    'allowed_conversions': conversions,
                    'description': desc,
                }

    return religions

# ---- Decisions ----

def parse_decisions_for_tag(tag, loc):
    """Find decisions associated with a country tag."""
    decisions_dir = os.path.join(MOD, "decisions")
    tag_decisions = []

    for fname in os.listdir(decisions_dir):
        if not fname.endswith('.txt'):
            continue
        filepath = os.path.join(decisions_dir, fname)
        content = read_file(filepath)
        if not content:
            continue
        if f'tag = {tag}' not in content:
            continue

        # Parse decision blocks
        top_blocks = find_top_level_blocks(content)
        for block_name, block_content in top_blocks:
            if block_name != 'country_decisions':
                continue
            decisions = find_top_level_blocks(block_content)
            for dec_name, dec_block in decisions:
                # Verify this decision references our tag
                if f'tag = {tag}' not in dec_block:
                    continue

                title = loc.get(dec_name, loc.get(f'{dec_name}_title', dec_name))
                desc = loc.get(f'{dec_name}_desc', '')

                tag_decisions.append({
                    'id': dec_name,
                    'title': title,
                    'desc': desc,
                })

    return tag_decisions

# ---- Events ----

def parse_events_for_tag(tag, loc):
    """Find events associated with a country tag (just titles and descriptions)."""
    events_dir = os.path.join(MOD, "events")
    tag_events = []
    seen_ids = set()

    for fname in os.listdir(events_dir):
        if not fname.endswith('.txt'):
            continue
        filepath = os.path.join(events_dir, fname)
        content = read_file(filepath)
        if not content:
            continue
        if f'tag = {tag}' not in content:
            continue

        # Find event blocks (country_event and province_event)
        blocks = find_top_level_blocks(content)
        for block_name, block_content in blocks:
            if block_name not in ('country_event', 'province_event'):
                continue

            # Get event ID
            id_m = re.search(r'id\s*=\s*([\w.]+)', block_content)
            if not id_m:
                continue
            event_id = id_m.group(1)
            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)

            # Check if this specific event references our tag
            # (the file might have events for multiple tags)
            trigger_block = extract_block(block_content, 'trigger')

            # Get title and desc
            title_m = re.search(r'title\s*=\s*"?([\w.]+)"?', block_content)
            desc_m = re.search(r'desc\s*=\s*([\w.]+)', block_content)

            title_key = title_m.group(1) if title_m else ''
            desc_key = desc_m.group(1) if desc_m else ''

            title = loc.get(title_key, title_key)
            desc = loc.get(desc_key, '')

            # Count options
            option_count = len(re.findall(r'\n\s*option\s*=\s*\{', block_content))

            tag_events.append({
                'id': event_id,
                'type': block_name,
                'title': title,
                'desc': desc[:300] + ('...' if len(desc) > 300 else ''),
                'options': option_count,
            })

    return tag_events


def extract_all_event_names(loc):
    """Build global event_id -> localized title mapping from ALL event files."""
    events_dir = os.path.join(MOD, "events")
    event_names = {}
    for fname in os.listdir(events_dir):
        if not fname.endswith('.txt'):
            continue
        content = read_file(os.path.join(events_dir, fname))
        if not content:
            continue
        blocks = find_top_level_blocks(content)
        for block_name, block_content in blocks:
            if block_name not in ('country_event', 'province_event'):
                continue
            id_m = re.search(r'id\s*=\s*([\w.]+)', block_content)
            if not id_m:
                continue
            event_id = id_m.group(1)
            title_m = re.search(r'title\s*=\s*"?([\w.]+)"?', block_content)
            if title_m:
                title_key = title_m.group(1)
                title = loc.get(title_key, title_key)
                event_names[event_id] = title
    return event_names


# ---- Culture groups ----

def parse_culture_groups():
    """Parse culture groups and map cultures to groups."""
    culture_file = os.path.join(MOD, "common", "cultures", "anb_cultures.txt")
    culture_to_group = {}

    try:
        content = read_file(culture_file)
        if not content:
            return culture_to_group

        groups = find_top_level_blocks(content)
        for group_name, group_block in groups:
            cultures = find_nested_blocks(group_block, {
                'graphical_culture', 'second_graphical_culture',
                'male_names', 'female_names', 'dynasty_names'
            })
            for culture_name, _ in cultures:
                culture_to_group[culture_name] = group_name
    except:
        pass

    return culture_to_group

# ---- Bookmarks (regions) ----

def parse_bookmarks(loc):
    """Parse bookmarks for region grouping."""
    bookmarks_dir = os.path.join(MOD, "common", "bookmarks")
    bookmarks = []

    for fname in sorted(os.listdir(bookmarks_dir)):
        if not fname.endswith('.txt'):
            continue
        content = read_file(os.path.join(bookmarks_dir, fname))
        if not content:
            continue

        blocks = find_top_level_blocks(content)
        for bname, bblock in blocks:
            name_m = re.search(r'name\s*=\s*"(\w+)"', bblock)
            desc_m = re.search(r'desc\s*=\s*"(\w+)"', bblock)
            if not name_m:
                continue

            bm_name = loc.get(name_m.group(1), name_m.group(1))
            bm_desc = loc.get(desc_m.group(1), '') if desc_m else ''

            # Countries in this bookmark
            countries = re.findall(r'country\s*=\s*(\w+)', bblock)
            easy = re.findall(r'easy_country\s*=\s*(\w+)', bblock)

            bookmarks.append({
                'name': bm_name,
                'description': bm_desc,
                'countries': list(dict.fromkeys(countries)),  # unique, preserve order
                'easy_countries': easy,
                'file': fname,
            })

    return bookmarks

# ---- Main ----

def main():
    print("Loading localisation...")
    loc = load_all_localisation()
    print(f"  Loaded {len(loc)} localisation keys")

    print("Parsing country tags...")
    tags = parse_country_tags()
    print(f"  Found {len(tags)} countries")

    print("Parsing culture groups...")
    culture_groups = parse_culture_groups()
    print(f"  Found {len(culture_groups)} culture mappings")

    print("Parsing national ideas...")
    all_ideas, group_ideas = parse_ideas()
    print(f"  Found {len(all_ideas)} tag-specific idea groups, {len(group_ideas)} group idea sets")

    print("Parsing religions...")
    religions = parse_religions(loc)
    print(f"  Found {len(religions)} religions")

    print("Parsing bookmarks...")
    bookmarks = parse_bookmarks(loc)
    print(f"  Found {len(bookmarks)} bookmarks/regions")

    print("Building country data...")
    countries = {}

    for tag, filename in tags.items():
        name = loc.get(tag, filename.replace('.txt', ''))
        adj = loc.get(f'{tag}_ADJ', '')

        country_info = parse_country_file(tag, filename)
        history = parse_country_history(tag)

        culture = history.get('primary_culture', '')
        culture_group = culture_groups.get(culture, '')
        culture_display = loc.get(culture, culture)
        culture_group_display = loc.get(culture_group, culture_group)

        religion = history.get('religion', '')
        religion_display = loc.get(religion, religion)

        gov = history.get('government', '')
        gov_display = loc.get(gov, gov)

        tech = history.get('technology_group', '')
        tech_display = loc.get(tech, tech)

        # Government reforms
        reforms = history.get('government_reforms', [])
        reform_names = [loc.get(r, r) for r in reforms]

        # Accepted cultures
        accepted = history.get('accepted_cultures', [])
        accepted_names = [loc.get(c, c) for c in accepted]

        # Historical rivals/friends
        rivals = history.get('historical_rivals', [])
        friends = history.get('historical_friends', [])

        # Ideas — first check tag-specific, then fall back to group ideas
        ideas = all_ideas.get(tag, None)
        if not ideas:
            # Try matching group ideas by culture_group or government reform
            for gi_data, gi_trigger in group_ideas:
                # Check excluded tags
                if tag in gi_trigger.get('excluded_tags', []):
                    continue
                # Check culture group match
                if culture_group and culture_group in gi_trigger.get('culture_groups', []):
                    ideas = gi_data
                    break
                # Check reform match
                if reforms:
                    for r in reforms:
                        if r in gi_trigger.get('reforms', []):
                            ideas = gi_data
                            break
                    if ideas:
                        break
        if ideas:
            ideas = get_idea_lore(tag, ideas, loc)

        # Missions
        print(f"  [{tag}] {name}...")
        missions = parse_missions(tag, loc)

        # Decisions
        decisions = parse_decisions_for_tag(tag, loc)

        # Events
        events = parse_events_for_tag(tag, loc)

        # Check if flag exists
        flag_exists = os.path.exists(os.path.join(
            os.path.dirname(__file__), 'flags', f'{tag}.png'))

        # Get the religion data for this country
        rel_data = religions.get(religion, None)

        countries[tag] = {
            'tag': tag,
            'name': name,
            'adjective': adj,
            'color': country_info.get('color', [128, 128, 128]),
            'graphical_culture': country_info.get('graphical_culture', ''),
            'government': gov_display,
            'government_rank': int(history.get('government_rank', 1)),
            'government_reforms': reform_names,
            'religion': religion_display,
            'religion_id': religion,
            'primary_culture': culture_display,
            'culture_group': culture_group_display,
            'accepted_cultures': accepted_names,
            'technology_group': tech_display,
            'historical_rivals': rivals,
            'historical_friends': friends,
            'ideas': ideas,
            'missions': missions,
            'has_missions': len(missions) > 0,
            'mission_count': len(missions),
            'decisions': decisions,
            'decision_count': len(decisions),
            # Full event objects were 26 MB (54% of the JSON) and the UI only
            # ever used the count — keep the count, drop the bodies.
            'event_count': len(events),
            'has_flag': flag_exists,
        }

    # Summary stats
    with_missions = sum(1 for c in countries.values() if c['has_missions'])
    with_ideas = sum(1 for c in countries.values() if c['ideas'])
    with_decisions = sum(1 for c in countries.values() if c['decision_count'] > 0)
    with_events = sum(1 for c in countries.values() if c['event_count'] > 0)

    print(f"\nSummary:")
    print(f"  {len(countries)} countries total")
    print(f"  {with_missions} countries with unique missions")
    print(f"  {with_ideas} countries with unique national ideas")
    print(f"  {with_decisions} countries with decisions")
    print(f"  {with_events} countries with events")
    print(f"  {len(religions)} religions")

    # Save main data
    output_path = os.path.join(os.path.dirname(__file__), 'anbennar_data.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(countries, f, ensure_ascii=False, indent=1)
    print(f"\nCountry data saved to {output_path}")
    print(f"File size: {os.path.getsize(output_path) / 1024 / 1024:.1f} MB")

    # Save religions
    rel_path = os.path.join(os.path.dirname(__file__), 'religions_data.json')
    with open(rel_path, 'w', encoding='utf-8') as f:
        json.dump(religions, f, ensure_ascii=False, indent=1)
    print(f"Religion data saved to {rel_path}")

    # Save bookmarks
    bm_path = os.path.join(os.path.dirname(__file__), 'bookmarks_data.json')
    with open(bm_path, 'w', encoding='utf-8') as f:
        json.dump(bookmarks, f, ensure_ascii=False, indent=1)
    print(f"Bookmark data saved to {bm_path}")

    # Extract and save global event names
    print("Extracting all event names...")
    event_names = extract_all_event_names(loc)
    print(f"  Found {len(event_names)} events with titles")
    en_path = os.path.join(os.path.dirname(__file__), 'event_names.json')
    with open(en_path, 'w', encoding='utf-8') as f:
        json.dump(event_names, f, ensure_ascii=False, separators=(',', ':'))
    print(f"Event names saved to {en_path}")

if __name__ == '__main__':
    main()
