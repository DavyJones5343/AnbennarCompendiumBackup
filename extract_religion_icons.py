"""
Extract religion icons from Anbennar's icon_religion.dds spritesheet.

Parses EU4 religion files to find icon indices, then crops each icon
from the DDS spritesheet and saves as individual PNGs.
"""

import os
import re
import struct
from PIL import Image

# Paths
MOD_ROOT = r"C:\Program Files (x86)\Steam\steamapps\workshop\content\236850\1385440355"
DDS_PATH = os.path.join(MOD_ROOT, "gfx", "interface", "icon_religion.dds")
RELIGION_FILES = [
    os.path.join(MOD_ROOT, "common", "religions", "00_anb_religion.txt"),
    os.path.join(MOD_ROOT, "common", "religions", "00_religion.txt"),
]
OUTPUT_DIR = r"C:\Users\jjdeg\OneDrive\Desktop\anbennar-guide\religion_icons"

NUM_FRAMES = 150
OUTPUT_SIZE = 32  # Resize icons to 32x32


def load_dds_b8g8r8a8(path):
    """Load a DX10 B8G8R8A8_UNORM DDS file into a PIL Image."""
    with open(path, "rb") as f:
        magic = f.read(4)
        if magic != b"DDS ":
            raise ValueError(f"Not a DDS file: {magic}")

        # Standard DDS header (124 bytes)
        header = f.read(124)
        _size, _flags, height, width = struct.unpack_from("<4I", header, 0)

        # Pixel format at offset 72 in header
        pf_fourcc = header[80:84]

        # If DX10 extended header, read 20 more bytes
        if pf_fourcc == b"DX10":
            dx10_header = f.read(20)
            dxgi_format = struct.unpack_from("<I", dx10_header, 0)[0]
            print(f"DX10 DXGI format: {dxgi_format}")
            # Format 91 = DXGI_FORMAT_B8G8R8A8_UNORM (4 bytes per pixel, BGRA)
            if dxgi_format != 91:
                print(f"Warning: expected DXGI format 91, got {dxgi_format}")

        # Read raw pixel data: 4 bytes per pixel (BGRA)
        pixel_data = f.read(width * height * 4)

    # Convert BGRA to RGBA
    rgba_data = bytearray(len(pixel_data))
    for i in range(0, len(pixel_data), 4):
        rgba_data[i] = pixel_data[i + 2]      # R <- B
        rgba_data[i + 1] = pixel_data[i + 1]  # G
        rgba_data[i + 2] = pixel_data[i]       # B <- R
        rgba_data[i + 3] = pixel_data[i + 3]   # A

    img = Image.frombytes("RGBA", (width, height), bytes(rgba_data))
    return img


def read_file_with_fallback(path):
    """Read a text file trying multiple encodings."""
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise RuntimeError(f"Could not read {path} with any encoding")


def parse_religions(file_paths):
    """
    Parse EU4 religion files to extract {religion_id: icon_number}.

    The structure is:
        religion_group = {
            religion_name = {
                icon = N
                ...
            }
        }

    We track brace depth: at depth 1 we're in a religion group,
    at depth 2 we're in a religion definition where we look for icon = N.
    Lines that are comments are skipped.
    """
    religions = {}

    for path in file_paths:
        if not os.path.exists(path):
            print(f"Warning: {path} not found, skipping")
            continue

        text = read_file_with_fallback(path)
        lines = text.split("\n")

        depth = 0
        current_religion = None
        # Track whether we're inside a commented-out block
        in_comment_block = False

        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Skip fully commented lines
            if stripped.startswith("#"):
                # Count braces in comments to avoid mismatching
                continue

            # Remove inline comments
            comment_pos = stripped.find("#")
            if comment_pos >= 0:
                stripped = stripped[:comment_pos].strip()

            if not stripped:
                continue

            # Count brace changes
            opens = stripped.count("{")
            closes = stripped.count("}")

            # At depth 1, a new block opening is a religion definition
            if depth == 1 and opens > 0:
                # Extract the key name before '='
                match = re.match(r"(\w+)\s*=\s*\{", stripped)
                if match:
                    key = match.group(1)
                    # Skip known non-religion keys
                    skip_keys = {
                        "can_form_personal_unions", "defender_of_faith",
                        "flags_with_emblem_percentage", "flag_emblem_index_range",
                        "ai_will_propagate_through_trade", "center_of_religion",
                        "religious_schools", "papacy", "reform_tooltip",
                    }
                    if key not in skip_keys:
                        current_religion = key

            # Look for icon = N at depth 2 (inside a religion)
            if depth >= 2 and current_religion:
                icon_match = re.match(r"icon\s*=\s*(\d+)", stripped)
                if icon_match:
                    icon_num = int(icon_match.group(1))
                    religions[current_religion] = icon_num
                    # Don't clear current_religion yet; wait for block to close

            depth += opens - closes

            # If we've returned to depth 1, we've left the religion block
            if depth <= 1:
                current_religion = None

    return religions


def main():
    # Load the spritesheet
    print(f"Loading DDS: {DDS_PATH}")
    spritesheet = load_dds_b8g8r8a8(DDS_PATH)
    print(f"Spritesheet size: {spritesheet.size}")

    frame_width = spritesheet.width // NUM_FRAMES
    frame_height = spritesheet.height
    print(f"Frame size: {frame_width}x{frame_height} ({NUM_FRAMES} frames)")

    # Parse religion files
    print(f"\nParsing religion files...")
    religions = parse_religions(RELIGION_FILES)
    print(f"Found {len(religions)} religions with icon definitions")

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Extract icons
    extracted = 0
    errors = 0
    for religion_id, icon_num in sorted(religions.items(), key=lambda x: x[1]):
        # EU4 icon numbers are 1-based
        frame_index = icon_num - 1
        if frame_index < 0 or frame_index >= NUM_FRAMES:
            print(f"  Warning: {religion_id} has icon {icon_num} (out of range 1-{NUM_FRAMES})")
            errors += 1
            continue

        x = frame_index * frame_width
        y = 0
        box = (x, y, x + frame_width, y + frame_height)
        icon = spritesheet.crop(box)

        # Resize to output size if needed
        if icon.size != (OUTPUT_SIZE, OUTPUT_SIZE):
            icon = icon.resize((OUTPUT_SIZE, OUTPUT_SIZE), Image.LANCZOS)

        out_path = os.path.join(OUTPUT_DIR, f"{religion_id}.png")
        icon.save(out_path, "PNG")
        extracted += 1

    print(f"\n=== Summary ===")
    print(f"Religions found: {len(religions)}")
    print(f"Icons extracted: {extracted}")
    if errors:
        print(f"Errors/warnings: {errors}")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
