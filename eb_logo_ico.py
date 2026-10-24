"""Fabrique un .ico lisible aux petites tailles (16/24/32 px).

Le logo complet, réduit tel quel à 16 px, devient une petite tache sombre.
On fabrique donc un ICO « multi-images » : tailles moyennes/grandes = dessin
complet, petites tailles = zoom sur le casque + un peu plus lumineux.

Usage :
    .venv/Scripts/python.exe eb_logo_ico.py eb_logo_1024.png eb_logo.ico
"""
import io
import os
import struct
import sys

from PIL import Image, ImageEnhance

SIZES_BIG = (256, 128, 64, 48)
SIZES_SMALL = (32, 24, 16)
SMALL_ZOOM = 0.74          # on garde 74 % du centre -> le casque remplit l'icône


def variant(img, size):
    if size >= 48:
        return img.resize((size, size), Image.LANCZOS)
    w, h = img.size
    m = int(w * (1 - SMALL_ZOOM) / 2)
    crop = img.crop((m, m, w - m, h - m)).resize((size, size), Image.LANCZOS)
    crop = ImageEnhance.Brightness(crop).enhance(1.12)
    crop = ImageEnhance.Contrast(crop).enhance(1.10)
    return crop


def write_ico(img, out_path):
    """Écrit un ICO contenant une image PNG par taille (supporté depuis Vista)."""
    variants = [(s, variant(img, s)) for s in SIZES_BIG + SIZES_SMALL]
    blobs = []
    for size, im in variants:
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        blobs.append((size, buf.getvalue()))

    header = struct.pack("<HHH", 0, 1, len(blobs))     # reservé, type=icône, nb images
    offset = 6 + 16 * len(blobs)
    entries, data = b"", b""
    for size, blob in blobs:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
        data += blob

    with open(out_path, "wb") as fh:
        fh.write(header + entries + data)
    return [s for s, _ in blobs]


def main(argv):
    src = argv[1] if len(argv) > 1 else "eb_logo_1024.png"
    out = argv[2] if len(argv) > 2 else "eb_logo.ico"
    if not os.path.exists(src):
        raise SystemExit("source absente : " + src)
    img = Image.open(src).convert("RGB")
    sizes = write_ico(img, out)
    print("ICO écrit : %s (%s)" % (out, ", ".join(str(s) for s in sizes)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
