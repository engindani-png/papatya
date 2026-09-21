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

    def test_ek_yoksa_ekli_takima_eslesmez(self):
        # (A)/(B) KATI kisit: eksiz ad ekli ada baglanmamali.
        h = dp.takim_haritasi(["GALATASARAY"], ["GALATASARAY (A)"])
        self.assertEqual(h, {})

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
