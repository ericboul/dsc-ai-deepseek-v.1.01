"""Génère le logo « pilote de chasse » de DCS RYZEN Copilote.

Sortie : eb_logo.png (512 px, aperçu) et eb_logo.ico (multi-résolutions, pour
l'exe et les raccourcis Windows).

Exécution : python avec Pillow (le .venv de build), pas le python embarqué.
    DCS-Translation-Tool-ai/.venv/Scripts/python.exe eb_logo.py
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
S = 2048                     # dessin en sur-échantillonnage, puis réduction
NAVY = (11, 18, 32)
DARK = (13, 17, 23)
CYAN = (76, 201, 240)
BLUE = (47, 129, 247)
VISOR = (9, 20, 34)
VISOR_HI = (86, 178, 255)
SHELL = (222, 229, 237)
SHELL_SHADE = (170, 182, 196)
MASK = (188, 198, 210)
HOSE = (120, 132, 146)


def sc(v):
    return int(v * S / 1024)


def circle(d, cx, cy, r, **kw):
    d.ellipse([sc(cx - r), sc(cy - r), sc(cx + r), sc(cy + r)], **kw)


def rounded(d, box, rad, **kw):
    d.rounded_rectangle([sc(box[0]), sc(box[1]), sc(box[2]), sc(box[3])],
                        radius=sc(rad), **kw)


def build():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # --- pastille de fond (dégradé radial simulé par cercles concentriques)
    cx, cy, R = 512, 512, 486
    for i in range(60, 0, -1):
        t = i / 60
        r = R * t
        col = (
            int(NAVY[0] + (24 - NAVY[0]) * (1 - t)),
            int(NAVY[1] + (38 - NAVY[1]) * (1 - t)),
            int(NAVY[2] + (56 - NAVY[2]) * (1 - t)),
            255,
        )
        circle(d, cx, cy, r, fill=col)

    # --- anneau extérieur cyan + anneau fin bleu
    circle(d, cx, cy, R, outline=CYAN + (255,), width=sc(9))
    circle(d, cx, cy, R - sc(22), outline=(47, 129, 247, 120), width=sc(3))

    # --- halo derrière le casque
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    circle(gd, 512, 470, 300, fill=(47, 129, 247, 90))
    glow = glow.filter(ImageFilter.GaussianBlur(sc(70)))
    img.alpha_composite(glow)
    d = ImageDraw.Draw(img)

    # --- respirateur / tuyau (derrière le casque, en bas à gauche)
    d.line([sc(452), sc(690), sc(400), sc(792), sc(300), sc(846)],
           fill=HOSE + (255,), width=sc(34), joint="curve")
    circle(d, 300, 846, 26, outline=(200, 208, 218, 255), width=sc(8))

    # --- coque du casque
    d.polygon([(sc(300), sc(560)), (sc(300), sc(430)), (sc(345), sc(330)),
               (sc(430), sc(268)), (sc(594), sc(268)), (sc(679), sc(330)),
               (sc(724), sc(430)), (sc(724), sc(560))], fill=SHELL + (255,))
    circle(d, 512, 470, 232, fill=SHELL + (255,))
    # ombre du bas de coque
    d.pieslice([sc(280), sc(300), sc(744), sc(700)], 20, 160, fill=SHELL_SHADE + (140,))
    circle(d, 512, 470, 232, fill=None, outline=(150, 162, 178, 255), width=sc(6))

    # --- protège-oreilles / pods latéraux
    circle(d, 300, 520, 52, fill=SHELL_SHADE + (255,), outline=(140, 152, 168, 255), width=sc(5))
    circle(d, 724, 520, 52, fill=SHELL_SHADE + (255,), outline=(140, 152, 168, 255), width=sc(5))
    circle(d, 300, 520, 18, fill=(47, 129, 247, 255))
    circle(d, 724, 520, 18, fill=(47, 129, 247, 255))

    # --- visière (grande bulle sombre)
    d.rounded_rectangle([sc(330), sc(360), sc(694), sc(560)], radius=sc(110),
                        fill=VISOR + (255,))
    # reflet diagonal dans la visière
    refl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    rd = ImageDraw.Draw(refl)
    rd.polygon([(sc(360), sc(520)), (sc(360), sc(420)), (sc(520), sc(372)),
                (sc(600), sc(372)), (sc(392), sc(540))], fill=VISOR_HI + (150,))
    refl = refl.filter(ImageFilter.GaussianBlur(sc(10)))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([sc(330), sc(360), sc(694), sc(560)],
                                           radius=sc(110), fill=255)
    img.paste(Image.alpha_composite(img.crop((0, 0, S, S)), refl), (0, 0), mask)
    d = ImageDraw.Draw(img)

    # contour de visière + liseré cyan
    d.rounded_rectangle([sc(330), sc(360), sc(694), sc(560)], radius=sc(110),
                        outline=(90, 104, 122, 255), width=sc(10))
    d.arc([sc(344), sc(374), sc(680), sc(546)], 200, 340, fill=CYAN + (230,), width=sc(7))

    # --- masque à oxygène
    rounded(d, (424, 566, 600, 700), 52, fill=MASK + (255,),
            outline=(140, 152, 168, 255), width=sc(7))
    d.line([sc(452), sc(600), sc(572), sc(600)], fill=(120, 132, 146, 255), width=sc(9))
    for x in (472, 512, 552):
        circle(d, x, 645, 13, fill=(90, 102, 118, 255))

    # --- rivets / détails de coque
    for (x, y) in [(352, 330), (672, 330), (512, 292)]:
        circle(d, x, y, 12, fill=(196, 206, 218, 255), outline=(150, 162, 178, 255), width=sc(3))

    # --- petit chasseur stylisé en bas du badge (silhouette delta vue du dessus)
    jet = [(512, 800), (536, 842), (632, 884), (632, 900), (542, 882),
           (528, 916), (496, 916), (482, 882), (392, 900), (392, 884),
           (488, 842)]
    d.polygon([(sc(x), sc(y)) for (x, y) in jet], fill=CYAN + (240,))

    # --- réduction anti-aliasée
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS
    out = img.resize((1024, 1024), resample)
    png = out.resize((512, 512), resample)
    png.save(os.path.join(HERE, "eb_logo.png"))
    out.save(os.path.join(HERE, "eb_logo_1024.png"))

    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
    out.save(os.path.join(HERE, "eb_logo.ico"), format="ICO", sizes=sizes)
    print("eb_logo.png + eb_logo.ico generes dans", HERE)


if __name__ == "__main__":
    build()
