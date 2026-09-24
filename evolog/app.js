/* Evolog U14 Kız — uygulama mantığı */
(function () {
  "use strict";

  var DATA_BASE = window.EVOLOG_DATA_PATH || "../data/";
  var INLINE = window.EVOLOG_INLINE_DATA || null;
  var QUERY = new URLSearchParams(location.search);
  var DEMO = QUERY.get("demo") === "1";
  var PANELS = ["maclar", "puan", "kadro", "antrenman"];

  // Yas gruplari: her birinin kendi veri klasoru var (data/<key>/). Secim
  // localStorage'da durur, yani uygulama bir sonraki degisiklige kadar hep
  // secili takimla acilir.
  // Su an tek takim var. Yeni yas grubu eklemek icin bu listeye bir satir
  // eklemek ve data/<key>/ klasorunu olusturmak yeterli: secici kendiliginden
  // geri gelir (tek grupta gizli durur).
  var AGES = [
    { key: "u14", label: "U14", title: "U14 Kızlar" }
  ];
  var AGE_STORE = "evolog.age";
  var PUSH_STORE = "evolog.pushAges";
  var IOS_STORE = "evolog.iosHint";
  var DUYURU_STORE = "evolog.duyuruOkundu";   // okundu isaretlenen duyuru id'leri
  var DUYURU_SIL_STORE = "evolog.duyuruSilindi";   // velinin kendi silmesi (mezar tasi)

  // localStorage gizli sekmede ya da kapali depolamada patlayabilir.
  function store(key, value) {
    try {
      if (value === undefined) return localStorage.getItem(key);
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, value);
    } catch (e) { /* depolama yok: varsayilanlarla devam */ }
    return null;
  }

  function knownAge(key) {
    for (var i = 0; i < AGES.length; i++) if (AGES[i].key === key) return key;
    return null;
  }

  // Bildirime dokunulunca gelen ?age=u14 baglantisi secimi de degistirir.
  var age = knownAge(QUERY.get("age")) || knownAge(store(AGE_STORE)) || AGES[0].key;

  function ageInfo(key) {
    var want = key || age;
    for (var i = 0; i < AGES.length; i++) if (AGES[i].key === want) return AGES[i];
    return AGES[0];
  }

  function dataPath() { return DATA_BASE + age + "/"; }

  var GUNLER = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];
  var AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

  var state = { team: null, training: null, league: null, venues: null, timer: null };

  // Arka planda kendini tazeleme: sunucu TBF'den her 10 dk veri çektiği için
  // uygulama da açık kaldığı sürece yeni skoru/istatistiği kendiliğinden alır.
  var REFRESH_MS = 90000;
  var sync = { poll: null, lastCheck: 0, busy: false, sig: null };

  // ------------------------------------------------------------- yardımcı
  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function el(id) { return document.getElementById(id); }

  function norm(s) {
    return String(s || "")
      .replace(/İ/g, "i").replace(/I/g, "i").replace(/ı/g, "i")
      .normalize("NFKD").replace(/[̀-ͯ]/g, "")
      .trim().toLowerCase();
  }

  var ICONS = {
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    pin: '<path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11Z"/><circle cx="12" cy="10" r="2.5"/>',
    cal: '<rect x="3" y="5" width="18" height="16" rx="1"/><path d="M3 10h18M8 3v4M16 3v4"/>'
  };
  function ico(name) {
    return '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">' + ICONS[name] + "</svg>";
  }

  // Takım logosu: TBF dışarıya bağlantı vermiyor, bu yüzden logolar
  // senkronizasyonda indirilip uygulamayla birlikte sunuluyor.
  function teamLogo(src, size) {
    if (!src) return "";
    return '<img class="lg' + (size ? " " + size : "") + '" src="' + esc(src) +
      '" alt="" loading="lazy" decoding="async">';
  }
  function teamCell(name, logo) {
    return '<span class="tm">' + teamLogo(logo) + "<span>" + esc(name) + "</span></span>";
  }

  // Forma numarasına göre sıralama. 0 geçerli bir numara — "|| 99" ile
  // numarasızlara karışmasın diye ayrıca kontrol ediliyor.
  function jersey(no) { return no == null || no === "" ? 999 : Number(no); }

  function matchDate(f) {
    if (!f || !f.date) return null;
    var p = String(f.date).split("-").map(Number);
    if (p.length < 3 || !p[0]) return null;
    var t = (f.time || "00:00").split(":").map(Number);
    return new Date(p[0], p[1] - 1, p[2], t[0] || 0, t[1] || 0);
  }

  function fmtDate(d) {
    return d ? d.getDate() + " " + AYLAR[d.getMonth()] + " " + d.getFullYear() +
      ", " + GUNLER[d.getDay()] : "";
  }

  /** "2026-10-03","18:30" -> "3 Eki Cmt 18:30" */
  function fmtShort(dateStr, timeStr) {
    var p = String(dateStr || "").split("-").map(Number);
    if (p.length < 3 || !p[0]) return dateStr || "";
    var d = new Date(p[0], p[1] - 1, p[2]);
    var out = d.getDate() + " " + AYLAR[d.getMonth()] + " " + GUNLER[d.getDay()].slice(0, 3);
    return timeStr ? out + " " + timeStr : out;
  }

  /**
   * Kulübün RESMİ adı. TBF'de ve TBF'nin Drive'ında "EVOLOG",
   * "DAÇKA ŞERİFALİ", "EVOLOG DAÇKA ŞERİFALİ" gibi karışık yazımlar dolaşıyor.
   * Uygulamada her yerde bu ad görünür.
   *
   * Düzeltme neden veri dosyasında değil BURADA: senkron `data/` altını saat
   * başı TBF'den yeniden yazıyor (ve git reset --hard ile eziyor), yani veriye
   * yazılan her düzeltme bir saat içinde kaybolur. Görüntüleme katmanı kalıcı.
   */
  var KULUP_ADI = "Şerifali Spor Kulübü";

  function isOurTeam(name) {
    // TBF yazımlarının hepsi: "EVOLOG", "DAÇKA ŞERİFALİ", ikisinin birleşimi.
    var aliases = ["evolog", "serifali", "dacka"];
    if (state.team && state.team.club) aliases.push(norm(state.team.club));
    var n = norm(name);
    return aliases.some(function (a) { return a && n.indexOf(a) !== -1; });
  }

  /** Ekrana yazılacak takım adı: bizim takımsa resmî ada çevrilir. */
  function takimAdi(ad) {
    return isOurTeam(ad) ? KULUP_ADI : (ad || "");
  }

  // ------------------------------------------------------------- veri
  /** Yaş grubundan bağımsız, data/ kökündeki dosya. */
  function loadRoot(key, file) {
    if (INLINE) return Promise.resolve(INLINE[key] || null);
    return fetch((window.EVOLOG_DATA_PATH || "../data/") + file, { cache: "no-cache" })
      .then(function (r) { if (!r.ok) throw new Error(file); return r.json(); })
      .catch(function () { return null; });
  }

  function load(key, file) {
    if (INLINE) return Promise.resolve(INLINE[key] || null);
    return fetch(dataPath() + file, { cache: "no-cache" })
      .then(function (r) { if (!r.ok) throw new Error(file); return r.json(); })
      .catch(function () { return null; });
  }

  function loadAll() {
    return Promise.all([
      load("team", "team.json"),
      load("training", "training.json"),
      load(DEMO ? "leagueDemo" : "league", DEMO ? "league.example.json" : "league.json"),
      loadRoot("venues", "venues.json")
    ]);
  }

  // Verinin "parmak izi": bunlardan biri değişmişse ekran yenilenir.
  function signature(team, training, league) {
    var lg = league || {};
    var skor = (lg.fixtures || []).map(function (f) {
      return [f.matchId, f.homeScore, f.awayScore,
        (f.boxscore && f.boxscore.home ? f.boxscore.home.length : 0),
        (f.quarters || []).length].join(":");
    }).join("|");
    var puan = (lg.standings || []).map(function (r) {
      return [r.team, r.played, r.points, r.pointsFor, r.pointsAgainst].join(":");
    }).join("|");
    return [lg.updatedAt, skor, puan,
      ((team || {}).players || []).length,
      JSON.stringify((training || {}).sessions || []).length].join("#");
  }

  function toast(msg) {
    var box = el("toast");
    if (!box) return;
    box.textContent = msg;
    box.hidden = false;
    box.classList.add("show");
    clearTimeout(toast._t);
    toast._t = setTimeout(function () {
      box.classList.remove("show");
      setTimeout(function () { box.hidden = true; }, 400);
    }, 4200);
  }

  function pulseSync() {
    var box = el("syncBox");
    if (!box) return;
    box.classList.remove("pulse");
    void box.offsetWidth;   // animasyon yeniden baslasin
    box.classList.add("pulse");
  }

  function refresh(announce) {
    if (INLINE || sync.busy) return Promise.resolve(false);
    sync.busy = true;
    sync.lastCheck = Date.now();
    return loadAll().then(function (res) {
      sync.busy = false;
      if (!res[2] && !res[0]) return false;      // ağ yok: eldeki veriyi koru
      var sig = signature(res[0], res[1], res[2]);
      if (sig === sync.sig) { renderSync(); return false; }
      sync.sig = sig;
      state.team = res[0] || state.team;
      state.training = res[1] || state.training;
      state.league = res[2] || state.league;
      state.venues = res[3] || state.venues;
      var y = window.scrollY;
      render();
      window.scrollTo(0, y);
      // Yeni veri geldiginde ekrani mesajla bolmuyoruz; ust bardaki saat
      // sessizce yenilenir ve kisa bir vurgu verir.
      if (announce) pulseSync();
      return true;
    }).catch(function () { sync.busy = false; return false; });
  }

  function startAutoRefresh() {
    if (INLINE || sync.poll) return;
    sync.poll = setInterval(function () {
      // Duyuru da yoklanir: uygulama acikken gelen duyuru icin yenileme
      // beklenmesin (bildirimi kapali veli yalnizca burayi gorur).
      if (document.visibilityState === "visible") { refresh(true); loadDuyuru(); }
    }, REFRESH_MS);
    document.addEventListener("visibilitychange", function () {
      // Uygulamaya dönüldüğünde (telefonda en sık bu olur) hemen bak.
      if (document.visibilityState === "visible" && Date.now() - sync.lastCheck > 15000) {
        refresh(true);
        loadDuyuru();
      }
    });
    window.addEventListener("online", function () { refresh(true); });
  }

  function applyData(res) {
    state.team = res[0];
    state.training = res[1];
    state.league = res[2];
    state.venues = res[3] || state.venues;
    sync.sig = signature(res[0], res[1], res[2]);
    sync.lastCheck = Date.now();
  }

  // Yas degistirme: veri yolu degisir, ekran bastan yuklenir. Secim kalici.
  function setAge(key) {
    if (!knownAge(key) || key === age) { closeSheet(); return; }
    age = key;
    store(AGE_STORE, key);
    closeSheet();
    state.team = null; state.training = null; state.league = null;
    sync.sig = null;
    renderIdentity();
    var box = el("syncBox");
    if (box) box.innerHTML = '<span class="dot off"></span>yükleniyor';
    loadAll().then(function (res) {
      applyData(res);
      render();
      window.scrollTo(0, 0);
    });
  }

  function teamTitle() {
    var lg = state.league || {}, tm = state.team || {};
    // TBF'nin adı ne olursa olsun kulüp RESMİ adıyla görünür; yaş grubu ekli.
    var yas = (tm && tm.team) || ageInfo().title;
    return (KULUP_ADI + " " + (yas || "")).trim();
  }

  function renderIdentity() {
    var name = teamTitle();
    var h1 = el("teamName");
    if (h1) h1.textContent = name;
    document.title = name;
    var badge = el("ageBadge");
    if (badge) badge.textContent = ageInfo().label;
  }

  function boot() {
    loadAll().then(function (res) {
      applyData(res);
      render();
      startAutoRefresh();
      initPush();
    });
    // Bildirime dokunan veli dogrudan tam metne dussun.
    loadDuyuru().then(function () {
      if (QUERY.get("duyuru") === "1") openDuyuru();
    });
  }

  // ------------------------------------------------------------- üst bar
  function renderSync() {
    var box = el("syncBox"), lg = state.league;
    if (!lg) { box.innerHTML = '<span class="dot off"></span>veri yok'; return; }
    if (lg.league) {
      el("leagueLabel").textContent = lg.league + (lg.group ? " · " + lg.group : "");
    }
    if (!lg.updatedAt) { box.innerHTML = '<span class="dot off"></span>senkronize değil'; return; }
    var d = new Date(lg.updatedAt);
    var saat = (Date.now() - d.getTime()) / 36e5;
    box.innerHTML = '<span class="dot ' + (saat < 24 ? "ok" : saat < 96 ? "stale" : "off") +
      '"></span>TBF verisi<br><span class="stamp">' +
      esc(d.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit" })) + " " +
      esc(d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })) + "</span>";
  }

  function notice(lg) {
    if (!lg) {
      return '<div class="note bad"><div>Lig verisi yüklenemedi. Sayfayı yenileyin ya da ' +
        "<code>data/league.json</code> dosyasını kontrol edin.</div></div>";
    }
    if (lg.isDemo) {
      return '<div class="note"><div><b>Örnek veri.</b> Buradaki maçlar ve puanlar gerçek değil, ' +
        "yalnızca ekranın nasıl görüneceğini gösteriyor.</div></div>";
    }
    if (lg.isPlaceholder || (!(lg.standings || []).length && !(lg.fixtures || []).length)) {
      return '<div class="note"><div><b>TBF verisi henüz çekilmedi.</b> ' +
        "Sunucudaki senkronizasyon birazdan çalışacak; ekran kendiliğinden " +
        "güncellenecek.</div></div>";
    }
    if (lg.errors && lg.errors.length) {
      return '<div class="note bad"><div><b>Son senkronizasyon uyarıları</b><br>' +
        lg.errors.map(esc).join("<br>") + "</div></div>";
    }
    return "";
  }

  // ------------------------------------------------------------- maçlar
  function splitFixtures() {
    var list = ((state.league && state.league.fixtures) || []).slice();
    list.forEach(function (f) {
      f._d = matchDate(f);
      if (f.isOurs == null) f.isOurs = isOurTeam(f.home) || isOurTeam(f.away);
    });
    var now = Date.now();
    var played = list.filter(function (f) { return f.homeScore != null && f.awayScore != null; });
    var upcoming = list.filter(function (f) {
      return !(f.homeScore != null && f.awayScore != null) &&
        (!f._d || f._d.getTime() > now - 3 * 36e5);
    });
    played.sort(function (a, b) { return (b.date || "").localeCompare(a.date || ""); });
    upcoming.sort(function (a, b) { return (a.date || "").localeCompare(b.date || ""); });
    return { played: played, upcoming: upcoming };
  }

  function renderBoard(next) {
    var slot = el("boardSlot");
    if (!next) { slot.innerHTML = ""; return; }
    var d = next._d;
    var belli = next.dateConfirmed !== false;

    // Tarihi kesin olmayan mac "siradaki mac" kartina hic girmez: geri sayim
    // ve amber, yalnizca TBF'nin ilan ettigi tarihe ayrilmis isaretlerdir.
    if (!belli) {
      slot.innerHTML =
        '<div class="sec"><span class="label">Sıradaki maç</span><i class="hair"></i></div>' +
        '<article class="event event--tbd">' +
          '<div class="ev-body"><div class="ev-team">' + esc(takimAdi(next.home)) + "</div>" +
          '<div class="ev-team">' + esc(takimAdi(next.away)) + "</div>" +
          '<div class="ev-sub">Tarih TBF tarafından ilan edilmedi' +
          (next.week ? " · " + esc(next.week) + ". hafta" : "") + "</div></div></article>";
      return;
    }

    slot.innerHTML =
      '<div class="sec"><span class="label">Sıradaki maç' +
        (next.week ? " · " + esc(next.week) + ". hafta" : "") + '</span><i class="hair"></i></div>' +
      '<section class="nextcard">' +
        '<div class="nc-teams">' +
          '<div class="nc-side"><div class="nc-tn">' + esc(takimAdi(next.home)) + "</div>" +
            '<div class="unit">Ev sahibi</div></div>' +
          '<div class="nc-vs">VS</div>' +
          '<div class="nc-side right"><div class="nc-tn">' + esc(takimAdi(next.away)) + "</div>" +
            '<div class="unit">Deplasman</div></div>' +
        "</div>" +
        '<div class="nc-meta">' +
          "<span>" + esc(fmtDate(d)) + "</span>" +
          (next.time ? '<span class="amber">' + esc(next.time) + "</span>" : "") +
        "</div>" +
        (next.venue ? '<div class="nc-venue">' + esc(next.venue) + "</div>" : "") +
        (next.changedAt && next.previousDate
          ? '<div class="event-note"><b>Değişti</b> önce ' +
            esc(fmtShort(next.previousDate, next.previousTime)) + " idi</div>"
          : "") +
        '<div class="clock" id="clock"></div>' +
      "</section>";
    startClock(d);
  }

  function startClock(target) {
    if (state.timer) clearInterval(state.timer);
    function tick() {
      var box = el("clock");
      if (!box) { clearInterval(state.timer); return; }
      var diff = target.getTime() - Date.now();
      if (diff <= 0) {
        box.className = "clock live";
        box.innerHTML = '<div class="seg2 live" style="grid-column:1/-1">' +
          '<span class="n">MAÇ GÜNÜ</span></div>';
        clearInterval(state.timer);
        return;
      }
      box.innerHTML = [
        [Math.floor(diff / 864e5), "gün"],
        [Math.floor(diff / 36e5) % 24, "saat"],
        [Math.floor(diff / 6e4) % 60, "dakika"],
        [Math.floor(diff / 1e3) % 60, "saniye"]
      ].map(function (p) {
        return '<div class="seg2"><span class="n">' + (p[0] < 10 ? "0" + p[0] : p[0]) +
          '</span><span class="unit">' + p[1] + "</span></div>";
      }).join("");
    }
    tick();
    state.timer = setInterval(tick, 1000);
  }

  function tagFor(f) {
    if (f.homeScore == null) return "";        // oynanacak: rozet gereksiz gurultu
    if (!f.isOurs) return "";
    var ourHome = isOurTeam(f.home);
    var biz = ourHome ? f.homeScore : f.awayScore;
    var rakip = ourHome ? f.awayScore : f.homeScore;
    return biz > rakip ? '<span class="badge win">Galibiyet</span>'
                       : '<span class="badge loss">Mağlubiyet</span>';
  }

  function hasDetail(f) {
    return !!((f.quarters && f.quarters.length) ||
      (f.boxscore && ((f.boxscore.home || []).length || (f.boxscore.away || []).length)));
  }

  /**
   * Oyuncu bu maçta sahaya çıktı mı?
   * TBF kutu skoru kadroda olup hiç oynamayanı da listeleyebiliyor; o zaman
   * dakika "00:00" gelir. Önce dakikaya bakılır, yoksa (TBF kimi maçta
   * dakika göndermiyor) herhangi bir istatistik izi aranır: bir oyuncu
   * ribaund aldıysa sahaya çıkmıştır.
   * Faul ve top kaybı da sayılır — kötü geçen bir dakika da dakikadır.
   */
  function sahayaCikti(r) {
    var m = String(r.min == null ? "" : r.min).match(/^(\d+):(\d+)/);
    if (m) return Number(m[1]) * 60 + Number(m[2]) > 0;
    return ["points", "rebounds", "assists", "steals", "blocks", "turnovers", "fouls"]
      .some(function (k) { return Number(r[k]) > 0; });
  }

  function boxTable(rows, title) {
    if (!rows || !rows.length) return "";
    var cols = [["min", "DK"], ["points", "SAY"], ["rebounds", "RIB"], ["assists", "AST"],
      ["steals", "TOP Ç"], ["blocks", "BLK"], ["turnovers", "HATA"], ["fouls", "FAUL"]]
      .filter(function (c) { return rows.some(function (r) { return r[c[0]] != null; }); });
    return '<div class="box-title">' + esc(title) + "</div>" +
      '<div class="scroll"><table class="box"><thead><tr><th>#</th><th>Oyuncu</th>' +
      cols.map(function (c) { return "<th>" + esc(c[1]) + "</th>"; }).join("") +
      "</tr></thead><tbody>" +
      rows.map(function (r) {
        var yildiz = sahayaCikti(r)
          ? '<i class="pstar" title="Sahaya çıktı">★</i>' : "";
        return '<tr class="' + (sahayaCikti(r) ? "oynadi" : "oynamadi") + '"><td>' +
          esc(r.no != null ? r.no : "") + "</td><td>" + esc(r.name || "") + yildiz + "</td>" +
          cols.map(function (c) {
            return "<td" + (c[0] === "points" ? ' class="pts"' : "") + ">" +
              esc(r[c[0]] != null ? r[c[0]] : "–") + "</td>";
          }).join("") + "</tr>";
      }).join("") + "</tbody></table></div>";
  }

  /** Mac karti. Iki tip var ve hicbir stil paylasmiyorlar:
   *   .event      — TBF tarihi ilan etmis: sol amber serit, gun + saat.
   *   .event--tbd — ilan etmemis: kesikli cerceve, tarali zemin, saat YOK.
   *  Amac: veli listeyi kaydirirken belirsizleri tek gri blok olarak gorsun,
   *  kesin mac tek basina ayrissin. */
  function fixtureRow(f, idx, opts) {
    opts = opts || {};
    var d = f._d;
    var played = f.homeScore != null && f.awayScore != null;
    var belli = f.dateConfirmed !== false;
    var detail = hasDetail(f);
    var bodyId = "fb-" + idx;
    var homeWin = played && f.homeScore > f.awayScore;
    var awayWin = played && f.awayScore > f.homeScore;

    var tarih = belli
      ? '<div class="ev-date"><span class="dd">' + (d ? d.getDate() : "–") + "</span>" +
        '<span class="mm">' + (d ? esc(AYLAR[d.getMonth()]) +
          (played ? "" : " " + esc(GUNLER[d.getDay()].slice(0, 3))) : "") + "</span>" +
        (!played && f.time ? '<span class="hh">' + esc(f.time) + "</span>" : "") + "</div>"
      : '<div class="ev-date"><span class="dd">?</span><span class="mm">' +
        (f.week ? esc(f.week) + ". hafta" : "tarih yok") + "</span></div>";

    var takimlar = played
      ? '<div class="ev-score"><span class="ev-team ' + (homeWin ? "won" : awayWin ? "lost" : "") +
          '">' + esc(takimAdi(f.home)) + '</span><span class="sc">' + esc(f.homeScore) + "</span></div>" +
        '<div class="ev-score"><span class="ev-team ' + (awayWin ? "won" : homeWin ? "lost" : "") +
          '">' + esc(takimAdi(f.away)) + '</span><span class="sc">' + esc(f.awayScore) + "</span></div>"
      : '<div class="ev-team">' + esc(takimAdi(f.home)) + "</div>" +
        '<div class="ev-team">' + esc(takimAdi(f.away)) + "</div>";

    var alt;
    if (!belli) {
      alt = "Tarih TBF tarafından ilan edilmedi";
    } else if (played) {
      alt = (f.quarters || []).map(function (q) { return q.home + "-" + q.away; }).join(" · ") ||
        [f.venue, f.week ? f.week + ". hafta" : null].filter(Boolean).join(" · ");
    } else {
      alt = [f.venue, f.week ? f.week + ". hafta" : null].filter(Boolean).join(" · ");
    }

    var govde = "<div>" + takimlar +
      (alt ? '<div class="ev-sub">' + esc(alt) + "</div>" : "") +
      (belli && f.changedAt && f.previousDate
        ? '<div class="ev-chg">Değişti · önce ' +
          esc(fmtShort(f.previousDate, f.previousTime)) + " idi</div>"
        : "") +
      "</div>";

    var sag = '<div class="ev-right">' + tagFor(f) +
      (detail ? '<span class="ev-detay">Detay ▾</span>' : "") + "</div>";

    var sinif = "event" + (belli ? "" : " event--tbd") + (opts.hot ? " hot" : "");
    if (!detail) {
      return '<div class="' + sinif + '">' + tarih + govde + sag + "</div>";
    }

    var per = (f.quarters || []).map(function (x, i) {
      return '<div class="p"><span class="pn">' + (i + 1) + '. Ç</span>' +
        '<span class="ps">' + esc(x.home) + "–" + esc(x.away) + "</span></div>";
    }).join("");

    return '<article class="fxwrap">' +
      '<button class="' + sinif + '" aria-expanded="false" aria-controls="' + bodyId + '">' +
        tarih + govde + sag +
      "</button>" +
      '<div class="fx-body" id="' + bodyId + '" hidden>' +
        (per ? '<div class="periods">' + per + "</div>" : "") +
        boxTable(f.boxscore && f.boxscore.home, f.home) +
        boxTable(f.boxscore && f.boxscore.away, f.away) +
      "</div></article>";
  }

  function renderMatches() {
    el("matchNotice").innerHTML = notice(state.league);
    var sets = splitFixtures();
    // Geri sayim yalnizca tarihi kesinlesmis maca yapilir; TBF'nin uretilmis
    // dolgu tarihine saat saymak veliyi yanlis gune goturur.
    var bizim = sets.upcoming.filter(function (f) { return f.isOurs !== false; });
    var kesin = bizim.filter(function (f) { return f.dateConfirmed !== false; });
    renderBoard(kesin[0] || bizim[0] || sets.upcoming[0]);

    // Sıralama: sıradaki maç → son oynanan maç → yaklaşan fikstür → önceki
    // maçlar. Taze sonuç en üstte dursun; geçmişe bakmak isteyen aşağı iner.
    var son = sets.played[0] || null;
    var oncekiler = sets.played.slice(1);

    el("lastTitle").hidden = !son;
    el("lastTitle").innerHTML = '<span class="label">Son maç</span><i class="hair"></i>';
    el("lastMatch").innerHTML = son ? fixtureRow(son, "s0", { hot: true }) : "";

    // Basligin saginda iki sayac: kac macin tarihi kesin, kac tanesi bekliyor.
    // Veli listeye bakmadan once beklentiyi dogru kuruyor.
    var kesinSayi = sets.upcoming.filter(function (f) { return f.dateConfirmed !== false; }).length;
    var bekleyen = sets.upcoming.length - kesinSayi;
    el("upcomingTitle").innerHTML =
      '<span class="label">Yaklaşan · ' + sets.upcoming.length + ' maç</span>' +
      '<i class="hair"></i>' +
      '<span class="cnt"><b>' + kesinSayi + " kesin</b> · " + bekleyen + " bekliyor</span>";

    el("upcomingList").innerHTML = sets.upcoming.length
      ? sets.upcoming.map(function (f, i) { return fixtureRow(f, "u" + i); }).join("")
      : '<div class="blank">Planlanmış maç görünmüyor.</div>';

    el("prevTitle").hidden = !oncekiler.length;
    el("prevTitle").innerHTML = '<span class="label">Önceki maçlar</span><i class="hair"></i>';
    el("playedList").innerHTML = oncekiler.length
      ? oncekiler.map(function (f, i) { return fixtureRow(f, "p" + i); }).join("")
      : "";
  }

  // ---------------------------------------------------------- lig geneli
  // Kendi maçlarımız ayrı sekmede; burada tüm ligin haftalık programı var.
  // Açılışta güncel hafta açık gelir, diğerleri katlanmış durur.
  function currentWeek(list) {
    var now = Date.now(), best = null;
    list.forEach(function (f) {
      var d = matchDate(f);
      if (!d) return;
      if (d.getTime() >= now - 6 * 36e5 && (best === null || f.week < best)) best = f.week;
    });
    return best || (list.length ? list[list.length - 1].week : 1);
  }

  function renderLeagueWeeks() {
    var box = el("leagueWeeks");
    if (!box) return;
    var list = (state.league && state.league.leagueFixtures) || [];
    if (!list.length) {
      box.innerHTML = '<div class="blank">Lig fikstürü henüz çekilmedi.</div>';
      return;
    }
    var weeks = [];
    list.forEach(function (f) {
      var w = weeks[weeks.length - 1];
      if (w && w.week === f.week) w.items.push(f);
      else weeks.push({ week: f.week, items: [f] });
    });
    var cur = currentWeek(list);

    box.innerHTML = weeks.map(function (w) {
      var open = w.week === cur;
      var oynanan = w.items.filter(function (f) { return f.played; }).length;
      return '<section class="wk">' +
        '<button class="wk-h" aria-expanded="' + (open ? "true" : "false") + '">' +
          '<span class="wk-n">' + esc(w.week) + ". hafta</span>" +
          '<span class="wk-s">' + esc(oynanan) + "/" + esc(w.items.length) + " oynandı</span>" +
          '<span class="caret">' + (open ? "▴" : "▾") + "</span>" +
        "</button>" +
        '<div class="wk-b"' + (open ? "" : " hidden") + ">" +
          w.items.map(function (f) {
            var ours = isOurTeam(f.home) || isOurTeam(f.away);
            var d = matchDate(f);
            var hw = f.played && f.homeScore > f.awayScore;
            var aw = f.played && f.awayScore > f.homeScore;
            return '<div class="lm' + (ours ? " ours" : "") + '">' +
              '<div class="lm-d">' + (d ? esc(d.getDate() + " " + AYLAR[d.getMonth()]) : "–") +
                (f.time ? '<span>' + esc(f.time) + "</span>" : "") + "</div>" +
              "<div>" +
                '<div class="lm-t ' + (hw ? "won" : aw ? "lost" : "") + '">' +
                  teamCell(f.home, f.homeLogo) +
                  '<span class="lm-s">' + (f.played ? esc(f.homeScore) : "") + "</span></div>" +
                '<div class="lm-t ' + (aw ? "won" : hw ? "lost" : "") + '">' +
                  teamCell(f.away, f.awayLogo) +
                  '<span class="lm-s">' + (f.played ? esc(f.awayScore) : "") + "</span></div>" +
                (f.venue ? '<div class="lm-v">' + ico("pin") + "<span>" + esc(f.venue) + "</span></div>" : "") +
              "</div></div>";
          }).join("") +
        "</div></section>";
    }).join("");
  }

  // ------------------------------------------------------------- puan durumu
  function renderStandings() {
    el("standingsNotice").innerHTML = notice(state.league);
    var rows = (state.league && state.league.standings) || [];
    var slot = el("standingsSlot");
    if (state.league && state.league.group) {
      el("standingsTitle").textContent = state.league.group;
    }
    if (!rows.length) {
      slot.innerHTML = '<div class="tbdbox"><b>Veri yok</b>Puan durumu henüz çekilmedi.</div>';
      return;
    }
    function v(x) { return x == null ? "–" : esc(x); }

    // Yedi sutun 390 pikselde yan yana sigiyor: yatay kaydirma yok, logo yok.
    // (Onceki surumde tablo kayiyordu ve logolar kirik kutu olarak duruyordu.)
    slot.innerHTML =
      '<div class="stbl">' +
        '<div class="strow sthead"><span class="unit">#</span><span class="unit">Takım</span>' +
          '<span class="unit">O</span><span class="unit">G</span><span class="unit">M</span>' +
          '<span class="unit">AV</span><span class="unit">P</span></div>' +
        rows.map(function (r, i) {
          var ours = r.isOurs != null ? r.isOurs : isOurTeam(r.team);
          return '<div class="strow' + (ours ? " ours" : "") + '">' +
            '<span class="rk">' + (r.rank != null ? esc(r.rank) : i + 1) + "</span>" +
            '<span class="tm">' + esc(takimAdi(r.team)) + "</span>" +
            "<span>" + v(r.played) + "</span><span>" + v(r.won) + "</span><span>" + v(r.lost) + "</span>" +
            '<span class="av">' + (r.diff == null ? "–" : (r.diff > 0 ? "+" : "") + esc(r.diff)) + "</span>" +
            '<span class="pt">' + v(r.points) + "</span></div>";
        }).join("") +
      "</div>" +
      '<p class="key">O oynanan · G galibiyet · M mağlubiyet · AV averaj · P puan<br>' +
      "Fikstür, skor ve puan durumu TBF sayfalarından otomatik çekilir.</p>";
  }

  // ------------------------------------------------------- oyuncu istatistiği
  // Maç istatistikleri TBF'den boxscore olarak geliyor; burada oyuncu bazında
  // sezona toplanır. Rakip takımın satırları alınmaz.
  function seasonStats() {
    var out = {};
    ((state.league && state.league.fixtures) || []).forEach(function (f) {
      if (!f.boxscore || !f.played) return;
      var ourHome = isOurTeam(f.home);
      var rows = ourHome ? f.boxscore.home : f.boxscore.away;
      if (!rows || !rows.length) return;
      var opp = ourHome ? f.away : f.home;
      var bizim = ourHome ? f.homeScore : f.awayScore;
      var rakip = ourHome ? f.awayScore : f.homeScore;
      rows.forEach(function (r) {
        var key = norm(r.name);
        if (!key) return;
        var p = out[key] || (out[key] = {
          name: r.name, no: r.no, games: 0, points: 0, rebounds: 0, assists: 0,
          steals: 0, blocks: 0, turnovers: 0, fouls: 0, minutes: 0, starts: 0, log: []
        });
        p.games++;
        if (r.starter) p.starts++;
        ["points", "rebounds", "assists", "steals", "blocks", "turnovers", "fouls"].forEach(function (k) {
          p[k] += Number(r[k]) || 0;
        });
        p.minutes += mmss(r.min);
        if (r.no != null) p.no = r.no;
        p.log.push({
          date: f.date, opp: opp, week: f.week,
          win: bizim != null && rakip != null && bizim > rakip,
          score: (bizim == null ? "" : bizim + "-" + rakip),
          min: r.min, points: Number(r.points) || 0,
          rebounds: Number(r.rebounds) || 0, assists: Number(r.assists) || 0,
          plusMinus: r.plusMinus
        });
      });
    });
    return out;
  }

  function mmss(v) {
    var m = String(v || "").split(":");
    if (m.length < 2) return 0;
    return (Number(m[0]) || 0) + (Number(m[1]) || 0) / 60;
  }

  function avg(total, games) {
    if (!games) return "–";
    var x = total / games;
    return (Math.round(x * 10) / 10).toString().replace(".", ",");
  }

  // Tek sayıya indirgenmiş sezon özeti: grafiğe gerek yok, rakam daha okunur.
  function tile(label, value, sub) {
    return '<div class="tile"><div class="tv">' + esc(value) + "</div>" +
      '<div class="tl">' + esc(label) + "</div>" +
      (sub ? '<div class="ts2">' + esc(sub) + "</div>" : "") + "</div>";
  }

  // TBF iki ayrı kaydında aynı ismi farklı yazabiliyor ("Eda" / "Ela" gibi).
  // Birebir eşleşme yoksa bir-iki harflik farkı tolere ederiz; daha fazlasını
  // eşleştirmek yanlış oyuncuya istatistik yazma riski taşır.
  function editDistance(a, b) {
    if (Math.abs(a.length - b.length) > 2) return 99;
    var prev = [], cur = [], i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      cur[0] = i;
      for (j = 1; j <= b.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1,
          prev[j - 1] + (a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1));
      }
      prev = cur.slice();
    }
    return prev[b.length];
  }

  function matchStats(stats, name) {
    var key = norm(name);
    if (stats[key]) return key;
    var best = null, bestD = 3;
    Object.keys(stats).forEach(function (k) {
      var d = editDistance(key, k);
      if (d < bestD) { bestD = d; best = k; }
    });
    return best;
  }

  function openPlayer(key) {
    var stats = seasonStats()[key];
    var players = (state.team && state.team.players) || [];
    // Önce birebir, olmazsa bir-iki harflik yazım farkını tolere ederek eşleştir.
    var roster = players.filter(function (p) { return norm(p.name) === key; })[0] ||
      players.filter(function (p) { return editDistance(norm(p.name), key) <= 2; })[0];
    if (!stats && !roster) return;

    var name = (stats && stats.name) || roster.name;
    var no = (roster && roster.no != null) ? roster.no : (stats && stats.no);
    var meta = [];
    if (roster && roster.birthYear) meta.push(roster.birthYear + " doğumlu");
    if (roster && roster.height) meta.push(roster.height + " cm");

    var body = "";
    if (stats && stats.games) {
      // En yüksek sayı, satır içi çubukların ölçeği olur.
      var peak = Math.max.apply(null, stats.log.map(function (m) { return m.points; })) || 1;
      body =
        '<div class="tiles">' +
          tile("Sayı ort.", avg(stats.points, stats.games), stats.points + " toplam") +
          tile("Ribaund ort.", avg(stats.rebounds, stats.games), stats.rebounds + " toplam") +
          tile("Asist ort.", avg(stats.assists, stats.games), stats.assists + " toplam") +
          tile("Top çalma", avg(stats.steals, stats.games), stats.steals + " toplam") +
          tile("Süre ort.", avg(stats.minutes, stats.games) + "′", null) +
          tile("Maç", String(stats.games), stats.starts + " ilk beş") +
        "</div>" +
        '<h3 class="eyebrow">Maç maç</h3>' +
        '<div class="scroll"><table class="box mlog"><thead><tr>' +
          "<th>Maç</th><th>Rakip</th><th>DK</th><th>SAY</th><th>RİB</th><th>AST</th>" +
        "</tr></thead><tbody>" +
        stats.log.map(function (m) {
          var w = Math.max(4, Math.round((m.points / peak) * 100));
          return "<tr>" +
            '<td class="mw">' + esc(m.week != null ? m.week + ". h" : "") + "</td>" +
            '<td class="mo"><span class="' + (m.win ? "w" : "l") + '"></span>' + esc(m.opp) + "</td>" +
            "<td>" + esc((m.min || "").slice(0, 5)) + "</td>" +
            '<td class="pts barcell"><span class="bar" style="width:' + w + '%"></span>' +
              "<b>" + esc(m.points) + "</b></td>" +
            "<td>" + esc(m.rebounds) + "</td><td>" + esc(m.assists) + "</td></tr>";
        }).join("") +
        "</tbody></table></div>";
    } else {
      body = '<div class="blank">Bu oyuncu için henüz maç istatistiği yok. ' +
        "TBF maç raporunu yayımladığında burada görünecek.</div>";
    }

    var ov = el("playerSheet");
    ov.innerHTML =
      '<div class="psheet" role="dialog" aria-modal="true" aria-label="' + esc(name) + '">' +
        '<header class="ph">' +
          '<div class="pno">' + esc(no != null ? no : "–") + "</div>" +
          "<div><h2>" + esc(name) + "</h2>" +
          (meta.length ? '<div class="pmeta">' + esc(meta.join(" · ")) + "</div>" : "") + "</div>" +
          '<button class="pclose" aria-label="Kapat">✕</button>' +
        "</header>" +
        '<div class="pbody">' + body + "</div>" +
      "</div>";
    ov.hidden = false;
    document.body.classList.add("locked");
    devamGoster(roster, name);
  }

  /** Antrenman devamı kişisel veridir: yalnız antrenör şifresiyle girilmişse
   *  gösterilir (uygulama herkese açık). Şifre yoksa istek bile atılmaz. */
  function kocSifresi() {
    try { return sessionStorage.getItem("evolog_admin_pass") || ""; } catch (e) { return ""; }
  }

  function devamGoster(roster, name) {
    var sifre = kocSifresi();
    if (!sifre) return;
    var anahtar = roster && roster.tbfPlayerId ? String(roster.tbfPlayerId) : norm(name || "");
    fetch("/api/attendance/summary?age=" + age + "&limit=20", {
      headers: { Authorization: "Bearer " + sifre }
    }).then(function (r) { return r.ok ? r.json() : null; }).then(function (ozet) {
      if (!ozet) return;
      var satir = (ozet.players || []).filter(function (x) { return String(x.key) === anahtar; })[0];
      if (!satir || satir.oran === null) return;
      var ov = el("playerSheet");
      var body = ov && ov.querySelector(".pbody");
      if (!body) return;
      var kutu = document.createElement("div");
      kutu.className = "kocnot";
      kutu.innerHTML = "<b>Antrenman devamı %" + satir.oran + "</b> · " +
        (satir.geldi + satir.gec) + " katılım, " + satir.gelmedi + " gelmedi" +
        (satir.izinli ? ", " + satir.izinli + " izinli" : "") +
        "<span>Son " + (ozet.sessions || []).length + " antrenman · yalnız antrenör görür</span>";
      body.insertBefore(kutu, body.firstChild);
    }).catch(function () { /* şifre eskimiş olabilir; sessizce geç */ });
  }

  function closePlayer() {
    var ov = el("playerSheet");
    if (!ov || ov.hidden) return;
    ov.hidden = true;
    ov.innerHTML = "";
    document.body.classList.remove("locked");
  }

  // ------------------------------------------------------------- kadro
  function renderRoster() {
    var t = state.team, slot = el("rosterSlot");
    if (!t || !(t.players || []).length) {
      slot.innerHTML = '<div class="blank">Kadro bilgisi bulunamadı.</div>';
      el("staffSlot").innerHTML = "";
      return;
    }
    var stats = seasonStats();
    var used = {};

    // Lisans listesi ile maç kadrosu tek listede birleşir ve forma numarasına
    // göre sıralanır. Veli oyuncuyu ararken hangi TBF listesinde olduğunu
    // bilmek zorunda değil; 0 da geçerli bir numara, en başta durur.
    var rows = t.players.map(function (p) {
      var key = matchStats(stats, p.name) || norm(p.name);
      var st = stats[key];
      if (st) used[key] = true;
      return {
        key: key, name: p.name, st: st,
        // Lisans listesinde numara boş olabiliyor; maç raporundaki numarayı kullan.
        no: p.no != null ? p.no : (st ? st.no : null),
        meta: [p.position, p.height ? p.height + " cm" : null].filter(Boolean).join(" · "),
        birthYear: p.birthYear
      };
    });

    // Maç kadrosunda oynayıp lisans listesinde görünmeyenler (üst yaş takviyesi
    // ya da TBF listesi henüz güncellenmemiş olabilir) kaybolmasın.
    //
    // ADI ALTINA ETİKET YAZILMIYOR. Önceden burada `meta: "maç kadrosu"` vardı;
    // veli çocuğunun adının altında anlam veremediği bir ibare görüyordu —
    // çünkü o ibare oyuncuyla ilgili değil, TBF'nin lisans listesiyle kutu skoru
    // arasındaki bir tutarsızlıkla ilgiliydi. Kim maçta sahaya çıktı bilgisi
    // artık ait olduğu yerde duruyor: her maçın kutu skorunda, yıldızla.
    Object.keys(stats).forEach(function (k) {
      if (used[k]) return;
      rows.push({ key: k, name: stats[k].name, st: stats[k], no: stats[k].no,
                  meta: null, birthYear: null });
    });

    // Üç kademe: (1) forma numarası olanlar, küçükten büyüğe — 0 dahil.
    // (2) numarası görünmeyen ama maçta oynamış olanlar, numaralı kadronun
    // hemen ardında. (3) bu sezon henüz oynamamış lisanslı oyuncular.
    function tier(r) {
      if (r.no != null && r.no !== "") return 0;
      return (r.st && r.st.games) ? 1 : 2;
    }
    rows.sort(function (a, b) {
      return (tier(a) - tier(b)) ||
        (jersey(a.no) - jersey(b.no)) ||
        ((b.st && b.st.points || 0) - (a.st && a.st.points || 0)) ||
        a.name.localeCompare(b.name, "tr");
    });

    // Tasarim iki bolum istiyor: sahaya cikan kadro ustte, henuz oynamamis
    // lisansli oyuncular altta. Veli once cocugunun oynadigi listeyi ariyor.
    function satir(r) {
      var oynadi = r.st && r.st.games;
      var sag = oynadi
        ? '<div class="yr avgpts"><b>' + esc(avg(r.st.points, r.st.games)) + "</b>" +
          '<span class="unit">sayı ort.</span></div>'
        : '<div class="yr unit">' + esc(r.birthYear || "") + "</div>";
      return '<button class="pl' + (oynadi ? " has" : "") + '" data-player="' + esc(r.key) + '">' +
        '<div class="no">' + esc(r.no != null ? r.no : "—") + "</div>" +
        '<div><div class="nm">' + esc(r.name) + "</div>" +
        (r.meta ? '<div class="meta">' + esc(r.meta) + "</div>" : "") + "</div>" +
        sag + "</button>";
    }
    var oynayan = rows.filter(function (r) { return r.st && r.st.games; });
    var digerleri = rows.filter(function (r) { return !(r.st && r.st.games); });
    slot.innerHTML =
      (oynayan.length
        ? '<div class="sec"><span class="label">Maç kadrosu</span><i class="hair"></i>' +
          '<span class="cnt">' + oynayan.length + " oyuncu</span></div>" +
          oynayan.map(satir).join("")
        : "") +
      (digerleri.length
        ? '<div class="sec"><span class="label">Lisanslı · maç oynamadı</span><i class="hair"></i>' +
          '<span class="cnt">' + digerleri.length + " oyuncu</span></div>" +
          digerleri.map(satir).join("")
        : "");

    el("staffSlot").innerHTML = (t.staff || []).map(function (s) {
      return '<div class="ss"><div><div class="role">' + esc(s.role) + "</div>" +
        '<div class="nm">' + esc(s.name) + "</div></div>" +
        (s.phone ? '<a href="tel:' + esc(s.phone) + '">Ara</a>' : "<span></span>") + "</div>";
    }).join("") || '<div class="blank">Teknik kadro bilgisi girilmemiş.</div>';
  }

  // ------------------------------------------------------------- antrenman
  function venueOf(id) {
    return ((state.training && state.training.venues) || [])
      .filter(function (v) { return v.id === id; })[0] || null;
  }

  /* Salon rehberi (data/venues.json): antrenörün yazdığı kısa ad ya da
     TBF'den gelen salon adı burada eşleşirse tam ad ve konum gösterilir.
     Böylece "TEV" yerine okulun tam adı, maçlarda da salonun gerçek adı
     çıkar - veri kaynağını değiştirmeden. */
  function salonBul(ad) {
    if (!ad) return null;
    var n = norm(ad);
    var liste = (state.venues && state.venues.venues) || [];
    for (var i = 0; i < liste.length; i++) {
      var kalip = liste[i].match || [];
      for (var j = 0; j < kalip.length; j++) {
        if (kalip[j] && n.indexOf(norm(kalip[j])) !== -1) return liste[i];
      }
    }
    return null;
  }

  /** Salonu tam adıyla ve varsa kort bilgisiyle yazar. */
  function salonAdi(ad) {
    var v = salonBul(ad);
    if (!v) return ad || "";
    var kort = "";
    if (v.courts) {
      var n = norm(ad);
      Object.keys(v.courts).forEach(function (k) {
        if (n.indexOf("(" + k + ")") !== -1 || n.indexOf(" " + k) !== -1) kort = v.courts[k];
      });
    }
    return v.name + (kort ? " · " + kort : "");
  }

  function salonLink(ad) {
    var v = salonBul(ad);
    return v && v.maps ? v.maps : null;
  }

  /** Bugünün içinde bulunduğu haftanın pazartesisi. */
  function thisMonday() {
    var n = new Date();
    var d = new Date(n.getFullYear(), n.getMonth(), n.getDate());
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    return d;
  }

  /** Program hangi hafta için girildi? (weekStart = o haftanın pazartesisi) */
  function programWeek(tr) {
    var parts = String((tr && tr.weekStart) || "").split("-");
    if (parts.length !== 3) return null;
    var d = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    return isNaN(d.getTime()) ? null : d;
  }

  /** Program hangi haftaya ait: "past" | "current" | "future" | null */
  function programWeekKind(tr) {
    var w = programWeek(tr);
    if (!w) return null;
    var fark = w.getTime() - thisMonday().getTime();
    if (fark === 0) return "current";
    return fark < 0 ? "past" : "future";
  }

  /** Program geçen haftaya mı ait? Öyleyse veliye kesinmiş gibi gösterilmez. */
  function programStale(tr) {
    return programWeekKind(tr) === "past";
  }

  /** Program haftasındaki günün tarihi (1=Pazartesi … 7=Pazar). */
  function haftaGunu(week, gun) {
    return week ? new Date(week.getFullYear(), week.getMonth(),
                           week.getDate() + (gun - 1)) : null;
  }

  /** Program haftasına düşen, tarihi kesinleşmiş kendi maçlarımız. */
  function haftaninMaclari(week) {
    if (!week) return {};
    var ilk = isoDay(week);
    var son = isoDay(haftaGunu(week, 7));
    var out = {};
    ((state.league && state.league.fixtures) || []).forEach(function (f) {
      if (!f.date || !f.isOurs || f.dateConfirmed === false) return;
      if (f.date < ilk || f.date > son) return;
      var d = new Date(f.date + "T00:00:00");
      var gun = ((d.getDay() + 6) % 7) + 1;
      (out[gun] = out[gun] || []).push(f);
    });
    return out;
  }

  /** 1=Pazartesi … 7=Pazar için bir sonraki tarih. */
  function nextOccurrence(day, start) {
    var now = new Date();
    var d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    d.setDate(d.getDate() + ((day % 7) - d.getDay() + 7) % 7);
    var hm = (start || "00:00").split(":").map(Number);
    d.setHours(hm[0] || 0, hm[1] || 0, 0, 0);
    if (d.getTime() < now.getTime()) d.setDate(d.getDate() + 7);
    return d;
  }

  function renderTraining() {
    var tr = state.training;
    var slot = el("sessionsSlot");
    var week = programWeek(tr);
    var stale = programStale(tr);
    var bugun = new Date();
    var bugunIso = isoDay(bugun);

    // Hafta seridi: antrenman olan gunler amber dolu, bugun cerceveli.
    var KISA = ["PZT", "SAL", "ÇAR", "PER", "CUM", "CMT", "PAZ"];
    var dolu = {};
    ((tr && tr.sessions) || []).forEach(function (x) { dolu[x.day] = true; });
    var bugunIdx = ((bugun.getDay() + 6) % 7) + 1;
    el("weekStrip").innerHTML = KISA.map(function (ad, i) {
      var g = i + 1;
      return '<div class="' + (dolu[g] && !programStale(tr) ? "on" : "") +
        (g === bugunIdx ? " today" : "") + '">' + ad + "</div>";
    }).join("");

    if (!tr || !(tr.sessions || []).length) {
      el("weekTitle").innerHTML = '<span class="label">Bu hafta</span><i class="hair"></i>';
      slot.innerHTML = '<div class="tbdbox"><b>Program yok</b>' +
        "Antrenman programı henüz girilmedi. Antrenör girdiğinde burada görünecek " +
        "ve size bildirim göndereceğiz.</div>";
      el("nextTrainingSlot").innerHTML = "";
      el("venuesSlot").innerHTML = "";
      return;
    }

    var sorted = tr.sessions.slice().sort(function (a, b) {
      return (a.day - b.day) || String(a.start).localeCompare(String(b.start));
    });

    function gunTarihi(gun) {
      if (!week) return null;
      return new Date(week.getFullYear(), week.getMonth(), week.getDate() + (gun - 1));
    }

    var kind = programWeekKind(tr);
    var baslik = kind === "past" ? "Geçen haftanın programı"
               : kind === "future" ? "Gelecek haftanın programı"
               : "Bu hafta";

    el("weekTitle").innerHTML = '<span class="label">' + esc(baslik) +
      "</span><i class=\"hair\"></i>" +
      (week ? '<span class="cnt">' + esc(haftaAraligi(week)) + "</span>" : "");

    // Gunlere gore topla: antrenman, izin, mac.
    var seansGun = {};
    sorted.forEach(function (x) { (seansGun[x.day] = seansGun[x.day] || []).push(x); });
    var izin = {};
    ((tr.offDays) || []).forEach(function (d) { izin[Number(d)] = true; });
    var maclar = haftaninMaclari(week);

    // Haftanin yedi gunu de yazilir: veli "o gun bos mu, izin mi, mac mi"
    // diye tahmin etmek zorunda kalmasin.
    // Antrenmani ve maci olmayan gun izin gunudur: antrenorun ayrica
    // isaretlemesine gerek yok, "program yok" diye bos birakilmaz.
    var satirlar = [];
    for (var gun = 1; gun <= 7; gun++) {
      var seanslar = seansGun[gun] || [];
      var gunMaclari = maclar[gun] || [];
      satirlar.push({
        gun: gun,
        d: haftaGunu(week, gun),
        seanslar: seanslar,
        maclar: gunMaclari,
        off: !seanslar.length && !gunMaclari.length
      });
    }

    slot.innerHTML = satirlar.map(function (r) {
      var bugunMu = r.d && isoDay(r.d) === bugunIso && kind === "current";
      var sinif = "tr" + (bugunMu ? " today" : "") +
                  (r.off ? " off" : "") +
                  (r.maclar && r.maclar.length ? " mac" : "");
      var gunAdi = esc(GUNLER[(r.gun % 7)]) +
        (r.d ? " · " + r.d.getDate() + " " + esc(AYLAR[r.d.getMonth()]) : "");

      var saat = r.off ? "İZİN"
               : (r.seanslar.length ? esc(r.seanslar[0].start)
                  : esc((r.maclar[0] || {}).time || ""));

      var alt;
      if (r.off) {
        alt = '<span class="dim">Antrenman yok</span>';
      } else {
        alt = r.seanslar.map(function (x) {
          var v = venueOf(x.venue);
          var ad = v ? salonAdi(v.name) : "";
          return "<b>" + esc(x.title || "Antrenman") + "</b> \u00b7 " + esc(x.start) +
            (x.end ? "\u2013" + esc(x.end) : "") + (ad ? " \u00b7 " + esc(ad) : "");
        }).join("<br>");
      }
      // Mac gunu programda da gorunur; antrenmanla ayni gune de dusebilir.
      if (r.maclar && r.maclar.length) {
        alt += (alt ? "<br>" : "") + r.maclar.map(function (f) {
          var rakip = isOurTeam(f.home) ? f.away : f.home;
          var nerede = isOurTeam(f.home) ? "ev sahibi" : "deplasman";
          return '<b class="macet">MAÇ</b> · ' + esc(f.time || "") + " · " +
            esc(rakip) + " <span class=\"dim\">(" + nerede + ")</span>" +
            (f.venue ? ' <span class="dim">· ' + esc(salonAdi(f.venue)) + "</span>" : "");
        }).join("<br>");
      }

      return '<article class="' + sinif + '">' +
        '<div class="day">' + gunAdi + "</div>" +
        '<div class="hh">' + saat + "</div>" +
        '<div class="sub">' + alt + "</div>" +
      "</article>";
    }).join("");

    // Gelecek hafta: program girilmediyse kesikli kutu — bos ekran birakilmaz.
    var sonraki = week ? new Date(week.getFullYear(), week.getMonth(), week.getDate() + 7) : null;
    // Gelecek haftanin programi geldiyse gosterilecek program odur; biten
    // hafta icin "henuz aciklanmadi" uyarisi asmak bilgi degil gurultu.
    // Uyari yalnizca elimizdeki program GECMIS haftaya aitse anlamli.
    el("nextTrainingSlot").innerHTML = (kind === "past" || !week)
      ? '<div class="sec"><span class="label">Bu hafta</span><i class="hair"></i>' +
        '<span class="cnt">' + esc(haftaAraligi(thisMonday())) + "</span></div>" +
        '<div class="tbdbox"><b>Henüz açıklanmadı</b>' +
        "Bu haftanın antrenman programı antrenörden gelmedi. Geldiğinde burada " +
        "görünecek ve size bildirim göndereceğiz.</div>"
      : kind === "current"
      ? '<div class="sec"><span class="label">Gelecek hafta</span><i class="hair"></i>' +
        '<span class="cnt">' + esc(haftaAraligi(new Date(week.getFullYear(),
            week.getMonth(), week.getDate() + 7))) + "</span></div>" +
        '<div class="tbdbox"><b>Henüz açıklanmadı</b>' +
        "Gelecek haftanın programı henüz açıklanmadı.</div>"
      : "";

    var exc = (tr.exceptions || []).filter(function (e) {
      return new Date(e.date + "T23:59:59") >= new Date();
    });
    el("venuesSlot").innerHTML =
      '<div class="venuelist">' + salonlariTopla(tr).map(function (v) {
        return "<div><span>" + esc(v.name) +
          (v.alt ? ' <span class="unit">' + esc(v.alt) + "</span>" : "") + "</span>" +
          (v.maps ? '<a href="' + esc(v.maps) + '" target="_blank" rel="noopener">Yol tarifi</a>' : "") +
          "</div>";
      }).join("") + "</div>" +
      (exc.length
        ? '<div class="sec"><span class="label">Program değişiklikleri</span><i class="hair"></i></div>' +
          exc.map(function (e) {
            return '<div class="tbdbox"><b>' + esc(e.date) + "</b>" + esc(e.type || "") +
              (e.reason ? " — " + esc(e.reason) : "") + "</div>";
          }).join("")
        : "");
  }

    /** Salonlar bolumu: antrenman salonlari + o haftanin mac salonlari,
      hepsi rehberdeki tam adi ve konumuyla, yinelenmeden. */
  function salonlariTopla(tr) {
    var out = [], gorulen = {};
    function ekle(hamAd, etiket) {
      if (!hamAd) return;
      var ad = salonAdi(hamAd);
      var anahtar = norm(ad);
      if (gorulen[anahtar]) return;
      gorulen[anahtar] = true;
      var v = salonBul(hamAd);
      out.push({
        name: ad,
        alt: etiket,
        maps: (v && v.maps) ||
              ("https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(hamAd))
      });
    }
    ((tr && tr.venues) || []).forEach(function (v) { ekle(v.name, "antrenman"); });
    var maclar = haftaninMaclari(programWeek(tr));
    Object.keys(maclar).forEach(function (g) {
      maclar[g].forEach(function (f) { ekle(f.venue, "maç"); });
    });
    return out;
  }

/** "14 – 20 Eylül" */
  function haftaAraligi(pazartesi) {
    if (!pazartesi) return "";
    var son = new Date(pazartesi.getFullYear(), pazartesi.getMonth(), pazartesi.getDate() + 6);
    var ay = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
              "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
    return pazartesi.getMonth() === son.getMonth()
      ? pazartesi.getDate() + " – " + son.getDate() + " " + ay[son.getMonth()]
      : pazartesi.getDate() + " " + ay[pazartesi.getMonth()] + " – " +
        son.getDate() + " " + ay[son.getMonth()];
  }

  function isoDay(d) {
    return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" +
      ("0" + d.getDate()).slice(-2);
  }

  // -------------------------------------------------------------- bildirim
  // PWA kapalıyken veri kendiliğinden güncellenemez (tarayıcılar izin vermiyor);
  // maç öncesi ve sonrası haber vermenin tek güvenilir yolu push bildirimi.
  var push = { sub: null, busy: false };

  function pushSupported() {
    return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  }

  function standalone() {
    return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  }

  function isIOS() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  }

  function urlB64ToUint8(base64) {
    var pad = "=".repeat((4 - (base64.length % 4)) % 4);
    var raw = atob((base64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  function pushAges() {
    var raw = store(PUSH_STORE), list = [];
    try { list = raw ? JSON.parse(raw) : []; } catch (e) { list = []; }
    return list.filter(knownAge);
  }

  function setPushAges(list) { store(PUSH_STORE, JSON.stringify(list)); }

  // iOS'ta bildirim yalnizca ana ekrana eklenmis uygulamada calisir; bu uyari
  // ana ekranda bir kez gorunur ve kapatilinca bir daha cikmaz.
  function renderIosHint() {
    var slot = el("iosHint");
    if (!slot) return;
    if (INLINE || !pushSupported() || !isIOS() || standalone() || store(IOS_STORE) === "off") {
      slot.innerHTML = "";
      return;
    }
    slot.innerHTML = '<div class="note"><div><b>Maç bildirimleri için</b> Paylaş → ' +
      "\u201CAna Ekrana Ekle\u201D deyip uygulamayı oradan açın. iPhone'da bildirimler " +
      "yalnızca böyle çalışıyor.</div>" +
      '<button class="hintx" id="iosHintClose" aria-label="Uyarıyı kapat">✕</button></div>';
  }

  function ensureSubscription() {
    if (push.sub) return Promise.resolve(push.sub);
    return Notification.requestPermission().then(function (perm) {
      if (perm !== "granted") return null;
      return fetch("/api/push/key").then(function (r) { return r.json(); })
        .then(function (k) {
          if (!k.publicKey) throw new Error("Sunucu anahtarı yok");
          return navigator.serviceWorker.ready.then(function (reg) {
            return reg.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: urlB64ToUint8(k.publicKey)
            });
          });
        })
        .then(function (sub) { push.sub = sub; return sub; });
    });
  }

  function dropSubscription() {
    var sub = push.sub;
    if (!sub) return Promise.resolve();
    var endpoint = sub.endpoint;
    push.sub = null;
    return sub.unsubscribe().catch(function () {}).then(function () {
      return fetch("/api/push/unsubscribe", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: endpoint })
      }).catch(function () {});
    });
  }

  function sendAges(list) {
    var j = push.sub.toJSON ? push.sub.toJSON() : push.sub;
    return fetch("/api/push/subscribe", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint: j.endpoint, keys: j.keys, ages: list })
    });
  }

  // Bir yas grubunun bildirimini ac/kapat. Hepsi kapaninca abonelik silinir.
  function togglePushAge(key, want) {
    if (push.busy || !knownAge(key)) return;
    var list = pushAges().slice();
    var at = list.indexOf(key);
    if (want && at === -1) list.push(key);
    if (!want && at !== -1) list.splice(at, 1);

    push.busy = true;
    renderSheet();
    var done = function () { push.busy = false; renderSheet(); };

    if (!list.length) {
      dropSubscription().then(function () { setPushAges([]); }).then(done, done);
      return;
    }

    ensureSubscription().then(function (sub) {
      if (!sub) return null;                 // izin verilmedi
      setPushAges(list);
      return sendAges(list);
    }).catch(function () {
      toast("Bildirim ayarlanamadı, sonra tekrar deneyin");
    }).then(done, done);
  }

  function initPush() {
    if (!pushSupported() || INLINE) return;
    navigator.serviceWorker.ready.then(function (reg) {
      return reg.pushManager.getSubscription();
    }).then(function (sub) {
      push.sub = sub;
      // Bu guncellemeden onceki abonelikler sunucuda ilk yas grubuna kayitli.
      if (sub && !pushAges().length) setPushAges([AGES[0].key]);
      if (!sub && pushAges().length) setPushAges([]);
      renderSheet();
    }).catch(function () { renderSheet(); });
  }

  // ------------------------------------------------------- takim / ayarlar
  function pushSection() {
    if (!pushSupported()) {
      return '<p class="shint">Bu tarayıcı maç bildirimlerini desteklemiyor.</p>';
    }
    if (isIOS() && !standalone()) {
      return '<p class="shint">iPhone\u2019da bildirim için uygulamayı Paylaş → ' +
        "\u201CAna Ekrana Ekle\u201D ile kurup oradan açın.</p>";
    }
    if (Notification.permission === "denied") {
      return '<p class="shint">Bildirimler engellenmiş. Tarayıcı ayarlarından bu ' +
        "siteye izin verirseniz maç hatırlatması ve skoru gönderebiliriz.</p>";
    }
    var on = pushAges();
    return AGES.map(function (a) {
      var isOn = on.indexOf(a.key) !== -1;
      return '<button type="button" class="srow tgl' + (isOn ? " on" : "") + '"' +
        (push.busy ? " disabled" : "") +
        ' data-push="' + a.key + '" data-want="' + (isOn ? "0" : "1") + '"' +
        ' role="switch" aria-checked="' + (isOn ? "true" : "false") + '">' +
        "<span>Telefona bildirim" +
        (AGES.length > 1 ? " · " + esc(a.label) : "") +
        '<span class="sdesc">' + (push.busy ? "Değiştiriliyor…" : (isOn ? "Açık" : "Kapalı")) +
        "</span></span>" +
        '<span class="sw" aria-hidden="true"></span></button>';
    }).join("") +
      '<p class="shint">Maç günü/saati değişince, maçtan 4 saat önce, maç bitince skor ' +
      "ve antrenman programı değişince haber veririz.</p>";
  }

  function renderSheet() {
    var ov = el("ageSheet");
    if (!ov || ov.hidden) return;
    var lg = state.league || {};
    var stamp = "";
    if (lg.updatedAt) {
      var d = new Date(lg.updatedAt);
      stamp = d.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit" }) + " " +
        d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
    }
    ov.innerHTML =
      '<div class="psheet" role="dialog" aria-modal="true" aria-label="Takım ve ayarlar">' +
        '<header class="ph sh">' +
          "<div><h2>Ayarlar</h2></div>" +
          '<button class="pclose" aria-label="Kapat">✕</button>' +
        "</header>" +
        '<div class="pbody">' +
          (AGES.length > 1
            ? '<div class="slist">' +
                AGES.map(function (a) {
                  var on = a.key === age;
                  return '<button type="button" class="srow pick' + (on ? " on" : "") + '"' +
                    ' data-age="' + a.key + '" aria-current="' + (on ? "true" : "false") + '">' +
                    "<span>" + esc(a.title) + "</span>" +
                    '<span class="tick" aria-hidden="true">' + (on ? "✓" : "") + "</span></button>";
                }).join("") +
              "</div>"
            : "") +
          '<h3 class="eyebrow">Bildirimler</h3>' +
          '<div class="slist">' + pushSection() + "</div>" +
          '<h3 class="eyebrow">Uygulama</h3>' +
          '<div class="slist">' +
            '<div class="srow flat"><span>Takım<span class="sdesc">' +
              esc(ageInfo().title) + " · " + esc((state.league || {}).season || "2026-2027") +
              "</span></span></div>" +
            '<div class="srow flat"><span>Veri güncelliği<span class="sdesc">' +
              esc(stamp ? stamp + " · TBF'den otomatik" : "—") + "</span></span></div>" +
            '<button type="button" class="srow link" data-coach="yoklama">' +
              '<span>Antrenör paneli<span class="sdesc">Yoklama · program · oyuncu analizi' +
              "</span></span>" +
              '<span class="gir">Giriş</span></button>' +
            gorunumSatiri() +
          "</div>" +
        "</div>" +
      "</div>";
  }

  /* Gorunum gecisi. 21 Eylul 2026'da yeni tasarim ana uygulamaya alindi;
     eskisi /klasik/ altinda duruyor, gerekirse geri donulebilsin diye.
     Adres calisma aninda hesaplanir: bu dosya demo/ ve klasik/ altina da
     uretiliyor, sabit "klasik/" yazilsaydi klasik surum kendine link verirdi. */
  function gorunumSatiri() {
    var taban = window.EVOLOG_ASSET_BASE || "";
    var klasikte = location.pathname.indexOf("/klasik/") !== -1;
    var adres = klasikte ? (taban || "./") : taban + "klasik/";
    var ad = klasikte ? "Yeni görünüm" : "Klasik görünüm";
    var alt = klasikte ? "Guncel tasarima dön" : "Önceki tasarımı aç";
    return '<a class="srow link" href="' + esc(adres) + '">' +
             "<span>" + ad + '<span class="sdesc">' + alt + "</span></span>" +
             '<span class="dim">›</span></a>';
  }

  function openSheet() {
    var ov = el("ageSheet");
    if (!ov) return;
    ov.hidden = false;
    document.body.classList.add("locked");
    var tab = el("tab-takim");
    if (tab) tab.setAttribute("aria-expanded", "true");
    renderSheet();
  }

  function closeSheet() {
    var ov = el("ageSheet");
    if (!ov || ov.hidden) return;
    ov.hidden = true;
    ov.innerHTML = "";
    document.body.classList.remove("locked");
    var tab = el("tab-takim");
    if (tab) tab.setAttribute("aria-expanded", "false");
  }

  // ------------------------------------------------------- antrenor paneli
  // Panel icerigi ayri sayfalarda durur (tek kaynak, iki kopya bakim demek);
  // uygulama onlari tam ekran bir cerceve icinde acar. Sifre kontrolu o
  // sayfanin kendi giris kutusunda ve sunucuda yapilir.
  var COACH_TABS = [
    { key: "yoklama", label: "Yoklama", title: "Yoklama", src: "yoklama.html?gomulu=1" },
    { key: "antrenman", label: "Program", title: "Antrenman programı", src: "yonetim.html?gomulu=1" },
    { key: "oyuncular", label: "Oyuncular", title: "Oyuncu analizi", src: "oyuncular.html?gomulu=1" },
    { key: "mac", label: "Maç", title: "Maç analizi", src: "macanaliz.html?gomulu=1" },
    { key: "rakip", label: "Rakip", title: "Rakip analizi", src: "rakip.html?gomulu=1" },
    { key: "duyuru", label: "Duyuru", title: "Duyuru", src: "duyuru.html?gomulu=1" }
  ];

  function coachTab(key) {
    for (var i = 0; i < COACH_TABS.length; i++) if (COACH_TABS[i].key === key) return COACH_TABS[i];
    return COACH_TABS[0];
  }

  function openCoach(key) {
    var panel = el("coachPanel");
    if (!panel) return;
    var tab = coachTab(key);
    el("coachTitle").textContent = COACH_TABS.length > 1 ? "Antrenör paneli" : tab.title;
    var tabs = el("coachTabs");
    tabs.innerHTML = COACH_TABS.length < 2 ? "" :
      COACH_TABS.map(function (c) {
        return '<button type="button" data-ctab="' + c.key + '" aria-pressed="' +
          (c.key === tab.key ? "true" : "false") + '">' + esc(c.label) + "</button>";
      }).join("");
    var frame = el("coachFrame");
    if (frame.dataset.tab !== tab.key) {
      frame.dataset.tab = tab.key;
      frame.src = tab.src;
    }
    panel.hidden = false;
    document.body.classList.add("locked");
    closeSheet();
  }

  function closeCoach() {
    var panel = el("coachPanel");
    if (!panel || panel.hidden) return;
    panel.hidden = true;
    var frame = el("coachFrame");
    frame.src = "about:blank";
    frame.dataset.tab = "";
    document.body.classList.remove("locked");
    // Antrenor programi degistirmis olabilir; veriyi tazele.
    refresh();
  }

  // ------------------------------------------------------------- sekmeler
  function showPanel(name) {
    PANELS.forEach(function (p) {
      var panel = el("panel-" + p), tab = el("tab-" + p);
      if (!panel || !tab) return;
      panel.hidden = p !== name;
      tab.setAttribute("aria-selected", p === name ? "true" : "false");
    });
    window.scrollTo(0, 0);
  }

  /* --------------------------------------------------------------- duyurular */
  /* Iki kaynak birlestirilir:
       SUNUCU  /api/duyuru  - antrenorun yazdigi duyurular, TAM metin, her
                              cihazda ayni. Bildirimi kaciran veli de gorur.
       YEREL   IndexedDB    - telefona GELEN her push (mac sonucu, saat
                              degisikligi, antrenman programi...). Bunlarin
                              sunucuda kaydi yok; bildirim kapatilinca
                              metin tamamen kayboluyordu.
     Ayni duyurunun iki kopyasi (sunucudaki tam metin + push'taki kisa ozet)
     `etiket` uzerinden eslesir ve TEK kart gosterilir; sunucudaki kazanir.
     Silme VELIYE OZELDIR: antrenorun duyurusunu kimse baskasi icin silemez,
     silinen id telefonda mezar tasi olarak tutulur. */
  var sunucuDuyurular = [];
  var yerelDuyurular = [];
  var sonSilinen = null;          // "Geri al" icin son silinen kayit

  function duyuruId(d) {
    return String(d && (d.id != null ? d.id : d.zaman) || "");
  }

  function depoListesi(anahtar) {
    try { return JSON.parse(store(anahtar) || "[]") || []; }
    catch (e) { return []; }
  }

  function okunanlar() { return depoListesi(DUYURU_STORE); }
  function silinenler() { return depoListesi(DUYURU_SIL_STORE); }

  function okunduMu(d) { return okunanlar().indexOf(duyuruId(d)) !== -1; }

  /** Gorulen tum duyurulari okundu isaretler; liste son 50 ile sinirli tutulur. */
  function okunduIsaretle() {
    var l = okunanlar();
    duyurular().forEach(function (d) {
      var k = duyuruId(d);
      if (k && l.indexOf(k) === -1) l.push(k);
    });
    store(DUYURU_STORE, JSON.stringify(l.slice(-50)));
    renderDuyuru();
  }

  /** Iki kaynagi birlestirir, silinenleri duser, yeniden eskiye sirali doner. */
  function duyurular() {
    var olu = silinenler();
    var sunucuEtiket = {};
    sunucuDuyurular.forEach(function (d) { if (d.etiket) sunucuEtiket[d.etiket] = true; });

    var hepsi = sunucuDuyurular.slice();
    yerelDuyurular.forEach(function (y) {
      // Sunucuda tam metni varsa push kopyasini atla.
      if (y.etiket && sunucuEtiket[y.etiket]) return;
      hepsi.push(y);
    });

    return hepsi.filter(function (d) {
      if (olu.indexOf(duyuruId(d)) !== -1) return false;
      return !(d.etiket && olu.indexOf("e:" + d.etiket) !== -1);
    }).sort(function (a, b) {
      return String(b.zaman || "").localeCompare(String(a.zaman || ""));
    });
  }

  function okunmamisSayisi() {
    return duyurular().filter(function (d) { return !okunduMu(d); }).length;
  }

  /** Veli kendi telefonundan siler. Sunucudaki kayda dokunmaz. */
  function duyuruSil(id) {
    var hedef = null;
    duyurular().forEach(function (d) { if (duyuruId(d) === id) hedef = d; });
    if (!hedef) return;

    var olu = silinenler();
    if (olu.indexOf(id) === -1) olu.push(id);
    // Etiketi de goml: ayni duyurunun push kopyasi geride kalmasin.
    if (hedef.etiket && olu.indexOf("e:" + hedef.etiket) === -1) olu.push("e:" + hedef.etiket);
    store(DUYURU_SIL_STORE, JSON.stringify(olu.slice(-200)));

    // Yerel arsivden gercekten sil: mezar tasi listesi sinirli, kayit degil.
    if (window.EvologArsiv && hedef.etiket) {
      window.EvologArsiv.etiketiSil(hedef.etiket)["catch"](function () { /* onemsiz */ });
    }
    sonSilinen = hedef;
    yerelDuyurular = yerelDuyurular.filter(function (y) { return duyuruId(y) !== id; });
    renderDuyuru();
  }

  function silmeyiGeriAl() {
    if (!sonSilinen) return;
    var d = sonSilinen, id = duyuruId(d);
    store(DUYURU_SIL_STORE, JSON.stringify(silinenler().filter(function (k) {
      return k !== id && k !== "e:" + d.etiket;
    })));
    sonSilinen = null;
    // Sunucu kaydi bir sonraki yuklemede kendiliginden geri gelir; yerel
    // kaydi ise arsivden silmistik, geri yazmak gerekiyor.
    var geri = (d.kaynak === "yerel" && window.EvologArsiv)
      ? window.EvologArsiv.yaz(d)["catch"](function () { return null; })
      : Promise.resolve(null);
    geri.then(loadDuyuru).then(function () { toast("Duyuru geri alındı"); });
  }

  /** Katmandaki tam kart. */
  function duyuruKart(d) {
    var z = String(d.zaman || "").replace("T", " ").slice(0, 16);
    var kimden = d.kaynak === "yerel" ? "Bildirim" : "Antrenörden";
    return '<div class="duyuru' + (okunduMu(d) ? " okundu" : "") + '">' +
      '<div class="ust"><span class="et">' + kimden + "</span>" +
      '<span class="z">' + esc(z) + "</span>" +
      '<button type="button" class="dsil" data-duyuru-sil="' + esc(duyuruId(d)) + '" ' +
        'aria-label="Bu duyuruyu sil">✕</button></div>' +
      (d.baslik ? '<div class="b">' + esc(d.baslik) + "</div>" : "") +
      '<div class="m">' + esc(d.metin || "") + "</div></div>";
  }

  /* Ana ekranda duyurunun TAM metni duruyordu; uzun duyuru butun ekrani
     asagi itiyordu. Artik yalnizca okunmamis duyuru icin tek satirlik bir
     serit var; tam metin Duyurular katmaninda. Okundu denince serit kayboluyor,
     duyuru katmanda kalmaya devam ediyor. */
  function renderDuyuru() {
    var hepsi = duyurular();
    var slot = el("duyuruSlot");
    if (slot) {
      var yeni = hepsi.filter(function (d) { return !okunduMu(d); });
      if (!yeni.length) {
        slot.innerHTML = "";
      } else {
        var d = yeni[0];
        var ozet = d.baslik || String(d.metin || "").replace(/\s+/g, " ").trim();
        if (ozet.length > 70) ozet = ozet.slice(0, 70) + "\u2026";
        slot.innerHTML =
          '<div class="duyuru-serit">' +
            '<button type="button" class="ds-ac" data-duyuru-ac>' +
              '<span class="ds-et">Antren\u00f6rden' +
              (yeni.length > 1 ? " \u00b7 " + yeni.length + " yeni" : "") + "</span>" +
              '<span class="ds-oz">' + esc(ozet) + "</span>" +
            "</button>" +
            '<button type="button" class="ds-ok" data-duyuru-okundu ' +
              'aria-label="Okundu olarak i\u015faretle">Okundu</button>' +
          "</div>";
      }
    }
    var kutu = el("duyuruListe");
    if (kutu) {
      var geri = sonSilinen
        ? '<div class="dgeri">Duyuru silindi' +
            '<button type="button" data-duyuru-geri>Geri al</button></div>'
        : "";
      kutu.innerHTML = geri + (hepsi.length
        ? hepsi.map(duyuruKart).join("") +
          '<button type="button" class="dokundu" data-duyuru-okundu>Hepsini okundu i\u015faretle</button>'
        : '<p class="bos">Hen\u00fcz duyuru yok.</p>');
    }
    var n = okunmamisSayisi();
    var rozet = el("duyuruRozet");
    if (rozet) {
      rozet.textContent = n > 99 ? "99+" : String(n);
      rozet.hidden = !n;
    }
    var sekme = el("tab-duyuru");
    if (sekme) {
      sekme.classList.toggle("yeni", !!n);
      sekme.setAttribute("aria-label", n ? "Duyurular \u00b7 " + n + " okunmam\u0131\u015f" : "Duyurular");
    }
  }

  function loadDuyuru() {
    // Cevrimdisiyken sunucu kismi sessizce bos kalir; duyuru kritik veri degil.
    var uzak = fetch("/api/duyuru?age=" + age, { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : { duyurular: [] }; })
      .then(function (res) { sunucuDuyurular = res.duyurular || []; })
      ["catch"](function () { /* sunucu yok: elimizdeki liste kalsin */ });
    var yerel = (window.EvologArsiv ? window.EvologArsiv.hepsi() : Promise.resolve([]))
      .then(function (l) { yerelDuyurular = l || []; })
      ["catch"](function () { yerelDuyurular = []; });
    return Promise.all([uzak, yerel]).then(renderDuyuru);
  }

  function openDuyuru() {
    var panel = el("duyuruPanel");
    if (!panel) return;
    renderDuyuru();
    panel.hidden = false;
    document.body.classList.add("locked");
  }

  function closeDuyuru() {
    var panel = el("duyuruPanel");
    if (!panel || panel.hidden) return;
    panel.hidden = true;
    document.body.classList.remove("locked");
    sonSilinen = null;   // "Geri al" yalnizca panel acikken gecerli
    // Katmani acip kapatan veli tam metni gormustur; serit bir daha cikmasin.
    okunduIsaretle();
  }

  // Uygulama ACIKKEN bildirim gelirse liste ve rozet aninda tazelensin.
  if (navigator.serviceWorker) {
    navigator.serviceWorker.addEventListener("message", function (ev) {
      if (ev.data && ev.data.tip === "duyuru-geldi") loadDuyuru();
    });
  }

  function render() {
    renderIdentity();
    renderDuyuru();
    renderSync();
    renderIosHint();
    renderMatches();
    renderLeagueWeeks();
    renderStandings();
    renderRoster();
    renderTraining();
    renderSheet();
  }

  // Basa don: acik katmanlari kapat, ilk sekmeye gec, yukari kaydir.
  function basaDon() {
    closeCoach();
    closeDuyuru();
    closeSheet();
    var ps = el("playerSheet");
    if (ps && !ps.hidden) { ps.hidden = true; ps.innerHTML = ""; document.body.classList.remove("locked"); }
    location.hash = PANELS[0];
    showPanel(PANELS[0]);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  var homeBtn = el("homeBtn");
  if (homeBtn) homeBtn.addEventListener("click", basaDon);

  document.addEventListener("click", function (ev) {
    if (!ev.target.closest) return;
    if (ev.target.closest("[data-duyuru-ac]")) { openDuyuru(); return; }
    if (ev.target.closest("[data-duyuru-okundu]")) {
      okunduIsaretle();
      toast("Duyurular okundu işaretlendi");
      return;
    }
    var silBtn = ev.target.closest("[data-duyuru-sil]");
    if (silBtn) { duyuruSil(silBtn.getAttribute("data-duyuru-sil")); return; }
    if (ev.target.closest("[data-duyuru-geri]")) { silmeyiGeriAl(); return; }
    if (ev.target.closest("#duyuruClose")) { closeDuyuru(); return; }
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") closeDuyuru();
  });

  document.querySelectorAll(".tabbar button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (btn.id === "tab-takim") { openSheet(); return; }
      if (btn.id === "tab-duyuru") { openDuyuru(); return; }
      if (!btn.dataset.panel) return;
      location.hash = btn.dataset.panel;
      showPanel(btn.dataset.panel);
    });
  });

  // Takım/ayarlar sayfası: takım seçimi, bildirim anahtarları, kapatma.
  document.addEventListener("click", function (ev) {
    var t = ev.target;
    if (!t.closest) return;
    if (t.id === "iosHintClose") { store(IOS_STORE, "off"); renderIosHint(); return; }

    var sheet = el("ageSheet");
    if (!sheet || sheet.hidden) return;
    if (t === sheet || t.closest(".pclose")) { closeSheet(); return; }

    var pick = t.closest("[data-age]");
    if (pick) { setAge(pick.dataset.age); return; }

    var coach = t.closest("[data-coach]");
    if (coach) { openCoach(coach.dataset.coach); return; }

    var tgl = t.closest("[data-push]");
    if (tgl && !tgl.disabled) { togglePushAge(tgl.dataset.push, tgl.dataset.want === "1"); }
  });

  // Panel: sekme degistirme ve kapatma (katmanin kendi olaylari).
  document.addEventListener("click", function (ev) {
    var t = ev.target;
    if (!t.closest) return;
    var panel = el("coachPanel");
    if (!panel || panel.hidden) return;
    if (t.closest("#coachClose")) { closeCoach(); return; }
    var ctab = t.closest("[data-ctab]");
    if (ctab) openCoach(ctab.dataset.ctab);
  });

  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    var panel = el("coachPanel");
    if (panel && !panel.hidden) closeCoach();
  });

  document.addEventListener("click", function (ev) {
    var head = ev.target.closest && ev.target.closest("button.event[aria-controls]");
    if (!head || head.disabled) return;
    var body = el(head.getAttribute("aria-controls") || "");
    if (!body) return;
    var open = body.hidden;
    body.hidden = !open;
    head.setAttribute("aria-expanded", open ? "true" : "false");
    var caret = head.querySelector(".ev-detay");
    if (caret) caret.textContent = open ? "Kapat ▴" : "Detay ▾";
  });

  document.addEventListener("click", function (ev) {
    var row = ev.target.closest && ev.target.closest(".pl[data-player]");
    if (row) { openPlayer(row.dataset.player); return; }
    if (ev.target.closest && (ev.target.closest(".pclose") ||
        (ev.target.id === "playerSheet"))) closePlayer();
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    var sheet = el("ageSheet");
    if (sheet && !sheet.hidden) { closeSheet(); return; }
    closePlayer();
  });

  document.querySelectorAll(".seg button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var lig = btn.dataset.view === "lig";
      el("seg-bizim").setAttribute("aria-selected", lig ? "false" : "true");
      el("seg-lig").setAttribute("aria-selected", lig ? "true" : "false");
      el("viewOurs").hidden = lig;
      el("viewLeague").hidden = !lig;
      window.scrollTo(0, 0);
    });
  });

  document.addEventListener("click", function (ev) {
    var head = ev.target.closest && ev.target.closest(".wk-h");
    if (!head) return;
    var body = head.nextElementSibling;
    if (!body) return;
    var open = body.hidden;
    body.hidden = !open;
    head.setAttribute("aria-expanded", open ? "true" : "false");
    var caret = head.querySelector(".caret");
    if (caret) caret.textContent = open ? "▴" : "▾";
  });

  window.addEventListener("hashchange", function () {
    var name = location.hash.replace("#", "");
    if (PANELS.indexOf(name) !== -1) showPanel(name);
  });

  var initial = location.hash.replace("#", "");
  if (PANELS.indexOf(initial) !== -1) showPanel(initial);

  if ("serviceWorker" in navigator && !INLINE) {
    // Yeni surum devralinca sayfayi bir kez yenile: maç saati degistiginde
    // velinin ikinci acilisi beklemeden guncel bilgiyi gormesi gerekiyor.
    // Ilk kurulumda controller yoktur; o durumda yenilemeyiz.
    var vardiKontrolcu = !!navigator.serviceWorker.controller;
    var yenileniyor = false;
    navigator.serviceWorker.addEventListener("controllerchange", function () {
      if (!vardiKontrolcu || yenileniyor) return;
      yenileniyor = true;
      location.reload();
    });

    window.addEventListener("load", function () {
      navigator.serviceWorker.register("sw.js", { updateViaCache: "none" }).then(function (reg) {
        reg.update().catch(function () {});
        // Uygulama one alindiginda yeni surum var mi diye bak.
        document.addEventListener("visibilitychange", function () {
          if (!document.hidden) reg.update().catch(function () {});
        });
      }).catch(function () {});
    });
  }

  boot();
})();
