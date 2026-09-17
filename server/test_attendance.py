#!/usr/bin/env python3
"""Yoklama kaydinin testleri.  Calistirma:  python -m unittest discover server"""

import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import attendance  # noqa: E402


KADRO = [
    {"no": 2, "name": "Zeynep D.", "tbfPlayerId": 750529},
    {"no": 7, "name": "Elif K.", "tbfPlayerId": 750530},
    {"no": 0, "name": "Numarasiz Oyuncu", "tbfPlayerId": None},
]


class YoklamaTest(unittest.TestCase):
    def setUp(self):
        self.dizin = pathlib.Path(tempfile.mkdtemp())

    # ------------------------------------------------------------ dogrulama
    def test_gecersiz_tarih_reddedilir(self):
        with self.assertRaises(ValueError):
            attendance.validate({"date": "18.09.2026", "start": "19:30",
                                 "players": {"750529": "geldi"}})

    def test_gecersiz_saat_reddedilir(self):
        with self.assertRaises(ValueError):
            attendance.validate({"date": "2026-09-18", "start": "7pm",
                                 "players": {"750529": "geldi"}})

    def test_bilinmeyen_durum_atilir(self):
        kayit = attendance.validate({"date": "2026-09-18", "start": "19:30",
                                     "players": {"750529": "geldi", "750530": "belki"}})
        self.assertEqual(kayit["players"], {"750529": "geldi"})

    def test_bos_yoklama_reddedilir(self):
        with self.assertRaises(ValueError):
            attendance.validate({"date": "2026-09-18", "start": "19:30", "players": {}})

    # --------------------------------------------------------------- kayit
    def test_kaydet_ve_oku(self):
        kayit = attendance.validate({"date": "2026-09-18", "start": "19:30",
                                     "title": "Basketbol", "venue": "tev",
                                     "players": {"750529": "geldi", "750530": "gelmedi"}})
        attendance.kaydet(self.dizin, "u14", kayit)
        okunan = attendance.get(self.dizin, "u14", "2026-09-18", "19:30")
        self.assertEqual(okunan["players"]["750530"], "gelmedi")
        self.assertEqual(okunan["title"], "Basketbol")

    def test_ayni_seans_uzerine_yazilir(self):
        for durum in ("gelmedi", "geldi"):
            attendance.kaydet(self.dizin, "u14", attendance.validate(
                {"date": "2026-09-18", "start": "19:30", "players": {"750529": durum}}))
        self.assertEqual(len(attendance.seanslar(self.dizin, "u14")), 1)
        self.assertEqual(attendance.get(self.dizin, "u14", "2026-09-18", "19:30")
                         ["players"]["750529"], "geldi")

    def test_eski_json_veritabanina_tasinir(self):
        eski = self.dizin / "attendance-u14.json"
        eski.write_text(json.dumps({"sessions": {"2026-09-16T19:30": {
            "date": "2026-09-16", "start": "19:30", "title": "Basketbol",
            "players": {"750529": "geldi", "750530": "gelmedi"}}}}), encoding="utf-8")
        okunan = attendance.get(self.dizin, "u14", "2026-09-16", "19:30")
        self.assertEqual(okunan["players"]["750530"], "gelmedi")
        self.assertFalse(eski.exists())          # bir kez tasinir, tekrar okunmaz

    # ---------------------------------------------------------------- ozet
    def test_ozet_izinliyi_payda_saymaz(self):
        attendance.kaydet(self.dizin, "u14", attendance.validate(
            {"date": "2026-09-16", "start": "19:30",
             "players": {"750529": "geldi", "750530": "izinli"}}))
        attendance.kaydet(self.dizin, "u14", attendance.validate(
            {"date": "2026-09-18", "start": "19:30",
             "players": {"750529": "gelmedi", "750530": "geldi"}}))
        ozet = attendance.summary(self.dizin, "u14", KADRO)
        satir = {r["key"]: r for r in ozet["players"]}
        self.assertEqual(satir["750529"]["oran"], 50)     # 1 geldi / 2 sayilan
        self.assertEqual(satir["750530"]["oran"], 100)    # izinli sayilmaz
        self.assertIsNone(satir["numarasiz oyuncu"]["oran"])

    def test_gec_gelen_gelmis_sayilir(self):
        attendance.kaydet(self.dizin, "u14", attendance.validate(
            {"date": "2026-09-18", "start": "19:30", "players": {"750529": "gec"}}))
        ozet = attendance.summary(self.dizin, "u14", KADRO)
        satir = {r["key"]: r for r in ozet["players"]}
        self.assertEqual(satir["750529"]["oran"], 100)
        self.assertEqual(satir["750529"]["gec"], 1)

    def test_ozet_son_n_seansla_sinirlanir(self):
        for gun in ("2026-09-10", "2026-09-12", "2026-09-18"):
            attendance.kaydet(self.dizin, "u14", attendance.validate(
                {"date": gun, "start": "19:30", "players": {"750529": "geldi"}}))
        ozet = attendance.summary(self.dizin, "u14", KADRO, limit=2)
        self.assertEqual(len(ozet["sessions"]), 2)
        self.assertEqual(ozet["sessions"][0]["date"], "2026-09-12")

    def test_kadrodan_ayrilan_oyuncu_ozeti_bozmaz(self):
        attendance.kaydet(self.dizin, "u14", attendance.validate(
            {"date": "2026-09-18", "start": "19:30",
             "players": {"750529": "geldi", "999999": "geldi"}}))
        ozet = attendance.summary(self.dizin, "u14", KADRO)
        self.assertEqual(len(ozet["players"]), len(KADRO))
        self.assertEqual(ozet["sessions"][0]["gelen"], 1)   # kadrodaki tek oyuncu



class DevamsizlikDokumuTest(unittest.TestCase):
    """Antrenorun sordugu soru "kac gun" degil, "nasil": ust uste mi?"""

    def setUp(self):
        self.dizin = pathlib.Path(tempfile.mkdtemp())
        # 6 antrenman: geldi, gelmedi, gelmedi, izinli, gelmedi, gelmedi
        plan = [("2026-09-01", "geldi"), ("2026-09-03", "gelmedi"), ("2026-09-05", "gelmedi"),
                ("2026-09-08", "izinli"), ("2026-09-10", "gelmedi"), ("2026-09-12", "gelmedi")]
        for gun, durum in plan:
            attendance.kaydet(self.dizin, "u14", attendance.validate(
                {"date": gun, "start": "19:30", "title": "Basketbol",
                 "players": {"750529": durum, "750530": "geldi"}}))

    def test_ust_uste_gelmeme_sayisi(self):
        d = attendance.oyuncu_dokumu(self.dizin, "u14", "750529", KADRO)
        self.assertEqual(d["streak"], 2)          # son iki antrenman
        self.assertEqual(d["enUzun"], 2)
        self.assertEqual(d["counts"]["gelmedi"], 4)
        self.assertEqual(d["counts"]["izinli"], 1)

    def test_gelmedigi_tarihler_yeniden_eskiye(self):
        d = attendance.oyuncu_dokumu(self.dizin, "u14", "750529", KADRO)
        self.assertEqual([k["date"] for k in d["missed"]],
                         ["2026-09-12", "2026-09-10", "2026-09-05", "2026-09-03"])

    def test_izinli_seriyi_bozar(self):
        # 08'deki izinli olmasaydi seri 4 olurdu; mazeretli gun seriyi keser.
        d = attendance.oyuncu_dokumu(self.dizin, "u14", "750529", KADRO)
        self.assertLess(d["streak"], 4)

    def test_tam_katilan_oyuncuda_seri_sifir(self):
        d = attendance.oyuncu_dokumu(self.dizin, "u14", "750530", KADRO)
        self.assertEqual(d["streak"], 0)
        self.assertEqual(d["oran"], 100)
        self.assertEqual(d["toplam"], 6)

    def test_isaretlenmemis_antrenman_sayilmaz(self):
        attendance.kaydet(self.dizin, "u14", attendance.validate(
            {"date": "2026-09-15", "start": "19:30", "players": {"750530": "geldi"}}))
        d = attendance.oyuncu_dokumu(self.dizin, "u14", "750529", KADRO)
        self.assertEqual(d["toplam"], 6)          # 15 Eylul onda isaretli degil


class DuyuruTest(unittest.TestCase):
    def setUp(self):
        self.dizin = pathlib.Path(tempfile.mkdtemp())

    def test_duyuru_kaydedilir_ve_okunur(self):
        attendance.duyuru_kaydet(self.dizin, "u14", "Duyuru", "Yarın antrenman yok", 9)
        kayit = attendance.duyurular(self.dizin, "u14")
        self.assertEqual(len(kayit), 1)
        self.assertEqual(kayit[0]["gonderim"], 9)

if __name__ == "__main__":
    unittest.main()
