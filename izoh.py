"""Monitoring bölimining samimiy izohi (darslar kamera orqali kuzatiladi) — har bir ustozga o'ziga xos.

Izoh post matnidagi dars jihatlariga (mavzu) qarab, oldindan yozilgan iliq gaplardan yiğiladi:
  kiriş (unvon soniga qarab) + darsning 1–2 jihati + (ba'zan fanga oid gap) + xotima, va anonim imzo.
Postdagi gaplar köçirilmaydi — faqat fikr olinadi. Bir ustozga bir gap ikki marta ishlatilmaydi.
"""
import hashlib
import random
import re


def _n(s):
    s = (s or "").lower()
    for a, b in (("ş", "sh"), ("ç", "ch"), ("ö", "o"), ("ğ", "g"), ("ʻ", ""), ("‘", ""), ("’", ""),
                 ("'", ""), ("`", ""), ("–", "-"), ("—", "-")):
        s = s.replace(a, b)
    return s


# mavzu: (aniqlash, gaplar) — tartib = ustuvorlik (aniqrog'i oldinda)
MAVZU = [
    ("namuna", r"namuna sifatida|ozi (korsat|namuna|bajar)|avval ozi|shaxsiy namuna", [
        "Har bir harakatni avval özingiz körsatib berdingiz — bolalar sizga qarab örganayotganini körib quvondik.",
        "Avval özingiz körsatib, keyin bolalarga bajartirganingiz bizga juda yoqdi."]),
    ("xavfsizlik", r"xavfsizlik", [
        "Bolalarning xavfsizligiga şunçalik eʼtiborli bölganingiz uçun sizdan minnatdormiz.",
        "Hamma maşqlar qiziqarli ham, xavfsiz ham böldi — bunga alohida rahmat."]),
    ("ikki_til", r"ingliz tilida ham|ikki tilda", [
        "Atamalarni ingliz tilida ham örgatganingiz bolalarga ikki baravar foyda böldi — zör ğoya!",
        "Fanni ikki tilda tuşuntirganingiz bizga juda yoqdi."]),
    ("hayotiy", r"hayotiy|kundalik hayot|real hayot|turmush", [
        "Mavzuni hayotiy misollar bilan tuşuntirdingiz — bolalar darrov tuşunib oldi, buni körib xursand böldik.",
        "Hayotdan misollar keltirganingiz uçun mavzu bolalarga juda yaqin böldi."]),
    ("amaliy", r"amaliy mashq|amaliy ish|tajriba|qol bilan|yasash|yasalgan|maket", [
        "Bolalar öz qöllari bilan bajarib örgandi — bunday bilim ularda uzoq qoladi. Rahmat!",
        "Amaliy işlar paytida bolalarning qiziqib işlayotganini körib quvondik."]),
    ("ijodiy", r"ijodiy|creative|loyiha|project|rasm chiz", [
        "Bolalarga özlarini ijodda körsatiş imkonini berganingiz bizga juda yoqdi.",
        "Ijodiy topşiriqlarni bolalar katta zavq bilan bajardi."]),
    ("harakat", r"egiluvchan|muvozanat|koordinatsiya|akrobatik|chaqqonlik", [
        "Egiluvçanlik va muvozanat maşqlarini şunday puxta ötkazganingizni körib quvondik.",
        "Har bir element tartib bilan, aniq bajarildi — ortida qançalik mehnat borligini his qildik."]),
    ("musiqa", r"musiqa|qoshiq|song", [
        "Musiqa bilan ötgan qism bolalarga ham, bizga ham juda yoqdi 🎵",
        "Darsga musiqani şunday çiroyli qöşganingiz bizning ham kayfiyatimizni kötardi."]),
    ("oyin", r"oyin|game|musobaqa|bellashuv|viktorina|quiz|kahoot|wordwall", [
        "Öyin paytida bolalarning közidagi quvonçni körib, biz ham xursand böldik.",
        "Kiçik musobaqa bolalarni şunday qiziqtirdiki — zör ğoya böldi!"]),
    ("guruh", r"guruh|jamoa|juftlik|pair work|group work", [
        "Guruhlarda işlaganda bolalarning bir-biriga yordam berayotganini körib quvondik.",
        "Guruh işini şunday taşkil qildingizki, hech bir bola çetda qolmadi."]),
    ("speaking", r"speaking|gapir|muloqot|communicative|dialog|role ?play|rolli", [
        "Bolalar tortinmay gapirdi — bunga sizning mehringiz va sabringiz sabab, deb öylaymiz.",
        "Öquvçilaringiz erkin gapirayotganini körib juda xursand böldik."]),
    ("lugat", r"lugat|yangi soz|vocabulary|new words", [
        "Yangi sözlarni şunday qiziqarli örgatdingizki, bolalar ularni tez eslab qoldi.",
        "Yangi sözlar ustida işlaganingiz bizga juda yoqdi."]),
    ("korgazma", r"korgazma|tarqatma|kartochka|flashcard|plakat", [
        "Körgazmali qurollarni qançalik puxta tayyorlaganingiz darhol sezildi — rahmat.",
        "Körsatmali materiallar mavzuni bolalarga ancha oson qildi."]),
    ("texno", r"video|slayd|taqdimot|proyektor|ipc|interaktiv|smart|planshet|kompyuter|robot", [
        "Video va qiziqarli topşiriqlar bilan bolalarning diqqatini oxirigaça uşlab turdingiz.",
        "Texnologiyani şunday öz örnida işlatganingiz bizga juda yoqdi."]),
    ("savol", r"savol-javob|savol javob|aqliy hujum|brainstorm", [
        "Savol-javob paytida bolalar qöl kötarişga şoşilayotganini körib quvondik 🙂",
        "Savollaringiz bolalarni öylaşga undadi — bu eng muhimi."]),
    ("warmup", r"warm-?up|qizdirish|energizer|badantarbiya|razminka", [
        "Darsni şunday quvnoq boşladingizki, sinf birinçi daqiqadanoq faol böldi.",
        "Darsning boşidagi qizdiriş qismi hammaning kayfiyatini kötardi."]),
    ("fikrlash", r"mantiq|fikrla|tanqidiy|critical|tahlil", [
        "Bolalarni öz fikrini aytişga, öylaşga undaganingiz bizga juda yoqdi.",
        "Bolalar tayyor javobni emas, özlari öylab topişni örgandi — rahmat sizga."]),
    ("ragbat", r"ragbat|maqtov|smayl|yulduzcha|sticker|reward", [
        "Bolalarni öz vaqtida maqtaganingiz ularni juda xursand qildi.",
        "Kiçik yutuqlarini ham eʼtibordan çetda qoldirmadingiz — bolalar buni his qiladi."]),
    ("bosqich", r"oddiydan murakkab|bosqichma-bosqich|ketma-ketlik", [
        "Mavzuni oddiydan murakkabga qarab şunday tuşuntirdingizki, hech kim adaşmadi."]),
    ("refleksiya", r"refleksiya|reflection|sarhisob|xulosa chiqar", [
        "Dars oxirida bolalar nimani örganganini özlari aytib berdi — bu juda yoqdi."]),
    ("individual", r"individual|har bir (oquvchi|bola|qiz|ogil)|alohida (etibor|yondash)|yakka tartib", [
        "Har bir bolaga alohida eʼtibor berganingizni körib juda quvondik.",
        "Hech bir bola eʼtibordan çetda qolmadi — har biriga vaqt topdingiz. Rahmat sizga!"]),
    ("doska", r"doskada|birgalikda", [
        "Doskada bolalar bilan birga işlaganingiz ularni ancha dadil qildi."]),
    ("shior", r"shior", [
        "Darsni fan şiori bilan boşlaganingiz bolalarning kayfiyatini darhol kötardi."]),
    ("intizom", r"intizom", [
        "Sinfda tartib ham, iliq muhit ham bor edi — bu oson emas, ustoz.",
        "Bolalar intizomli, lekin erkin edi — buni körib xursand böldik."]),
    ("kayfiyat", r"ijobiy kayfiyat|samimiy|iliq|xushkayfiyat|quvnoq", [
        "Sinfdagi iliq va samimiy muhitni hatto kamera orqali ham his qildik 🙂",
        "Bolalar sizning darsingizda özlarini juda erkin his qilayotgani körinib turdi."]),
    ("mustahkam", r"mustahkam|takrorla", [
        "Ötilgan mavzuni şunday yaxşi mustahkamladingizki, bolalar hammasini eslab qoldi.",
        "Takrorlaş qismi juda yaxşi ötdi — bilim mustahkam böldi."]),
]
_MC = [(k, re.compile(rx), g) for k, rx, g in MAVZU]

FAN = [  # (aniqlash, gap)
    (r"ingliz|english", "Ingliz tili darsida bolalarni bunday faol qiliş oson emas — siz buni uddaladingiz."),
    (r"boshlang|tabiiy fan|oqish|alifbo", "Kiçkintoylar bilan qançalik sabr va mehr bilan işlayotganingiz körinib turdi."),
    (r"rus", "Rus tili darsini bunday qiziqarli ötganingiz bizga juda yoqdi."),
    (r"matemat|geometr|algebra", "Matematikani bunçalik tuşunarli tuşuntirganingiz uçun bolalar sizdan minnatdor bölsa kerak 🙂"),
    (r"gimnast|jismoniy|taekvon|kamon|sport|kurash|suzish", "Bolalarning soğliği va xavfsizligiga bunday eʼtibor — katta masʼuliyat, rahmat."),
    (r"tasviriy|sanat|musiqa|raqs", "Bolalarda gözallikka mehr uyğotayotganingiz uçun rahmat."),
    (r"shaxmat", "Şaxmat orqali bolalarni öylaşga örgatayotganingiz juda qadrli."),
    (r"robot|texnolog|texnalog|\bit\b|informat|dastur", "Bolalar öz qöllari bilan nimadir yaratganidan juda xursand böldi."),
    (r"tarix", "Tarixni şunday qiziqarli hikoya qildingizki, biz ham tinglab qoldik."),
    (r"arab|nemis|xitoy|koreys|turk", "Til örgatişdagi sabr-toqatingizni his qildik."),
]
FAN_DEF = "Şunday darslar uçun sizga katta rahmat."

KIRISH = [
    ["{U}, bugungi darsingizni katta zavq bilan kuzatdik.",
     "{U}, {sinf} sinfdagi darsingizni körib juda xursand böldik!",
     "Assalomu alaykum, {U}! Bugungi darsingizni körib, sizga albatta yozgimiz keldi.",
     "{U}, darsingizni kuzatar ekanmiz, vaqt qanday ötganini sezmay qoldik 🙂",
     "{U}, bugun sizning darsingiz bizga juda yoqdi."],
    ["{U}, yana siz! Bugungi darsingizni ham katta qiziqiş bilan kuzatdik.",
     "{U}, darsingizni yana kuzatdik — va yana xursand böldik.",
     "Yana bir zör dars, {U}! Endi bu tasodif emasligini bilamiz 🙂",
     "{U}, sizning darslaringizni kutib qoladigan bölib qoldik 🙂"],
    ["{U}, bu sizning {n}-unvoningiz — va bugungi dars ham bunga munosib böldi.",
     "{U}, har safar darsingizni kuzatganda yangi bir narsa örganamiz.",
     "{U}, rostini aytsak, darsingizni kuzatib biz ham köp narsa örgandik."],
    ["{U}, bu {n}-unvoningiz! Siz bilan çin dildan faxrlanamiz.",
     "{U}, darslaringiz boşqa ustozlarimizga ham namuna bölib qoldi.",
     "{U}, {n}-marta «Kun öqituvçisi» — bu katta mehnat va mehrning natijasi."],
]
XOTIMA = [
    ["Rahmat sizga, ustoz!", "Şunday davom eting! 👏", "Birinçi unvoningiz muborak bölsin!", "Sizdan faxrlanamiz.",
     "Keyingi darslaringizni intiqlik bilan kutamiz."],
    ["Bardavom böling, ustoz!", "Keyingi darslaringizni kutamiz 🙂", "Rahmat sizga!", "Şu ruhda davom eting!"],
    ["Biz ham sizdan örganyapmiz. Rahmat!", "Siz bilan birga işlayotganimizdan xursandmiz.", "Ofarin, ustoz!",
     "Şunday davom eting!"],
    ["Siz bilan faxrlanamiz!", "Yangi darslaringizni kutamiz!", "Çin dildan rahmat!", "Katta rahmat, ustoz!"],
]
IMZO = ["— Registon monitoring bölimi"]


def mavzular(matn):
    t = _n(matn)
    return [(k, g) for k, rx, g in _MC if rx.search(t)]


def sinf_of(matn):
    m = re.search(r"(?:Dars|Sinf)\s*:[^\n]*?\b(\d{1,2})\s*-?\s*[«\"“”]?\s*([A-Za-zА-Яа-я])\b", matn or "")
    return f"{m.group(1)}-{m.group(2).upper()}" if m else None


def fan_gap(fan_text, matn):
    t = _n((fan_text or "") + " " + re.sub(r"(?s)Natija:.*", "", matn or "")[:400])
    for rx, g in FAN:
        if re.search(rx, t):
            return g
    return FAN_DEF


def tier(nth):
    return 0 if nth <= 1 else 1 if nth <= 3 else 2 if nth <= 6 else 3


def yoz(ism_toliq, matn, fan_text, n, nth, used=None):
    """-> (izoh, imzo, ishlatilgan_gap_kalitlari). used: shu ustozga avval berilgan gaplar (takrorlanmasin)."""
    used = set(used or [])
    rnd = random.Random(int(hashlib.md5(f"{n}|{ism_toliq}".encode()).hexdigest()[:8], 16))
    w = (ism_toliq or "").split()
    U = f"{(w[1] if len(w) > 1 else (w[0] if w else 'Hurmatli'))} ustoz"
    sinf = sinf_of(matn)
    ti = tier(nth)

    def pick(key, items):
        opts = [(f"{key}{i}", s) for i, s in enumerate(items)]
        fresh = [o for o in opts if o[0] not in used] or opts
        k, s = rnd.choice(fresh)
        used.add(k)
        return k, s

    keys = []
    kir = [s for s in KIRISH[ti] if "{sinf}" not in s or sinf]
    k, s = pick(f"k{ti}.", kir); keys.append(k)
    parts = [s.format(U=U, sinf=sinf, n=nth)]
    mz = mavzular(matn)
    top = mz[:4]
    rnd.shuffle(top)
    tanlangan = sorted(top[:2], key=lambda x: [m[0] for m in mz].index(x[0]))
    for mk, gaps in tanlangan:
        k, s = pick(f"m.{mk}.", gaps); keys.append(k); parts.append(s)
    if len(tanlangan) < 2 or rnd.random() < 0.3:
        parts.append(fan_gap(fan_text, matn))
    k, s = pick(f"x{ti}.", XOTIMA[ti]); keys.append(k); parts.append(s)
    imzo = IMZO[rnd.randrange(len(IMZO))]
    return " ".join(parts), imzo, keys
