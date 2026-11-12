"""@kun_oqituvchisi_bot — «Kun o'qituvchisi» tashakkurnomalarini avtomatik tayyorlaydi.

Guruhga tushgan har bir xabar = bitta ustoz. Bot xabardan ism va filialni ajratadi,
Registon yoki Turkiston shablonida tashakkurnoma (JPG) chizadi, ketma-ket raqamlaydi
va egasiga (Yosinxon aka) belgilangan izoh bilan yuboradi.
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
from zoneinfo import ZoneInfo

import requests

try:
    import render  # eski (Canva) shablon — ixtiyoriy
except Exception:
    render = None
import render2

TOKEN = os.environ["BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"
TZ = ZoneInfo("Asia/Tashkent")
STATE_FILE = os.environ.get("STATE_FILE", "state.enc")
STATE_KEY = os.environ.get("STATE_KEY")  # bo'lsa — holat shifrlanadi
RUN_SECONDS = int(os.environ.get("RUN_SECONDS", "0"))  # 0 = cheksiz
GIT_SYNC = os.environ.get("GIT_SYNC") == "1"

DEFAULT_IZOH = ("🏅 «Kun o'qituvchisi» tashakkurnomasi\n"
                "👤 {ism}\n📚 {fan}\n🏫 {filial}\n📄 № {raqam} · {sana}")

FILIALLAR = {  # normallashgan kalit so'z -> (ko'rinadigan nom, maktab); Turkiston birinchi tekshiriladi
    "sergeli": ("Sergeli Turkiston", "turkiston"),
    "turkiston": ("Sergeli Turkiston", "turkiston"),
    "turkistan": ("Sergeli Turkiston", "turkiston"),
    "tinclik": ("Tinchlik", "registon"),
    "fargona": ("Farg'ona", "registon"),
    "yunusobod": ("Yunusobod", "registon"),
    "cilonzor": ("Chilonzor", "registon"),
    "samarqand": ("Samarqand", "registon"),
    "buxoro": ("Buxoro", "registon"),
}


def _norm(t):
    t = t.lower()
    for a, b in (("ʻ", ""), ("‘", ""), ("’", ""), ("'", ""), ("`", ""), ("ch", "c"), ("sh", "s"),
                 ("ç", "c"), ("ş", "s"), ("ğ", "g"), ("ö", "o")):
        t = t.replace(a, b)
    return t


# ---------------------------------------------------------------- holat
def _fernet():
    from cryptography.fernet import Fernet
    return Fernet(STATE_KEY.encode())


def load_state():
    st = {"offset": 0, "owner": None, "next": 152, "izoh": DEFAULT_IZOH, "dizayn": "eski",
          "seen": {}, "log": [], "pending": {}}
    if os.path.exists(STATE_FILE):
        raw = open(STATE_FILE, "rb").read()
        if STATE_KEY:
            raw = _fernet().decrypt(raw)
        st.update(json.loads(raw))
    return st


def save_state(st, msg="holat"):
    # faqat oxirgi 14 kunlik takror-tekshiruvni saqlaymiz
    cutoff = (dt.datetime.now(TZ).date() - dt.timedelta(days=14)).isoformat()
    st["seen"] = {k: v for k, v in st["seen"].items() if v >= cutoff}
    raw = json.dumps(st, ensure_ascii=False).encode()
    if STATE_KEY:
        raw = _fernet().encrypt(raw)
    open(STATE_FILE, "wb").write(raw)
    if GIT_SYNC:
        subprocess.run(["git", "add", STATE_FILE], check=False)
        r = subprocess.run(["git", "commit", "-q", "-m", msg], capture_output=True)
        if r.returncode == 0:
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
            print("TG xato", method, j, file=sys.stderr)
            return None
        except requests.RequestException as e:
            print("tarmoq", e, file=sys.stderr)
            time.sleep(3 + attempt * 3)
    return None


def say(chat, text, **kw):
    return tg("sendMessage", chat_id=chat, text=text, **kw)


# ---------------------------------------------------------------- tahlil
SEP = re.compile(r"\s*(?:[·•|;\n/]|\s[-–—]\s|,)\s*")
WORD = r"[A-ZА-ЯÖĞŞÇO'ʻ‘’`][\w'ʻ‘’`\-]+"
NAME_RE = re.compile(rf"^{WORD}(?:\s+{WORD}){{1,3}}$")


def find_filial(text):
    low = _norm(text)
    for key, val in FILIALLAR.items():
        if key in low:
            return val
    return None


def _is_filial_token(tok):
    return find_filial(tok) is not None and len(tok.split()) <= 3


def clean_name(s):
    s = re.sub(r"\s+", " ", s.strip(" .:-–—«»\"'"))
    if s.isupper():
        s = " ".join(w[:1].upper() + w[1:].lower() for w in s.split())
    return s


FIELD = re.compile(r"^\W*(sana|filial|ustoz|fan|natija)\W*\s*[:\-–]\s*(.+)$", re.I | re.M)


def parse_fields(text):
    """«Sana: ... / Filial: ... / Ustoz: Ism Familiya fan ...» formatini o'qiydi."""
    f = {k.lower(): v.strip() for k, v in FIELD.findall(text or "")}
    if "ustoz" not in f:
        return None
    words = f["ustoz"].split()
    name = []
    for w in words:
        if re.match(WORD, w) and not _stop(w) and len(name) < 3:
            name.append(w.strip(".,;"))
        else:
            break
    if len(name) < 2:
        return None
    rest = " ".join(words[len(name):]).strip(" ,.-–")
    day = None
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", f.get("sana", ""))
    if m:
        try:
            day = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return {"ism": clean_name(" ".join(name)), "fil": find_filial(f.get("filial", "")) or find_filial(text),
            "sana": day, "fan": rest}


def parse(text):
    """-> (ism | None, (filial, maktab) | None)"""
    text = (text or "").strip()
    if not text:
        return None, None
    pf = parse_fields(text)
    if pf:
        return pf["ism"], pf["fil"]
    fil = find_filial(text)
    toks = [t for t in SEP.split(text) if t and t.strip()]
    name = None
    for t in toks:
        t2 = clean_name(re.sub(r"^(f\.?i\.?sh\.?|ustoz|o'qituvchi)\s*[:\-]\s*", "", t, flags=re.I))
        if re.search(r"\d", t2) or _is_filial_token(t2):
            continue
        if NAME_RE.match(t2) and not _stop(t2):
            name = t2
            break
    if not name:  # ajratgichsiz: "Karimov Anvar Chilonzor"
        words = [w for w in re.split(r"\s+", text) if w and not re.search(r"\d", w)
                 and not find_filial(w)]
        caps = [w.strip(".,:;") for w in words if re.match(WORD, w) and not _stop(w)]
        if 2 <= len(caps) <= 4:
            name = clean_name(" ".join(caps))
    return name, fil


STOP = {"texnologiya", "robototexnika", "shaxmat", "rasm", "kamondan", "gimnastika", "futbol",
        "taekvondo", "ot", "sporti", "bugun", "kun", "ustozi", "ustoz", "video", "dars", "darsi",
        "filial", "filiali", "maktab", "registon", "school", "o'qituvchisi", "mashg'ulot",
        "matematika", "ingliz", "tili", "rus", "arab", "tarbiya", "boshlang'ich", "musiqa", "raqs"}


def _stop(name):
    return any(w.lower().strip(".,") in STOP for w in name.split())


def norm_key(name, day):
    n = re.sub(r"[^a-zа-я]", "", name.lower().replace("ö", "o").replace("ğ", "g")
               .replace("ş", "sh").replace("ç", "ch"))
    return hashlib.sha1(f"{n}|{day}".encode()).hexdigest()[:16]


# ---------------------------------------------------------------- asosiy ish
def issue(st, name, filial, maktab, day, source="", fan=""):
    raqam = st["next"]
    used = {r["n"] for r in st["log"]}
    while raqam in used:          # raqam hech qachon takrorlanmasin
        raqam += 1
    st["next"] = raqam + 1
    st["log"].append({"n": raqam, "ism": name, "filial": filial, "sana": day.isoformat(),
                      "manba": source[:200]})
    st["log"] = st["log"][-3000:]
    save_state(st, f"№ {raqam}")   # raqam yuborishdan OLDIN saqlanadi
    if st.get("dizayn", "eski") == "eski" and render is not None:
        jpg = render.render(maktab, name, raqam, day)
    else:
        v = st.get("dizayn", "v3")
        if not os.path.exists(os.path.join(render2.TPL, f"{v}_{maktab}.png")):
            v = "v3"
        jpg = render2.render(v, maktab, name, raqam, day, filial)
    sana = f"{day.day}-{render.OYLAR[day.month - 1]}, {day.year}"
    try:
        caption = st["izoh"].format(ism=name, filial=filial, raqam=f"{raqam:04d}",
                                    sana=sana, maktab=maktab.capitalize(), fan=fan)
    except (KeyError, IndexError, ValueError):
        caption = st["izoh"]
    fname = f"Tashakkurnoma_{raqam:04d}_{re.sub(r'[^A-Za-z0-9]+', '_', name)}.jpg"
    tg("sendDocument", chat_id=st["owner"], caption=caption[:1024],
       files={"document": (fname, jpg, "image/jpeg")})
    return raqam


HELP = ("Assalomu alaykum! Men «Kun o'qituvchisi» tashakkurnomalarini tayyorlayman.\n\n"
        "Guruhga tushgan har bir ustoz uchun tashakkurnoma (JPG) tayyorlab, sizga yuboraman.\n\n"
        "Buyruqlar:\n"
        "/izoh <matn> — rasm ostidagi izohni o'rnatish. Ichida {ism}, {fan}, {filial}, {raqam}, {sana} ishlatish mumkin\n"
        "/izoh — hozirgi izohni ko'rish\n"
        "/raqam <son> — keyingi raqamni o'rnatish (hozir: {next})\n"
        "/dizayn 1…5 — tashakkurnoma dizaynini tanlash\n"
        "/yangi Ism Familiya; Filial — qo'lda tashakkurnoma\n"
        "/royxat — oxirgi 20 ta berilgan tashakkurnoma\n"
        "/holat — bot holati")


def handle_private(st, m):
    chat = m["chat"]["id"]
    text = (m.get("text") or "").strip()
    if st["owner"] is None and text.startswith("/start"):
        st["owner"] = chat
        say(chat, "✅ Siz bot egasi sifatida belgilandingiz.\n\n" + HELP.replace("{next}", f"{st['next']:04d}"))
        return True
    if chat != st["owner"]:
        say(chat, "Bu bot faqat Monitoring bo'limi rahbari uchun.")
        return False
    body = text or (m.get("caption") or "").strip()
    if body and not body.startswith("/"):
        # egasi guruhdagi e'lonni botga uzatsa (forward) yoki matnini yuborsa — tashakkurnoma
        fm = dict(m)
        fm["text"] = body
        fm["date"] = (m.get("forward_origin") or {}).get("date") or m.get("forward_date") or m["date"]
        if not handle_group(st, fm, manual=True):
            pass
        return True
    if not body and m.get("media_group_id"):
        return False
    if not body:
        kind = next((k for k in ("photo", "video", "document", "animation", "voice", "video_note", "sticker") if k in m), "xabar")
        say(chat, f"Bu {kind}da matn (izoh) yo'q — ustoz ismi va filiali yozilmagan. "
                  "Ism yozilgan xabarni uzating yoki: /yangi Ism Familiya; Filial")
        return False
    cmd, _, arg = text.partition(" ")
    cmd = cmd.split("@")[0].lower()
    arg = arg.strip()
    if cmd in ("/start", "/help"):
        say(chat, HELP.replace("{next}", f"{st['next']:04d}"))
    elif cmd == "/izoh":
        if arg:
            st["izoh"] = arg
            say(chat, "✅ Izoh saqlandi. Namuna:\n\n" + arg.replace("{ism}", "Karimov Anvar")
                .replace("{filial}", "Chilonzor").replace("{raqam}", f"{st['next']:04d}")
                .replace("{sana}", "12-noyabr, 2026"))
            return True
        say(chat, "Hozirgi izoh:\n\n" + st["izoh"] + "\n\nO'zgartirish: /izoh <yangi matn>")
    elif cmd == "/raqam":
        if arg.isdigit():
            st["next"] = int(arg)
            say(chat, f"✅ Keyingi tashakkurnoma raqami: № {st['next']:04d}")
            return True
        say(chat, f"Keyingi raqam: № {st['next']:04d}\nO'zgartirish: /raqam 160")
    elif cmd == "/yangi":
        name_part, _, fil_part = arg.partition(";")
        name = clean_name(name_part)
        fil = find_filial(fil_part or arg)
        if not name or len(name.split()) < 2:
            say(chat, "Yozilishi: /yangi Karimov Anvar; Chilonzor")
            return False
        if not fil:
            fil = ("Registon", "registon")
        n = issue(st, name, fil[0], fil[1], dt.datetime.now(TZ).date(), "qo'lda")
        say(chat, f"✅ № {n:04d} tayyor.")
        return True
    elif cmd == "/dizayn":
        v = arg.strip().lower().lstrip("v")
        if v in ("1", "2", "3", "4", "5"):
            st["dizayn"] = "v" + v
            say(chat, f"✅ Endi tashakkurnomalar {v}-dizaynda chiqadi.")
            return True
        if v == "eski":
            st["dizayn"] = "eski"
            say(chat, "✅ Eski (Canva) dizayniga qaytildi.")
            return True
        say(chat, f"Hozirgi dizayn: {st.get('dizayn', 'eski')}\nTanlash: /dizayn 1 … /dizayn 5 yoki /dizayn eski")
    elif cmd == "/royxat":
        rows = [f"№ {r['n']:04d} — {r['ism']} ({r['filial']}, {r['sana']})" for r in st["log"][-20:]]
        say(chat, "\n".join(rows) or "Hali tashakkurnoma berilmagan.")
    elif cmd == "/holat":
        say(chat, f"Keyingi raqam: № {st['next']:04d}\nJami berilgan: {len(st['log'])}\n"
                  f"Kutilayotgan (filial so'ralgan): {len(st['pending'])}")
    else:
        say(chat, "Buyruqni tushunmadim. /help")
    return False


def ask_filial(st, name, day, src):
    pid = hashlib.sha1(f"{name}{day}{time.time()}".encode()).hexdigest()[:10]
    st["pending"][pid] = {"ism": name, "sana": day.isoformat(), "manba": src[:200]}
    say(st["owner"], f"❓ «{name}» qaysi filialdan? Xabarda filial topilmadi:\n\n{src[:300]}",
        reply_markup={"inline_keyboard": [[
            {"text": "Registon", "callback_data": f"f:{pid}:registon"},
            {"text": "Turkiston", "callback_data": f"f:{pid}:turkiston"},
            {"text": "Bekor", "callback_data": f"f:{pid}:x"}]]})


def handle_group(st, m, manual=False):
    if st["owner"] is None:
        return False
    if m.get("from", {}).get("is_bot"):
        return False
    text = m.get("text") or m.get("caption") or ""
    if not text.strip() or text.startswith("/"):
        return False
    day = dt.datetime.fromtimestamp(m["date"], TZ).date()
    pf = parse_fields(text)
    if pf and pf["sana"]:
        day = pf["sana"]
    fan = pf["fan"] if pf else ""
    name, fil = parse(text)
    if not name:
        say(st["owner"], "⚠️ Guruhdagi xabardan ustoz ismini aniqlay olmadim:\n\n"
            f"{text[:400]}\n\nQo'lda: /yangi Ism Familiya; Filial")
        return False
    key = norm_key(name, day.isoformat())
    if key in st["seen"]:
        if manual:
            say(st["owner"], f"ℹ️ «{name}» ga bugun tashakkurnoma allaqachon berilgan.")
        return False  # bugun bu ustozga tashakkurnoma berilgan
    st["seen"][key] = day.isoformat()
    if not fil:
        ask_filial(st, name, day, text)
        return True
    issue(st, name, fil[0], fil[1], day, text, fan)
    return True


def handle_callback(st, cq):
    tg("answerCallbackQuery", callback_query_id=cq["id"])
    if cq["from"]["id"] != st["owner"]:
        return False
    data = cq.get("data") or "::"
    msg = cq.get("message", {})
    if data.startswith("d:"):
        st["dizayn"] = data[2:]
        say(st["owner"], f"✅ Tanlandi: {data[3:]}-dizayn. Bundan keyingi tashakkurnomalar shu dizaynda chiqadi.")
        return True
    _, pid, choice = data.split(":", 2)
    p = st["pending"].pop(pid, None)
    msg = cq.get("message", {})
    if not p:
        return False
    if choice == "x":
        tg("editMessageText", chat_id=msg["chat"]["id"], message_id=msg["message_id"],
           text=f"❌ «{p['ism']}» bekor qilindi.")
        return True
    filial = "Registon" if choice == "registon" else "Sergeli Turkiston"
    n = issue(st, p["ism"], filial, choice, dt.date.fromisoformat(p["sana"]), p["manba"])
    tg("editMessageText", chat_id=msg["chat"]["id"], message_id=msg["message_id"],
       text=f"✅ «{p['ism']}» — {filial}, № {n:04d}")
    return True


def main():
    st = load_state()
    tg("deleteWebhook")
    tg("setMyCommands", commands=[
        {"command": "izoh", "description": "Rasm ostidagi izoh"},
        {"command": "raqam", "description": "Keyingi raqam"},
        {"command": "dizayn", "description": "Dizaynni tanlash (1-5)"},
        {"command": "yangi", "description": "Qo'lda tashakkurnoma"},
        {"command": "royxat", "description": "Oxirgi tashakkurnomalar"},
        {"command": "holat", "description": "Bot holati"}])
    start = time.time()
    print("bot ishga tushdi", flush=True)
    while not RUN_SECONDS or time.time() - start < RUN_SECONDS:
        ups = tg("getUpdates", offset=st["offset"], timeout=50,
                 allowed_updates=["message", "channel_post", "callback_query", "my_chat_member"])
        if ups is None:
            time.sleep(5)
            continue
        changed = False
        for u in ups:
            st["offset"] = u["update_id"] + 1
            try:
                if "callback_query" in u:
                    changed |= handle_callback(st, u["callback_query"])
                    continue
                m = u.get("message") or u.get("channel_post")
                if not m:
                    if "my_chat_member" in u and st["owner"]:
                        c = u["my_chat_member"]["chat"]
                        status = u["my_chat_member"]["new_chat_member"]["status"]
                        say(st["owner"], f"ℹ️ Bot «{c.get('title')}» guruhida: {status}"
                            + ("\nMuhim: barcha xabarlarni ko'rishim uchun meni guruhda ADMIN qiling."
                               if status == "member" else ""))
                    continue
                if m["chat"]["type"] == "private":
                    changed |= handle_private(st, m)
                else:
                    changed |= handle_group(st, m)
            except Exception:
                traceback.print_exc()
                if st["owner"]:
                    say(st["owner"], "⚠️ Xabarni ishlashda xato yuz berdi, qo'lda tekshiring.")
        if ups:
            save_state(st, "holat" if changed else "offset")


if __name__ == "__main__":
    main()
