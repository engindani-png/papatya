#!/usr/bin/env python3
"""Yoklama kaydinin testleri.  Calistirma:  python -m unittest discover server"""

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
        attendance.save(self.dizin, "u14", kayit)
        okunan = attendance.get(self.dizin, "u14", "2026-09-18", "19:30")
        self.assertEqual(okunan["players"]["750530"], "gelmedi")
        self.assertEqual(okunan["title"], "Basketbol")

    def test_ayni_seans_uzerine_yazilir(self):
        for durum in ("gelmedi", "geldi"):
            attendance.save(self.dizin, "u14", attendance.validate(
                {"date": "2026-09-18", "start": "19:30", "players": {"750529": durum}}))
        veri = attendance.load(self.dizin, "u14")
        self.assertEqual(len(veri["sessions"]), 1)
        self.assertEqual(veri["sessions"]["2026-09-18T19:30"]["players"]["750529"], "geldi")

    def test_bozuk_dosya_bos_kabul_edilir(self):
        attendance.path(self.dizin, "u14").write_text("{bozuk", encoding="utf-8")
        self.assertEqual(attendance.load(self.dizin, "u14"), {"sessions": {}})

    # ---------------------------------------------------------------- ozet
    def test_ozet_izinliyi_payda_saymaz(self):
        attendance.save(self.dizin, "u14", attendance.validate(
            {"date": "2026-09-16", "start": "19:30",
             "players": {"750529": "geldi", "750530": "izinli"}}))
        attendance.save(self.dizin, "u14", attendance.validate(
            {"date": "2026-09-18", "start": "19:30",
             "players": {"750529": "gelmedi", "750530": "geldi"}}))
        ozet = attendance.summary(self.dizin, "u14", KADRO)
        satir = {r["key"]: r for r in ozet["players"]}
        self.assertEqual(satir["750529"]["oran"], 50)     # 1 geldi / 2 sayilan
        self.assertEqual(satir["750530"]["oran"], 100)    # izinli sayilmaz
        self.assertIsNone(satir["numarasiz oyuncu"]["oran"])

    def test_gec_gelen_gelmis_sayilir(self):
        attendance.save(self.dizin, "u14", attendance.validate(
            {"date": "2026-09-18", "start": "19:30", "players": {"750529": "gec"}}))
        ozet = attendance.summary(self.dizin, "u14", KADRO)
        satir = {r["key"]: r for r in ozet["players"]}
        self.assertEqual(satir["750529"]["oran"], 100)
        self.assertEqual(satir["750529"]["gec"], 1)

    def test_ozet_son_n_seansla_sinirlanir(self):
        for gun in ("2026-09-10", "2026-09-12", "2026-09-18"):
            attendance.save(self.dizin, "u14", attendance.validate(
                {"date": gun, "start": "19:30", "players": {"750529": "geldi"}}))
        ozet = attendance.summary(self.dizin, "u14", KADRO, limit=2)
        self.assertEqual(len(ozet["sessions"]), 2)
        self.assertEqual(ozet["sessions"][0]["date"], "2026-09-12")

    def test_kadrodan_ayrilan_oyuncu_ozeti_bozmaz(self):
        attendance.save(self.dizin, "u14", attendance.validate(
            {"date": "2026-09-18", "start": "19:30",
             "players": {"750529": "geldi", "999999": "geldi"}}))
        ozet = attendance.summary(self.dizin, "u14", KADRO)
        self.assertEqual(len(ozet["players"]), len(KADRO))
        self.assertEqual(ozet["sessions"][0]["gelen"], 1)   # kadrodaki tek oyuncu


if __name__ == "__main__":
    unittest.main()
