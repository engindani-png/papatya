#!/usr/bin/env python3
"""TBF Istanbul U14 Kiz A Grubu verisini cekip data/league.json dosyasina yazar.

Sadece standart kutuphane kullanir (GitHub Actions'ta ek kurulum gerekmez).

Kullanim:
    python3 scripts/tbf_sync.py                 # config'teki kaynaklardan cek
    python3 scripts/tbf_sync.py --dry-run       # dosyaya yazma, sonucu ekrana bas
    python3 scripts/tbf_sync.py --from-file puan.html --kind standings
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "scripts", "tbf_config.json")
OUT_PATH = os.path.join(ROOT, "data", "league.json")

UA = "Mozilla/5.0 (compatible; EvologU14Bot/1.0; +https://github.com/)"
TZ = dt.timezone(dt.timedelta(hours=3))  # Turkiye saati


# --------------------------------------------------------------------------
# Yardimcilar
# --------------------------------------------------------------------------
def norm(text: str) -> str:
    """Turkce karakterleri sadelestirip kucuk harfe cevirir (eslestirme icin)."""
    if text is None:
        return ""
    text = str(text).replace("İ", "i").replace("I", "i").replace("ı", "i")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def to_int(value):
    if value is None:
        return None
    m = re.search(r"-?\d+", str(value).replace("\xa0", " "))
    return int(m.group()) if m else None


def dig(obj, path):
    """'a.b.c' yolunu sozlukte takip eder."""
    cur = obj
    for part in str(path).split("."):
        if isinstance(cur, list):
            idx = to_int(part)
            cur = cur[idx] if idx is not None and idx < len(cur) else None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


def fetch(url: str, retries: int = 4, timeout: int = 30) -> str:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Accept-Language": "tr,en;q=0.8"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            charset = "utf-8"
            try:
                charset = resp.headers.get_content_charset() or "utf-8"
            except Exception:
                pass
            return raw.decode(charset, errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            last = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"{url} alinamadi: {last}")


# --------------------------------------------------------------------------
# HTML tablo ayristirma
# --------------------------------------------------------------------------
class TableParser(HTMLParser):
    """Sayfadaki butun <table> ogelerini satir/hucre metnine cevirir."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._stack = []
        self._row = None
        self._cell = None
        self._links = []
        self._cell_link = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._stack.append({"rows": [], "links": []})
        elif tag == "tr" and self._stack:
            self._row = []
            self._links = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._cell_link = dict(attrs).get("href")
        elif tag == "a" and self._cell is not None and self._cell_link is None:
            self._cell_link = dict(attrs).get("href")
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._links.append(self._cell_link)
            self._cell = None
            self._cell_link = None
        elif tag == "tr" and self._row is not None and self._stack:
            if any(c for c in self._row):
                self._stack[-1]["rows"].append(self._row)
                self._stack[-1]["links"].append(self._links)
            self._row = None
            self._links = []
        elif tag == "table" and self._stack:
            self.tables.append(self._stack.pop())

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def close(self):
        super().close()
        while self._stack:  # kapanmamis <table> etiketleri
            self.tables.append(self._stack.pop())


def extract_tables(html: str):
    parser = TableParser()
    parser.feed(html)
    parser.close()
    return [t for t in parser.tables if len(t["rows"]) >= 2]


# --------------------------------------------------------------------------
# Puan durumu
# --------------------------------------------------------------------------
STANDING_COLUMNS = [
    ("played", ["o", "om", "oyn", "oynadigi", "macs", "mac", "g+m"]),
    ("won", ["g", "gal", "galibiyet", "w"]),
    ("lost", ["m", "mag", "maglubiyet", "l"]),
    ("pointsFor", ["a", "att", "attigi", "sayi at", "ap", "for"]),
    ("pointsAgainst", ["y", "yed", "yedigi", "sayi yed", "yp", "against"]),
    ("diff", ["av", "avr", "averaj", "fark", "+/-", "dif"]),
    ("points", ["p", "puan", "pts"]),
]


def _match_column(header: str):
    h = norm(header)
    if not h:
        return None
    for key, aliases in STANDING_COLUMNS:
        for alias in aliases:
            if h == alias or h.startswith(alias + " ") or h == alias + ".":
                return key
    for key, aliases in STANDING_COLUMNS:
        if any(alias in h for alias in aliases if len(alias) > 2):
            return key
    return None


def parse_standings(tables):
    """Basliginda takim + puan gecen tabloyu puan durumu olarak yorumlar."""
    best = None
    for table in tables:
        rows = table["rows"]
        header = rows[0]
        hnorm = [norm(c) for c in header]
        if not any("takim" in h or "kulup" in h for h in hnorm):
            continue
        if not any(h in ("p", "puan", "pts") or "puan" in h for h in hnorm):
            continue
        if len(rows) - 1 < 2:
            continue
        if best is None or len(rows) > len(best["rows"]):
            best = table
    if best is None:
        return []

    header = best["rows"][0]
    team_idx = next(
        (i for i, c in enumerate(header) if "takim" in norm(c) or "kulup" in norm(c)), 1
    )
    colmap = {}
    for i, cell in enumerate(header):
        if i == team_idx:
            continue
        key = _match_column(cell)
        if key and key not in colmap:
            colmap[key] = i

    standings = []
    for rank, row in enumerate(best["rows"][1:], start=1):
        if len(row) <= team_idx:
            continue
        team = row[team_idx].strip()
        if not team or norm(team) in ("takim", "kulup"):
            continue
        entry = {"rank": to_int(row[0]) or rank, "team": team}
        for key, idx in colmap.items():
            entry[key] = to_int(row[idx]) if idx < len(row) else None
        if entry.get("diff") is None and entry.get("pointsFor") is not None \
                and entry.get("pointsAgainst") is not None:
            entry["diff"] = entry["pointsFor"] - entry["pointsAgainst"]
        standings.append(entry)
    return standings


# --------------------------------------------------------------------------
# Fikstur / sonuclar
# --------------------------------------------------------------------------
DATE_PATTERNS = [
    (re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})"), ("d", "m", "y")),
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})"), ("y", "m", "d")),
]
TIME_RE = re.compile(r"\b([0-2]?\d)[:.]([0-5]\d)\b")
SCORE_RE = re.compile(r"\b(\d{1,3})\s*[-:]\s*(\d{1,3})\b")


def parse_date(cell: str):
    for pattern, order in DATE_PATTERNS:
        m = pattern.search(cell or "")
        if not m:
            continue
        parts = dict(zip(order, m.groups()))
        try:
            return dt.date(int(parts["y"]), int(parts["m"]), int(parts["d"])).isoformat()
        except ValueError:
            return None
    return None


def strip_date(cell: str) -> str:
    """Hucredeki tarih metnini temizler (ayni hucredeki saati okuyabilmek icin)."""
    out = cell or ""
    for pattern, _ in DATE_PATTERNS:
        out = pattern.sub(" ", out)
    return out


def parse_time(cell: str):
    m = TIME_RE.search(cell or "")
    if not m:
        return None
    hour, minute = int(m.group(1)), m.group(2)
    if hour > 23:
        return None
    return f"{hour:02d}:{minute}"


def looks_like_team(cell: str) -> bool:
    c = (cell or "").strip()
    if len(c) < 3 or len(c) > 60:
        return False
    if SCORE_RE.fullmatch(c) or parse_date(c) or TIME_RE.fullmatch(c):
        return False
    return bool(re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{3}", c))


def parse_fixtures(tables):
    """Tarih + iki takim adi iceren satirlari mac olarak yorumlar."""
    fixtures = []
    seen = set()
    for table in tables:
        rows = table["rows"]
        header_norm = [norm(c) for c in rows[0]]
        has_header = any(
            any(k in h for k in ("tarih", "saat", "ev sahibi", "misafir", "salon", "hafta"))
            for h in header_norm
        )
        body = rows[1:] if has_header else rows

        idx = {}
        if has_header:
            for i, h in enumerate(header_norm):
                if "tarih" in h and "date" not in idx:
                    idx["date"] = i
                elif "saat" in h and "time" not in idx:
                    idx["time"] = i
                elif ("ev sahibi" in h or h == "ev") and "home" not in idx:
                    idx["home"] = i
                elif ("misafir" in h or "deplasman" in h or "konuk" in h) and "away" not in idx:
                    idx["away"] = i
                elif ("salon" in h or "saha" in h or "yer" in h) and "venue" not in idx:
                    idx["venue"] = i
                elif "hafta" in h and "week" not in idx:
                    idx["week"] = i

        for row in body:
            cells = [c.strip() for c in row]
            joined = " | ".join(cells)
            date = None
            for i, c in enumerate(cells):
                if idx.get("date") is not None and i != idx["date"]:
                    continue
                date = parse_date(c)
                if date:
                    break
            if not date:
                continue

            inline_score = None
            if "home" in idx and "away" in idx and max(idx["home"], idx["away"]) < len(cells):
                home, away = cells[idx["home"]], cells[idx["away"]]
            else:
                teams = [c for c in cells if looks_like_team(c)]
                if len(teams) >= 2:
                    home, away = teams[0], teams[1]
                else:
                    # skorlu tek hucre: "Takim A 61 - 48 Takim B"
                    pair = None
                    for c in cells:
                        if parse_date(c):
                            continue
                        m = re.search(
                            r"^(.+?)\s+(\d{1,3})\s*[-:]\s*(\d{1,3})\s+(.+)$", c.strip()
                        )
                        if m and looks_like_team(m.group(1)) and looks_like_team(m.group(4)):
                            pair = (m.group(1).strip(), m.group(4).strip(),
                                    int(m.group(2)), int(m.group(3)))
                            break
                    if not pair:
                        continue
                    home, away = pair[0], pair[1]
                    inline_score = (pair[2], pair[3])
            if not looks_like_team(home) or not looks_like_team(away):
                continue

            home_score = away_score = None
            for c in cells:
                m = SCORE_RE.search(c)
                if m and not parse_date(c) and not TIME_RE.search(c):
                    home_score, away_score = int(m.group(1)), int(m.group(2))
                    break
            if home_score is None and inline_score:
                home_score, away_score = inline_score

            time_val = None
            if idx.get("time") is not None and idx["time"] < len(cells):
                time_val = parse_time(cells[idx["time"]])
            if not time_val:
                for c in cells:
                    time_val = parse_time(strip_date(c))
                    if time_val:
                        break

            venue = None
            if idx.get("venue") is not None and idx["venue"] < len(cells):
                venue = cells[idx["venue"]] or None
            if not venue:
                candidates = [
                    c for c in cells
                    if looks_like_team(c) and c not in (home, away)
                    and re.search(r"salon|spor|hall|kompleks", norm(c))
                ]
                venue = candidates[0] if candidates else None

            key = (date, norm(home), norm(away))
            if key in seen:
                continue
            seen.add(key)
            fixtures.append({
                "id": f"{date}-{norm(home)[:12]}-{norm(away)[:12]}".replace(" ", "_"),
                "week": to_int(cells[idx["week"]]) if idx.get("week") is not None
                        and idx["week"] < len(cells) else None,
                "date": date,
                "time": time_val,
                "venue": venue,
                "home": home,
                "away": away,
                "homeScore": home_score,
                "awayScore": away_score,
                "status": "played" if home_score is not None else "scheduled",
            })
    fixtures.sort(key=lambda f: (f["date"], f["time"] or "99:99"))
    return fixtures


# --------------------------------------------------------------------------
# JSON kaynak adaptoru
# --------------------------------------------------------------------------
def parse_json_source(payload, source):
    rows = dig(payload, source.get("rowsPath", "")) if source.get("rowsPath") else payload
    if not isinstance(rows, list):
        return []
    fields = source.get("fields", {})
    out = []
    for row in rows:
        item = {key: dig(row, path) for key, path in fields.items()}
        if source.get("kind") == "fixtures":
            item.setdefault("date", None)
            if item.get("date"):
                item["date"] = parse_date(str(item["date"])) or str(item["date"])[:10]
            item["homeScore"] = to_int(item.get("homeScore"))
            item["awayScore"] = to_int(item.get("awayScore"))
            item["status"] = "played" if item["homeScore"] is not None else "scheduled"
            item["id"] = f"{item.get('date')}-{norm(item.get('home'))[:12]}-{norm(item.get('away'))[:12]}"
        else:
            for key in ("played", "won", "lost", "pointsFor", "pointsAgainst", "diff", "points", "rank"):
                if key in item:
                    item[key] = to_int(item[key])
        out.append(item)
    return out


# --------------------------------------------------------------------------
# Ana akis
# --------------------------------------------------------------------------
def mark_ours(data, aliases):
    alias_norm = [norm(a) for a in aliases if a]

    def is_ours(name):
        n = norm(name)
        return any(a and a in n for a in alias_norm)

    for row in data.get("standings", []):
        row["isOurs"] = is_ours(row.get("team"))
    for fix in data.get("fixtures", []):
        fix["isOurs"] = is_ours(fix.get("home")) or is_ours(fix.get("away"))
    return data


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default if default is not None else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=CONFIG_PATH)
    ap.add_argument("--out", default=OUT_PATH)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--from-file", help="URL yerine yerel HTML/JSON dosyasi kullan")
    ap.add_argument("--kind", choices=["standings", "fixtures"], help="--from-file ile birlikte")
    args = ap.parse_args()

    config = load_json(args.config)
    previous = load_json(args.out, {})
    aliases = config.get("teamAliases", ["evolog"])

    standings, fixtures, errors, used_sources = [], [], [], []

    if args.from_file:
        if not args.kind:
            ap.error("--from-file ile --kind zorunlu")
        with open(args.from_file, encoding="utf-8") as fh:
            body = fh.read()
        tables = extract_tables(body)
        if args.kind == "standings":
            standings = parse_standings(tables)
        else:
            fixtures = parse_fixtures(tables)
        used_sources.append(f"file:{os.path.basename(args.from_file)}")
    else:
        for source in config.get("sources", []):
            url = (source.get("url") or "").strip()
            if not url or source.get("enabled") is False:
                continue
            kind = source.get("kind")
            try:
                body = fetch(url)
                if source.get("type") == "json":
                    rows = parse_json_source(json.loads(body), source)
                    if kind == "standings":
                        standings.extend(rows)
                    else:
                        fixtures.extend(rows)
                else:
                    tables = extract_tables(body)
                    if kind == "standings":
                        standings.extend(parse_standings(tables))
                    elif kind == "fixtures":
                        fixtures.extend(parse_fixtures(tables))
                used_sources.append(url)
            except Exception as exc:  # noqa: BLE001 - tek kaynak hatasi tumunu bozmasin
                errors.append(f"{kind} ({url}): {exc}")

    if not config.get("sources") or all(
        not (s.get("url") or "").strip() for s in config.get("sources", [])
    ):
        if not args.from_file:
            errors.append(
                "scripts/tbf_config.json icinde hicbir kaynak URL'i tanimli degil."
            )

    # Yeni veri bos ise eskisini koru (yayindaki uygulama bosalmasin).
    if not standings and previous.get("standings"):
        standings = previous["standings"]
        errors.append("Puan durumu cekilemedi, onceki veri korundu.")
    if not fixtures and previous.get("fixtures"):
        fixtures = previous["fixtures"]
        errors.append("Fikstur cekilemedi, onceki veri korundu.")

    # Fikstur birlestirme: ayni mac birden fazla kaynaktan gelirse skoru olani tut.
    merged = {}
    for fix in fixtures:
        key = (fix.get("date"), norm(fix.get("home")), norm(fix.get("away")))
        if key not in merged or (fix.get("homeScore") is not None
                                 and merged[key].get("homeScore") is None):
            merged[key] = {**merged.get(key, {}), **fix}
    fixtures = sorted(merged.values(), key=lambda f: (f.get("date") or "", f.get("time") or "99:99"))

    for rank, row in enumerate(standings, start=1):
        row.setdefault("rank", rank)

    data = {
        "isPlaceholder": not (standings or fixtures),
        "updatedAt": dt.datetime.now(TZ).isoformat(timespec="seconds"),
        "source": used_sources or None,
        "season": config.get("season"),
        "league": config.get("league"),
        "group": config.get("group"),
        "ourTeamKey": norm(aliases[0]) if aliases else "evolog",
        "standings": standings,
        "fixtures": fixtures,
        "errors": errors,
    }
    mark_ours(data, aliases)

    body = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if args.dry_run:
        print(body)
    else:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(body)
        print(f"Yazildi: {args.out}")
    print(
        f"  puan durumu: {len(standings)} satir, fikstur: {len(fixtures)} mac, "
        f"hata: {len(errors)}",
        file=sys.stderr,
    )
    for err in errors:
        print(f"  ! {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
