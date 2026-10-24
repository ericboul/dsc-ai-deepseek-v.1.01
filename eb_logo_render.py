#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rend les SVG du logo en PNG + ICO multi-tailles (via Edge headless).

Usage : python eb_logo_render.py
"""
import pathlib
import subprocess
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROFILE = str(pathlib.Path.home() / "AppData/Local/Temp/edgeprof_logo")
JOBS = {  # svg -> (largeur, hauteur, echelle)
    "eb_logo_neural": (1024, 1024, 2),
    "eb_logo_neural_icon": (1024, 1024, 2),
    "eb_logo_neural_wide": (1600, 560, 2),
}


def shoot(svg_stem, w, h, scale):
    out = HERE / f"_render_{svg_stem}.png"
    url = "file:///" + str(HERE / f"{svg_stem}.svg").replace("\\", "/").replace(" ", "%20")
    subprocess.run(
        [EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         f"--force-device-scale-factor={scale}", f"--user-data-dir={PROFILE}",
         f"--window-size={w},{h}", f"--screenshot={out}", url],
        check=True, capture_output=True,
    )
    return Image.open(out).convert("RGB")


def main():
    icon_big = None
    for stem, (w, h, sc) in JOBS.items():
        im = shoot(stem, w, h, sc)
        big = HERE / f"{stem}_2048.png" if w == 1024 else HERE / f"{stem}_3200.png"
        im.save(big)
        if w == 1024:
            im.resize((1024, 1024), Image.LANCZOS).save(HERE / f"{stem}_1024.png")
        else:
            im.resize((1600, 560), Image.LANCZOS).save(HERE / f"{stem}.png")
        if stem == "eb_logo_neural":
            im.resize((512, 512), Image.LANCZOS).save(HERE / "eb_logo_neural_512.png")
            im.resize((256, 256), Image.LANCZOS).save(HERE / "eb_logo_neural_256.png")
        if stem == "eb_logo_neural_icon":
            icon_big = im
        print("rendu:", stem)

    if icon_big:
        sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
        icon_big.save(HERE / "eb_logo_neural.ico", format="ICO", sizes=sizes,
                      append_images=[icon_big.resize(s, Image.LANCZOS) for s in sizes])
        print("ico ok:", HERE / "eb_logo_neural.ico")


if __name__ == "__main__":
    sys.exit(main())
