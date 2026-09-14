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

# TBF, sade bir bot kimligine 403 donuyor; normal bir tarayici gibi istek yapiyoruz.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Connection": "keep-alive",
}
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


def fetch(url: str, retries: int = 4, timeout: int = 30, referer: str = None) -> str:
    headers = dict(BROWSER_HEADERS)
    if referer:
        headers["Referer"] = referer
        headers["Sec-Fetch-Site"] = "same-origin"
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            last = exc
            # 4xx tekrar denemekle duzelmez (429 haric); bosuna beklemeyelim.
            if exc.code != 429 and 400 <= exc.code < 500:
                break
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
        except (urllib.error.URLError, OSError) as exc:
            last = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"{url} alinamadi: {last}")


def describe_page(html: str) -> str:
    """Sayfa alindi ama tablo cikmadiysa: icerigin ne oldugunu tarif eder."""
    marks = []
    if "__NEXT_DATA__" in html:
        marks.append("__NEXT_DATA__ (Next.js gomulu JSON)")
    if "window.__NUXT__" in html:
        marks.append("__NUXT__ gomulu JSON")
    if "<table" in html.lower():
        marks.append("<table> var ama ayristirilamadi")
    else:
        marks.append("<table> yok (icerik JS ile yukleniyor olabilir)")
    return f"{len(html)} bayt; " + ", ".join(marks)


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


MATCH_ID_RE = re.compile(r"/mac-detay/(\d+)")


def row_match_id(links):
    """Satirdaki baglantilardan TBF mac kimligini cikarir."""
    for href in links or []:
        if not href:
            continue
        m = MATCH_ID_RE.search(href)
        if m:
            return m.group(1)
    return None


def parse_fixtures(tables):
    """Tarih + iki takim adi iceren satirlari mac olarak yorumlar."""
    fixtures = []
    seen = set()
    for table in tables:
        rows = table["rows"]
        row_links = table.get("links") or []
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

        offset = len(rows) - len(body)
        for row_index, row in enumerate(body):
            links = row_links[row_index + offset] if row_index + offset < len(row_links) else []
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
                "matchId": row_match_id(links),
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
# Mac detayi: ceyrek skorlari + oyuncu istatistikleri
# --------------------------------------------------------------------------
BOX_COLUMNS = [
    ("no", ["no", "#", "forma"]),
    ("min", ["dk", "dak", "sure", "min", "dakika"]),
    ("points", ["sayi", "say", "pts", "pt", "sy"]),
    ("rebounds", ["rib", "ribaund", "reb", "rb", "top toplama"]),
    ("assists", ["ast", "asist", "as"]),
    ("steals", ["cal", "top calma", "stl", "cl"]),
    ("blocks", ["blk", "blok", "bs"]),
    ("turnovers", ["tk", "top kaybi", "hata", "to"]),
    ("fouls", ["faul", "fl", "pf", "kf"]),
]
NAME_HEADERS = ["oyuncu", "isim", "ad soyad", "adi soyadi", "sporcu", "player"]


def _box_column(header: str):
    h = norm(header)
    if not h:
        return None
    for key, aliases in BOX_COLUMNS:
        if h in aliases:
            return key
    for key, aliases in BOX_COLUMNS:
        if any(a in h for a in aliases if len(a) > 2):
            return key
    return None


def parse_boxscore_table(table):
    """Basliginda oyuncu adi sutunu olan bir tabloyu istatistik satirlarina cevirir."""
    rows = table["rows"]
    header = rows[0]
    hnorm = [norm(c) for c in header]
    name_idx = next(
        (i for i, h in enumerate(hnorm) if any(n in h for n in NAME_HEADERS)), None
    )
    if name_idx is None:
        return []

    colmap = {}
    for i, cell in enumerate(header):
        if i == name_idx:
            continue
        key = _box_column(cell)
        if key and key not in colmap:
            colmap[key] = i
    if "points" not in colmap:
        return []

    players = []
    for row in rows[1:]:
        if len(row) <= name_idx:
            continue
        name = row[name_idx].strip()
        if not name or norm(name) in NAME_HEADERS:
            continue
        if norm(name).startswith(("toplam", "takim toplam", "total")):
            continue
        entry = {"name": name}
        for key, idx in colmap.items():
            if idx >= len(row):
                continue
            raw = row[idx].strip()
            entry[key] = raw if key == "min" and ":" in raw else to_int(raw)
        if any(entry.get(k) is not None for k in ("points", "rebounds", "assists")):
            players.append(entry)
    return players


PERIOD_RE = re.compile(r"^\s*(\d)\s*[.\-]?\s*(periyot|ceyrek|c|p)\b", re.I)


def parse_quarters(tables):
    """Periyot basliklari olan tablodan ceyrek skorlarini cikarir."""
    for table in tables:
        rows = table["rows"]
        hnorm = [norm(c) for c in rows[0]]
        idxs = [i for i, h in enumerate(hnorm) if PERIOD_RE.match(h) or h in
                ("1", "2", "3", "4") and len(hnorm) >= 5]
        if len(idxs) < 4:
            continue
        numeric_rows = []
        for row in rows[1:]:
            vals = [to_int(row[i]) if i < len(row) else None for i in idxs]
            if all(v is not None for v in vals):
                numeric_rows.append(vals)
        if len(numeric_rows) >= 2:
            home, away = numeric_rows[0], numeric_rows[1]
            return [{"home": h, "away": a} for h, a in zip(home, away)]
    return []


def fetch_match_detail(url):
    """Tek bir mac detay sayfasindan ceyrekleri ve iki takimin box score'unu okur."""
    tables = extract_tables(fetch(url))
    boxes = []
    for table in tables:
        players = parse_boxscore_table(table)
        if players:
            boxes.append(players)
    detail = {}
    quarters = parse_quarters(tables)
    if quarters:
        detail["quarters"] = quarters
    if boxes:
        detail["boxscore"] = {
            "home": boxes[0],
            "away": boxes[1] if len(boxes) > 1 else [],
        }
    return detail


def enrich_with_details(fixtures, config, errors):
    """Oynanmis maclarin detay sayfalarindan istatistikleri cekip ekler."""
    cfg = config.get("matchDetail") or {}
    if not cfg.get("enabled"):
        return 0
    base = (config.get("baseUrl") or "").rstrip("/")
    template = cfg.get("pathTemplate") or ""
    league_id = str(config.get("leagueId") or "")
    if not base or not template or not league_id:
        return 0

    limit = cfg.get("maxMatches", 30)
    done = 0
    for fix in fixtures:
        if done >= limit:
            break
        if not fix.get("matchId") or fix.get("homeScore") is None:
            continue
        if cfg.get("onlyOurMatches") and not fix.get("isOurs"):
            continue
        if fix.get("boxscore") or fix.get("quarters"):
            continue  # zaten var
        url = base + template.replace("{leagueId}", league_id).replace(
            "{matchId}", str(fix["matchId"])
        )
        try:
            detail = fetch_match_detail(url)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"mac detayi ({url}): {exc}")
            continue
        if detail:
            fix.update(detail)
            fix["detailUrl"] = url
            done += 1
    return done

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


def candidate_urls(source, config):
    """Kaynak icin denenecek adresleri sirayla verir."""
    explicit = (source.get("url") or "").strip()
    if explicit:
        return [explicit]
    base = (config.get("baseUrl") or "").rstrip("/")
    league_id = str(config.get("leagueId") or "")
    team_id = str(config.get("teamId") or "")
    if not base or not league_id:
        return []
    urls = []
    for path in source.get("candidatePaths", []):
        if "{teamId}" in path and not team_id:
            continue  # takim kimligi yoksa o adresi atla
        urls.append(
            base + path.replace("{leagueId}", league_id).replace("{teamId}", team_id)
        )
    return urls


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
            if source.get("enabled") is False:
                continue
            kind = source.get("kind")
            urls = candidate_urls(source, config)
            if not urls:
                errors.append(f"{kind}: denenecek adres uretilemedi (url/leagueId bos).")
                continue

            tried = []
            # Aday adreslerde az deneme yeterli; tek/acik adreste israrli ol.
            tries = 4 if len(urls) == 1 else 2
            for url in urls:
                try:
                    body = fetch(url, retries=tries, timeout=20)
                    if source.get("type") == "json":
                        rows = parse_json_source(json.loads(body), source)
                    else:
                        tables = extract_tables(body)
                        rows = (parse_standings(tables) if kind == "standings"
                                else parse_fixtures(tables))
                except Exception as exc:  # noqa: BLE001
                    # fetch() hatasi zaten adresi iceriyor; tekrarlamayalim.
                    reason = str(exc).split(" alinamadi: ")[-1]
                    tried.append(f"{url} -> {reason}")
                    continue

                if rows:
                    if kind == "standings":
                        standings.extend(rows)
                    else:
                        fixtures.extend(rows)
                    used_sources.append(url)
                    break
                tried.append(f"{url} -> veri yok [{describe_page(body)}]")
            else:
                errors.append(f"{kind} icin calisan adres bulunamadi: " + " | ".join(tried))

    if not args.from_file and not config.get("leagueId") and all(
        not (src.get("url") or "").strip() for src in config.get("sources", [])
    ):
        errors.append(
            "scripts/tbf_config.json icinde ne leagueId ne de kaynak URL'i tanimli."
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

    # Onceki calismada cekilmis mac detaylarini tasi, eksikleri tamamla.
    previous_detail = {
        (f.get("date"), norm(f.get("home")), norm(f.get("away"))): f
        for f in previous.get("fixtures", [])
    }
    for fix in fixtures:
        old_fix = previous_detail.get(
            (fix.get("date"), norm(fix.get("home")), norm(fix.get("away")))
        )
        if old_fix:
            for key in ("quarters", "boxscore", "detailUrl"):
                if old_fix.get(key) and not fix.get(key):
                    fix[key] = old_fix[key]

    mark_ours({"standings": standings, "fixtures": fixtures}, aliases)
    if not args.from_file:
        try:
            added = enrich_with_details(fixtures, config, errors)
            if added:
                print(f"  {added} mac detayi cekildi", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"mac detaylari cekilemedi: {exc}")

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
