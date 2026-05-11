"""Extract province names from EU4 localisation files (base + Anbennar overrides)."""
import os
import re
import json

EU4_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis IV"
MOD_PATH = r"C:\Program Files (x86)\Steam\steamapps\workshop\content\236850\1385440355"
OUTPUT = os.path.join(os.path.dirname(__file__), "province_names.json")

ENCODINGS = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
PROV_RE = re.compile(r'\s*PROV(\d+):\d*\s+"(.*)"')


def read_file(filepath):
    for enc in ENCODINGS:
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def scan_loc_dir(loc_dir, province_names, label):
    if not os.path.isdir(loc_dir):
        print(f"  [{label}] missing: {loc_dir}")
        return 0
    added = 0
    for root, _, files in os.walk(loc_dir):
        for fname in files:
            if not fname.endswith("_l_english.yml"):
                continue
            text = read_file(os.path.join(root, fname))
            if not text:
                continue
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("l_english"):
                    continue
                m = PROV_RE.match(line)
                if m:
                    prov_id, name = m.group(1), m.group(2)
                    name = re.sub(r"§[A-Za-z!]", "", name)
                    province_names[prov_id] = name
                    added += 1
    print(f"  [{label}] scanned {loc_dir} ({added} entries)")
    return added


def main():
    province_names = {}
    scan_loc_dir(os.path.join(EU4_PATH, "localisation"), province_names, "base")
    scan_loc_dir(os.path.join(MOD_PATH, "localisation"), province_names, "mod")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(province_names, f, separators=(",", ":"), ensure_ascii=False)

    print(f"Extracted {len(province_names)} province names")
    print(f"Output: {OUTPUT} ({os.path.getsize(OUTPUT):,} bytes)")


if __name__ == "__main__":
    main()
