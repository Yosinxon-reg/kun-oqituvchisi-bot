"""Monitoring bölimining samimiy izohi (darslar kamera orqali kuzatiladi) — har bir ustozga o'ziga xos.

v2 (bepul, qoidaga asoslangan):
  1) kiriş — ustozga murojaat + aniq dars konteksti (sinf, fan);
  2) postdan olingan ANIQ lahza: nomi bilan atalgan öyin/metod («Ha/Yöq» öyini) yoki dars vositasi (lenta, kartoçka…);
  3) darsning 1–2 jihati (mavzu bankidan, har jihatga bir neça variant);
  4) ustoz tarixi (birinçi unvon / nechanchi unvon);
  5) xotima. Imzo — bitta: «— Registon monitoring bölimi».
Hamma gaplar yangi alifboda; yakuniy matn imlo tekşiruvidan ötadi (tekşir()). Emoji yöq.
Bir ustozga bir gap ikki marta ishlatilmaydi (used).
"""
import hashlib
import random
import re

try:
    from names import yangi as _yangi
except Exception:                                    # testlar uçun
    def _yangi(s):
        return s


def _n(s):
    s = (s or "").lower()
    for a, b in (("ş", "sh"), ("ç", "ch"), ("ö", "o"), ("ğ", "g"), ("ʻ", ""), ("‘", ""), ("’", ""), ("ʼ", ""),
                 ("'", ""), ("`", ""), ("–", "-"), ("—", "-")):
        s = s.replace(a, b)
    return s


# ---------------------------------------------------------------- darsning jihatlari (aniqlaş, gaplar)
MAVZU = [
    ("namuna", r"namuna sifatida|ozi (korsat|namuna|bajar)|avval ozi|shaxsiy namuna", [
        "Har bir harakatni avval özingiz körsatib berdingiz — bolalar sizga qarab örganayotgani yaqqol sezildi.",
        "Avval özingiz körsatib, keyin bolalarga bajartirganingiz darsni ança tuşunarli qildi.",
        "Şaxsiy namunangiz bolalar uçun eng yaxşi tuşuntiriş böldi."]),
    ("xavfsizlik", r"xavfsizlik", [
        "Bolalarning xavfsizligiga şunçalik eʼtiborli ekaningiz uçun sizdan minnatdormiz.",
        "Har bir maşq qiziqarli ham, xavfsiz ham böldi — buni alohida qayd etamiz.",
        "Xavfsizlik qoidalarini eslatib turganingiz katta masʼuliyat belgisi."]),
    ("ikki_til", r"ingliz tilida ham|ikki tilda", [
        "Atamalarni ingliz tilida ham örgatganingiz bolalarga ikki baravar foyda berdi.",
        "Mavzuni ikki tilda tuşuntirganingiz darsni yanada boyitdi."]),
    ("hayotiy", r"hayotiy|kundalik hayot|real hayot|turmush", [
        "Mavzuni hayotiy misollar bilan bağlaganingiz uçun bolalar uni tez ilib oldi.",
        "Hayotdan olingan misollar mavzuni bolalarga ança yaqin qildi.",
        "Bilimni kundalik hayot bilan bağlaş — darsning eng kuçli tomonlaridan biri böldi."]),
    ("amaliy", r"amaliy mashq|amaliy ish|tajriba|qol bilan|yasash|yasalgan|maket", [
        "Bolalar öz qöllari bilan bajarib örgandi — bunday bilim xotirada uzoq saqlanadi.",
        "Amaliy iş paytida bolalarning berilib işlayotganini zavq bilan kuzatdik.",
        "Nazariyani darrov amaliyotda sinab köriş bolalarga juda foydali böldi."]),
    ("ijodiy", r"ijodiy|creative|loyiha|project|rasm chiz", [
        "Bolalarga özlarini ijodda körsatiş imkonini berganingiz darsga alohida ruh bağişladi.",
        "Ijodiy topşiriqlarni bolalar katta zavq bilan bajardi.",
        "Har bir bolaning ijodiga hurmat bilan qaraganingiz sezilib turdi."]),
    ("harakat", r"egiluvchan|muvozanat|koordinatsiya|akrobatik|chaqqonlik", [
        "Egiluvçanlik va muvozanat maşqlari puxta, bosqiçma-bosqiç ötkazildi.",
        "Har bir element tartib bilan, aniq bajarildi — ortida qançalik mehnat borligini his qildik."]),
    ("musiqa", r"musiqa|qoshiq (ayt|kuyla|bilan|orqali)|\bsong\b", [
        "Musiqa bilan ötgan qism darsga yengil va quvnoq ruh bağişladi.",
        "Darsga musiqani şunday öz örnida qöşganingiz bolalarning kayfiyatini kötardi."]),
    ("oyin", r"oyin|game|musobaqa|bellashuv|viktorina|quiz|kahoot|wordwall", [
        "Öyin paytida bolalarning közidagi quvonçni kamera orqali ham aniq kördik.",
        "Kiçik musobaqa sinfni bir zumda jonlantirib yubordi.",
        "Öyin orqali örgatiş — bolalar uçun eng tabiiy yöl, siz undan juda öz örnida foydalandingiz."]),
    ("guruh", r"guruh|jamoa|juftlik|pair work|group work", [
        "Guruhlarda işlaganda bolalar bir-biriga yordam berayotganini körib quvondik.",
        "Guruh işi şunday taşkil etildiki, heç bir bola çetda qolmadi.",
        "Juftlik va guruhlarda işlaş bolalarni bir-birini tinglaşga örgatdi."]),
    ("speaking", r"speaking|gapir|muloqot|communicative|dialog|role ?play|rolli", [
        "Bolalar tortinmay gapirdi — bunga sizning sabr va mehringiz sabab, deb öylaymiz.",
        "Öquvçilaringiz erkin muloqot qilayotganini körib juda xursand böldik.",
        "Darsda bolalarning ovozi köp eşitildi — bu eng yaxşi belgi."]),
    ("lugat", r"lugat|yangi soz|vocabulary|new words", [
        "Yangi sözlar şunday qiziqarli örgatildiki, bolalar ularni tez eslab qoldi.",
        "Yangi sözlar ustida işlaş qismi juda puxta taşkil etildi."]),
    ("korgazma", r"korgazma|tarqatma|kartochka|flashcard|plakat|vizual", [
        "Körgazmali qurollar qançalik puxta tayyorlangani darhol sezildi.",
        "Körsatmali materiallar mavzuni bolalarga ança oson qildi.",
        "Vizual vositalar darsni yanada tuşunarli va esda qolarli qildi."]),
    ("texno", r"video|slayd|taqdimot|proyektor|interaktiv doska|smart|planshet|kompyuter|robot", [
        "Texnologiyadan öz örnida foydalanib, bolalarning diqqatini oxirigaça uşlab turdingiz.",
        "Taqdimot va videolar mavzuni yanada jonli qildi."]),
    ("savol", r"savol-javob|savol javob|aqliy hujum|brainstorm|ogzaki savol", [
        "Savol-javob paytida bolalar qöl kötarişga şoşilayotgani bizni quvontirdi.",
        "Savollaringiz bolalarni öylaşga undadi — bu eng muhimi.",
        "Oğzaki savollar orqali ötilgan mavzu tez va samarali esga tuşirildi."]),
    ("warmup", r"warm-?up|qizdirish|energizer|badantarbiya|razminka", [
        "Darsni şunday quvnoq boşladingizki, sinf birinçi daqiqadanoq faol böldi.",
        "Darsning boşidagi qizdiriş qismi hammaning kayfiyatini kötardi."]),
    ("fikrlash", r"mantiq|fikrla|tanqidiy|critical|tahlil", [
        "Bolalarni öz fikrini aytişga, öylab topişga undaganingiz alohida tahsinga loyiq.",
        "Bolalar tayyor javobni emas, javobni özlari izlab topişni örgandi."]),
    ("ragbat", r"ragbat|maqtov|smayl|yulduzcha|sticker|reward|qollab-quvvat", [
        "Bolalarni öz vaqtida rağbatlantirganingiz ularning ruhini kötardi.",
        "Kiçik yutuqlarni ham eʼtibordan çetda qoldirmadingiz — bolalar buni albatta his qiladi.",
        "Iliq va rağbatlantiruvçi sözlaringiz sinfda işonç muhitini yaratdi."]),
    ("bosqich", r"oddiydan murakkab|bosqiçma-bosqiç|ketma-ketlik|puxta reja|reja asosida", [
        "Mavzu oddiydan murakkabga qarab şunday izçil tuşuntirildiki, heç kim adaşmadi.",
        "Dars puxta reja asosida, bir maromda ötdi — har bir bosqiç öz örnida edi."]),
    ("refleksiya", r"refleksiya|reflection|sarhisob|xulosa chiqar", [
        "Dars oxirida bolalar nimani örganganini özlari aytib berdi — bu juda qimmatli.",
        "Yakuniy sarhisob mavzuni bolalar xotirasida mustahkamladi."]),
    ("individual", r"individual|har bir (oquvchi|bola|qiz|ogil)|alohida (etibor|yondash)|yakka tartib", [
        "Har bir bolaga alohida eʼtibor berganingiz yaqqol körindi.",
        "Heç bir bola eʼtibordan çetda qolmadi — har biriga vaqt topdingiz.",
        "Öquvçilar mustaqil işlayotganda har biri bilan alohida şuğullanganingiz eʼtiborimizni tortdi."]),
    ("doska", r"doskaga|doskada|birgalikda", [
        "Bolalarni doskaga faol jalb etganingiz ularni ança dadil qildi.",
        "Doskada birgalikda işlaş bolalarning özlariga işonçini oşirdi."]),
    ("shior", r"shior", [
        "Darsni fan şiori bilan boşlaganingiz bolalarning kayfiyatini darhol kötardi."]),
    ("intizom", r"intizom", [
        "Sinfda tartib ham, iliq muhit ham bor edi — bu ikkisini uyğunlaştiriş oson emas.",
        "Bolalar intizomli, ammo erkin edi — buni körib xursand böldik."]),
    ("kayfiyat", r"ijobiy kayfiyat|samimiy|iliq|xushkayfiyat|quvnoq|kotarinki|psixologik muhit", [
        "Sinfdagi iliq va samimiy muhitni hatto kamera orqali ham his qildik.",
        "Bolalar darsingizda özlarini erkin his qilayotgani körinib turdi.",
        "Kötarinki kayfiyat birinçi daqiqadanoq butun sinfga yuqdi."]),
    ("mustahkam", r"mustahkam|takrorla", [
        "Ötilgan mavzu şunday yaxşi mustahkamlandiki, bolalar uni bemalol esladi.",
        "Takrorlaş qismi juda samarali ötdi — bilim puxta mustahkamlandi."]),
]
_MC = [(k, re.compile(rx), g) for k, rx, g in MAVZU]

FAN = [  # (aniqlaş, gap)
    (r"ingliz|english", "Ingliz tili darsida bolalarni bunday faol qiliş oson emas — siz buni uddaladingiz."),
    (r"boshlang|oqish|alifbo", "Kiçkintoylar bilan qançalik sabr va mehr bilan işlayotganingiz körinib turdi."),
    (r"rus", "Rus tili darsini bunday qiziqarli ötganingiz tahsinga loyiq."),
    (r"matemat|geometr|algebra", "Matematikani bunçalik sodda va tuşunarli tuşuntiriş — katta mahorat."),
    (r"gimnast|jismoniy|taekvon|kamon|sport|kurash|suzish", "Bolalarning soğliği va xavfsizligiga bunday eʼtibor — katta masʼuliyat."),
    (r"tasviriy|sanat|musiqa|raqs", "Bolalarda gözallikka mehr uyğotayotganingiz uçun rahmat."),
    (r"shaxmat", "Şaxmat orqali bolalarni öylaşga örgatayotganingiz juda qadrli."),
    (r"robot|texnolog|texnalog|\bit\b|informat|dastur", "Bolalar öz qöllari bilan nimadir yaratganidan qançalik xursand bölganini kördik."),
    (r"tarix", "Tarixni şunday qiziqarli hikoya qildingizki, biz ham tinglab qoldik."),
    (r"ona tili|adabiyot", "Ona tilimizga mehr uyğotayotganingiz uçun sizdan minnatdormiz."),
    (r"arab|nemis|xitoy|koreys|turk", "Til örgatişdagi sabr-toqatingizni yaqqol his qildik."),
]
FAN_DEF = "Bunday darslar bolalar xotirasida uzoq saqlanadi."

# ---------------------------------------------------------------- kiriş, tarix, xotima
KIRISH = [
    "{U}, {ctx}darsingizni katta qiziqiş bilan kuzatdik.",
    "{U}, {ctx}darsingizni kuzatib, sizga albatta yozgimiz keldi.",
    "{U}, {ctx}darsingizni kuzatar ekanmiz, vaqt qanday ötganini sezmay qoldik.",
    "{U}, bugungi {ctx}darsingiz bizda juda iliq taassurot qoldirdi.",
    "{U}, {ctx}darsingiz boşidan oxirigaça bir nafasda ötdi.",
    "{U}, {ctx}darsingizni zavq bilan kuzatdik — bunday darslar köp uçrayvermaydi.",
]
TARIX = [
    ["Bu sizning ilk «Kun öqituvçisi» unvoningiz — çin dildan muborak bölsin!",
     "Monitoringdagi birinçi unvoningiz bilan samimiy tabriklaymiz.",
     "Ilk unvoningiz — bu endigina boşlanişi, deb işonamiz."],
    ["Bu sizning {nth}-unvoningiz — natijalaringiz barqarorligi bizni quvontiradi.",
     "{nth}-marta «Kun öqituvçisi» — demak, bu tasodif emas.",
     "Darslaringiz yana bir bor yuqori bahoga loyiq böldi — bu {nth}-unvoningiz."],
    ["{nth}-marta «Kun öqituvçisi» — bu tizimli mehnat va katta mehrning samarasi.",
     "{nth}-unvoningiz bilan tabriklaymiz — darslaringiz boşqa ustozlarimizga ham namuna bölmoqda.",
     "Siz bu unvonni {nth}-marta qölga kiritdingiz — bunday barqarorlik çin mahoratdan dalolat."],
]
XOTIMA = [
    "Mehnatingiz uçun samimiy rahmat!",
    "Şu ruhda davom eting!",
    "Sizga yangi ijodiy yutuqlar tilaymiz.",
    "Bunday darslaringiz uçun katta rahmat.",
    "Keyingi darslaringizni ham intiqlik bilan kutamiz.",
    "Siz bilan faxrlanamiz!",
    "Öquvçilaringizga bergan mehringiz uçun rahmat.",
    "Bardavom böling!",
]
IMZO = ["— Registon monitoring bölimi"]

# ---------------------------------------------------------------- postdan aniq lahzalar
QUOTE = re.compile(r"[«“\"]([^»”\"\n]{3,32})[»”\"]\s*([A-Za-zÖöĞğŞşÇçʻʼ'‘’`-]{3,14})?")
TURI = [  # (söz boşi, egalik şakli)
    (r"oyin", "öyini"), (r"metod", "metodi"), (r"usul", "usuli"), (r"texnika", "texnikasi"),
    (r"mashq", "maşqi"), (r"topshiri", "topşiriği"), (r"strategiya", "strategiyasi"), (r"savol", "savoli"),
]
QUOTE_GAP = [
    "Ayniqsa {Q} sinfni bir zumda jonlantirib yubordi.",
    "{Q} alohida eʼtiborimizni tortdi — bolalar unda katta qiziqiş bilan qatnaşdi.",
    "{Q} darsga juda öz örnida qöşilgan, topqir yeçim böldi.",
]
VOSITA = [  # (aniqlaş, nomi)
    (r"\blenta", "lenta"), (r"geometrik shakl", "geometrik şakllar"), (r"kubik", "kubiklar"),
    (r"kartochka|kartocka|flashcard", "kartoçkalar"), (r"plakat", "plakatlar"), (r"globus", "globus"),
    (r"xarita", "xarita"), (r"tayoqcha", "sanoq tayoqçalari"), (r"pazl|puzzle", "pazllar"),
    (r"lego", "LEGO konstruktori"), (r"plastilin", "plastilin"), (r"rangli qogoz", "rangli qoğoz"),
    (r"koptok", "koptok"), (r"mozaika", "mozaika"), (r"magnit", "magnitli materiallar"),
]
VOSITA_GAP = [
    "{V} yordamida mavzuni körsatganingiz uni bolalar köz oldida jonlantirdi.",
    "{V} bilan işlaganda bolalarning qiziqişi yanada oşganini aniq sezdik.",
    "Oddiygina {v} ham sizning qölingizda ajoyib dars vositasiga aylandi.",
]


def mavzular(matn):
    t = _n(matn)
    return [(k, g) for k, rx, g in _MC if rx.search(t)]


def _body(matn):
    parts = (matn or "").split("\n\n", 1)
    return parts[1] if len(parts) > 1 else ""


def lahza_quote(matn):
    """Postda nomi bilan atalgan öyin/metod: «Ha/Yöq» öyini -> "«Ha/Yöq» öyini"."""
    for m in QUOTE.finditer(_body(matn)):
        q, w = m.group(1).strip(), _n(m.group(2) or "")
        if "kun" in _n(q) or len(re.sub(r"\W", "", q)) < 2:
            continue
        for rx, eg in TURI:
            if w.startswith(rx):
                return f"«{_yangi(q)}» {eg}"
    return None


def lahza_vosita(matn):
    t = _n(_body(matn))
    for rx, nom in VOSITA:
        if re.search(rx, t):
            return nom
    return None


def sinf_of(matn):
    m = re.search(r"(?:Dars|Sinf)\s*:[^\n]*?\b(\d{1,2})\s*-?\s*[«\"“”]?\s*([A-Za-zА-Яа-я])\b", matn or "")
    return f"{m.group(1)}-{m.group(2).upper()}" if m else None


def fan_soz(fan_text, matn):
    """«matematika», «ingliz tili» … (boşlanğiç sinf uçun Dars qatoridan)."""
    m = re.search(r"(?:Dars|Sinf)\s*:[^\n]*?([A-Za-zÖöĞğŞşÇç'ʻʼ‘’]+(?: tili)?)\s+darsi", matn or "", re.I)
    if m and _n(m.group(1)) not in ("sinf", "soat", "ochiq"):
        return _yangi(m.group(1).lower())
    f = _n(fan_text or "")
    f = re.sub(r"\s*(fani\s+)?(oqituvchisi|oqituvcisi|ustozi?)\s*$", "", f).strip()
    if not f or "sinf" in f or "boshlang" in f or len(f) > 25:
        return None
    return _yangi(f)


def fan_gap(fan_text, matn):
    for t in (_n(fan_text or ""), _n(re.sub(r"(?s)Natija:.*", "", matn or "")[:400])):
        for rx, g in FAN:
            if re.search(rx, t):
                return g
    return FAN_DEF


def tier(nth):
    return 0 if nth <= 1 else 1 if nth <= 3 else 2


def murojaat(ism_toliq):
    w = _yangi(ism_toliq or "").split()
    if len(w) >= 3:
        return " ".join(w[1:])                    # Nigina Ganijon qizi
    if len(w) == 2:
        return f"{w[1]} ustoz"
    return "Hurmatli ustoz"


# ---------------------------------------------------------------- imlo tekşiruvi
BANNED = ["jon kiritdi", "ilhom berasiz", "siz ilhom", "zör ğoya", "kirdik", "darsga kirib", "darsingizga keldik"]
OLD = re.compile(r"sh|ch|[oOgG]['ʻ‘’`]|\s{2,}| ,| \.|\.\.|[\U0001F300-\U0001FAFF☀-➿]")


def tekshir(text, ism=""):
    """-> xatolar röyxati (böş bölsa — toza)."""
    t = text.replace(_yangi(ism or ""), "")
    xato = []
    for m in OLD.finditer(t.lower() if not re.search(r"[\U0001F300-\U0001FAFF☀-➿]", t) else t):
        xato.append(m.group(0))
    lt = t.lower()
    xato += [b for b in BANNED if b in lt]
    return xato


# ---------------------------------------------------------------- yiğiş
def yoz(ism_toliq, matn, fan_text, n, nth, used=None):
    """-> (izoh, imzo, ishlatilgan_gap_kalitlari). used: shu ustozga avval berilgan gaplar (takrorlanmasin)."""
    used = set(used or [])
    rnd = random.Random(int(hashlib.md5(f"{n}|{ism_toliq}".encode()).hexdigest()[:8], 16))
    U = murojaat(ism_toliq)
    sinf, fs = sinf_of(matn), fan_soz(fan_text, matn)
    ctx = (f"{sinf} sinfdagi " if sinf else "") + (f"{fs} " if fs else "")
    ti = tier(nth)

    def pick(key, items):
        opts = [(f"{key}{i}", s) for i, s in enumerate(items)]
        fresh = [o for o in opts if o[0] not in used] or opts
        k, s = rnd.choice(fresh)
        used.add(k)
        return k, s

    keys, parts = [], []
    k, s = pick("K.", KIRISH); keys.append(k)
    parts.append(s.format(U=U, ctx=ctx))

    # aniq lahza(lar)
    q, v = lahza_quote(matn), lahza_vosita(matn)
    skip = set()
    if q:
        k, s = pick("Q.", QUOTE_GAP); keys.append(k)
        parts.append(s.format(Q=q[0].upper() + q[1:] if s.startswith("{Q}") else q))
        skip |= {"oyin"}
    if v and (not q or rnd.random() < 0.6):
        k, s = pick("V.", VOSITA_GAP); keys.append(k)
        parts.append(s.format(V=v[0].upper() + v[1:], v=v))
        skip |= {"korgazma"}

    # darsning jihatlari
    mz = [m for m in mavzular(matn) if m[0] not in skip]
    nj = 1 if len(parts) >= 3 else 2
    top = mz[:5]
    rnd.shuffle(top)
    tanlangan = sorted(top[:nj], key=lambda x: [m[0] for m in mz].index(x[0]))
    for mk, gaps in tanlangan:
        k, s = pick(f"m.{mk}.", gaps); keys.append(k); parts.append(s)
    if len(parts) < 3:
        parts.append(fan_gap(fan_text, matn))

    # tarix
    if ti == 0 or rnd.random() < 0.75:
        k, s = pick(f"T{ti}.", TARIX[ti]); keys.append(k); parts.append(s.format(nth=nth))
    k, s = pick("X.", XOTIMA); keys.append(k); parts.append(s)

    text = re.sub(r"\s+", " ", " ".join(parts)).strip()
    if tekshir(text, ism_toliq):                     # xavfsiz yöl: aniq lahzalarsiz qayta yiğiş
        parts = [parts[0]] + [g for _, gs in tanlangan for g in gs[:1]] + [XOTIMA[0]]
        text = re.sub(r"\s+", " ", " ".join(parts)).strip()
    return text, IMZO[0], keys
