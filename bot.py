"""@kun_oqituvchisi_bot — «Kun öqituvçisi» hisob-kitob, reyting, taşakkurnoma va rekordlar tizimi.

Asosiy qoidalar (egasi bergan topşiriq böyiça):
* Hisob birligi — tasdiqlangan «Kun öqituvçisi» NATIJALARI soni (noyob ustozlar emas). Foiz 100% bilan çeklanmaydi.
* Bir ustoz bir kalendar oyida 3 martagaça hisoblanadi; 4-natija «tekşiriş kutilmoqda» holatiga ötadi.
* Sana — xabar guruhga yuborilgan sana (Asia/Tashkent), dars sanasi emas.
* Nusxalar: bir xabar (chat+message_id) bir marta; bir xil media (file_unique_id) qayta kelsa — nusxa.
  Tahrir avvalgi yozuvni yangilaydi. Şubhali takrorlar tekşirişga chiqariladi.
* Hisob-kitob va taşakkurnomalar faqat egasining şaxsiy çatiga. Manba guruhiga hech narsa yozilmaydi.
* Ismlar tekşiruvi (rasmiy röyxat böyiça) — har kuni 17:45 da RegMon guruhiga; javoblar doimiy saqlanadi.
"""
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
from fractions import Fraction
from zoneinfo import ZoneInfo

import requests

import names
import render2

TOKEN = os.environ.get("BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}"
TZ = ZoneInfo("Asia/Tashkent")
STATE_FILE = os.environ.get("STATE_FILE", "state.enc")
STATE_KEY = os.environ.get("STATE_KEY")
RUN_SECONDS = int(os.environ.get("RUN_SECONDS", "0"))
GIT_SYNC = os.environ.get("GIT_SYNC") == "1"

OY = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul",
      "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
render2.OYLAR = OY

FILIAL = {  # normallaşgan kalit -> (nom, maktab şabloni)
    "sergeli": ("Turkiston", "turkiston"), "turkiston": ("Turkiston", "turkiston"),
    "turkistan": ("Turkiston", "turkiston"),
    "tinclik": ("Tinçlik", "registon"), "fargona": ("Farğona", "registon"), "fargna": ("Farğona", "registon"),
    "yunusobod": ("Yunusobod", "registon"), "cilonzor": ("Çilonzor", "registon"),
    "samarqand": ("Samarqand", "registon"), "buxoro": ("Buxoro", "registon"),
}
FILIALLAR = ["Tinçlik", "Çilonzor", "Yunusobod", "Samarqand", "Farğona", "Buxoro", "Turkiston"]  # kunlik xabar tartibi
CAP = 3  # bir ustoz bir oyda


def _norm(t):
    t = (t or "").lower()
    for a, b in (("ʻ", ""), ("‘", ""), ("’", ""), ("'", ""), ("`", ""), ("ch", "c"), ("sh", "s"),
                 ("ç", "c"), ("ş", "s"), ("ğ", "g"), ("ö", "o"), ("ı", "i"), ("i̇", "i")):
        t = t.replace(a, b)
    return t


def find_filial(text):
    low = _norm(text)
    for k, v in FILIAL.items():
        if k in low:
            return v
    return None


def now():
    return dt.datetime.now(TZ)


def sana_txt(d, yil=False):
    s = f"{d.day}-{OY[d.month - 1]}"
    return s + f" {d.year}" if yil else s


def D(iso):
    return dt.date.fromisoformat(iso)


# ================================================================ holat
def _fernet():
    from cryptography.fernet import Fernet
    return Fernet(STATE_KEY.encode())


def default_state():
    nov = {"Tinçlik": 96, "Çilonzor": 54, "Yunusobod": 79, "Samarqand": 85, "Farğona": 86, "Buxoro": 58, "Turkiston": 51}
    return {
        "v": 3, "offset": 0, "owner": None, "group": None,
        "next": 154, "izoh": "🏆🏆🌟KUN ÖQITUVÇISI NOMINATSIYASI🌟🏆🏆\n{filial} maktabi\n{ism} {fan}",
        "dizayn": "v3", "vaqt": "18:00",
        "setup_day": None,            # sozlaş kuni: 17:00 dastlabki + 18:00 qayta tekşiriş
        "rid": 0, "results": [],      # manba natijalar
        "baseline": {"2026-11": {"as_of": "2026-11-12",
                                 "by": {"Çilonzor": 22, "Farğona": 35, "Yunusobod": 29, "Buxoro": 16,
                                        "Samarqand": 21, "Turkiston": 12, "Tinçlik": 19}}},
        "xodim_v": [{"from": "2026-11-01", "counts": nov, "sabab": "Noyabr boşlanğiç bazasi (egasi tasdiği)",
                     "kiritildi": "2026-11-13"}],
        "archive_day": {  # tasdiqlangan kunlik arxiv (boşlanğiç qoldiq içida)
            "2026-11-09": {"Tinçlik": 2, "Çilonzor": 3, "Yunusobod": 6, "Samarqand": 3, "Farğona": 2, "Buxoro": 2, "Turkiston": 3},
            "2026-11-10": {"Tinçlik": 0, "Çilonzor": 3, "Yunusobod": 11, "Samarqand": 0, "Farğona": 1, "Buxoro": 4, "Turkiston": 1},
            "2026-11-11": {"Tinçlik": 4, "Çilonzor": 2, "Yunusobod": 1, "Samarqand": 6, "Farğona": 5, "Buxoro": 1, "Turkiston": 2},
            "2026-11-12": {"Tinçlik": 5, "Çilonzor": 4, "Yunusobod": 2, "Samarqand": 6, "Farğona": 9, "Buxoro": 3, "Turkiston": 2},
        },
        "extra_branch_day": [["Farğona", 6, "2026-09-16"], ["Farğona", 7, "2026-10-28"], ["Farğona", 7, "2026-10-30"]],
        "extra_system_day": {"2026-10-20": 16},
        "monthly_hist": [  # [filial, foiz, "YYYY-MM", öquv yili]
            ["Farğona", 92.5, "2026-05", "2025–2026"], ["Çilonzor", 88.6, "2026-10", "2026–2027"],
            ["Farğona", 64.7, "2026-04", "2025–2026"], ["Yunusobod", 64.4, "2026-05", "2025–2026"],
            ["Yunusobod", 61.4, "2026-09", "2026–2027"], ["Farğona", 60.5, "2026-10", "2026–2027"],
            ["Çilonzor", 59.1, "2026-09", "2026–2027"], ["Tinçlik", 57.3, "2026-09", "2026–2027"],
            ["Yunusobod", 55.7, "2026-10", "2026–2027"], ["Farğona", 54.4, "2026-09", "2026–2027"],
            ["Tinçlik", 53.0, "2026-05", "2025–2026"], ["Samarqand", 52.5, "2026-05", "2025–2026"],
            ["Farğona", 50.7, "2026-02", "2025–2026"], ["Samarqand", 50.6, "2026-10", "2026–2027"],
            ["Farğona", 47.9, "2026-03", "2025–2026"], ["Çilonzor", 45.0, "2026-04", "2025–2026"]],
        "order": ["Çilonzor", "Farğona", "Yunusobod", "Buxoro", "Samarqand", "Turkiston", "Tinçlik"],  # oxirgi ekran tartibi
        "ranks": {"Çilonzor": 1, "Farğona": 2, "Yunusobod": 3, "Buxoro": 4, "Samarqand": 5, "Turkiston": 6, "Tinçlik": 7},
        "packages": {},               # "sana|tur" -> {...}
        "rec_snap": None,             # oxirgi yuborilgan rekordlar holati
        "milestones": {},             # "YYYY-MM|filial" -> [100, 200]
        "certs": [],                  # yuborilgan taşakkurnomalar jurnali
        "audit": [],
        # ismlar tekşiruvi
        "regmon": None, "chats": {}, "aliases": {}, "roster_add": [], "roster": None, "qmsg": {},
        "ism_live": None,
    }


def load_state():
    st = default_state()
    if os.path.exists(STATE_FILE):
        raw = open(STATE_FILE, "rb").read()
        if STATE_KEY:
            raw = _fernet().decrypt(raw)
        old = json.loads(raw)
        if old.get("v") == 3:
            st.update(old)
        else:
            st = migrate(old, st)
    if st["rec_snap"] is None:
        st["rec_snap"] = records_state(st, now().date())
    for r in st["results"]:
        if "nc" not in r:
            apply_check(st, r)
    return st


def migrate(old, st):
    """v2 holatidan ko'çiriş: egasi, offset, raqam va yiğilgan natijalar (qayta tekşirib)."""
    for k in ("offset", "owner", "next", "dizayn", "vaqt"):
        if k in old:
            st[k] = old[k]
    st["setup_day"] = now().date().isoformat()
    for it in old.get("items", []):
        if it.get("hisobot"):
            continue
        day = it["sana"]
        if day <= st["baseline"]["2026-11"]["as_of"]:
            audit(st, "migratsiya", f"{it['ism']} ({day}) — boşlanğiç qoldiq içida, qöşilmadi")
            continue
        m = {"chat": {"id": it.get("chat") or 0, "type": "supergroup"}, "message_id": it.get("mid") or 0,
             "date": int(it.get("t") or time.time()), "caption": it.get("manba", "")}
        ingest(st, m, notify=False)
    audit(st, "migratsiya", f"v2 dan ko'çirildi: {len(st['results'])} ta yozuv")
    return st


def save_state(st, msg="holat"):
    st["audit"] = st["audit"][-3000:]
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


def audit(st, tur, matn):
    st["audit"].append([now().isoformat(timespec="seconds"), tur, matn])


# ================================================================ telegram
SENT = []  # sinovda: yuborilganlar


def tg(method, **kw):
    if not TOKEN:  # sinov rejimi
        SENT.append((method, kw))
        return {"message_id": len(SENT)}
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


def say(st, text):
    if not st.get("owner"):
        return None
    out = None
    for i in range(0, len(text), 4000):
        out = tg("sendMessage", chat_id=st["owner"], text=text[i:i + 4000])
    return out


# ================================================================ postni tanib oliş
WORD = r"[A-ZÖĞŞÇ][\w'ʻ‘’`\-]+"
OTA = re.compile(r"(ovich|evich|ovna|evna|qizi|o['ʻ‘’`]?g['ʻ‘’`]?li|ugli)$", re.I)
FIELD = re.compile(r"^[^\w\n]*([\w'ʻ‘’` ]{2,40}?)[^\w\n]*\s*[:;]\s*(.+)$", re.M)
STOP = {"robototexnika", "texnologiya", "taekvondo", "kamon", "kamondan", "shaxmat", "şaxmat",
        "futbol", "gimnastika", "suziş", "suzish", "rus", "ingliz", "arab", "ona", "matematika",
        "musiqa", "rasm", "tasviriy", "boşlanğiç", "boshlang'ich", "fan", "fani", "tili", "sinf",
        "öqituvçisi", "o'qituvchisi", "maşğuloti", "mashg'uloti", "ustoz", "ustozi"}


def split_name(s):
    s = re.sub(r"\s+", " ", (s or "").strip(" ,.-–—:«»\"'"))
    words = s.split(" ")
    name = []
    for w in words:
        wc = w.strip(",.;:-–—")
        if not re.match(WORD + "$", wc) or wc.lower() in STOP or (wc.isupper() and len(wc) > 3):
            break
        if len(name) >= 2 and not OTA.search(wc):
            break
        name.append(wc)
        if w.endswith(("-", "–", "—", ",")) or len(name) == 3:
            break
    if len(name) < 2:
        return None, ""
    rest = " ".join(words[len(name):]).strip(" ,.-–—")
    return " ".join(name), rest


def name_key(name):
    return re.sub(r"[^a-z]", "", _norm(name))


def parse_post(text):
    """-> None (natija posti emas) yoki dict(ism, filial, maktab, fan, dars, tasdiq, sabab)"""
    if not text:
        return None
    low = _norm(text)
    if "nominatsiya" in low or "joriy natijalari" in low or "kunlik umumiy natijalar" in low or "rekord" in low:
        return None                                       # natija/eʼlon postlari — manba emas
    fields = [(k.strip(), v.strip()) for k, v in FIELD.findall(text)]
    f = {}
    for k, v in fields:
        nk = _norm(k)
        nk = "filial" if nk.startswith(("filial", "filal", "fillial")) else nk
        f.setdefault(nk, v)
    ism, fan = None, ""
    if "ustoz" in f:
        ism, fan = split_name(f["ustoz"])
    else:
        for k, v in fields:
            if _norm(k).endswith(("oqituvcisi", "oqituvchisi")):
                ism, _ = split_name(v)
                fan = k.lower()
                break
    has_person = ism is not None or "ustoz" in f
    if not has_person and "filial" not in f:
        return None                                       # oddiy yozişma
    if not fan and f.get("fan"):
        fan = f"{f['fan'].lower()} fani öqituvçisi"
    fan = re.sub(r"^[-–—,\s]+", "", fan).strip()
    if fan and fan[0].isupper() and not fan.isupper():
        fan = fan[0].lower() + fan[1:]
    fil = find_filial(f.get("filial", "")) or find_filial(text)
    natija = next((v for k, v in f.items() if k.startswith("natija")), "")
    nn = _norm(natija)
    tasdiq = ("kun oqituvcisi" in nn or "kun oqituvchisi" in nn or
              ("25" in nn and "akadem" not in nn and "ball" in nn and natija != ""))
    sabab = []
    if not ism:
        sabab.append("ustoz ismi topilmadi")
    if not fil:
        sabab.append("filial topilmadi")
    if not natija:
        sabab.append("«Natija» qatori yöq — «Kun öqituvçisi» tasdiği yöq")
    elif not tasdiq:
        sabab.append(f"natija aniq emas: «{natija[:60]}»")
    return {"ism": ism, "filial": fil[0] if fil else None, "maktab": fil[1] if fil else None, "fan": fan,
            "dars": f.get("dars") or f.get("sinf") or "", "natija": natija, "tasdiq": tasdiq and not sabab,
            "sabab": "; ".join(sabab)}


# ================================================================ natijalar
def month_of(iso):
    return iso[:7]


def counted(st, month=None, filial=None, day=None, ism_n=None, packaged=False):
    out = []
    for r in st["results"]:
        if r["holat"] != "hisob":
            continue
        if packaged and r.get("paket") is None:
            continue
        if month and month_of(r["sana"]) != month:
            continue
        if filial and r["filial"] != filial:
            continue
        if day and r["sana"] != day:
            continue
        if ism_n and r["ism_n"] != ism_n:
            continue
        out.append(r)
    return out


def link(chat, mid):
    s = str(chat)
    return f"https://t.me/c/{s[4:]}/{mid}" if s.startswith("-100") else ""


def recheck_cap(st, r):
    """Oyiga 3 martalik çeklov: 4-natija tekşirişga."""
    if r["holat"] != "hisob" or not r["ism_n"]:
        return
    same = [x for x in counted(st, month_of(r["sana"]), ism_n=r["ism_n"]) if x["id"] != r["id"]]
    before = [x for x in same if (x["posted"], x["id"]) < (r["posted"], r["id"])]
    if len(before) >= CAP:
        r["holat"] = "tekshir"
        r["sabab"] = f"oyiga {CAP} martalik çeklovdan oşdi ({len(before) + 1}-natija)"


def ingest(st, m, notify=True, edited=False):
    """Guruh xabarini qayta işlaş. True -> holat özgardi."""
    text = m.get("text") or m.get("caption") or ""
    chat, mid = m["chat"]["id"], m["message_id"]
    media = None
    for k in ("video", "animation", "document", "video_note"):
        if k in m:
            media = m[k].get("file_unique_id")
    if "photo" in m and m["photo"]:
        media = m["photo"][-1].get("file_unique_id")
    p = parse_post(text)
    old = next((r for r in st["results"] if r["chat"] == chat and r["mid"] == mid), None)
    if p is None:
        if old and edited and old["holat"] != "bekor":    # tahrir natijani olib taşladi
            old["holat"], old["sabab"] = "bekor", "xabar tahrirlanib natija olib taşlandi"
            audit(st, "bekor", f"#{old['id']} {old['ism']}: tahrir")
            return True
        return False
    posted = dt.datetime.fromtimestamp(m["date"], TZ)
    if old:                                               # bir xabar qayta öqildi yoki tahrirlandi
        if not edited:
            return False
        before = (old["ism"], old["filial"], old["holat"])
        old.update(ism=p["ism"], ism_n=name_key(p["ism"] or ""), filial=p["filial"], maktab=p["maktab"],
                   fan=p["fan"], dars=p["dars"], natija=p["natija"], matn=text[:600])
        if old["holat"] != "bekor":
            old["holat"] = "hisob" if p["tasdiq"] else "tekshir"
            old["sabab"] = p["sabab"]
            recheck_cap(st, old)
        if (old["ism"], old["filial"]) != before[:2]:
            apply_check(st, old, force=True)
            if notify:
                live_ism(st, old)
        if (old["ism"], old["filial"], old["holat"]) != before:
            old["tuzatildi"] = bool(old["cert_sent"])
            audit(st, "tahrir", f"#{old['id']}: {before} -> {(old['ism'], old['filial'], old['holat'])}")
            return True
        return False
    if media and any(r.get("media") == media and r["holat"] != "bekor" for r in st["results"]):
        audit(st, "nusxa", f"xabar {mid}: shu media avval qayd etilgan — qöşilmadi")
        return False
    st["rid"] += 1
    r = {"id": st["rid"], "chat": chat, "mid": mid, "link": link(chat, mid), "media": media,
         "posted": posted.isoformat(timespec="seconds"), "sana": posted.date().isoformat(),
         "ism": p["ism"], "ism_n": name_key(p["ism"] or ""), "filial": p["filial"], "maktab": p["maktab"],
         "fan": p["fan"], "dars": p["dars"], "natija": p["natija"], "matn": text[:600],
         "holat": "hisob" if p["tasdiq"] else "tekshir", "sabab": p["sabab"],
         "forward": bool(m.get("forward_origin") or m.get("forward_date")),
         "paket": None, "cert": None, "cert_sent": False, "tuzatildi": False}
    base = st["baseline"].get(month_of(r["sana"]))
    if base and r["sana"] <= base["as_of"]:
        r["holat"], r["sabab"] = "bekor", f"{base['as_of']} gaça boşlanğiç qoldiq içida — qayta qöşilmaydi"
    if r["holat"] == "hisob":
        dup = [x for x in counted(st, day=r["sana"], ism_n=r["ism_n"])]
        if r["forward"] and dup:
            r["holat"], r["sabab"] = "tekshir", "şubhali takror: uzatilgan xabar, şu kuni şu ustoz bor"
        elif any(x.get("dars") and _norm(x["dars"]) == _norm(r["dars"]) for x in dup):
            r["holat"], r["sabab"] = "tekshir", "şubhali takror: şu kuni şu ustozning aynan şu darsi bor"
        recheck_cap(st, r)
    st["results"].append(r)
    apply_check(st, r)
    audit(st, "yangi", f"#{r['id']} {r['ism']} | {r['filial']} | {r['holat']} {r['sabab']} | ism: {r['nc']['holat']}")
    if notify:
        live_ism(st, r)
    if notify and r["holat"] == "tekshir":
        say(st, f"⚠️ Tekşiriş kutilmoqda #{r['id']}\n{r['ism'] or '—'} · {r['filial'] or '—'}\nSabab: {r['sabab']}\n"
                f"{r['link']}\n\nTasdiqlaş: /tasdiq {r['id']}   Bekor: /bekor {r['id']}\n"
                f"Tuzatiş: /tuzat {r['id']} Familiya Ism; Filial; fan")
    return True


# ================================================================ hisoblar
def xodimlar(st, month):
    """Şu oy uçun amaldagi öqituvçilar soni (oy boşidagi versiya)."""
    first = f"{month}-01"
    cur = None
    for v in sorted(st["xodim_v"], key=lambda v: v["from"]):
        if v["from"] <= first or cur is None:
            cur = v["counts"]
    return cur


def month_counts(st, month, packaged=False):
    base = st["baseline"].get(month)
    by = {f: (base["by"].get(f, 0) if base else 0) for f in FILIALLAR}
    for r in counted(st, month, packaged=packaged):
        if base and r["sana"] <= base["as_of"]:
            continue
        by[r["filial"]] = by.get(r["filial"], 0) + 1
    return by


def day_counts(st, iso, packaged=False):
    if iso in st["archive_day"]:
        return dict(st["archive_day"][iso])
    by = {f: 0 for f in FILIALLAR}
    for r in counted(st, day=iso, packaged=packaged):
        by[r["filial"]] += 1
    return by


def known_days(st):
    days = set(st["archive_day"]) | {r["sana"] for r in counted(st)}
    return sorted(days)


def ranking(st, month, packaged=False):
    cnt = month_counts(st, month, packaged)
    xod = xodimlar(st, month)
    frac = {f: Fraction(cnt[f], xod[f]) for f in FILIALLAR}
    prev = {f: i for i, f in enumerate(st.get("order") or FILIALLAR)}
    order = sorted(FILIALLAR, key=lambda f: (-frac[f], prev.get(f, 9)))
    ranks, last, lastr = {}, None, 0
    for i, f in enumerate(order, 1):
        if frac[f] != last:
            lastr, last = i, frac[f]
        ranks[f] = lastr
    return order, ranks, frac, cnt, xod


def pct1(fr):
    return f"{float(fr) * 100:.1f}".replace(".", ",")


def pct4(fr):
    return f"{float(fr) * 100:.4f}".replace(".", ",")


MEDAL = {1: "🥇", 2: "🥈", 3: "🥉", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣", 7: "7️⃣"}


def rating_msg(st, day, today_by, late_note=""):
    month = day.isoformat()[:7]
    order, ranks, frac, cnt, xod = ranking(st, month)
    L = [f"🏆 FILIALLAR KESIMIDAGI {OY[day.month - 1].upper()} OYI JORIY NATIJALARI", "",
         f"📅 {sana_txt(day)} holatiga — foizlar böyiça umumiy reyting", ""]
    for a, b in zip(order, order[1:]):
        if pct1(frac[a]) == pct1(frac[b]) and frac[a] != frac[b]:
            L += [f"{a} va {b}ning yaxlitlangan natijasi bir xil — {pct1(frac[a])}%. Aniq hisobda {a} {pct4(frac[a])}%, "
                  f"{b} {pct4(frac[b])}% bölgani uçun {a} oldinda.", ""]
        elif frac[a] == frac[b]:
            L += [f"{a} va {b}ning natijasi aniq teng — ikkalasi {ranks[a]}-örinda.", ""]
    for f in order:
        b = today_by.get(f, 0)
        L += [f"{MEDAL[ranks[f]]} {f} maktabi — {pct1(frac[f])}%",
              f"{xod[f]} nafar öqituvçi böyiça {cnt[f]} ta “Kun öqituvçisi” natijasi",
              f"📈 Bugungi natija: +{b} ta" if b else "Bugungi natija: 0 ta", ""]
    jt, jm = sum(today_by.values()), sum(cnt.values())
    L.append(f"📎 Eslatma: {sana_txt(day)} kuni jami {jt} ta yangi “Kun öqituvçisi” natijasi qayd etildi. "
             f"{OY[day.month - 1].capitalize()} oyi böyiça umumiy hisob {jm} taga yetdi.")
    if late_note:
        L += ["", late_note]
    old = st.get("ranks", {})
    up = [f"{f} {ranks[f]}-öringa" for f in order if old.get(f) and ranks[f] < old[f]]
    dn = [f"{f} {ranks[f]}-öringa" for f in order if old.get(f) and ranks[f] > old[f]]
    parts = []
    if up:
        parts.append(", ".join(up) + " kötarildi.")
    if dn:
        parts.append(", ".join(dn) + " tuşdi.")
    if parts:
        L += ["", "📊 Reytingdagi özgarişlar: " + " ".join(parts)]
    return "\n".join(L), order, ranks


def counts_msg(by):
    return "\n".join(f"{f}: {by.get(f, 0)} ta" for f in FILIALLAR)


# ================================================================ rekordlar
def records_state(st, upto):
    """Yuborilgan (paketga kirgan) natijalar böyiça rekord holati (taqqoslaş uçun)."""
    days = {}
    for iso in known_days(st):
        if iso <= upto.isoformat():
            days[iso] = day_counts(st, iso, packaged=True)
    sysd = dict(st["extra_system_day"])
    for iso, by in days.items():
        sysd[iso] = sum(by.values())
    top_sys = sorted(sysd.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    br = [list(x) for x in st["extra_branch_day"]]
    for iso, by in days.items():
        for f, n in by.items():
            if n > 0:
                br.append([f, n, iso])
    br.sort(key=lambda r: (-r[1], r[2]))
    cut = br[4][1] if len(br) >= 5 else 0
    top_br = [r for r in br if r[1] >= cut]
    # oylik Top-10: arxiv + joriy oy (bir filial-oy bitta yozuv)
    month = upto.isoformat()[:7]
    order, ranks, frac, cnt, xod = ranking(st, month, packaged=True)
    ent = {(f, ym): [f, p, ym, y, False] for f, p, ym, y in st["monthly_hist"]}
    yil = f"{upto.year}–{upto.year + 1}" if upto.month >= 9 else f"{upto.year - 1}–{upto.year}"
    for f in FILIALLAR:
        ent[(f, month)] = [f, round(float(frac[f]) * 100, 4), month, yil, True]
    top10 = sorted(ent.values(), key=lambda e: -e[1])[:10]
    best = {}
    for f, p, ym, y, cur in ent.values():
        if f not in best or p > best[f][1]:
            best[f] = [f, p, ym, y, cur]
    return {"top_sys": top_sys, "top_br": top_br, "top10": [[e[0], round(e[1], 1), e[2], e[3], e[4]] for e in top10],
            "best": {f: [b[0], round(b[1], 1), b[2], b[3], b[4]] for f, b in best.items()},
            "milest": {f: [m for m in (100, 200, 300) if frac[f] * 100 >= m] for f in FILIALLAR}, "month": month}


def ym_txt(ym, yil=None):
    y, m = ym.split("-")
    return f"{OY[int(m) - 1]}, {yil}" if yil else f"{OY[int(m) - 1]} {y}"


def record_posts(st, day):
    """Faqat özgargan rekordlar haqida bitta yaxlit post."""
    old, new = st["rec_snap"], records_state(st, day)
    parts = []
    if old and new["top_sys"] != old["top_sys"]:
        o1 = old["top_sys"][0] if old["top_sys"] else None
        n1 = new["top_sys"][0]
        if o1 and n1[1] > o1[1] and n1[0] != o1[0]:
            parts.append(f"🏆 YANGI KUNLIK REKORD!\n\nBugun barça filiallar böyiça {n1[1]} ta “Kun öqituvçisi” natijasi qayd etildi.\n\n"
                         f"Avvalgi rekord: {o1[1]} ta — {sana_txt(D(o1[0]), True)}.\nYangi rekord: {n1[1]} ta — {sana_txt(D(n1[0]), True)}.\n"
                         f"Ösiş: +{n1[1] - o1[1]} ta.")
        else:
            parts.append("📊 UMUMIY KUNLIK TOP-5 (mavjud tasdiqlangan arxiv böyiça)\n\n" +
                         "\n".join(f"{i}. {sana_txt(D(k), True)} — {v} ta" for i, (k, v) in enumerate(new["top_sys"], 1)))
    if old and new["top_br"] != old["top_br"]:
        L = ["🎖 BIR FILIALNING BIR KUNLIK TOP-5 (mavjud tasdiqlangan arxiv böyiça)", ""]
        for f, n, iso in new["top_br"]:
            rk = 1 + sum(1 for x in new["top_br"] if x[1] > n)
            L.append(f"{rk}. {f} — {n} ta — {sana_txt(D(iso), True)}")
        if len(new["top_br"]) > 5:
            L += ["", "Teng natijalar sababli röyxatda 5 tadan köp yozuv bor."]
        parts.append("\n".join(L))
    if old and new["top10"] != old["top10"] and any(e[4] for e in new["top10"]):
        L = ["📈 TARIXIY OYLIK TOP-10", ""]
        for i, (f, p, ym, y, cur) in enumerate(new["top10"], 1):
            s = f"{i}. {f} — {str(p).replace('.', ',')}% — {ym_txt(ym, y)}"
            L.append(f"<b>{s} (joriy natija, oy yakunlanmagan)</b>" if cur else s)
        parts.append("\n".join(L))
    if old:
        for f in FILIALLAR:
            ob, nb = old["best"].get(f), new["best"].get(f)
            if nb and nb[4] and ob and nb[1] > ob[1] and not ob[4]:
                parts.append(f"⭐️ {f}: şaxsiy oylik rekord yangilandi — {str(nb[1]).replace('.', ',')}% "
                             f"(avvalgi: {str(ob[1]).replace('.', ',')}%, {ym_txt(ob[2], ob[3])}). Joriy natija, oy yakunlanmagan.")
        for f in FILIALLAR:
            om = set(old["milest"].get(f, [])) if old.get("month") == new["month"] else set()
            for mm in new["milest"][f]:
                key = f"{new['month']}|{f}"
                if mm not in om and mm not in st["milestones"].get(key, []):
                    parts.append(f"🎯 {f}: {OY[day.month - 1]} oyida natijalar nisbati {mm}% marrasidan birinçi marta ötdi.")
                    st["milestones"].setdefault(key, []).append(mm)
    return parts, new


# ================================================================ paket
def pending_for_package(st):
    return [r for r in st["results"] if r["holat"] == "hisob" and (r["paket"] is None or r.get("tuzatildi"))]


def build_package(st, day):
    new = pending_for_package(st)
    if not new:
        return None
    today = day.isoformat()
    by_today = day_counts(st, today)
    late = [r for r in new if r["sana"] < today and r["paket"] is None]
    late_note = ""
    if late:
        g = {}
        for r in late:
            g.setdefault(r["sana"], {}).setdefault(r["filial"], 0)
            g[r["sana"]][r["filial"]] += 1
        late_note = "⏱ Keçikkan qöşimça: " + "; ".join(
            f"{sana_txt(D(s))} hisobiga " + ", ".join(f"{f} +{n} ta" for f, n in fs.items()) for s, fs in sorted(g.items()))
    r1, order, ranks = rating_msg(st, day, by_today, late_note)
    r2 = counts_msg(by_today)
    # taşakkurnomalar tartibi: kunlik son kamayiş, teng bölsa oylik örin
    dcount = {}
    for r in new:
        dcount[r["filial"]] = dcount.get(r["filial"], 0) + 1
    allc = sorted(new, key=lambda r: (-dcount[r["filial"]], ranks.get(r["filial"], 9), r["posted"], r["id"]))
    certs = [r for r in allc if not held(r)]
    hold = [r for r in allc if held(r)]
    return {"rating": r1, "counts": r2, "certs": certs, "held": hold, "order": order, "ranks": ranks}


def render_cert(st, r):
    v = st.get("dizayn", "v3")
    if not os.path.exists(os.path.join(render2.TPL, f"{v}_{r['maktab']}.png")):
        v = "v3"
    return render2.render(v, r["maktab"], r["ism"], r["cert"], D(r["sana"]), r["filial"])


def send_package(st, day, tur="yakuniy", sinov=False):
    key = f"{day.isoformat()}|{tur}"
    pk = build_package(st, day)
    if pk is None:
        return False
    rec_parts, rec_new = [], None
    pref = "🧪 SINOV — haqiqiy hisobga qöşilmaydi\n\n" if sinov else ""
    if not sinov:
        # raqamlar va paket yozuvi yuborişdan OLDIN saqlanadi (takror yuborilmasin)
        used = {c["n"] for c in st["certs"]}
        for r in pk["certs"]:
            if r["cert"] is None:
                n = st["next"]
                while n in used:
                    n += 1
                r["cert"], st["next"] = n, n + 1
                used.add(n)
            r["paket"] = key
        for r in pk["held"]:
            r["paket"] = key
        st["packages"][key] = {"ts": now().isoformat(timespec="seconds"), "ids": [r["id"] for r in pk["certs"]],
                               "steps": []}
        st["order"], st["ranks"] = pk["order"], pk["ranks"]
        rec_parts, rec_new = record_posts(st, day)
        st["packages"][key]["rec"] = rec_parts
        save_state(st, f"paket {key}")
    steps = st["packages"].get(key, {"steps": []})["steps"] if not sinov else []
    if "rating" not in steps:
        say(st, pref + pk["rating"]); steps.append("rating")
    if "counts" not in steps:
        say(st, (pref + pk["counts"]) if sinov else pk["counts"]); steps.append("counts")
    for r in pk["certs"]:
        if not sinov and r["cert_sent"] and not r.get("tuzatildi"):
            continue
        n = r["cert"] if r["cert"] is not None else 0
        send_cert(st, r, n, key, sinov=sinov)
        time.sleep(0.5)
    if pk["held"] and "held" not in steps:
        say(st, (pref if sinov else "") + f"⏳ {len(pk['held'])} ta taşakkurnoma ism tasdiğini kutmoqda "
            f"({'RegMon guruhida' if st.get('regmon') else 'sizga'} savol yuborilgan). Qaror bölişi bilan şu yerga keladi:\n" +
            "\n".join(f"#{r['id']} {r['ism']} — {r['filial'] or '—'}" for r in pk["held"]))
        steps.append("held")
    if rec_parts and "records" not in steps:
        import html as _h
        body = "\n\n".join(rec_parts)
        body = _h.escape(body).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
        tg("sendMessage", chat_id=st["owner"], text=body[:4000], parse_mode="HTML"); steps.append("records")
    if not sinov:
        st["rec_snap"] = rec_new
        st["packages"][key]["steps"] = steps
        audit(st, "paket", f"{key}: {len(pk['certs'])} ta taşakkurnoma")
        save_state(st, f"paket {key} yuborildi")
    return True


def resend_certs(st):
    """Qayta işga tuşganda: paketga kirgan, lekin fayli yuborilmay qolgan taşakkurnomalar."""
    left = [r for r in st["results"] if r["holat"] == "hisob" and r.get("paket") and not r["cert_sent"] and r["cert"]
            and not held(r)]
    for r in left:
        send_cert(st, r, r["cert"], r["paket"])
    if left:
        save_state(st, "qolgan taşakkurnomalar")


def schedule_tick(st, t):
    """17:00/18:00 jadvali. Har bir paket bir marta."""
    today = t.date().isoformat()
    hm = (t.hour, t.minute)
    h, mi = map(int, st["vaqt"].split(":"))
    if hm >= (17, 45) and f"{today}|ismlar" not in st["packages"]:
        st["packages"][f"{today}|ismlar"] = {"ts": t.isoformat(), "ids": [], "steps": []}
        ism_report(st, t.date())
        st["ism_live"] = today
        did = True
    else:
        did = False
    if st.get("setup_day") == today:
        if hm >= (17, 0) and f"{today}|dastlabki" not in st["packages"] and hm < (h, mi):
            if send_package(st, t.date(), "dastlabki"):
                return True
            st["packages"][f"{today}|dastlabki"] = {"ts": t.isoformat(), "ids": [], "steps": ["boş"]}
            return True
    if hm >= (h, mi) and f"{today}|yakuniy" not in st["packages"]:
        if not send_package(st, t.date(), "yakuniy"):
            st["packages"][f"{today}|yakuniy"] = {"ts": t.isoformat(), "ids": [], "steps": ["boş"]}
        return True
    return did


# ================================================================ ismlar tekşiruvi (rasmiy röyxat)
def held(r):
    nc = r.get("nc")
    return bool(nc) and nc["holat"] in ("savol", "yoq") and not nc.get("qaror")


def cname(r):
    """Taşakkurnomadagi ism: tasdiqlangan rasmiy şakl (yangi alifboda)."""
    return r.get("ism_r") or names.yangi(r["ism"] or "")


def send_cert(st, r, n, key, sinov=False):
    try:
        ism = cname(r)
        img = render2.render(st.get("dizayn", "v3"), r["maktab"], ism, n, D(r["sana"]), r["filial"])
        cap = st["izoh"].format(ism=ism, filial=r["filial"], fan=r["fan"], raqam=f"{n:04d}", sana=sana_txt(D(r["sana"])))
        if r.get("tuzatildi") and r["cert_sent"]:
            cap = "✏️ TUZATILGAN TAŞAKKURNOMA\n" + cap
        if sinov:
            cap = "🧪 SINOV\n" + cap
        ok = tg("sendDocument", chat_id=st["owner"], caption=cap[:1024],
                files={"document": (f"Kun öqituvçisi {n}.jpg", img, "image/jpeg")})
        if ok is not None and not sinov:
            r["cert_sent"], r["tuzatildi"], r["cert_ism"] = True, False, ism
            st["certs"].append({"n": n, "id": r["id"], "ism": ism, "filial": r["filial"], "sana": r["sana"],
                                "paket": key, "ts": now().isoformat(timespec="seconds")})
        return ok is not None
    except Exception:
        traceback.print_exc()
        say(st, f"⚠️ #{r['id']} {r['ism']} taşakkurnomasini tayyorlab bölmadi — tekşiraman.")
        return False


def apply_check(st, r, force=False):
    """Ismni röyxat bilan solişhtiriş. Avvalgi qaror bölsa (force bölmasa) özgartirilmaydi."""
    old = r.get("nc") or {}
    if old.get("qaror") and not force:
        return
    nc = names.check(st, r["ism"], r["filial"], f"{r.get('fan', '')} {r.get('dars', '')}")
    nc.update(qaror=None, xabar=False, auto_xabar=False)
    r["nc"] = nc
    before = r.get("cert_ism")
    r["ism_r"] = nc["rasmiy"] if nc["holat"] in ("ok", "auto") else None
    if r["cert_sent"] and r["ism_r"] and before and r["ism_r"] != before:
        r["tuzatildi"] = True


def ism_target(st):
    return st.get("regmon") or st.get("owner")


def who(u):
    if not u:
        return "?"
    n = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x)
    return n + (f" (@{u['username']})" if u.get("username") else "")


def q_text(st, r):
    nc = r["nc"]
    belgi = "❓ ANIQLAŞTIRIŞ KERAK" if nc["holat"] == "savol" else "❗ RÖYXATDA YÖQ"
    L = [f"{belgi} · #{r['id']}",
         f"📍 {r['filial'] or 'filial yozilmagan'} · {r['fan'] or 'fan yozilmagan'}",
         f"📝 Postda: «{r['ism'] or '—'}»",
         f"📅 {sana_txt(D(r['sana']))}" + (f" · {r['link']}" if r.get("link") else ""),
         f"ℹ️ {nc['izoh']}"]
    if nc["nomzodlar"]:
        L += ["", "Öxşaşlari:"]
        L += [f"{i}) {c['disp']} — {c['filial']}, {c['fan']} ({c['ball']}%)" for i, c in enumerate(nc["nomzodlar"], 1)]
    if r["sana"] < now().date().isoformat():
        L += ["", f"⏳ {sana_txt(D(r['sana']))}dan beri qaror kutmoqda"]
    L += ["", "Tugmani bosing yoki şu xabarga «Javob berish» qilib yozing:",
          "raqam (1, 2…) · yangi · postdagi · kiritilmasin · yoki Familiya Ism; Filial; fan"]
    return "\n".join(L)


def q_keyboard(r):
    rows = [[{"text": f"{i}) {c['disp']}"[:60], "callback_data": f"n|{r['id']}|c{i}"}]
            for i, c in enumerate(r["nc"]["nomzodlar"], 1)]
    rows.append([{"text": "🆕 Yangi ustoz", "callback_data": f"n|{r['id']}|new"},
                 {"text": "📝 Postdagi ism", "callback_data": f"n|{r['id']}|post"}])
    rows.append([{"text": "❌ Kiritilmasin", "callback_data": f"n|{r['id']}|no"}])
    return {"inline_keyboard": rows}


def post_question(st, r):
    chat = ism_target(st)
    if not chat:
        return
    res = tg("sendMessage", chat_id=chat, text=q_text(st, r)[:4000], reply_markup=q_keyboard(r),
             disable_web_page_preview=True)
    if res:
        st["qmsg"][f"{chat}:{res['message_id']}"] = r["id"]
        r["nc"]["xabar"] = True


def auto_line(r):
    nc = r["nc"]
    s = f"#{r['id']} «{r['ism']}» → «{nc['rasmiy']}» ({r['filial']}"
    if nc["nomzodlar"]:
        s += f", {nc['nomzodlar'][0]['fan']}"
    s += ")"
    if nc.get("izoh"):
        s += f" — {nc['izoh']}"
    return s


def auto_keyboard(rs):
    rows, row = [], []
    for r in rs:
        row.append({"text": f"↩️ #{r['id']}", "callback_data": f"n|{r['id']}|undo"})
        if len(row) == 4:
            rows.append(row); row = []
    if row:
        rows.append(row)
    return {"inline_keyboard": rows}


def ism_report(st, day):
    """17:45: kunlik ismlar tekşiruvi. Ochiq savollar har kuni qayta çiqadi — hech kim qolib ketmaydi."""
    chat = ism_target(st)
    if not chat:
        return
    iso = day.isoformat()
    act = [r for r in st["results"] if r["holat"] in ("hisob", "tekshir") and r.get("nc")]
    today = [r for r in act if r["sana"] == iso]
    ok = [r for r in today if r["nc"]["holat"] == "ok" and not r["nc"].get("qaror")]
    auto = [r for r in today if r["nc"]["holat"] == "auto" and not r["nc"].get("qaror")]
    open_q = [r for r in act if held(r)]
    sav = [r for r in open_q if r["nc"]["holat"] == "savol"]
    yoq = [r for r in open_q if r["nc"]["holat"] == "yoq"]
    pre = "" if st.get("regmon") else "ℹ️ RegMon guruhi hali aniqlanmagan — şu sababli sizga yuborildi. Guruhda /regmon deb yozing.\n\n"
    if not auto and not open_q:
        tg("sendMessage", chat_id=chat, text=pre + f"📋 ISMLAR TEKŞIRUVI — {sana_txt(day)}\n\n✅ Barça ismlar röyxatga mos ({len(ok)} ta).")
        return
    tg("sendMessage", chat_id=chat, text=pre + f"📋 ISMLAR TEKŞIRUVI — {sana_txt(day)}\n\n"
       f"✅ Töğri yozilganlar: {len(ok)} ta\n✏️ Avtomatik töğrilanganlar: {len(auto)} ta\n"
       f"❓ Aniqlaştiriş kerak: {len(sav)} ta\n❗ Röyxatda yöq: {len(yoq)} ta" +
       ("\n\nQuyidagi har bir savolga javob bering. Qaror qilinmaguncha taşakkurnoma kutib turadi, savol har kuni 17:45 da qayta çiqadi."
        if open_q else ""))
    if auto:
        txt = "✏️ AVTOMATIK TÖĞRILANGANLAR (röyxat böyiça)\n\n" + "\n".join(auto_line(r) for r in auto) + \
              "\n\nNotöğri bölsa — ↩️ tugmasini bosing, savolga aylanadi."
        tg("sendMessage", chat_id=chat, text=txt[:4000], reply_markup=auto_keyboard(auto[:96]))
        for r in auto:
            r["nc"]["auto_xabar"] = True
    for r in sorted(open_q, key=lambda r: (r["sana"], r["id"])):
        post_question(st, r)
        time.sleep(0.3)
    audit(st, "ismlar", f"{iso}: ok {len(ok)}, auto {len(auto)}, savol {len(sav)}, yoq {len(yoq)}")


def live_ism(st, r):
    """17:45 dan keyin kelgan postlar — darhol."""
    if st.get("ism_live") != now().date().isoformat() or r["holat"] not in ("hisob", "tekshir"):
        return
    chat = ism_target(st)
    if not chat:
        return
    if held(r) and not r["nc"].get("xabar"):
        post_question(st, r)
    elif r["nc"]["holat"] == "auto" and not r["nc"].get("auto_xabar"):
        tg("sendMessage", chat_id=chat, text="✏️ AVTOMATIK TÖĞRILANDI\n\n" + auto_line(r),
           reply_markup=auto_keyboard([r]))
        r["nc"]["auto_xabar"] = True


def deliver_now(st, r):
    """Qarordan keyin: paket allaqaçon ketgan bölsa — taşakkurnoma darhol egasiga."""
    if r["holat"] != "hisob" or held(r) or not r.get("paket"):
        return
    if r["cert_sent"] and not r.get("tuzatildi"):
        return
    if r["cert"] is None:
        used = {c["n"] for c in st["certs"]}
        n = st["next"]
        while n in used:
            n += 1
        r["cert"], st["next"] = n, n + 1
        save_state(st, f"raqam #{r['id']}")
    send_cert(st, r, r["cert"], r["paket"])


def resolve(st, r, action, arg, user):
    """Savolga qaror. -> (natija matni) yoki None (tuşunilmadi)."""
    nc = r["nc"]
    kim = who(user)
    if action == "undo":
        if nc["holat"] != "auto" or nc.get("qaror"):
            return "Bu yozuv allaqaçon özgartirilgan."
        nc.update(holat="savol", izoh=f"avtomatik tuzatiş bekor qilindi ({kim}); avval: «{nc['rasmiy']}»", rasmiy=None,
                  xabar=False)
        r["ism_r"] = None
        audit(st, "ism-undo", f"#{r['id']} {kim}")
        post_question(st, r)
        return f"↩️ #{r['id']} savolga aylantirildi."
    if nc.get("qaror"):
        return f"Bu savolga allaqaçon javob berilgan: {nc['qaror']['matn']}"
    if action.startswith("c"):
        i = int(action[1:]) - 1
        if not 0 <= i < len(nc["nomzodlar"]):
            return None
        c = nc["nomzodlar"][i]
        r["ism_r"] = c["disp"]
        st["aliases"][names.alias_key(r["ism"] or "", r["filial"])] = {"ism": c["ism"], "filial": c["filial"], "disp": c["disp"]}
        if not r["filial"]:
            fil = find_filial(c["filial"])
            r["filial"], r["maktab"] = fil
            st["aliases"][names.alias_key(r["ism"] or "", r["filial"])] = {"ism": c["ism"], "filial": c["filial"], "disp": c["disp"]}
        matn = f"{i + 1}-nomzod: «{c['disp']}» ({c['filial']}, {c['fan']})"
    elif action == "new":
        if not r["ism"] or not r["filial"]:
            return "Yangi ustoz qöşiş uçun ism va filial kerak — «Familiya Ism; Filial; fan» deb yozing."
        fans = names.fan_set(r.get("fan", ""))
        st["roster_add"].append({"ism": r["ism"], "filial": r["filial"], "fan": next(iter(fans), r.get("fan") or "—"),
                                 "tur": "asosiy", "qoshildi": now().date().isoformat(), "kim": kim})
        r["ism_r"] = names.display(r["ism"])
        matn = f"yangi ustoz — «{r['ism_r']}» röyxatga qöşildi ({r['filial']})"
    elif action == "post":
        if not r["ism"]:
            return None
        r["ism_r"] = names.display(r["ism"])
        matn = f"postdagi ism bilan — «{r['ism_r']}» (röyxatga qöşilmadi)"
    elif action == "no":
        r["holat"], r["sabab"] = "bekor", f"RegMon qarori: kiritilmasin ({kim})"
        r["ism_r"] = None
        matn = "kiritilmasin — natija hisobdan çiqarildi, taşakkurnoma berilmaydi"
    elif action == "text":
        parts = [x.strip() for x in arg.split(";")]
        ism, _ = split_name(" ".join(w[:1].upper() + w[1:] for w in parts[0].split()))
        if not ism:
            return None
        fil = find_filial(parts[1]) if len(parts) > 1 and parts[1] else None
        if len(parts) > 1 and parts[1] and not fil:
            return None
        if fil:
            r["filial"], r["maktab"] = fil
        if len(parts) > 2 and parts[2]:
            r["fan"] = parts[2]
        chk = names.check(st, ism, r["filial"], r.get("fan", ""))
        if chk["holat"] not in ("ok", "auto") and len(parts) < 2:
            return None                       # erkin gap ism deb taxmin qilinmaydi
        if chk["holat"] == "ok" or (chk["holat"] == "auto" and len(parts) < 2):
            r["ism_r"] = chk["rasmiy"]
            e = chk["nomzodlar"][0] if chk["nomzodlar"] else None
            if e:
                st["aliases"][names.alias_key(r["ism"] or "", r["filial"])] = {"ism": e["ism"], "filial": e["filial"], "disp": chk["rasmiy"]}
            matn = f"«{chk['rasmiy']}» (röyxat böyiça) — {r['filial']}"
        else:
            r["ism_r"] = names.display(ism)
            matn = f"yozilgan ism bilan — «{r['ism_r']}» ({r['filial'] or '—'}; röyxatda yöq)"
    else:
        return None
    if r["holat"] == "tekshir" and r["ism"] and r["filial"] and r.get("sabab", "").startswith("filial topilmadi") \
            and "natija" not in r["sabab"]:
        r["holat"], r["sabab"] = "hisob", "filial RegMon qarori bilan aniqlandi"
        recheck_cap(st, r)
    nc["qaror"] = {"matn": matn, "kim": kim, "ts": now().isoformat(timespec="seconds"), "action": action}
    audit(st, "ism-qaror", f"#{r['id']} {r['ism']}: {matn} — {kim}")
    if r["cert_sent"] and r.get("ism_r") and r["ism_r"] != r.get("cert_ism"):
        r["tuzatildi"] = True
    deliver_now(st, r)
    return f"✅ #{r['id']}: {matn}"


ANS = [("kiritilmasin", "no"), ("kiritma", "no"), ("bekor", "no"), ("yangi", "new"), ("postdagi", "post"),
       ("postdagidek", "post"), ("shundayligicha", "post")]


def parse_answer(text):
    t = (text or "").strip()
    low = _norm(t).strip(" .!")
    if re.fullmatch(r"\d", low):
        return f"c{low}", ""
    for k, a in ANS:
        if low.startswith(_norm(k)):
            return a, ""
    return "text", t


def finish_q(st, chat, mid, r, res):
    """Savol xabarini yopiş: qaror yoziladi, tugmalar olinadi."""
    tg("editMessageText", chat_id=chat, message_id=mid, text=(q_text(st, r) + f"\n\n{res}\n👤 {r['nc']['qaror']['kim']}")[:4000],
       disable_web_page_preview=True)


def handle_callback(st, cq):
    data = cq.get("data") or ""
    msg = cq.get("message") or {}
    chat = msg.get("chat", {}).get("id")
    if not data.startswith("n|") or chat not in (st.get("regmon"), st.get("owner")):
        tg("answerCallbackQuery", callback_query_id=cq["id"], text="Bu tugma bu yerda ishlamaydi.")
        return False
    _, rid, action = data.split("|")
    r = next((x for x in st["results"] if x["id"] == int(rid)), None)
    if not r:
        tg("answerCallbackQuery", callback_query_id=cq["id"], text="Yozuv topilmadi.")
        return False
    res = resolve(st, r, action, "", cq.get("from"))
    tg("answerCallbackQuery", callback_query_id=cq["id"], text=(res or "Tuşunmadim")[:190])
    if res and action != "undo" and r["nc"].get("qaror"):
        finish_q(st, chat, msg["message_id"], r, res)
    return True


def handle_answer_msg(st, m):
    """RegMon (yoki egasi) savol xabariga reply qilib yozdi."""
    chat = m["chat"]["id"]
    rep = m.get("reply_to_message") or {}
    rid = st["qmsg"].get(f"{chat}:{rep.get('message_id')}")
    if not rid:
        return False
    r = next((x for x in st["results"] if x["id"] == rid), None)
    if not r:
        return False
    action, arg = parse_answer(m.get("text") or "")
    res = resolve(st, r, action, arg, m.get("from"))
    if res is None:
        tg("sendMessage", chat_id=chat, reply_to_message_id=m["message_id"],
           text="🤔 Tuşunmadim — savol oçiq qoldi. Yozing: raqam (1, 2…), «yangi», «postdagi», «kiritilmasin» "
                "yoki «Familiya Ism; Filial; fan».")
        return False
    tg("sendMessage", chat_id=chat, reply_to_message_id=m["message_id"], text=res)
    if r["nc"].get("qaror"):
        finish_q(st, chat, rep["message_id"], r, res)
    return True


def note_chat(st, chat, frm=None, text=""):
    """Guruhlarni qayd etiş; RegMon guruhini aniqlaş."""
    cid, title = chat["id"], chat.get("title") or ""
    st["chats"][str(cid)] = title
    if cid == st.get("group"):
        return
    t = _norm(title).replace(" ", "")
    if st.get("regmon") is None and ("regmon" in t or ("registon" in t and "monitoring" in t)):
        st["regmon"] = cid
        audit(st, "regmon", f"guruh aniqlandi: {title} ({cid})")
        say(st, f"✅ RegMon guruhi aniqlandi: «{title}». Ismlar tekşiruvi har kuni 17:45 da şu guruhga yuboriladi.")
    if (text or "").split("@")[0].strip().lower() == "/regmon" and frm and frm.get("id") == st.get("owner"):
        st["regmon"] = cid
        audit(st, "regmon", f"egasi belgiladi: {title} ({cid})")
        tg("sendMessage", chat_id=cid, text="✅ Bu guruh ismlar tekşiruvi uçun belgilandi. Har kuni 17:45 da savollar şu yerga keladi.")
        say(st, f"✅ RegMon guruhi belgilandi: «{title}».")


def handle_roster_doc(st, m):
    """Egasi yangi röyxat faylini (.txt) yubordi."""
    d = m["document"]
    f = tg("getFile", file_id=d["file_id"])
    if not f or not TOKEN:
        return False
    raw = requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{f['file_path']}", timeout=60).content
    try:
        new = names.parse_roster_text(raw.decode("utf-8"))
    except Exception:
        new = []
    if len(new) < 50:
        say(st, "Faylda röyxat topilmadi (kamida 50 ta ustoz bölişi kerak). Shakl: «=== FILIAL ===» va «- Fan: Ism; Ism».")
        return False
    old = {(names.display(e["ism"]), e["filial"]) for e in (st.get("roster") or names.base_roster())}
    nw = {(names.display(e["ism"]), e["filial"]) for e in new}
    add, rem = sorted(nw - old), sorted(old - nw)
    st["roster"] = new
    audit(st, "royxat", f"yangi röyxat: {len(new)} ta (+{len(add)}, -{len(rem)})")
    say(st, f"✅ Yangi röyxat qabul qilindi: {len(new)} ta ustoz.\n\n➕ Qöşilgan ({len(add)}):\n" +
        "\n".join(f"{a} — {b}" for a, b in add[:60]) + f"\n\n➖ Çiqarilgan ({len(rem)}):\n" +
        "\n".join(f"{a} — {b}" for a, b in rem[:60]))
    return True


# ================================================================ egasi buyruqlari
HELP = """Boşqaruv buyruqlari (faqat siz uçun):
/bugun — bugungi hisob
/reyting — oylik reyting
/rekordlar — rekordlar holati
/top10 — tarixiy oylik Top-10
/top5 — kunlik Top-5 röyxatlar
/kutilmoqda — tekşiriş kutilayotganlar
/tasdiq ID — natijani tasdiqlaş
/bekor ID sabab — natijani bekor qiliş
/tuzat ID Familiya Ism; Filial; fan — tuzatiş
/yangi Familiya Ism; Filial; fan — qölda natija qöşiş
/xodim Filial son sabab — öqituvçilar sonini yangilaş
/oldindan — paketni oldindan köriş
/yubor — paketni hozir yuboriş
/vaqt 18:00 · /raqam 160 · /holat

Ismlar tekşiruvi (rasmiy röyxat):
/ismlar — oçiq savollar (qayta yuboriladi)
/royxat [Filial] — röyxat holati
/ustoz_qosh Familiya Ism; Filial; fan — röyxatga qöşiş
/regmon — RegMon guruhi holati (guruhda /regmon deb yozsangiz, şu guruh belgilanadi)
Yangi röyxat: .txt faylini şu çatga yuboring."""


def find_r(st, arg):
    m = re.match(r"#?(\d+)", arg or "")
    return next((r for r in st["results"] if m and r["id"] == int(m.group(1))), None)


def handle_private(st, m):
    chat = m["chat"]["id"]
    text = (m.get("text") or "").strip()
    if st["owner"] is None and text.startswith("/start"):
        st["owner"] = chat
        say(st, HELP)
        return True
    if chat != st["owner"]:
        tg("sendMessage", chat_id=chat, text="Bu bot faqat Monitoring bölimi rahbari uçun.")
        return False
    if m.get("document") and (m["document"].get("file_name", "").lower().endswith(".txt")):
        return handle_roster_doc(st, m)
    if m.get("reply_to_message") and handle_answer_msg(st, m):
        return True
    if not text.startswith("/"):
        say(st, "Buyruqlar röyxati: /help")
        return False
    cmd, _, arg = text.partition(" ")
    cmd, arg = cmd.split("@")[0].lower(), arg.strip()
    t = now()
    month = t.date().isoformat()[:7]
    if cmd in ("/start", "/help"):
        say(st, HELP)
    elif cmd == "/bugun":
        rs = [r for r in st["results"] if r["sana"] == t.date().isoformat()]
        L = [f"📅 {sana_txt(t.date())} — hisobga olingan: {len([r for r in rs if r['holat'] == 'hisob'])} ta", ""]
        L += [f"#{r['id']} {'✅' if r['holat'] == 'hisob' else '⏳' if r['holat'] == 'tekshir' else '❌'} {r['ism']} — {r['filial']}"
              for r in rs]
        L += ["", counts_msg(day_counts(st, t.date().isoformat()))]
        say(st, "\n".join(L))
    elif cmd == "/reyting":
        say(st, rating_msg(st, t.date(), day_counts(st, t.date().isoformat()))[0])
    elif cmd == "/kutilmoqda":
        rs = [r for r in st["results"] if r["holat"] == "tekshir"]
        say(st, "\n\n".join(f"#{r['id']} {r['ism'] or '—'} · {r['filial'] or '—'} · {r['sana']}\n{r['sabab']}\n{r['link']}"
                            for r in rs) or "Tekşiriş kutilayotgan natija yöq.")
    elif cmd in ("/tasdiq", "/bekor", "/tuzat"):
        r = find_r(st, arg)
        if not r:
            say(st, "ID topilmadi. /kutilmoqda röyxatidan oling.")
            return False
        if cmd == "/tasdiq":
            if not (r["ism"] and r["filial"]):
                say(st, f"#{r['id']}: ism yoki filial yöq — avval /tuzat {r['id']} Familiya Ism; Filial; fan")
                return False
            r["holat"], r["sabab"] = "hisob", "egasi tasdiqladi"
            audit(st, "tasdiq", f"#{r['id']} {r['ism']}")
            say(st, f"✅ #{r['id']} {r['ism']} hisobga olindi. Keyingi paketda yuboriladi.")
        elif cmd == "/bekor":
            sab = arg.split(" ", 1)[1] if " " in arg else "egasi bekor qildi"
            r["holat"], r["sabab"] = "bekor", sab
            audit(st, "bekor", f"#{r['id']} {r['ism']}: {sab}")
            say(st, f"❌ #{r['id']} {r['ism']} bekor qilindi. Hisoblar qayta hisoblandi.")
        else:
            body = arg.split(" ", 1)[1] if " " in arg else ""
            parts = [x.strip() for x in body.split(";")]
            ism, _ = split_name(parts[0] if parts else "")
            fil = find_filial(parts[1]) if len(parts) > 1 else None
            if not ism:
                say(st, f"Yozilişi: /tuzat {r['id']} Familiya Ism; Filial; fan")
                return False
            before = (r["ism"], r["filial"])
            r["ism"], r["ism_n"] = ism, name_key(ism)
            if fil:
                r["filial"], r["maktab"] = fil
            if len(parts) > 2 and parts[2]:
                r["fan"] = parts[2]
            apply_check(st, r, force=True)
            if held(r):
                r["ism_r"] = names.display(ism)
                r["nc"]["qaror"] = {"matn": f"egasi /tuzat bilan: «{r['ism_r']}»", "kim": "egasi",
                                    "ts": t.isoformat(timespec="seconds"), "action": "tuzat"}
            if r["cert_sent"] and r["ism_r"] != r.get("cert_ism"):
                r["tuzatildi"] = True
            if r["cert_sent"]:
                r["tuzatildi"] = True
            audit(st, "tuzatiş", f"#{r['id']}: {before} -> {(r['ism'], r['filial'])}")
            say(st, f"✏️ #{r['id']} tuzatildi: {r['ism']} — {r['filial']}." + (" Tuzatilgan taşakkurnoma keyingi paketda keladi." if r["cert_sent"] else ""))
        return True
    elif cmd == "/yangi":
        parts = [x.strip() for x in arg.split(";")]
        ism, _ = split_name(parts[0] if parts else "")
        fil = find_filial(parts[1]) if len(parts) > 1 else None
        if not ism or not fil:
            say(st, "Yozilişi: /yangi Karimov Anvar; Çilonzor; matematika fani öqituvçisi")
            return False
        st["rid"] += 1
        r = {"id": st["rid"], "chat": chat, "mid": -st["rid"], "link": "", "media": None,
             "posted": t.isoformat(timespec="seconds"), "sana": t.date().isoformat(), "ism": ism, "ism_n": name_key(ism),
             "filial": fil[0], "maktab": fil[1], "fan": parts[2] if len(parts) > 2 else "", "dars": "", "natija": "qölda",
             "matn": "qölda", "holat": "hisob", "sabab": "egasi qölda qöşdi", "forward": False, "paket": None,
             "cert": None, "cert_sent": False, "tuzatildi": False}
        recheck_cap(st, r)
        st["results"].append(r)
        apply_check(st, r)
        if held(r):
            r["ism_r"] = names.display(ism)
            r["nc"]["qaror"] = {"matn": "egasi qölda kiritdi", "kim": "egasi", "ts": t.isoformat(timespec="seconds"),
                                "action": "qolda"}
        audit(st, "qölda", f"#{r['id']} {ism} {fil[0]}")
        say(st, f"✅ #{r['id']} {ism} — {fil[0]} ({r['holat']})")
        return True
    elif cmd == "/xodim":
        mm = re.match(r"^(\S+)\s+(\d+)\s*(.*)$", arg)
        fil = find_filial(mm.group(1)) if mm else None
        if not fil:
            say(st, "\n".join(f"{f}: {n}" for f, n in xodimlar(st, month).items()) +
                f"\nJami: {sum(xodimlar(st, month).values())}\n\nYangilaş: /xodim Çilonzor 55 sabab")
            return False
        counts = dict(xodimlar(st, month))
        counts[fil[0]] = int(mm.group(2))
        st["xodim_v"].append({"from": f"{month}-01", "counts": counts, "sabab": mm.group(3) or "egasi tuzatişi",
                              "kiritildi": t.date().isoformat()})
        audit(st, "xodim", f"{fil[0]} = {mm.group(2)} ({mm.group(3)})")
        say(st, f"✅ {fil[0]}: {mm.group(2)} nafar ({month} oyi uçun). Bu qayta hisoblaş — yangi mehnat natijasi emas.")
        return True
    elif cmd == "/oldindan":
        pk = build_package(st, t.date())
        if not pk:
            say(st, "Yuboriladigan yangi natija yöq.")
        else:
            say(st, "👁 OLDINDAN KÖRIŞ (yuborilmagan)\n\n" + pk["rating"])
            say(st, pk["counts"])
            say(st, "Taşakkurnomalar tartibi:\n" + "\n".join(f"{r['filial']} — {r['ism']}" for r in pk["certs"]))
    elif cmd == "/yubor":
        if not send_package(st, t.date(), f"qölda-{t.strftime('%H%M%S')}"):
            say(st, "Yuboriladigan yangi natija yöq.")
        return True
    elif cmd in ("/rekordlar", "/top10", "/top5"):
        rs = records_state(st, t.date())
        if cmd == "/top10":
            say(st, "📈 TARIXIY OYLIK TOP-10\n\n" + "\n".join(
                f"{i}. {f} — {str(p).replace('.', ',')}% — {ym_txt(ym, y)}{' (joriy, oy yakunlanmagan)' if c else ''}"
                for i, (f, p, ym, y, c) in enumerate(rs["top10"], 1)))
        elif cmd == "/top5":
            say(st, "UMUMIY KUNLIK TOP-5:\n" + "\n".join(f"{i}. {sana_txt(D(k), True)} — {v} ta" for i, (k, v) in enumerate(rs["top_sys"], 1))
                + "\n\nBIR FILIAL KUNLIK TOP-5:\n" + "\n".join(f"{f} — {n} ta — {sana_txt(D(s), True)}" for f, n, s in rs["top_br"])
                + "\n\n(mavjud tasdiqlangan arxiv böyiça)")
        else:
            order, ranks, frac, cnt, xod = ranking(st, month)
            sysp = Fraction(sum(cnt.values()), sum(xod.values()))
            L = ["🏅 REKORDLAR (mavjud tasdiqlangan arxiv böyiça)", "",
                 "Tarixiy mutlaq oylik rekord: Farğona — 92,5% (may, 2025–2026)",
                 "Joriy öquv yili oylik rekordi: Çilonzor — 88,6% (oktabr, 2026–2027)", "",
                 "Filiallarning şaxsiy rekordlari:"]
            for f in FILIALLAR:
                b = rs["best"].get(f)
                known = any(h[0] == f for h in st["monthly_hist"])
                L.append(f"• {f}: {str(b[1]).replace('.', ',')}% — {ym_txt(b[2], b[3])}" +
                         ("" if known else " (faqat joriy oy maʼlum — tarixiy arxiv yöq)"))
            L += ["", f"Butun tizim joriy oylik foizi: {pct1(sysp)}% ({sum(cnt.values())} / {sum(xod.values())})",
                  f"Kunlik eng yuqori (tizim): {rs['top_sys'][0][1]} ta — {sana_txt(D(rs['top_sys'][0][0]), True)}",
                  f"Bir filial kunlik eng yuqori: {rs['top_br'][0][0]} — {rs['top_br'][0][1]} ta — {sana_txt(D(rs['top_br'][0][2]), True)}",
                  "", "Tekşirilmagan (töliq arxiv yöq): haftalik va oylik natijalar soni rekordlari, oldingi oy / ötgan yilga nisbatan ösiş, "
                  "oylik ğoliblik va ketma-ket ğoliblik, ketma-ket natijali nazorat kunlari, 50% ga eng tez erişiş (nazorat taqvimi kerak), "
                  "tizimning tarixiy oylik soni va foizi."]
            say(st, "\n".join(L))
    elif cmd == "/ismlar":
        rs = [r for r in st["results"] if r["holat"] in ("hisob", "tekshir") and held(r)]
        if not rs:
            say(st, "✅ Oçiq ism savollari yöq.")
        else:
            say(st, f"Oçiq ism savollari: {len(rs)} ta — {'RegMon guruhiga' if st.get('regmon') else 'şu yerga'} qayta yuborildi.")
            for r in rs:
                post_question(st, r)
        return True
    elif cmd == "/royxat":
        R = names.roster(st)
        fil = find_filial(arg) if arg else None
        if fil:
            by = {}
            for e in R:
                if e["filial"] == fil[0]:
                    by.setdefault(e["fan"], []).append(names.display(e["ism"]))
            say(st, f"📚 {fil[0]} — {sum(len(v) for v in by.values())} ta ustoz\n\n" +
                "\n\n".join(f"{k}: " + "; ".join(v) for k, v in sorted(by.items())))
        else:
            cnt = {}
            for e in R:
                cnt[e["filial"]] = cnt.get(e["filial"], 0) + 1
            say(st, "📚 Rasmiy röyxat (" + ("yangilangan fayl" if st.get("roster") else "portal, 13.11.2026") + f"): {len(R)} ta ustoz\n" +
                "\n".join(f"{f}: {cnt.get(f, 0)}" for f in FILIALLAR) +
                f"\n\nQaror bilan qöşilganlar: {len(st['roster_add'])} ta · Eslab qolingan tuzatişlar: {len(st['aliases'])} ta"
                "\n\nFilial böyiça: /royxat Çilonzor")
    elif cmd == "/ustoz_qosh":
        parts = [x.strip() for x in arg.split(";")]
        ism, _ = split_name(" ".join(w[:1].upper() + w[1:] for w in parts[0].split()) if parts and parts[0] else "")
        fil = find_filial(parts[1]) if len(parts) > 1 else None
        if not ism or not fil:
            say(st, "Yozilişi: /ustoz_qosh Karimova Dilnoza; Çilonzor; ingliz tili")
            return False
        fans = names.fan_set(parts[2] if len(parts) > 2 else "")
        st["roster_add"].append({"ism": ism, "filial": fil[0], "fan": next(iter(fans), parts[2] if len(parts) > 2 else "—"),
                                 "tur": "asosiy", "qoshildi": t.date().isoformat(), "kim": "egasi"})
        audit(st, "royxat+", f"{ism} {fil[0]}")
        say(st, f"✅ Röyxatga qöşildi: {names.display(ism)} — {fil[0]}")
        return True
    elif cmd == "/regmon":
        rg = st.get("regmon")
        say(st, (f"RegMon guruhi: «{st['chats'].get(str(rg), rg)}»" if rg else "RegMon guruhi hali aniqlanmagan.") +
            "\nBelgilaş: RegMon guruhida /regmon deb yozing.")
    elif cmd == "/vaqt":
        if re.match(r"^\d{1,2}:\d{2}$", arg):
            st["vaqt"] = arg.zfill(5)
            say(st, f"✅ Yakuniy paket vaqti: {st['vaqt']}")
            return True
        say(st, f"Hozir: {st['vaqt']}")
    elif cmd == "/raqam":
        if arg.isdigit():
            st["next"] = int(arg)
            say(st, f"✅ Keyingi taşakkurnoma raqami: {st['next']}")
            return True
        say(st, f"Keyingi raqam: {st['next']}")
    elif cmd == "/holat":
        say(st, f"Paket vaqti: {st['vaqt']}" + (f" (bugun 17:00 dastlabki + {st['vaqt']} qayta tekşiriş)" if st.get("setup_day") == t.date().isoformat() else "") +
            f"\nKeyingi raqam: {st['next']}\nJami yozuvlar: {len(st['results'])}\n"
            f"Kutilmoqda: {len([r for r in st['results'] if r['holat'] == 'tekshir'])}")
    else:
        say(st, "Buyruqni tuşunmadim. /help")
    return False


# ================================================================ asosiy sikl
def main():
    st = load_state()
    tg("deleteWebhook")
    tg("setMyCommands", commands=[{"command": c, "description": d} for c, d in [
        ("bugun", "Bugungi hisob"), ("reyting", "Oylik reyting"), ("rekordlar", "Rekordlar"),
        ("top10", "Tarixiy Top-10"), ("top5", "Kunlik Top-5"), ("kutilmoqda", "Tekşiriş kutilayotganlar"),
        ("tasdiq", "Natijani tasdiqlaş"), ("bekor", "Natijani bekor qiliş"), ("tuzat", "Natijani tuzatiş"),
        ("xodim", "Öqituvçilar soni"), ("oldindan", "Paketni oldindan köriş"), ("yubor", "Paketni yuboriş"),
        ("holat", "Holat"), ("ismlar", "Oçiq ism savollari"), ("royxat", "Rasmiy röyxat"),
        ("ustoz_qosh", "Röyxatga ustoz qöşiş"), ("regmon", "RegMon guruhi")]])
    print("bot ishga tushdi", flush=True)
    resend_certs(st)
    start = time.time()
    while not RUN_SECONDS or time.time() - start < RUN_SECONDS:
        ups = tg("getUpdates", offset=st["offset"], timeout=50,
                 allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post", "my_chat_member",
                                  "callback_query"])
        changed = False
        for u in ups or []:
            st["offset"] = u["update_id"] + 1
            try:
                m = u.get("message") or u.get("channel_post")
                em = u.get("edited_message") or u.get("edited_channel_post")
                if u.get("callback_query"):
                    changed |= bool(handle_callback(st, u["callback_query"]))
                elif u.get("my_chat_member"):
                    note_chat(st, u["my_chat_member"]["chat"])
                    changed = True
                elif m:
                    if m["chat"]["type"] == "private":
                        changed |= bool(handle_private(st, m))
                    else:
                        if st.get("group") is None and "kun" in _norm(m["chat"].get("title", "")):
                            st["group"] = m["chat"]["id"]
                        if m["chat"]["id"] == st.get("group"):
                            changed |= bool(ingest(st, m))
                        else:                         # RegMon va boşqa guruhlar — manba emas
                            note_chat(st, m["chat"], m.get("from"), m.get("text") or "")
                            if m["chat"]["id"] == st.get("regmon") and m.get("reply_to_message"):
                                handle_answer_msg(st, m)
                            changed = True
                elif em and em["chat"]["type"] != "private" and em["chat"]["id"] == st.get("group"):
                    changed |= bool(ingest(st, em, edited=True))
            except Exception:
                traceback.print_exc()
        try:
            changed |= schedule_tick(st, now())
        except Exception:
            traceback.print_exc()
        if ups or changed:
            save_state(st, "holat")
        if ups is None:
            time.sleep(5)


if __name__ == "__main__":
    main()
