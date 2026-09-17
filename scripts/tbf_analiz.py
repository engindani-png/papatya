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
        if ceyrek >= 3:                      # devre arasi saha degisimi
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
