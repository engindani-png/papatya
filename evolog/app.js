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

  function boot() {
    Promise.all([
      load("team", "team.json"),
      load("training", "training.json"),
      load(DEMO ? "leagueDemo" : "league", DEMO ? "league.example.json" : "league.json")
    ]).then(function (res) {
      state.team = res[0];
      state.training = res[1];
      state.league = res[2];
      render();
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
        "<code>scripts/tbf_config.json</code> içine lig sayfası adreslerini girip " +
        "“TBF veri senkronizasyonu” iş akışını çalıştırın.</div></div>";
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
          '<div class="side"><div class="tname">' + esc(next.home) + "</div>" +
            '<div class="trole">Ev sahibi</div></div>' +
          '<div class="dash">—</div>' +
          '<div class="side right"><div class="tname">' + esc(next.away) + "</div>" +
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
            '<span class="nm">' + esc(f.home) + "</span>" +
            '<span class="sc">' + (played ? esc(f.homeScore) : "") + "</span></div>" +
          '<div class="fx-team ' + (awayWin ? "won" : homeWin ? "lost" : "") + '">' +
            '<span class="nm">' + esc(f.away) + "</span>" +
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
          "<td>" + esc(r.team) + "</td>" +
          "<td>" + v(r.played) + "</td><td>" + v(r.won) + "</td><td>" + v(r.lost) + "</td>" +
          "<td>" + v(r.pointsFor) + "</td><td>" + v(r.pointsAgainst) + "</td>" +
          "<td>" + (r.diff == null ? "–" : (r.diff > 0 ? "+" : "") + esc(r.diff)) + "</td>" +
          "<td>" + v(r.points) + "</td></tr>";
      }).join("") + "</tbody></table></div>" +
      '<p class="key">O oynanan · G galibiyet · M mağlubiyet · A atılan sayı · ' +
      "Y yenilen sayı · AV averaj · P puan</p>";
  }

  // ------------------------------------------------------------- kadro
  function renderRoster() {
    var t = state.team, slot = el("rosterSlot");
    if (!t || !(t.players || []).length) {
      slot.innerHTML = '<div class="blank">Kadro bilgisi bulunamadı.</div>';
      el("staffSlot").innerHTML = "";
      return;
    }
    slot.innerHTML = t.players.slice()
      .sort(function (a, b) { return (a.no || 99) - (b.no || 99); })
      .map(function (p) {
        var meta = [p.position, p.height ? p.height + " cm" : null].filter(Boolean).join(" · ");
        return '<div class="pl"><div class="no">' + esc(p.no != null ? p.no : "–") + "</div>" +
          '<div><div class="nm">' + esc(p.name) + "</div>" +
          (meta ? '<div class="meta">' + esc(meta) + "</div>" : "") + "</div>" +
          '<div class="yr">' + esc(p.birthYear || "") + "</div></div>";
      }).join("");

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

    slot.innerHTML = sorted.map(function (s) {
      var v = venueOf(s.venue), jsDay = s.day % 7;
      return '<div class="ts' + (jsDay === today ? " today" : "") + '">' +
        '<div class="dy">' + esc(GUNLER[jsDay]) +
        (jsDay === today ? '<span class="now">BUGÜN</span>' : "") + "</div>" +
        '<div><div class="tt">' + esc(s.title || "Antrenman") + "</div>" +
        '<div class="hr">' + esc(s.start) + (s.end ? " – " + esc(s.end) : "") + "</div>" +
        '<div class="wh">' + ico("pin") + "<span>" + (v ? esc(v.name) : esc(s.venue || "–")) +
        (s.coach ? " · " + esc(s.coach) : "") + "</span>" +
        (v && v.maps ? '<a href="' + esc(v.maps) + '" target="_blank" rel="noopener">Yol tarifi</a>' : "") +
        "</div></div></div>";
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
