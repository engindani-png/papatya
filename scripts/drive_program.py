#!/usr/bin/env python3
"""Federasyonun Google Drive'daki haftalik mac programi (resmi kaynak).

NEDEN: TBF'nin fikstur servisi ilan edilmemis maclar icin dolgu tarih donuyor
(bkz. local_edits.detect_generated) ve ilan edilmis maclarda bile salon yanlis
kalabiliyor. Istanbul temsilciligi ayni programi her hafta Drive'a Google Sheet
olarak koyuyor; orasi RESMI kaynak. 21 Eylul 2026'da olculdu: TBF 23 Eylul maci
icin "Ulker Go Ahead Salonu (C2)" diyordu, Drive'daki 4. hafta programi ise
"BGM ULKER CIZI SALONU (C3)" - yani veliler yanlis salona gidecekti.

ONCELIK (local_edits.apply icinde uygulanir):
    elle overrides.json  >  BU DOSYA (Drive)  >  TBF API

MALIYET: saat basi yalnizca klasor listesi cekilir (~10 KB). Bir hafta dosyasi
ancak YENIyse ya da degisiklik imzasi degistiyse indirilir (~45 KB).

DEGISIKLIK IMZASI: Drive'in gomulu klasor listesi mutlak zaman damgasi vermez,
goreli yazar - bugun degistiyse "5:33 am", bu yil icindeyse "Sep 19", daha
eskiyse "7/29/25". Ustelik ayni dosya baska bir uctan okundugunda baska dilde
ve saat diliminde gorunuyor (gomulu liste "5:33 am" derken klasor sayfasi
"15:33" diyordu - ayni an). Bu yuzden imza TARIH OLARAK YORUMLANMAZ, opak bir
dize gibi "oncekiyle ayni mi" diye karsilastirilir ve HEP AYNI UCTAN okunur.

EMNIYET AGI: imza degismese bile dosya gunde bir kez yine de indirilip
dogrulanir. Sebep: gecmis bir gunun imzasi "Sep 19" olarak donuyor, yani
senkron bir gunden uzun durursa ayni gun icinde yapilmis bir degisiklik
imzadan anlasilmayabilir.

HATA POLITIKASI: hicbir hata senkronu bozmaz. Drive erisilemezse, bicim
degisirse ya da takim adi eslesmezse onceki veri korunur ve durum gunluge
yazilir - uygulama TBF verisiyle calismaya devam eder.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import pathlib
import re
import unicodedata
import urllib.request
import zipfile
from difflib import SequenceMatcher
from xml.etree import ElementTree as ET

TZ = dt.timezone(dt.timedelta(hours=3))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
ZAMAN_ASIMI = 45
# Imza degismese bile bu kadar sonra yine indir (yukaridaki emniyet agi).
TAZELEME_SAATI = 24

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
# Excel'in gun sayaci: seri 1 = 1900-01-01, ama 1900'u artik yil sayan hatasi
# yuzunden taban 1899-12-30 alinir.
EXCEL_EPOK = dt.date(1899, 12, 30)

AYLAR = {
    "OCAK": 1, "SUBAT": 2, "MART": 3, "NISAN": 4, "MAYIS": 5, "HAZIRAN": 6,
    "TEMMUZ": 7, "AGUSTOS": 8, "EYLUL": 9, "EKIM": 10, "KASIM": 11, "ARALIK": 12,
}


# --------------------------------------------------------------------------- ag

def _getir(url: str) -> bytes:
    istek = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI) as yanit:
        return yanit.read()


def klasor_html(klasor_id: str, resource_key: str = "") -> str:
    """Gomulu klasor listesi - anonim erisilebilir, ~10 KB."""
    url = f"https://drive.google.com/embeddedfolderview?id={klasor_id}"
    if resource_key:
        url += f"&resourcekey={resource_key}"
    return _getir(url + "#list").decode("utf-8", "replace")


def sheet_indir(dosya_id: str) -> bytes:
    """Google Sheet'i xlsx olarak disari aktar - anonim erisilebilir."""
    return _getir(f"https://docs.google.com/spreadsheets/d/{dosya_id}/export?format=xlsx")


# ------------------------------------------------------------------ klasor ayristirma

GIRIS_RE = re.compile(
    r'id="entry-([^"]+)".*?flip-entry-title">([^<]*)<'
    r'.*?flip-entry-last-modified"><div>([^<]*)</div>',
    re.S)


def klasor_girisleri(html: str) -> list[dict]:
    """[{id, ad, imza}] - imza opak degisiklik dizesi (bkz. modul basligi)."""
    return [{"id": fid, "ad": ad.strip(), "imza": imza.strip()}
            for fid, ad, imza in GIRIS_RE.findall(html)]


# "4.HAFTA_(21-27 EYLUL 2026)" ve ay atlayan "5.HAFTA_(28 EYLUL-4 EKIM 2026)"
HAFTA_RE = re.compile(r"^\s*(\d+)\s*\.?\s*HAFTA", re.I)


def _harfle(metin: str) -> str:
    """Turkce harfleri sadelestirir; ay adlarini eslestirmek icin."""
    esle = str.maketrans("İIŞĞÜÖÇışğüöç", "IISGUOCisguoc")
    return metin.translate(esle).upper()


def hafta_araligi(ad: str):
    """Dosya adindan (hafta_no, baslangic, bitis) cikarir; degilse None."""
    m = HAFTA_RE.match(ad)
    if not m:
        return None
    no = int(m.group(1))
    icerik = ad[m.end():]
    parantez = re.search(r"\(([^)]*)\)", icerik)
    if not parantez:
        return None
    metin = _harfle(parantez.group(1))
    # Yillari ONCE ayikla: "28 ARALIK 2026-3 OCAK 2027" gibi adlarda yil
    # rakamlari gun ayristiricisina takiliyordu (2026 -> gun 20 + gun 26).
    yillar = [int(y) for y in re.findall(r"\b(20\d{2})\b", metin)]
    if not yillar:
        return None
    metin = re.sub(r"\b20\d{2}\b", " ", metin)

    # Gun ve (varsa) hemen ardindaki ay adini sirayla topla.
    gunler = []
    for gun, ay in re.findall(r"(\d{1,2})\s*([A-Z]+)?", metin):
        g = int(gun)
        if not 1 <= g <= 31:
            continue
        gunler.append((g, AYLAR.get((ay or "").strip())))
    if len(gunler) < 2:
        return None
    (g1, a1), (g2, a2) = gunler[0], gunler[1]
    ay2 = a2 or a1
    ay1 = a1 or ay2
    if not ay1 or not ay2:
        return None

    yil1 = yillar[0]
    # Iki yil yazilmissa ikincisi bitisin yilidir; tek yil varsa Aralik->Ocak
    # gecisinde bitis bir sonraki yila dusuyor demektir.
    yil2 = yillar[-1] if len(yillar) > 1 else yil1 + (1 if ay2 < ay1 else 0)
    try:
        return no, dt.date(yil1, ay1, g1), dt.date(yil2, ay2, g2)
    except ValueError:
        return None


def secilecek_haftalar(girisler: list[dict], bugun: dt.date, ileri: int = 1) -> list[dict]:
    """Bugunu kapsayan hafta + sonraki `ileri` hafta. Gecmis haftalar atlanir.

    Bugunu kapsayan dosya henuz yoksa (ornegin sezon arasi), en yakin gelecek
    haftalardan `ileri`+1 tanesi alinir; boylece 5. hafta yayinlandiginda hic
    beklemeden yakalanir.
    """
    hafta = []
    for g in girisler:
        ar = hafta_araligi(g["ad"])
        if ar:
            no, bas, bit = ar
            hafta.append({**g, "hafta": no, "bas": bas, "bit": bit})
    hafta.sort(key=lambda h: h["bas"])

    guncel = [h for h in hafta if h["bas"] <= bugun <= h["bit"]]
    gelecek = [h for h in hafta if h["bas"] > bugun]
    if guncel:
        return guncel + gelecek[:ileri]
    return gelecek[:ileri + 1]


# ------------------------------------------------------------------- xlsx (stdlib)

def _hucre_degeri(hucre, paylasilan: list[str]) -> str:
    tip = hucre.get("t")
    if tip == "inlineStr":
        return "".join(t.text or "" for t in hucre.iter(f"{NS}t"))
    v = hucre.find(f"{NS}v")
    if v is None or v.text is None:
        return ""
    if tip == "s":
        try:
            return paylasilan[int(v.text)]
        except (ValueError, IndexError):
            return ""
    return v.text


def _sutun(ref: str) -> int:
    """'C12' -> 2 (0 tabanli sutun indeksi)."""
    n = 0
    for ch in ref:
        if not ch.isalpha():
            break
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def xlsx_satirlari(veri: bytes) -> list[list[str]]:
    """Ilk sayfayi satir listesi olarak dondurur; bosluklar korunur.

    openpyxl kullanilmiyor: bu sunucuda sistem geneline pip kurulumu certbot'u
    bozuyor (bkz. proje notlari), stdlib yetiyor.
    """
    with zipfile.ZipFile(io.BytesIO(veri)) as z:
        paylasilan = []
        if "xl/sharedStrings.xml" in z.namelist():
            kok = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in kok.iter(f"{NS}si"):
                paylasilan.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
        sayfalar = sorted(n for n in z.namelist()
                          if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        if not sayfalar:
            return []
        kok = ET.fromstring(z.read(sayfalar[0]))

    satirlar = []
    for row in kok.iter(f"{NS}row"):
        hucreler = {}
        for c in row.findall(f"{NS}c"):
            ref = c.get("r") or ""
            hucreler[_sutun(ref)] = _hucre_degeri(c, paylasilan)
        if not hucreler:
            continue
        genislik = max(hucreler) + 1
        satirlar.append([hucreler.get(i, "") for i in range(genislik)])
    return satirlar


def _tarih(ham: str) -> str:
    """Excel gun sayacini YYYY-MM-DD'ye cevirir; zaten metinse oldugu gibi."""
    ham = (ham or "").strip()
    if not ham:
        return ""
    try:
        seri = float(ham)
    except ValueError:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", ham)
        return m.group(0) if m else ham
    return (EXCEL_EPOK + dt.timedelta(days=int(seri))).isoformat()


def _saat(ham: str) -> str:
    """Excel gun kesrini HH:MM'ye cevirir; zaten metinse sadelestirir."""
    ham = (ham or "").strip()
    if not ham:
        return ""
    try:
        kesir = float(ham)
    except ValueError:
        m = re.match(r"(\d{1,2}):(\d{2})", ham)
        return f"{int(m.group(1)):02d}:{m.group(2)}" if m else ham
    dakika = round((kesir % 1) * 24 * 60)
    return f"{dakika // 60 % 24:02d}:{dakika % 60:02d}"


# Programdaki sutun basliklari (Turkce harfler sadelestirilerek aranir).
BASLIKLAR = {"TARIH": "tarih", "SALON": "salon", "SAAT": "saat",
             "A TAKIMI": "ev", "B TAKIMI": "deplasman",
             "KATEGORI": "kategori", "GRUP": "grup"}


def program_satirlari(veri: bytes, kategori: str) -> list[dict]:
    """xlsx -> [{tarih, saat, salon, ev, deplasman, grup}] (yalniz `kategori`)."""
    satirlar = xlsx_satirlari(veri)
    if not satirlar:
        return []
    basliklar = [_harfle(h).strip() for h in satirlar[0]]
    idx = {}
    for i, h in enumerate(basliklar):
        if h in BASLIKLAR and BASLIKLAR[h] not in idx:
            idx[BASLIKLAR[h]] = i
    for gerekli in ("tarih", "saat", "ev", "deplasman", "kategori"):
        if gerekli not in idx:
            raise ValueError(f"program sutunu bulunamadi: {gerekli} ({basliklar[:8]})")

    kat = _harfle(kategori).strip()
    cikti = []
    for satir in satirlar[1:]:
        def al(ad):
            i = idx.get(ad)
            return satir[i] if i is not None and i < len(satir) else ""
        if _harfle(al("kategori")).strip() != kat:
            continue
        cikti.append({
            "tarih": _tarih(al("tarih")),
            "saat": _saat(al("saat")),
            "salon": (al("salon") or "").strip(),
            "ev": (al("ev") or "").strip(),
            "deplasman": (al("deplasman") or "").strip(),
            "grup": (al("grup") or "").strip(),
        })
    return cikti


# ------------------------------------------------------------------ takim eslestirme

EK_RE = re.compile(r"\(\s*([ABC])\s*\)\s*$", re.I)
GURULTU_RE = re.compile(
    r"\b(SPOR\s+KULUBU|SPOR\s+KULUBU|S\s*K|SK|BLD|BELEDIYESI|BELEDIYE|"
    r"GENCLIK|OKULLARI|BASKETBOL|BASKET|KULUBU|SK\.)\b")


def ek_ayir(ad: str):
    """'GALATASARAY (B)' -> ('GALATASARAY', 'B'). Ek KATI kisittir."""
    m = EK_RE.search(ad.strip())
    govde = EK_RE.sub("", ad).strip()
    return govde, (m.group(1).upper() if m else None)


def normalize(ad: str) -> str:
    a = _harfle(ad)
    a = unicodedata.normalize("NFKD", a).encode("ascii", "ignore").decode()
    a = re.sub(r"[^A-Z0-9 ]", " ", a)
    a = GURULTU_RE.sub(" ", a)
    return re.sub(r"\s+", " ", a).strip()


def benzerlik(a: str, b: str) -> float:
    """Kelime kumesi ortusmesi + dize benzerligi; buyuk olan alinir.

    Kelime kumesi sart: 'EVOLOG DACKA SERIFALI' ile 'SERIFALI SPOR KULUBU'
    dize olarak uzak ama ortak kelime tasiyor.
    """
    na, nb = normalize(a), normalize(b)
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    return max(jaccard, SequenceMatcher(None, na, nb).ratio() * 0.95)


def takim_haritasi(excel_adlari, tbf_adlari, esik: float = 0.45) -> dict:
    """Excel adi -> TBF adi. Birebir atama; (A)/(B) eki birebir tutmak ZORUNDA.

    Tek tek en yakini secmek yerine tum ciftler skora gore siralanip birebir
    atanir; boylece bir TBF takimi iki Excel adina eslesemez.
    """
    ciftler = []
    for x in excel_adlari:
        x_govde, x_ek = ek_ayir(x)
        for t in tbf_adlari:
            t_govde, t_ek = ek_ayir(t)
            if x_ek != t_ek:
                continue                   # KATI: (A)/(B)/yok birebir tutmali
            ciftler.append((benzerlik(x_govde, t_govde), x, t))
    ciftler.sort(key=lambda c: -c[0])

    harita, kullanilan = {}, set()
    for skor, x, t in ciftler:
        if x in harita or t in kullanilan or skor < esik:
            continue
        harita[x] = t
        kullanilan.add(t)
    return harita


# ------------------------------------------------------------------------ birlestirme

def _anahtar(ad: str) -> str:
    govde, ek = ek_ayir(ad)
    return f"{normalize(govde)}|{ek or ''}"


def maclari_eslestir(program: list[dict], fixtures: list[dict], bizim: list[str]) -> tuple[dict, list]:
    """Drive satirlarini TBF matchId'lerine baglar.

    Eslesme olcutu: iki takim da ayni (birebir atanan adlarla) VE macin TBF'deki
    tarihi Drive'daki tarihe 10 gunden yakin. Tarih penceresi sart, cunku ayni
    rakiple sezonda iki kez oynaniyor (ilk ve ikinci devre).
    """
    tbf_adlari = sorted({f["home"] for f in fixtures} | {f["away"] for f in fixtures})
    excel_adlari = sorted({m["ev"] for m in program} | {m["deplasman"] for m in program})
    harita = takim_haritasi(excel_adlari, tbf_adlari)

    bizim_norm = {_anahtar(b) for b in bizim}
    sonuc, eslesmeyen = {}, []

    for m in program:
        ev_t, dep_t = harita.get(m["ev"]), harita.get(m["deplasman"])
        if not ev_t or not dep_t:
            eslesmeyen.append({**m, "neden": "takim adi eslesmedi"})
            continue
        if _anahtar(ev_t) not in bizim_norm and _anahtar(dep_t) not in bizim_norm:
            continue                        # bizim macimiz degil
        aday = None
        for f in fixtures:
            if f.get("home") != ev_t or f.get("away") != dep_t:
                continue
            try:
                fark = abs((dt.date.fromisoformat(f["date"])
                            - dt.date.fromisoformat(m["tarih"])).days)
            except (KeyError, TypeError, ValueError):
                continue
            if fark <= 10 and (aday is None or fark < aday[0]):
                aday = (fark, f)
        if aday is None:
            eslesmeyen.append({**m, "neden": "TBF fiksturunde karsiligi yok"})
            continue
        sonuc[str(aday[1]["matchId"])] = {
            "date": m["tarih"], "time": m["saat"], "venue": m["salon"] or None,
            "source": "drive",
        }
    return sonuc, eslesmeyen


# ----------------------------------------------------------------------------- akis

def _simdi() -> str:
    return dt.datetime.now(TZ).isoformat(timespec="seconds")


def _yasli(zaman: str | None, saat: int = TAZELEME_SAATI) -> bool:
    if not zaman:
        return True
    try:
        t = dt.datetime.fromisoformat(zaman)
    except ValueError:
        return True
    return (dt.datetime.now(TZ) - t) > dt.timedelta(hours=saat)


def guncelle(cfg: dict, fixtures: list[dict], onceki: dict | None,
             bugun: dt.date | None = None, gunluk=print) -> dict:
    """Klasoru yoklar, gerekirse indirir, {matchId: {...}} uretir.

    Donen sozlugun `matches` alani local_edits.apply'a verilir. Hata durumunda
    onceki durum oldugu gibi dondurulur - senkron asla kirilmaz.
    """
    bugun = bugun or dt.datetime.now(TZ).date()
    onceki = onceki or {}
    onceki_dosyalar = onceki.get("files") or {}
    durum = {
        "updatedAt": _simdi(),
        "folder": cfg.get("folderId"),
        "files": dict(onceki_dosyalar),
        "matches": dict(onceki.get("matches") or {}),
        "unmatched": list(onceki.get("unmatched") or []),
        "weeks": [],
    }

    try:
        html = klasor_html(cfg["folderId"], cfg.get("resourceKey", ""))
        girisler = klasor_girisleri(html)
    except Exception as hata:                                  # noqa: BLE001
        gunluk(f"  drive: klasor okunamadi ({hata}) - onceki veri korunuyor")
        return onceki or durum
    if not girisler:
        gunluk("  drive: klasor listesi bos ayristirildi - onceki veri korunuyor")
        return onceki or durum

    secili = secilecek_haftalar(girisler, bugun, int(cfg.get("weeksAhead", 1)))
    if not secili:
        gunluk("  drive: islenecek hafta dosyasi yok")
        return durum

    yeni_maclar, yeni_eslesmeyen, degisen = {}, [], False
    for h in secili:
        durum["weeks"].append({"hafta": h["hafta"], "ad": h["ad"],
                               "bas": h["bas"].isoformat(), "bit": h["bit"].isoformat()})
        onceki_d = onceki_dosyalar.get(h["id"]) or {}
        imza_ayni = onceki_d.get("imza") == h["imza"]
        tazele = _yasli(onceki_d.get("indirildi"))
        if imza_ayni and not tazele and onceki_d.get("matches") is not None:
            gunluk(f"  drive: {h['ad']} degismemis (imza {h['imza']}), indirilmedi")
            yeni_maclar.update(onceki_d["matches"])
            durum["files"][h["id"]] = onceki_d
            continue

        neden = "yeni/degisti" if not imza_ayni else "gunluk dogrulama"
        try:
            veri = sheet_indir(h["id"])
            program = program_satirlari(veri, cfg.get("category", "U14KA"))
        except Exception as hata:                              # noqa: BLE001
            gunluk(f"  drive: {h['ad']} islenemedi ({hata}) - onceki veri korunuyor")
            if onceki_d:
                durum["files"][h["id"]] = onceki_d
                yeni_maclar.update(onceki_d.get("matches") or {})
            continue

        maclar, eslesmeyen = maclari_eslestir(program, fixtures, cfg.get("teamNames", []))
        ozet = hashlib.sha256(
            json.dumps(maclar, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        if ozet != onceki_d.get("ozet"):
            degisen = True
        durum["files"][h["id"]] = {
            "ad": h["ad"], "imza": h["imza"], "indirildi": _simdi(),
            "ozet": ozet, "matches": maclar,
        }
        yeni_maclar.update(maclar)
        yeni_eslesmeyen.extend(eslesmeyen)
        gunluk(f"  drive: {h['ad']} indirildi ({neden}), "
               f"{len(program)} {cfg.get('category','U14KA')} satiri, "
               f"{len(maclar)} macimiz")

    durum["matches"] = yeni_maclar
    durum["unmatched"] = yeni_eslesmeyen
    durum["changed"] = degisen
    # Artik islenmeyen (gecmis) hafta dosyalarini durumdan dusur.
    gecerli = {h["id"] for h in secili}
    durum["files"] = {k: v for k, v in durum["files"].items() if k in gecerli}
    for e in yeni_eslesmeyen:
        gunluk(f"  drive UYARI: {e['neden']} -> {e['ev']} - {e['deplasman']} ({e['tarih']})")
    return durum


def yukle(yol: pathlib.Path) -> dict:
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def yaz(yol: pathlib.Path, durum: dict) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(durum, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
