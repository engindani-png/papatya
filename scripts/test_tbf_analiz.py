#!/usr/bin/env python3
"""tbf_analiz testleri.  Calistirma:  python -m unittest scripts.test_tbf_analiz"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tbf_analiz as A  # noqa: E402


def olay(q, saat, skor, ev, no="", action="", ad=""):
    return {"quarterNumber": q, "time": saat, "score": skor, "isHome": ev,
            "jerseyNumber": no, "action": action, "playerName": ad}


class SureTest(unittest.TestCase):
    def test_geri_sayan_saat_gecen_sureye_cevrilir(self):
        self.assertEqual(A.sure_saniye(1, "10:00"), 0)
        self.assertEqual(A.sure_saniye(1, "09:00"), 60)
        self.assertEqual(A.sure_saniye(2, "10:00"), 600)
        self.assertEqual(A.sure_saniye(3, "07:18"), 1200 + 162)

    def test_bozuk_saat_cokmez(self):
        self.assertEqual(A.sure_saniye(1, None), 0)
        self.assertEqual(A.sure_saniye(None, "abc"), 0)


class AtisTest(unittest.TestCase):
    def test_ikinci_yari_aynalanir(self):
        atislar = [
            {"x": 10, "y": 50, "period": 1, "isSucceed": True, "isHome": True, "jerseyNumber": "2"},
            {"x": 88, "y": 50, "period": 3, "isSucceed": False, "isHome": True, "jerseyNumber": "5"},
        ]
        out = A.atislari_topla(atislar, bizim_ev=True)
        self.assertEqual(out[0], [10, 50, 1, 1, "2"])
        self.assertEqual(out[1], [12, 50, 3, 0, "5"])     # 100 - 88

    def test_rakip_atislari_alinmaz(self):
        atislar = [{"x": 10, "y": 50, "period": 1, "isSucceed": True, "isHome": False,
                    "jerseyNumber": "9"}]
        self.assertEqual(A.atislari_topla(atislar, bizim_ev=True), [])

    def test_deplasmanda_kendi_atislarimiz(self):
        atislar = [{"x": 90, "y": 40, "period": 1, "isSucceed": True, "isHome": False,
                    "jerseyNumber": "7"}]
        self.assertEqual(A.atislari_topla(atislar, bizim_ev=False), [[90, 40, 1, 1, "7"]])


class AkisTest(unittest.TestCase):
    def test_skor_akisi_ev_sahibiyken(self):
        ev = [olay(1, "10:00", "0-0", None),
              olay(1, "09:00", "2-0", True, "2", "2 Sayı Turnike Başarılı"),
              olay(1, "08:00", "2-3", False, "9", "3 Sayı Sıçrayarak Atış Başarılı")]
        c = A.akisi_coz(ev, bizim_ev=True)
        self.assertEqual(c["flow"], [[0, 0, 0], [60, 2, 0], [120, 2, 3]])

    def test_skor_akisi_deplasmandayken_ters_cevrilir(self):
        ev = [olay(1, "10:00", "0-0", None),
              olay(1, "09:00", "2-0", True, "9", "2 Sayı Turnike Başarılı")]
        c = A.akisi_coz(ev, bizim_ev=False)
        self.assertEqual(c["flow"][-1], [60, 0, 2])

    def test_top_kaybi_sebebe_gore_ayrilir(self):
        ev = [olay(1, "09:00", "0-0", True, "2", "Top Kaybı - Kötü Pas"),
              olay(1, "08:00", "0-0", True, "5", "Top Kaybı - Kötü Pas"),
              olay(1, "07:00", "0-0", True, "5", "Top Kaybı - 24 Saniye"),
              olay(1, "06:00", "0-0", False, "9", "Top Kaybı - Kötü Pas")]
        c = A.akisi_coz(ev, bizim_ev=True)
        self.assertEqual(c["turnovers"], {"Kötü Pas": 2, "24 Saniye": 1})

    def test_sut_tipleri_gruplanir(self):
        ev = [olay(1, "09:00", "0-0", True, "2", "2 Sayı Turnike Başarılı"),
              olay(1, "08:00", "0-0", True, "2", "2 Sayı Turnike Başarısız"),
              olay(1, "07:00", "0-0", True, "5", "3 Sayı Sıçrayarak Atış Başarılı"),
              olay(1, "06:00", "0-0", True, "5", "Serbest Atış 1/2 Başarısız")]
        c = A.akisi_coz(ev, bizim_ev=True)
        self.assertEqual(c["shotTypes"]["Turnike"], [1, 2])
        self.assertEqual(c["shotTypes"]["Üçlük"], [1, 1])
        self.assertEqual(c["shotTypes"]["Serbest atış"], [0, 1])

    def test_oyuncu_suresi_degisikliklerden_hesaplanir(self):
        ev = [olay(1, "10:00", "0-0", None),
              olay(1, "08:00", "0-0", True, "2", "Değişiklik Çıkan"),    # ilk beste basladi
              olay(1, "08:00", "0-0", True, "7", "Değişiklik Giren"),
              olay(1, "06:00", "0-0", True, "7", "Değişiklik Çıkan")]
        c = A.akisi_coz(ev, bizim_ev=True)
        self.assertEqual(c["players"]["2"]["sec"], 120)   # 0 -> 2. dakika
        self.assertEqual(c["players"]["7"]["sec"], 120)   # 2 -> 4. dakika

    def test_arti_eksi_sahadakilere_yazilir(self):
        ev = [olay(1, "10:00", "0-0", None),
              olay(1, "09:30", "0-0", True, "7", "Değişiklik Giren"),
              olay(1, "09:00", "2-0", True, "7", "2 Sayı Turnike Başarılı"),
              olay(1, "08:30", "2-3", False, "9", "3 Sayı Sıçrayarak Atış Başarılı"),
              olay(1, "08:00", "2-3", True, "7", "Değişiklik Çıkan")]
        c = A.akisi_coz(ev, bizim_ev=True)
        self.assertEqual(c["players"]["7"]["pm"], -1)     # +2 sonra -3

    def test_en_uzun_seri_yakalanir(self):
        ev = [olay(1, "10:00", "0-0", None),
              olay(1, "09:00", "2-0", True, "2", "2 Sayı Turnike Başarılı"),
              olay(1, "08:00", "5-0", True, "5", "3 Sayı Sıçrayarak Atış Başarılı"),
              olay(1, "07:00", "5-2", False, "9", "2 Sayı Turnike Başarılı"),
              olay(1, "06:00", "7-2", True, "2", "2 Sayı Turnike Başarılı")]
        c = A.akisi_coz(ev, bizim_ev=True)
        self.assertEqual(c["run"][0], 5)


class TakimTest(unittest.TestCase):
    RAPOR = {"sY_A": 67, "s20_A": 27, "s21_A": 84, "s30_A": 2, "s31_A": 10,
             "sA0_A": 7, "sA1_A": 17, "tR_A": 63, "hR_A": 27, "sR_A": 36,
             "aS_A": 15, "tC_A": 36, "bL_A": 8, "tK_A": 33, "fA_A": 6,
             "sY_B": 38, "s20_B": 15, "s21_B": 70, "s30_B": 1, "s31_B": 8,
             "sA0_B": 5, "sA1_B": 12, "tR_B": 45, "hR_B": 18, "sR_B": 27,
             "aS_B": 9, "tC_B": 20, "bL_B": 3, "tK_B": 40, "fA_B": 9}

    def test_ev_sahibiyken_A_bizimdir(self):
        o = A.takim_ozeti(self.RAPOR, bizim_ev=True)
        self.assertEqual(o["biz"]["sayi"], 67)
        self.assertEqual(o["biz"]["iki"], [27, 84])
        self.assertEqual(o["rakip"]["sayi"], 38)

    def test_deplasmandayken_B_bizimdir(self):
        o = A.takim_ozeti(self.RAPOR, bizim_ev=False)
        self.assertEqual(o["biz"]["sayi"], 38)
        self.assertEqual(o["rakip"]["sayi"], 67)

    def test_eksik_alan_none_doner(self):
        o = A.takim_ozeti({"sY_A": "67"}, bizim_ev=True)
        self.assertEqual(o["biz"]["sayi"], 67)
        self.assertIsNone(o["biz"]["asist"])


if __name__ == "__main__":
    unittest.main()
