#!/usr/bin/env python3
"""Bildirim olaylari: sessiz saat ve salon degisikligi.

Calistirma:  python -m unittest discover server

NEDEN (sessiz saat): bildirimler cocuk velilerinin telefonuna gidiyor.
Senkron saat basi calisiyor, yani gece 03:00'te bulunan bir degisiklik
gece 03:00'te veliye gidiyordu. Artik 22:00-07:00 arasi olaylar bekletilir;
"gonderildi" diye isaretlenmedikleri icin pencere bitince ilk turda giderler.

NEDEN (salon): federasyonun haftalik Drive programi bazen gun ve saati
birakip YALNIZCA salonu duzeltiyor. Degisiklik olayi yalnizca tarih/saat
karsilastirdigi icin bu sessizce geciyordu - yani veli yanlis salona
gidiyordu. drive_program.py'nin var olma sebebi tam olarak bu.

DIKKAT: bu testler GERCEK PUSH GONDERMEZ; yalnizca olay uretimini sinar.
"""

import datetime as dt
import os
import pathlib
import sys
import tempfile
import unittest

SUNUCU_DIZIN = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SUNUCU_DIZIN))
sys.path.insert(0, str(SUNUCU_DIZIN.parent / "scripts"))

GECICI = pathlib.Path(tempfile.mkdtemp())
os.environ.setdefault("EVOLOG_STATE_DIR", str(GECICI))
os.environ.setdefault("EVOLOG_DATA_DIR", str(GECICI / "data"))

import evolog_push      # noqa: E402
import local_edits      # noqa: E402


def _saat(h, d=24):
    return dt.datetime(2026, 9, d, h, 0, tzinfo=evolog_push.TZ)


class SessizSaatTest(unittest.TestCase):
    """22:00-07:00 arasi otomatik bildirim gitmez."""

    def test_gece_sessiz(self):
        for h in (22, 23, 0, 3, 6):
            self.assertTrue(evolog_push.sessiz_saat(_saat(h)), f"{h}:00 sessiz olmali")

    def test_gunduz_sessiz_degil(self):
        for h in (7, 8, 12, 19, 21):
            self.assertFalse(evolog_push.sessiz_saat(_saat(h)), f"{h}:00 acik olmali")

    def test_pencere_sinirlari(self):
        """Bas dahil, bit haric: 22:00 sessiz, 07:00 degil."""
        self.assertTrue(evolog_push.sessiz_saat(_saat(22)))
        self.assertFalse(evolog_push.sessiz_saat(_saat(7)))

    def test_pencere_yapilandirilabilir(self):
        """Gece yarisini asmayan pencere de dogru hesaplanmali."""
        bas, bit = evolog_push.SESSIZ_BAS, evolog_push.SESSIZ_BIT
        try:
            evolog_push.SESSIZ_BAS, evolog_push.SESSIZ_BIT = 1, 7
            self.assertTrue(evolog_push.sessiz_saat(_saat(3)))
            self.assertFalse(evolog_push.sessiz_saat(_saat(23)))
        finally:
            evolog_push.SESSIZ_BAS, evolog_push.SESSIZ_BIT = bas, bit


def _mac(**ek):
    temel = {
        "matchId": 900, "date": "2026-10-04", "time": "11:30",
        "home": "EVOLOG DAÇKA ŞERİFALİ", "away": "EMLAK KONUT SPOR (B)",
        "homeScore": None, "awayScore": None, "played": False,
        "isOurs": True, "isHome": True, "venue": "BGM SALON C3",
    }
    temel.update(ek)
    return temel


def _lig(fixtures):
    return {"season": "2026-2027", "fixtures": fixtures, "leagueFixtures": fixtures}


def _degisiklikler(lig):
    olaylar = evolog_push.build_events(lig, "u14")
    return [e for e in olaylar if e["id"].startswith("change-")]


class SalonDegisikligiTest(unittest.TestCase):
    """Yalnizca salon degistiginde de veliye haber gitmeli."""

    def test_sadece_salon_degisince_olay_uretilir(self):
        f = _mac(previousDate="2026-10-04", previousTime="11:30",
                 previousVenue="Ülker Go Ahead Salonu (C2)",
                 changedAt="2026-09-24T23:00:00+03:00")
        olaylar = _degisiklikler(_lig([f]))
        self.assertEqual(len(olaylar), 1, "salon degisikligi bildirilmeli")
        self.assertEqual(olaylar[0]["title"], evolog_push.MAC_BASLIK)
        self.assertIn("salonu değişti", olaylar[0]["body"])
        self.assertIn("BGM SALON C3", olaylar[0]["body"])
        self.assertIn("Ülker Go Ahead", olaylar[0]["body"], "eski salon da yazmali")

    def test_saat_degisince_baslik_saat_der(self):
        f = _mac(previousDate="2026-10-04", previousTime="18:30",
                 previousVenue="BGM SALON C3",
                 changedAt="2026-09-24T23:00:00+03:00")
        olaylar = _degisiklikler(_lig([f]))
        self.assertEqual(len(olaylar), 1)
        self.assertIn("saati değişti", olaylar[0]["body"])
        self.assertNotIn("salonu", olaylar[0]["body"])

    def test_ikisi_birden_degisince_ikisi_de_yazilir(self):
        f = _mac(previousDate="2026-10-04", previousTime="18:30",
                 previousVenue="Ülker Go Ahead Salonu (C2)",
                 changedAt="2026-09-24T23:00:00+03:00")
        olaylar = _degisiklikler(_lig([f]))
        self.assertIn("saati ve salonu değişti", olaylar[0]["body"])

    def test_hicbir_sey_degismediyse_olay_yok(self):
        f = _mac(previousDate="2026-10-04", previousTime="11:30",
                 previousVenue="BGM SALON C3",
                 changedAt="2026-09-24T23:00:00+03:00")
        self.assertEqual(_degisiklikler(_lig([f])), [])

    def test_olay_kimligi_salonu_icerir(self):
        """Yalnizca salon degistiginde kimlik de degismeli; yoksa olay
        'zaten gonderilmis' sayilip hic gitmez."""
        ortak = dict(previousDate="2026-10-04", previousTime="11:30",
                     changedAt="2026-09-24T23:00:00+03:00")
        a = _degisiklikler(_lig([_mac(venue="BGM SALON C3",
                                      previousVenue="Ülker (C2)", **ortak)]))
        b = _degisiklikler(_lig([_mac(venue="Ülker Go Ahead (C2)",
                                      previousVenue="Ülker (C2)", **ortak)]))
        self.assertNotEqual(a[0]["id"], b[0]["id"])

    def test_salon_bos_gelirse_olay_uretilmez(self):
        """Veri kaybi bildirime donusmemeli: salon silinince 'degisti' demeyiz."""
        f = _mac(venue="", previousDate="2026-10-04", previousTime="11:30",
                 previousVenue="BGM SALON C3",
                 changedAt="2026-09-24T23:00:00+03:00")
        self.assertEqual(_degisiklikler(_lig([f])), [])


class GecmisMacTest(unittest.TestCase):
    """Oynanmis/gecmis mac icin degisiklik bildirimi gitmez.

    Olay kimligi artik salonu da iceriyor. Gecmis bir macin kaydi sonradan
    duzeltilince YENI kimlik olusuyor ve veliye "maci sali oynayacaksiniz"
    diye gecmise ait bir bildirim gidiyordu.
    """

    def test_gecmis_mac_icin_degisiklik_bildirimi_yok(self):
        f = _mac(date="2026-01-05", time="20:00", venue="BGM SALON C3",
                 previousDate="2026-01-05", previousTime="18:30",
                 previousVenue="Ülker (C2)", changedAt="2026-09-24T23:00:00+03:00")
        self.assertEqual(_degisiklikler(_lig([f])), [])

    def test_gelecek_mac_icin_bildirim_gider(self):
        f = _mac(date="2099-01-05", time="20:00", venue="BGM SALON C3",
                 previousDate="2099-01-05", previousTime="18:30",
                 previousVenue="Ülker (C2)", changedAt="2026-09-24T23:00:00+03:00")
        self.assertEqual(len(_degisiklikler(_lig([f]))), 1)


class BaslikTest(unittest.TestCase):
    """Mac bildirimleri TEK baslik altinda: "MAÇ DUYURUSU".

    Kullanici istegi (24 Eylul 2026): "Maç duyuruları - MAÇ DUYURUSU başlığı
    ile gönderilsin. içeriğini yaz tabiki. Koç duyuruları ayrı gider."
    Baslik artik ne oldugunu soylemedigi icin govde TASIMAK ZORUNDA.
    """

    def test_sonuc_hatirlatma_degisiklik_hepsi_ayni_baslik(self):
        fixtures = [
            _mac(matchId=901, played=True, homeScore=67, awayScore=38),
            _mac(matchId=902, date="2099-10-04", previousDate="2099-10-04",
                 previousTime="18:30", previousVenue="Ülker (C2)",
                 changedAt="2026-09-24T23:00:00+03:00"),
        ]
        olaylar = evolog_push.build_events(_lig(fixtures), "u14")
        self.assertTrue(olaylar, "olay uretilmeliydi")
        for e in olaylar:
            self.assertEqual(e["title"], evolog_push.MAC_BASLIK, e["id"])
            self.assertTrue(e["body"].strip(), f"{e['id']} govdesi bos")

    def test_sonuc_govdesi_skoru_tasir(self):
        f = _mac(matchId=901, played=True, homeScore=67, awayScore=38)
        olay = [e for e in evolog_push.build_events(_lig([f]), "u14")
                if e["id"].startswith("result-")][0]
        self.assertIn("67", olay["body"])
        self.assertIn("38", olay["body"])
        self.assertIn("Kazandık", olay["body"], "sonuc basligi govdeye tasinmali")

    def test_koc_duyurusu_ayri_baslik(self):
        """Antrenorun duyurusu mac bildirimiyle ayni baslikta gitmemeli."""
        self.assertNotEqual("Antrenörden duyuru", evolog_push.MAC_BASLIK)


class DegisiklikIzleriTest(unittest.TestCase):
    """local_edits salon degisikligini de isaretlemeli."""

    def test_salon_degisince_previousVenue_yazilir(self):
        onceki = {"fixtures": [_mac(venue="Ülker Go Ahead Salonu (C2)")]}
        lig = _lig([_mac(venue="BGM SALON C3")])
        sonuc = local_edits.apply(lig, GECICI / "yok.json", onceki)
        f = sonuc["fixtures"][0]
        self.assertEqual(f.get("previousVenue"), "Ülker Go Ahead Salonu (C2)")
        self.assertTrue(f.get("changedAt"))

    def test_hicbir_sey_degismezse_iz_birakilmaz(self):
        onceki = {"fixtures": [_mac()]}
        sonuc = local_edits.apply(_lig([_mac()]), GECICI / "yok.json", onceki)
        self.assertIsNone(sonuc["fixtures"][0].get("changedAt"))


if __name__ == "__main__":
    unittest.main()
