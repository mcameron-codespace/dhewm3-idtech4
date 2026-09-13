#!/usr/bin/env python3
"""
Procedural asset generator for dhewm3 minimal engine startup.

Produces only the technical minimum the engine demands to pass initialization
-- no copyrighted DOOM 3 art, audio, maps, or content of any kind.

Output tree (all under `assets/`):
  assets/
  └── base/                          # +set fs_basepath .../assets
      ├── default.cfg                # REQUIRED (hard fatal if missing)
      ├── script/
      │   ├── doom_defs.script       # REQUIRED by idGameLocal::Init (Game_local.cpp:342)
      │   └── doom_main.script       # REQUIRED by idGameLocal::Init (Game_local.cpp:342)
      ├── materials/
      │   ├── _default.mtr          # REQUIRED (tr.defaultMaterial fallback)
      │   ├── textures/
      │   │   ├── bigchars.mtr      # REQUIRED (console font + loading text)
      │   │   ├── _white.mtr
      │   │   ├── console.mtr
      │   │   └── splashScreen.mtr
      │   └── lights/
      │       ├── defaultPointLight.mtr
      │       └── defaultProjectedLight.mtr
      └── textures/
          ├── bigchars.tga         # 256x256 font atlas, 16x16 cells
          ├── _white.tga           # 4x4 solid white
          ├── console.tga          # 640x480 near-black
          ├── splashScreen.tga     # 640x480 loading backdrop
          └── lights/
              ├── defaultpointlight.tga
              └── defaultprojectedlight.tga
"""

import os
import struct
import math
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# TGA writer (uncompressed, 32-bit RGBA, bottom-up row order)
# The engine's LoadTGA iterates rows from bottom to top, so we emit
# row 0 last (bottom of image first in the file).
# ---------------------------------------------------------------------------

def write_tga(path, width, height, pixels):
    """pixels: list of (r,g,b,a) rows from TOP to BOTTOM (normal image order).
    We flip to bottom-up for the file."""
    with open(path, "wb") as f:
        # Header (18 bytes)
        f.write(struct.pack("<BBB", 0, 0, 2))          # id_len, colormap, type=RGB
        f.write(struct.pack("<HH", 0, 0))              # colormap index, length
        f.write(struct.pack("<B", 0))                  # colormap size
        f.write(struct.pack("<HH", 0, 0))              # x_origin, y_origin
        f.write(struct.pack("<HH", width, height))     # width, height
        f.write(struct.pack("<BB", 32, 8))             # pixel_size=32, attributes(8-bit alpha)

        # Rows bottom-up: last image row first in file
        for y in range(height - 1, -1, -1):
            row = pixels[y]
            for (r, g, b, a) in row:
                f.write(struct.pack("<BBBB", b, g, r, a))  # TGA is BGR(A) order


def make_solid(width, height, r, g, b, a=255):
    row = [(r, g, b, a)] * width
    return [row[:] for _ in range(height)]


def make_vertical_gradient(width, height, top_r, top_g, top_b, bot_r, bot_g, bot_b, a=255):
    pixels = []
    for y in range(height):
        t = y / max(height - 1, 1)
        r = int(top_r + (bot_r - top_r) * t)
        g = int(top_g + (bot_g - top_g) * t)
        b = int(top_b + (bot_b - top_b) * t)
        row = [(r, g, b, a)] * width
        pixels.append(row)
    return pixels


def make_font_atlas(cell_size=16, grid=16):
    """256x256 texture, 16x16 grid of cells. Each cell has a unique grayscale
    value so individual glyphs are distinguishable (proves the font system works).
    Characters 0-255 get gray value = index (mod 256)."""
    size = cell_size * grid  # 256
    pixels = []
    for gy in range(grid):
        for y in range(cell_size):
            row = []
            for gx in range(grid):
                idx = gy * grid + gx
                gray = idx % 256
                # draw a tiny border so cells are visible
                for x in range(cell_size):
                    if x == 0 or x == cell_size - 1 or y == 0 or y == cell_size - 1:
                        row.append((255, 255, 255, 255))  # white border
                    else:
                        row.append((gray, gray, gray, 255))
            # repeat the row `grid` times (once per column cell)
            for _ in range(grid):
                pixels.append(row[:])
    # We built it as grid*CELL per row, grid rows of cells -- that's correct.
    # But the above double-loop produces grid*CELL rows total = 256 rows. Good.
    return pixels


def make_splash(width, height):
    """Simple loading-screen backdrop: dark gradient with a faint grid."""
    pixels = make_vertical_gradient(width, height, 10, 12, 16, 24, 28, 32)
    # draw a subtle crosshair-ish marker in center
    cx, cy = width // 2, height // 2
    for y in range(max(0, cy - 20), min(height, cy + 20)):
        for x in range(max(0, cx - 20), min(width, cx + 20)):
            dx, dy = x - cx, y - cy
            if abs(dx) <= 2 and abs(dy) <= 20:
                pixels[y][x] = (60, 70, 80, 255)
            if abs(dy) <= 2 and abs(dx) <= 20:
                pixels[y][x] = (60, 70, 80, 255)
    # center dot
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            if dx * dx + dy * dy <= 9:
                px, py = cx + dx, cy + dy
                if 0 <= py < height and 0 <= px < width:
                    pixels[py][px] = (120, 140, 160, 255)
    return pixels


# ---------------------------------------------------------------------------
# Material (.mtr) writer
# Format:  name { { map <image> } }   (minimal single-stage material)
# ---------------------------------------------------------------------------

def write_material(path, name, image_path, extra_lines=None):
    lines = [
        f"{name}",
        "{",
        f"\t{{",
        f"\t\tmap\t{image_path}",
        f"\t}}",
        "}",
        "",
    ]
    if extra_lines:
        lines.extend(extra_lines)
    with open(path, "w") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# default.cfg writer
# ---------------------------------------------------------------------------

def write_default_cfg(path):
    lines = [
        "// procedurally generated minimal config for dhewm3 startup",
        "// (no copyrighted DOOM 3 content -- purely engine-bootstrapping)",
        "",
        "seta r_fullscreen        \"0\"",
        "seta r_mode              \"-1\"",
        "seta r_customWidth       \"640\"",
        "seta r_customHeight      \"480\"",
        "seta r_aspect            \"1\"",
        "seta r_displayIndex     \"0\"",
        "seta s_volume            \"0.7\"",
        "seta m_volume            \"0.7\"",
        "seta in_mouse            \"1\"",
        "seta in_mouseAxis        \"0\"",
        "seta in_reverseMouse     \"0\"",
        "seta in_suppressKeyboard \"0\"",
        "seta con_actionToken    \"^^\"",
        "seta con_actionPredToken \"^\"",
        "seta g_showGun          \"1\"",
        "seta g_selectForced     \"0\"",
        "seta g_forcedColor      \"0\"",
        "seta g_skipIntro        \"1\"",
        "",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines))


def write_script_stub(path, func_name, body_lines):
    """Write a minimal Doom 3 script file.

    Doom 3 scripting uses a C-like syntax compiled by idCompiler
    (neo/game/script/Script_Compiler.cpp).  The engine's
    idGameLocal::Init (Game_local.cpp:342) calls
        program.Startup( SCRIPT_DEFAULT )  // = "script/doom_main.script"
    and later FindFunction( "doom_main" ) (line 1890), so the file must
    define a function called `doom_main`.

    A valid minimal file is just:
        void functionName() {
            // empty body
        }
    """
    lines = [
        f"void {func_name}() {{",
        *body_lines,
        "}",
        "",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate(root: Path, cell_size=16, grid=16):
    base = root / "base"
    mats = base / "materials"
    txt = base / "textures"
    lightdata_txt = txt / "lightdata"
    scr = base / "script"

    for d in [mats / "textures", mats / "lights", txt, lightdata_txt, scr]:
        d.mkdir(parents=True, exist_ok=True)

    # --- default.cfg ---
    write_default_cfg(base / "default.cfg")

    # --- game scripts (hard-required by idGameLocal::Init) ---
    write_script_stub(scr / "doom_defs.script", "doom_defs", [""])
    write_script_stub(scr / "doom_main.script", "doom_main", [""])

    # --- _default material ---
    write_material(mats / "_default.mtr", "_default", "textures/_white.tga")

    # --- texture materials (map path = "textures/<name>.tga") ---
    write_material(mats / "textures" / "_white.mtr",      "_white",          "textures/_white.tga")
    write_material(mats / "textures" / "bigchars.mtr",    "textures/bigchars", "textures/bigchars.tga")
    write_material(mats / "textures" / "console.mtr",     "console",         "textures/console.tga")
    write_material(mats / "textures" / "splashScreen.mtr","splashScreen",    "textures/splashScreen.tga")

    # --- light materials ---
    # Image_files.cpp:1357 rejects any image whose name starts with "lights/"
    # when com_machineSpec >= 1 (i.e. any real hardware).  We use the
    # "lightdata/" subdirectory instead so the resolved image name is
    # "textures/lightdata/<name>.tga".
    write_material(mats / "lights" / "defaultPointLight.mtr",     "lights/defaultPointLight",     "textures/lightdata/defaultpointlight.tga")
    write_material(mats / "lights" / "defaultProjectedLight.mtr", "lights/defaultProjectedLight", "textures/lightdata/defaultprojectedlight.tga")

    # --- image files (all under base/textures/) ---
    write_tga(txt / "bigchars.tga",      256, 256, make_font_atlas(cell_size, grid))
    write_tga(txt / "_white.tga",          4,   4, make_solid(4, 4, 255, 255, 255, 255))
    write_tga(txt / "console.tga",      640, 480, make_solid(640, 480, 8, 8, 10, 255))
    write_tga(txt / "splashScreen.tga", 640, 480, make_splash(640, 480))

    # --- light texture images (under base/textures/lightdata/) ---
    # Image_files.cpp:1357 rejects images whose resolved name starts with
    # "lights/" on real hardware, so we use "lightdata/" instead.
    write_tga(lightdata_txt / "defaultpointlight.tga",     16, 16, make_solid(16, 16, 255, 200, 120, 255))
    write_tga(lightdata_txt / "defaultprojectedlight.tga", 16, 16, make_solid(16, 16, 255, 255, 220, 255))

    return root


def main():
    parser = argparse.ArgumentParser(description="Generate minimal dhewm3 bootstrap assets")
    parser.add_argument("--out", type=Path, default=Path("assets"),
                        help="output directory (default: ./assets)")
    parser.add_argument("--cell", type=int, default=16, help="font cell size")
    parser.add_argument("--grid", type=int, default=16, help="font grid dimension")
    args = parser.parse_args()

    out = args.out.resolve()
    generate(out, cell_size=args.cell, grid=args.grid)

    print(f"Wrote bootstrap assets to: {out}")
    print(f"  base/default.cfg")
    print(f"  base/materials/  (6 .mtr files)")
    print(f"  base/textures/   (4 .tga files)")
    print()
    print("To test:")
    print(f'  cmake --build build --target dhewm3   # ensure binary exists')
    print(f'  ./build/dhewm3 +set fs_basepath {out} +set r_fullscreen 0 +quit')


if __name__ == "__main__":
    main()
