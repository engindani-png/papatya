#!/usr/bin/env python3
"""Elle girilen kesin bilgiler + uretilmis (sahte) tarih tespiti.

TBF fikstur servisi, ilan edilmemis maclar icin gercek tarih yerine duzenli
araliklarla dizilmis dolgu tarihler donuyor: her mac tam 9 gun arayla ve hep
ayni saatte, haftanin gunleri sirayla kayarak. Bunlar takvim degil, yer
tutucu. Velilere kesin gunmus gibi gosterilmemeli.

Bu modul iki is yapar:
  1. data/<yas>/overrides.json icindeki elle girilmis kesin bilgileri uygular
     (senkronizasyon bunlari asla ezmez).
  2. Kalan maclarda uretilmis diziyi bulup dateConfirmed=false isaretler.

Ayrica bir macin tarihi/saati bir onceki veriye gore degistiyse changedAt ve
previousDate/previousTime alanlarini yazar; bildirim scripti bunu kullanir.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib

TZ = dt.timezone(dt.timedelta(hours=3))

# Uretilmis dizinin imzasi: ardisik maclar arasi tam bu kadar gun ve ayni saat.
GENERATED_STEP_DAYS = 9
# Bu uzunlukta bir dizi bulunmadan "uretilmis" demeyiz (yanlis pozitif olmasin).
MIN_RUN = 4


def _mid(fixture: dict) -> str:
    return str(fixture.get("matchId") or "")


def _date(fixture: dict):
    try:
        return dt.date.fromisoformat(fixture["date"])
    except (KeyError, TypeError, ValueError):
        return None


def load_overrides(path: pathlib.Path) -> dict:
    """data/<yas>/overrides.json -> {matchId: {date, time, venue, note}}"""
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return {str(k): v for k, v in (raw.get("matches") or {}).items()}


def detect_generated(fixtures: list[dict]) -> set:
    """Duzenli araliklarla uretilmis gorunen maclarin matchId kumesini verir."""
    dated = [f for f in fixtures if _date(f) and f.get("week")]
    dated.sort(key=lambda f: f["week"])
    if len(dated) < MIN_RUN:
        return set()

    generated = set()
    run = [dated[0]]
    for prev, cur in zip(dated, dated[1:]):
        same_step = (_date(cur) - _date(prev)).days == GENERATED_STEP_DAYS
        same_time = (cur.get("time") or "") == (prev.get("time") or "")
        if same_step and same_time:
            run.append(cur)
        else:
            if len(run) >= MIN_RUN:
                generated.update(_mid(f) for f in run)
            run = [cur]
    if len(run) >= MIN_RUN:
        generated.update(_mid(f) for f in run)
    return generated


def detect_generated_lig(fixtures: list[dict]) -> set:
    """Lig GENELI listesinde uretilmis tarihleri bulur - takim takim.

    detect_generated tek bir takimin fikstur listesi icin yazildi: maclari
    haftaya gore siralar ve aralarinda sabit gun farki arar. Lig geneli
    listesinde her haftada 12 mac var, dolayisiyla ardisik iki kayit ayni
    takima ait degil; dizi hicbir zaman tutmuyor ve TEK BIR mac bile
    "uretilmis" sayilmiyordu.

    Sonuc: lig geneli ekraninda TBF'nin uydurdugu butun dolgu tarihler
    KESIN tarih gibi basiliyordu. 24 Eylul 2026'da gorulen hali: Emlak
    Konut Spor (B) 4 Ekim'de iki maca birden cikiyor (3. hafta 11:30,
    4. hafta 18:30), 8. hafta maci 10 Eylul'de yani 1. haftadan once
    oynanmis gorunuyor.

    Duzeltme: dizi sezgisi her takimin KENDI mac listesi uzerinde ayri
    calistirilir, sonuclar birlestirilir. Bir mac iki takimdan birinin
    dizisinde uretilmis gorunuyorsa uretilmistir.
    """
    takimlar: dict[str, list] = {}
    for f in fixtures:
        for ad in (f.get("home"), f.get("away")):
            if ad:
                takimlar.setdefault(ad, []).append(f)
    uretilmis: set = set()
    for maclar in takimlar.values():
        uretilmis |= detect_generated(maclar)
    return uretilmis


def _eskimis_tarihleri_isaretle(league: dict, drive: dict) -> None:
    """Drive'in kesinlestirdigi bir gune dusen, Drive'da OLMAYAN macimizi
    "TBF'nin eskimis verisi" diye isaretler.

    Kullanici kurali (24 Eylul 2026): "Ayni gun 2 mac gozukuyorsa ve bu
    google drive'da degilse TBF'nin diger sitesi guncellenmemis demektir.
    Bu tip durumlarda guncel bilgi hep google drive baz alinmali."

    Gercek ornek: 4 Ekim 2026'da Drive bizi 11:30'da Emlak Konut (B) ile
    BGM Salon C3'te gosteriyordu; TBF ayni gune bir de Galatasaray (A)
    deplasmani koymustu ve o tarih TBF'de zaten ilan edilmemisti
    (dateConfirmed=false). Veli ayni gun iki mac goruyordu.

    Isaret yalnizca TBF'nin ILAN ETMEDIGI maclara konur: ilan edilmis bir
    mac gercekten ayni gune denk gelebilir (cift mac), onu susturmak
    yanlis olur.
    """
    if not drive:
        return
    drive_gunleri = {p.get("date") for p in drive.values() if p.get("date")}
    if not drive_gunleri:
        return
    drive_maclari = {str(mid) for mid in drive}
    for fx in (league.get("fixtures") or []):
        if not fx.get("isOurs") or fx.get("played"):
            continue
        if str(fx.get("matchId")) in drive_maclari:
            continue                      # bu macin kaynagi zaten Drive
        if fx.get("dateConfirmed") is not False:
            continue                      # TBF ilan etmis; karismayiz
        if fx.get("date") in drive_gunleri:
            fx["dateStale"] = True


def apply(league: dict, overrides_path: pathlib.Path, previous: dict | None = None,
          drive: dict | None = None) -> dict:
    """Elle duzeltmeleri uygular, uretilmis tarihleri isaretler, degisikligi yazar.

    `drive`: federasyonun Drive'daki haftalik programindan cikan
    {matchId: {date, time, venue}} (bkz. scripts/drive_program.py).
    ONCELIK: elle overrides > Drive > TBF.
    """
    overrides = load_overrides(overrides_path)
    drive = drive or {}
    now = dt.datetime.now(TZ).isoformat(timespec="seconds")

    prev_by_id = {}
    for f in ((previous or {}).get("fixtures") or []):
        prev_by_id[_mid(f)] = f

    for bucket in ("fixtures", "leagueFixtures"):
        fixtures = league.get(bucket) or []
        # Lig geneli listesi cok takimli: dizi sezgisi takim takim calismali,
        # yoksa hicbir dolgu tarih yakalanmiyor (bkz. detect_generated_lig).
        generated = (detect_generated_lig(fixtures) if bucket == "leagueFixtures"
                     else detect_generated(fixtures))

        for fx in fixtures:
            mid = _mid(fx)
            old = prev_by_id.get(mid) or {}
            patch = overrides.get(mid)

            drive_patch = drive.get(mid) if not fx.get("played") else None

            if patch or drive_patch:
                # Oncelik ALAN BAZINDA: once Drive, ustune elle girilen.
                # Kayit bazinda olsaydi, yalnizca tarih/saat yazilmis bir
                # override federasyonun verdigi SALONU da bloklardi.
                kaynak = []
                if drive_patch:
                    for field in ("date", "time", "venue"):
                        if drive_patch.get(field):
                            fx[field] = drive_patch[field]
                    fx["source"] = "drive"
                    kaynak.append("Federasyon haftalık programı")
                if patch:
                    for field in ("date", "time", "venue"):
                        if patch.get(field):
                            fx[field] = patch[field]
                    kaynak.insert(0, patch.get("note") or "Kulüpten gelen bilgi")
                fx["dateConfirmed"] = True
                fx["confirmedBy"] = " · ".join(kaynak)
            elif fx.get("played"):
                fx["dateConfirmed"] = True     # oynanmis mac: tarihi zaten kesin
            else:
                fx["dateConfirmed"] = mid not in generated

            # Tarih/saat/SALON bir onceki veriye gore degistiyse isaretle.
            # Salon da sayilir: federasyonun haftalik programi ayni gun ve
            # saati birakip yalnizca salonu duzeltebiliyor ve veli o zaman
            # yanlis salona gidiyordu (bkz. drive_program.py basligi).
            changed = (old and (old.get("date") != fx.get("date")
                                or old.get("time") != fx.get("time")
                                or old.get("venue") != fx.get("venue")))
            if changed and old.get("date"):
                fx["previousDate"] = old.get("date")
                fx["previousTime"] = old.get("time")
                fx["previousVenue"] = old.get("venue")
                fx["changedAt"] = now
            else:
                # Onceki calismada isaretlenmis degisiklik bilgisini koru.
                for field in ("previousDate", "previousTime", "previousVenue",
                              "changedAt"):
                    if old.get(field) and not fx.get(field):
                        fx[field] = old[field]

    _eskimis_tarihleri_isaretle(league, drive)

    unconfirmed = sum(1 for f in (league.get("fixtures") or [])
                      if f.get("dateConfirmed") is False)
    league["unconfirmedCount"] = unconfirmed
    return league
