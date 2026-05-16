"""Parse EU4 Anbennar startup screen lore text into JSON."""
import json
import re
import os
import unicodedata
import glob

MOD_PATH = r"C:\Program Files (x86)\Steam\steamapps\workshop\content\236850\1385440355"
LOC_DIR = os.path.join(MOD_PATH, "localisation")
OUTPUT = os.path.join(os.path.dirname(__file__), "startup_lore.json")

DATA_FILE = os.path.join(os.path.dirname(__file__), "anbennar_data.json")
REGIONS_FILE = os.path.join(os.path.dirname(__file__), "regions_data.json")

with open(DATA_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)
with open(REGIONS_FILE, 'r', encoding='utf-8') as f:
    regions = json.load(f)

tag_to_name = {tag: info.get('name', '') for tag, info in data.items()}

# Read ALL localisation files
content = ""
for yml_file in glob.glob(os.path.join(LOC_DIR, "*_l_english.yml")):
    with open(yml_file, 'r', encoding='utf-8-sig') as f:
        content += f.read() + "\n"

# Parse titles and descriptions from all files
titles = {}
descriptions = {}

for match in re.finditer(r'string_start_title_(\w+):\s*\d*\s*"(.+)"\s*$', content, re.MULTILINE):
    titles[match.group(1).lower()] = match.group(2)

for match in re.finditer(r'string_start_(\w+):\s*\d*\s*"(.+)"\s*$', content, re.MULTILINE):
    key = match.group(1).lower()
    if key.startswith('title_'):
        continue
    descriptions[key] = match.group(2)

# Anbennar stand-in glyphs -> real Unicode (see extract_data.py for context)
STANDIN_MAP = str.maketrans({
    '€': 'ā',  # € -> ā
    '‹': 'ū',  # ‹ -> ū
    '‡': 'ō',  # ‡ -> ō
    '•': 'Ā',  # • -> Ā
    # ‘ (U+2018) intentionally not mapped — overwhelmingly English left-quote
})

def clean_text(text):
    text = re.sub(r'§[A-Za-z!]', '', text).translate(STANDIN_MAP)
    text = text.replace('\\n', '\n')
    text = text.replace('\\"', '"')
    text = re.sub(r'£\w+£', '', text)
    text = re.sub(r'\$[^$]+\$', '', text)
    text = re.sub(r'\[Root\.[\w.]+\]\s*', '', text)
    text = re.sub(r'\[[\w.]+\]\s*', '', text)
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def normalize(s):
    """Strip accents and everything except lowercase alphanumeric for fuzzy matching."""
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]', '', s.lower())

# Build multiple lookup tables for matching
norm_to_tag = {}
for tag, info in data.items():
    name = info.get('name', '')
    if name:
        norm = normalize(name)
        norm_to_tag[norm] = tag
        if norm.startswith('the'):
            norm_to_tag[norm[3:]] = tag
    norm_to_tag[normalize(tag)] = tag

# Skip keys - region/religion primers, bookmarks, game mechanic text
SKIP_PATTERNS = {'primer', 'religion', 'bookmark', 'tag_', 'generic', 'government_',
                 'serpentspine_description', 'serpentspine', 'forbidden_plains_description',
                 'forbidden_plains', 'triunic_explanation'}
# Region-level descriptions to skip (not country-specific)
SKIP_EXACT = {'cannor', 'escann', 'bulwar', 'haless', 'sarhal', 'rahen',
              'cannor_description', 'africa_americas_description', 'sarhal_description',
              'deepwoods', 'deepwoods_description'}

result = {}
unmatched = []

# Track generic lore entries for later assignment
GENERIC_KEYS = {
    'dwarovar_adventurer_description': 'dwarven_adventurer',
    'dwarovar_remnant_description': 'dwarven_remnant',
    'cave_goblin_description': 'cave_goblin',
    'northern_isles_description': 'lake_federation_north',
    'southern_isles_description': 'lake_federation_south',
    'forbidden_lands': 'centaur',
    'ogre_kingdoms_description': 'ogre',
    'escann_adventurer': 'escann_adventurer',
    'escann_nonadventurer': 'escann_nonadventurer',
    'deepwoods_elves': 'deepwoods_elves',
    'deepwoods_goblins': 'deepwoods_goblins',
    'deepwoods_orcs': 'deepwoods_orcs',
    'hobgoblins': 'hobgoblins',
    'lizardfolk': 'lizardfolk',
}
generic_lore = {}

for key, text in descriptions.items():
    # Capture generic lore entries
    if key in GENERIC_KEYS:
        generic_key = GENERIC_KEYS[key]
        title_key = key.replace('_description', '')
        generic_lore[generic_key] = {
            'title': clean_text(titles.get(title_key, titles.get(key, ''))),
            'lore': clean_text(text),
        }
        continue

    if any(p in key for p in SKIP_PATTERNS):
        continue
    if key in SKIP_EXACT:
        continue

    norm_key = normalize(key)
    norm_key_clean = re.sub(r'description$', '', norm_key)

    tag = None
    for try_key in [norm_key, norm_key_clean]:
        if try_key in norm_to_tag:
            tag = norm_to_tag[try_key]
            break

    if not tag:
        best_match = None
        best_len = 0
        for norm_name, t in norm_to_tag.items():
            if len(norm_name) < 3:
                continue
            if norm_key.startswith(norm_name) or norm_name.startswith(norm_key_clean):
                if len(norm_name) > best_len:
                    best_len = len(norm_name)
                    best_match = t
            elif norm_key_clean == norm_name:
                best_match = t
                break
        tag = best_match

    if tag:
        title_key = key.replace('_description', '')
        title = titles.get(key, titles.get(title_key, ''))
        result[tag] = {
            'title': clean_text(title),
            'lore': clean_text(text),
        }
    else:
        unmatched.append(key)

# Now assign generic lore to countries that don't have specific lore
generic_assigned = 0
for tag, info in data.items():
    if tag in result:
        continue  # Already has specific lore

    reforms = info.get('government_reforms', [])
    culture_group = info.get('culture_group', '')
    primary_culture = info.get('primary_culture', '')
    reg = regions.get(tag, {})
    superregion = reg.get('superregion_name', '')

    assigned_key = None

    # Dwarven Adventurers
    if 'Dwarovar Adventurer Company' in reforms:
        assigned_key = 'dwarven_adventurer'
    # Dwarven Remnants (check for specific reform patterns)
    elif any('remnant' in r.lower() for r in reforms) or (
        culture_group == 'Dwarven' and any('hold' in r.lower() for r in reforms)):
        assigned_key = 'dwarven_remnant'
    # Cave Goblins in Serpentspine
    elif culture_group == 'Goblin' and 'Serpentspine' in superregion:
        assigned_key = 'cave_goblin'
    # Centaurs
    elif culture_group == 'Centaur':
        assigned_key = 'centaur'
    # Ogres (Fathide Ogre culture group)
    elif 'Ogre' in culture_group:
        assigned_key = 'ogre'
    # Lake Federation - Khamgunai/Triunic peoples
    elif culture_group in ('Triunic',) or primary_culture in ('Khamgunai', 'Metsamic', 'Zabatlari'):
        if 'Forbidden' in superregion or 'Lake' in reg.get('region_name', ''):
            assigned_key = 'lake_federation_north'
    # Escann adventurers (non-dwarven adventurer companies in Escann)
    elif any(r in ('Aelantir Adventurer Company', 'Adventurer Council', 'Adventurer Kingdom', 'Sponsored Adventurers') for r in reforms):
        assigned_key = 'escann_adventurer'
    # Hobgoblins (non-Command hobgoblin countries)
    elif culture_group == 'Hobgoblin':
        assigned_key = 'hobgoblins'
    # Deepwoods elves
    elif culture_group == 'Elven' and ('Deepwood' in reg.get('region_name', '') or 'Deepwood' in superregion):
        assigned_key = 'deepwoods_elves'
    # Deepwoods goblins
    elif culture_group == 'Goblin' and ('Deepwood' in reg.get('region_name', '') or 'Deepwood' in superregion):
        assigned_key = 'deepwoods_goblins'
    # Deepwoods orcs
    elif culture_group == 'Orcish' and ('Deepwood' in reg.get('region_name', '') or 'Deepwood' in superregion):
        assigned_key = 'deepwoods_orcs'
    # Lizardfolk
    elif 'Lizardfolk' in culture_group or 'lizardfolk' in primary_culture.lower():
        assigned_key = 'lizardfolk'

    if assigned_key and assigned_key in generic_lore:
        entry = generic_lore[assigned_key].copy()
        # Substitute country name into generic titles that had [Root.GetName]
        country_name = info.get('name', '')
        if country_name and entry['title']:
            # Clean up titles that end with dangling "of the" etc from stripped [Root.GetName]
            entry['title'] = re.sub(r'\s+of\s+the\s*$', '', entry['title'])
            entry['title'] = re.sub(r'\s+of\s*$', '', entry['title'])
            entry['title'] = entry['title'].strip()
            if entry['title']:
                entry['title'] = f"{entry['title']}: {country_name}"
            else:
                entry['title'] = country_name
        result[tag] = entry
        generic_assigned += 1

with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"Parsed {len(descriptions)} descriptions from all localisation files")
print(f"Matched {len(result) - generic_assigned} specific + {generic_assigned} generic = {len(result)} total")
print(f"Generic lore categories found: {list(generic_lore.keys())}")
print(f"Output: {OUTPUT} ({os.path.getsize(OUTPUT):,} bytes)")
if unmatched:
    print(f"Unmatched keys ({len(unmatched)}): {unmatched}")
print(f"\nSample matches:")
for tag in list(result.keys())[:5]:
    print(f"  {tag} ({tag_to_name.get(tag, '?')}): {result[tag]['lore'][:80]}...")
