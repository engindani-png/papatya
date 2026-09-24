#!/usr/bin/env python3
"""Duyuru akisinin testleri.  Calistirma:  python -m unittest discover server

NEDEN: veliler duyuruyu telefonda kesik goruyor ve geri donup okuyacak yer
yok. Duyuru SQLite'a yaziliyor ama okuma ucu antrenor sifresi istiyordu.
Duzeltme uc yerde:
  1. GET /api/duyuru herkese acilir (POST sifreli kalir)
  2. metin siniri 300 -> 1000
  3. push govdesi kisa ozet olur, tam metin uygulamada okunur

DIKKAT: bu testler GERCEK PUSH GONDERMEZ. POST yalnizca sifresiz (401)
yolunda denenir; sifreli yol alt surec calistirip velilere bildirim
gonderecegi icin teste alinmaz.
"""

import json
import os
import pathlib
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

SUNUCU_DIZIN = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SUNUCU_DIZIN))

# Ortam, evolog_api ice aktarilmadan ONCE kurulmali: modul sabitleri
# ice aktarma aninda okunuyor.
GECICI = pathlib.Path(tempfile.mkdtemp())
os.environ["EVOLOG_STATE_DIR"] = str(GECICI)
os.environ["EVOLOG_ADMIN_PASS"] = "test-sifre"
os.environ.setdefault("EVOLOG_DATA_DIR", str(GECICI / "data"))

import attendance      # noqa: E402
import evolog_api      # noqa: E402
import evolog_push     # noqa: E402

from http.server import ThreadingHTTPServer   # noqa: E402

UZUN = ("Yarinki antrenman saat 20:00'de Maltepe TOKI Spor Salonu'nda yapilacak. "
        "Servis 19:30'da okul onunden kalkacak, lutfen cocuklari 19:25'te "
        "hazir edin. Yanlarinda su, havlu ve yedek tisort olsun. Hafta sonu "
        "deplasman maci oldugu icin cumartesi antrenmani iptal, pazar gunu "
        "saat 11:00'de salonda toplaniyoruz. Maca gelemeyecek olanlar en gec "
        "cuma aksamina kadar haber versin ki kafileyi ona gore olusturalim. "
        "Ayrica lisans islemleri icin eksik evraki olan velilerden ricamiz, "
        "pazartesiye kadar tamamlamalari.")


class DepoTest(unittest.TestCase):
    """Uzun metin kesilmeden saklanmali (SQLite'in siniri yok, kod koymamali)."""

    def setUp(self):
        self.dizin = pathlib.Path(tempfile.mkdtemp())

    def test_uzun_metin_kesilmeden_kaydedilir(self):
        self.assertGreater(len(UZUN), 300, "test metni 300'den uzun olmali")
        attendance.duyuru_kaydet(self.dizin, "u14", "Antrenman degisikligi", UZUN, 5)
        liste = attendance.duyurular(self.dizin, "u14")
        self.assertEqual(len(liste), 1)
        self.assertEqual(liste[0]["metin"], UZUN)


class GovdeTest(unittest.TestCase):
    """Push govdesi: telefonda kesilecegi icin KASITLI olarak kisaltilir."""

    def test_kisa_metin_aynen_gecer(self):
        kisa = "Yarinki antrenman 20:00'de."
        self.assertEqual(evolog_push.bildirim_govdesi(kisa), kisa)

    def test_uzun_metin_kisaltilir(self):
        g = evolog_push.bildirim_govdesi(UZUN)
        self.assertLess(len(g), len(UZUN))
        self.assertLessEqual(len(g), 220)
        self.assertTrue(g.endswith("…"), f"sonu uc nokta olmali: {g[-20:]!r}")

    def test_kisaltma_kelimeyi_ortadan_bolmez(self):
        g = evolog_push.bildirim_govdesi(UZUN)
        self.assertFalse(g[:-1].rstrip().endswith("-"))
        # son karakterden onceki parca bosluga kadar temiz bitmeli
        self.assertNotIn("  ", g)


class UcTest(unittest.TestCase):
    """HTTP uclarinin yetki davranisi."""

    @classmethod
    def setUpClass(cls):
        GECICI.mkdir(parents=True, exist_ok=True)
        attendance.duyuru_kaydet(GECICI, "u14", "Antrenman degisikligi", UZUN, 5)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), evolog_api.Handler)
        cls.port = cls.srv.server_address[1]
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.th.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def url(self, yol):
        return f"http://127.0.0.1:{self.port}{yol}"

    def ac(self, yol, yontem="GET", govde=None):
        """Tek yerden istek kurar; her istek kendi baglantisini kullanir.

        NOT: bu testin bir donem kirilgan olmasinin sebebi keep-alive DEGIL,
        gercek bir sunucu kusuruydu: do_POST yetkisizken 401 donuyor ama
        istek GOVDESINI hic okumuyordu; sokette kalan okunmamis baytlar
        yuzunden Windows baglantiyi RST ile kapatiyordu. Kusur
        evolog_api.govdeyi_tuket() ile giderildi. `Connection: close` yine de
        duruyor: testin yalitimini artiriyor, zarari yok.
        """
        basliklar = {"Connection": "close"}
        veri = None
        if govde is not None:
            veri = json.dumps(govde).encode()
            basliklar["Content-Type"] = "application/json"
        istek = urllib.request.Request(self.url(yol), method=yontem,
                                       data=veri, headers=basliklar)
        return urllib.request.urlopen(istek, timeout=5)

    def test_get_duyuru_sifresiz_acik(self):
        """Velinin duyuruyu okuyabilmesi icin GET herkese acik olmali."""
        with self.ac("/api/duyuru?age=u14") as r:
            self.assertEqual(r.status, 200)
            veri = json.loads(r.read())
        self.assertIn("duyurular", veri)
        self.assertGreaterEqual(len(veri["duyurular"]), 1)

    def test_get_duyuru_tam_metni_dondurur(self):
        """Uygulamada TAM metin okunacak; uc kisaltmamali."""
        with self.ac("/api/duyuru?age=u14") as r:
            veri = json.loads(r.read())
        self.assertEqual(veri["duyurular"][0]["metin"], UZUN)

    def test_post_duyuru_sifresiz_reddedilir(self):
        """Gonderme yetkisi SADECE antrenorde kalmali (bu yol push tetiklemez)."""
        with self.assertRaises(urllib.error.HTTPError) as c:
            self.ac("/api/duyuru?age=u14", "POST",
                    {"title": "Deneme", "body": "Deneme metni"})
        self.assertEqual(c.exception.code, 401)

    def test_yoklama_hala_sifreli(self):
        """Duyuruyu acarken kisisel veri ucunu yanlislikla acmadigimizi dogrular."""
        with self.assertRaises(urllib.error.HTTPError) as c:
            self.ac("/api/attendance/summary?age=u14")
        self.assertEqual(c.exception.code, 401)


class TekrarTest(unittest.TestCase):
    """Ayni duyuru kisa sure icinde IKI KEZ gitmemeli.

    Kodda "ayni metin iki kez gonderilmez" yorumu vardi ama kontrol HIC
    yapilmiyordu: `done` okunuyor, gonderimden SONRA yaziliyor, ama gondermeden
    once bakilmiyordu. Fikstur yolunda kontrol var (`e["id"] not in done`),
    duyuru yolunda yoktu. CP kopru ucu zaman asiminda tekrar denerse veliler
    cift bildirim alirdi.
    """

    def test_yeni_duyuru_gonderilir(self):
        self.assertFalse(evolog_push.duyuru_tekrar_mi({}, "duyuru-abc", 1000.0))

    def test_ayni_duyuru_pencere_icinde_ENGELLENIR(self):
        done = {"duyuru-abc": evolog_push.dt.datetime.fromtimestamp(
            1000.0, evolog_push.TZ).isoformat(timespec="seconds")}
        self.assertTrue(evolog_push.duyuru_tekrar_mi(done, "duyuru-abc", 1000.0 + 60))

    def test_ayni_duyuru_pencere_disinda_GECER(self):
        """Kocun ayni hatirlatmayi gelecek hafta tekrar gondermesi mesru."""
        done = {"duyuru-abc": evolog_push.dt.datetime.fromtimestamp(
            1000.0, evolog_push.TZ).isoformat(timespec="seconds")}
        self.assertFalse(evolog_push.duyuru_tekrar_mi(done, "duyuru-abc",
                                                      1000.0 + 11 * 60))

    def test_bozuk_zaman_damgasi_engellemez(self):
        """Okunamayan kayit yuzunden mesru duyuru bloklanmasin."""
        self.assertFalse(evolog_push.duyuru_tekrar_mi({"duyuru-abc": "bozuk"},
                                                      "duyuru-abc", 1000.0))


class SinirTest(unittest.TestCase):
    """Metin siniri 1000 olmali (eskiden 300'du ve sessizce kesiyordu)."""

    def test_duyuru_siniri_1000(self):
        self.assertEqual(evolog_api.DUYURU_MAX, 1000)

    def test_clean_str_sinira_kadar_korur(self):
        metin = "a" * 1000
        self.assertEqual(len(evolog_api.clean_str(metin, evolog_api.DUYURU_MAX)), 1000)


if __name__ == "__main__":
    unittest.main()
