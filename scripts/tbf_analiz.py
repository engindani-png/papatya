#!/usr/bin/env python3
"""TBF'nin ayrintili mac verisini isleyip kompakt analiz dosyasi uretir.

TBF uc ayri uc veriyor ve hepsi bizim maclarimiz icin dolu geliyor:

  /api/Match/shot-chart      168 atis, her biri x-y koordinatli
  /api/Match/game-flow       693 olay (play-by-play), saat + skor + oyuncu
  /api/Match/get-match-report-with-players   iki takimin karsilastirmali yuzdeleri

Ham hallerinin toplami mac basina ~250 KB; depoya ve telefona tasinmaz. Burada
yalnizca ise yarayan kisim cikarilip ~15 KB'lik `data/<yas>/analiz/<macId>.json`
uretiliyor.

Cozulen iki inceligi not edelim:

1. **Koordinat sistemi.** `x` sahanin boyu (0-100), `y` genisligi. Takimlar
   devre arasinda saha degistirdigi icin 1-2. ceyrekte atislarimiz x≈10,
   3-4. ceyrekte x≈88 civarinda. 3 ve 4. ceyregin x degeri aynalanarak
   (100-x) butun atislar tek yari sahaya oturtuluyor.

2. **Saat geri sayiyor.** Olaylardaki `time` ceyrek icinde 10:00'dan 0:00'a
   iner; gecen sure (ceyrek-1)*10 + (10:00 - time) ile bulunuyor.
   `score` daima "ev-deplasman" sirasindadir.
"""

from __future__ import annotations

import re

CEYREK_SN = 10 * 60          # yerel liglerde ceyrek 10 dakika

# Analiz dosyasinin bicim surumu. Artirilinca senkron eski dosyalari
# yeniden uretir (bkz. tbf_sync.py).
ANALIZ_SURUM = 3

# Play-by-play olay adlarindan sut tipi cikarimi. TBF metinleri uzun
# ("2 Sayı Havada Kayarak Sıçrayarak Atış Başarısız"); veliye ve antrenore
# anlamli gelen dort gruba indiriyoruz.
SUT_TIPLERI = [
    ("Serbest atış", ("Serbest Atış",)),
    ("Üçlük", ("3 Sayı",)),
    ("Turnike", ("Turnike", "Tip-In")),
    ("Dış şut", ("Sıçrayarak",)),
]


def sure_saniye(quarter: int, saat: str) -> int:
    """q3 '07:18' -> mac basindan beri gecen saniye."""
    try:
        dk, sn = str(saat or "").split(":")
        kalan = int(dk) * 60 + int(sn)
    except (ValueError, AttributeError):
        # Okunamayan saat, ceyregin basi sayilir. (Sifir dersek olay ceyregin
        # SONUNA dusuyordu; skor akisi grafigi yanlis yerde kirilir.)
        kalan = CEYREK_SN
    q = max(1, int(quarter or 1))
    return (q - 1) * CEYREK_SN + max(0, CEYREK_SN - kalan)


def skor_ayir(metin: str) -> tuple[int, int] | None:
    """'12-9' -> (12, 9). Bozuk deger None."""
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(metin or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def atislari_topla(shot_infos: list, bizim_ev: bool) -> list:
    """Kendi atislarimiz, tek yari sahaya katlanmis: [x, y, ceyrek, isabet, no].

    Liste-icinde-liste kullaniliyor: 90+ atisin JSON boyutu bu sekilde ucte
    birine iniyor, telefonda bir maclik atis haritasi ~3 KB.
    """
    out = []
    for a in shot_infos or []:
        if bool(a.get("isHome")) != bool(bizim_ev):
            continue
        try:
            x, y = int(a.get("x")), int(a.get("y"))
        except (TypeError, ValueError):
            continue
        ceyrek = int(a.get("period") or 1)
        # Saha yarisini normalize et: potaya x=0 tarafindan bakiyoruz.
        # Ev sahibi 1-2. ceyrekte x~10, 3-4'te x~88 atiyor; deplasman tersi.
        # "x > 50 ise aynala" kurali iki takim icin de dogru sonucu veriyor;
        # ceyrege bakan eski kural deplasman atislarini yanlis yariya koyuyordu
        # (hepsi ucluk gorunuyor, saha disina dusuyordu).
        if x > 50:
            x = 100 - x
        out.append([x, y, ceyrek, 1 if a.get("isSucceed") else 0,
                    str(a.get("jerseyNumber") or "").strip()])
    return out


def _sut_tipi(action: str) -> str | None:
    if "Sayı" not in action and "Serbest Atış" not in action:
        return None
    for ad, anahtarlar in SUT_TIPLERI:
        if any(k in action for k in anahtarlar):
            return ad
    return None


def akisi_coz(events: list, bizim_ev: bool) -> dict:
    """Play-by-play'den skor akisi, top kaybi, sut tipi ve oyuncu suresi.

    Doner:
      flow      [[saniye, bizim, rakip], ...]   skor her degistiginde
      turnovers {"Kötü Pas": 47, ...}           yalniz bizim takim
      shotTypes {"Turnike": [basarili, deneme]} yalniz bizim takim
      players   {"2": {"sec": 1536, "pm": 9}}   sahada gecen sure ve +/-
      runs      en uzun kendi serimiz [sayi, "q2"]
    """
    flow = [[0, 0, 0]]
    turnovers: dict[str, int] = {}
    shot_types: dict[str, list] = {}
    sahada: dict[str, int] = {}        # forma no -> sahaya girdigi saniye
    toplam: dict[str, dict] = {}       # forma no -> {"sec", "pm"}
    onceki = (0, 0)
    seri = {"bizim": 0, "rakip": 0}
    en_uzun = [0, ""]

    def kayit(no: str) -> dict:
        return toplam.setdefault(no, {"sec": 0, "pm": 0})

    def skor_uygula(t: int, bizim_puan: int, rakip_puan: int) -> None:
        """Sahadaki herkesin +/- degerini gunceller."""
        fark = bizim_puan - rakip_puan
        if not fark:
            return
        for no in sahada:
            kayit(no)["pm"] += fark

    for e in events or []:
        action = str(e.get("action") or "")
        t = sure_saniye(e.get("quarterNumber"), e.get("time"))
        bizde = bool(e.get("isHome")) == bool(bizim_ev)
        no = str(e.get("jerseyNumber") or "").strip()

        # --- skor
        s = skor_ayir(e.get("score"))
        if s:
            bizim, rakip = (s[0], s[1]) if bizim_ev else (s[1], s[0])
            if (bizim, rakip) != onceki:
                d_biz, d_rak = bizim - onceki[0], rakip - onceki[1]
                skor_uygula(t, d_biz, d_rak)
                if d_biz and not d_rak:
                    seri["bizim"] += d_biz
                    seri["rakip"] = 0
                    if seri["bizim"] > en_uzun[0]:
                        en_uzun = [seri["bizim"], "%d. çeyrek" % int(e.get("quarterNumber") or 1)]
                elif d_rak:
                    seri["rakip"] += d_rak
                    seri["bizim"] = 0
                flow.append([t, bizim, rakip])
                onceki = (bizim, rakip)

        if not bizde:
            continue

        # --- top kaybi sebebi
        if action.startswith("Top Kaybı"):
            sebep = action.split("-", 1)[1].strip() if "-" in action else "Diğer"
            turnovers[sebep] = turnovers.get(sebep, 0) + 1

        # --- sut tipi
        tip = _sut_tipi(action)
        if tip:
            kutu = shot_types.setdefault(tip, [0, 0])
            kutu[1] += 1
            if "Başarılı" in action:
                kutu[0] += 1

        # --- oyuncu degisimi
        if no:
            if action == "Değişiklik Giren":
                sahada.setdefault(no, t)
            elif action == "Değişiklik Çıkan":
                giris = sahada.pop(no, None)
                if giris is not None:
                    kayit(no)["sec"] += max(0, t - giris)
                else:                       # ilk beste baslamis
                    kayit(no)["sec"] += t

    son = flow[-1][0] if flow else 0
    for no, giris in sahada.items():
        kayit(no)["sec"] += max(0, son - giris)

    return {"flow": flow, "turnovers": turnovers, "shotTypes": shot_types,
            "players": toplam, "run": en_uzun}


def _sayi(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        try:
            return float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return None


def takim_ozeti(report: dict, bizim_ev: bool) -> dict:
    """get-match-report-with-players ciktisindan iki takimin sayilari.

    Alan adlari '_A' (ev) ve '_B' (deplasman) ekiyle geliyor: sY=sayi,
    s20/s21=ikilik isabet/deneme, s30/s31=uclук, sA0/sA1=serbest atis,
    tR/sR/hR=ribaundlar, aS=asist, tC=top calma, bL=blok, tK=top kaybi, fA=faul.
    """
    def al(kok: str, taraf: str):
        return _sayi((report or {}).get(kok + "_" + taraf))

    def taraf_ozeti(taraf: str) -> dict:
        return {
            "sayi": al("sY", taraf),
            "iki": [al("s20", taraf), al("s21", taraf)],
            "uc": [al("s30", taraf), al("s31", taraf)],
            "sa": [al("sA0", taraf), al("sA1", taraf)],
            "rib": al("tR", taraf), "hucumRib": al("hR", taraf), "savunmaRib": al("sR", taraf),
            "asist": al("aS", taraf), "topCalma": al("tC", taraf),
            "blok": al("bL", taraf), "topKaybi": al("tK", taraf), "faul": al("fA", taraf),
        }

    biz, rakip = ("A", "B") if bizim_ev else ("B", "A")
    return {"biz": taraf_ozeti(biz), "rakip": taraf_ozeti(rakip)}


def mac_analizi(fixture: dict, shot_infos: list, events: list, report: dict) -> dict:
    """Bir macin butun analiz ciktisi (dosyaya yazilan bicim)."""
    bizim_ev = bool(fixture.get("isHome"))
    coz = akisi_coz(events, bizim_ev)
    return {
        "matchId": fixture.get("matchId"),
        "date": fixture.get("date"),
        "opp": fixture.get("away") if bizim_ev else fixture.get("home"),
        "isHome": bizim_ev,
        "score": [fixture.get("homeScore") if bizim_ev else fixture.get("awayScore"),
                  fixture.get("awayScore") if bizim_ev else fixture.get("homeScore")],
        "quarters": fixture.get("quarters") or [],
        "shots": atislari_topla(shot_infos, bizim_ev),
        "flow": coz["flow"],
        "turnovers": coz["turnovers"],
        "shotTypes": coz["shotTypes"],
        "players": coz["players"],
        "run": coz["run"],
        "team": takim_ozeti(report, bizim_ev),
    }



def mac_analizi_notr(fixture: dict, shot_infos: list, events: list, report: dict,
                     box_home: list | None = None, box_away: list | None = None) -> dict:
    """Iki takimi da kapsayan analiz (rakip analizi bunu okur).

    Ev sahibi ve deplasman ayri ayri cikarilir; hangi tarafin "biz" oldugunu
    okuyan taraf secer. Boylece ligdeki her mac ayni dosya biciminde durur ve
    rakiplerin gecmis maclarini da inceleyebiliyoruz.
    """
    ev = akisi_coz(events, True)
    dep = akisi_coz(events, False)
    takim = takim_ozeti(report, True)
    return {
        "v": ANALIZ_SURUM,
        "matchId": fixture.get("matchId"),
        "date": fixture.get("date"),
        "time": fixture.get("time"),
        "week": fixture.get("week"),
        "home": fixture.get("home"),
        "away": fixture.get("away"),
        "homeId": fixture.get("homeId"),
        "awayId": fixture.get("awayId"),
        "venue": fixture.get("venue"),
        "score": [fixture.get("homeScore"), fixture.get("awayScore")],
        "quarters": fixture.get("quarters") or [],
        "shots": {"home": atislari_topla(shot_infos, True),
                  "away": atislari_topla(shot_infos, False)},
        "flow": ev["flow"],                       # [saniye, ev, deplasman]
        "turnovers": {"home": ev["turnovers"], "away": dep["turnovers"]},
        "shotTypes": {"home": ev["shotTypes"], "away": dep["shotTypes"]},
        "players": {"home": ev["players"], "away": dep["players"]},
        "run": {"home": ev["run"], "away": dep["run"]},
        "team": {"home": takim["biz"], "away": takim["rakip"]},
        "box": {"home": box_home or [], "away": box_away or []},
        # --- derin olcumler (boxscore'da olmayanlar)
        "asist": {"home": asist_agi(events, True), "away": asist_agi(events, False)},
        "kayiptan": {"home": kayiptan_yenilen(events, True),
                     "away": kayiptan_yenilen(events, False)},
        "besli": {"home": besliler(events, True, box_home),
                  "away": besliler(events, False, box_away)},
        "faul": {"home": faul_dokumu(events, True), "away": faul_dokumu(events, False)},
    }


# =====================================================================
# Derin analiz — play-by-play'den cikan, boxscore'da olmayan olcumler
# =====================================================================

def _sut_denemesi(action: str) -> bool:
    """Saha sutu denemesi mi? (serbest atis sayilmaz — standart FGA tanimi)"""
    return ("Sayı" in action and ("Başarılı" in action or "Başarısız" in action)
            and "Serbest Atış" not in action)


def _serbest_denemesi(action: str) -> bool:
    return "Serbest Atış" in action and ("Başarılı" in action or "Başarısız" in action)


def asist_agi(events: list, bizim_ev: bool) -> dict:
    """Asistli basket orani ve "kim kime" cifti.

    TBF'de asist olayi, basketin HEMEN ARDINDAN ayni saniyede geliyor
    (olculdu). Skoru atan bir onceki olayin sahibi, asisti yapan da asist
    olayinin sahibi.
    """
    basket = 0
    asistli = 0
    ciftler: dict[tuple, int] = {}
    for i, e in enumerate(events or []):
        action = str(e.get("action") or "")
        if bool(e.get("isHome")) != bool(bizim_ev):
            continue
        if _sut_denemesi(action) and "Başarılı" in action:
            basket += 1
        if action != "Asist" or i == 0:
            continue
        onceki = events[i - 1]
        if bool(onceki.get("isHome")) != bool(bizim_ev):
            continue
        if not ("Başarılı" in str(onceki.get("action") or "")):
            continue
        asistci = str(e.get("jerseyNumber") or "").strip()
        skorcu = str(onceki.get("jerseyNumber") or "").strip()
        if not asistci or not skorcu:
            continue
        asistli += 1
        ciftler[(asistci, skorcu)] = ciftler.get((asistci, skorcu), 0) + 1

    sirali = sorted(ciftler.items(), key=lambda kv: -kv[1])[:8]
    return {"basket": basket, "asistli": asistli,
            "ciftler": [[a, s, n] for (a, s), n in sirali]}


def kayiptan_yenilen(events: list, bizim_ev: bool) -> dict:
    """Top kaybindan sonra rakibin bulduğu sayi.

    Kural: kaybin ardindan rakip sayi bulursa yazilir; arada bizim sutumuz,
    ribaundumuz ya da rakibin top kaybi varsa pozisyon degismis sayilir ve
    o kayip "sonucsuz" kabul edilir. Sut saati verisi olmadigi icin bu bir
    yaklasim; standart "points off turnovers" tanimina en yakin olani.
    """
    kayip = 0
    yenilen = 0
    olaylar = events or []
    for i, e in enumerate(olaylar):
        action = str(e.get("action") or "")
        if not action.startswith("Top Kaybı"):
            continue
        if bool(e.get("isHome")) != bool(bizim_ev):
            continue
        kayip += 1
        for j in range(i + 1, min(len(olaylar), i + 14)):
            x = olaylar[j]
            xa = str(x.get("action") or "")
            bizde = bool(x.get("isHome")) == bool(bizim_ev)
            if bizde and (_sut_denemesi(xa) or "Ribaundu" in xa or xa == "Ribaund"):
                break                      # pozisyon bize dondu
            if not bizde and xa.startswith("Top Kaybı"):
                break                      # rakip de kaybetti
            if not bizde and "Başarılı" in xa:
                if _serbest_denemesi(xa):
                    yenilen += 1
                elif "3 Sayı" in xa:
                    yenilen += 3
                    break
                else:
                    yenilen += 2
                    break
    return {"kayip": kayip, "yenilen": yenilen}


def _ilk_bes(box: list | None, events: list, bizim_ev: bool) -> list:
    """Ilk bes: once boxscore'daki starter isareti, yoksa olaylardan cikarim."""
    numaralar = [str(r.get("no")) for r in (box or []) if r.get("starter") and r.get("no") is not None]
    if len(numaralar) == 5:
        return numaralar
    # Cikarim: ilk kez "Değişiklik Giren" gormeden "Çıkan" olan ya da mac
    # basinda olaya karisan oyuncular sahada baslamistir.
    girdi: set = set()
    bulunan: list = []
    for e in events or []:
        if bool(e.get("isHome")) != bool(bizim_ev):
            continue
        no = str(e.get("jerseyNumber") or "").strip()
        action = str(e.get("action") or "")
        if not no:
            continue
        if action == "Değişiklik Giren":
            girdi.add(no)
            continue
        if no not in girdi and no not in bulunan:
            bulunan.append(no)
        if len(bulunan) >= 5:
            break
    return bulunan[:5]


def besliler(events: list, bizim_ev: bool, box: list | None = None) -> dict:
    """Sahadaki beslinin skor farki ve oyuncu bazinda sut payi (usage).

    Play-by-play'de her degisikligin saati var; sahadaki bes kisiyi her an
    yeniden kurabiliyoruz. Doner:
      lineups  [{"p": ["0","2",...], "sec", "lehte", "aleyhte"}]  en cok
               oynayan ilk 8 besli
      usage    {"2": {"fga": 8, "takim": 40}} oyuncu sahadayken takimin
               kac sutunun kac tanesini kendisi kullandi
    """
    sahada = set(_ilk_bes(box, events, bizim_ev))
    if not sahada:
        return {"lineups": [], "usage": {}}

    kutu: dict[tuple, dict] = {}
    usage: dict[str, dict] = {}
    baslangic = 0
    onceki_skor = (0, 0)

    def kayit(anahtar):
        return kutu.setdefault(anahtar, {"sec": 0, "lehte": 0, "aleyhte": 0})

    for e in events or []:
        action = str(e.get("action") or "")
        t = sure_saniye(e.get("quarterNumber"), e.get("time"))
        bizde = bool(e.get("isHome")) == bool(bizim_ev)
        no = str(e.get("jerseyNumber") or "").strip()

        s = skor_ayir(e.get("score"))
        if s:
            bizim, rakip = (s[0], s[1]) if bizim_ev else (s[1], s[0])
            if (bizim, rakip) != onceki_skor and len(sahada) == 5:
                k = kayit(tuple(sorted(sahada)))
                k["lehte"] += bizim - onceki_skor[0]
                k["aleyhte"] += rakip - onceki_skor[1]
                onceki_skor = (bizim, rakip)

        if bizde and _sut_denemesi(action):
            for oyuncu in sahada:
                u = usage.setdefault(oyuncu, {"fga": 0, "takim": 0})
                u["takim"] += 1
            if no:
                u = usage.setdefault(no, {"fga": 0, "takim": 0})
                u["fga"] += 1

        if bizde and no and action in ("Değişiklik Giren", "Değişiklik Çıkan"):
            if len(sahada) == 5:
                kayit(tuple(sorted(sahada)))["sec"] += max(0, t - baslangic)
            baslangic = t
            if action == "Değişiklik Giren":
                sahada.add(no)
            else:
                sahada.discard(no)

    if len(sahada) == 5:
        son = sure_saniye(4, "00:00")
        kayit(tuple(sorted(sahada)))["sec"] += max(0, son - baslangic)

    sirali = sorted(kutu.items(), key=lambda kv: -kv[1]["sec"])[:8]
    return {
        "lineups": [{"p": list(anahtar), "sec": v["sec"], "lehte": v["lehte"],
                     "aleyhte": v["aleyhte"]} for anahtar, v in sirali if v["sec"] > 30],
        "usage": usage,
    }


def faul_dokumu(events: list, bizim_ev: bool) -> dict:
    """Faul istatistigi: kim yapti, kim aldirdi, hangi ceyrekte.

    TBF play-by-play'inde "Kişisel Faul" faulu YAPANI, "Faul Yapılan" faulu
    UZERINE alan oyuncuyu isaretliyor (karsi takimda). Hucum faulu ayri.
    Boxscore da oyuncu basina toplam faulu veriyor ama zamanlamayi ve faul
    aldiran oyuncuyu yalniz akis veriyor — asil is orada.
    """
    yapan: dict[str, int] = {}
    aldiran: dict[str, int] = {}
    ceyrek = [0, 0, 0, 0]
    hucum = 0
    for e in events or []:
        action = str(e.get("action") or "")
        no = str(e.get("jerseyNumber") or "").strip()
        bizde = bool(e.get("isHome")) == bool(bizim_ev)
        q = int(e.get("quarterNumber") or 1)
        if action in ("Kişisel Faul", "Hücum Faul") and bizde:
            if no:
                yapan[no] = yapan.get(no, 0) + 1
            if 1 <= q <= 4:
                ceyrek[q - 1] += 1
            if action == "Hücum Faul":
                hucum += 1
        elif action == "Faul Yapılan" and bizde and no:
            aldiran[no] = aldiran.get(no, 0) + 1
    return {"yapan": yapan, "aldiran": aldiran, "ceyrek": ceyrek, "hucum": hucum}
