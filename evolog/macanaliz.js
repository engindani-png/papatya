/* Maç analizi — TBF'nin ayrıntılı maç verisinin antrenör görünümü.
 *
 * Veri `data/<yaş>/analiz/<macId>.json` dosyalarından geliyor; bunları
 * senkron üretiyor (scripts/tbf_analiz.py). Sayfa yalnız okur.
 *
 * Grafik kararları:
 *  - Skor akışı tek seri olarak **fark** çizilir (biz eksi rakip). İki ayrı
 *    çizgi telefonda birbirine giriyor; fark eğrisi "maç ne zaman koptu"
 *    sorusunu tek bakışta cevaplıyor. Sıfır çizgisi her zaman görünür.
 *  - Atış haritası gerçek yarı saha ölçüleriyle çizilir (metre bazlı).
 *    İsabet dolu daire, ıska içi boş halka — renk körlüğünde de ayrışsın.
 */
(function () {
  "use strict";

  var P = window.EvologPanel;
  var AGE = "u14";
  var AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

  // Saha ölçüleri (FIBA, metre). x: dip çizgiden uzaklık, y: merkezden sapma.
  var SAHA = { boy: 14, en: 15, potaX: 1.575, panoX: 1.2, boyaBoy: 5.8, boyaEn: 2.45,
               serbestR: 1.8, ucR: 6.75, ucKose: 6.6, ucKoseX: 2.99 };
  var BIRIM_X = 0.28;   // koordinat birimi başına metre (saha boyu 28 m / 100)
  var BIRIM_Y = 0.15;   // saha genişliği 15 m / 100

  var durum = { maclar: [], secili: null, analiz: null, oyuncu: "hepsi" };

  function el(id) { return document.getElementById(id); }
  function esc(v) { return P.esc(v); }
  function gunAy(iso) {
    var p = String(iso || "").split("-");
    return p.length === 3 ? Number(p[2]) + " " + AYLAR[Number(p[1]) - 1] : (iso || "");
  }
  function yuzde(pay, payda) {
    return payda ? Math.round((100 * pay) / payda) : 0;
  }

  // ------------------------------------------------------------- yükleme
  function maclariYukle() {
    return fetch("/data/" + AGE + "/league.json", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (lig) {
        var analizli = lig.analiz || [];
        durum.maclar = (lig.fixtures || []).filter(function (f) {
          return f.played && analizli.indexOf(f.matchId) !== -1;
        }).sort(function (a, b) { return String(b.date).localeCompare(String(a.date)); });
      });
  }

  function analizYukle(mac) {
    return fetch("/data/" + AGE + "/analiz/" + mac.matchId + ".json", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (a) { return yonlendir(a, !!mac.isHome); });
  }

  /** Analiz dosyalari notr (ev/deplasman); ekran "biz/rakip" diliyle calisiyor.
   *  Ayni dosyayi rakip analizi ekrani da okuyor, orada taraf rakip oluyor. */
  function yonlendir(a, bizEv) {
    var b = bizEv ? "home" : "away", r = bizEv ? "away" : "home";
    return {
      matchId: a.matchId, date: a.date, isHome: bizEv,
      opp: bizEv ? a.away : a.home,
      score: [a.score[bizEv ? 0 : 1], a.score[bizEv ? 1 : 0]],
      quarters: (a.quarters || []).map(function (q) {
        return bizEv ? q : { home: q.away, away: q.home };
      }),
      shots: (a.shots || {})[b] || [],
      flow: (a.flow || []).map(function (f) {
        return [f[0], bizEv ? f[1] : f[2], bizEv ? f[2] : f[1]];
      }),
      turnovers: (a.turnovers || {})[b] || {},
      asist: (a.asist || {})[b] || null,
      kayiptan: (a.kayiptan || {})[b] || null,
      kayiptanBiz: (a.kayiptan || {})[r] || null,
      besli: (a.besli || {})[b] || null,
      faul: (a.faul || {})[b] || null,
      faulRakip: (a.faul || {})[r] || null,
      shotTypes: (a.shotTypes || {})[b] || {},
      players: (a.players || {})[b] || {},
      run: (a.run || {})[b] || [0, ""],
      team: { biz: (a.team || {})[b] || {}, rakip: (a.team || {})[r] || {} },
      box: { biz: (a.box || {})[b] || [], rakip: (a.box || {})[r] || [] }
    };
  }

  // -------------------------------------------------------------- çizim
  function seritCiz() {
    el("macSerit").innerHTML = durum.maclar.map(function (m) {
      var biz = m.isHome ? m.homeScore : m.awayScore;
      var rak = m.isHome ? m.awayScore : m.homeScore;
      var rakip = m.isHome ? m.away : m.home;
      var on = durum.secili && durum.secili.matchId === m.matchId;
      return '<button type="button" data-mac="' + m.matchId + '" aria-pressed="' +
        (on ? "true" : "false") + '">' + esc(gunAy(m.date)) + " · " + biz + "-" + rak +
        "<small>" + esc(rakip) + "</small></button>";
    }).join("") || '<p class="hint">Analiz edilecek oynanmış maç yok.</p>';
  }

  /** Skor farkı eğrisi: sıfır çizgisi, önde geçen bölge amber. */
  function farkGrafigi(flow) {
    var W = 320, H = 120, L = 24, R = 8, T = 10, B = 16;
    var son = flow.length ? flow[flow.length - 1][0] : 1;
    var farklar = flow.map(function (f) { return f[1] - f[2]; });
    var enBuyuk = Math.max(6, Math.max.apply(null, farklar.map(Math.abs)));
    var tavan = Math.ceil(enBuyuk / 5) * 5;

    function x(t) { return L + (t / (son || 1)) * (W - L - R); }
    function y(v) { return T + (H - T - B) / 2 * (1 - v / tavan); }

    var parcalar = [];
    // Çeyrek sınırları
    for (var q = 1; q <= 4; q++) {
      var t = q * 600;
      if (t > son) break;
      parcalar.push('<line x1="' + x(t).toFixed(1) + '" y1="' + T + '" x2="' + x(t).toFixed(1) +
        '" y2="' + (H - B) + '" stroke="rgba(232,240,236,.10)" stroke-width="1"/>');
    }
    parcalar.push('<line x1="' + L + '" y1="' + y(0).toFixed(1) + '" x2="' + (W - R) +
      '" y2="' + y(0).toFixed(1) + '" stroke="rgba(232,240,236,.32)" stroke-width="1"/>');
    parcalar.push('<text x="' + (L - 4) + '" y="' + (y(tavan) + 4).toFixed(1) +
      '" fill="#6f8a81" font-size="9" text-anchor="end">+' + tavan + "</text>");
    parcalar.push('<text x="' + (L - 4) + '" y="' + (y(0) + 3.5).toFixed(1) +
      '" fill="#6f8a81" font-size="9" text-anchor="end">0</text>');

    var nokta = flow.map(function (f) { return x(f[0]).toFixed(1) + "," + y(f[1] - f[2]).toFixed(1); });
    // Sıfır çizgisiyle kapatılmış alan: önde olduğumuz süre gözle ölçülebilsin.
    parcalar.push('<polygon points="' + x(0).toFixed(1) + "," + y(0).toFixed(1) + " " +
      nokta.join(" ") + " " + x(son).toFixed(1) + "," + y(0).toFixed(1) +
      '" fill="rgba(242,163,60,.16)"/>');
    parcalar.push('<polyline points="' + nokta.join(" ") +
      '" fill="none" stroke="#f2a33c" stroke-width="2" stroke-linejoin="round"/>');

    var sonFark = farklar[farklar.length - 1] || 0;
    parcalar.push('<text x="' + (W - R) + '" y="' + (y(sonFark) - 6).toFixed(1) +
      '" fill="#e8f0ec" font-size="11" font-weight="700" text-anchor="end">' +
      (sonFark > 0 ? "+" : "") + sonFark + "</text>");
    for (var i = 1; i <= 4; i++) {
      if (i * 600 > son + 60) break;
      parcalar.push('<text x="' + x((i - 0.5) * 600).toFixed(1) + '" y="' + (H - 4) +
        '" fill="#6f8a81" font-size="9" text-anchor="middle">' + i + ". çeyrek</text>");
    }
    return '<svg viewBox="0 0 ' + W + " " + H + '" role="img">' + parcalar.join("") + "</svg>";
  }

  /** Yarı saha + atışlar. Ölçüler metre; koordinatlar metreye çevriliyor. */
  function atisHaritasi(shots, oyuncu) {
    var m2p = 20;                       // 1 metre = 20 px
    var W = SAHA.en * m2p, H = SAHA.boy * m2p;
    function px(metreY) { return (metreY + SAHA.en / 2) * m2p; }   // yatay
    function py(metreX) { return metreX * m2p; }                   // dikey (dip çizgi üstte)

    var ciz = ['<rect x="0" y="0" width="' + W + '" height="' + H +
      '" fill="none" stroke="rgba(232,240,236,.18)"/>'];
    // boya
    ciz.push('<rect x="' + px(-SAHA.boyaEn) + '" y="0" width="' + (SAHA.boyaEn * 2 * m2p) +
      '" height="' + py(SAHA.boyaBoy) + '" fill="none" stroke="rgba(232,240,236,.18)"/>');
    // serbest atış çemberi
    ciz.push('<circle cx="' + px(0) + '" cy="' + py(SAHA.boyaBoy) + '" r="' + (SAHA.serbestR * m2p) +
      '" fill="none" stroke="rgba(232,240,236,.18)"/>');
    // pota ve panya
    ciz.push('<line x1="' + px(-0.9) + '" y1="' + py(SAHA.panoX) + '" x2="' + px(0.9) +
      '" y2="' + py(SAHA.panoX) + '" stroke="rgba(232,240,236,.3)" stroke-width="2"/>');
    ciz.push('<circle cx="' + px(0) + '" cy="' + py(SAHA.potaX) + '" r="' + (0.225 * m2p) +
      '" fill="none" stroke="rgba(232,240,236,.3)"/>');
    // üç sayı: köşelerde düz, sonra yay
    var r = SAHA.ucR * m2p, cx = px(0), cy = py(SAHA.potaX);
    ciz.push('<line x1="' + px(-SAHA.ucKose) + '" y1="0" x2="' + px(-SAHA.ucKose) + '" y2="' +
      py(SAHA.ucKoseX) + '" stroke="rgba(232,240,236,.18)"/>');
    ciz.push('<line x1="' + px(SAHA.ucKose) + '" y1="0" x2="' + px(SAHA.ucKose) + '" y2="' +
      py(SAHA.ucKoseX) + '" stroke="rgba(232,240,236,.18)"/>');
    ciz.push('<path d="M ' + px(-SAHA.ucKose) + " " + py(SAHA.ucKoseX) + " A " + r + " " + r +
      " 0 0 0 " + px(SAHA.ucKose) + " " + py(SAHA.ucKoseX) +
      '" fill="none" stroke="rgba(232,240,236,.18)"/>');

    var sec = shots.filter(function (a) { return oyuncu === "hepsi" || a[4] === oyuncu; });
    sec.forEach(function (a) {
      var mx = a[0] * BIRIM_X;                 // dip çizgiden uzaklık (m)
      var my = (a[1] - 50) * BIRIM_Y;          // merkezden sapma (m)
      var X = px(my).toFixed(1), Y = py(mx).toFixed(1);
      if (a[3]) {
        ciz.push('<circle cx="' + X + '" cy="' + Y + '" r="5" fill="#f2a33c" ' +
          'stroke="#0d1714" stroke-width="1.5"/>');
      } else {
        ciz.push('<circle cx="' + X + '" cy="' + Y + '" r="5" fill="none" ' +
          'stroke="rgba(232,240,236,.45)" stroke-width="1.6"/>');
      }
    });
    var isabet = sec.filter(function (a) { return a[3]; }).length;
    return {
      svg: '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Atış haritası">' +
        ciz.join("") + "</svg>",
      isabet: isabet, deneme: sec.length
    };
  }

  function karsilastirma(biz, rakip) {
    var satirlar = [
      ["Sayı", biz.sayi, rakip.sayi, null],
      ["Saha isabeti", (biz.iki[0] || 0) + (biz.uc[0] || 0), (rakip.iki[0] || 0) + (rakip.uc[0] || 0),
        [(biz.iki[1] || 0) + (biz.uc[1] || 0), (rakip.iki[1] || 0) + (rakip.uc[1] || 0)]],
      ["İkilik", biz.iki[0], rakip.iki[0], [biz.iki[1], rakip.iki[1]]],
      ["Üçlük", biz.uc[0], rakip.uc[0], [biz.uc[1], rakip.uc[1]]],
      ["Serbest atış", biz.sa[0], rakip.sa[0], [biz.sa[1], rakip.sa[1]]],
      ["Ribaund", biz.rib, rakip.rib, null],
      ["Hücum ribaundu", biz.hucumRib, rakip.hucumRib, null],
      ["Asist", biz.asist, rakip.asist, null],
      ["Top çalma", biz.topCalma, rakip.topCalma, null],
      ["Top kaybı", biz.topKaybi, rakip.topKaybi, null],
      ["Blok", biz.blok, rakip.blok, null],
      ["Faul", biz.faul, rakip.faul, null]
    ];
    return '<div class="cmp">' + satirlar.map(function (r) {
      var b = r[1] == null ? 0 : r[1], k = r[2] == null ? 0 : r[2];
      var toplam = b + k || 1;
      var bYazi = r[3] ? b + "/" + r[3][0] + " · %" + yuzde(b, r[3][0]) : String(b);
      var kYazi = r[3] ? k + "/" + r[3][1] + " · %" + yuzde(k, r[3][1]) : String(k);
      return '<div class="row"><div class="top"><b>' + esc(bYazi) + "</b>" +
        '<span class="ad">' + esc(r[0]) + "</span><b>" + esc(kYazi) + "</b></div>" +
        '<div class="bar"><i class="biz" style="width:' + (100 * b / toplam) + '%"></i>' +
        '<i class="rak" style="width:' + (100 * k / toplam) + '%"></i></div></div>';
    }).join("") + "</div>";
  }

  function dokum(baslik, nesne, ikili) {
    var anahtarlar = Object.keys(nesne || {});
    if (!anahtarlar.length) return "";
    anahtarlar.sort(function (a, b) {
      var av = ikili ? nesne[a][1] : nesne[a], bv = ikili ? nesne[b][1] : nesne[b];
      return bv - av;
    });
    return "<h2>" + esc(baslik) + '</h2><div class="dokum">' +
      anahtarlar.map(function (k) {
        var v = nesne[k];
        return "<span>" + esc(k) + (ikili ? ' <span class="s">%' + yuzde(v[0], v[1]) + "</span>" : "") +
          "</span><b>" + (ikili ? v[0] + "/" + v[1] : v) + "</b>";
      }).join("") + "</div>";
  }

  function ciz() {
    var a = durum.analiz;
    if (!a) { el("icerik").innerHTML = ""; return; }
    var biz = a.team.biz, rakip = a.team.rakip;
    var bizAd = a.isHome ? "Evolog" : "Evolog";
    var harita = atisHaritasi(a.shots, durum.oyuncu);

    var oyuncular = {};
    a.shots.forEach(function (s) { oyuncular[s[4]] = (oyuncular[s[4]] || 0) + 1; });
    var numaralar = Object.keys(oyuncular).sort(function (x, y) { return Number(x) - Number(y); });

    var satirlar = Object.keys(a.players || {}).map(function (no) {
      var p = a.players[no];
      return { no: no, dk: p.sec / 60, pm: p.pm };
    }).sort(function (x, y) { return y.dk - x.dk; });

    el("icerik").innerHTML =
      '<div class="skor">' +
        '<div><div class="tn">' + esc(bizAd) + '</div></div>' +
        '<div class="sc">' + a.score[0] + " – " + a.score[1] + "</div>" +
        '<div class="r"><div class="tn">' + esc(a.opp) + "</div></div>" +
        '<div class="cey">' + (a.quarters || []).map(function (q, i) {
          return (i + 1) + ". Ç " + q.home + "-" + q.away;
        }).join(" · ") + (a.run && a.run[0] ? " · en uzun seri " + a.run[0] + " sayı (" +
          esc(a.run[1]) + ")" : "") + "</div>" +
      "</div>" +

      '<div class="grafik"><div class="bas"><h4>Skor farkı</h4>' +
        "<span>sıfır çizgisinin üstü önde</span></div>" + farkGrafigi(a.flow) + "</div>" +

      "<h2>Karşılaştırma</h2>" + karsilastirma(biz, rakip) +

      "<h2>Atış haritası</h2>" +
      '<div class="filtre"><button type="button" data-oyuncu="hepsi" aria-pressed="' +
        (durum.oyuncu === "hepsi" ? "true" : "false") + '">Takım</button>' +
        numaralar.map(function (n) {
          return '<button type="button" data-oyuncu="' + esc(n) + '" aria-pressed="' +
            (durum.oyuncu === n ? "true" : "false") + '">' + esc(n) + "</button>";
        }).join("") + "</div>" +
      '<div class="saha">' + harita.svg + "</div>" +
      '<p class="aciklama">Dolu daire isabet, boş halka ıska. ' +
        harita.isabet + "/" + harita.deneme + " · %" + yuzde(harita.isabet, harita.deneme) +
        ". İkinci yarının koordinatları saha değişimi için aynalandı.</p>" +

      verimlilikBolumu(a) +

      faulBolumu(a) +

      dokum("Top kaybı nerede", a.turnovers, false) +
      dokum("Şut tipine göre", a.shotTypes, true) +

      "<h2>Süre ve katkı</h2>" +
      '<table class="ptab"><thead><tr><th>Forma</th><th>Süre</th><th>+/–</th></tr></thead><tbody>' +
      satirlar.map(function (r) {
        return "<tr><td><b>" + esc(r.no) + "</b></td><td>" + r.dk.toFixed(1) + " dk</td>" +
          '<td class="pm ' + (r.pm > 0 ? "arti" : r.pm < 0 ? "eksi" : "") + '">' +
          (r.pm > 0 ? "+" : "") + r.pm + "</td></tr>";
      }).join("") + "</tbody></table>" +
      '<p class="aciklama">Süre ve +/– oyun akışındaki değişikliklerden hesaplandı; ' +
        "TBF'nin kendi değerleriyle karşılaştırılıp doğrulandı.</p>";
  }

  /** Pozisyon bazlı verimlilik, dört faktör, kayıptan sayı, asist, beşliler. */
  function verimlilikBolumu(a) {
    var A2 = window.EvologAnaliz;
    var biz = a.team.biz, rakip = a.team.rakip;
    var poz = A2.pozisyon(biz), pozR = A2.pozisyon(rakip);
    if (!poz || !pozR) return "";
    var tempo = A2.tempo(biz, rakip);

    var asist = a.asist
      ? '<div class="olcum"><b>%' + yuzde(a.asist.asistli, a.asist.basket) + "</b>" +
        "<span>Asistli basket</span><small>" + a.asist.asistli + "/" + a.asist.basket +
        "</small></div>"
      : "";
    var kayip = a.kayiptan
      ? '<div class="olcum"><b>' + a.kayiptan.yenilen + "</b>" +
        "<span>Kayıptan yenilen</span><small>" + a.kayiptan.kayip + " kayıpta</small></div>"
      : "";
    var kazanc = a.kayiptanBiz
      ? '<div class="olcum"><b>' + a.kayiptanBiz.yenilen + "</b>" +
        "<span>Kayıptan bulduğumuz</span><small>rakip " + a.kayiptanBiz.kayip +
        " kayıp</small></div>"
      : "";

    var ciftler = (a.asist && a.asist.ciftler && a.asist.ciftler.length)
      ? '<p class="aciklama">En sık asist: ' + a.asist.ciftler.slice(0, 4).map(function (c) {
          return c[0] + " → " + c[1] + (c[2] > 1 ? " (" + c[2] + ")" : "");
        }).join(" · ") + " (forma numaraları).</p>"
      : "";

    var besliler = (a.besli && a.besli.lineups && a.besli.lineups.length)
      ? "<h2>Beşliler</h2>" +
        '<table class="ptab"><thead><tr><th>Sahadaki beş</th><th>Süre</th><th>Fark</th>' +
        "</tr></thead><tbody>" +
        a.besli.lineups.map(function (l) {
          var fark = l.lehte - l.aleyhte;
          return "<tr><td>" + l.p.join(" · ") + "</td><td>" + (l.sec / 60).toFixed(1) +
            ' dk</td><td class="pm ' + (fark > 0 ? "arti" : fark < 0 ? "eksi" : "") + '">' +
            (fark > 0 ? "+" : "") + fark + " <small>(" + l.lehte + "-" + l.aleyhte +
            ")</small></td></tr>";
        }).join("") + "</tbody></table>" +
        '<p class="aciklama">Oyuncu değişikliklerinden yeniden kurulan beşliler; ' +
        "30 saniyeden kısa duran kombinasyonlar gösterilmiyor.</p>"
      : "";

    var kullanim = (a.besli && a.besli.usage)
      ? "<h2>Şut payı</h2>" +
        '<table class="ptab"><thead><tr><th>Forma</th><th>Kendi şutu</th>' +
        "<th>Sahadayken takım</th><th>Pay</th></tr></thead><tbody>" +
        Object.keys(a.besli.usage).map(function (no) {
          return { no: no, v: a.besli.usage[no] };
        }).filter(function (x) { return x.v.fga; })
          .sort(function (x, y) { return (y.v.fga / y.v.takim) - (x.v.fga / x.v.takim); })
          .map(function (x) {
            return "<tr><td><b>" + esc(x.no) + "</b></td><td>" + x.v.fga + "</td>" +
              "<td>" + x.v.takim + "</td><td><b>%" + yuzde(x.v.fga, x.v.takim) +
              "</b></td></tr>";
          }).join("") + "</tbody></table>" +
        '<p class="aciklama">Oyuncu sahadayken takımın attığı şutların yüzde kaçını ' +
        "kendisi kullandı (usage). Sayı ortalamasından bağımsız bir yük ölçüsü.</p>"
      : "";

    return "<h2>Verimlilik</h2>" +
      '<div class="olcumler">' +
        '<div class="olcum"><b>' + Math.round(A2.rating(a.score[0], poz)) + "</b>" +
          "<span>Hücum ratingi</span><small>100 pozisyonda</small></div>" +
        '<div class="olcum"><b>' + Math.round(A2.rating(a.score[1], pozR)) + "</b>" +
          "<span>Savunma ratingi</span><small>100 pozisyonda</small></div>" +
        '<div class="olcum"><b>' + Math.round(tempo) + "</b>" +
          "<span>Tempo</span><small>maçtaki pozisyon</small></div>" +
        asist + kayip + kazanc +
      "</div>" + ciftler +
      A2.dortFaktorTablosu(biz, rakip, "Biz", "Rakip") +
      '<p class="aciklama">Dört faktör, kazanmayı en çok açıklayan dört orandır. ' +
      "Pozisyon tahmini: şut denemesi − hücum ribaundu + top kaybı + 0,44 × serbest atış.</p>" +
      besliler + kullanim;
  }

  /** Faul: kim yaptı, kim aldırdı, hangi çeyrekte. Boxscore yalnız toplamı
   *  veriyor; zamanlama ve faul aldıran oyuncu yalnız oyun akışında var. */
  function faulBolumu(a) {
    var f = a.faul;
    if (!f) return "";
    var yapan = Object.keys(f.yapan || {}).map(function (no) {
      return { no: no, n: f.yapan[no] };
    }).sort(function (x, y) { return y.n - x.n; });
    var aldiran = Object.keys(f.aldiran || {}).map(function (no) {
      return { no: no, n: f.aldiran[no] };
    }).sort(function (x, y) { return y.n - x.n; });
    var toplam = yapan.reduce(function (t, x) { return t + x.n; }, 0);
    var rakipToplam = a.faulRakip
      ? Object.keys(a.faulRakip.yapan || {}).reduce(function (t, k) {
          return t + a.faulRakip.yapan[k];
        }, 0)
      : 0;

    return "<h2>Faul</h2>" +
      '<div class="olcumler">' +
        '<div class="olcum"><b>' + toplam + "</b><span>Yaptığımız faul</span>" +
          "<small>çeyrek: " + (f.ceyrek || []).join(" · ") + "</small></div>" +
        '<div class="olcum"><b>' + rakipToplam + "</b><span>Rakip faulü</span>" +
          "<small>" + (a.faulRakip ? (a.faulRakip.ceyrek || []).join(" · ") : "") +
          "</small></div>" +
        '<div class="olcum"><b>' + (f.hucum || 0) + "</b><span>Hücum faulü</span>" +
          "<small>kendi yaptığımız</small></div>" +
      "</div>" +
      (aldiran.length
        ? '<p class="aciklama"><b>Faul aldıranlar:</b> ' + aldiran.slice(0, 5).map(function (x) {
            return x.no + " (" + x.n + ")";
          }).join(" · ") + ". Serbest atışa giden oyuncu, savunmayı zorlayan oyuncudur.</p>"
        : "") +
      (yapan.length
        ? '<p class="aciklama"><b>Faul yapanlar:</b> ' + yapan.slice(0, 5).map(function (x) {
            return x.no + " (" + x.n + ")";
          }).join(" · ") + ".</p>"
        : "");
  }

  function macSec(m) {
    durum.secili = m;
    durum.oyuncu = "hepsi";
    seritCiz();
    el("icerik").innerHTML = '<p class="hint">Yükleniyor…</p>';
    analizYukle(m).then(function (a) { durum.analiz = a; ciz(); }).catch(function () {
      el("icerik").innerHTML = '<div class="note bad"><div>Bu maçın analizi okunamadı.</div></div>';
    });
  }

  document.addEventListener("click", function (ev) {
    var t = ev.target;
    if (!t.closest) return;
    var mac = t.closest("[data-mac]");
    if (mac) {
      var m = durum.maclar.filter(function (x) {
        return String(x.matchId) === mac.dataset.mac;
      })[0];
      if (m) macSec(m);
      return;
    }
    var f = t.closest("[data-oyuncu]");
    if (f) { durum.oyuncu = f.dataset.oyuncu; ciz(); }
  });

  P.requireLogin(function () {
    maclariYukle().then(function () {
      seritCiz();
      if (durum.maclar.length) macSec(durum.maclar[0]);
      else el("icerik").innerHTML =
        '<div class="note"><div>Analiz, oynanmış maçlar için üretiliyor. ' +
        "İlk maçtan sonra burada atış haritası, skor akışı ve süre dökümü olacak.</div></div>";
    }).catch(function (err) {
      el("icerik").innerHTML = '<div class="note bad"><div>' + esc(err.message) + "</div></div>";
    });
  });
})();
