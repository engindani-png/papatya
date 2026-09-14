#!/usr/bin/env python3
"""TBF verisini resmi JSON API'sinden ceker ve data/league.json dosyasini uretir.

TBF sitesi (www.tbf.org.tr) bir Nuxt uygulamasi: sayfa HTML'inde tablo yok,
puan durumu / fikstur / mac istatistigi tarayicida su adresten aliniyor:

    https://miniappapi.tbf.org.tr/webapi-service/api/...

Bu script dogrudan o API'yi kullanir. Kimlik dogrulama, cerez ya da tarayici
gerekmez; yalnizca Python standart kutuphanesi kullanilir.

Kullanim:
    python3 scripts/tbf_sync.py                # cek ve data/league.json yaz
    python3 scripts/tbf_sync.py --dry-run      # cek, ekrana yaz, dosyaya dokunma
    python3 scripts/tbf_sync.py --probe        # endpoint'leri dene, ne donuyor goster
    python3 scripts/tbf_sync.py --roster       # data/team.json kadrosunu da guncelle
    python3 scripts/tbf_sync.py --no-details   # ceyrek/oyuncu istatistigi cekme
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "scripts" / "tbf_config.json"
LEAGUE_PATH = ROOT / "data" / "league.json"
TEAM_PATH = ROOT / "data" / "team.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip",
    "Origin": "https://www.tbf.org.tr",
    "Referer": "https://www.tbf.org.tr/",
}


# --------------------------------------------------------------------- yardim
def log(msg: str = "") -> None:
    print(msg, flush=True)


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def now_iso() -> str:
    tz = dt.timezone(dt.timedelta(hours=3))
    return dt.datetime.now(tz).replace(microsecond=0).isoformat()


def api_get(base: str, path: str, tries: int = 3, timeout: int = 45):
    """API'den JSON ceker. Basarisizsa RuntimeError firlatir."""
    url = base.rstrip("/") + path
    last = None
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                payload = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            last = f"HTTP {exc.code} — {body or exc.reason}"
        except Exception as exc:  # aglar, zaman asimi, bozuk JSON
            last = f"{type(exc).__name__}: {exc}"
        else:
            if not payload.get("isSuccess", True):
                detail = (payload.get("problemDetails") or {}).get("detail", "")
                raise RuntimeError(f"{path} — API hata: {detail or payload.get('message')}")
            return payload.get("data")
        if attempt < tries:
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"{path} — {last}")


def num(value, default=None):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def title_tr(name: str) -> str:
    """TBF adlari BUYUK harf gonderir; okunur hale getirir (Turkce uyumlu)."""
    if not name:
        return ""
    parts = []
    for word in re.split(r"(\s+|-)", name.strip()):
        if not word.strip() or word == "-":
            parts.append(word)
            continue
        low = word.lower()
        low = low.replace("i̇", "i")  # ust-uste nokta birlesimi
        parts.append(low[0].upper() + low[1:])
    out = "".join(parts)
    # I -> i donusumu Turkce'de yanlis olur; yaygin harfleri duzelt
    return out.replace("Ii", "İi").replace("Ş", "Ş")


# ------------------------------------------------------------------ cekicilik
def fetch_standings(cfg: dict) -> tuple[list, str | None, list]:
    """Puan durumunu ceker. (satirlar, grup_adi, uyarilar)"""
    base = cfg["apiBaseUrl"]
    league_id = cfg["leagueId"]
    our_id = num(cfg["teamProcessId"])
    groups = api_get(base, f"/api/League/get-standings-table?leagueId={league_id}") or []
    if not groups:
        return [], None, ["Puan durumu bos dondu."]

    chosen = None
    for grp in groups:
        rows = grp.get("standings") or []
        if any(num(r.get("takimIslemId")) == our_id for r in rows):
            chosen = grp
            break
    if chosen is None:
        chosen = groups[0]

    out = []
    for row in chosen.get("standings") or []:
        scored = num(row.get("a"), 0)
        against = num(row.get("y"), 0)
        out.append({
            "rank": num(row.get("sira")),
            "team": row.get("takimAdi") or "",
            "played": num(row.get("o")),
            "won": num(row.get("g")),
            "lost": num(row.get("m")),
            "pointsFor": scored,
            "pointsAgainst": against,
            "diff": (scored - against) if scored is not None and against is not None else None,
            "points": num(row.get("puan")),
            "logo": row.get("teamLogo") or None,
            "isOurs": num(row.get("takimIslemId")) == our_id,
        })
    out.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0))
    return out, chosen.get("grup"), []


WEEK_RE = re.compile(r"(\d+)")


def fetch_fixtures(cfg: dict) -> tuple[list, list]:
    """Takimin tum sezon maclarini ceker."""
    base = cfg["apiBaseUrl"]
    our_id = num(cfg["teamProcessId"])
    query = (f"?teamProcessId={cfg['teamProcessId']}"
             f"&leagueId={cfg['leagueId']}&seasonId={cfg['seasonId']}")
    data = api_get(base, "/api/Team/get-team-detail-matches-by-season-and-league" + query) or {}
    matches = data.get("maclar") or []
    if not matches:
        return [], ["Fikstur bos dondu."]

    out = []
    for m in matches:
        stamp = m.get("tarih") or ""
        date = stamp[:10] if len(stamp) >= 10 else None
        clock = stamp[11:16] if len(stamp) >= 16 else None
        played = bool(m.get("isPlayed"))
        week_match = WEEK_RE.search(m.get("formattedWeek") or "")
        out.append({
            "matchId": num(m.get("matchId")),
            "date": date,
            "time": clock,
            "home": m.get("takimA") or "",
            "away": m.get("takimB") or "",
            "homeScore": num(m.get("skorA")) if played else None,
            "awayScore": num(m.get("skorB")) if played else None,
            "venue": m.get("salon") or None,
            "city": m.get("sehir") or None,
            "week": num(week_match.group(1)) if week_match else None,
            "homeLogo": m.get("takimALogo") or None,
            "awayLogo": m.get("takimBLogo") or None,
            "isOurs": num(m.get("takimAId")) == our_id or num(m.get("takimBId")) == our_id,
            "isHome": bool(m.get("isHome")),
            "played": played,
        })
    out.sort(key=lambda f: (f["date"] or "9999", f["time"] or ""))
    return out, []


BOX_FIELDS = [
    ("no", "jerseyNumber"),
    ("name", "playerName"),
    ("min", "minutesPlayed"),
    ("points", "points"),
    ("rebounds", "totalRebounds"),
    ("assists", "assists"),
    ("steals", "steals"),
    ("blocks", "blocks"),
    ("turnovers", "turnovers"),
    ("fouls", "fouls"),
]


def box_rows(players: list) -> list:
    rows = []
    for p in players or []:
        row = {}
        for out_key, src_key in BOX_FIELDS:
            value = p.get(src_key)
            if out_key == "name":
                value = title_tr(value or "")
            elif out_key == "no":
                value = num(value)
            row[out_key] = value
        row["starter"] = bool(p.get("isStarter"))
        row["plusMinus"] = p.get("plusMinus")
        row["efficiency"] = p.get("efficiency")
        rows.append(row)
    return rows


def fetch_detail(cfg: dict, match_id: int) -> dict:
    """Bir macin ceyrek skorlari ve oyuncu istatistiklerini ceker."""
    base = cfg["apiBaseUrl"]
    detail: dict = {}

    summary = api_get(base, f"/api/Match/mac-ozet?matchId={match_id}") or {}
    home_q = summary.get("homeTeamScore") or []
    away_q = summary.get("awayTeamScore") or []
    quarters = []
    for i in range(max(len(home_q), len(away_q))):
        quarters.append({
            "home": home_q[i].get("score") if i < len(home_q) else None,
            "away": away_q[i].get("score") if i < len(away_q) else None,
        })
    if quarters:
        detail["quarters"] = quarters

    stats = api_get(base, f"/api/Match/mac-istatistik?matchId={match_id}") or {}
    home = box_rows((stats.get("homeTopFive") or []) + (stats.get("homeBenchPlayers") or []))
    away = box_rows((stats.get("awayTopFive") or []) + (stats.get("awayBenchPlayers") or []))
    if home or away:
        detail["boxscore"] = {"home": home, "away": away}
    return detail


def fetch_roster(cfg: dict) -> list:
    base = cfg["apiBaseUrl"]
    query = (f"?teamProcessId={cfg['teamProcessId']}"
             f"&leagueId={cfg['leagueId']}&seasonId={cfg['seasonId']}")
    players = api_get(base, "/api/Team/get-team-active-player-list-by-season-and-league" + query) or []
    out = []
    for p in players:
        birthday = p.get("birthDay") or ""
        full = f"{p.get('firstName') or ''} {p.get('lastName') or ''}".strip()
        out.append({
            "no": num(p.get("jerseyNo")),
            "name": title_tr(full),
            "position": None,
            "birthYear": num(birthday[:4]) if len(birthday) >= 4 else None,
            "height": num(p.get("height")),
            "photo": p.get("playerPhoto") or None,
            "tbfPlayerId": num(p.get("personId")),
        })
    out.sort(key=lambda p: (p["no"] is None, p["no"] or 0, p["name"]))
    return out


# ------------------------------------------------------------------- teshis
def probe(cfg: dict) -> int:
    base = cfg["apiBaseUrl"]
    checks = [
        ("puan durumu", f"/api/League/get-standings-table?leagueId={cfg['leagueId']}"),
        ("haftalar", f"/api/League/get-league-weeks?leagueId={cfg['leagueId']}&seasonId={cfg['seasonId']}"),
        ("fikstur", f"/api/Team/get-team-detail-matches-by-season-and-league"
                    f"?teamProcessId={cfg['teamProcessId']}&leagueId={cfg['leagueId']}&seasonId={cfg['seasonId']}"),
        ("kadro", f"/api/Team/get-team-active-player-list-by-season-and-league"
                  f"?teamProcessId={cfg['teamProcessId']}&leagueId={cfg['leagueId']}&seasonId={cfg['seasonId']}"),
    ]
    bad = 0
    log(f"API: {base}")
    for label, path in checks:
        try:
            data = api_get(base, path, tries=1)
        except Exception as exc:
            bad += 1
            log(f"  [HATA] {label}: {exc}")
            continue
        if isinstance(data, list):
            size = f"{len(data)} kayit"
        elif isinstance(data, dict):
            size = f"{len(data)} alan"
        else:
            size = str(type(data).__name__)
        log(f"  [OK]   {label}: {size}")
    return 1 if bad else 0


# ------------------------------------------------------------------- ana akis
def build(cfg: dict, want_details: bool) -> dict:
    errors: list[str] = []
    previous = {}
    if LEAGUE_PATH.exists():
        try:
            previous = json.loads(LEAGUE_PATH.read_text(encoding="utf-8"))
        except Exception:
            previous = {}
    old_details = {}
    for f in previous.get("fixtures") or []:
        if f.get("matchId") and (f.get("quarters") or f.get("boxscore")):
            old_details[f["matchId"]] = {k: f[k] for k in ("quarters", "boxscore") if k in f}

    try:
        standings, group, warn = fetch_standings(cfg)
        errors += warn
    except Exception as exc:
        standings, group = previous.get("standings") or [], previous.get("group")
        errors.append(f"Puan durumu cekilemedi: {exc}")

    try:
        fixtures, warn = fetch_fixtures(cfg)
        errors += warn
    except Exception as exc:
        fixtures = previous.get("fixtures") or []
        errors.append(f"Fikstur cekilemedi: {exc}")

    if want_details and fixtures:
        detail_cfg = cfg.get("matchDetail") or {}
        only_ours = detail_cfg.get("onlyOurMatches", True)
        limit = int(detail_cfg.get("maxMatches", 30))
        done = 0
        for f in fixtures:
            if not f.get("played") or not f.get("matchId"):
                continue
            if only_ours and not f.get("isOurs"):
                continue
            cached = old_details.get(f["matchId"])
            if cached:
                f.update(cached)
                continue
            if done >= limit:
                break
            try:
                f.update(fetch_detail(cfg, f["matchId"]))
                done += 1
            except Exception as exc:
                errors.append(f"Mac {f['matchId']} detayi alinamadi: {exc}")

    played = [f for f in fixtures if f.get("played")]
    return {
        "isPlaceholder": not standings and not fixtures,
        "updatedAt": now_iso(),
        "source": cfg["apiBaseUrl"],
        "season": cfg.get("season"),
        "league": cfg.get("league"),
        "group": group or cfg.get("group"),
        "ourTeamKey": cfg.get("ourTeamKey", "evolog"),
        "ourTeamId": num(cfg.get("teamProcessId")),
        "counts": {"standings": len(standings), "fixtures": len(fixtures), "played": len(played)},
        "standings": standings,
        "fixtures": fixtures,
        "errors": errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="TBF API senkronizasyonu")
    ap.add_argument("--dry-run", action="store_true", help="dosyaya yazma, ozeti goster")
    ap.add_argument("--probe", action="store_true", help="endpoint'leri dene ve cik")
    ap.add_argument("--roster", action="store_true", help="data/team.json kadrosunu da guncelle")
    ap.add_argument("--no-details", action="store_true", help="ceyrek/oyuncu istatistigi cekme")
    args = ap.parse_args()

    cfg = load_config()

    if args.probe:
        return probe(cfg)

    league = build(cfg, want_details=not args.no_details)
    counts = league["counts"]
    log(f"Puan durumu: {counts['standings']} takim · Fikstur: {counts['fixtures']} mac "
        f"({counts['played']} oynanmis) · Grup: {league['group']}")
    for err in league["errors"]:
        log(f"  uyari: {err}")

    if args.roster:
        try:
            players = fetch_roster(cfg)
            team = json.loads(TEAM_PATH.read_text(encoding="utf-8"))
            team["players"] = players
            team["league"] = f"{cfg.get('league')} - {league['group']}" if league.get("group") else cfg.get("league")
            team["season"] = cfg.get("season")
            if not args.dry_run:
                TEAM_PATH.write_text(json.dumps(team, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            log(f"Kadro: {len(players)} oyuncu")
        except Exception as exc:
            log(f"  uyari: Kadro cekilemedi: {exc}")

    if args.dry_run:
        log(json.dumps(league, ensure_ascii=False, indent=1)[:2000])
        return 0

    LEAGUE_PATH.write_text(json.dumps(league, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log(f"Yazildi: {LEAGUE_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
