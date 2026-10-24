"""Logo « pilote de chasse » à partir d'une photo (cockpit F-15).

Découpe la tête du pilote (casque + visière + masque), la pose dans une pastille
ronde sur fond bleu nuit avec anneau cyan, et écrit eb_logo.png / eb_logo.ico.

    .venv/Scripts/python.exe eb_logo_photo.py "chemin/photo.png"

Rognage par défaut réglé pour la photo fournie (1376x768). Modifier CROP pour
une autre image : (gauche, haut, droite, bas).
"""
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = None
CROP = (862, 26, 1202, 366)        # tête du pilote dans la photo d'origine
S = 1024
NAVY_MID = (16, 26, 44)
NAVY_EDGE = (6, 10, 18)
CYAN = (76, 201, 240)
BLUE = (47, 129, 247)
CENTER = (512, 500)
RADIUS = 428


def radial_bg():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(120, 0, -1):
        t = i / 120
        col = (int(NAVY_EDGE[0] + (NAVY_MID[0] - NAVY_EDGE[0]) * (1 - t)),
               int(NAVY_EDGE[1] + (NAVY_MID[1] - NAVY_EDGE[1]) * (1 - t)),
               int(NAVY_EDGE[2] + (NAVY_MID[2] - NAVY_EDGE[2]) * (1 - t)), 255)
        r = S * 0.62 * t
        d.ellipse([S / 2 - r, S / 2 - r, S / 2 + r, S / 2 + r], fill=col)
    return img


def portrait(src_path):
    im = Image.open(src_path).convert("RGB")
    w, h = im.size
    cx0, cy0, cx1, cy1 = CROP
    # recadrage carré centré sur la tête
    side = min(cx1 - cx0, cy1 - cy0, w - cx0, h - cy0)
    box = (cx0, cy0, cx0 + side, cy0 + side)
    p = im.crop(box).resize((RADIUS * 2, RADIUS * 2), Image.LANCZOS)
    # étalonnage « verre de visière » : un peu plus froid et contrasté
    p = ImageEnhance.Color(p).enhance(1.08)
    p = ImageEnhance.Contrast(p).enhance(1.12)
    p = ImageEnhance.Brightness(p).enhance(1.04)
    cool = Image.new("RGB", p.size, (150, 190, 255))
    p = Image.blend(p, cool, 0.06)
    return p


def build(src_path, out_dir=HERE):
    base = radial_bg()

    # halo derrière le portrait
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        [CENTER[0] - RADIUS - 40, CENTER[1] - RADIUS - 40,
         CENTER[0] + RADIUS + 40, CENTER[1] + RADIUS + 40],
        fill=BLUE + (120,))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    base.alpha_composite(glow)

    photo = portrait(src_path)

    # masque rond + léger dégradé sombre en bas (lisibilité de l'anneau)
    mask = Image.new("L", (RADIUS * 2, RADIUS * 2), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, RADIUS * 2, RADIUS * 2], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))

    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    canvas.paste(photo, (CENTER[0] - RADIUS, CENTER[1] - RADIUS), mask)

    d = ImageDraw.Draw(canvas)
    # anneau intérieur fin (accent bleu) puis anneau cyan principal
    d.ellipse([CENTER[0] - RADIUS + 6, CENTER[1] - RADIUS + 6,
               CENTER[0] + RADIUS - 6, CENTER[1] + RADIUS - 6],
              outline=(255, 255, 255, 70), width=4)
    d.ellipse([CENTER[0] - RADIUS, CENTER[1] - RADIUS,
               CENTER[0] + RADIUS, CENTER[1] + RADIUS],
              outline=CYAN + (255,), width=14)

    out = Image.alpha_composite(base, canvas)

    # vignette légère pour asseoir le tout
    vig = Image.new("L", (S, S), 0)
    ImageDraw.Draw(vig).ellipse([-S * 0.15, -S * 0.15, S * 1.15, S * 1.15], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new("RGBA", (S, S), (0, 0, 0, 120))
    out = Image.composite(out, Image.alpha_composite(out, dark), vig)

    png = out.resize((512, 512), Image.LANCZOS)
    png.save(os.path.join(out_dir, "eb_logo.png"))
    out.save(os.path.join(out_dir, "eb_logo_1024.png"))
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
    out.save(os.path.join(out_dir, "eb_logo.ico"), format="ICO", sizes=sizes)
    print("logo photo genere dans", out_dir)


if __name__ == "__main__":
    import sys
    SRC = sys.argv[1] if len(sys.argv) > 1 else None
    if not SRC or not os.path.exists(SRC):
        raise SystemExit("usage: eb_logo_photo.py <photo.png>")
    build(SRC)
