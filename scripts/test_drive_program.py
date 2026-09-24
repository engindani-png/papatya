#!/usr/bin/env python3
"""drive_program testleri - ag ERISIMI YOK, hepsi yerel veriyle.

Calistir:  python3 scripts/test_drive_program.py
"""

from __future__ import annotations

import datetime as dt
import io
import pathlib
import sys
import unittest
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import drive_program as dp  # noqa: E402


# ----------------------------------------------------------------- hafta adlari

class HaftaAdi(unittest.TestCase):
    def test_ayni_ay(self):
        self.assertEqual(dp.hafta_araligi("4.HAFTA_(21-27 EYLÜL 2026)"),
                         (4, dt.date(2026, 9, 21), dt.date(2026, 9, 27)))

    def test_ay_atlayan(self):
        self.assertEqual(dp.hafta_araligi("5.HAFTA_(28 EYLÜL-4 EKİM 2026)"),
                         (5, dt.date(2026, 9, 28), dt.date(2026, 10, 4)))

    def test_yil_atlayan_iki_yil_yazili(self):
        # Yil rakamlari gun ayristiricisina takiliyordu (2026 -> 20 + 26).
        self.assertEqual(dp.hafta_araligi("14.HAFTA_(28 ARALIK 2026-3 OCAK 2027)"),
                         (14, dt.date(2026, 12, 28), dt.date(2027, 1, 3)))

    def test_yil_atlayan_tek_yil_yazili(self):
        self.assertEqual(dp.hafta_araligi("14.HAFTA_(28 ARALIK-3 OCAK 2026)"),
                         (14, dt.date(2026, 12, 28), dt.date(2027, 1, 3)))

    def test_bosluklu_ve_noktasiz(self):
        self.assertEqual(dp.hafta_araligi("7 . HAFTA _ (12-18 EKİM 2026)"),
                         (7, dt.date(2026, 10, 12), dt.date(2026, 10, 18)))

    def test_hafta_olmayanlar(self):
        for ad in ("Arşiv ( Maç Programları )", "Dökümanlar",
                   "CEZA KARARLARI (2025-2026)", "HÜKMEN MAÇLARI ( 2026-2027 )"):
            self.assertIsNone(dp.hafta_araligi(ad), ad)


class HaftaSecimi(unittest.TestCase):
    def kur(self):
        return [{"id": str(n), "ad": ad, "imza": "x"} for n, ad in enumerate([
            "3.HAFTA_(14-20 EYLÜL 2026)",
            "4.HAFTA_(21-27 EYLÜL 2026)",
            "5.HAFTA_(28 EYLÜL-4 EKİM 2026)",
            "Arşiv ( Maç Programları )",
        ])]

    def test_bu_hafta_ve_gelecek(self):
        s = dp.secilecek_haftalar(self.kur(), dt.date(2026, 9, 23), ileri=1)
        self.assertEqual([h["hafta"] for h in s], [4, 5])

    def test_gecmis_hafta_atlanir(self):
        s = dp.secilecek_haftalar(self.kur(), dt.date(2026, 9, 23), ileri=1)
        self.assertNotIn(3, [h["hafta"] for h in s])

    def test_gelecek_hafta_yoksa_tek_dosya(self):
        girisler = [g for g in self.kur() if "5.HAFTA" not in g["ad"]]
        s = dp.secilecek_haftalar(girisler, dt.date(2026, 9, 23), ileri=1)
        self.assertEqual([h["hafta"] for h in s], [4])

    def test_bu_hafta_yayinlanmamissa_en_yakin_gelecekler(self):
        # Sezon arasi: bugunu kapsayan dosya yok.
        s = dp.secilecek_haftalar(self.kur(), dt.date(2026, 9, 10), ileri=1)
        self.assertEqual([h["hafta"] for h in s], [3, 4])

    def test_ileri_sayisi_uygulanir(self):
        s = dp.secilecek_haftalar(self.kur(), dt.date(2026, 9, 23), ileri=0)
        self.assertEqual([h["hafta"] for h in s], [4])


# ------------------------------------------------------------------- takim adlari

class TakimEslestirme(unittest.TestCase):
    TBF = ["EVOLOG DAÇKA ŞERİFALİ", "EYÜPSULTAN BELEDİYESİ", "FENERBAHÇE (A)",
           "FENERBAHÇE (B)", "GALATASARAY (A)", "GALATASARAY (B)",
           "EMLAK KONUT SPOR (A)", "EMLAK KONUT SPOR (B)",
           "ÜMRANİYE BELEDİYESİ SK", "ALLSTARS", "BEŞİKTAŞ", "AÇI OKULLARI"]
    XLS = ["EVOLOG DAÇKA ŞERİFALİ", "EYÜPSULTAN BELEDİYESİ", "FENERBAHÇE (A)",
           "FENERBAHÇE (B)", "GALATASARAY (A)", "GALATASARAY (B)",
           "EMLAK KONUT (A)", "EMLAK KONUT (B)",
           "ÜMRANİYE BLD. S.K", "ALLSTARS İSTANBUL", "BEŞİKTAŞ", "AÇI OKULLARI"]

    def test_hepsi_birebir_eslesir(self):
        h = dp.takim_haritasi(self.XLS, self.TBF)
        self.assertEqual(len(h), 12)
        self.assertEqual(len(set(h.values())), 12, "bir TBF takimi iki kez eslesmis")

    def test_ab_takimlari_karismaz(self):
        h = dp.takim_haritasi(self.XLS, self.TBF)
        self.assertEqual(h["GALATASARAY (A)"], "GALATASARAY (A)")
        self.assertEqual(h["GALATASARAY (B)"], "GALATASARAY (B)")
        self.assertEqual(h["EMLAK KONUT (A)"], "EMLAK KONUT SPOR (A)")
        self.assertEqual(h["EMLAK KONUT (B)"], "EMLAK KONUT SPOR (B)")

    def test_ek_belirsizken_eslesmez(self):
        """(A)/(B) korumasi: iki aday varken ek farki YUTULMAZ.

        Asil tehlike bu. Excel "GALATASARAY" derken TBF'de hem (A) hem (B)
        varsa hangisi oldugu bilinemez; yanlis takima baglanan mac, veliyi
        yanlis salona gonderir. Bilgi vermemek yanlis bilgi vermekten iyidir.
        """
        h = dp.takim_haritasi(["GALATASARAY"],
                              ["GALATASARAY (A)", "GALATASARAY (B)"])
        self.assertEqual(h, {})

    def test_tek_aday_varken_ek_farki_yutulur(self):
        """Ek tek tarafta ve govdeye uyan TEK takim varsa eslesme kurulur.

        Federasyon 5. hafta tablosunda (28 Eylul 2026) bizi
        "EVOLOG DACKA SERIFALI (A)" yazdi, TBF ise eksiz tutuyor. Kati kural
        yuzunden 4 Ekim macinin resmi saati (11:30) ve salonu (BGM C3)
        uygulamaya hic gelmiyordu; veliler TBF'nin dolgu verisini goruyordu.
        """
        h = dp.takim_haritasi(["EVOLOG DAÇKA ŞERİFALİ (A)"],
                              ["EVOLOG DAÇKA ŞERİFALİ"])
        self.assertEqual(h.get("EVOLOG DAÇKA ŞERİFALİ (A)"),
                         "EVOLOG DAÇKA ŞERİFALİ")

    def test_ek_farki_iki_yonde_de_yutulur(self):
        """Eksik ek hangi tarafta olursa olsun, tek aday varsa guvenli."""
        h = dp.takim_haritasi(["GALATASARAY"], ["GALATASARAY (A)"])
        self.assertEqual(h.get("GALATASARAY"), "GALATASARAY (A)")

    def test_gercek_lig_tablosunda_ekli_adimiz_dogru_baglanir(self):
        """Tam lig listesiyle: (A) ekli adimiz dogru baglanmali VE
        EMLAK KONUT / GALATASARAY A-B ayrimi bozulmamali."""
        xls = list(self.XLS)
        xls[xls.index("EVOLOG DAÇKA ŞERİFALİ")] = "EVOLOG DAÇKA ŞERİFALİ (A)"
        h = dp.takim_haritasi(xls, self.TBF)
        self.assertEqual(h.get("EVOLOG DAÇKA ŞERİFALİ (A)"), "EVOLOG DAÇKA ŞERİFALİ")
        self.assertEqual(h["GALATASARAY (A)"], "GALATASARAY (A)")
        self.assertEqual(h["GALATASARAY (B)"], "GALATASARAY (B)")
        self.assertEqual(h["EMLAK KONUT (A)"], "EMLAK KONUT SPOR (A)")
        self.assertEqual(h["EMLAK KONUT (B)"], "EMLAK KONUT SPOR (B)")
        self.assertEqual(len(set(h.values())), len(h), "bir TBF takimi iki kez eslesmis")

    def test_kademe1_kademe0in_adayini_calamaz(self):
        """Ek farkiyla kurulan eslesme, birebir ek tutan eslesmeyi bozmamali."""
        h = dp.takim_haritasi(["FENERBAHÇE", "FENERBAHÇE (A)"],
                              ["FENERBAHÇE (A)"])
        self.assertEqual(h.get("FENERBAHÇE (A)"), "FENERBAHÇE (A)")
        self.assertIsNone(h.get("FENERBAHÇE"), "tek TBF takimi iki kez eslesemez")

    def test_kulup_eki_farkliligi(self):
        h = dp.takim_haritasi(["ŞERİFALİ SPOR KULÜBÜ"], ["EVOLOG DAÇKA ŞERİFALİ"])
        self.assertEqual(h.get("ŞERİFALİ SPOR KULÜBÜ"), "EVOLOG DAÇKA ŞERİFALİ")

    def test_alakasiz_ad_eslesmez(self):
        h = dp.takim_haritasi(["TOFAŞ"], ["EVOLOG DAÇKA ŞERİFALİ"])
        self.assertEqual(h, {})


# ------------------------------------------------------------------------- xlsx

def _xlsx(satirlar: list[list[str]]) -> bytes:
    """Test icin en yalin xlsx: her hucre inlineStr."""
    def hucre(r, c, v):
        ref = ""
        n = c + 1
        while n:
            n, k = divmod(n - 1, 26)
            ref = chr(65 + k) + ref
        v = (v.replace("&", "&amp;").replace("<", "&lt;"))
        return f'<c r="{ref}{r}" t="inlineStr"><is><t>{v}</t></is></c>'

    govde = "".join(
        f'<row r="{i+1}">' + "".join(hucre(i + 1, j, str(v)) for j, v in enumerate(satir)) + "</row>"
        for i, satir in enumerate(satirlar))
    sheet = ('<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/'
             f'spreadsheetml/2006/main"><sheetData>{govde}</sheetData></worksheet>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


BASLIK = ["TARİH", "SALON", "SAAT", "A TAKIMI", "B TAKIMI", "KATEGORİ", "GRUP"]


class BizimMacimizTest(unittest.TestCase):
    """"Bu satir bizim macimiz mi?" sorusu (A)/(B) ekinden etkilenmemeli.

    TBF lig geneli akisi 23 Eylul 2026'da bizi "EVOLOG DACKA SERIFALI (A)"
    yazmaya basladi; takimin kendi fikstur listesi eksiz tutuyor. Ek dahil
    karsilastirildigi icin butun satirlarimiz SESSIZCE "bizim degil" sayildi:
    ne eslesme kuruldu ne de uyari dustu. Federasyonun resmi programi
    hicbir maca uygulanmadi.
    """

    BIZ = ["EVOLOG DAÇKA ŞERİFALİ", "DAÇKA ŞERİFALİ", "EVOLOG"]
    FIX = [{"matchId": 500, "date": "2026-10-04",
            "home": "EVOLOG DAÇKA ŞERİFALİ (A)", "away": "EMLAK KONUT SPOR (B)"}]
    SATIR = [{"tarih": "2026-10-04", "saat": "11:30", "salon": "BGM SALON C3",
              "ev": "EVOLOG DAÇKA ŞERİFALİ (A)", "deplasman": "EMLAK KONUT (B)",
              "grup": "SERİ A"}]

    def test_tbf_ekli_yazsa_da_bizim_macimiz(self):
        sonuc, esle = dp.maclari_eslestir(self.SATIR, self.FIX, self.BIZ)
        self.assertEqual(esle, [])
        self.assertIn("500", sonuc)
        self.assertEqual(sonuc["500"]["venue"], "BGM SALON C3")
        self.assertEqual(sonuc["500"]["time"], "11:30")

    def test_excel_eksiz_tbf_ekliyken_de_bulunur(self):
        satir = [dict(self.SATIR[0], ev="EVOLOG DAÇKA ŞERİFALİ")]
        sonuc, esle = dp.maclari_eslestir(satir, self.FIX, self.BIZ)
        self.assertIn("500", sonuc, f"eslesmedi: {esle}")

    ADIMIZIN_HALLERI = [
        "EVOLOG DAÇKA ŞERİFALİ", "EVOLOG DAÇKA ŞERİFALİ (A)",
        "ŞERİFALİ SPOR KULÜBÜ", "ŞERİFALİ SPOR", "ŞERİFALİ",
        "EVOLOG ŞERİFALİ", "EVOLOG", "DAÇKA ŞERİFALİ",
    ]

    def test_adimizin_butun_halleri_bizim_sayilir(self):
        """Ad her yerde ayni yazilmiyor ve zaman icinde degisiyor.

        TBF takim fiksturu "EVOLOG DAÇKA ŞERİFALİ", lig geneli akisi
        "... (A)", Drive tablosu haftadan haftaya baska bir hali yazabiliyor.
        U14A kiz liginde bu kelimeleri tasiyan baska takim yok; genis
        davranmak guvenli.
        """
        bizim = {dp._govde_anahtari(b) for b in self.BIZ}
        for ad in self.ADIMIZIN_HALLERI:
            self.assertTrue(dp._bizim_mi(ad, bizim), f"bizim sayilmali: {ad}")

    def test_ligdeki_diger_takimlar_bizim_sayilmaz(self):
        bizim = {dp._govde_anahtari(b) for b in self.BIZ}
        for ad in ["GALATASARAY (A)", "FENERBAHÇE (B)", "BEŞİKTAŞ",
                   "EMLAK KONUT SPOR (A)", "EYÜPSULTAN BELEDİYESİ",
                   "ÜMRANİYE BELEDİYESİ SK", "ALLSTARS", "AÇI OKULLARI"]:
            self.assertFalse(dp._bizim_mi(ad, bizim), f"bizim sayilmamali: {ad}")

    def test_bos_ad_bizim_sayilmaz(self):
        bizim = {dp._govde_anahtari(b) for b in self.BIZ}
        for ad in ["", "   ", "(A)"]:
            self.assertFalse(dp._bizim_mi(ad, bizim), repr(ad))

    def test_baskasinin_maci_bizim_sayilmaz(self):
        satir = [{"tarih": "2026-10-04", "saat": "11:30", "salon": "X",
                  "ev": "GALATASARAY (A)", "deplasman": "BEŞİKTAŞ", "grup": "A"}]
        fix = [{"matchId": 501, "date": "2026-10-04",
                "home": "GALATASARAY (A)", "away": "BEŞİKTAŞ"}]
        sonuc, esle = dp.maclari_eslestir(satir, fix, self.BIZ)
        self.assertEqual(sonuc, {}, "baskasinin maci kaydedilmemeli")
        self.assertEqual(esle, [], "baskasinin maci uyari da uretmemeli")

    def test_tbf_tarihi_aylarca_uzaksa_da_drive_kazanir(self):
        """TBF dolgu tarih donuyor; +-10 gun penceresi resmi programi
        reddediyordu (4 Ekim maci TBF'de 8 Aralik goruluyordu)."""
        fix = [{"matchId": 502, "date": "2026-12-08",
                "home": "EVOLOG DAÇKA ŞERİFALİ (A)", "away": "EMLAK KONUT SPOR (B)"}]
        sonuc, esle = dp.maclari_eslestir(self.SATIR, fix, self.BIZ)
        self.assertIn("502", sonuc, f"eslesmedi: {esle}")
        self.assertEqual(sonuc["502"]["date"], "2026-10-04", "Drive tarihi kazanmali")


class XlsxOkuma(unittest.TestCase):
    def test_kategori_suzulur(self):
        veri = _xlsx([BASLIK,
                      ["2026-09-23", "C3", "20:00", "EYÜPSULTAN BELEDİYESİ",
                       "EVOLOG DAÇKA ŞERİFALİ", "U14KA", "SERİ A"],
                      ["2026-09-23", "C2", "18:00", "BEŞİKTAŞ", "FENERBAHÇE (A)",
                       "U16KA", "SERİ A"]])
        satirlar = dp.program_satirlari(veri, "U14KA")
        self.assertEqual(len(satirlar), 1)
        self.assertEqual(satirlar[0]["salon"], "C3")

    def test_eksik_sutun_hata_verir(self):
        veri = _xlsx([["TARİH", "SALON"], ["2026-09-23", "C3"]])
        with self.assertRaises(ValueError):
            dp.program_satirlari(veri, "U14KA")

    def test_excel_seri_tarihi_cevrilir(self):
        # 2026-09-23 -> 1899-12-30 tabanli seri
        seri = (dt.date(2026, 9, 23) - dt.date(1899, 12, 30)).days
        self.assertEqual(dp._tarih(str(seri)), "2026-09-23")

    def test_excel_saat_kesri_cevrilir(self):
        self.assertEqual(dp._saat(str(20 / 24)), "20:00")
        self.assertEqual(dp._saat(str(18.5 / 24)), "18:30")

    def test_metin_tarih_ve_saat_korunur(self):
        self.assertEqual(dp._tarih("2026-09-23 00:00:00"), "2026-09-23")
        self.assertEqual(dp._saat("9:05"), "09:05")


# -------------------------------------------------------------------- birlestirme

FIXTURES = [
    {"matchId": 346858, "date": "2026-09-23", "time": "20:00",
     "home": "EYÜPSULTAN BELEDİYESİ", "away": "EVOLOG DAÇKA ŞERİFALİ"},
    {"matchId": 346867, "date": "2026-09-25", "time": "18:30",
     "home": "EVOLOG DAÇKA ŞERİFALİ", "away": "EMLAK KONUT SPOR (B)"},
    # Ayni rakiple ikinci devre - tarih penceresi bunu ayirt etmeli.
    {"matchId": 349900, "date": "2027-01-15", "time": "18:30",
     "home": "EVOLOG DAÇKA ŞERİFALİ", "away": "EYÜPSULTAN BELEDİYESİ"},
    {"matchId": 346860, "date": "2026-09-24", "time": "20:00",
     "home": "GALATASARAY (A)", "away": "BEŞİKTAŞ"},
]
BIZIM = ["EVOLOG DAÇKA ŞERİFALİ", "DAÇKA ŞERİFALİ"]


class Birlestirme(unittest.TestCase):
    def test_bizim_mac_bulunur_salon_gelir(self):
        program = [{"tarih": "2026-09-23", "saat": "20:00",
                    "salon": "BGM ÜLKER ÇİZİ SALONU (C3)",
                    "ev": "EYÜPSULTAN BELEDİYESİ", "deplasman": "EVOLOG DAÇKA ŞERİFALİ",
                    "grup": "SERİ A"}]
        maclar, eslesmeyen = dp.maclari_eslestir(program, FIXTURES, BIZIM)
        self.assertEqual(eslesmeyen, [])
        self.assertEqual(maclar["346858"],
                         {"date": "2026-09-23", "time": "20:00",
                          "venue": "BGM ÜLKER ÇİZİ SALONU (C3)", "source": "drive"})

    def test_bizim_olmayan_mac_alinmaz(self):
        program = [{"tarih": "2026-09-24", "saat": "20:00", "salon": "C3",
                    "ev": "GALATASARAY (A)", "deplasman": "BEŞİKTAŞ", "grup": "SERİ A"}]
        maclar, _ = dp.maclari_eslestir(program, FIXTURES, BIZIM)
        self.assertEqual(maclar, {})

    def test_ikinci_devre_karismaz(self):
        # Ayni eslesme, ocak ayinda: 346858 degil 349900 secilmeli.
        program = [{"tarih": "2027-01-15", "saat": "19:00", "salon": "C2",
                    "ev": "EVOLOG DAÇKA ŞERİFALİ", "deplasman": "EYÜPSULTAN BELEDİYESİ",
                    "grup": "SERİ A"}]
        maclar, _ = dp.maclari_eslestir(program, FIXTURES, BIZIM)
        self.assertEqual(list(maclar), ["349900"])

    def test_saat_degisikligi_yansir(self):
        program = [{"tarih": "2026-09-23", "saat": "18:00", "salon": "C3",
                    "ev": "EYÜPSULTAN BELEDİYESİ", "deplasman": "EVOLOG DAÇKA ŞERİFALİ",
                    "grup": "SERİ A"}]
        maclar, _ = dp.maclari_eslestir(program, FIXTURES, BIZIM)
        self.assertEqual(maclar["346858"]["time"], "18:00")

    def test_tbf_de_olmayan_mac_uyari_olur(self):
        program = [{"tarih": "2026-09-23", "saat": "20:00", "salon": "C3",
                    "ev": "EVOLOG DAÇKA ŞERİFALİ", "deplasman": "BEŞİKTAŞ",
                    "grup": "SERİ A"}]
        maclar, eslesmeyen = dp.maclari_eslestir(program, FIXTURES, BIZIM)
        self.assertEqual(maclar, {})
        self.assertEqual(len(eslesmeyen), 1)
        self.assertIn("TBF", eslesmeyen[0]["neden"])


# -------------------------------------------------------------------- klasor HTML

KLASOR_HTML = """
<div class="flip-entry" id="entry-AAA"><div class="flip-entry-info">
<div class="flip-entry-title">3.HAFTA_(14-20 EYLÜL 2026)</div>
<div class="flip-entry-last-modified"><div>Sep 19</div></div></div></div>
<div class="flip-entry" id="entry-BBB"><div class="flip-entry-info">
<div class="flip-entry-title">4.HAFTA_(21-27 EYLÜL 2026)</div>
<div class="flip-entry-last-modified"><div>5:33&#8239;am</div></div></div></div>
"""


class KlasorAyristirma(unittest.TestCase):
    def test_giris_ve_imza_okunur(self):
        g = dp.klasor_girisleri(KLASOR_HTML)
        self.assertEqual(len(g), 2)
        self.assertEqual(g[0]["id"], "AAA")
        self.assertEqual(g[1]["ad"], "4.HAFTA_(21-27 EYLÜL 2026)")
        self.assertEqual(g[0]["imza"], "Sep 19")

    def test_bos_html_bos_liste(self):
        self.assertEqual(dp.klasor_girisleri("<html></html>"), [])


# ------------------------------------------------------------------------ akis

class Akis(unittest.TestCase):
    """guncelle(): ag cagrilari yamalanir, karar mantigi sinanir."""

    def kur(self, indirilen: list):
        cfg = {"folderId": "F", "category": "U14KA", "weeksAhead": 0,
               "teamNames": BIZIM}
        program = [BASLIK, ["2026-09-23", "BGM ÜLKER ÇİZİ SALONU (C3)", "20:00",
                            "EYÜPSULTAN BELEDİYESİ", "EVOLOG DAÇKA ŞERİFALİ",
                            "U14KA", "SERİ A"]]
        dp.klasor_html = lambda *a, **k: KLASOR_HTML
        def indir(fid):
            indirilen.append(fid)
            return _xlsx(program)
        dp.sheet_indir = indir
        return cfg

    def setUp(self):
        self._html, self._indir = dp.klasor_html, dp.sheet_indir

    def tearDown(self):
        dp.klasor_html, dp.sheet_indir = self._html, self._indir

    def test_ilk_calismada_indirir(self):
        ind = []
        cfg = self.kur(ind)
        d = dp.guncelle(cfg, FIXTURES, None, bugun=dt.date(2026, 9, 23), gunluk=lambda *_: None)
        self.assertEqual(ind, ["BBB"])
        self.assertEqual(d["matches"]["346858"]["venue"], "BGM ÜLKER ÇİZİ SALONU (C3)")
        self.assertTrue(d["changed"])

    def test_imza_ayniysa_indirmez(self):
        ind = []
        cfg = self.kur(ind)
        d1 = dp.guncelle(cfg, FIXTURES, None, bugun=dt.date(2026, 9, 23), gunluk=lambda *_: None)
        ind.clear()
        d2 = dp.guncelle(cfg, FIXTURES, d1, bugun=dt.date(2026, 9, 23), gunluk=lambda *_: None)
        self.assertEqual(ind, [], "imza degismedigi halde indirdi")
        self.assertEqual(d2["matches"], d1["matches"])

    def test_imza_degisince_indirir(self):
        ind = []
        cfg = self.kur(ind)
        d1 = dp.guncelle(cfg, FIXTURES, None, bugun=dt.date(2026, 9, 23), gunluk=lambda *_: None)
        d1["files"]["BBB"]["imza"] = "BASKA"
        ind.clear()
        dp.guncelle(cfg, FIXTURES, d1, bugun=dt.date(2026, 9, 23), gunluk=lambda *_: None)
        self.assertEqual(ind, ["BBB"])

    def test_gunluk_dogrulama_imza_ayni_olsa_da_indirir(self):
        ind = []
        cfg = self.kur(ind)
        d1 = dp.guncelle(cfg, FIXTURES, None, bugun=dt.date(2026, 9, 23), gunluk=lambda *_: None)
        eski = (dt.datetime.now(dp.TZ) - dt.timedelta(hours=dp.TAZELEME_SAATI + 1))
        d1["files"]["BBB"]["indirildi"] = eski.isoformat(timespec="seconds")
        ind.clear()
        dp.guncelle(cfg, FIXTURES, d1, bugun=dt.date(2026, 9, 23), gunluk=lambda *_: None)
        self.assertEqual(ind, ["BBB"], "gunluk dogrulama calismadi")

    def test_klasor_okunamazsa_onceki_korunur(self):
        ind = []
        cfg = self.kur(ind)
        d1 = dp.guncelle(cfg, FIXTURES, None, bugun=dt.date(2026, 9, 23), gunluk=lambda *_: None)
        def patla(*a, **k):
            raise OSError("ag yok")
        dp.klasor_html = patla
        d2 = dp.guncelle(cfg, FIXTURES, d1, bugun=dt.date(2026, 9, 23), gunluk=lambda *_: None)
        self.assertEqual(d2["matches"], d1["matches"])

    def test_indirme_patlarsa_onceki_korunur(self):
        ind = []
        cfg = self.kur(ind)
        d1 = dp.guncelle(cfg, FIXTURES, None, bugun=dt.date(2026, 9, 23), gunluk=lambda *_: None)
        d1["files"]["BBB"]["imza"] = "BASKA"          # indirmeye zorla
        def patla(*a, **k):
            raise OSError("indirilemedi")
        dp.sheet_indir = patla
        d2 = dp.guncelle(cfg, FIXTURES, d1, bugun=dt.date(2026, 9, 23), gunluk=lambda *_: None)
        self.assertEqual(d2["matches"], d1["matches"])

    def test_bozuk_dosya_onceki_veriyi_silmez(self):
        ind = []
        cfg = self.kur(ind)
        d1 = dp.guncelle(cfg, FIXTURES, None, bugun=dt.date(2026, 9, 23), gunluk=lambda *_: None)
        d1["files"]["BBB"]["imza"] = "BASKA"
        dp.sheet_indir = lambda fid: _xlsx([["ALAKASIZ"], ["x"]])
        d2 = dp.guncelle(cfg, FIXTURES, d1, bugun=dt.date(2026, 9, 23), gunluk=lambda *_: None)
        self.assertEqual(d2["matches"], d1["matches"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
