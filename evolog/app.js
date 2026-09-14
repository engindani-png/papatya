/* Evolog U14 Kız — uygulama mantığı */
(function () {
  "use strict";

  var DATA = window.EVOLOG_DATA_PATH || "../data/";
  var INLINE = window.EVOLOG_INLINE_DATA || null;
  var DEMO = new URLSearchParams(location.search).get("demo") === "1";
  var PANELS = ["maclar", "puan", "kadro", "antrenman"];

  var GUNLER = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];
  var AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

  var state = { team: null, training: null, league: null, timer: null };

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

  function isOurTeam(name) {
    var aliases = ["evolog"];
    if (state.team && state.team.club) aliases.push(norm(state.team.club));
    var n = norm(name);
    return aliases.some(function (a) { return a && n.indexOf(a) !== -1; });
  }

  // ------------------------------------------------------------- veri
  function load(key, file) {
    if (INLINE) return Promise.resolve(INLINE[key] || null);
    return fetch(DATA + file, { cache: "no-cache" })
      .then(function (r) { if (!r.ok) throw new Error(file); return r.json(); })
      .catch(function () { return null; });
  }

  function loadAll() {
    return Promise.all([
      load("team", "team.json"),
      load("training", "training.json"),
      load(DEMO ? "leagueDemo" : "league", DEMO ? "league.example.json" : "league.json")
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
      var y = window.scrollY;
      render();
      window.scrollTo(0, y);
      if (announce) toast("Yeni veri geldi — ekran güncellendi");
      return true;
    }).catch(function () { sync.busy = false; return false; });
  }

  function startAutoRefresh() {
    if (INLINE || sync.poll) return;
    sync.poll = setInterval(function () {
      if (document.visibilityState === "visible") refresh(true);
    }, REFRESH_MS);
    document.addEventListener("visibilitychange", function () {
      // Uygulamaya dönüldüğünde (telefonda en sık bu olur) hemen bak.
      if (document.visibilityState === "visible" && Date.now() - sync.lastCheck > 15000) {
        refresh(true);
      }
    });
    window.addEventListener("online", function () { refresh(true); });
  }

  function boot() {
    loadAll().then(function (res) {
      state.team = res[0];
      state.training = res[1];
      state.league = res[2];
      sync.sig = signature(res[0], res[1], res[2]);
      sync.lastCheck = Date.now();
      render();
      startAutoRefresh();
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
    slot.innerHTML =
      '<section class="board">' +
        '<div class="label">Sıradaki maç' + (next.week ? " · " + esc(next.week) + ". hafta" : "") + "</div>" +
        '<div class="board-teams">' +
          '<div class="side">' + teamLogo(next.homeLogo, "big") +
          '<div class="tname">' + esc(next.home) + "</div>" +
            '<div class="trole">Ev sahibi</div></div>' +
          '<div class="dash">—</div>' +
          '<div class="side right">' + teamLogo(next.awayLogo, "big") +
          '<div class="tname">' + esc(next.away) + "</div>" +
            '<div class="trole">Deplasman</div></div>' +
        "</div>" +
        '<div class="board-meta">' +
          (d ? "<span>" + ico("cal") + esc(fmtDate(d)) + "</span>" : "") +
          (next.time ? "<span>" + ico("clock") + esc(next.time) + "</span>" : "") +
          (next.venue ? "<span>" + ico("pin") + esc(next.venue) + "</span>" : "") +
        "</div>" +
        (d ? '<div class="clock" id="clock"></div>' : "") +
      "</section>";
    if (d) startClock(d);
  }

  function startClock(target) {
    if (state.timer) clearInterval(state.timer);
    function tick() {
      var box = el("clock");
      if (!box) { clearInterval(state.timer); return; }
      var diff = target.getTime() - Date.now();
      if (diff <= 0) {
        box.className = "clock live";
        box.innerHTML = '<div class="seg" style="grid-column:1/-1">' +
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
        return '<div class="seg"><span class="n">' + p[0] +
          '</span><span class="u">' + p[1] + "</span></div>";
      }).join("");
    }
    tick();
    state.timer = setInterval(tick, 1000);
  }

  function tagFor(f) {
    if (f.homeScore == null) return '<span class="tag s">Oynanacak</span>';
    if (!f.isOurs) return "";
    var ourHome = isOurTeam(f.home);
    var biz = ourHome ? f.homeScore : f.awayScore;
    var rakip = ourHome ? f.awayScore : f.homeScore;
    return biz > rakip ? '<span class="tag w">Galibiyet</span>'
                       : '<span class="tag l">Mağlubiyet</span>';
  }

  function hasDetail(f) {
    return !!((f.quarters && f.quarters.length) ||
      (f.boxscore && ((f.boxscore.home || []).length || (f.boxscore.away || []).length)));
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
        return "<tr><td>" + esc(r.no != null ? r.no : "") + "</td><td>" + esc(r.name || "") + "</td>" +
          cols.map(function (c) {
            return "<td" + (c[0] === "points" ? ' class="pts"' : "") + ">" +
              esc(r[c[0]] != null ? r[c[0]] : "–") + "</td>";
          }).join("") + "</tr>";
      }).join("") + "</tbody></table></div>";
  }

  function fixtureRow(f, idx) {
    var d = f._d;
    var played = f.homeScore != null && f.awayScore != null;
    var homeWin = played && f.homeScore > f.awayScore;
    var awayWin = played && f.awayScore > f.homeScore;
    var detail = hasDetail(f);
    var bodyId = "fb-" + idx;

    var sub = [f.venue, f.week ? f.week + ". hafta" : null].filter(Boolean).join(" · ");

    var head =
      '<button class="fx-head"' +
        (detail ? ' aria-expanded="false" aria-controls="' + bodyId + '"' : " disabled") + ">" +
        '<time class="fx-when"><span class="dd">' + (d ? d.getDate() : "–") + "</span>" +
          '<span class="mm">' + (d ? esc(AYLAR[d.getMonth()]) : "") + "</span>" +
          (f.time ? '<span class="hh">' + esc(f.time) + "</span>" : "") + "</time>" +
        "<div>" +
          '<div class="fx-team ' + (homeWin ? "won" : awayWin ? "lost" : "") + '">' +
            '<span class="nm">' + teamCell(f.home, f.homeLogo) + "</span>" +
            '<span class="sc">' + (played ? esc(f.homeScore) : "") + "</span></div>" +
          '<div class="fx-team ' + (awayWin ? "won" : homeWin ? "lost" : "") + '">' +
            '<span class="nm">' + teamCell(f.away, f.awayLogo) + "</span>" +
            '<span class="sc">' + (played ? esc(f.awayScore) : "") + "</span></div>" +
          (sub ? '<div class="fx-sub">' + ico("pin") + "<span>" + esc(sub) + "</span></div>" : "") +
        "</div>" +
        "<div>" + tagFor(f) + (detail ? '<div class="caret">Detay ▾</div>' : "") + "</div>" +
      "</button>";

    var body = "";
    if (detail) {
      var per = (f.quarters || []).map(function (x, i) {
        return '<div class="p"><span class="pn">' + (i + 1) + '. Ç</span>' +
          '<span class="ps">' + esc(x.home) + "–" + esc(x.away) + "</span></div>";
      }).join("");
      body = '<div class="fx-body" id="' + bodyId + '" hidden>' +
        (per ? '<div class="periods">' + per + "</div>" : "") +
        boxTable(f.boxscore && f.boxscore.home, f.home) +
        boxTable(f.boxscore && f.boxscore.away, f.away) +
        "</div>";
    }
    return '<article class="fx' + (f.isOurs ? " ours" : "") + '">' + head + body + "</article>";
  }

  function renderMatches() {
    el("matchNotice").innerHTML = notice(state.league);
    var sets = splitFixtures();
    renderBoard(sets.upcoming.filter(function (f) { return f.isOurs !== false; })[0] || sets.upcoming[0]);
    el("upcomingList").innerHTML = sets.upcoming.length
      ? sets.upcoming.map(function (f, i) { return fixtureRow(f, "u" + i); }).join("")
      : '<div class="blank">Planlanmış maç görünmüyor.</div>';
    el("playedList").innerHTML = sets.played.length
      ? sets.played.map(function (f, i) { return fixtureRow(f, "p" + i); }).join("")
      : '<div class="blank">Henüz oynanmış maç yok.</div>';
  }

  // ------------------------------------------------------------- puan durumu
  function renderStandings() {
    el("standingsNotice").innerHTML = notice(state.league);
    var rows = (state.league && state.league.standings) || [];
    var slot = el("standingsSlot");
    if (state.league && state.league.group) {
      el("standingsTitle").textContent = "Puan durumu · " + state.league.group;
    }
    if (!rows.length) {
      slot.innerHTML = '<div class="blank">Puan durumu henüz çekilmedi.</div>';
      return;
    }
    function v(x) { return x == null ? "–" : esc(x); }
    slot.innerHTML =
      '<div class="scroll"><table class="tbl"><thead><tr><th>#</th><th>Takım</th>' +
      "<th>O</th><th>G</th><th>M</th><th>A</th><th>Y</th><th>AV</th><th>P</th></tr></thead><tbody>" +
      rows.map(function (r, i) {
        var ours = r.isOurs != null ? r.isOurs : isOurTeam(r.team);
        return '<tr class="' + (ours ? "ours" : "") + '">' +
          "<td>" + (r.rank != null ? esc(r.rank) : i + 1) + "</td>" +
          "<td>" + teamCell(r.team, r.logo) + "</td>" +
          "<td>" + v(r.played) + "</td><td>" + v(r.won) + "</td><td>" + v(r.lost) + "</td>" +
          "<td>" + v(r.pointsFor) + "</td><td>" + v(r.pointsAgainst) + "</td>" +
          "<td>" + (r.diff == null ? "–" : (r.diff > 0 ? "+" : "") + esc(r.diff)) + "</td>" +
          "<td>" + v(r.points) + "</td></tr>";
      }).join("") + "</tbody></table></div>" +
      '<p class="swipe-hint">← Tabloyu yana kaydırarak tüm sütunları görebilirsiniz.</p>' +
      '<p class="key">O oynanan · G galibiyet · M mağlubiyet · A atılan sayı · ' +
      "Y yenilen sayı · AV averaj · P puan</p>";
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
    slot.innerHTML = t.players.slice()
      .sort(function (a, b) { return (a.no || 99) - (b.no || 99); })
      .map(function (p) {
        var key = matchStats(stats, p.name) || norm(p.name);
        var st = stats[key];
        if (st) used[key] = true;
        var meta = [p.position, p.height ? p.height + " cm" : null].filter(Boolean).join(" · ");
        // Maç oynamışsa sezon ortalaması satırda görünür, satır profile açılır.
        var right = st && st.games
          ? '<div class="yr avgpts"><b>' + esc(avg(st.points, st.games)) + "</b><span>sayı ort.</span></div>"
          : '<div class="yr">' + esc(p.birthYear || "") + "</div>";
        return '<button class="pl' + (st && st.games ? " has" : "") + '" data-player="' + esc(key) + '">' +
          '<div class="no">' + esc(p.no != null ? p.no : "–") + "</div>" +
          '<div><div class="nm">' + esc(p.name) + "</div>" +
          (meta ? '<div class="meta">' + esc(meta) + "</div>" : "") + "</div>" +
          right + "</button>";
      }).join("");

    // Maç kadrosunda oynayıp lisans listesinde görünmeyenler (üst yaş takviyesi
    // ya da TBF listesi henüz güncellenmemiş olabilir) kaybolmasın.
    var extra = Object.keys(stats).filter(function (k) { return !used[k]; });
    if (extra.length) {
      slot.innerHTML += extra.sort(function (a, b) {
        return (stats[a].no || 99) - (stats[b].no || 99);
      }).map(function (k) {
        var st = stats[k];
        return '<button class="pl has" data-player="' + esc(k) + '">' +
          '<div class="no">' + esc(st.no != null ? st.no : "–") + "</div>" +
          '<div><div class="nm">' + esc(st.name) + "</div>" +
          '<div class="meta">maç kadrosu</div></div>' +
          '<div class="yr avgpts"><b>' + esc(avg(st.points, st.games)) +
          "</b><span>sayı ort.</span></div></button>";
      }).join("");
    }

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
    var tr = state.training, slot = el("sessionsSlot");
    if (!tr || !(tr.sessions || []).length) {
      slot.innerHTML = '<div class="blank">Antrenman programı girilmemiş.</div>';
      el("nextTrainingSlot").innerHTML = "";
      el("venuesSlot").innerHTML = "";
      return;
    }

    var today = new Date().getDay();
    var sorted = tr.sessions.slice().sort(function (a, b) {
      return (a.day - b.day) || String(a.start).localeCompare(String(b.start));
    });
    var next = sorted.map(function (s) { return { s: s, when: nextOccurrence(s.day, s.start) }; })
      .sort(function (a, b) { return a.when - b.when; })[0];

    if (next) {
      var nv = venueOf(next.s.venue);
      el("nextTrainingSlot").innerHTML =
        '<section class="board"><div class="label">Sıradaki antrenman</div>' +
        '<div class="board-teams"><div class="side"><div class="tname">' +
        esc(next.s.title || "Antrenman") + "</div>" +
        (next.s.coach ? '<div class="trole">' + esc(next.s.coach) + "</div>" : "") + "</div></div>" +
        '<div class="board-meta"><span>' + ico("cal") + esc(fmtDate(next.when)) + "</span>" +
        "<span>" + ico("clock") + esc(next.s.start) +
        (next.s.end ? " – " + esc(next.s.end) : "") + "</span>" +
        (nv ? "<span>" + ico("pin") + esc(nv.name) + "</span>" : "") + "</div></section>";
    }

    // Aynı güne düşen antrenmanlar tek gün başlığı altında toplanır —
    // WhatsApp mesajı da böyle geliyor, veliler de böyle okuyor.
    var byDay = [];
    sorted.forEach(function (s) {
      var last = byDay[byDay.length - 1];
      if (last && last.day === s.day) last.items.push(s);
      else byDay.push({ day: s.day, items: [s] });
    });

    slot.innerHTML = byDay.map(function (grp) {
      var jsDay = grp.day % 7;
      var isToday = jsDay === today;
      var when = nextOccurrence(grp.day, grp.items[0].start);
      return '<section class="tday' + (isToday ? " today" : "") + '">' +
        '<header class="tday-h">' +
          '<span class="tday-n">' + esc(GUNLER[jsDay]) + "</span>" +
          '<span class="tday-d">' + esc(when ? when.getDate() + " " + AYLAR[when.getMonth()] : "") + "</span>" +
          (isToday ? '<span class="now">BUGÜN</span>' : "") +
        "</header>" +
        grp.items.map(function (s) {
          var v = venueOf(s.venue);
          var col = (v && v.color) || "#f2a03d";
          return '<div class="tslot" style="--venue:' + esc(col) + '">' +
            '<div class="tslot-t">' + esc(s.start) +
              (s.end ? '<span class="tslot-e">' + esc(s.end) + "</span>" : "") + "</div>" +
            '<div class="tslot-b">' +
              '<div class="tslot-x">' + esc(s.title || "Antrenman") + "</div>" +
              '<div class="tslot-v"><span class="vchip">' +
                (v ? esc(v.name) : esc(s.venue || "Salon belirtilmemiş")) + "</span>" +
                (v && v.maps ? '<a href="' + esc(v.maps) + '" target="_blank" rel="noopener">Yol tarifi</a>' : "") +
              "</div>" +
              (s.coach ? '<div class="tslot-c">' + esc(s.coach) + "</div>" : "") +
            "</div></div>";
        }).join("") +
        "</section>";
    }).join("");

    var exc = (tr.exceptions || []).filter(function (e) {
      return new Date(e.date + "T23:59:59") >= new Date();
    });
    el("venuesSlot").innerHTML =
      (tr.venues || []).map(function (v) {
        return '<div class="venue"><div class="vn">' + esc(v.name) + "</div>" +
          '<div class="va">' + esc(v.address || "") + "</div>" +
          (v.maps ? '<a href="' + esc(v.maps) + '" target="_blank" rel="noopener">Haritada aç →</a>' : "") +
          "</div>";
      }).join("") +
      (exc.length
        ? '<h2 class="eyebrow">Program değişiklikleri</h2>' +
          exc.map(function (e) {
            return '<div class="note"><div><b>' + esc(e.date) + "</b> · " + esc(e.type || "") +
              (e.reason ? " — " + esc(e.reason) : "") + "</div></div>";
          }).join("")
        : "");
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

  function render() {
    renderSync();
    renderMatches();
    renderStandings();
    renderRoster();
    renderTraining();
  }

  document.querySelectorAll(".tabbar button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      location.hash = btn.dataset.panel;
      showPanel(btn.dataset.panel);
    });
  });

  document.addEventListener("click", function (ev) {
    var head = ev.target.closest && ev.target.closest(".fx-head");
    if (!head || head.disabled) return;
    var body = el(head.getAttribute("aria-controls") || "");
    if (!body) return;
    var open = body.hidden;
    body.hidden = !open;
    head.setAttribute("aria-expanded", open ? "true" : "false");
    var caret = head.querySelector(".caret");
    if (caret) caret.textContent = open ? "Kapat ▴" : "Detay ▾";
  });

  document.addEventListener("click", function (ev) {
    var row = ev.target.closest && ev.target.closest(".pl[data-player]");
    if (row) { openPlayer(row.dataset.player); return; }
    if (ev.target.closest && (ev.target.closest(".pclose") ||
        (ev.target.id === "playerSheet"))) closePlayer();
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") closePlayer();
  });

  window.addEventListener("hashchange", function () {
    var name = location.hash.replace("#", "");
    if (PANELS.indexOf(name) !== -1) showPanel(name);
  });

  var initial = location.hash.replace("#", "");
  if (PANELS.indexOf(initial) !== -1) showPanel(initial);

  if ("serviceWorker" in navigator && !INLINE) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("sw.js").catch(function () {});
    });
  }

  boot();
})();
