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


def apply(league: dict, overrides_path: pathlib.Path, previous: dict | None = None) -> dict:
    """Elle duzeltmeleri uygular, uretilmis tarihleri isaretler, degisikligi yazar."""
    overrides = load_overrides(overrides_path)
    now = dt.datetime.now(TZ).isoformat(timespec="seconds")

    prev_by_id = {}
    for f in ((previous or {}).get("fixtures") or []):
        prev_by_id[_mid(f)] = f

    for bucket in ("fixtures", "leagueFixtures"):
        fixtures = league.get(bucket) or []
        generated = detect_generated(fixtures)

        for fx in fixtures:
            mid = _mid(fx)
            old = prev_by_id.get(mid) or {}
            patch = overrides.get(mid)

            if patch:
                # Elle girilen bilgi her zaman kazanir.
                for field in ("date", "time", "venue"):
                    if patch.get(field):
                        fx[field] = patch[field]
                fx["dateConfirmed"] = True
                fx["confirmedBy"] = patch.get("note") or "Kulüpten gelen bilgi"
            elif fx.get("played"):
                fx["dateConfirmed"] = True     # oynanmis mac: tarihi zaten kesin
            else:
                fx["dateConfirmed"] = mid not in generated

            # Tarih/saat bir onceki veriye gore degistiyse isaretle.
            changed = (old and (old.get("date") != fx.get("date")
                                or old.get("time") != fx.get("time")))
            if changed and old.get("date"):
                fx["previousDate"] = old.get("date")
                fx["previousTime"] = old.get("time")
                fx["changedAt"] = now
            else:
                # Onceki calismada isaretlenmis degisiklik bilgisini koru.
                for field in ("previousDate", "previousTime", "changedAt"):
                    if old.get(field) and not fx.get(field):
                        fx[field] = old[field]

    unconfirmed = sum(1 for f in (league.get("fixtures") or [])
                      if f.get("dateConfirmed") is False)
    league["unconfirmedCount"] = unconfirmed
    return league
