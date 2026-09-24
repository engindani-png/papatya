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

import hashlib
import json
import os
import pathlib
import sqlite3
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


class EtiketTest(unittest.TestCase):
    """Duyuru etiketi: sunucu kaydi ile telefondaki push kopyasini eslestirir.

    NEDEN: telefon gelen HER bildirimi kendi IndexedDB arsivine yaziyor
    (mac sonucu, saat degisikligi, antrenman programi -- bunlarin sunucuda
    kaydi yok). Antrenorun duyurusu ise HEM sunucuda (tam metin) HEM de
    arsivde (kisaltilmis push govdesi) bulunur. Uygulama ikisini `etiket`
    uzerinden eslestirip tek kart gosteriyor. Etiket iki tarafta ayrisirsa
    veli ayni duyuruyu iki kez gorur.
    """

    def setUp(self):
        self.dizin = pathlib.Path(tempfile.mkdtemp())

    def test_etiket_push_tagi_ile_ayni_formul(self):
        etiket = evolog_push.duyuru_etiketi(UZUN)
        self.assertTrue(etiket.startswith("duyuru-"), etiket)
        beklenen = "duyuru-" + hashlib.sha1(UZUN.encode("utf-8")).hexdigest()[:10]
        self.assertEqual(etiket, beklenen)

    def test_ayni_metin_ayni_etiket(self):
        self.assertEqual(evolog_push.duyuru_etiketi(UZUN),
                         evolog_push.duyuru_etiketi(UZUN))

    def test_farkli_metin_farkli_etiket(self):
        self.assertNotEqual(evolog_push.duyuru_etiketi("Antrenman 20:00"),
                            evolog_push.duyuru_etiketi("Antrenman 21:00"))

    def test_bosluk_temizligi_etiketi_degistirmez(self):
        """API metni clean_str ile, push ise .strip() ile aliyor; ayni kalmali."""
        self.assertEqual(evolog_push.duyuru_etiketi("  Antrenman 20:00  "),
                         evolog_push.duyuru_etiketi("Antrenman 20:00"))

    def test_etiket_kaydedilir_ve_okunur(self):
        etiket = evolog_push.duyuru_etiketi(UZUN)
        attendance.duyuru_kaydet(self.dizin, "u14", "Baslik", UZUN, 3, etiket=etiket)
        liste = attendance.duyurular(self.dizin, "u14")
        self.assertEqual(liste[0]["etiket"], etiket)

    def test_etiketsiz_kayit_da_calisir(self):
        """Eski cagri bicimi (etiket verilmeden) kirilmamali."""
        attendance.duyuru_kaydet(self.dizin, "u14", "Baslik", "Kisa duyuru", 1)
        liste = attendance.duyurular(self.dizin, "u14")
        self.assertEqual(liste[0]["metin"], "Kisa duyuru")
        self.assertIn("etiket", liste[0])

    def test_eski_veritabanina_sutun_eklenir(self):
        """Sunucudaki evolog.db aylardir duruyor; CREATE TABLE IF NOT EXISTS
        var olan tabloya dokunmaz. Gocun calistigini kanitlar."""
        yol = attendance.db_path(self.dizin)
        yol.parent.mkdir(parents=True, exist_ok=True)
        eski = sqlite3.connect(str(yol))
        eski.execute("CREATE TABLE duyuru (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                     "yas TEXT, baslik TEXT, metin TEXT, gonderim INTEGER, zaman TEXT)")
        eski.execute("INSERT INTO duyuru (yas, baslik, metin, gonderim, zaman) "
                     "VALUES ('u14','Eski','Eski duyuru',2,'2026-01-01T10:00:00')")
        eski.commit()
        eski.close()

        liste = attendance.duyurular(self.dizin, "u14")
        self.assertEqual(len(liste), 1, "eski kayit kaybolmamali")
        self.assertEqual(liste[0]["metin"], "Eski duyuru")
        self.assertIsNone(liste[0]["etiket"], "eski satirin etiketi bos olmali")

        # Goc sonrasi yeni kayit etiketiyle yazilabilmeli.
        attendance.duyuru_kaydet(self.dizin, "u14", "Yeni", "Yeni duyuru", 1,
                                 etiket="duyuru-abc1234567")
        liste = attendance.duyurular(self.dizin, "u14")
        self.assertEqual(liste[0]["etiket"], "duyuru-abc1234567")

    def test_api_push_ile_ayni_fonksiyonu_kullanir(self):
        """Formul iki yere kopyalanmasin: API, push modulundekini cagiriyor."""
        self.assertIs(evolog_api.evolog_push.duyuru_etiketi,
                      evolog_push.duyuru_etiketi)


class ArsivTest(unittest.TestCase):
    """Telefondaki push arsivi (evolog/duyuru-arsiv.js) sozlesme testi.

    JavaScript burada calistirilamiyor; sinanan sey, sunucunun gonderdigi
    push govdesinin arsivin bekledigi alanlari TASIDIGI: tag, title, body.
    Arsiv kaydinin kimligi `tag + "|" + zaman`; tag bos gelirse kayitlar
    birbirinin uzerine yazilirdi.
    """

    def test_duyuru_olayinda_tag_var(self):
        etiket = evolog_push.duyuru_etiketi("Yarin antrenman yok")
        self.assertTrue(etiket)
        self.assertNotIn("|", etiket, "kimlik ayraci etikette gecmemeli")

    def test_mac_olaylarinin_tagi_bos_degil(self):
        """build_events'in urettigi her olay arsivlenebilir olmali."""
        lig = {
            "season": "2026-2027",
            "fixtures": [{
                "id": "m1", "date": "2026-01-10", "time": "12:00",
                "home": "Serifali", "away": "Rakip",
                "homeScore": 50, "awayScore": 40, "played": True,
            }],
            "ourTeam": "Serifali",
        }
        for olay in evolog_push.build_events(lig, "u14"):
            self.assertTrue(olay.get("tag"), f"tagsiz olay: {olay}")
            self.assertTrue(olay.get("title"), f"basliksiz olay: {olay}")
            self.assertNotIn("|", olay["tag"])


if __name__ == "__main__":
    unittest.main()
