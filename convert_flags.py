"""Convert all TGA country flags to small PNGs for the web guide.

(A previous version also wrote flag_data.json — an 8.7 MB base64 blob —
but nothing ever consumed it; the UI loads flags/<TAG>.png directly.)
"""
import os
from PIL import Image

MOD = r"C:\Program Files (x86)\Steam\steamapps\workshop\content\236850\1385440355"
FLAGS_DIR = os.path.join(MOD, "gfx", "flags")
OUT_DIR = os.path.join(os.path.dirname(__file__), "flags")

def convert_flags():
    os.makedirs(OUT_DIR, exist_ok=True)

    count = 0
    errors = 0

    for fname in os.listdir(FLAGS_DIR):
        if not fname.endswith('.tga'):
            continue

        tag = fname.replace('.tga', '')
        src = os.path.join(FLAGS_DIR, fname)

        try:
            img = Image.open(src)
            # Resize to 64x64 for web use (smaller file size)
            img = img.resize((64, 64), Image.LANCZOS)

            out_path = os.path.join(OUT_DIR, f"{tag}.png")
            img.save(out_path, "PNG", optimize=True)

            count += 1
        except Exception as e:
            print(f"  Error converting {fname}: {e}")
            errors += 1

    print(f"Converted {count} flags ({errors} errors)")
    print(f"PNG files saved to: {OUT_DIR}")

if __name__ == '__main__':
    convert_flags()
