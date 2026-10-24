#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Logo 'Le Lien Neural' pour EB & DSC RYZEN Copilote (SVG vectoriel).

Trois variantes :
  badge  -> 1024x1024, casque + lettrage (ecran, installeur, page d'accueil)
  icon   -> 1024x1024, casque seul (lisible a 16 px, sert de .ico)
  wide   -> 1600x560, bandeau horizontal (entete UI)

Usage : python eb_logo_neural.py
"""
import base64
import math
import pathlib
import random

HERE = pathlib.Path(__file__).resolve().parent
FONT_CANDIDATES = [
    HERE / "assets" / "Orbitron.ttf",
    pathlib.Path.home() / "AppData" / "Local" / "Temp" / "orbitron.ttf",
]
CYAN = "#00F0FF"
CYAN_L = "#A8FEFF"
ORANGE = "#FF4500"


def font_b64() -> str:
    for p in FONT_CANDIDATES:
        if p.exists():
            return base64.b64encode(p.read_bytes()).decode("ascii")
    raise SystemExit("Orbitron.ttf introuvable")


def neural_mesh(cx, cy, a, b, step_x=32, step_y=28, seed=11, near=44):
    """Grille de noeuds + liens -> maillage neuronal (coordonnees absolues)."""
    rnd = random.Random(seed)
    pts = []
    x = cx - a
    while x <= cx + a:
        y = cy - b
        while y <= cy + b:
            jx, jy = x + rnd.uniform(-9, 9), y + rnd.uniform(-8, 8)
            if ((jx - cx) / a) ** 2 + ((jy - cy) / b) ** 2 <= 0.94:
                pts.append((round(jx, 1), round(jy, 1)))
            y += step_y
        x += step_x
    lines = []
    for i, (x1, y1) in enumerate(pts):
        for x2, y2 in pts[i + 1:]:
            d = math.hypot(x2 - x1, y2 - y1)
            if d < near:
                op = round(0.72 - d / near * 0.38, 2)
                lines.append(
                    f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                    f'stroke="{CYAN}" stroke-width="1.9" opacity="{op}"/>'
                )
    nodes = "".join(
        f'<circle cx="{px}" cy="{py}" r="2.6" fill="{CYAN_L}" opacity="0.9"/>'
        for px, py in pts
    )
    return "".join(lines) + nodes


def build_svg(variant="badge") -> str:
    if variant == "wide":
        W, H, ox, oy, sc, radius = 1600, 560, -50, -60, 0.62, 56
    elif variant == "icon":
        W, H, ox, oy, sc, radius = 1024, 1024, -182, -62, 1.34, 176
    else:
        W, H, ox, oy, sc, radius = 1024, 1024, 0, 0, 1.0, 176

    style = (
        "@font-face{font-family:'Orbitron';"
        "src:url(data:font/ttf;base64," + font_b64() + ") format('truetype');"
        "font-weight:400 900;font-style:normal;}"
        "text{font-family:'Orbitron',sans-serif;}"
    )
    mesh = neural_mesh(283, 312, 168, 80)

    defs = f"""
  <defs>
    <radialGradient id="bg" cx="72%" cy="18%" r="95%">
      <stop offset="0%" stop-color="#122E3B"/>
      <stop offset="45%" stop-color="#0C1319"/>
      <stop offset="100%" stop-color="#07080B"/>
    </radialGradient>
    <radialGradient id="warm" cx="8%" cy="92%" r="55%">
      <stop offset="0%" stop-color="{ORANGE}" stop-opacity="0.22"/>
      <stop offset="100%" stop-color="{ORANGE}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="halo" cx="50%" cy="45%" r="50%">
      <stop offset="0%" stop-color="{CYAN}" stop-opacity="0.20"/>
      <stop offset="100%" stop-color="{CYAN}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="shell" x1="0" y1="0" x2="0.9" y2="1">
      <stop offset="0%" stop-color="#3C5169"/>
      <stop offset="45%" stop-color="#27343F"/>
      <stop offset="100%" stop-color="#10161D"/>
    </linearGradient>
    <linearGradient id="shell2" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#2B3A4D"/>
      <stop offset="100%" stop-color="#111821"/>
    </linearGradient>
    <linearGradient id="visor" x1="0.05" y1="0.1" x2="0.95" y2="0.95">
      <stop offset="0%" stop-color="#04313D"/>
      <stop offset="45%" stop-color="#0097B4"/>
      <stop offset="78%" stop-color="{CYAN}"/>
      <stop offset="100%" stop-color="#E8FEFF"/>
    </linearGradient>
    <linearGradient id="word" x1="0" y1="0" x2="1" y2="0.4">
      <stop offset="0%" stop-color="#FFFFFF"/>
      <stop offset="55%" stop-color="#DFF7FF"/>
      <stop offset="100%" stop-color="{CYAN}"/>
    </linearGradient>
    <linearGradient id="speed" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{ORANGE}" stop-opacity="0"/>
      <stop offset="32%" stop-color="{ORANGE}" stop-opacity="0.95"/>
      <stop offset="78%" stop-color="{CYAN}" stop-opacity="0.85"/>
      <stop offset="100%" stop-color="{CYAN}" stop-opacity="0"/>
    </linearGradient>
    <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="10" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="glowS" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="4" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="visorClip">
      <path d="M574 300 L726 344 L776 434 L748 522 L612 522 L552 404 Z"/>
    </clipPath>
    <clipPath id="lensClip">
      <path d="M118 320 C190 236 372 224 448 302 C378 398 196 404 118 320 Z"/>
    </clipPath>
    <style>{style}</style>
  </defs>
"""

    bg = f"""
  <rect x="0" y="0" width="{W}" height="{H}" rx="{radius}" fill="url(#bg)"/>
  <rect x="0" y="0" width="{W}" height="{H}" rx="{radius}" fill="url(#warm)"/>
  <rect x="18" y="18" width="{W-36}" height="{H-36}" rx="{max(radius-16,20)}"
        fill="none" stroke="{CYAN}" stroke-width="2.5" opacity="0.22"/>
  <path d="M56 190 L56 86 Q56 56 86 56 L190 56" fill="none" stroke="{CYAN}"
        stroke-width="6" opacity="0.75" transform="translate(18 18)"/>
  <path d="M{W-56} {H-190} L{W-56} {H-86} Q{W-56} {H-56} {W-86} {H-56} L{W-190} {H-56}"
        fill="none" stroke="{ORANGE}" stroke-width="6" opacity="0.9" transform="translate(-18 -18)"/>
"""

    # --- visage numerique / oeil cybernetique (derriere le casque) ---
    eye = f"""
  <g filter="url(#glow)">
    <path d="M118 320 C190 236 372 224 448 302 C378 398 196 404 118 320 Z"
          fill="{CYAN}" opacity="0.14" stroke="{CYAN}" stroke-width="3.5"/>
  </g>
  <g clip-path="url(#lensClip)" opacity="0.9">{mesh}</g>
  <g clip-path="url(#lensClip)">
    <circle cx="300" cy="312" r="46" fill="none" stroke="{CYAN_L}" stroke-width="3" opacity="0.9"/>
    <circle cx="300" cy="312" r="17" fill="{CYAN_L}" opacity="0.95" filter="url(#glowS)"/>
    <path d="M300 246 L300 196 M300 378 L300 428" stroke="{CYAN}" stroke-width="3" opacity="0.45"/>
  </g>
  <path d="M118 320 C190 236 372 224 448 302" fill="none" stroke="{CYAN_L}"
        stroke-width="3.5" opacity="0.85" filter="url(#glowS)"/>
"""

    # --- flux de donnees oeil -> visiere ---
    streams = ""
    for i, (y0, cy1, y2) in enumerate([(282, 300, 352), (312, 350, 400), (348, 400, 452)]):
        streams += (
            f'<path d="M372 {y0} C 470 {cy1}, 520 {y2-40}, 596 {y2}" fill="none" '
            f'stroke="{CYAN}" stroke-width="{3.4 - i*0.5:.1f}" opacity="{0.75 - i*0.12:.2f}" '
            f'stroke-dasharray="7 13" stroke-linecap="round"/>'
            f'<circle cx="596" cy="{y2}" r="{4 - i*0.4:.1f}" fill="{CYAN_L}" filter="url(#glowS)"/>'
        )
    streams += (
        f'<path d="M300 232 C 420 150, 640 190, 700 320" fill="none" stroke="{CYAN}" '
        f'stroke-width="2.6" opacity="0.5" stroke-dasharray="4 16"/>'
    )

    # --- casque ---
    helmet = f"""
  <g transform="translate({ox} {oy}) scale({sc})">
    <path d="M300 652 L262 600 L250 470 L262 376 L322 268 L438 196 L566 186
             L668 242 L742 330 L772 432 L752 540 L676 626 L520 662 L360 656 Z"
          fill="url(#shell)" stroke="#7CA3C0" stroke-width="3.5" stroke-linejoin="round"/>
    <path d="M438 196 L566 186 L668 242 L600 300 L470 312 L360 268 Z"
          fill="url(#shell2)" opacity="0.65"/>
    <path d="M300 652 L360 656 L520 662 L676 626 L640 596 L430 610 L322 600 Z"
          fill="#0D131A" opacity="0.9"/>
    <path d="M250 470 L262 376 L322 268 L438 196 L566 186 L668 242" fill="none"
          stroke="#9CEBFF" stroke-width="4" opacity="0.6" stroke-linecap="round"
          filter="url(#glowS)"/>
    <path d="M470 232 L574 206 L580 224 L476 250 Z" fill="{ORANGE}" opacity="0.95"/>
    <path d="M330 470 L420 452 L470 500 L404 542 L330 520 Z" fill="none"
          stroke="{CYAN}" stroke-width="3" opacity="0.32"/>
    <path d="M574 300 L726 344 L776 434 L748 522 L612 522 L552 404 Z"
          fill="url(#visor)" stroke="{CYAN_L}" stroke-width="4" filter="url(#glow)"/>
    <g clip-path="url(#visorClip)">
      <path d="M552 404 L776 434 L748 522 L612 522 Z" fill="#001A22" opacity="0.28"/>
      <g stroke="{CYAN_L}" stroke-width="2" opacity="0.55">
        <path d="M600 372 L744 392"/>
        <path d="M606 356 L740 374" opacity="0.35"/>
        <path d="M596 500 L736 512" opacity="0.45"/>
      </g>
      <g stroke="{CYAN_L}" stroke-width="2" opacity="0.75">
        <path d="M628 362 L628 382"/><path d="M660 366 L660 386"/>
        <path d="M692 372 L692 392"/><path d="M724 378 L724 398"/>
      </g>
      <circle cx="700" cy="452" r="28" fill="none" stroke="{CYAN_L}" stroke-width="2.5" opacity="0.9"/>
      <path d="M672 452 L728 452 M700 424 L700 480" stroke="{CYAN_L}" stroke-width="2" opacity="0.75"/>
      <path d="M600 512 L690 372" stroke="#E8FEFF" stroke-width="2" opacity="0.35"
            stroke-dasharray="10 10"/>
      <g fill="{CYAN_L}" opacity="0.85">
        <rect x="622" y="470" width="8" height="26" rx="2"/>
        <rect x="636" y="480" width="8" height="16" rx="2"/>
        <rect x="650" y="462" width="8" height="34" rx="2"/>
      </g>
      <rect x="712" y="492" width="34" height="8" rx="3" fill="{ORANGE}" opacity="0.95"/>
    </g>
    <path d="M552 404 L612 522 M748 522 L752 540 L676 626" fill="none"
          stroke="{CYAN_L}" stroke-width="3" opacity="0.55"/>
    <path d="M676 626 L752 540" stroke="{CYAN_L}" stroke-width="5" opacity="0.8"
          stroke-linecap="round" filter="url(#glowS)"/>
    <path d="M470 312 L560 300" stroke="{CYAN}" stroke-width="2.5" opacity="0.3"/>
  </g>
"""

    # --- lettrage ---
    word = ""
    if variant == "badge":
        word = f"""
  <path d="M150 676 L874 676" stroke="url(#speed)" stroke-width="4"/>
  <g transform="translate(512 806) skewX(-6) translate(-512 -806)">
    <text x="512" y="806" text-anchor="middle" font-size="108"
          font-weight="900" fill="url(#word)" letter-spacing="3">EB &amp; DSC</text>
  </g>
  <text x="512" y="898" text-anchor="middle" font-size="50"
        font-weight="600" fill="#8FF6FF" letter-spacing="15">RYZEN</text>
  <path d="M322 862 L292 862 M712 862 L742 862"
        stroke="{ORANGE}" stroke-width="5" stroke-linecap="round" opacity="0.9"/>
"""
    elif variant == "wide":
        word = f"""
  <rect x="146" y="146" width="6" height="260" fill="url(#speed)" opacity="0.9"/>
  <g transform="translate(640 300) skewX(-6) translate(-640 -300)">
    <text x="640" y="300" font-size="116" font-weight="900"
          fill="url(#word)" letter-spacing="3">EB &amp; DSC</text>
  </g>
  <path d="M642 330 L1330 330" stroke="url(#speed)" stroke-width="4"/>
  <text x="644" y="412" font-size="50" font-weight="500"
        fill="{CYAN}" letter-spacing="17">RYZEN</text>
  <text x="646" y="472" font-size="26" font-weight="400" fill="#8FB6C6"
        letter-spacing="8" opacity="0.9">COPILOTE VOCAL DCS</text>
"""

    halo = (
        f'<ellipse cx="{W*0.5:.0f}" cy="{H*0.44:.0f}" rx="{W*0.42:.0f}" '
        f'ry="{H*0.40:.0f}" fill="url(#halo)"/>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">' + defs + bg + halo + eye + streams + helmet + word + "</svg>"
    )


if __name__ == "__main__":
    for name, fname in [
        ("badge", "eb_logo_neural.svg"),
        ("icon", "eb_logo_neural_icon.svg"),
        ("wide", "eb_logo_neural_wide.svg"),
    ]:
        p = HERE / fname
        p.write_text(build_svg(name), encoding="utf-8")
        print("ecrit:", p.name, p.stat().st_size, "octets")
