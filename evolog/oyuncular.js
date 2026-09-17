/* Oyuncu analizi — maç maç istatistik, sezon ortalaması ve gelişim grafikleri.
 *
 * Veri kaynağı zaten elimizde: TBF senkronu her oynanmış maçın boxscore'unu
 * league.json içine yazıyor. Burada sunucuya yeni bir uç eklemedik; sayfa aynı
 * dosyayı okuyup oyuncu bazına çeviriyor.
 *
 * Grafik kararları (tek seri, koyu zemin):
 *  - Her ölçüt kendi küçük grafiğinde; iki farklı ölçek asla tek grafikte
 *    birleştirilmiyor.
 *  - Tek seri olduğu için lejant yok; başlık neyi gösterdiğini söylüyor.
 *  - Ortalama, kesikli gri çizgi olarak arka planda; renk değil metin taşıyor.
 *  - Eğilim rozeti ok + kelime ile yazılıyor, yalnız renkle anlatılmıyor.
 */
(function () {
  "use strict";

  var P = window.EvologPanel;
  var AGE = "u14";
  var AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

  var OLCUTLER = [
    { k: "points", ad: "Sayı" },
    { k: "rebounds", ad: "Ribaund" },
    { k: "assists", ad: "Asist" },
    { k: "steals", ad: "Top çalma" },
    { k: "dk", ad: "Dakika" },
    // Asagidaki ikisi mac analizinden (oyun akisi + atis haritasi) geliyor:
    // boxscore'da olmayan iki sey, sahadayken skor farki ve sut isabeti.
    { k: "pm", ad: "Sahadayken fark" },
    { k: "isabetYuzde", ad: "Şut isabeti %" }
  ];

  // Saha olculeri (atis haritasi) — mac analizi ekraniyla ayni.
  var SAHA = { boy: 14, en: 15, potaX: 1.575, boyaBoy: 5.8, boyaEn: 2.45,
               serbestR: 1.8, ucR: 6.75, ucKose: 6.6, ucKoseX: 2.99 };
  var BIRIM_X = 0.28, BIRIM_Y = 0.15;

  var SIRALAMA = [
    { k: "points", ad: "Sayı" },
    { k: "rebounds", ad: "Ribaund" },
    { k: "assists", ad: "Asist" },
    { k: "dk", ad: "Dakika" },
    { k: "no", ad: "Forma no" }
  ];

  var durum = { oyuncular: [], sirala: "points", kadro: {} };

  function el(id) { return document.getElementById(id); }
  function esc(v) { return P.esc(v); }

  function dakika(v) {
    if (typeof v === "number") return v;
    var s = String(v || "").split(":");
    if (s.length !== 2) return 0;
    return (Number(s[0]) || 0) + (Number(s[1]) || 0) / 60;
  }

  function ortalama(list) {
    if (!list.length) return 0;
    return list.reduce(function (a, b) { return a + b; }, 0) / list.length;
  }

  function bir(v) { return Math.round(v * 10) / 10; }

  function gunAy(isoStr) {
    var p = String(isoStr || "").split("-");
    if (p.length !== 3) return isoStr || "";
    return Number(p[2]) + " " + AYLAR[Number(p[1]) - 1];
  }

  /** En küçük kareler eğimi: maç sırasına göre artıyor mu, azalıyor mu? */
  function egilim(degerler) {
    var n = degerler.length;
    if (n < 3) return null;
    var ortX = (n - 1) / 2, ortY = ortalama(degerler), pay = 0, payda = 0;
    for (var i = 0; i < n; i++) {
      pay += (i - ortX) * (degerler[i] - ortY);
      payda += (i - ortX) * (i - ortX);
    }
    if (!payda) return null;
    var egim = pay / payda;
    // Maç başına değişim, ortalamanın %8'inden küçükse "sabit" sayılır:
    // gençlerde maçtan maça dalgalanma normal, gürültüyü eğilim diye sunmayalım.
    var esik = Math.max(0.35, Math.abs(ortY) * 0.08);
    if (egim > esik) return { yon: "yukari", ad: "↗ Yükseliyor", egim: egim };
    if (egim < -esik) return { yon: "asagi", ad: "↘ Düşüyor", egim: egim };
    return { yon: "sabit", ad: "→ Sabit", egim: egim };
  }

  // --------------------------------------------------------------- veri
  function veriYukle() {
    return Promise.all([
      fetch("/data/" + AGE + "/league.json", { cache: "no-store" }).then(function (r) { return r.json(); }),
      fetch("/data/" + AGE + "/team.json", { cache: "no-store" }).then(function (r) { return r.json(); })
    ]).then(function (res) {
      var lig = res[0], takim = res[1];
      durum.lig = lig;
      (takim.players || []).forEach(function (p) { durum.kadro[(p.name || "").toLowerCase()] = p; });

      var maclar = (lig.fixtures || []).filter(function (f) {
        return f.isOurs && f.played && f.boxscore;
      }).sort(function (a, b) { return String(a.date).localeCompare(String(b.date)); });

      var havuz = {};
      maclar.forEach(function (f, sira) {
        var bizim = f.isHome ? (f.boxscore.home || []) : (f.boxscore.away || []);
        var rakip = f.isHome ? f.away : f.home;
        var bizimSkor = f.isHome ? f.homeScore : f.awayScore;
        var rakipSkor = f.isHome ? f.awayScore : f.homeScore;
        bizim.forEach(function (r) {
          var ad = (r.name || "").trim();
          if (!ad) return;
          var anahtar = ad.toLowerCase();
          if (!havuz[anahtar]) {
            havuz[anahtar] = { name: ad, no: r.no, maclar: [] };
          }
          if (havuz[anahtar].no == null) havuz[anahtar].no = r.no;
          havuz[anahtar].maclar.push({
            sira: sira + 1, date: f.date, week: f.week, opp: rakip,
            sonuc: (bizimSkor > rakipSkor ? "G " : "M ") + bizimSkor + "-" + rakipSkor,
            dk: dakika(r.min), min: r.min,
            points: r.points || 0, rebounds: r.rebounds || 0, assists: r.assists || 0,
            steals: r.steals || 0, blocks: r.blocks || 0, turnovers: r.turnovers || 0,
            fouls: r.fouls || 0, efficiency: r.efficiency || 0,
            plusMinus: r.plusMinus, starter: !!r.starter
          });
        });
      });

      durum.oyuncular = Object.keys(havuz).map(function (k) {
        var o = havuz[k];
        var kadro = durum.kadro[k] || {};
        o.photo = kadro.photo || null;
        o.birthYear = kadro.birthYear || null;
        o.ort = {};
        OLCUTLER.forEach(function (m) {
          o.ort[m.k] = ortalama(o.maclar.map(function (x) { return x[m.k]; }));
        });
        o.toplamMac = o.maclar.length;
        return o;
      });
      durum.toplamMac = maclar.length;
      return analizleriIsle(maclar);
    });
  }

  /** Mac analizi dosyalarindan oyuncuya: gercek sure, +/-, atislar. */
  function analizleriIsle(maclar) {
    var analizli = (durum.lig.analiz || []);
    var istenen = maclar.filter(function (f) { return analizli.indexOf(f.matchId) !== -1; });
    return Promise.all(istenen.map(function (f) {
      return fetch("/data/" + AGE + "/analiz/" + f.matchId + ".json", { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (a) { return { fix: f, analiz: a }; })
        .catch(function () { return null; });
    })).then(function (liste) {
      liste.filter(Boolean).forEach(function (kayit) {
        var taraf = kayit.fix.isHome ? "home" : "away";
        var sureler = (kayit.analiz.players || {})[taraf] || {};
        var atislar = (kayit.analiz.shots || {})[taraf] || [];
        durum.oyuncular.forEach(function (o) {
          var mac = o.maclar.filter(function (m) { return m.date === kayit.fix.date; })[0];
          if (!mac || o.no == null) return;
          var s2 = sureler[String(o.no)];
          if (s2) {
            mac.pm = s2.pm;
            mac.gercekDk = s2.sec / 60;
          }
          var kendi = atislar.filter(function (x) { return String(x[4]) === String(o.no); });
          if (kendi.length) {
            mac.sut = kendi.length;
            mac.isabet = kendi.filter(function (x) { return x[3]; }).length;
            mac.isabetYuzde = Math.round((100 * mac.isabet) / kendi.length);
            o.atislar = (o.atislar || []).concat(kendi);
          }
        });
      });
      durum.oyuncular.forEach(function (o) {
        OLCUTLER.forEach(function (m) {
          var degerler = o.maclar.map(function (x) { return x[m.k]; })
            .filter(function (v) { return typeof v === "number"; });
          o.ort[m.k] = degerler.length ? ortalama(degerler) : 0;
        });
      });
    });
  }

  /** Oyuncunun butun maclardaki atislari tek yari sahada. */
  function atisHaritasi(atislar) {
    var m2p = 18, W = SAHA.en * m2p, H = SAHA.boy * m2p;
    function px(y) { return (y + SAHA.en / 2) * m2p; }
    function py(x) { return x * m2p; }
    var r = SAHA.ucR * m2p;
    var ciz = ['<rect x="0" y="0" width="' + W + '" height="' + H +
      '" fill="none" stroke="rgba(232,240,236,.18)"/>',
      '<rect x="' + px(-SAHA.boyaEn) + '" y="0" width="' + (SAHA.boyaEn * 2 * m2p) +
      '" height="' + py(SAHA.boyaBoy) + '" fill="none" stroke="rgba(232,240,236,.18)"/>',
      '<circle cx="' + px(0) + '" cy="' + py(SAHA.boyaBoy) + '" r="' + (SAHA.serbestR * m2p) +
      '" fill="none" stroke="rgba(232,240,236,.18)"/>',
      '<circle cx="' + px(0) + '" cy="' + py(SAHA.potaX) + '" r="' + (0.225 * m2p) +
      '" fill="none" stroke="rgba(232,240,236,.3)"/>',
      '<path d="M ' + px(-SAHA.ucKose) + " " + py(SAHA.ucKoseX) + " A " + r + " " + r +
      " 0 0 0 " + px(SAHA.ucKose) + " " + py(SAHA.ucKoseX) +
      '" fill="none" stroke="rgba(232,240,236,.18)"/>'];
    var isabet = 0;
    (atislar || []).forEach(function (s3) {
      if (s3[3]) isabet++;
      var X = px((s3[1] - 50) * BIRIM_Y).toFixed(1), Y = py(s3[0] * BIRIM_X).toFixed(1);
      ciz.push(s3[3]
        ? '<circle cx="' + X + '" cy="' + Y + '" r="4.5" fill="#f2a33c"/>'
        : '<circle cx="' + X + '" cy="' + Y + '" r="4.5" fill="none" ' +
          'stroke="rgba(232,240,236,.42)" stroke-width="1.4"/>');
    });
    return { svg: '<svg viewBox="0 0 ' + W + " " + H + '" role="img">' + ciz.join("") + "</svg>",
             isabet: isabet, deneme: (atislar || []).length };
  }

  // ------------------------------------------------------------- grafik
  /** Tek serili çizgi grafiği (SVG). Nokta sayısı 1 ise yalnız nokta çizer. */
  function cizgi(degerler, etiketler, renk) {
    var W = 320, H = 108, L = 26, R = 10, T = 12, B = 20;
    var enUst = Math.max.apply(null, degerler.concat([1]));
    var tavan = enUst <= 4 ? Math.ceil(enUst) : Math.ceil(enUst / 5) * 5;
    var ort = ortalama(degerler);
    var n = degerler.length;

    function x(i) { return n === 1 ? (L + (W - L - R) / 2) : L + (i * (W - L - R)) / (n - 1); }
    function y(v) { return T + (H - T - B) * (1 - (tavan ? v / tavan : 0)); }

    var parcalar = [];
    // Izgara: yalnız üst ve sıfır çizgisi — grafik verinin önüne geçmesin.
    [0, tavan].forEach(function (v) {
      parcalar.push('<line x1="' + L + '" y1="' + y(v).toFixed(1) + '" x2="' + (W - R) +
        '" y2="' + y(v).toFixed(1) + '" stroke="#24423d" stroke-width="1"/>');
      parcalar.push('<text x="' + (L - 5) + '" y="' + (y(v) + 3.5).toFixed(1) +
        '" fill="#5e7a75" font-size="9" text-anchor="end">' + v + "</text>");
    });
    // Ortalama: kesikli, gri — renk değil metin anlatıyor.
    if (n > 1) {
      parcalar.push('<line x1="' + L + '" y1="' + y(ort).toFixed(1) + '" x2="' + (W - R) +
        '" y2="' + y(ort).toFixed(1) + '" stroke="#8fa9a3" stroke-width="1" ' +
        'stroke-dasharray="4 3" opacity=".65"/>');
    }
    if (n > 1) {
      parcalar.push('<polyline fill="none" stroke="' + renk + '" stroke-width="2" ' +
        'stroke-linejoin="round" stroke-linecap="round" points="' +
        degerler.map(function (v, i) { return x(i).toFixed(1) + "," + y(v).toFixed(1); }).join(" ") +
        '"/>');
    }
    degerler.forEach(function (v, i) {
      parcalar.push('<circle class="nk" data-i="' + i + '" cx="' + x(i).toFixed(1) + '" cy="' +
        y(v).toFixed(1) + '" r="4.5" fill="' + renk + '" stroke="#132825" stroke-width="2"/>');
      // Dokunma alanı noktadan büyük olsun (parmak 4.5 px'i bulamaz).
      parcalar.push('<circle class="hit" data-i="' + i + '" cx="' + x(i).toFixed(1) + '" cy="' +
        y(v).toFixed(1) + '" r="16" fill="transparent"/>');
    });
    // Yalnızca son değer yazılır; her noktaya sayı basılmaz.
    var sonI = n - 1;
    parcalar.push('<text x="' + (n === 1 ? x(0) : x(sonI) - 4) + '" y="' + (y(degerler[sonI]) - 9).toFixed(1) +
      '" fill="#eff5f2" font-size="11" font-weight="700" text-anchor="' +
      (n === 1 ? "middle" : "end") + '">' + bir(degerler[sonI]) + "</text>");
    // X ekseni: ilk ve son maç.
    parcalar.push('<text x="' + L + '" y="' + (H - 5) + '" fill="#5e7a75" font-size="9">' +
      esc(etiketler[0]) + "</text>");
    if (n > 1) {
      parcalar.push('<text x="' + (W - R) + '" y="' + (H - 5) +
        '" fill="#5e7a75" font-size="9" text-anchor="end">' + esc(etiketler[sonI]) + "</text>");
    }
    return '<svg viewBox="0 0 ' + W + " " + H + '" role="img" preserveAspectRatio="xMidYMid meet">' +
      parcalar.join("") + "</svg>";
  }

  function grafikKutu(olcut, oyuncu) {
    var degerler = oyuncu.maclar.map(function (m) { return Math.round(m[olcut.k] * 10) / 10; });
    var etiketler = oyuncu.maclar.map(function (m) { return gunAy(m.date); });
    var e = egilim(degerler);
    return '<section class="chart" data-olcut="' + olcut.k + '">' +
      '<div class="ch-h"><h4>' + esc(olcut.ad) + "</h4>" +
      (e ? '<span class="egilim ' + e.yon + '">' + esc(e.ad) + "</span>" : "") +
      '<span class="ort">ort ' + bir(ortalama(degerler)) + "</span></div>" +
      cizgi(degerler, etiketler, "#f2a03d") +
      '<div class="cap" data-cap="' + olcut.k + '">' +
      (degerler.length > 1 ? "Noktaya dokununca o maçın değeri yazılır." : "") +
      "</div></section>";
  }

  // ------------------------------------------------------------- çizim
  function listeCiz() {
    el("siralama").innerHTML = SIRALAMA.map(function (s) {
      return '<button type="button" class="ghost" data-sirala="' + s.k + '"' +
        (durum.sirala === s.k ? ' aria-pressed="true" style="color:var(--amber);border-color:var(--amber)"' : "") +
        ">" + esc(s.ad) + "</button>";
    }).join("");

    var liste = durum.oyuncular.slice().sort(function (a, b) {
      if (durum.sirala === "no") return (a.no == null) - (b.no == null) || a.no - b.no;
      return b.ort[durum.sirala] - a.ort[durum.sirala];
    });

    el("olist").innerHTML = liste.map(function (o) {
      var birim = durum.sirala === "no" ? "" : "";
      var deger = durum.sirala === "no" ? (o.no == null ? "–" : o.no) : bir(o.ort[durum.sirala]);
      var etiket = (SIRALAMA.filter(function (s) { return s.k === durum.sirala; })[0] || {}).ad;
      return '<button type="button" class="orow" data-oyuncu="' + esc(o.name) + '">' +
        '<span class="no">' + (o.no == null ? "–" : esc(o.no)) + "</span>" +
        '<span><span class="nm">' + esc(o.name) + "</span>" +
        '<span class="alt">' + o.toplamMac + " maç · " + bir(o.ort.dk) + " dk ort</span></span>" +
        '<span class="big">' + esc(deger) + birim + "<small>" + esc(etiket) + " ort</small></span>" +
        "</button>";
    }).join("");

    el("listeMsg").innerHTML = durum.toplamMac
      ? '<p class="hint">' + durum.toplamMac + " oynanmış maçın istatistikleri TBF'den alınıyor.</p>"
      : '<div class="note"><div>Henüz oynanmış maç istatistiği yok. İlk maçtan sonra burası dolacak.</div></div>';
  }

  function oyuncuCiz(o) {
    var ml = o.maclar;
    var toplam = function (k) { return ml.reduce(function (a, m) { return a + m[k]; }, 0); };

    var kunye = '<div class="pkunye">' +
      (o.photo ? '<img src="' + esc(o.photo) + '" alt="" ' +
        'onerror="this.remove()">' : "") +
      "<div><h3>" + (o.no == null ? "" : esc(o.no) + " · ") + esc(o.name) + "</h3>" +
      '<div class="alt">' + o.toplamMac + " maç" +
      (o.birthYear ? " · " + o.birthYear + " doğumlu" : "") +
      " · " + toplam("points") + " sayı, " + toplam("rebounds") + " ribaund, " +
      toplam("assists") + " asist</div></div></div>";

    var tiles = '<div class="tiles">' +
      [["dk", "Dakika"], ["points", "Sayı"], ["rebounds", "Ribaund"],
       ["assists", "Asist"], ["steals", "Top çalma"], ["pm", "Sahadayken fark"]]
        .map(function (t) {
          return '<div class="tile"><b>' + bir(ortalama(ml.map(function (m) { return m[t[0]]; }))) +
            "</b><span>" + t[1] + " ort</span></div>";
        }).join("") + "</div>";

    var grafikler = '<h2>Gelişim</h2>' +
      (ml.length < 2
        ? '<div class="note"><div>Gelişim grafiği için en az iki maç gerekli; ' +
          "şu an " + ml.length + " maç var. Eğilim (yükseliyor/düşüyor) üç maçtan sonra yazılır.</div></div>"
        : "") +
      OLCUTLER.map(function (m) { return grafikKutu(m, o); }).join("");

    var harita = o.atislar && o.atislar.length ? atisHaritasi(o.atislar) : null;
    var sahaBolumu = harita
      ? "<h2>Atış haritası</h2>" +
        '<div class="chart" style="padding:.5rem">' + harita.svg + "</div>" +
        '<p class="hint" style="margin-top:-.3rem">' + harita.isabet + "/" + harita.deneme +
        " · %" + Math.round((100 * harita.isabet) / harita.deneme) +
        ". Dolu daire isabet, boş halka ıska; bütün maçlar üst üste.</p>"
      : "";

    var tablo = "<h2>Maç maç</h2>" +
      '<div class="mtable"><table><thead><tr><th>Maç</th><th>Dk</th><th>Sayı</th><th>Rib</th>' +
      "<th>Ast</th><th>Çal</th><th>Şut</th><th>Kayıp</th><th>Faul</th><th>+/–</th></tr></thead><tbody>" +
      ml.slice().reverse().map(function (m) {
        return "<tr><td>" + esc(gunAy(m.date)) + " · " + esc(m.opp) +
          '<div style="color:var(--chalk-faint);font-size:.75rem">' + esc(m.sonuc) +
          (m.starter ? " · ilk beş" : "") + "</div></td>" +
          "<td>" + esc(m.min || bir(m.dk)) + "</td><td><b>" + m.points + "</b></td><td>" + m.rebounds +
          "</td><td>" + m.assists + "</td><td>" + m.steals + "</td><td>" +
          (m.sut ? m.isabet + "/" + m.sut : "–") +
          "</td><td>" + m.turnovers + "</td><td>" + m.fouls + "</td><td>" +
          esc(m.pm != null ? (m.pm > 0 ? "+" + m.pm : m.pm)
                           : (m.plusMinus == null ? "" : m.plusMinus)) + "</td></tr>";
      }).join("") + "</tbody></table></div>";

    el("oyuncuIcerik").innerHTML = kunye + tiles + grafikler + sahaBolumu + tablo;
    el("listeGorunum").hidden = true;
    el("oyuncuGorunum").hidden = false;
    window.scrollTo({ top: 0, behavior: "auto" });
    durum.acik = o;
  }

  // ------------------------------------------------------------- olaylar
  document.addEventListener("click", function (ev) {
    var t = ev.target;
    if (!t.closest) return;

    var sirala = t.closest("[data-sirala]");
    if (sirala) { durum.sirala = sirala.dataset.sirala; listeCiz(); return; }

    var sec = t.closest("[data-oyuncu]");
    if (sec) {
      var ad = sec.dataset.oyuncu;
      var o = durum.oyuncular.filter(function (x) { return x.name === ad; })[0];
      if (o) oyuncuCiz(o);
      return;
    }

    if (t.closest("#geriBtn")) {
      el("oyuncuGorunum").hidden = true;
      el("listeGorunum").hidden = false;
      window.scrollTo({ top: 0, behavior: "auto" });
      return;
    }

    // Grafikte bir maça dokunma: o maçın değerini alt yazıda göster.
    var nokta = t.closest(".hit, .nk");
    if (nokta && durum.acik) {
      var kutu = nokta.closest(".chart");
      var olcut = kutu.dataset.olcut;
      var mac = durum.acik.maclar[Number(nokta.dataset.i)];
      if (!mac) return;
      var ad2 = (OLCUTLER.filter(function (m) { return m.k === olcut; })[0] || {}).ad;
      kutu.querySelector(".cap").textContent =
        gunAy(mac.date) + " · " + mac.opp + " · " + ad2 + ": " + bir(mac[olcut]) +
        (olcut === "dk" ? " dk" : "");
    }
  });

  // --------------------------------------------------------------- açılış
  P.requireLogin(function () {
    veriYukle().then(listeCiz).catch(function (err) {
      P.note("listeMsg", "bad", esc(err.message));
    });
  });
})();
