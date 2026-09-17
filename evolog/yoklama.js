/* Yoklama ekranı — antrenör bir antrenmanı seçer, kadroyu tek dokunuşla
 * işaretler, kaydeder.
 *
 * Tasarım kararları:
 *  - Seans listesi antrenman programından gelir; antrenör tarih yazmak zorunda
 *    kalmasın. "Başka gün" ile elle de girilebiliyor (telafi antrenmanı).
 *  - Varsayılan seçim, şimdiye en yakın geçmiş/bugünkü antrenman: yoklama
 *    genelde antrenmanın sonunda alınıyor.
 *  - Hiçbir oyuncu varsayılan olarak "geldi" değil; işaretlenmemiş oyuncu
 *    kaydedilmez. Yanlışlıkla tam katılım yazılmasın.
 */
(function () {
  "use strict";

  var P = window.EvologPanel;
  var AGE = "u14";
  var DURUMLAR = [
    { k: "geldi", ad: "Geldi" },
    { k: "gec", ad: "Geç" },
    { k: "gelmedi", ad: "Yok" },
    { k: "izinli", ad: "İzinli" }
  ];
  var GUNLER = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];
  var AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
               "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];

  var durum = {
    kadro: [],          // [{no, name, key}]
    seanslar: [],       // [{date, start, title, venue}]
    secili: null,       // seçili seans
    isaret: {},         // key -> durum
    kayitli: {},        // sunucudan gelen hali (değişiklik var mı diye)
    salonlar: {}        // venue id -> ad
  };

  function el(id) { return document.getElementById(id); }
  function esc(v) { return P.esc(v); }

  function iso(d) {
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  }
  function pad(n) { return (n < 10 ? "0" : "") + n; }

  function tarihAdi(isoStr) {
    var p = String(isoStr).split("-");
    var d = new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
    if (isNaN(d.getTime())) return isoStr;
    var bugun = iso(new Date());
    var etiket = d.getDate() + " " + AYLAR[d.getMonth()];
    if (isoStr === bugun) return "Bugün";
    return GUNLER[d.getDay()] + " · " + etiket;
  }

  function oyuncuAnahtar(p) {
    return p.tbfPlayerId ? String(p.tbfPlayerId) : String(p.name || "").trim().toLowerCase();
  }

  // ------------------------------------------------------------- yükleme
  function kadroYukle() {
    return fetch("/data/" + AGE + "/team.json", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (t) {
        durum.kadro = (t.players || []).map(function (p) {
          return { no: p.no, name: p.name || "", key: oyuncuAnahtar(p) };
        }).sort(function (a, b) {
          return (a.no == null) - (b.no == null) || (a.no - b.no);
        });
      });
  }

  function programYukle() {
    return P.api("/training?age=" + AGE).then(function (tr) {
      (tr.venues || []).forEach(function (v) { durum.salonlar[v.id] = v.name; });
      var hafta = tr.weekStart;
      if (!hafta) {                       // haftası yoksa bu haftayı varsay
        var b = new Date();
        b.setDate(b.getDate() - ((b.getDay() + 6) % 7));
        hafta = iso(b);
      }
      var p = hafta.split("-");
      durum.seanslar = (tr.sessions || []).map(function (s) {
        var d = new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]) + (s.day - 1));
        return { date: iso(d), start: s.start, title: s.title || "Antrenman", venue: s.venue };
      }).sort(function (a, b) {
        return (a.date + a.start).localeCompare(b.date + b.start);
      });
    }).catch(function () { durum.seanslar = []; });
  }

  /** Şimdiye en yakın geçmiş antrenman; yoksa ilk sıradaki. */
  function varsayilanSeans() {
    if (!durum.seanslar.length) {
      var simdi = new Date();
      return { date: iso(simdi), start: pad(simdi.getHours()) + ":00",
               title: "Antrenman", venue: null };
    }
    var now = new Date();
    var damga = iso(now) + pad(now.getHours()) + ":" + pad(now.getMinutes());
    var gecmis = durum.seanslar.filter(function (s) { return (s.date + s.start) <= damga; });
    return gecmis.length ? gecmis[gecmis.length - 1] : durum.seanslar[0];
  }

  // -------------------------------------------------------------- çizim
  function seansCiz() {
    var box = el("seansStrip");
    box.innerHTML = durum.seanslar.map(function (s) {
      var on = durum.secili && s.date === durum.secili.date && s.start === durum.secili.start;
      var salon = durum.salonlar[s.venue] || "";
      return '<button type="button" data-seans="' + esc(s.date + "|" + s.start) + '"' +
        ' aria-pressed="' + (on ? "true" : "false") + '">' +
        esc(tarihAdi(s.date) + " · " + s.start) +
        "<small>" + esc(s.title + (salon ? " · " + salon : "")) + "</small></button>";
    }).join("") || '<p class="hint">Bu haftanın programında antrenman yok. “Başka gün” ile girin.</p>';
  }

  function ozetCiz() {
    var say = { geldi: 0, gec: 0, gelmedi: 0, izinli: 0 };
    Object.keys(durum.isaret).forEach(function (k) { say[durum.isaret[k]]++; });
    var isaretli = say.geldi + say.gec + say.gelmedi + say.izinli;
    el("ozet").innerHTML =
      "<span><b>" + say.geldi + "</b> geldi</span>" +
      (say.gec ? "<span><b>" + say.gec + "</b> geç</span>" : "") +
      "<span><b>" + say.gelmedi + "</b> yok</span>" +
      (say.izinli ? "<span><b>" + say.izinli + "</b> izinli</span>" : "") +
      "<span>" + isaretli + "/" + durum.kadro.length + " işaretlendi</span>";

    var degisti = JSON.stringify(durum.isaret) !== JSON.stringify(durum.kayitli);
    el("saveMsg").textContent = !isaretli
      ? "Yoklama alınmadı."
      : (degisti ? "Kaydedilmemiş değişiklik var." : "Kaydedildi.");
    el("saveBtn").disabled = !isaretli || !degisti;
  }

  function kadroCiz() {
    el("plist").innerHTML = durum.kadro.map(function (p) {
      var secili = durum.isaret[p.key];
      return '<div class="prow' + (secili ? "" : " bos") + '" data-p="' + esc(p.key) + '">' +
        '<div class="no">' + (p.no == null ? "–" : esc(p.no)) + "</div>" +
        "<div>" +
          '<div class="nm">' + esc(p.name) + "</div>" +
          '<div class="seg">' +
            DURUMLAR.map(function (d) {
              return '<button type="button" data-s="' + d.k + '" data-p="' + esc(p.key) + '"' +
                ' aria-pressed="' + (secili === d.k ? "true" : "false") + '">' + d.ad + "</button>";
            }).join("") +
          "</div>" +
        "</div></div>";
    }).join("");
    ozetCiz();
  }

  function devamCiz(ozet) {
    var satirlar = (ozet.players || []).filter(function (r) { return r.oran !== null; });
    if (!satirlar.length) {
      el("devam").innerHTML = '<p class="hint">Henüz yeterli yoklama kaydı yok.</p>';
      return;
    }
    el("devam").innerHTML =
      "<table><thead><tr><th>Oyuncu</th><th>Geldi</th><th>Yok</th>" +
      '<th style="text-align:right">Oran</th></tr></thead><tbody>' +
      satirlar.map(function (r) {
        var sinif = r.oran >= 80 ? "" : (r.oran >= 60 ? " class=\"orta\"" : " class=\"az\"");
        return "<tr><td>" + (r.no == null ? "" : "<b>" + esc(r.no) + "</b> ") + esc(r.name) +
          '<div class="bar"><i' + sinif + ' style="width:' + r.oran + '%"></i></div></td>' +
          "<td>" + (r.geldi + r.gec) + "</td><td>" + r.gelmedi + "</td>" +
          '<td class="o">%' + r.oran + "</td></tr>";
      }).join("") + "</tbody></table>" +
      '<p class="hint">' + (ozet.sessions || []).length + " antrenman kaydı üzerinden.</p>";
  }

  // --------------------------------------------------------------- veri
  function seansSec(s) {
    durum.secili = s;
    durum.isaret = {};
    durum.kayitli = {};
    seansCiz();
    kadroCiz();
    el("elleTarih").value = s.date;
    el("elleSaat").value = s.start;
    P.api("/attendance?age=" + AGE + "&date=" + s.date + "&start=" + encodeURIComponent(s.start))
      .then(function (kayit) {
        durum.isaret = Object.assign({}, kayit.players || {});
        durum.kayitli = Object.assign({}, kayit.players || {});
        if (kayit.takenAt) {
          P.note("seansMsg", "ok", "Bu antrenmanın yoklaması daha önce alınmış; " +
            "değiştirip tekrar kaydedebilirsiniz.");
        } else {
          el("seansMsg").innerHTML = "";
        }
        kadroCiz();
      }).catch(function (err) {
        P.note("seansMsg", "bad", esc(err.message));
      });
  }

  function devamYukle() {
    P.api("/attendance/summary?age=" + AGE + "&limit=20").then(devamCiz).catch(function () {
      el("devam").innerHTML = '<p class="hint">Devam durumu okunamadı.</p>';
    });
  }

  function kaydet() {
    if (!durum.secili) return;
    el("saveBtn").disabled = true;
    el("saveMsg").textContent = "Kaydediliyor…";
    P.api("/attendance?age=" + AGE, {
      method: "POST",
      body: JSON.stringify({
        date: durum.secili.date, start: durum.secili.start,
        title: durum.secili.title, venue: durum.secili.venue,
        players: durum.isaret
      })
    }).then(function (res) {
      durum.kayitli = Object.assign({}, durum.isaret);
      ozetCiz();
      P.note("seansMsg", "ok", "<b>Kaydedildi.</b> " + esc(tarihAdi(durum.secili.date)) +
        " " + esc(durum.secili.start) + " · " + res.gelen + "/" + res.toplam + " geldi.");
      // Kullanıcı kaydettikten sonra başa döner: sonuç mesajı ve seans şeridi
      // ekranın üstünde, oradan bir sonraki antrenmana geçilir.
      window.scrollTo({ top: 0, behavior: "smooth" });
      devamYukle();
    }).catch(function (err) {
      P.note("seansMsg", "bad", esc(err.message));
      el("saveBtn").disabled = false;
    });
  }

  // ------------------------------------------------------------- olaylar
  document.addEventListener("click", function (ev) {
    var t = ev.target;
    if (!t.closest) return;

    var seans = t.closest("[data-seans]");
    if (seans) {
      var parts = seans.dataset.seans.split("|");
      var bul = durum.seanslar.filter(function (s) {
        return s.date === parts[0] && s.start === parts[1];
      })[0];
      if (bul) seansSec(bul);
      return;
    }

    var tik = t.closest(".seg button");
    if (tik) {
      var key = tik.dataset.p;
      if (durum.isaret[key] === tik.dataset.s) delete durum.isaret[key];
      else durum.isaret[key] = tik.dataset.s;
      kadroCiz();
      return;
    }

    if (t.closest("#hepsiBtn")) {
      durum.kadro.forEach(function (p) { durum.isaret[p.key] = "geldi"; });
      kadroCiz();
      return;
    }
    if (t.closest("#temizleBtn")) { durum.isaret = {}; kadroCiz(); return; }
    if (t.closest("#elleBtn")) {
      var d = el("elleTarih").value, s = el("elleSaat").value;
      if (!d || !s) { P.note("seansMsg", "bad", "Tarih ve saat gerekli."); return; }
      seansSec({ date: d, start: s, title: "Antrenman", venue: null });
      return;
    }
    if (t.closest("#saveBtn")) kaydet();
  });

  // --------------------------------------------------------------- açılış
  P.requireLogin(function () {
    el("bar").hidden = false;
    kadroYukle()
      .then(programYukle)
      .then(function () {
        seansCiz();
        seansSec(varsayilanSeans());
        devamYukle();
      })
      .catch(function (err) { P.note("seansMsg", "bad", esc(err.message)); });
  });
})();
