#!/usr/bin/env python3
"""Construit les sprite sheets d'Ayo à partir de ayo.mp4.

Le recadrage est FIXE : le même rectangle pour les 32 images. Le mouvement
réel d'Ayo est donc conservé tel quel, y compris le léger recul et le
changement d'échelle qui l'accompagne le long du clip — c'est la danse
filmée, pas une version redressée.

Le rectangle est calculé automatiquement : on isole la silhouette sur le
fond uni, on prend l'union des positions sur toutes les images, on ajoute
une marge, puis on étend au rapport d'une case de la grille.

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

COLS, ROWS = 8, 4              # grille de la sprite sheet
CELL_W, CELL_H = 369, 720      # taille d'une case
CELL_W_SM, CELL_H_SM = 185, 360

# WebP plutôt que JPEG : à qualité égale (~39 dB de PSNR), 395 K contre 746 K.
Q_BIG, Q_SM = 82, 80

SRC_W, SRC_H = 1920, 1080
MARGIN = 14                    # marge autour de la silhouette, en px source

MEAS_W, MEAS_H = 480, 270      # résolution d'analyse
THRESHOLD = 22                 # écart de luma au fond pour dire « personnage »


def run(args):
    subprocess.run(args, check=True)


def union_bbox(tmp):
    """Rectangle contenant la silhouette sur l'ensemble des images."""
    raw = os.path.join(tmp, "gray.raw")
    run(["ffmpeg", "-v", "error", "-y", "-i", SRC,
         "-vf", f"scale={MEAS_W}:{MEAS_H},format=gray",
         "-f", "rawvideo", raw])

    data = open(raw, "rb").read()
    frame_size = MEAS_W * MEAS_H
    count = len(data) // frame_size
    bg = data[(MEAS_H // 2) * MEAS_W + 5]

    x0, x1, y0, y1 = MEAS_W, -1, MEAS_H, -1
    for f in range(count):
        off = f * frame_size
        # on saute les bords : la première ligne du clip est une bande sombre
        for y in range(2, MEAS_H - 1):
            row = off + y * MEAS_W
            for x in range(1, MEAS_W - 1):
                if abs(data[row + x] - bg) > THRESHOLD:
                    x0 = min(x0, x); x1 = max(x1, x)
                    y0 = min(y0, y); y1 = max(y1, y)

    if x1 < 0:
        sys.exit("silhouette introuvable : vérifier THRESHOLD")

    k = SRC_W / MEAS_W
    return count, (x0 * k, (x1 + 1) * k, y0 * k, (y1 + 1) * k)


def crop_rect(bbox):
    """Étend le rectangle au rapport d'une case, sans sortir de l'image."""
    x0, x1, y0, y1 = bbox
    x0, x1 = max(0, x0 - MARGIN), min(SRC_W, x1 + MARGIN)
    y0, y1 = max(0, y0 - MARGIN), min(SRC_H, y1 + MARGIN)

    w, h = x1 - x0, y1 - y0
    target = CELL_W / CELL_H

    if w / h < target:                     # trop étroit : on élargit
        need = h * target
        cx = (x0 + x1) / 2
        x0, x1 = cx - need / 2, cx + need / 2
        if x0 < 0:
            x0, x1 = 0, need
        elif x1 > SRC_W:
            x0, x1 = SRC_W - need, SRC_W
    else:                                  # trop large : on rehausse
        need = w / target
        cy = (y0 + y1) / 2
        y0, y1 = cy - need / 2, cy + need / 2
        if y0 < 0:
            y0, y1 = 0, need
        elif y1 > SRC_H:
            y0, y1 = SRC_H - need, SRC_H

    return (round(x1 - x0), round(y1 - y0), round(x0), round(y0))


def build(crop, tmp):
    from PIL import Image

    w, h, x, y = crop
    os.makedirs("assets", exist_ok=True)

    for out, cell_w, cell_h, quality in (
        (OUT_BIG, CELL_W, CELL_H, Q_BIG),
        (OUT_SM, CELL_W_SM, CELL_H_SM, Q_SM),
    ):
        png = os.path.join(tmp, f"tile_{cell_w}.png")
        run(["ffmpeg", "-v", "error", "-y", "-i", SRC,
             "-vf", (f"crop={w}:{h}:{x}:{y},"
                     f"scale={cell_w}:{cell_h}:flags=lanczos,"
                     f"tile={COLS}x{ROWS}"),
             "-frames:v", "1", png])
        Image.open(png).convert("RGB").save(out, "WEBP", quality=quality, method=6)


def main():
    if not os.path.exists(SRC):
        sys.exit(f"{SRC} introuvable — lancer le script depuis la racine du projet")
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg est requis")

    tmp = tempfile.mkdtemp(prefix="ayo-sprites-")
    try:
        count, bbox = union_bbox(tmp)
        if count != COLS * ROWS:
            sys.exit(f"{count} images pour une grille {COLS}×{ROWS} : ajuster COLS/ROWS")

        crop = crop_rect(bbox)
        print(f"{count} images · recadrage fixe "
              f"{crop[0]}×{crop[1]} en ({crop[2]},{crop[3]})")

        build(crop, tmp)
        print(f"écrit {OUT_BIG} ({COLS * CELL_W}×{ROWS * CELL_H}) et "
              f"{OUT_SM} ({COLS * CELL_W_SM}×{ROWS * CELL_H_SM})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
