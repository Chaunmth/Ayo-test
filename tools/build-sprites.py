#!/usr/bin/env python3
"""Construit les sprite sheets d'Ayo à partir de ayo.mp4.

Pourquoi ce script plutôt qu'une commande ffmpeg unique : le long du clip,
Ayo recule en dansant. Sa hauteur à l'image varie de 18 % et ses pieds
remontent d'une centaine de pixels. Comme la position de la main choisit
l'image affichée, ce glissement se verrait comme un défaut — Ayo
rétrécirait et flotterait quand on bouge la main.

On mesure donc chaque image (le fond est uni, la silhouette est facile à
isoler), puis on recadre image par image pour imposer une hauteur constante
et une ligne de sol fixe. Le léger balancement latéral, lui, est conservé :
il fait partie de la danse.

Usage : python3 tools/build-sprites.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

SRC = "ayo.mp4"
OUT_BIG = "assets/ayo_sheet.webp"
OUT_SM = "assets/ayo_sheet_sm.webp"

# WebP plutôt que JPEG : à qualité égale (~39 dB de PSNR), 395 K contre 746 K.
Q_BIG, Q_SM = 82, 80

COLS, ROWS = 8, 4              # grille de la sprite sheet
CELL_W, CELL_H = 369, 720      # taille d'une case
CELL_W_SM, CELL_H_SM = 185, 360

H_OUT = 648                    # hauteur imposée au personnage, en px de sortie
FEET_Y = 706                   # ligne de sol dans la case, fixe
PAD = 200                      # marge ajoutée à la source (autorise les débords)
BG = "0xD6D4D2"                # couleur du fond du clip

MEAS_W, MEAS_H = 960, 540      # résolution d'analyse
THRESHOLD = 22                 # écart de luma au fond pour dire « personnage »
FOOT_BAND = 0.12               # fraction basse servant d'ancrage (les chaussures)


def run(args):
    subprocess.run(args, check=True)


def measure(tmp):
    """Renvoie, par image : (hauteur, centre x du bas, y des pieds) en pixels source."""
    raw = os.path.join(tmp, "gray.raw")
    run(["ffmpeg", "-v", "error", "-y", "-i", SRC,
         "-vf", f"scale={MEAS_W}:{MEAS_H},format=gray",
         "-f", "rawvideo", raw])

    data = open(raw, "rb").read()
    frame_size = MEAS_W * MEAS_H
    count = len(data) // frame_size
    bg = data[(MEAS_H // 2) * MEAS_W + 5]
    scale_back = 1920 / MEAS_W

    frames = []
    for f in range(count):
        off = f * frame_size
        x0, x1, y0, y1 = MEAS_W, -1, MEAS_H, -1
        for y in range(2, MEAS_H - 1):
            row = off + y * MEAS_W
            for x in range(1, MEAS_W - 1):
                if abs(data[row + x] - bg) > THRESHOLD:
                    x0 = min(x0, x); x1 = max(x1, x)
                    y0 = min(y0, y); y1 = max(y1, y)

        # ancrage sur la bande basse : insensible à l'extension d'un bras
        band_top = int(y1 - (y1 - y0 + 1) * FOOT_BAND)
        sx = cnt = 0
        for y in range(band_top, y1 + 1):
            row = off + y * MEAS_W
            for x in range(1, MEAS_W - 1):
                if abs(data[row + x] - bg) > THRESHOLD:
                    sx += x; cnt += 1
        foot_cx = (sx / cnt) if cnt else (x0 + x1) / 2

        frames.append(((y1 - y0 + 1) * scale_back,
                       foot_cx * scale_back,
                       y1 * scale_back))
    return frames


def normalize(frames, tmp):
    """Écrit une image PNG normalisée par frame."""
    for i, (height, foot_cx, foot_y) in enumerate(frames):
        s = H_OUT / height
        crop_w, crop_h = CELL_W / s, CELL_H / s
        x0 = foot_cx + PAD - (CELL_W / 2) / s
        y0 = foot_y + PAD - FEET_Y / s
        vf = (f"select='eq(n\\,{i})',"
              f"pad={1920 + 2 * PAD}:{1080 + 2 * PAD}:{PAD}:{PAD}:{BG},"
              f"crop={crop_w:.0f}:{crop_h:.0f}:{x0:.0f}:{y0:.0f},"
              f"scale={CELL_W}:{CELL_H}:flags=lanczos")
        run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-vf", vf,
             "-fps_mode", "passthrough", "-frames:v", "1",
             os.path.join(tmp, f"n{i:02d}.png")])


def tile(tmp, count):
    """Assemble la grille en PNG (sans perte) puis encode en WebP."""
    from PIL import Image

    pattern = os.path.join(tmp, "n%02d.png")
    if count != COLS * ROWS:
        sys.exit(f"{count} images pour une grille {COLS}×{ROWS} : ajuster COLS/ROWS")

    os.makedirs("assets", exist_ok=True)
    for out, cell_w, cell_h, quality in (
        (OUT_BIG, CELL_W, CELL_H, Q_BIG),
        (OUT_SM, CELL_W_SM, CELL_H_SM, Q_SM),
    ):
        png = os.path.join(tmp, f"tile_{cell_w}.png")
        vf = f"tile={COLS}x{ROWS}"
        if (cell_w, cell_h) != (CELL_W, CELL_H):
            vf = f"scale={cell_w}:{cell_h}:flags=lanczos," + vf
        run(["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i", pattern,
             "-vf", vf, "-frames:v", "1", png])
        Image.open(png).convert("RGB").save(out, "WEBP", quality=quality, method=6)


def main():
    if not os.path.exists(SRC):
        sys.exit(f"{SRC} introuvable — lancer le script depuis la racine du projet")
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg est requis")

    tmp = tempfile.mkdtemp(prefix="ayo-sprites-")
    try:
        frames = measure(tmp)
        heights = [f[0] for f in frames]
        print(f"{len(frames)} images analysées · "
              f"hauteur source {min(heights):.0f}–{max(heights):.0f} px "
              f"({(max(heights) - min(heights)) / max(heights) * 100:.0f} % d'écart)")

        normalize(frames, tmp)
        tile(tmp, len(frames))
        print(f"écrit {OUT_BIG} ({COLS * CELL_W}×{ROWS * CELL_H}) et "
              f"{OUT_SM} ({COLS * CELL_W_SM}×{ROWS * CELL_H_SM})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
