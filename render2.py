"""Tashakkurnoma: tayyor fon (templates/<variant>_<maktab>.png) + ism, filial, sana, raqam."""
import io
import json
import os
import re
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "templates") if os.path.isdir(os.path.join(HERE, "templates")) else HERE
FONTS = os.path.join(HERE, "fonts") if os.path.isdir(os.path.join(HERE, "fonts")) else HERE
SCALE = 3.125

OYLAR = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul",
         "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"]


def _font(weight, px):
    return ImageFont.truetype(os.path.join(FONTS, f"Montserrat-{weight}.ttf"), int(round(px)))


def _upper(s):
    return s.replace("i", "I").upper() if False else s.upper()


def _width(draw, text, font, track):
    if not text:
        return 0
    return sum(draw.textlength(c, font=font) for c in text) + track * font.size * (len(text) - 1)


def _draw_line(draw, x, base, text, font, track, fill):
    for c in text:
        draw.text((x, base), c, font=font, fill=fill, anchor="ls")
        x += draw.textlength(c, font=font) + track * font.size


def draw_field(draw, text, st):
    x, y, w, h = st["box"]
    if st.get("upper"):
        text = _upper(text)
    words = text.split()
    if st.get("split") and len(words) >= 2:
        lines = [words[0], " ".join(words[1:])]          # Familiya / Ism (Otasining ismi)
    else:
        lines = [" ".join(words)]
    track = st.get("track", 0)
    lh = st.get("lh", 1.15)
    size = st["max"] * SCALE
    min_size = st["min"] * SCALE
    while True:
        f = _font(st["font"], size)
        widest = max(_width(draw, ln, f, track) for ln in lines)
        asc, desc = f.getmetrics()
        total_h = asc + (len(lines) - 1) * size * lh + desc * 0.3
        if (widest <= w and total_h <= h) or size <= min_size:
            break
        size -= 1
    if widest > w and len(lines) == 1 and len(words) >= 2:   # baribir sig'masa — ikki qatorga
        st = dict(st, split=True)
        return draw_field(draw, text, st)
    f = _font(st["font"], size)
    asc, desc = f.getmetrics()
    total_h = asc + (len(lines) - 1) * size * lh + desc * 0.3
    top = y + (h - total_h) / 2
    for i, ln in enumerate(lines):
        lw = _width(draw, ln, f, track)
        if st["align"] == "center":
            lx = x + (w - lw) / 2
        elif st["align"] == "right":
            lx = x + w - lw
        else:
            lx = x
        _draw_line(draw, lx, top + asc + i * size * lh, ln, f, track, st["color"])
    return size / SCALE


def sana_matni(d):
    return f"{d.day}-{OYLAR[d.month - 1]}, {d.year}"


SITE = "https://yosinxon-reg.github.io/kun-oqituvchisi-bot/"


def qr_url(raqam):
    return f"{SITE}?n={int(raqam)}"


def draw_qr(im, box, url):
    import qrcode
    q = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10)
    q.add_data(url)
    q.make(fit=True)
    img = q.make_image(fill_color="#1B2340", back_color="white").convert("RGB")
    x, y, w, h = [int(round(v)) for v in box]
    im.paste(img.resize((w, h), Image.NEAREST), (x, y))


def render(variant, maktab, ism, raqam, sana, filial="", fmt="JPEG"):
    im = Image.open(os.path.join(TPL, f"{variant}_{maktab}.png")).convert("RGB")
    spec = json.load(open(os.path.join(TPL, f"{variant}_{maktab}.json")))
    d = ImageDraw.Draw(im)
    ism = re.sub(r"\s+", " ", ism).strip()
    draw_field(d, ism, spec["name"])
    if filial:
        f = filial if "filial" in filial.lower() else f"{filial} filiali"
        draw_field(d, f, spec["filial"])
    draw_field(d, sana_matni(sana), spec["date"])
    draw_field(d, f"№ {int(raqam):04d}", spec["number"])
    if "qr" in spec:
        draw_qr(im, spec["qr"]["box"], qr_url(raqam))
    buf = io.BytesIO()
    if fmt == "JPEG":
        im.save(buf, "JPEG", quality=93, optimize=True, dpi=(300, 300))
    else:
        im.save(buf, fmt)
    buf.seek(0)
    return buf
