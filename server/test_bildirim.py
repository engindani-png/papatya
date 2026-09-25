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


class EskimisTarihTest(unittest.TestCase):
    """Drive'in kesinlestirdigi gune dusen, Drive'da olmayan mac eskimistir.

    Kullanici kurali (24 Eylul 2026): "Ayni gun 2 mac gozukuyorsa ve bu
    google drive'da degilse TBF'nin diger sitesi guncellenmemis demektir."
    4 Ekim 2026'da tam bu oldu: Drive 11:30 Emlak Konut (B) derken TBF ayni
    gune bir de Galatasaray deplasmani koymustu.
    """

    DRIVE = {"346867": {"date": "2026-10-04", "time": "11:30",
                        "venue": "BGM SALON C3", "source": "drive"}}

    # Birimi DOGRUDAN sinariz: apply() dateConfirmed'i kendi hesapliyor
    # (uretilmis dizi sezgisi), testte onu zorlamak sezgiyi test etmek olur.
    def _isaretle(self, fixtures, drive=None):
        lig = {"fixtures": fixtures}
        local_edits._eskimis_tarihleri_isaretle(
            lig, self.DRIVE if drive is None else drive)
        return {f["matchId"]: f for f in fixtures}

    def test_ayni_gune_dusen_ilan_edilmemis_mac_eskimis_sayilir(self):
        f = self._isaretle([
            _mac(matchId=346867, dateConfirmed=True),
            _mac(matchId=346872, date="2026-10-04", time="18:30",
                 home="GALATASARAY (A)", away="EVOLOG DAÇKA ŞERİFALİ",
                 isHome=False, venue="Ülker Go Ahead Salonu (C2)",
                 dateConfirmed=False),
        ])
        self.assertTrue(f[346872].get("dateStale"), "TBF'nin eski verisi isaretlenmeli")

    def test_drive_macinin_kendisi_eskimis_sayilmaz(self):
        f = self._isaretle([_mac(matchId=346867, dateConfirmed=True)])
        self.assertIsNone(f[346867].get("dateStale"))

    def test_tbfnin_ILAN_ETTIGI_mac_susturulmaz(self):
        """Gercekten ayni gune iki mac konabilir; ilan edilmise karismayiz."""
        f = self._isaretle([
            _mac(matchId=346867, dateConfirmed=True),
            _mac(matchId=346872, date="2026-10-04", time="18:30",
                 home="GALATASARAY (A)", dateConfirmed=True),
        ])
        self.assertIsNone(f[346872].get("dateStale"))

    def test_baska_gundeki_mac_etkilenmez(self):
        f = self._isaretle([
            _mac(matchId=346867, dateConfirmed=True),
            _mac(matchId=346878, date="2026-10-13", dateConfirmed=False),
        ])
        self.assertIsNone(f[346878].get("dateStale"))

    def test_oynanmis_mac_etkilenmez(self):
        f = self._isaretle([
            _mac(matchId=346867, dateConfirmed=True),
            _mac(matchId=346880, date="2026-10-04", played=True,
                 dateConfirmed=False),
        ])
        self.assertIsNone(f[346880].get("dateStale"))

    def test_drive_bos_ise_hicbir_sey_isaretlenmez(self):
        f = self._isaretle([_mac(matchId=346872, date="2026-10-04",
                                 dateConfirmed=False)], drive={})
        self.assertIsNone(f[346872].get("dateStale"))

    def test_apply_icinden_de_calisir(self):
        """Tam akista da cagriliyor olmali (baglanti testi)."""
        lig = _lig([_mac(matchId=346867)])
        sonuc = local_edits.apply(lig, GECICI / "yok.json", None, drive=self.DRIVE)
        self.assertIn("unconfirmedCount", sonuc)


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


class LigSonucuTest(unittest.TestCase):
    """Ligdeki DIGER takimlarin sonuclari - tek bildirimde, ayri baslikla.

    Kullanici (24-25 Eylul 2026): "Bizim ligimizde oynanan rakip takim
    maclarinin da sonuclari push edilsin. Eski maclara gerek yok, yeni
    oynanan maclar bitince bizim sisteme sonucu dustugunde push edilebilir."

    Neden toplu: ligde haftada 11 rakip maci var; tek tek gitse veli bir
    aksamda alti bildirim alir, hepsini kapatir ve kendi macininkini kacirir.
    Neden ayri baslik: "MAÇ DUYURUSU" gorunce veli kendi cocugunun macini
    sanar.
    """

    def setUp(self):
        self.simdi = dt.datetime(2026, 9, 25, 12, 0, tzinfo=evolog_push.TZ)

    def _lig(self, lig_maclari, bizim=None):
        return {"label": "U14", "fixtures": bizim or [],
                "leagueFixtures": (bizim or []) + lig_maclari}

    def _mac(self, mid, tarih, ev, dep, es, ds, oynandi=True):
        return {"matchId": mid, "date": tarih, "time": "18:30",
                "home": ev, "away": dep, "homeScore": es, "awayScore": ds,
                "played": oynandi}

    def test_yeni_rakip_sonucu_bildirilir(self):
        lig = self._lig([self._mac(10, "2026-09-25", "GALATASARAY (A)",
                                   "BEŞİKTAŞ", 45, 38)])
        olaylar, sessiz = evolog_push.build_league_result_events(
            lig, "u14", {}, self.simdi)
        self.assertEqual(len(olaylar), 1)
        self.assertEqual(olaylar[0]["title"], evolog_push.LIG_BASLIK)
        self.assertIn("GALATASARAY (A) 45-38 BEŞİKTAŞ", olaylar[0]["body"])
        self.assertEqual(sessiz, [])

    def test_birden_fazla_sonuc_TEK_bildirimde(self):
        lig = self._lig([
            self._mac(10, "2026-09-25", "A", "B", 45, 38),
            self._mac(11, "2026-09-25", "C", "D", 50, 49),
            self._mac(12, "2026-09-25", "E", "F", 30, 60),
        ])
        olaylar, _ = evolog_push.build_league_result_events(lig, "u14", {}, self.simdi)
        self.assertEqual(len(olaylar), 1, "tek bildirim olmali")
        for parca in ("A 45-38 B", "C 50-49 D", "E 30-60 F"):
            self.assertIn(parca, olaylar[0]["body"])

    def test_kapsam_her_maci_ayri_tasir(self):
        """Toplu bildirim teslim edilince maclar TEK TEK isaretlenmeli;
        yoksa sonraki turda farkli gruplamayla tekrar giderler."""
        lig = self._lig([self._mac(10, "2026-09-25", "A", "B", 45, 38),
                         self._mac(11, "2026-09-25", "C", "D", 50, 49)])
        olaylar, _ = evolog_push.build_league_result_events(lig, "u14", {}, self.simdi)
        self.assertEqual(sorted(olaylar[0]["kapsam"]),
                         ["ligsonuc-10", "ligsonuc-11"])

    def test_eski_mac_SESSIZCE_isaretlenir(self):
        """Ilk calistirmada sezonun gecmis sonuclari topluca gitmesin."""
        lig = self._lig([self._mac(10, "2026-09-08", "A", "B", 45, 38)])
        olaylar, sessiz = evolog_push.build_league_result_events(
            lig, "u14", {}, self.simdi)
        self.assertEqual(olaylar, [])
        self.assertEqual(sessiz, ["ligsonuc-10"])

    def test_bizim_macimiz_burada_bildirilmez(self):
        """Kendi macimizin sonucu zaten MAÇ DUYURUSU olarak gidiyor."""
        bizim = [self._mac(20, "2026-09-25", "ŞERİFALİ", "X", 60, 40)]
        lig = self._lig([], bizim)
        olaylar, sessiz = evolog_push.build_league_result_events(
            lig, "u14", {}, self.simdi)
        self.assertEqual((olaylar, sessiz), ([], []))

    def test_oynanmamis_mac_bildirilmez(self):
        lig = self._lig([self._mac(10, "2026-09-25", "A", "B", None, None, False)])
        self.assertEqual(evolog_push.build_league_result_events(
            lig, "u14", {}, self.simdi), ([], []))

    def test_skoru_girilmemis_mac_bildirilmez(self):
        """TBF 'oynandi' deyip skoru bos birakabiliyor."""
        lig = self._lig([self._mac(10, "2026-09-25", "A", "B", None, None, True)])
        self.assertEqual(evolog_push.build_league_result_events(
            lig, "u14", {}, self.simdi), ([], []))

    def test_daha_once_bildirilen_tekrar_gitmez(self):
        lig = self._lig([self._mac(10, "2026-09-25", "A", "B", 45, 38)])
        done = {"ligsonuc-10": "2026-09-25T09:00:00+03:00"}
        self.assertEqual(evolog_push.build_league_result_events(
            lig, "u14", done, self.simdi), ([], []))

    def test_cok_sonuc_varsa_govde_kisaltilir(self):
        lig = self._lig([self._mac(10 + i, "2026-09-25", f"A{i}", f"B{i}", 40, 30)
                         for i in range(10)])
        olaylar, _ = evolog_push.build_league_result_events(lig, "u14", {}, self.simdi)
        self.assertIn("maç daha", olaylar[0]["body"])
        self.assertEqual(len(olaylar[0]["kapsam"]), 10, "hepsi isaretlenmeli")

    def test_baslik_mac_duyurusundan_farkli(self):
        self.assertNotEqual(evolog_push.LIG_BASLIK, evolog_push.MAC_BASLIK)


class BildirimTuruTest(unittest.TestCase):
    """Veli hangi bildirimlerin gelecegini ayri ayri secebilmeli.

    Kullanici (25 Eylul 2026): "Bildirimler ayarlar kismina bildirim
    ayarlari ekleyelim. Koc duyurulari, Mac duyurulari, Tum mac duyurulari
    olarak acip kapatabilelim."

    Eskiden tek anahtar vardi: rakip maclarinin sonucunu istemeyen veli
    KENDI cocugunun mac bildirimini de kapatmak zorunda kaliyordu.
    """

    def test_olay_turleri_dogru_eslesir(self):
        beklenen = {
            "duyuru-abc123": "koc",
            "training-u14-ff00": "koc",
            "ligsonuc-toplu-aa11": "lig",
            "result-346856": "mac",
            "change-346867-2026-10-04-11:30-abc": "mac",
            "reminder-346867": "mac",
            "macduyuru-9f8e7d": "mac",
        }
        for olay_id, tur in beklenen.items():
            self.assertEqual(evolog_push.olay_turu(olay_id), tur, olay_id)

    def test_bilinmeyen_olay_mac_sayilir(self):
        """Yeni bir olay turu eklenince sessizce kaybolmasin, gorunsun."""
        self.assertEqual(evolog_push.olay_turu("yepyeni-1"), "mac")

    def test_alan_yoksa_hepsi_acik(self):
        """Bu guncellemeden onceki abonelikler bildirim kaybetmemeli."""
        for tur in evolog_push.TURLER:
            self.assertTrue(evolog_push.tur_istiyor_mu({}, tur), tur)

    def test_bos_liste_de_hepsi_acik_sayilir(self):
        """Bos liste 'hicbirini istemiyorum' degil, 'bilgi yok' demektir;
        kapatma islemi abonelikle birlikte yapilir."""
        self.assertTrue(evolog_push.tur_istiyor_mu({"turler": []}, "mac"))

    def test_secili_tur_gelir_digeri_gelmez(self):
        sub = {"turler": ["mac"]}
        self.assertTrue(evolog_push.tur_istiyor_mu(sub, "mac"))
        self.assertFalse(evolog_push.tur_istiyor_mu(sub, "lig"))
        self.assertFalse(evolog_push.tur_istiyor_mu(sub, "koc"))

    def test_lig_kapaliyken_kendi_macimiz_gelir(self):
        """Istegin asil sebebi: rakip sonuclarini istemeyen veli kendi
        macinin bildirimini kaybetmemeli."""
        sub = {"turler": ["koc", "mac"]}
        self.assertTrue(evolog_push.tur_istiyor_mu(sub, "mac"))
        self.assertFalse(evolog_push.tur_istiyor_mu(sub, "lig"))

    def test_api_turleri_temizler(self):
        import evolog_api
        self.assertEqual(evolog_api.clean_turler(["mac", "lig"]), ["mac", "lig"])
        self.assertEqual(evolog_api.clean_turler(["mac", "uydurma"]), ["mac"])
        self.assertEqual(evolog_api.clean_turler([]), [])
        self.assertIsNone(evolog_api.clean_turler(None), "alan gelmedi = hepsi acik")
        self.assertIsNone(evolog_api.clean_turler("mac"), "bicim bozuk = hepsi acik")

    def test_api_turleri_sirayi_kendi_belirler(self):
        import evolog_api
        self.assertEqual(evolog_api.clean_turler(["lig", "koc", "mac"]),
                         ["koc", "mac", "lig"])


class EmojiTest(unittest.TestCase):
    """Bildirim basliklarindaki emojiler.

    Kullanici (25 Eylul 2026): "Mac duyurusunun basina basket topu emojisi,
    koc duyurusuna alev, diger takim mac duyurularina anons emojisi."

    Telefonda bildirimler alt alta yigiliyor; emoji veli okumadan once
    neyle karsilasacagini soyluyor.
    """

    def test_baslik_emojileri(self):
        self.assertTrue(evolog_push.MAC_BASLIK.startswith("\U0001F3C0"))
        self.assertTrue(evolog_push.LIG_BASLIK.startswith("\U0001F4E3"))
        self.assertEqual(evolog_push.EMOJI_KOC, "\U0001F525")

    def test_emojiler_birbirinden_farkli(self):
        e = {evolog_push.EMOJI_MAC, evolog_push.EMOJI_KOC, evolog_push.EMOJI_LIG}
        self.assertEqual(len(e), 3)

    def test_baslik_metni_korunur(self):
        """Uygulama duyuru turunu basliktan cikariyor; metin bozulmamali."""
        self.assertIn("MAÇ DUYURUSU", evolog_push.MAC_BASLIK)
        self.assertIn("LİG SONUCU", evolog_push.LIG_BASLIK)

    def test_mac_olaylari_emojili_baslikla_gider(self):
        f = _mac(matchId=901, played=True, homeScore=67, awayScore=38)
        for e in evolog_push.build_events(_lig([f]), "u14"):
            self.assertTrue(e["title"].startswith("\U0001F3C0"), e["id"])

    def test_lig_sonucu_anons_emojili(self):
        lig = {"label": "U14", "fixtures": [], "leagueFixtures": [
            {"matchId": 10, "date": "2026-09-25", "home": "A", "away": "B",
             "homeScore": 45, "awayScore": 38, "played": True}]}
        olaylar, _ = evolog_push.build_league_result_events(
            lig, "u14", {}, dt.datetime(2026, 9, 25, 12, 0, tzinfo=evolog_push.TZ))
        self.assertTrue(olaylar[0]["title"].startswith("\U0001F4E3"))

    def test_antrenman_bildirimi_alev_emojili(self):
        """Antrenman programi da 'Koc duyurulari' turunde; ayni emoji."""
        self.assertEqual(evolog_push.olay_turu("training-u14-ab12"), "koc")
