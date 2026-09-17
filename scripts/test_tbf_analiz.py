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
    def test_ev_sahibinin_ikinci_yarisi_aynalanir(self):
        atislar = [
            {"x": 10, "y": 50, "period": 1, "isSucceed": True, "isHome": True, "jerseyNumber": "2"},
            {"x": 88, "y": 50, "period": 3, "isSucceed": False, "isHome": True, "jerseyNumber": "5"},
        ]
        out = A.atislari_topla(atislar, bizim_ev=True)
        self.assertEqual(out[0], [10, 50, 1, 1, "2"])
        self.assertEqual(out[1], [12, 50, 3, 0, "5"])     # 100 - 88

    def test_deplasmanin_ilk_yarisi_aynalanir(self):
        # Deplasman 1-2. ceyrekte karsi potaya (x~90) atiyor; ayni yari sahaya
        # katlanmali. Ceyrege bakan eski kural bunu kaciriyordu.
        atislar = [
            {"x": 90, "y": 50, "period": 1, "isSucceed": True, "isHome": False, "jerseyNumber": "9"},
            {"x": 12, "y": 50, "period": 4, "isSucceed": False, "isHome": False, "jerseyNumber": "9"},
        ]
        out = A.atislari_topla(atislar, bizim_ev=False)
        self.assertEqual(out[0][0], 10)
        self.assertEqual(out[1][0], 12)

    def test_normalize_edilen_x_her_zaman_yari_sahada(self):
        atislar = [{"x": v, "y": 50, "period": 1, "isSucceed": True, "isHome": True,
                    "jerseyNumber": "2"} for v in (1, 30, 51, 98)]
        for satir in A.atislari_topla(atislar, bizim_ev=True):
            self.assertLessEqual(satir[0], 50)

    def test_rakip_atislari_alinmaz(self):
        atislar = [{"x": 10, "y": 50, "period": 1, "isSucceed": True, "isHome": False,
                    "jerseyNumber": "9"}]
        self.assertEqual(A.atislari_topla(atislar, bizim_ev=True), [])

    def test_deplasmanda_kendi_atislarimiz(self):
        atislar = [{"x": 90, "y": 40, "period": 1, "isSucceed": True, "isHome": False,
                    "jerseyNumber": "7"}]
        # x=90 aynalanir: her iki takimin atisi da ayni yari sahaya oturur.
        self.assertEqual(A.atislari_topla(atislar, bizim_ev=False), [[10, 40, 1, 1, "7"]])


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


class NotrTest(unittest.TestCase):
    """Notr bicim: ligdeki her mac ayni dosyada, taraf secimi okuyanda."""

    FIX = {"matchId": 1, "date": "2026-09-14", "home": "EVOLOG", "away": "GALATASARAY",
           "homeScore": 67, "awayScore": 38, "quarters": [{"home": 12, "away": 9}]}
    ATIS = [{"x": 10, "y": 50, "period": 1, "isSucceed": True, "isHome": True, "jerseyNumber": "2"},
            {"x": 90, "y": 50, "period": 1, "isSucceed": False, "isHome": False, "jerseyNumber": "9"}]
    OLAY = [olay(1, "10:00", "0-0", None),
            olay(1, "09:00", "2-0", True, "2", "2 Sayı Turnike Başarılı"),
            olay(1, "08:00", "2-3", False, "9", "3 Sayı Sıçrayarak Atış Başarılı"),
            olay(1, "07:00", "2-3", False, "9", "Top Kaybı - Kötü Pas")]

    def test_iki_takimin_atislari_ayri_durur(self):
        a = A.mac_analizi_notr(self.FIX, self.ATIS, self.OLAY, TakimTest.RAPOR)
        self.assertEqual(len(a["shots"]["home"]), 1)
        self.assertEqual(len(a["shots"]["away"]), 1)

    def test_akis_ev_deplasman_sirasinda(self):
        a = A.mac_analizi_notr(self.FIX, self.ATIS, self.OLAY, TakimTest.RAPOR)
        self.assertEqual(a["flow"][-1], [120, 2, 3])

    def test_rakibin_top_kaybi_kendi_tarafinda(self):
        a = A.mac_analizi_notr(self.FIX, self.ATIS, self.OLAY, TakimTest.RAPOR)
        self.assertEqual(a["turnovers"]["away"], {"Kötü Pas": 1})
        self.assertEqual(a["turnovers"]["home"], {})

    def test_takim_ozeti_ev_deplasman_ayrilir(self):
        a = A.mac_analizi_notr(self.FIX, self.ATIS, self.OLAY, TakimTest.RAPOR)
        self.assertEqual(a["team"]["home"]["sayi"], 67)
        self.assertEqual(a["team"]["away"]["sayi"], 38)

    def test_boxscore_satirlari_tasinir(self):
        a = A.mac_analizi_notr(self.FIX, self.ATIS, self.OLAY, TakimTest.RAPOR,
                               box_home=[{"no": 2, "name": "X", "points": 14}], box_away=[])
        self.assertEqual(a["box"]["home"][0]["points"], 14)


class DerinTest(unittest.TestCase):
    """Boxscore'da olmayan olcumler: asist agi, kayiptan yenilen, besliler."""

    def test_asist_basketin_ardindaki_olaydan_eslesir(self):
        ev = [olay(1, "09:00", "2-0", True, "24", "2 Sayı Turnike Başarılı"),
              olay(1, "09:00", "2-0", True, "0", "Asist"),
              olay(1, "08:00", "4-0", True, "96", "2 Sayı Turnike Başarılı")]
        a = A.asist_agi(ev, bizim_ev=True)
        self.assertEqual(a["basket"], 2)
        self.assertEqual(a["asistli"], 1)
        self.assertEqual(a["ciftler"][0], ["0", "24", 1])

    def test_rakibin_asisti_bizim_sayilmaz(self):
        ev = [olay(1, "09:00", "0-2", False, "9", "2 Sayı Turnike Başarılı"),
              olay(1, "09:00", "0-2", False, "7", "Asist")]
        self.assertEqual(A.asist_agi(ev, bizim_ev=True)["asistli"], 0)
        self.assertEqual(A.asist_agi(ev, bizim_ev=False)["asistli"], 1)

    def test_kayiptan_yenilen_sayilir(self):
        ev = [olay(1, "09:00", "0-0", True, "2", "Top Kaybı - Kötü Pas"),
              olay(1, "08:55", "0-2", False, "9", "2 Sayı Turnike Başarılı")]
        self.assertEqual(A.kayiptan_yenilen(ev, bizim_ev=True), {"kayip": 1, "yenilen": 2})

    def test_pozisyon_bize_donunce_sayilmaz(self):
        # Kayiptan sonra topu geri aldik ve biz sut attik: o kayip sonucsuz.
        ev = [olay(1, "09:00", "0-0", True, "2", "Top Kaybı - Kötü Pas"),
              olay(1, "08:50", "0-0", True, "5", "Savunma Ribaundu"),
              olay(1, "08:40", "2-0", True, "5", "2 Sayı Turnike Başarılı"),
              olay(1, "08:20", "2-2", False, "9", "2 Sayı Turnike Başarılı")]
        self.assertEqual(A.kayiptan_yenilen(ev, bizim_ev=True)["yenilen"], 0)

    def test_ucluk_uc_sayi_yazilir(self):
        ev = [olay(1, "09:00", "0-0", True, "2", "Top Kaybı - Kötü Pas"),
              olay(1, "08:55", "0-3", False, "9", "3 Sayı Sıçrayarak Atış Başarılı")]
        self.assertEqual(A.kayiptan_yenilen(ev, bizim_ev=True)["yenilen"], 3)

    def test_ilk_bes_boxscore_isaretinden(self):
        box = [{"no": n, "starter": True} for n in (2, 5, 8, 11, 96)] +               [{"no": 24, "starter": False}]
        self.assertEqual(sorted(A._ilk_bes(box, [], True)),
                         sorted(["2", "5", "8", "11", "96"]))

    def test_besli_suresi_ve_farki(self):
        box = [{"no": n, "starter": True} for n in (1, 2, 3, 4, 5)]
        ev = [olay(1, "10:00", "0-0", None),
              olay(1, "08:00", "4-0", True, "2", "2 Sayı Turnike Başarılı"),
              olay(1, "07:00", "4-0", True, "5", "Değişiklik Çıkan"),
              olay(1, "07:00", "4-0", True, "7", "Değişiklik Giren"),
              olay(1, "06:00", "4-3", False, "9", "3 Sayı Sıçrayarak Atış Başarılı")]
        b = A.besliler(ev, True, box)
        ilk = [l for l in b["lineups"] if "5" in l["p"]][0]
        self.assertEqual(ilk["sec"], 180)          # 0 -> 3. dakika
        self.assertEqual(ilk["lehte"], 4)

    def test_usage_sahadayken_takim_sutuyla_oranlanir(self):
        box = [{"no": n, "starter": True} for n in (1, 2, 3, 4, 5)]
        ev = [olay(1, "09:00", "0-0", True, "2", "2 Sayı Turnike Başarısız"),
              olay(1, "08:00", "0-0", True, "2", "2 Sayı Turnike Başarısız"),
              olay(1, "07:00", "0-0", True, "3", "2 Sayı Turnike Başarısız")]
        u = A.besliler(ev, True, box)["usage"]
        self.assertEqual(u["2"]["fga"], 2)
        self.assertEqual(u["2"]["takim"], 3)       # sahadayken takimin 3 sutu

    def test_serbest_atis_saha_sutu_sayilmaz(self):
        box = [{"no": n, "starter": True} for n in (1, 2, 3, 4, 5)]
        ev = [olay(1, "09:00", "0-0", True, "2", "Serbest Atış 1/2 Başarılı")]
        u = A.besliler(ev, True, box)["usage"]
        self.assertEqual(u.get("2", {}).get("fga", 0), 0)


class GecisTest(unittest.TestCase):
    """Gecis hucumu: topu kazandiktan sonra <=7 sn icinde atilan sut."""

    def test_hizli_sut_gecis_sayilir(self):
        ev = [olay(1, "09:00", "0-0", True, "5", "Savunma Ribaundu"),
              olay(1, "08:55", "2-0", True, "2", "2 Sayı Turnike Başarılı")]
        g = A.gecis_dokumu(ev, bizim_ev=True)
        self.assertEqual(g["gecis"], {"deneme": 1, "isabet": 1, "sayi": 2})
        self.assertEqual(g["yariSaha"]["deneme"], 0)
        self.assertEqual(g["oyuncu"]["2"], {"deneme": 1, "isabet": 1})

    def test_yavas_sut_yari_saha_sayilir(self):
        ev = [olay(1, "09:00", "0-0", True, "5", "Savunma Ribaundu"),
              olay(1, "08:45", "0-0", True, "2", "2 Sayı Turnike Başarısız")]
        g = A.gecis_dokumu(ev, bizim_ev=True)
        self.assertEqual(g["gecis"]["deneme"], 0)
        self.assertEqual(g["yariSaha"]["deneme"], 1)

    def test_ucluk_uc_sayi_yazilir(self):
        ev = [olay(1, "09:00", "0-0", True, "5", "Top Çalma"),
              olay(1, "08:57", "3-0", True, "2", "3 Sayı Sıçrayarak Atış Başarılı")]
        self.assertEqual(A.gecis_dokumu(ev, bizim_ev=True)["gecis"]["sayi"], 3)

    def test_arada_top_kaybi_varsa_sayilmaz(self):
        ev = [olay(1, "09:00", "0-0", True, "5", "Savunma Ribaundu"),
              olay(1, "08:58", "0-0", True, "2", "Top Kaybı - Kötü Pas"),
              olay(1, "08:50", "0-2", False, "9", "2 Sayı Turnike Başarılı")]
        g = A.gecis_dokumu(ev, bizim_ev=True)
        self.assertEqual(g["kazanim"], 1)
        self.assertEqual(g["gecis"]["deneme"], 0)

    def test_rakibin_kazanimi_bize_yazilmaz(self):
        ev = [olay(1, "09:00", "0-0", False, "9", "Savunma Ribaundu"),
              olay(1, "08:55", "0-2", False, "9", "2 Sayı Turnike Başarılı")]
        self.assertEqual(A.gecis_dokumu(ev, bizim_ev=True)["kazanim"], 0)
        self.assertEqual(A.gecis_dokumu(ev, bizim_ev=False)["gecis"]["deneme"], 1)

    def test_ceyrek_gecisinde_negatif_sure_atilir(self):
        ev = [olay(2, "01:00", "0-0", True, "5", "Savunma Ribaundu"),
              olay(1, "05:00", "0-0", True, "2", "2 Sayı Turnike Başarılı")]
        self.assertEqual(A.gecis_dokumu(ev, bizim_ev=True)["gecis"]["deneme"], 0)


class IkinciSansTest(unittest.TestCase):
    """Ikinci sans: kendi iskasini toplayip tekrar atmak."""

    def test_ribaund_sonrasi_sut_sayilir(self):
        ev = [olay(1, "09:00", "0-0", True, "30", "Hücum Ribaundu"),
              olay(1, "08:57", "2-0", True, "30", "2 Sayı Tip-In Başarılı")]
        i = A.ikinci_sans_dokumu(ev, bizim_ev=True)
        self.assertEqual(i["deneme"], 1)
        self.assertEqual(i["isabet"], 1)
        self.assertEqual(i["sayi"], 2)
        self.assertEqual(i["tipin"], 1)
        self.assertEqual(i["sutaCevrilen"], 100)

    def test_sutsuz_kapanan_ribaund_orani_dusurur(self):
        ev = [olay(1, "09:00", "0-0", True, "30", "Hücum Ribaundu"),
              olay(1, "08:55", "0-0", True, "2", "Top Kaybı - Kötü Pas"),
              olay(1, "08:00", "0-0", True, "30", "Hücum Ribaundu"),
              olay(1, "07:57", "2-0", True, "30", "2 Sayı Turnike Başarılı")]
        i = A.ikinci_sans_dokumu(ev, bizim_ev=True)
        self.assertEqual(i["ribaund"], 2)
        self.assertEqual(i["deneme"], 1)
        self.assertEqual(i["sutaCevrilen"], 50)

    def test_gec_kalan_sut_ikinci_sans_degil(self):
        # 8 saniyeden sonrasi artik yeniden kurulmus hucum.
        ev = [olay(1, "09:00", "0-0", True, "30", "Hücum Ribaundu"),
              olay(1, "08:45", "2-0", True, "2", "2 Sayı Turnike Başarılı")]
        self.assertEqual(A.ikinci_sans_dokumu(ev, bizim_ev=True)["deneme"], 0)

    def test_rakip_ribaundu_bize_yazilmaz(self):
        ev = [olay(1, "09:00", "0-0", False, "9", "Hücum Ribaundu"),
              olay(1, "08:57", "0-2", False, "9", "2 Sayı Tip-In Başarılı")]
        self.assertEqual(A.ikinci_sans_dokumu(ev, bizim_ev=True)["ribaund"], 0)
        self.assertEqual(A.ikinci_sans_dokumu(ev, bizim_ev=False)["deneme"], 1)


if __name__ == "__main__":
    unittest.main()
