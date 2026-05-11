"""
Master script to run the full Anbennar compendium extraction + build.
Mirrors the sibling eu4-compendium/run_all.py, adapted for this project.
"""
import json
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run(script_name, desc):
    print(f"\n{'='*70}\n  {desc}\n  -> {script_name}\n{'='*70}", flush=True)
    t0 = time.time()
    result = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, script_name)], cwd=SCRIPT_DIR)
    dt = time.time() - t0
    status = "OK" if result.returncode == 0 else f"FAIL ({result.returncode})"
    print(f"  [{status}] {script_name} in {dt:.1f}s", flush=True)
    return result.returncode


STEPS = [
    ("extract_data.py",             "Extract country data (tags, ideas, missions, religions)"),
    ("extract_formables.py",        "Extract formable/playable nation status"),
    ("extract_areas.py",            "Extract areas and regions"),
    ("extract_diplomacy.py",        "Extract diplomatic relationships"),
    ("extract_province_details.py", "Extract province details"),
    ("extract_province_owners.py",  "Extract province ownership"),
    ("extract_province_names.py",   "Extract province names (base EU4 + Anbennar)"),
    ("extract_triggers.py",         "Extract mission triggers and effects"),
    ("extract_extras.py",           "Extract government reforms and region mapping"),
    ("parse_modifiers.py",          "Parse event modifiers"),
    ("parse_startup_lore.py",       "Parse startup lore"),
    ("convert_flags.py",            "Convert country flags (TGA -> PNG)"),
    ("convert_mission_icons.py",    "Convert mission icons (DDS -> PNG)"),
    ("extract_religion_icons.py",   "Extract religion icons"),
    ("generate_map.py",             "Generate political map"),
]


def main():
    failures = []
    for script, desc in STEPS:
        rc = run(script, desc)
        if rc != 0:
            failures.append(script)

    wiki_path = os.path.join(SCRIPT_DIR, "wiki_data.json")
    if not os.path.exists(wiki_path):
        print(f"\n  Creating empty wiki_data.json")
        with open(wiki_path, "w") as f:
            json.dump({}, f)

    rc = run("build_html.py", "Build final index.html")
    if rc != 0:
        failures.append("build_html.py")

    print(f"\n{'='*70}")
    if failures:
        print(f"  DONE with {len(failures)} failure(s): {', '.join(failures)}")
    else:
        print(f"  ALL DONE")
    print(f"{'='*70}")
    print(f"Open {os.path.join(SCRIPT_DIR, 'index.html')} in a browser to view.")


if __name__ == "__main__":
    main()
