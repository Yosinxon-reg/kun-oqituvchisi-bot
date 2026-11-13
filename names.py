"""Ustoz ismlarini rasmiy röyxat (Registon portali) bilan solişhtiriş.

Natija holatlari:
  ok    — röyxatdagi bilan aynan bir xil
  auto  — işonçli tuzatiş (alifbo, x/h, o'/u, ye/e, ism-familiya örni, otasining ismi, 1 harflik imlo xato)
  savol — aniqlaştiriş kerak (ikki öxşaş nomzod, öxşaşlik örtaça, filial yozilmagan)
  yoq   — şu filial va fanda röyxatda yöq (boşqa joyda topilsa — nomzod sifatida körsatiladi)
Hеç qaçon röyxatda yöq ism töqib çiqarilmaydi.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

CYR = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ё": "yo", "ж": "j", "з": "z", "и": "i", "й": "y",
       "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
       "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "'", "ы": "i", "ь": "", "э": "e",
       "ю": "yu", "я": "ya", "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h"}
APOS = "ʻ‘’`ʼ´′"
OTA_T = re.compile(r"(ovich|evich|ovna|evna|ovic|evic)$")
OTA_W = {"qizi", "o'g'li", "ogli", "ugli", "u'gli", "ug'li", "o'gli", "og'li", "qiz", "kizi"}
SUFX = ("xonim", "xon", "jon", "bek", "oy", "bonu", "begim", "bibi", "niso")


def cyr2lat(s):
    out, prev = [], ""
    for ch in s:
        lo = ch.lower()
        if lo == "е":
            t = "ye" if (not prev or prev in "aeiouаеёиоуэюяў ") else "e"
        else:
            t = CYR.get(lo)
        if t is None:
            out.append(ch)
        else:
            out.append(t.capitalize() if ch != lo and t else t)
        prev = lo
    return "".join(out)


def canon(s):
    """Eski lotin, kiçik harf, apostroflar bitta."""
    s = cyr2lat(s or "")
    for a in APOS:
        s = s.replace(a, "'")
    s = s.lower()
    for a, b in (("ş", "sh"), ("ç", "ch"), ("ğ", "g'"), ("ö", "o'"), ("ı", "i"), ("i̇", "i")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip(" .,;:-–—")


def phon(tok):
    """Talaffuz kaliti: o'/u, x/h, q/k, ye/e, dj/j, iy/i, ikkilangan harflar."""
    t = tok.replace("o'", "u").replace("g'", "g").replace("'", "")
    t = re.sub(r"[^a-z.]", "", t)
    for a, b in (("dj", "j"), ("h", "x"), ("q", "k"), ("ye", "e"), ("iy", "i"), ("yo", "yu"), ("ts", "s"), ("w", "v")):
        t = t.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", t)


def tokens(name):
    """Asosiy qism: otasining ismi va «qizi/o'g'li» olib taşlanadi."""
    ws = [w for w in canon(name).split(" ") if w]
    core = []
    for i, w in enumerate(ws):
        if w in OTA_W:
            if len(core) > 2:
                core.pop()
            continue
        if i >= 2 and OTA_T.search(w):
            continue
        core.append(w)
    return core[:2]


def yangi(s):
    """Röyxat (eski lotin) -> yangi alifbo: o' -> ö, g' -> ğ, sh -> ş, ch -> ç; boşqa apostrof -> ʼ."""
    s = cyr2lat(s or "")
    for a in APOS:
        s = s.replace(a, "'")
    s = re.sub(r"([oO])'", lambda m: "Ö" if m.group(1) == "O" else "ö", s)
    s = re.sub(r"([gG])'", lambda m: "Ğ" if m.group(1) == "G" else "ğ", s)
    s = s.replace("Sh", "Ş").replace("SH", "Ş").replace("sh", "ş").replace("Ch", "Ç").replace("CH", "Ç").replace("ch", "ç")
    s = s.replace("'", "ʼ")
    return re.sub(r"\s+", " ", s).strip()


SURN = re.compile(r"(ova|eva|yeva|ov|ev|yev|iy|aya|ovna|xonova|zoda|ina)$", re.I)


def display(name):
    """Röyxat yozuvini taşakkurnoma uçun: yangi alifbo, bosh harflar, kerak bölsa Familiya Ism tartibi."""
    s = yangi(name)
    ws = s.split(" ")
    ws = [w if not w.isupper() or len(w) <= 2 else w.capitalize() for w in ws]
    ws = [w[0].upper() + w[1:] if w and w[0].islower() and w.lower() not in ("qizi", "öğli", "uğli", "oğli") else w for w in ws]
    if len(ws) == 2 and SURN.search(ws[1]) and not SURN.search(ws[0]):
        ws = [ws[1], ws[0]]
    return " ".join(ws)


def lev(a, b):
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def tok_d(a, b):
    """Bir söz masofasi; qöşimça (Nargiza/Nargizaxon) -> 0.5"""
    if a == b:
        return 0.0
    for x, y in ((a, b), (b, a)):
        if x.startswith(y) and x[len(y):] in [phon(s) for s in SUFX] and len(y) >= 4:
            return 0.5
    return float(lev(a, b))


def compare(pc, rc):
    """pc, rc — tokens() natijasi. -> (tur, masofa, tafsil) yoki None"""
    if not pc or not rc:
        return None
    pp = [phon(t) for t in pc]
    rp = [phon(t) for t in rc]
    if len(rc) == 2 and len(rp[1].strip(".")) == 1:          # «Bektemirova R.»
        ini = rp[1].strip(".")
        for i, t in enumerate(pp):
            other = pp[1 - i] if len(pp) == 2 else ""
            if t == rp[0] and other.startswith(ini):
                return ("init", 0.0, [0.0, 0.0])
        return None
    if len(rc) == 1:
        return ("single", 0.0, [0.0]) if rp[0] in pp else None
    if len(pp) < 2:
        return None
    best = None
    for a, b, swap in ((pp[0], pp[1], False), (pp[1], pp[0], True)):
        d1, d2 = tok_d(a, rp[0]), tok_d(b, rp[1])
        cand = (d1 + d2, [d1, d2], swap, a, b)
        if best is None or cand[0] < best[0]:
            best = cand
    d, parts, swap, a, b = best
    if d == 0:
        return ("phon", 0.0, parts)
    if all(x in (0.0, 0.5) for x in parts):
        return ("suffix", d, parts)
    return ("fuzzy", d, parts + [a[:1] == rp[0][:1], min(len(rp[0]), len(rp[1]))])


FAN_KW = [
    ("Ingliz tili", ["ingliz", "english", "inglis", "ielts", "anglis"]),
    ("Rus tili", ["rus til", "rus fan", "rus ", "русск", "rustili"]),
    ("Arab tili", ["arab"]),
    ("Ona tili", ["ona til"]),
    ("Adabiyot", ["adabiyot"]),
    ("Matematika", ["matem", "algebra", "geometr"]),
    ("Fizika", ["fizika"]),
    ("Kimyo", ["kimyo", "ximiya"]),
    ("Biologiya", ["biolog"]),
    ("Geografiya", ["geograf"]),
    ("Tarix", ["tarix", "huquq"]),
    ("Informatika", ["informatika", "it fan", "it öqit", "dasturlash"]),
    ("Tarbiya", ["tarbiya"]),
    ("Boshlang'ich ta'lim", ["boshlang", "boşlanğ", "boslang", "sinf rahbar", "sinf öqit", "sinf o'qit", "1-sinf", "2-sinf", "3-sinf", "4-sinf"]),
    ("Bog'cha", ["bog'cha", "boğça", "bogcha", "mtt", "maktabgaça", "maktabgacha", "tarbiyaçi", "tarbiyachi"]),
    ("Ochiq mashg'ulot", ["ochiq mash", "oçiq maş"]),
    ("Gimnastika", ["gimnast"]),
    ("Kamondan o'q otish", ["kamon"]),
    ("Muhandislik", ["muhandis"]),
    ("Robototexnika", ["robot"]),
    ("Shaxmat", ["shaxmat", "şaxmat", "shahmat"]),
    ("Taekvondo", ["taekvondo", "tekvondo"]),
    ("Tasviriy san'at", ["tasviriy", "rasm"]),
    ("Suzish", ["suzish", "suziş"]),
    ("Futbol va jismoniy tarbiya", ["futbol", "jismoniy"]),
    ("Ot sporti", ["ot sport", "otda"]),
    ("Musiqa", ["musiqa"]),
    ("Tikuvchilik", ["tikuv"]),
]


def fan_set(*texts):
    low = " " + " ".join(canon(t or "") for t in texts) + " "
    low = low.replace("ş", "sh")
    out = set()
    for fan, kws in FAN_KW:
        if any(canon(k) in low for k in kws):
            out.add(fan)
    if "Tarbiya" in out and "Futbol va jismoniy tarbiya" in out:
        out.discard("Tarbiya")
    return out


# ------------------------------------------------------------------ röyxat
def parse_roster_text(t):
    FIL = {"BUXORO": "Buxoro", "CHILONZOR": "Çilonzor", "FARG'ONA": "Farğona", "FARGONA": "Farğona",
           "SAMARQAND": "Samarqand", "SERGELI TURKISTON": "Turkiston", "TURKISTON": "Turkiston",
           "TINCHLIK": "Tinçlik", "YUNUSOBOD": "Yunusobod"}
    out, fil, tur = [], None, None
    for line in t.split("\n"):
        m = re.match(r"\s*=+\s*(.+?)\s*=+\s*$", line)
        if m:
            k = canon(m.group(1)).upper().replace("ʼ", "'")
            fil = FIL.get(k) or next((v for kk, v in FIL.items() if kk in k), None)
            continue
        if line.lower().startswith("asosiy fan"):
            tur = "asosiy"; continue
        if line.lower().startswith("amaliyot fan"):
            tur = "amaliyot"; continue
        m = re.match(r"\s*-\s*([^:]+):\s*(.+)", line)
        if m and fil:
            for n in m.group(2).split(";"):
                if n.strip():
                    out.append({"ism": n.strip(), "filial": fil, "fan": m.group(1).strip(), "tur": tur or "asosiy"})
    return out


_BASE = None


def base_roster():
    global _BASE
    if _BASE is None:
        _BASE = json.load(open(os.path.join(HERE, "roster.json"), encoding="utf-8"))["ustozlar"]
    return _BASE


def roster(st):
    rs = st.get("roster") or base_roster()
    fx = st.get("roster_fix", {})
    out = []
    for i, e in enumerate(rs + st.get("roster_add", [])):
        e = dict(e, k=i)
        nv = fx.get(f"{e['ism']}|{e['filial']}")
        if nv:
            e["ism"] = nv
        out.append(e)
    return out


def alias_key(name, filial):
    return "|".join(sorted(phon(t) for t in tokens(name))) + "|" + (filial or "")


def check(st, ism, filial, fan_text):
    """-> dict(holat, rasmiy, nomzodlar, izoh, turi)"""
    if not ism:
        return {"holat": "yoq", "rasmiy": None, "nomzodlar": [], "izoh": "ism topilmadi", "turi": None}
    R = roster(st)
    fans = fan_set(fan_text)
    pc = tokens(ism)
    post_disp = yangi(ism)
    # 1) avvalgi qaror (alias)
    al = st.get("aliases", {}).get(alias_key(ism, filial))
    if al:
        e = next((x for x in R if x["ism"] == al["ism"] and x["filial"] == al["filial"]), None)
        if e:
            disp = al.get("disp") or display(e["ism"])
            return {"holat": "ok" if disp == post_disp else "auto", "rasmiy": disp, "nomzodlar": [_c(e, 0, "alias")],
                    "izoh": "avvalgi qaror asosida", "turi": "alias"}
    scored = []
    for e in R:
        c = compare(pc, tokens(e["ism"]))
        if c:
            scored.append((e, c))

    def scope(e):
        if filial and e["filial"] == filial and (not fans or e["fan"] in fans):
            return 1
        if filial and e["filial"] == filial:
            return 2
        return 3

    prim = 1 if (filial and fans) else 2 if filial else 3
    strong = [(e, c) for e, c in scored if c[0] in ("phon", "suffix", "init", "single")]
    fuzzy = sorted([(e, c) for e, c in scored if c[0] == "fuzzy" and c[1] <= 3], key=lambda x: x[1][1])

    def uniq(lst):
        seen, out = set(), []
        for e, c in lst:
            k = (display(e["ism"]), e["filial"])
            if k not in seen:
                seen.add(k)
                out.append((e, c))
        return out

    P = uniq([(e, c) for e, c in strong if scope(e) <= prim])
    cands = uniq(sorted(strong + fuzzy, key=lambda x: (scope(x[0]), x[1][1])))[:3]
    nom = [_c(e, c[1], c[0]) for e, c in cands]
    if len(P) == 1:
        e, c = P[0]
        if c[0] == "init":
            disp = post_disp
            return {"holat": "auto" if prim < 3 else "savol", "rasmiy": disp, "nomzodlar": nom, "turi": "init",
                    "izoh": f"röyxatda faqat bosh harf bor («{e['ism']}») — portalda töliq ismni kiritiş kerak"}
        if c[0] == "single":
            return {"holat": "savol", "rasmiy": None, "nomzodlar": nom, "turi": "single",
                    "izoh": f"röyxatda faqat «{e['ism']}» deb yozilgan (familiyasiz)"}
        disp = display(e["ism"])
        if prim == 3:
            return {"holat": "savol", "rasmiy": None, "nomzodlar": nom, "turi": c[0],
                    "izoh": f"postda filial yözilmagan; röyxatda {e['filial']}, {e['fan']}"}
        return {"holat": "ok" if disp == post_disp else "auto", "rasmiy": disp, "nomzodlar": nom, "turi": c[0],
                "izoh": "" if disp == post_disp else _why(c)}
    if len(P) > 1:
        return {"holat": "savol", "rasmiy": None, "nomzodlar": [_c(e, c[1], c[0]) for e, c in P[:3]], "turi": "kop",
                "izoh": "bir filial/fanda bir nečta mos ustoz bor — taxmin qilinmaydi"}
    # 2) imlo xatosi (fuzzy) — faqat asosiy doirada va qatʼiy şartlar bilan
    PF = uniq([(e, c) for e, c in fuzzy if scope(e) <= prim])
    if PF and prim < 3:
        e, c = PF[0]
        d, parts, first_ok, minlen = c[1], c[2][:2], c[2][2], c[2][3]
        rival = [x for x in uniq(fuzzy + strong) if x[0] is not e and x[0]["filial"] == filial and x[1][1] <= d + 2]
        safe = (d <= 2 and max(parts) <= 1 and first_ok and minlen >= 4 and not rival)
        if safe:
            return {"holat": "auto", "rasmiy": display(e["ism"]), "nomzodlar": nom, "turi": "fuzzy",
                    "izoh": f"imlo xatosi tuzatildi ({int(d) if d == int(d) else d} harf farqi)"}
        return {"holat": "savol", "rasmiy": None, "nomzodlar": nom, "turi": "fuzzy",
                "izoh": "öxşaş ustoz bor, lekin avtomatik tuzatiş uçun yetarliça işonçli emas"}
    if cands and not filial:
        e = cands[0][0]
        return {"holat": "savol", "rasmiy": None, "nomzodlar": nom, "turi": "filialsiz",
                "izoh": f"postda filial yozilmagan; öxşaşi röyxatda {e['filial']}, {e['fan']} böyiça turibdi"}
    if cands:
        e = cands[0][0]
        where = f"{e['filial']}, {e['fan']}"
        return {"holat": "yoq", "rasmiy": None, "nomzodlar": nom, "turi": "boshqa",
                "izoh": f"şu filial va fanda röyxatda yöq; öxşaşi röyxatda {where} böyiça turibdi"}
    return {"holat": "yoq", "rasmiy": None, "nomzodlar": [], "turi": None,
            "izoh": "röyxatda yöq (yangi ustoz, boşqa filial yoki notöğri fan bölişi mumkin)"}


def _c(e, d, tur):
    sc = {"phon": 100, "alias": 100, "suffix": 95, "init": 90, "single": 80}.get(tur, max(50, 100 - int(d * 12)))
    return {"ism": e["ism"], "disp": display(e["ism"]), "filial": e["filial"], "fan": e["fan"], "ball": sc}


def _why(c):
    t = c[0]
    if t == "phon":
        return "yozuv röyxatdagi şaklga keltirildi"
    if t == "suffix":
        return "ism qöşimçasi röyxatdagi şaklga keltirildi"
    return ""
