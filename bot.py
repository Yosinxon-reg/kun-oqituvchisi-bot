"""@kun_oqituvchisi_bot — «KUN O'QITUVCHISI» guruhi uchun.

Kun davomida: guruhga tushgan «Sana / Filial / Ustoz / Natija: 25 ball — «Kun öqituvçisi»» postlaridan
ustozlarni yig'adi (bir kunda bir ustoz — bir marta).
Kun oxirida (sozlanadigan vaqt, standart 18:00): egasiga
  1) «FILIALLAR KESIMIDAGI ... OYI JORIY NATIJALARI» reytingi,
  2) «KUNLIK UMUMIY NATIJALAR — ENG KUÇLI 5 TALIK»,
  3) har bir ustozning tashakkurnomasi (ketma-ket raqam, NOMINATSIYA izohi bilan) yuboriladi.
«NOMINATSIYA» va reyting postlari (natijalarning o'zi) o'qilmaydi.
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import traceback
from zoneinfo import ZoneInfo

import requests

import render2

TOKEN = os.environ["BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"
TZ = ZoneInfo("Asia/Tashkent")
STATE_FILE = os.environ.get("STATE_FILE", "state.enc")
STATE_KEY = os.environ.get("STATE_KEY")
RUN_SECONDS = int(os.environ.get("RUN_SECONDS", "0"))
GIT_SYNC = os.environ.get("GIT_SYNC") == "1"

OY = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul",
      "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
render2.OYLAR = OY

# normallashgan kalit -> filial nomi (yangi alifbo), maktab shabloni
FILIAL = {
    "sergeli": ("Turkiston", "turkiston"), "turkiston": ("Turkiston", "turkiston"),
    "turkistan": ("Turkiston", "turkiston"),
    "tinclik": ("Tinçlik", "registon"), "fargona": ("Farğona", "registon"),
    "yunusobod": ("Yunusobod", "registon"), "cilonzor": ("Çilonzor", "registon"),
    "samarqand": ("Samarqand", "registon"), "buxoro": ("Buxoro", "registon"),
}
FILIAL_NOMLARI = ["Çilonzor", "Farğona", "Yunusobod", "Buxoro", "Samarqand", "Turkiston", "Tinçlik"]

DEFAULT_IZOH = "🏆🏆🌟KUN ÖQITUVÇISI NOMINATSIYASI🌟🏆🏆\n{filial} maktabi\n{ism} {fan}"


def _norm(t):
    t = t.lower()
    for a, b in (("ʻ", ""), ("‘", ""), ("’", ""), ("'", ""), ("`", ""), ("ch", "c"), ("sh", "s"),
                 ("ç", "c"), ("ş", "s"), ("ğ", "g"), ("ö", "o")):
        t = t.replace(a, b)
    return t


def find_filial(text):
    low = _norm(text or "")
    for key_, val in FILIAL.items():
        if key_ in low:
            return val
    return None


def sana(d):
    return f"{d.day}-{OY[d.month - 1]}"


# ---------------------------------------------------------------- holat
def _fernet():
    from cryptography.fernet import Fernet
    return Fernet(STATE_KEY.encode())


def default_state():
    return {
        "offset": 0, "owner": None, "next": 154, "izoh": DEFAULT_IZOH, "dizayn": "v3",
        "vaqt": "18:00",
        "items": [],            # kun davomida yig'ilgan ustozlar
        "log": [],              # berilgan tashakkurnomalar
        "oy": "2026-11",
        "oy_soni": {"Çilonzor": 22, "Farğona": 35, "Yunusobod": 29, "Buxoro": 16,
                    "Samarqand": 21, "Turkiston": 12, "Tinçlik": 19},
        "xodimlar": {"Çilonzor": 54, "Farğona": 86, "Yunusobod": 79, "Buxoro": 58,
                     "Samarqand": 85, "Turkiston": 51, "Tinçlik": 96},
        "orin": {"Çilonzor": 1, "Farğona": 2, "Yunusobod": 3, "Buxoro": 4,
                 "Samarqand": 5, "Turkiston": 6, "Tinçlik": 7},
        "kunlik": {"2026-11-12": 31, "2026-11-09": 21, "2026-11-11": 21, "2026-11-10": 20,
                   "2026-10-20": 16},
        "filial_kun": [["Yunusobod", 11, "2026-11-10"], ["Farğona", 9, "2026-11-12"],
                       ["Farğona", 7, "2026-10-28"], ["Farğona", 7, "2026-10-30"],
                       ["Farğona", 6, "2026-09-16"], ["Yunusobod", 6, "2026-11-09"],
                       ["Samarqand", 6, "2026-11-11"], ["Samarqand", 6, "2026-11-12"]],
        "hisobot_sana": "2026-11-12",
    }


def load_state():
    st = default_state()
    if os.path.exists(STATE_FILE):
        raw = open(STATE_FILE, "rb").read()
        if STATE_KEY:
            raw = _fernet().decrypt(raw)
        st.update(json.loads(raw))
    return st


def save_state(st, msg="holat"):
    st["log"] = st["log"][-3000:]
    st["items"] = st["items"][-500:]
    raw = json.dumps(st, ensure_ascii=False).encode()
    if STATE_KEY:
        raw = _fernet().encrypt(raw)
    tmp = STATE_FILE + ".tmp"
    open(tmp, "wb").write(raw)
    os.replace(tmp, STATE_FILE)
    if GIT_SYNC:
        subprocess.run(["git", "add", STATE_FILE], check=False)
        if subprocess.run(["git", "commit", "-q", "-m", msg], capture_output=True).returncode == 0:
            for _ in range(3):
                if subprocess.run(["git", "push", "-q"]).returncode == 0:
                    break
                subprocess.run(["git", "pull", "-q", "--rebase", "-X", "ours"])


# ---------------------------------------------------------------- telegram
def tg(method, **kw):
    files = kw.pop("files", None)
    for attempt in range(5):
        try:
            r = requests.post(f"{API}/{method}", data=kw if files else None,
                              json=None if files else kw, files=files, timeout=70)
            j = r.json()
            if j.get("ok"):
                return j["result"]
            if j.get("error_code") == 429:
                time.sleep(j.get("parameters", {}).get("retry_after", 5))
                continue
            print("TG xato", method, j.get("description"), file=sys.stderr)
            return None
        except requests.RequestException as e:
            print("tarmoq", e, file=sys.stderr)
            time.sleep(3 + attempt * 3)
    return None


def say(chat, text, **kw):
    return tg("sendMessage", chat_id=chat, text=text, **kw)


# ---------------------------------------------------------------- post tahlili
WORD = r"[A-ZÖĞŞÇ][\w'ʻ‘’`\-]+"
OTA = re.compile(r"(ovich|evich|ovna|evna|qizi|o['ʻ‘’`]?g['ʻ‘’`]?li|ugli)$", re.I)
FIELD = re.compile(r"^[^\w\n]*([\w'ʻ‘’` ]{2,40}?)[^\w\n]*\s*:\s*(.+)$", re.M)
STOP = {"robototexnika", "texnologiya", "taekvondo", "kamon", "kamondan", "shaxmat", "şaxmat",
        "futbol", "gimnastika", "suziş", "suzish", "rus", "ingliz", "arab", "ona", "matematika",
        "musiqa", "rasm", "tasviriy", "boşlanğiç", "boshlang'ich", "fan", "fani", "tili", "sinf",
        "öqituvçisi", "o'qituvchisi", "maşğuloti", "mashg'uloti", "ustoz", "ustozi"}


def split_name(s):
    """«Familiya Ism [Otasining ismi] qolgan» -> (ism, qolgan)."""
    s = re.sub(r"\s+", " ", (s or "").strip(" ,.-–—:«»\"'"))
    words = s.split(" ")
    name = []
    for w in words:
        wc = w.strip(",.;:-–—")
        if not re.match(WORD + "$", wc) or wc.lower() in STOP or (wc.isupper() and len(wc) > 3):
            break
        if len(name) >= 2 and not OTA.search(wc):   # 3-so'z faqat otasining ismi bo'lsa
            break
        name.append(wc)
        if len(name) == 3:
            break
    if len(name) < 2:
        return None, ""
    rest = " ".join(words[len(name):]).strip(" ,.-–—")
    return " ".join(name), rest


def parse_post(text):
    """Kun öqituvçisi postini o'qiydi. -> dict, None (bu post emas) yoki {'xato': ...}"""
    if not text or "natija" not in text.lower():
        return None
    low = _norm(text)
    if "nominatsiya" in low or "joriy natijalari" in low:
        return None                                      # natija postlari — o'qilmaydi
    fields = [(k.strip(), v.strip()) for k, v in FIELD.findall(text)]
    f = {_norm(k): v for k, v in fields}
    natija = next((v for k, v in f.items() if k.startswith("natija")), "")
    if "kun" not in _norm(natija):
        return None                                      # «Kun öqituvçisi» emas
    fil = find_filial(next((v for k, v in f.items() if k.startswith("filial")), "")) or find_filial(text)
    ism, fan = None, ""
    if "ustoz" in f:
        ism, fan = split_name(f["ustoz"])
    else:   # «Boşlanğiç sinf öqituvçisi: Fayziyeva Moxigul»
        for k, v in fields:
            nk = _norm(k)
            if nk.endswith("oqituvcisi") or nk.endswith("oqituvchisi"):
                ism, _ = split_name(v)
                fan = k.lower()
                break
    if not fan:
        fn = f.get("fan", "")
        if fn:
            fan = f"{fn.lower()} fani öqituvçisi"
    fan = re.sub(r"^[-–—,\s]+", "", fan).strip()
    if fan and fan[0].isupper() and not fan.isupper():
        fan = fan[0].lower() + fan[1:]
    if not ism:
        return {"xato": "ism topilmadi"}
    if not fil:
        return {"xato": "filial topilmadi", "ism": ism}
    return {"ism": ism, "filial": fil[0], "maktab": fil[1], "fan": fan}


def key(name):
    return re.sub(r"[^a-zа-я]", "", _norm(name))


# ---------------------------------------------------------------- kun davomida
def add_item(st, p, day, mid=None, chat=None, manba=""):
    for it in st["items"]:
        if it["sana"] == day.isoformat() and key(it["ism"]) == key(p["ism"]):
            return False                                  # bugun bu ustoz bor
    st["items"].append({"ism": p["ism"], "filial": p["filial"], "maktab": p["maktab"],
                        "fan": p["fan"], "sana": day.isoformat(), "mid": mid, "chat": chat,
                        "manba": manba[:300], "hisobot": False, "t": time.time()})
    return True


def handle_group(st, m, edited=False):
    text = m.get("text") or m.get("caption") or ""
    p = parse_post(text)
    if p is None:
        return False
    day = dt.datetime.fromtimestamp(m["date"], TZ).date()
    if "xato" in p:
        if st["owner"]:
            say(st["owner"], f"⚠️ Postda {p['xato']} — tekshiring:\n\n{text[:500]}\n\n"
                             "Qo'lda qo'shish: /yangi Familiya Ism; Filial; fan")
        return False
    if edited:   # tahrir qilingan post — mos yozuvni yangilash
        for it in st["items"]:
            if it.get("mid") == m["message_id"] and it.get("chat") == m["chat"]["id"] and not it["hisobot"]:
                it.update(ism=p["ism"], filial=p["filial"], maktab=p["maktab"], fan=p["fan"])
                return True
    return add_item(st, p, day, m["message_id"], m["chat"]["id"], text)


# ---------------------------------------------------------------- kun yakuni
MEDAL = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]


def pct(n, total):
    return 100.0 * n / total if total else 0.0


def fmt_pct(x, k=1):
    return f"{x:.{k}f}".replace(".", ",")


def reyting_xabari(st, day, bugun):
    rows = [(f, st["oy_soni"].get(f, 0), st["xodimlar"].get(f, 0), bugun.get(f, 0)) for f in FILIAL_NOMLARI]
    rows.sort(key=lambda r: (-pct(r[1], r[2]), FILIAL_NOMLARI.index(r[0])))
    out = [f"🏆 FILIALLAR KESIMIDAGI {OY[day.month - 1].upper()} OYI JORIY NATIJALARI", "",
           f"📅 {sana(day)} holatiga — foizlar böyiça umumiy reyting", ""]
    for a, b in zip(rows, rows[1:]):
        pa, pb = pct(a[1], a[2]), pct(b[1], b[2])
        if fmt_pct(pa) == fmt_pct(pb) and pa != pb:
            out += [f"{a[0]} va {b[0]}ning yaxlitlangan natijasi bir xil — {fmt_pct(pa)}%. Aniq hisobda "
                    f"{a[0]} {fmt_pct(pa, 4)}%, {b[0]} {fmt_pct(pb, 4)}% bölgani uçun {a[0]} oldinda.", ""]
    for i, (f, n, total, b) in enumerate(rows):
        out += [f"{MEDAL[i]} {f} maktabi — {fmt_pct(pct(n, total))}%",
                f"{total} nafar öqituvçidan {n} nafari — “Kun öqituvçisi”",
                f"📈 Bugungi natija: +{b} nafar" if b else "➖ Bugungi natija: 0 nafar", ""]
    out += [f"📎 Eslatma: {sana(day)} kuni jami {sum(bugun.values())} nafar yangi “Kun öqituvçisi” aniqlandi. "
            f"{OY[day.month - 1].capitalize()} oyi böyiça umumiy natija {sum(st['oy_soni'].values())} nafarga yetdi.", ""]
    yangi = {r[0]: i + 1 for i, r in enumerate(rows)}
    eski = st.get("orin", {})
    kot, ot, ciq = [], [], []
    for f in [r[0] for r in rows]:
        o, y = eski.get(f), yangi[f]
        if o is None or o == y:
            continue
        if y < o:
            (kot if y <= 2 else ciq).append(f"{f} {y}-öringa")
        else:
            ot.append(f"{f} {y}-öringa")
    parts = []
    if kot:
        parts.append(", ".join(kot) + " kötarildi.")
    if ot:
        parts.append(", ".join(ot) + " ötdi.")
    if ciq:
        parts.append(", ".join(ciq) + " çiqdi.")
    out.append("📊 Reytingdagi özgarişlar: " + (" ".join(parts) if parts else "örinlar özgarmadi."))
    st["orin"] = yangi
    return "\n".join(out)


def kunlik_xabari(st, day, bugun):
    kun = st["kunlik"]
    oldingi_max = max([v for k, v in kun.items() if k != day.isoformat()] or [0])
    top = sorted(kun.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    out = ["🏆 KUNLIK UMUMIY NATIJALAR — ENG KUÇLI 5 TALIK", "", "Mavjud kunlik hisobotlar böyiça:", ""]
    for i, (k, v) in enumerate(top, 1):
        rek = " — YANGI KUNLIK REKORD!" if (k == day.isoformat() and v > oldingi_max) else "."
        out.append(f"{i}. {sana(dt.date.fromisoformat(k))} — {v} nafar{rek}")
    out += ["", "🎖 BIR FILIALNING BIR KUNLIK ENG YUQORI NATIJALARI", ""]
    fk = sorted(st["filial_kun"], key=lambda r: (-r[1], r[2]))
    counts = sorted({r[1] for r in fk}, reverse=True)
    for ci, c in enumerate(counts[:3]):
        for f, n, d in [r for r in fk if r[1] == c]:
            out.append(f"{['🥇', '🥈', '🥉'][ci]} {f} — {n} nafar — {sana(dt.date.fromisoformat(d))}.")
    if len(counts) > 3:
        c = counts[3]
        out += ["", f"Keyingi eng yuqori körsatkiç — {c} nafar:"]
        by_f = {}
        for f, n, d in [r for r in fk if r[1] == c]:
            by_f.setdefault(f, []).append(dt.date.fromisoformat(d))
        for f, ds in by_f.items():
            ds.sort()
            if len(ds) > 1 and len({(x.year, x.month) for x in ds}) == 1:
                txt = ", ".join(str(x.day) for x in ds[:-1]) + f" va {ds[-1].day}-{OY[ds[-1].month - 1]}"
            else:
                txt = ", ".join(sana(x) for x in ds)
            out.append(f"• {f} — {txt}.")
    bor = [f for f in FILIAL_NOMLARI if bugun.get(f)]
    yoq = [f for f in FILIAL_NOMLARI if not bugun.get(f)]
    xul = []
    if not yoq:
        xul.append("Bugun barça filiallarda yangi natija qayd etildi.")
    elif bor:
        xul.append(f"Bugun {', '.join(yoq)} filiallarida yangi natija qayd etilmadi.")
    if bor:
        mx = max(bugun.values())
        lid = [f for f in bor if bugun[f] == mx]
        xul.append(f"{lid[0]} {mx} nafar bilan kun yetakçisi böldi." if len(lid) == 1 else
                   f"{' va '.join(lid)} {mx} nafardan natija bilan kun yetakçilari böldi.")
    xul.append("Barça filiallar jamoalarini tabriklaymiz!")
    out += ["", "📈 " + " ".join(xul)]
    return "\n".join(out)


def send_cert(st, rec):
    try:
        d = dt.date.fromisoformat(rec["sana"])
        v = st.get("dizayn", "v3")
        if not os.path.exists(os.path.join(render2.TPL, f"{v}_{rec['maktab']}.png")):
            v = "v3"
        jpg = render2.render(v, rec["maktab"], rec["ism"], rec["n"], d, rec["filial"])
        try:
            cap = st["izoh"].format(ism=rec["ism"], filial=rec["filial"], fan=rec["fan"],
                                    raqam=f"{rec['n']:04d}", sana=sana(d)).strip()
        except (KeyError, IndexError, ValueError):
            cap = st["izoh"]
        if tg("sendDocument", chat_id=st["owner"], caption=cap[:1024],
              files={"document": (f"Kun öqituvçisi {rec['n']}.jpg", jpg, "image/jpeg")}) is not None:
            rec["sent"] = True
    except Exception:
        traceback.print_exc()


def kun_yakuni(st, day, qolda=False):
    """Hisobot: reyting + 5 talik + tashakkurnomalar."""
    items = [it for it in st["items"] if not it["hisobot"]]
    if not items:
        if qolda:
            say(st["owner"], "Hozircha yangi «Kun öqituvçisi» yöq.")
        return False
    oy = f"{day.year}-{day.month:02d}"
    if st["oy"] != oy:                      # yangi oy — oylik hisob noldan
        st["oy"] = oy
        st["oy_soni"] = {f: 0 for f in FILIAL_NOMLARI}
    items.sort(key=lambda it: it["t"])
    bugun = {}
    for it in items:
        bugun[it["filial"]] = bugun.get(it["filial"], 0) + 1
    for f, n in bugun.items():
        st["oy_soni"][f] = st["oy_soni"].get(f, 0) + n
        st["filial_kun"] = [r for r in st["filial_kun"] if not (r[0] == f and r[2] == day.isoformat())]
        st["filial_kun"].append([f, n, day.isoformat()])
    st["kunlik"][day.isoformat()] = st["kunlik"].get(day.isoformat(), 0) + sum(bugun.values())
    used = {r["n"] for r in st["log"]}
    recs = []
    for it in items:                         # raqamlar — post tushgan tartibda
        n = st["next"]
        while n in used:
            n += 1
        st["next"] = n + 1
        used.add(n)
        it["hisobot"] = True
        rec = {"n": n, "ism": it["ism"], "filial": it["filial"], "maktab": it["maktab"],
               "fan": it["fan"], "sana": it["sana"], "sent": False}
        st["log"].append(rec)
        recs.append(rec)
    r1 = reyting_xabari(st, day, bugun)
    r2 = kunlik_xabari(st, day, bugun)
    st["hisobot_sana"] = day.isoformat()
    save_state(st, f"hisobot {day}")         # raqamlar yuborishdan OLDIN saqlanadi
    say(st["owner"], r1)
    say(st["owner"], r2)
    order = {f: st["orin"].get(f, 9) for f in FILIAL_NOMLARI}
    for rec in sorted(recs, key=lambda r: (order.get(r["filial"], 9), r["n"])):
        send_cert(st, rec)
        time.sleep(1)
    save_state(st, "yuborildi")
    return True


def resend_unsent(st):
    pend = [r for r in st["log"] if r.get("sent") is False]
    for r in pend:
        send_cert(st, r)
        time.sleep(1)
    if pend:
        save_state(st, "qayta yuborildi")


# ---------------------------------------------------------------- egasi buyruqlari
HELP = ("Men «KUN O'QITUVCHISI» guruhini kuzataman.\n\n"
        "Kun davomida «Sana / Filial / Ustoz / Natija: 25 ball — «Kun öqituvçisi»» postlaridan ustozlarni yig'aman. "
        "Har kuni {vaqt} da sizga reyting, 5 talik va har bir ustozning tashakkurnomasini yuboraman.\n\n"
        "/bugun — bugun yig'ilgan ustozlar\n"
        "/hisobot — hisobotni hozir yuborish\n"
        "/yangi Familiya Ism; Filial; fan — qo'lda qo'shish\n"
        "/ochir 3 — /bugun ro'yxatidagi 3-ustozni olib tashlash\n"
        "/vaqt 18:00 — kunlik hisobot vaqti\n"
        "/raqam 160 — keyingi tashakkurnoma raqami\n"
        "/xodim Çilonzor 54 — filialdagi öqituvçilar soni\n"
        "/izoh <matn> — tashakkurnoma izohi ({ism}, {filial}, {fan}, {raqam}, {sana})\n"
        "/dizayn 1…5 — tashakkurnoma dizayni\n"
        "/holat — sozlamalar")


def bugun_list(st):
    return [it for it in st["items"] if not it["hisobot"]]


def handle_private(st, m):
    chat = m["chat"]["id"]
    text = (m.get("text") or "").strip()
    if st["owner"] is None and text.startswith("/start"):
        st["owner"] = chat
        say(chat, HELP.replace("{vaqt}", st["vaqt"]))
        return True
    if chat != st["owner"]:
        say(chat, "Bu bot faqat Monitoring bölimi rahbari uçun.")
        return False
    body = text or (m.get("caption") or "").strip()
    if not body:
        return False
    if not body.startswith("/"):
        p = parse_post(body)
        if p and "xato" not in p:
            ok = add_item(st, p, dt.datetime.now(TZ).date(), manba=body)
            say(chat, f"✅ Qo'shildi: {p['ism']} — {p['filial']}" if ok else f"ℹ️ {p['ism']} bugun allaqaçon bor.")
            return ok
        say(chat, "Bu «Kun öqituvçisi» posti emas yoki ism/filial topilmadi.")
        return False
    cmd, _, arg = text.partition(" ")
    cmd = cmd.split("@")[0].lower()
    arg = arg.strip()
    if cmd in ("/start", "/help"):
        say(chat, HELP.replace("{vaqt}", st["vaqt"]))
    elif cmd == "/bugun":
        L = bugun_list(st)
        say(chat, "\n".join(f"{i}. {it['ism']} — {it['filial']} ({it['fan']})" for i, it in enumerate(L, 1))
            or "Hozircha yöq.")
    elif cmd == "/hisobot":
        return kun_yakuni(st, dt.datetime.now(TZ).date(), qolda=True)
    elif cmd == "/yangi":
        parts = [x.strip() for x in arg.split(";")]
        ism, _ = split_name(parts[0] if parts else "")
        fil = find_filial(parts[1] if len(parts) > 1 else "")
        if not ism or not fil:
            say(chat, "Yozilişi: /yangi Karimov Anvar; Çilonzor; matematika fani öqituvçisi")
            return False
        add_item(st, {"ism": ism, "filial": fil[0], "maktab": fil[1],
                      "fan": parts[2] if len(parts) > 2 else ""}, dt.datetime.now(TZ).date(), manba="qo'lda")
        say(chat, f"✅ Qo'shildi: {ism} — {fil[0]}")
        return True
    elif cmd == "/ochir":
        L = bugun_list(st)
        if arg.isdigit() and 1 <= int(arg) <= len(L):
            it = L[int(arg) - 1]
            st["items"].remove(it)
            say(chat, f"🗑 Olib tashlandi: {it['ism']}")
            return True
        say(chat, "Avval /bugun, keyin masalan: /ochir 3")
    elif cmd == "/vaqt":
        if re.match(r"^\d{1,2}:\d{2}$", arg):
            st["vaqt"] = arg.zfill(5)
            say(chat, f"✅ Kunlik hisobot vaqti: {st['vaqt']}")
            return True
        say(chat, f"Hozir: {st['vaqt']}. Özgartiriş: /vaqt 18:00")
    elif cmd == "/raqam":
        if arg.isdigit():
            st["next"] = int(arg)
            say(chat, f"✅ Keyingi raqam: {st['next']}")
            return True
        say(chat, f"Keyingi raqam: {st['next']}")
    elif cmd == "/xodim":
        mm = re.match(r"^(.+?)\s+(\d+)$", arg)
        fil = find_filial(mm.group(1)) if mm else None
        if fil:
            st["xodimlar"][fil[0]] = int(mm.group(2))
            say(chat, f"✅ {fil[0]}: {mm.group(2)} nafar öqituvçi")
            return True
        say(chat, "\n".join(f"{f}: {n}" for f, n in st["xodimlar"].items()) + "\n\nÖzgartiriş: /xodim Çilonzor 54")
    elif cmd == "/izoh":
        if arg:
            st["izoh"] = arg
            say(chat, "✅ Izoh saqlandi.")
            return True
        say(chat, "Hozirgi izoh:\n\n" + st["izoh"])
    elif cmd == "/dizayn":
        v = arg.lstrip("v")
        if v in ("1", "2", "3", "4", "5"):
            st["dizayn"] = "v" + v
            say(chat, f"✅ {v}-dizayn tanlandi.")
            return True
        say(chat, f"Hozirgi dizayn: {st['dizayn']}. Tanlash: /dizayn 3")
    elif cmd == "/holat":
        say(chat, f"Hisobot vaqti: {st['vaqt']}\nKeyingi raqam: {st['next']}\nBugun yig'ilgan: {len(bugun_list(st))}\n"
                  f"Oxirgi hisobot: {st['hisobot_sana']}\nOylik jami: {sum(st['oy_soni'].values())}")
    else:
        say(chat, "Buyruqni tuşunmadim. /help")
    return False


# ---------------------------------------------------------------- asosiy sikl
def vaqt_keldi(st, now):
    h, mi = map(int, st["vaqt"].split(":"))
    return (now.hour, now.minute) >= (h, mi) and st["hisobot_sana"] < now.date().isoformat()


def main():
    st = load_state()
    tg("deleteWebhook")
    tg("setMyCommands", commands=[
        {"command": "bugun", "description": "Bugun yig'ilgan ustozlar"},
        {"command": "hisobot", "description": "Hisobotni hozir yuborish"},
        {"command": "yangi", "description": "Qo'lda qo'shish"},
        {"command": "ochir", "description": "Ro'yxatdan olib tashlash"},
        {"command": "vaqt", "description": "Hisobot vaqti"},
        {"command": "raqam", "description": "Keyingi raqam"},
        {"command": "xodim", "description": "Filial öqituvçilari soni"},
        {"command": "holat", "description": "Sozlamalar"}])
    print("bot ishga tushdi", flush=True)
    if st["owner"]:
        resend_unsent(st)
    start = time.time()
    while not RUN_SECONDS or time.time() - start < RUN_SECONDS:
        ups = tg("getUpdates", offset=st["offset"], timeout=50,
                 allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post",
                                  "my_chat_member"])
        changed = False
        for u in ups or []:
            st["offset"] = u["update_id"] + 1
            try:
                m = u.get("message") or u.get("channel_post")
                em = u.get("edited_message") or u.get("edited_channel_post")
                if m:
                    if m["chat"]["type"] == "private":
                        changed |= bool(handle_private(st, m))
                    else:
                        changed |= bool(handle_group(st, m))
                elif em and em["chat"]["type"] != "private":
                    changed |= bool(handle_group(st, em, edited=True))
                elif "my_chat_member" in u and st["owner"]:
                    c = u["my_chat_member"]["chat"]
                    say(st["owner"], f"ℹ️ Bot «{c.get('title')}» guruhida: "
                                     f"{u['my_chat_member']['new_chat_member']['status']}")
            except Exception:
                traceback.print_exc()
        now = dt.datetime.now(TZ)
        if st["owner"] and vaqt_keldi(st, now):
            try:
                if not kun_yakuni(st, now.date()):
                    st["hisobot_sana"] = now.date().isoformat()   # bugun hech kim yöq
                    changed = True
            except Exception:
                traceback.print_exc()
        if ups or changed:
            save_state(st, "holat")
        if ups is None:
            time.sleep(5)


if __name__ == "__main__":
    main()
