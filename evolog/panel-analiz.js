/* Antrenör panelinin ortak analiz hesapları.
 *
 * Basketbolun standart ölçüleri; üç ekran da (maç analizi, oyuncular, rakip)
 * buradan okuyor ki aynı sayı iki yerde farklı çıkmasın.
 *
 * Pozisyon tahmini:  FGA − hücum ribaundu + top kaybı + 0.44 × FTA
 * Bu, şut saati verisi olmadan kullanılan standart yaklaşımdır; 0.44 katsayısı
 * serbest atışların kaçının ayrı bir pozisyon olduğunu tahmin eder.
 *
 * Dört Faktör (Dean Oliver): kazanmayı en çok açıklayan dört oran.
 *   eFG%  — üçlüğü 1.5 sayarak saha isabeti (şut seçimi + isabet)
 *   TOV%  — pozisyon başına top kaybı
 *   OREB% — kendi ıskasını toplama oranı (kendi HR / (kendi HR + rakip SR))
 *   FT/FGA— serbest atışa gitme sıklığı
 */
window.EvologAnaliz = (function () {
  "use strict";

  function say(v) { return typeof v === "number" ? v : 0; }

  function fga(t) { return say((t.iki || [])[1]) + say((t.uc || [])[1]); }
  function fgm(t) { return say((t.iki || [])[0]) + say((t.uc || [])[0]); }
  function fta(t) { return say((t.sa || [])[1]); }

  /** Tahmini pozisyon sayısı. */
  function pozisyon(t) {
    return fga(t) - say(t.hucumRib) + say(t.topKaybi) + 0.44 * fta(t);
  }

  /** İki takımın pozisyonunun ortalaması: tempo (maç başına pozisyon). */
  function tempo(biz, rakip) {
    var a = pozisyon(biz), b = pozisyon(rakip);
    return (a && b) ? (a + b) / 2 : (a || b);
  }

  /** 100 pozisyonda üretilen sayı. */
  function rating(sayi, poz) {
    return poz > 0 ? (100 * say(sayi)) / poz : 0;
  }

  function dortFaktor(t, rakip) {
    var f = fga(t);
    var poz = pozisyon(t);
    var hr = say(t.hucumRib), rakipSr = say((rakip || {}).savunmaRib);
    return {
      efg: f ? (fgm(t) + 0.5 * say((t.uc || [])[0])) / f : 0,
      tov: poz > 0 ? say(t.topKaybi) / poz : 0,
      oreb: (hr + rakipSr) ? hr / (hr + rakipSr) : 0,
      ftr: f ? fta(t) / f : 0,
      poz: poz
    };
  }

  /** Dakikaya göre normalize: 36 dakikada ne üretiyor. */
  function per36(deger, dakika) {
    return dakika > 0 ? (say(deger) * 36) / dakika : null;
  }

  function yuzde(pay, payda) { return payda ? Math.round((100 * pay) / payda) : 0; }
  function bir(v) { return Math.round(v * 10) / 10; }

  /** Dört faktör tablosu (iki takım yan yana). */
  function dortFaktorTablosu(biz, rakip, bizAd, rakipAd) {
    var a = dortFaktor(biz, rakip), b = dortFaktor(rakip, biz);
    var satirlar = [
      ["eFG%", Math.round(a.efg * 100) + "%", Math.round(b.efg * 100) + "%",
       "Üçlüğü 1,5 sayan saha isabeti"],
      ["Top kaybı %", Math.round(a.tov * 100) + "%", Math.round(b.tov * 100) + "%",
       "Pozisyon başına top kaybı — düşük olan iyi"],
      ["Hücum rib. %", Math.round(a.oreb * 100) + "%", Math.round(b.oreb * 100) + "%",
       "Kendi ıskasını toplama oranı"],
      ["Serbest atış/şut", a.ftr.toFixed(2), b.ftr.toFixed(2),
       "Faul aldırma sıklığı"]
    ];
    return '<table class="ff"><thead><tr><th>Dört faktör</th><th>' +
      (bizAd || "Biz") + "</th><th>" + (rakipAd || "Rakip") + "</th></tr></thead><tbody>" +
      satirlar.map(function (r) {
        return "<tr><td>" + r[0] + '<div class="ffa">' + r[3] + "</div></td>" +
          "<td><b>" + r[1] + "</b></td><td>" + r[2] + "</td></tr>";
      }).join("") + "</tbody></table>";
  }

  return {
    pozisyon: pozisyon, tempo: tempo, rating: rating, dortFaktor: dortFaktor,
    per36: per36, yuzde: yuzde, bir: bir, dortFaktorTablosu: dortFaktorTablosu
  };
})();
