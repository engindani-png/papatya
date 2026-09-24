/* Rakip analizi — ligdeki her takımın oynadığı maçlardan çıkarılan profil.
 *
 * Kaynak: `data/<yaş>/analiz/<macId>.json`. Senkron, ligin bütün oynanmış
 * maçlarını nötr biçimde (ev/deplasman) üretiyor; burada seçilen takımın
 * tarafı alınıp maçlar üst üste konuyor.
 *
 * Ne veriyor:
 *  - Son maçlar, skorlar, sezon ortalamaları
 *  - Oyuncu tablosu (maç raporlarından toplanmış)
 *  - Şut bölgesi dağılımı: boya / orta mesafe / üçlük, sol-merkez-sağ
 *  - Maçtan maça tekrar eden örüntüler ve bunlardan çıkan taktik okuması
 *
 * Kural: her cümlenin yanında dayandığı sayı yazar. Veriden çıkmayan yorum
 * yapılmaz; "şu oyuncuyu şöyle savun" gibi tahminler antrenöre bırakılır.
 */
(function () {
  "use strict";

  var P = window.EvologPanel;
  var AGE = "u14";
  var AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

  var SAHA = { boy: 14, en: 15, potaX: 1.575, panoX: 1.2, boyaBoy: 5.8, boyaEn: 2.45,
               serbestR: 1.8, ucR: 6.75, ucKose: 6.6, ucKoseX: 2.99 };
  var BIRIM_X = 0.28, BIRIM_Y = 0.15;

  var durum = { lig: null, takimlar: [], secili: null, analizler: [], mac: null };

  function el(id) { return document.getElementById(id); }
  function esc(v) { return P.esc(v); }
  function gunAy(iso) {
    var p = String(iso || "").split("-");
    return p.length === 3 ? Number(p[2]) + " " + AYLAR[Number(p[1]) - 1] : (iso || "");
  }
  function yuzde(pay, payda) { return payda ? Math.round((100 * pay) / payda) : 0; }
  function ort(liste) {
    var v = liste.filter(function (x) { return typeof x === "number"; });
    return v.length ? v.reduce(function (a, b) { return a + b; }, 0) / v.length : 0;
  }
  function bir(v) { return Math.round(v * 10) / 10; }

  /** Atışın bölgesi: metre cinsinden potaya uzaklık ve yana sapma ile. */
  function bolge(a) {
    var mx = a[0] * BIRIM_X;                 // dip çizgiden uzaklık
    var my = (a[1] - 50) * BIRIM_Y;          // merkezden sapma (− sol, + sağ)
    var d = Math.sqrt(Math.pow(mx - SAHA.potaX, 2) + Math.pow(my, 2));
    var alan = (Math.abs(my) <= SAHA.boyaEn && mx <= SAHA.boyaBoy) ? "Boya içi"
      : (d >= SAHA.ucR - 0.15 ? "Üçlük" : "Orta mesafe");
    var taraf = my < -1.5 ? "Sol" : (my > 1.5 ? "Sağ" : "Merkez");
    return { alan: alan, taraf: taraf, uzaklik: d };
  }

  // ------------------------------------------------------------- yükleme
  function ligYukle() {
    return fetch("/data/" + AGE + "/league.json", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (lig) {
        durum.lig = lig;
        var adlar = {};
        (lig.standings || []).forEach(function (s) { adlar[s.team] = true; });
        (lig.leagueFixtures || []).forEach(function (f) { adlar[f.home] = true; adlar[f.away] = true; });
        durum.takimlar = Object.keys(adlar).filter(Boolean).sort(function (a, b) {
          return a.localeCompare(b, "tr");
        });
        // Sıradaki rakip: tarihi kesin ilk maçımızdaki karşı taraf.
        var siradaki = (lig.fixtures || []).filter(function (f) {
          return !f.played && f.isOurs && f.dateConfirmed !== false;
        })[0];
        // isHome = BIZ ev sahibiyiz demek; rakip o zaman karsi taraftir.
        durum.siradakiRakip = siradaki ? (siradaki.isHome ? siradaki.away : siradaki.home) : null;
        // Kendi takimimiz listede en sonda dursun; ekran rakipler icin.
        var biz = (durum.lig.teamName || "").toLowerCase();
        durum.takimlar.sort(function (a, b) {
          var ao = a === durum.siradakiRakip ? 0 : 1, bo = b === durum.siradakiRakip ? 0 : 1;
          var ab = /evolog|daçka|dacka/i.test(a) ? 1 : 0, bb = /evolog|daçka|dacka/i.test(b) ? 1 : 0;
          return (ab - bb) || (ao - bo) || a.localeCompare(b, "tr");
        });
      });
  }

  /**
   * Seçilen takımın ligde oynadığı BÜTÜN maçlar — analizi olsun olmasın.
   *
   * Eskiden "Maçları" listesi yalnız analizi ÜRETİLMİŞ maçları gösteriyordu.
   * Sonuç: ligde oynanmış ama henüz analiz dosyası çıkmamış maçlar koç için
   * yok hükmündeydi (canlıda 9 oynanmış maçın 2'si böyleydi). Skor zaten
   * league.json'da duruyor; gizlemenin sebebi yoktu.
   */
  function takiminMaclari(ad) {
    var analizli = (durum.lig.analiz || []);
    return (durum.lig.leagueFixtures || []).filter(function (f) {
      return f.played && (f.home === ad || f.away === ad);
    }).sort(function (a, b) { return String(b.date).localeCompare(String(a.date)); })
      .map(function (f) {
        var evMi = f.home === ad;
        return {
          matchId: f.matchId,
          date: f.date,
          rakip: evMi ? f.away : f.home,
          evMi: evMi,
          score: evMi ? [f.homeScore, f.awayScore] : [f.awayScore, f.homeScore],
          analizVar: analizli.indexOf(f.matchId) !== -1,
        };
      });
  }

  /** Seçilen takımın oynadığı, analizi olan bütün maçlar. */
  function takimAnalizleri(ad) {
    var analizli = (durum.lig.analiz || []);
    var maclar = (durum.lig.leagueFixtures || []).filter(function (f) {
      return f.played && analizli.indexOf(f.matchId) !== -1 &&
        (f.home === ad || f.away === ad);
    }).sort(function (a, b) { return String(b.date).localeCompare(String(a.date)); });

    return Promise.all(maclar.map(function (f) {
      return fetch("/data/" + AGE + "/analiz/" + f.matchId + ".json", { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (a) { return yonlendir(a, a.home === ad); })
        .catch(function () { return null; });
    })).then(function (liste) {
      return liste.filter(Boolean);
    });
  }

  /** Nötr dosyayı "o takım / karşısı" diline çevirir. */
  function yonlendir(a, evMi) {
    var b = evMi ? "home" : "away", r = evMi ? "away" : "home";
    return {
      matchId: a.matchId, date: a.date, evMi: evMi,
      takim: evMi ? a.home : a.away,
      rakip: evMi ? a.away : a.home,
      score: [a.score[evMi ? 0 : 1], a.score[evMi ? 1 : 0]],
      quarters: (a.quarters || []).map(function (q) {
        return evMi ? { lehte: q.home, aleyhte: q.away } : { lehte: q.away, aleyhte: q.home };
      }),
      shots: (a.shots || {})[b] || [],
      flow: (a.flow || []).map(function (f) {
        return [f[0], evMi ? f[1] : f[2], evMi ? f[2] : f[1]];
      }),
      turnovers: (a.turnovers || {})[b] || {},
      shotTypes: (a.shotTypes || {})[b] || {},
      players: (a.players || {})[b] || {},
      run: (a.run || {})[b] || [0, ""],
      team: (a.team || {})[b] || {},
      karsi: (a.team || {})[r] || {},
      box: (a.box || {})[b] || [],
      karsiAtislar: (a.shots || {})[r] || [],
      asist: (a.asist || {})[b] || null,
      kayiptan: (a.kayiptan || {})[b] || null,
      faul: (a.faul || {})[b] || null,
      gecis: (a.gecis || {})[b] || null,
      ikinciSans: (a.ikinciSans || {})[b] || null
    };
  }

  // ------------------------------------------------------------- hesaplar
  function bolgeDokumu(analizler) {
    var kutular = {};
    analizler.forEach(function (a) {
      a.shots.forEach(function (s) {
        var b = bolge(s);
        var anahtar = b.alan;
        var k = kutular[anahtar] || (kutular[anahtar] = { deneme: 0, isabet: 0,
          Sol: 0, Merkez: 0, Sağ: 0 });
        k.deneme++;
        if (s[3]) k.isabet++;
        k[b.taraf]++;
      });
    });
    return kutular;
  }

  function taraflar(analizler) {
    var t = { Sol: 0, Merkez: 0, Sağ: 0 };
    analizler.forEach(function (a) {
      a.shots.forEach(function (s) { t[bolge(s).taraf]++; });
    });
    return t;
  }

  function oyuncuTablosu(analizler) {
    var havuz = {};
    analizler.forEach(function (a) {
      (a.box || []).forEach(function (r) {
        var ad = (r.name || "").trim();
        if (!ad) return;
        var k = havuz[ad] || (havuz[ad] = { ad: ad, no: r.no, mac: 0, sayi: 0, rib: 0,
          ast: 0, cal: 0, dk: 0 });
        k.mac++;
        k.sayi += r.points || 0;
        k.rib += r.rebounds || 0;
        k.ast += r.assists || 0;
        k.cal += r.steals || 0;
        var m = String(r.min || "").split(":");
        k.dk += m.length === 2 ? Number(m[0]) + Number(m[1]) / 60 : 0;
        if (k.no == null) k.no = r.no;
      });
      // Şut sayısı: atış haritasından forma numarasına göre
      a.shots.forEach(function (s) {
        var no = s[4];
        Object.keys(havuz).forEach(function (ad) {
          if (String(havuz[ad].no) === String(no)) {
            havuz[ad].sut = (havuz[ad].sut || 0) + 1;
            if (s[3]) havuz[ad].isabet = (havuz[ad].isabet || 0) + 1;
          }
        });
      });
    });
    return Object.keys(havuz).map(function (ad) { return havuz[ad]; })
      .sort(function (x, y) { return (y.sayi / y.mac) - (x.sayi / x.mac); });
  }

  /** Bir takımın maçlarındaki sayıları toplar (dört faktör hesabı için). */
  function toplaTaraf(analizler, secici) {
    var t = { iki: [0, 0], uc: [0, 0], sa: [0, 0], hucumRib: 0, savunmaRib: 0,
              topKaybi: 0, rib: 0, asist: 0, sayi: 0 };
    analizler.forEach(function (a) {
      var k = secici(a);
      ["iki", "uc", "sa"].forEach(function (alan) {
        t[alan][0] += ((k[alan] || [])[0] || 0);
        t[alan][1] += ((k[alan] || [])[1] || 0);
      });
      ["hucumRib", "savunmaRib", "topKaybi", "rib", "asist", "sayi"].forEach(function (alan) {
        t[alan] += (k[alan] || 0);
      });
    });
    return t;
  }

  /** Sayılardan çıkan, sayıyla birlikte yazılan taktik okuması.
   *
   *  Dayanaklar: şut bölgeleri ve kanat dağılımı (atış koordinatları),
   *  pozisyon bazlı verimlilik ve tempo, Dört Faktör, top kaybından yenen
   *  sayı, asistli basket oranı, faul profili, çeyrek profili ve kimin şut
   *  kullandığı. Hepsi maç analizi dosyalarından; her cümlenin yanında
   *  dayandığı sayı yazılır. */
  function okuma(analizler, kutular, oyuncular) {
    var A2 = window.EvologAnaliz;
    var satirlar = [];
    var macSayisi = analizler.length;
    var toplamSut = Object.keys(kutular).reduce(function (t, k) { return t + kutular[k].deneme; }, 0);
    if (!toplamSut) return satirlar;

    // --- pozisyon bazlı verimlilik ve tempo
    var kendi = toplaTaraf(analizler, function (a) { return a.team; });
    var karsi = toplaTaraf(analizler, function (a) { return a.karsi; });
    var poz = A2.pozisyon(kendi), pozR = A2.pozisyon(karsi);
    var atilan = analizler.reduce(function (t, a) { return t + (a.score[0] || 0); }, 0);
    var yenilen = analizler.reduce(function (t, a) { return t + (a.score[1] || 0); }, 0);
    if (poz && pozR) {
      var hucum = Math.round(A2.rating(atilan, poz));
      var savunma = Math.round(A2.rating(yenilen, pozR));
      var tempo = Math.round((poz + pozR) / (2 * macSayisi));
      satirlar.push(["Verimlilik",
        "100 pozisyonda " + hucum + " sayı üretiyor, " + savunma + " yiyor. " +
        "Tempo maç başına " + tempo + " pozisyon — " +
        (tempo >= 95 ? "hızlı oynuyor, geri dönüş disiplini belirleyici."
                     : "kontrollü oynuyor, yarı saha savunması öne çıkacak.")]);

      var ff = A2.dortFaktor(kendi, karsi);
      if (ff.tov >= 0.22) {
        satirlar.push(["Topu kaybediyor",
          "Pozisyonlarının %" + Math.round(ff.tov * 100) + "'inde top kaybı (" +
          kendi.topKaybi + " kayıp / " + macSayisi + " maç). Baskı karşılık verir."]);
      }
      if (ff.efg <= 0.30) {
        satirlar.push(["Şut isabeti düşük",
          "eFG %" + Math.round(ff.efg * 100) + ". Boyayı kapatıp dış şuta zorlamak " +
          "sayılarını kurutur."]);
      } else if (ff.efg >= 0.42) {
        satirlar.push(["İsabetli takım",
          "eFG %" + Math.round(ff.efg * 100) + ". Açık şut vermemek kritik."]);
      }
      if (ff.ftr >= 0.25) {
        satirlar.push(["Faul aldırıyor",
          "Her 100 şuta " + Math.round(ff.ftr * 100) + " serbest atış. Temassız savunma şart."]);
      }
    }

    // --- top kaybından yenen sayı (bizim için fırsat)
    var kayip = 0, kayiptanYenilen = 0;
    analizler.forEach(function (a) {
      if (a.kayiptan) { kayip += a.kayiptan.kayip; kayiptanYenilen += a.kayiptan.yenilen; }
    });
    if (kayip && kayiptanYenilen) {
      satirlar.push(["Kayıptan sayı yiyor",
        "Maç başına " + bir(kayip / macSayisi) + " top kaybı, bunlardan " +
        bir(kayiptanYenilen / macSayisi) + " sayı yiyor. Hızlı hücum fırsatı burada."]);
    }

    // --- asistli basket oranı: top çeviriyor mu, bireysel mi?
    var asistli = 0, basket = 0;
    analizler.forEach(function (a) {
      if (a.asist) { asistli += a.asist.asistli; basket += a.asist.basket; }
    });
    if (basket >= 10) {
      var oran = yuzde(asistli, basket);
      satirlar.push([oran >= 50 ? "Top çeviriyor" : "Bireysel hücum",
        "Basketlerinin %" + oran + "'i asistli (" + asistli + "/" + basket + "). " +
        (oran >= 50 ? "Pas hatlarını kesmek ve yardımı erken vermek gerekiyor."
                    : "Topu taşıyan oyuncuyu kuşatmak hücumu durdurur.")]);
    }

    var boya = kutular["Boya içi"] || { deneme: 0, isabet: 0 };
    var uc = kutular["Üçlük"] || { deneme: 0, isabet: 0 };
    var orta = kutular["Orta mesafe"] || { deneme: 0, isabet: 0 };

    var boyaPay = yuzde(boya.deneme, toplamSut);
    var ucPay = yuzde(uc.deneme, toplamSut);
    if (boyaPay >= 55) {
      satirlar.push(["Hücum potaya dayalı",
        "Şutların %" + boyaPay + "'i boya içinden (" + boya.deneme + "/" + toplamSut +
        "). Boya savunması ve yardım rotasyonu belirleyici olacak."]);
    } else if (ucPay >= 25) {
      satirlar.push(["Dış şut arıyor",
        "Şutların %" + ucPay + "'i üçlük (" + uc.deneme + " deneme, %" +
        yuzde(uc.isabet, uc.deneme) + " isabet). Çıkışları kapatmak gerekiyor."]);
    } else {
      satirlar.push(["Dengeli dağılım",
        "Boya %" + boyaPay + " · orta mesafe %" + yuzde(orta.deneme, toplamSut) +
        " · üçlük %" + ucPay + "."]);
    }

    var t = taraflar(analizler);
    var enCok = ["Sol", "Merkez", "Sağ"].sort(function (a, b) { return t[b] - t[a]; })[0];
    var enCokPay = yuzde(t[enCok], t.Sol + t.Merkez + t.Sağ);
    if (enCokPay >= 42 && enCok !== "Merkez") {
      satirlar.push([enCok + " taraf ağırlıklı",
        "Şutların %" + enCokPay + "'i " + enCok.toLowerCase() +
        " taraftan geldi. O kanatta yardımı erken vermek mantıklı."]);
    }

    var hucumRib = ort(analizler.map(function (a) { return a.team.hucumRib; }));
    if (hucumRib >= 12) {
      satirlar.push(["İkinci şansa yükleniyor",
        "Maç başına " + bir(hucumRib) + " hücum ribaundu. Şut sonrası blok-out şart."]);
    }

    var topKaybi = ort(analizler.map(function (a) { return a.team.topKaybi; }));
    var sebepler = {};
    analizler.forEach(function (a) {
      Object.keys(a.turnovers || {}).forEach(function (k) {
        sebepler[k] = (sebepler[k] || 0) + a.turnovers[k];
      });
    });
    var enSik = Object.keys(sebepler).sort(function (a, b) { return sebepler[b] - sebepler[a]; })[0];
    if (topKaybi >= 18 && enSik) {
      satirlar.push(["Baskıda top kaybediyor",
        "Maç başına " + bir(topKaybi) + " top kaybı; en sık sebep " +
        enSik.toLowerCase() + " (" + sebepler[enSik] + " kez). Yarı saha baskısı karşılık verebilir."]);
    }

    // Çeyrek profili: hangi çeyrekte açılıyor / düşüyor
    var ceyrekOrt = [0, 1, 2, 3].map(function (i) {
      return ort(analizler.map(function (a) {
        return a.quarters[i] ? a.quarters[i].lehte : null;
      }));
    });
    var enIyi = ceyrekOrt.indexOf(Math.max.apply(null, ceyrekOrt));
    var enKotu = ceyrekOrt.indexOf(Math.min.apply(null, ceyrekOrt));
    if (Math.max.apply(null, ceyrekOrt) - Math.min.apply(null, ceyrekOrt) >= 4) {
      satirlar.push(["Çeyrek profili",
        (enIyi + 1) + ". çeyrekte ortalama " + bir(ceyrekOrt[enIyi]) + " sayı atıyor, " +
        (enKotu + 1) + ". çeyrekte " + bir(ceyrekOrt[enKotu]) + ". " +
        (enIyi >= 2 ? "Maçın ikinci yarısında açılıyor." : "Maça hızlı başlıyor.")]);
    }

    // --- faul yükü: kimin üstüne gidilir
    var faulYapan = {}, faulToplam = 0, faulMac = 0;
    analizler.forEach(function (a) {
      if (!a.faul) return;
      faulMac++;
      Object.keys(a.faul.yapan || {}).forEach(function (no) {
        faulYapan[no] = (faulYapan[no] || 0) + a.faul.yapan[no];
        faulToplam += a.faul.yapan[no];
      });
    });
    if (faulMac && faulToplam) {
      var enCok = Object.keys(faulYapan).sort(function (x, y) {
        return faulYapan[y] - faulYapan[x];
      })[0];
      satirlar.push(["Faul yükü",
        "Maç başına " + bir(faulToplam / faulMac) + " faul; en çok " + enCok +
        " numara (" + bir(faulYapan[enCok] / faulMac) + "/maç). " +
        "O oyuncunun üstüne gitmek erken faul yükü yaratır."]);
    }

    // --- geçiş profili: koşan takım mı, yarı sahada mı oynuyor
    var gd = { deneme: 0, isabet: 0, sayi: 0 }, gy = { deneme: 0, isabet: 0 };
    var isaRib = 0, isaDeneme = 0, isaSayi = 0, gMac = 0;
    analizler.forEach(function (a) {
      if (a.gecis) {
        gMac++;
        gd.deneme += a.gecis.gecis.deneme; gd.isabet += a.gecis.gecis.isabet;
        gd.sayi += a.gecis.gecis.sayi;
        gy.deneme += a.gecis.yariSaha.deneme; gy.isabet += a.gecis.yariSaha.isabet;
      }
      if (a.ikinciSans) {
        isaRib += a.ikinciSans.ribaund; isaDeneme += a.ikinciSans.deneme;
        isaSayi += a.ikinciSans.sayi;
      }
    });
    if (gMac && (gd.deneme + gy.deneme) >= 10) {
      var pay = yuzde(gd.deneme, gd.deneme + gy.deneme);
      var gY = yuzde(gd.isabet, gd.deneme);
      satirlar.push([pay >= 45 ? "Koşan takım" : "Yarı sahada oynuyor",
        "Şutlarının %" + pay + "'i geçişten (maç başına " + bir(gd.sayi / gMac) +
        " sayı, %" + gY + " isabet). " +
        (pay >= 45
          ? "Şut sonrası geri dönüş ve top kaybından sonra denge şart."
          : "Hücumu kurup oynuyorlar; yarı saha savunması belirleyici olacak.")]);
    }
    if (isaRib >= 8) {
      satirlar.push(["İkinci şans",
        "Hücum ribaundlarının %" + yuzde(isaDeneme, isaRib) + "'ini şuta çeviriyor, " +
        "maç başına " + bir(isaSayi / Math.max(1, gMac)) + " ikinci şans sayısı. " +
        (yuzde(isaDeneme, isaRib) >= 60
          ? "Şut sonrası blok-out ihmal edilirse pahalıya patlar."
          : "Ribaundu alıyor ama şuta çevirmekte zorlanıyor.")]);
    }

    // --- neyi veriyor: rakiplerinin ona karşı en verimli olduğu bölge
    var verdigi = { "Boya içi": [0, 0], "Orta mesafe": [0, 0], "Üçlük": [0, 0] };
    analizler.forEach(function (a) {
      (a.karsiAtislar || []).forEach(function (s2) {
        var b = bolge(s2);
        if (!verdigi[b.alan]) return;
        verdigi[b.alan][1]++;
        if (s2[3]) verdigi[b.alan][0]++;
      });
    });
    var acikBolge = Object.keys(verdigi).filter(function (k) {
      return verdigi[k][1] >= 8;
    }).sort(function (x, y) {
      return (verdigi[y][0] / verdigi[y][1]) - (verdigi[x][0] / verdigi[x][1]);
    })[0];
    if (acikBolge && yuzde(verdigi[acikBolge][0], verdigi[acikBolge][1]) >= 33) {
      satirlar.push(["Neyi veriyor",
        "Rakipleri " + acikBolge.toLowerCase() + " bölgesinden %" +
        yuzde(verdigi[acikBolge][0], verdigi[acikBolge][1]) + " atmış (" +
        verdigi[acikBolge][0] + "/" + verdigi[acikBolge][1] +
        "). Hücumu oraya taşımak mantıklı."]);
    }

    // --- örneklem uyarısı: az maçta oran okumak yanıltır
    if (macSayisi < 3) {
      satirlar.push(["Dikkat · örneklem",
        macSayisi + " maç üzerinden çıkarıldı. Oranlar doğru ama " +
        "eğilim demek için en az 3 maç gerekiyor; TBF yeni maç raporu " +
        "yayımladıkça bu okuma kendiliğinden güncellenir."]);
    }

    var sutcu = oyuncular.filter(function (o) { return o.sut; })
      .sort(function (a, b) { return b.sut - a.sut; }).slice(0, 2);
    if (sutcu.length) {
      satirlar.push(["Hücum kimden geçiyor",
        sutcu.map(function (o) {
          return (o.no != null ? o.no + " " : "") + o.ad + " (" + o.sut + " şut, " +
            bir(o.sayi / o.mac) + " sayı ort.)";
        }).join(" · ") + ". " + macSayisi + " maçın tamamında böyle."]);
    }

    return satirlar;
  }

  /** Pozisyon bazlı profil + dört faktör + neyi verdiği (savunma profili). */
  function verimlilikBolumu(analizler) {
    var A2 = window.EvologAnaliz;
    var poz = 0, pozR = 0, atilan = 0, yenilen = 0, n = 0;
    analizler.forEach(function (a) {
      var p1 = A2.pozisyon(a.team), p2 = A2.pozisyon(a.karsi);
      if (!p1 || !p2) return;
      poz += p1; pozR += p2; atilan += a.score[0]; yenilen += a.score[1]; n++;
    });
    if (!n) return "";

    // Dört faktör için maç toplamları (okuma() ile aynı fonksiyon).
    var kendi = toplaTaraf(analizler, function (a) { return a.team; });
    var karsi = toplaTaraf(analizler, function (a) { return a.karsi; });

    // Savunma profili: rakiplerinin ONA KARŞI attığı şutların bölge dağılımı.
    var verdigi = { "Boya içi": { d: 0, i: 0 }, "Orta mesafe": { d: 0, i: 0 },
                    "Üçlük": { d: 0, i: 0 } };
    analizler.forEach(function (a) {
      (a.karsiAtislar || []).forEach(function (s2) {
        var b = bolge(s2);
        if (!verdigi[b.alan]) return;
        verdigi[b.alan].d++;
        if (s2[3]) verdigi[b.alan].i++;
      });
    });
    var verdigiToplam = Object.keys(verdigi).reduce(function (t, k) {
      return t + verdigi[k].d;
    }, 0);

    var asistli = 0, basket = 0, kayip = 0, kayiptanYenilen = 0;
    analizler.forEach(function (a) {
      if (a.asist) { asistli += a.asist.asistli; basket += a.asist.basket; }
      if (a.kayiptan) { kayip += a.kayiptan.kayip; kayiptanYenilen += a.kayiptan.yenilen; }
    });

    return "<h2>Verimlilik</h2>" +
      '<div class="kutular">' +
        '<div class="kutu"><b>' + Math.round(A2.rating(atilan, poz)) +
          "</b><span>Hücum ratingi</span></div>" +
        '<div class="kutu"><b>' + Math.round(A2.rating(yenilen, pozR)) +
          "</b><span>Savunma ratingi</span></div>" +
        '<div class="kutu"><b>' + Math.round((poz + pozR) / (2 * n)) +
          "</b><span>Tempo</span></div>" +
        '<div class="kutu"><b>%' + yuzde(asistli, basket) +
          "</b><span>Asistli basket</span></div>" +
        '<div class="kutu"><b>' + bir(kayiptanYenilen / n) +
          "</b><span>Kayıptan yediği</span></div>" +
        '<div class="kutu"><b>' + bir(kayip / n) +
          "</b><span>Top kaybı</span></div>" +
      "</div>" +
      A2.dortFaktorTablosu(kendi, karsi, "Rakip", "Karşısı") +
      '<p class="aciklama">' + n + " maçın toplamı üzerinden. Pozisyon tahmini: " +
      "şut denemesi − hücum ribaundu + top kaybı + 0,44 × serbest atış.</p>" +

      gecisProfili(analizler) +
      faulProfili(analizler) +

      (verdigiToplam
        ? "<h2>Neyi veriyor</h2>" +
          '<table class="bolge"><thead><tr><th>Rakiplerinin attığı</th><th>Deneme</th>' +
          "<th>İsabet</th><th>Pay</th></tr></thead><tbody>" +
          Object.keys(verdigi).map(function (k) {
            var v = verdigi[k];
            var pay = yuzde(v.d, verdigiToplam);
            return "<tr" + (v.d && yuzde(v.i, v.d) >= 45 ? ' class="vurgu"' : "") +
              "><td>" + esc(k) + "</td><td>" + v.d + "</td><td><b>%" +
              yuzde(v.i, v.d) + "</b></td><td>%" + pay + "</td></tr>";
          }).join("") + "</tbody></table>" +
          '<p class="aciklama">Bu takıma karşı oynayanların attığı şutlar. Yüksek ' +
          "isabet verdiği bölge, bizim arayacağımız bölgedir.</p>"
        : "");
  }

  /** Rakibin geçiş ve ikinci şans profili: koşan takım mı, ribaundu
   *  şuta çeviriyor mu. */
  function gecisProfili(analizler) {
    var gd = { deneme: 0, isabet: 0, sayi: 0 };
    var gy = { deneme: 0, isabet: 0, sayi: 0 };
    var isa = { deneme: 0, isabet: 0, sayi: 0, ribaund: 0, tipin: 0 };
    var mac = 0;
    analizler.forEach(function (a) {
      if (a.gecis) {
        mac++;
        ["deneme", "isabet", "sayi"].forEach(function (k) {
          gd[k] += a.gecis.gecis[k];
          gy[k] += a.gecis.yariSaha[k];
        });
      }
      if (a.ikinciSans) {
        ["deneme", "isabet", "sayi", "ribaund", "tipin"].forEach(function (k) {
          isa[k] += (a.ikinciSans[k] || 0);
        });
      }
    });
    if (!mac) return "";
    var toplam = gd.deneme + gy.deneme;

    return "<h2>Geçiş ve ikinci şans</h2>" +
      '<div class="kutular">' +
        '<div class="kutu"><b>%' + yuzde(gd.deneme, toplam) +
          "</b><span>Şutu geçişten</span></div>" +
        '<div class="kutu"><b>%' + yuzde(gd.isabet, gd.deneme) +
          "</b><span>Geçişte isabet</span></div>" +
        '<div class="kutu"><b>' + bir(gd.sayi / mac) +
          "</b><span>Geçişten sayı</span></div>" +
        '<div class="kutu"><b>%' + yuzde(gy.isabet, gy.deneme) +
          "</b><span>Yarı sahada</span></div>" +
        '<div class="kutu"><b>%' + yuzde(isa.deneme, isa.ribaund) +
          "</b><span>Ribaundu şuta</span></div>" +
        '<div class="kutu"><b>' + bir(isa.sayi / mac) +
          "</b><span>İkinci şans sayı</span></div>" +
      "</div>" +
      '<p class="aciklama">Geçiş: topu kazandıktan sonra 7 saniye içinde atılan şut. ' +
      "İkinci şans: kendi hücum ribaundundan 8 saniye içinde çıkan şut.</p>";
  }

  /** Rakibin faul profili: kim faule giriyor, kim faul aldırıyor. */
  function faulProfili(analizler) {
    var yapan = {}, aldiran = {}, ceyrek = [0, 0, 0, 0], mac = 0;
    analizler.forEach(function (a) {
      if (!a.faul) return;
      mac++;
      Object.keys(a.faul.yapan || {}).forEach(function (no) {
        yapan[no] = (yapan[no] || 0) + a.faul.yapan[no];
      });
      Object.keys(a.faul.aldiran || {}).forEach(function (no) {
        aldiran[no] = (aldiran[no] || 0) + a.faul.aldiran[no];
      });
      (a.faul.ceyrek || []).forEach(function (n, i) { ceyrek[i] += n; });
    });
    if (!mac) return "";
    var toplam = Object.keys(yapan).reduce(function (t, k) { return t + yapan[k]; }, 0);
    var sirala = function (nesne) {
      return Object.keys(nesne).map(function (no) { return { no: no, n: nesne[no] }; })
        .sort(function (x, y) { return y.n - x.n; }).slice(0, 5);
    };
    var enCokYapan = sirala(yapan), enCokAldiran = sirala(aldiran);

    return "<h2>Faul profili</h2>" +
      '<div class="kutular">' +
        '<div class="kutu"><b>' + bir(toplam / mac) + "</b><span>Maç başına faul</span></div>" +
        '<div class="kutu"><b>' + ceyrek.map(function (n) { return Math.round(n / mac); }).join("·") +
          "</b><span>Çeyrek dağılımı</span></div>" +
        '<div class="kutu"><b>' + (enCokYapan[0] ? enCokYapan[0].no : "–") +
          "</b><span>En çok faul yapan</span></div>" +
      "</div>" +
      (enCokYapan.length
        ? '<p class="aciklama"><b>Faule giren oyuncuları:</b> ' + enCokYapan.map(function (x) {
            return x.no + " (" + bir(x.n / mac) + "/maç)";
          }).join(" · ") + ". Bu oyuncuların üstüne gitmek faul yükü yaratır.</p>"
        : "") +
      (enCokAldiran.length
        ? '<p class="aciklama"><b>Faul aldıranları:</b> ' + enCokAldiran.map(function (x) {
            return x.no + " (" + bir(x.n / mac) + "/maç)";
          }).join(" · ") + ". Bunlara temassız savunmak gerekiyor.</p>"
        : "");
  }

  /** Birden çok maçın atışları tek yarı sahada. */
  function atisHaritasi(analizler) {
    var m2p = 20, W = SAHA.en * m2p, H = SAHA.boy * m2p;
    function px(y) { return (y + SAHA.en / 2) * m2p; }
    function py(x) { return x * m2p; }
    var ciz = ['<rect x="0" y="0" width="' + W + '" height="' + H +
      '" fill="none" stroke="rgba(232,240,236,.18)"/>',
      '<rect x="' + px(-SAHA.boyaEn) + '" y="0" width="' + (SAHA.boyaEn * 2 * m2p) +
      '" height="' + py(SAHA.boyaBoy) + '" fill="none" stroke="rgba(232,240,236,.18)"/>',
      '<circle cx="' + px(0) + '" cy="' + py(SAHA.boyaBoy) + '" r="' + (SAHA.serbestR * m2p) +
      '" fill="none" stroke="rgba(232,240,236,.18)"/>',
      '<circle cx="' + px(0) + '" cy="' + py(SAHA.potaX) + '" r="' + (0.225 * m2p) +
      '" fill="none" stroke="rgba(232,240,236,.3)"/>'];
    var r = SAHA.ucR * m2p;
    ciz.push('<path d="M ' + px(-SAHA.ucKose) + " " + py(SAHA.ucKoseX) + " A " + r + " " + r +
      " 0 0 0 " + px(SAHA.ucKose) + " " + py(SAHA.ucKoseX) +
      '" fill="none" stroke="rgba(232,240,236,.18)"/>');
    ciz.push('<line x1="' + px(-SAHA.ucKose) + '" y1="0" x2="' + px(-SAHA.ucKose) + '" y2="' +
      py(SAHA.ucKoseX) + '" stroke="rgba(232,240,236,.18)"/>');
    ciz.push('<line x1="' + px(SAHA.ucKose) + '" y1="0" x2="' + px(SAHA.ucKose) + '" y2="' +
      py(SAHA.ucKoseX) + '" stroke="rgba(232,240,236,.18)"/>');

    var toplam = 0, isabet = 0;
    analizler.forEach(function (a) {
      a.shots.forEach(function (s) {
        toplam++;
        if (s[3]) isabet++;
        var X = px((s[1] - 50) * BIRIM_Y).toFixed(1), Y = py(s[0] * BIRIM_X).toFixed(1);
        ciz.push(s[3]
          ? '<circle cx="' + X + '" cy="' + Y + '" r="4.5" fill="#f2a33c" opacity=".85"/>'
          : '<circle cx="' + X + '" cy="' + Y + '" r="4.5" fill="none" ' +
            'stroke="rgba(232,240,236,.4)" stroke-width="1.4"/>');
      });
    });
    return { svg: '<svg viewBox="0 0 ' + W + " " + H + '" role="img">' + ciz.join("") + "</svg>",
             toplam: toplam, isabet: isabet };
  }

  // -------------------------------------------------------------- çizim
  function seritCiz() {
    el("takimSerit").innerHTML = durum.takimlar.map(function (ad) {
      var on = durum.secili === ad;
      var sira = durum.siradakiRakip === ad;
      return '<button type="button" data-takim="' + esc(ad) + '" class="' +
        (sira ? "siradaki" : "") + '" aria-pressed="' + (on ? "true" : "false") + '">' +
        esc(ad) + (sira ? " ·  sıradaki" : "") + "</button>";
    }).join("");
  }

  function ciz() {
    var analizler = durum.analizler;
    var ad = durum.secili;
    if (!analizler.length) {
      el("icerik").innerHTML = '<div class="note"><div><b>' + esc(ad) + "</b> için analiz " +
        "edilmiş maç yok. TBF maç raporunu yayımladıkça burası dolacak.</div></div>";
      return;
    }

    var galibiyet = analizler.filter(function (a) { return a.score[0] > a.score[1]; }).length;
    var kutular = bolgeDokumu(analizler);
    var oyuncular = oyuncuTablosu(analizler);
    var harita = atisHaritasi(analizler);
    var satirlar = okuma(analizler, kutular, oyuncular);
    var toplamSut = harita.toplam;

    var atilan = ort(analizler.map(function (a) { return a.score[0]; }));
    var yenilen = ort(analizler.map(function (a) { return a.score[1]; }));
    var ucDeneme = ort(analizler.map(function (a) { return (a.team.uc || [])[1]; }));
    var fgIsabet = ort(analizler.map(function (a) {
      return yuzde(((a.team.iki || [])[0] || 0) + ((a.team.uc || [])[0] || 0),
                   ((a.team.iki || [])[1] || 0) + ((a.team.uc || [])[1] || 0));
    }));

    el("icerik").innerHTML =
      '<div class="kunye"><h3>' + esc(ad) + "</h3>" +
        '<div class="alt">' + analizler.length + " maç analiz edildi · " +
        galibiyet + " galibiyet, " + (analizler.length - galibiyet) + " mağlubiyet</div></div>" +

      '<div class="kutular">' +
        '<div class="kutu"><b>' + bir(atilan) + "</b><span>Attığı ort.</span></div>" +
        '<div class="kutu"><b>' + bir(yenilen) + "</b><span>Yediği ort.</span></div>" +
        '<div class="kutu"><b>%' + Math.round(fgIsabet) + "</b><span>Saha isabeti</span></div>" +
        '<div class="kutu"><b>' + bir(ort(analizler.map(function (a) { return a.team.hucumRib; }))) +
          "</b><span>Hücum rib.</span></div>" +
        '<div class="kutu"><b>' + bir(ort(analizler.map(function (a) { return a.team.topKaybi; }))) +
          "</b><span>Top kaybı</span></div>" +
        '<div class="kutu"><b>' + bir(ucDeneme) + "</b><span>Üçlük den.</span></div>" +
      "</div>" +

      verimlilikBolumu(analizler) +

      (satirlar.length
        ? "<h2>Taktik okuması</h2><div class=\"okuma\">" + satirlar.map(function (r) {
            return '<div><span class="im">▸</span><span><b>' + esc(r[0]) + "</b> — " +
              esc(r[1]) + "</span></div>";
          }).join("") + "</div>"
        : "") +

      "<h2>Şut bölgeleri</h2>" +
      '<table class="bolge"><thead><tr><th>Bölge</th><th>Deneme</th><th>İsabet</th>' +
      "<th>Pay</th></tr></thead><tbody>" +
      ["Boya içi", "Orta mesafe", "Üçlük"].map(function (k) {
        var v = kutular[k] || { deneme: 0, isabet: 0 };
        var pay = yuzde(v.deneme, toplamSut);
        return "<tr" + (pay >= 45 ? ' class="vurgu"' : "") + "><td>" + esc(k) + "</td>" +
          "<td>" + v.deneme + "</td><td><b>%" + yuzde(v.isabet, v.deneme) + "</b></td>" +
          "<td>%" + pay + "</td></tr>";
      }).join("") + "</tbody></table>" +
      '<p class="aciklama">Sol / merkez / sağ dağılımı: ' +
        ["Sol", "Merkez", "Sağ"].map(function (t) {
          var tt = taraflar(analizler);
          return t.toLowerCase() + " %" + yuzde(tt[t], tt.Sol + tt.Merkez + tt.Sağ);
        }).join(" · ") + ".</p>" +

      "<h2>Atış haritası · " + analizler.length + " maç</h2>" +
      '<div class="saha">' + harita.svg + "</div>" +
      '<p class="aciklama">Dolu daire isabet, boş halka ıska. ' + harita.isabet + "/" +
        harita.toplam + " · %" + yuzde(harita.isabet, harita.toplam) +
        ". Bütün maçlar üst üste konuldu; tekrar eden bölgeler böyle görünür.</p>" +

      "<h2>Oyuncular</h2>" +
      '<table class="ptab"><thead><tr><th>Oyuncu</th><th>Maç</th><th>Sayı</th><th>Rib</th>' +
      "<th>Ast</th><th>Şut</th></tr></thead><tbody>" +
      oyuncular.slice(0, 14).map(function (o) {
        return '<tr><td><span class="no">' + (o.no == null ? "–" : esc(o.no)) + "</span> " +
          esc(o.ad) + "</td><td>" + o.mac + "</td>" +
          "<td><b>" + bir(o.sayi / o.mac) + "</b></td><td>" + bir(o.rib / o.mac) + "</td>" +
          "<td>" + bir(o.ast / o.mac) + "</td><td>" + (o.sut || 0) +
          (o.sut ? " · %" + yuzde(o.isabet || 0, o.sut) : "") + "</td></tr>";
      }).join("") + "</tbody></table>" +

      "<h2>Maçları</h2><div class=\"maclist\">" + takiminMaclari(durum.secili).map(function (a) {
        var kazandi = a.score[0] > a.score[1];
        var ic = '<span class="t">' + esc(gunAy(a.date)) + "</span>" +
          "<span>" + esc(a.rakip) + (a.evMi ? "" : " (deplasman)") + "</span>" +
          '<span class="s ' + (kazandi ? "g" : "m") + '">' + a.score[0] + "-" + a.score[1] +
          "</span>";
        // Analizi olmayan maçın skoru yine görünür ama tıklanamaz: koç
        // "burada bir şey vardı ama açılmadı" diye düşünmesin, sebebi yazsın.
        return a.analizVar
          ? '<button type="button" data-mac="' + a.matchId + '">' + ic + "</button>"
          : '<div class="yok" title="Bu maçın ayrıntılı analizi henüz üretilmedi">' +
            ic + '<span class="nt">analiz yok</span></div>';
      }).join("") + "</div>" +
      '<div id="macDetay"></div>';
  }

  /** Tek maçın rakip gözüyle dökümü. */
  function macCiz(a) {
    var harita = atisHaritasi([a]);
    var sebepler = Object.keys(a.turnovers).sort(function (x, y) {
      return a.turnovers[y] - a.turnovers[x];
    });
    el("macDetay").innerHTML =
      '<div class="kunye" style="margin-top:.8rem"><h3>' + esc(gunAy(a.date)) + " · " +
        esc(a.rakip) + "</h3>" +
        '<div class="alt">' + a.score[0] + " – " + a.score[1] +
        (a.evMi ? " (ev sahibi)" : " (deplasman)") +
        " · çeyrekler " + a.quarters.map(function (q) {
          return q.lehte + "-" + q.aleyhte;
        }).join(" · ") +
        (a.run && a.run[0] ? " · en uzun serisi " + a.run[0] + " sayı" : "") + "</div></div>" +
      '<div class="saha">' + harita.svg + "</div>" +
      '<p class="aciklama">Bu maçta ' + harita.isabet + "/" + harita.toplam + " atış (%" +
        yuzde(harita.isabet, harita.toplam) + "). " +
        (sebepler.length ? "Top kaybı: " + sebepler.slice(0, 3).map(function (k) {
          return k.toLowerCase() + " " + a.turnovers[k];
        }).join(", ") + "." : "") + "</p>" +
      '<table class="ptab"><thead><tr><th>Oyuncu</th><th>Dk</th><th>Sayı</th><th>Rib</th>' +
      "<th>Ast</th></tr></thead><tbody>" +
      (a.box || []).slice().sort(function (x, y) {
        return (y.points || 0) - (x.points || 0);
      }).map(function (r) {
        return '<tr><td><span class="no">' + (r.no == null ? "–" : esc(r.no)) + "</span> " +
          esc(r.name || "") + "</td><td>" + esc((r.min || "").slice(0, 5)) + "</td>" +
          "<td><b>" + (r.points || 0) + "</b></td><td>" + (r.rebounds || 0) + "</td>" +
          "<td>" + (r.assists || 0) + "</td></tr>";
      }).join("") + "</tbody></table>";
    el("macDetay").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function takimSec(ad) {
    durum.secili = ad;
    seritCiz();
    el("icerik").innerHTML = '<p class="hint">Maçlar okunuyor…</p>';
    takimAnalizleri(ad).then(function (liste) {
      durum.analizler = liste;
      ciz();
    });
  }

  document.addEventListener("click", function (ev) {
    var t = ev.target;
    if (!t.closest) return;
    var takim = t.closest("[data-takim]");
    if (takim) { takimSec(takim.dataset.takim); return; }
    var mac = t.closest("[data-mac]");
    if (mac) {
      var a = durum.analizler.filter(function (x) {
        return String(x.matchId) === mac.dataset.mac;
      })[0];
      if (a) macCiz(a);
    }
  });

  P.requireLogin(function () {
    ligYukle().then(function () {
      seritCiz();
      takimSec(durum.siradakiRakip || durum.takimlar[0]);
    }).catch(function (err) {
      el("icerik").innerHTML = '<div class="note bad"><div>' + esc(err.message) + "</div></div>";
    });
  });
})();
