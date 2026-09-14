/* Evolog U14 Kız - uygulama mantığı */
(function () {
  "use strict";

  var DATA = "../data/";
  var params = new URLSearchParams(location.search);
  var DEMO = params.get("demo") === "1";

  var GUNLER = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];
  var AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

  var state = { team: null, training: null, league: null, countdownTimer: null };

  // ---------------------------------------------------------------- yardımcı
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

  /** "2026-01-24" + "13:30" -> Date (yerel saat) */
  function matchDate(f) {
    if (!f || !f.date) return null;
    var p = String(f.date).split("-").map(Number);
    if (p.length < 3 || !p[0]) return null;
    var t = (f.time || "00:00").split(":").map(Number);
    return new Date(p[0], p[1] - 1, p[2], t[0] || 0, t[1] || 0);
  }

  function fmtDate(d) {
    if (!d) return "";
    return d.getDate() + " " + AYLAR[d.getMonth()] + " " + d.getFullYear() +
      ", " + GUNLER[d.getDay()];
  }

  function isOurTeam(name) {
    var aliases = ["evolog"];
    if (state.team && state.team.club) aliases.push(norm(state.team.club));
    var n = norm(name);
    return aliases.some(function (a) { return a && n.indexOf(a) !== -1; });
  }

  // ---------------------------------------------------------------- veri
  function load(file) {
    return fetch(DATA + file, { cache: "no-cache" })
      .then(function (r) {
        if (!r.ok) throw new Error(file + " okunamadı (" + r.status + ")");
        return r.json();
      });
  }

  function boot() {
    Promise.all([
      load("team.json").catch(function () { return null; }),
      load("training.json").catch(function () { return null; }),
      load(DEMO ? "league.example.json" : "league.json").catch(function () { return null; })
    ]).then(function (res) {
      state.team = res[0];
      state.training = res[1];
      state.league = res[2];
      render();
    });
  }

  // ---------------------------------------------------------------- başlık
  function renderSync() {
    var box = el("syncBox");
    var lg = state.league;
    if (!lg) {
      box.innerHTML = '<span><span class="dot off"></span> veri yok</span>';
      return;
    }
    if (lg.league) {
      el("leagueLabel").textContent = lg.league + (lg.group ? " · " + lg.group : "");
    }
    if (!lg.updatedAt) {
      box.innerHTML = '<span><span class="dot off"></span> senkronize değil</span>';
      return;
    }
    var d = new Date(lg.updatedAt);
    var saatFarki = (Date.now() - d.getTime()) / 36e5;
    var cls = saatFarki < 24 ? "ok" : saatFarki < 96 ? "stale" : "off";
    box.innerHTML =
      '<span><span class="dot ' + cls + '"></span> TBF verisi</span>' +
      '<span>' + esc(d.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit" })) +
      " " + esc(d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })) + "</span>";
  }

  function notice(lg) {
    if (!lg) {
      return '<div class="banner error"><span>⚠️</span><div>Lig verisi yüklenemedi. ' +
        'Sayfayı yenileyin veya <code>data/league.json</code> dosyasını kontrol edin.</div></div>';
    }
    var out = "";
    if (lg.isDemo) {
      out += '<div class="banner"><span>🧪</span><div><b>Önizleme verisi.</b> ' +
        'Bu ekrandaki maçlar ve puanlar gerçek değildir, yalnızca arayüzü göstermek içindir.</div></div>';
    } else if (lg.isPlaceholder || (!(lg.standings || []).length && !(lg.fixtures || []).length)) {
      out += '<div class="banner"><span>⏳</span><div><b>TBF verisi henüz çekilmedi.</b> ' +
        '<code>scripts/tbf_config.json</code> içine lig sayfası adreslerini girip ' +
        '“TBF veri senkronizasyonu” iş akışını çalıştırın.</div></div>';
    }
    if (lg.errors && lg.errors.length && !lg.isDemo && !out) {
      out += '<div class="banner error"><span>⚠️</span><div><b>Son senkronizasyon uyarıları:</b><br>' +
        lg.errors.map(esc).join("<br>") + "</div></div>";
    }
    return out;
  }

  // ---------------------------------------------------------------- maçlar
  function splitFixtures() {
    var list = ((state.league && state.league.fixtures) || []).slice();
    list.forEach(function (f) {
      f._d = matchDate(f);
      if (f.isOurs == null) f.isOurs = isOurTeam(f.home) || isOurTeam(f.away);
    });
    var now = new Date();
    var played = list.filter(function (f) { return f.homeScore != null && f.awayScore != null; });
    var upcoming = list.filter(function (f) {
      return !(f.homeScore != null && f.awayScore != null) &&
        (!f._d || f._d.getTime() > now.getTime() - 3 * 36e5);
    });
    played.sort(function (a, b) { return (b.date || "").localeCompare(a.date || ""); });
    upcoming.sort(function (a, b) { return (a.date || "").localeCompare(b.date || ""); });
    return { played: played, upcoming: upcoming };
  }

  function renderHero(next) {
    var slot = el("heroSlot");
    if (!next) { slot.innerHTML = ""; return; }
    var d = next._d;
    slot.innerHTML =
      '<div class="hero">' +
        '<div class="label">Sıradaki Maç' + (next.week ? " · " + esc(next.week) + ". Hafta" : "") + "</div>" +
        '<div class="teams">' +
          '<div class="team">' + esc(next.home) + "</div>" +
          '<div class="vs">VS</div>' +
          '<div class="team away">' + esc(next.away) + "</div>" +
        "</div>" +
        '<div class="meta">' +
          (d ? "<span>📅 " + esc(fmtDate(d)) + "</span>" : "") +
          (next.time ? "<span>🕐 " + esc(next.time) + "</span>" : "") +
          (next.venue ? "<span>📍 " + esc(next.venue) + "</span>" : "") +
        "</div>" +
        (d ? '<div class="countdown" id="countdown"></div>' : "") +
      "</div>";
    if (d) startCountdown(d);
  }

  function startCountdown(target) {
    if (state.countdownTimer) clearInterval(state.countdownTimer);
    function tick() {
      var box = el("countdown");
      if (!box) { clearInterval(state.countdownTimer); return; }
      var diff = target.getTime() - Date.now();
      if (diff <= 0) {
        box.innerHTML = '<div class="cd-box"><span class="n">🏀</span>' +
          '<span class="u">Maç zamanı!</span></div>';
        clearInterval(state.countdownTimer);
        return;
      }
      var gun = Math.floor(diff / 864e5);
      var saat = Math.floor(diff / 36e5) % 24;
      var dk = Math.floor(diff / 6e4) % 60;
      var sn = Math.floor(diff / 1e3) % 60;
      box.innerHTML = [[gun, "gün"], [saat, "saat"], [dk, "dakika"], [sn, "saniye"]]
        .map(function (p) {
          return '<div class="cd-box"><span class="n">' + p[0] +
            '</span><span class="u">' + p[1] + "</span></div>";
        }).join("");
    }
    tick();
    state.countdownTimer = setInterval(tick, 1000);
  }

  function resultPill(f) {
    if (f.homeScore == null) return '<span class="pill s">Oynanacak</span>';
    if (!f.isOurs) return "";
    var ourHome = isOurTeam(f.home);
    var bizim = ourHome ? f.homeScore : f.awayScore;
    var rakip = ourHome ? f.awayScore : f.homeScore;
    return bizim > rakip ? '<span class="pill w">Galibiyet</span>'
                         : '<span class="pill l">Mağlubiyet</span>';
  }

  function hasDetail(f) {
    return !!((f.quarters && f.quarters.length) ||
      (f.boxscore && ((f.boxscore.home || []).length || (f.boxscore.away || []).length)));
  }

  function boxTable(rows, title) {
    if (!rows || !rows.length) return "";
    var cols = [
      ["min", "DK"], ["points", "SAY"], ["rebounds", "RIB"], ["assists", "AST"],
      ["steals", "TOP Ç"], ["blocks", "BLK"], ["turnovers", "HATA"], ["fouls", "FAUL"]
    ].filter(function (c) {
      return rows.some(function (r) { return r[c[0]] != null; });
    });
    return '<div class="section-title">' + esc(title) + "</div>" +
      '<div class="table-wrap"><table class="box"><thead><tr><th>#</th><th>Oyuncu</th>' +
      cols.map(function (c) { return "<th>" + esc(c[1]) + "</th>"; }).join("") +
      "</tr></thead><tbody>" +
      rows.map(function (r) {
        return "<tr><td>" + esc(r.no != null ? r.no : "") + "</td><td>" + esc(r.name || "") + "</td>" +
          cols.map(function (c) {
            var cls = c[0] === "points" ? ' class="pts"' : "";
            return "<td" + cls + ">" + esc(r[c[0]] != null ? r[c[0]] : "-") + "</td>";
          }).join("") + "</tr>";
      }).join("") + "</tbody></table></div>";
  }

  function matchCard(f, idx) {
    var d = f._d;
    var played = f.homeScore != null && f.awayScore != null;
    var homeWin = played && f.homeScore > f.awayScore;
    var awayWin = played && f.awayScore > f.homeScore;
    var detail = hasDetail(f);
    var bodyId = "mb-" + idx;

    var head =
      '<button class="match-head" ' + (detail ? 'aria-expanded="false" aria-controls="' + bodyId + '"' : 'disabled') + '>' +
        '<div class="match-date"><span class="d">' + (d ? d.getDate() : "?") + "</span>" +
          '<span class="m">' + (d ? esc(AYLAR[d.getMonth()]) : "") + "</span></div>" +
        '<div class="match-teams">' +
          '<div class="row ' + (homeWin ? "win" : awayWin ? "lose" : "") + '">' +
            '<span class="nm">' + esc(f.home) + "</span>" +
            '<span class="sc">' + (played ? esc(f.homeScore) : "") + "</span></div>" +
          '<div class="row ' + (awayWin ? "win" : homeWin ? "lose" : "") + '">' +
            '<span class="nm">' + esc(f.away) + "</span>" +
            '<span class="sc">' + (played ? esc(f.awayScore) : "") + "</span></div>" +
          '<div class="info">' +
            (f.time ? "<span>🕐 " + esc(f.time) + "</span>" : "") +
            (f.venue ? "<span>📍 " + esc(f.venue) + "</span>" : "") +
            (f.week ? "<span>" + esc(f.week) + ". hafta</span>" : "") +
          "</div>" +
        "</div>" +
        "<div>" + resultPill(f) + (detail ? '<div class="chev">▾</div>' : "") + "</div>" +
      "</button>";

    var body = "";
    if (detail) {
      var q = (f.quarters || []).map(function (x, i) {
        return '<div class="q"><span class="qn">' + (i + 1) + '. Ç</span>' +
          '<span class="qs">' + esc(x.home) + "-" + esc(x.away) + "</span></div>";
      }).join("");
      body = '<div class="match-body" id="' + bodyId + '" hidden>' +
        (q ? '<div class="quarters">' + q + "</div>" : "") +
        boxTable(f.boxscore && f.boxscore.home, f.home + " istatistikleri") +
        boxTable(f.boxscore && f.boxscore.away, f.away + " istatistikleri") +
        "</div>";
    }
    return '<article class="match' + (f.isOurs ? " ours" : "") + '">' + head + body + "</article>";
  }

  function renderMatches() {
    el("matchNotice").innerHTML = notice(state.league);
    var sets = splitFixtures();
    renderHero(sets.upcoming.filter(function (f) { return f.isOurs !== false; })[0] || sets.upcoming[0]);

    el("upcomingList").innerHTML = sets.upcoming.length
      ? sets.upcoming.map(matchCard).join("")
      : '<div class="empty">Planlanmış maç görünmüyor.</div>';
    el("playedList").innerHTML = sets.played.length
      ? sets.played.map(function (f, i) { return matchCard(f, "p" + i); }).join("")
      : '<div class="empty">Henüz oynanmış maç yok.</div>';
  }

  // ---------------------------------------------------------------- puan durumu
  function renderStandings() {
    el("standingsNotice").innerHTML = notice(state.league);
    var rows = (state.league && state.league.standings) || [];
    var slot = el("standingsSlot");
    if (state.league && state.league.group) {
      el("standingsTitle").textContent = "Puan Durumu · " + state.league.group;
    }
    if (!rows.length) {
      slot.innerHTML = '<div class="empty">Puan durumu henüz çekilmedi.</div>';
      return;
    }
    slot.innerHTML =
      '<div class="card" style="padding:8px 10px"><div class="table-wrap"><table class="standings">' +
      "<thead><tr><th>#</th><th>Takım</th><th>O</th><th>G</th><th>M</th>" +
      "<th>A</th><th>Y</th><th>AV</th><th>P</th></tr></thead><tbody>" +
      rows.map(function (r, i) {
        var ours = r.isOurs != null ? r.isOurs : isOurTeam(r.team);
        function v(x) { return x == null ? "-" : esc(x); }
        return '<tr class="' + (ours ? "ours" : "") + '">' +
          '<td class="rank">' + (r.rank != null ? esc(r.rank) : i + 1) + "</td>" +
          '<td class="tm">' + esc(r.team) + "</td>" +
          "<td>" + v(r.played) + "</td><td>" + v(r.won) + "</td><td>" + v(r.lost) + "</td>" +
          "<td>" + v(r.pointsFor) + "</td><td>" + v(r.pointsAgainst) + "</td>" +
          "<td>" + (r.diff == null ? "-" : (r.diff > 0 ? "+" : "") + esc(r.diff)) + "</td>" +
          '<td class="pts-col">' + v(r.points) + "</td></tr>";
      }).join("") +
      "</tbody></table></div>" +
      '<div class="legend">O: oynanan · G: galibiyet · M: mağlubiyet · ' +
      "A: atılan sayı · Y: yenilen sayı · AV: averaj · P: puan</div></div>";
  }

  // ---------------------------------------------------------------- kadro
  function renderRoster() {
    var t = state.team;
    var slot = el("rosterSlot");
    if (!t || !(t.players || []).length) {
      slot.innerHTML = '<div class="empty">Kadro bilgisi bulunamadı.</div>';
      el("staffSlot").innerHTML = "";
      return;
    }
    slot.innerHTML = t.players.slice()
      .sort(function (a, b) { return (a.no || 99) - (b.no || 99); })
      .map(function (p) {
        var detay = [p.position, p.birthYear || null,
          p.height ? p.height + " cm" : null].filter(Boolean).join(" · ");
        return '<div class="player"><div class="jersey">' + esc(p.no != null ? p.no : "-") + "</div>" +
          '<div><div class="nm">' + esc(p.name) + "</div>" +
          '<div class="po">' + esc(detay) + "</div></div></div>";
      }).join("");

    el("staffSlot").innerHTML = (t.staff || []).map(function (s) {
      return '<div class="staff-row"><div><div>' + esc(s.name) + "</div>" +
        '<div class="role">' + esc(s.role) + "</div></div>" +
        (s.phone ? '<a href="tel:' + esc(s.phone) + '">Ara</a>' : "") + "</div>";
    }).join("") || '<div class="empty">Teknik kadro bilgisi girilmemiş.</div>';
  }

  // ---------------------------------------------------------------- antrenman
  function venueOf(id) {
    return ((state.training && state.training.venues) || [])
      .filter(function (v) { return v.id === id; })[0] || null;
  }

  /** Verilen haftanın gününe ait bir sonraki tarihi bulur (1=Pzt ... 7=Paz). */
  function nextOccurrence(day, start) {
    var now = new Date();
    var jsDay = day % 7; // 7 (Pazar) -> 0
    var d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var delta = (jsDay - d.getDay() + 7) % 7;
    d.setDate(d.getDate() + delta);
    var hm = (start || "00:00").split(":").map(Number);
    d.setHours(hm[0] || 0, hm[1] || 0, 0, 0);
    if (d.getTime() < now.getTime()) d.setDate(d.getDate() + 7);
    return d;
  }

  function renderTraining() {
    var tr = state.training;
    var sessionsSlot = el("sessionsSlot");
    if (!tr || !(tr.sessions || []).length) {
      sessionsSlot.innerHTML = '<div class="empty">Antrenman programı girilmemiş.</div>';
      el("nextTrainingSlot").innerHTML = "";
      el("venuesSlot").innerHTML = "";
      return;
    }

    var today = new Date().getDay(); // 0=Pazar
    var sorted = tr.sessions.slice().sort(function (a, b) {
      return (a.day - b.day) || String(a.start).localeCompare(String(b.start));
    });

    var next = sorted.map(function (s) {
      return { s: s, when: nextOccurrence(s.day, s.start) };
    }).sort(function (a, b) { return a.when - b.when; })[0];

    if (next) {
      var v = venueOf(next.s.venue);
      el("nextTrainingSlot").innerHTML =
        '<div class="hero"><div class="label">Sıradaki Antrenman</div>' +
        '<div class="teams"><div class="team">' + esc(next.s.title || "Antrenman") + "</div></div>" +
        '<div class="meta"><span>📅 ' + esc(fmtDate(next.when)) + "</span>" +
        "<span>🕐 " + esc(next.s.start) + (next.s.end ? " - " + esc(next.s.end) : "") + "</span>" +
        (v ? "<span>📍 " + esc(v.name) + "</span>" : "") + "</div></div>";
    }

    sessionsSlot.innerHTML = sorted.map(function (s) {
      var v = venueOf(s.venue);
      var jsDay = s.day % 7;
      return '<div class="session' + (jsDay === today ? " today" : "") + '">' +
        '<div class="day"><div class="dn">' + esc(GUNLER[jsDay]) + "</div>" +
        (jsDay === today ? '<div class="badge">BUGÜN</div>' : "") + "</div>" +
        '<div><div class="tt">' + esc(s.title || "Antrenman") + "</div>" +
        '<div class="hh">🕐 ' + esc(s.start) + (s.end ? " - " + esc(s.end) : "") + "</div>" +
        '<div class="vv">📍 ' + (v ? esc(v.name) : esc(s.venue || "-")) +
        (v && v.maps ? ' · <a href="' + esc(v.maps) + '" target="_blank" rel="noopener">Yol tarifi</a>' : "") +
        (s.coach ? " · " + esc(s.coach) : "") + "</div></div></div>";
    }).join("");

    var exc = (tr.exceptions || []).filter(function (e) {
      return new Date(e.date + "T23:59:59") >= new Date();
    });
    el("venuesSlot").innerHTML =
      (tr.venues || []).map(function (v) {
        return '<div class="card"><div style="font-weight:700">' + esc(v.name) + "</div>" +
          '<div style="font-size:12.5px;color:var(--muted);margin-top:4px">' + esc(v.address || "") + "</div>" +
          (v.maps ? '<div style="margin-top:8px"><a href="' + esc(v.maps) +
            '" target="_blank" rel="noopener" style="color:var(--pink);font-weight:700;font-size:13px">Haritada aç →</a></div>' : "") +
          "</div>";
      }).join("") +
      (exc.length
        ? '<h2 class="section-title">Program Değişiklikleri</h2>' +
          exc.map(function (e) {
            return '<div class="banner"><span>ℹ️</span><div><b>' + esc(e.date) + "</b> · " +
              esc(e.type || "") + (e.reason ? " - " + esc(e.reason) : "") + "</div></div>";
          }).join("")
        : "");
  }

  // ---------------------------------------------------------------- sekmeler
  function showPanel(name) {
    ["maclar", "puan", "kadro", "antrenman"].forEach(function (p) {
      var panel = el("panel-" + p), tab = el("tab-" + p);
      if (!panel || !tab) return;
      var active = p === name;
      panel.hidden = !active;
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
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
      var name = btn.dataset.panel;
      location.hash = name;
      showPanel(name);
    });
  });

  document.addEventListener("click", function (ev) {
    var head = ev.target.closest && ev.target.closest(".match-head");
    if (!head || head.disabled) return;
    var id = head.getAttribute("aria-controls");
    var body = id && el(id);
    if (!body) return;
    var open = body.hidden;
    body.hidden = !open;
    head.setAttribute("aria-expanded", open ? "true" : "false");
    var chev = head.querySelector(".chev");
    if (chev) chev.textContent = open ? "▴" : "▾";
  });

  window.addEventListener("hashchange", function () {
    var name = location.hash.replace("#", "");
    if (["maclar", "puan", "kadro", "antrenman"].indexOf(name) !== -1) showPanel(name);
  });

  var initial = location.hash.replace("#", "");
  if (["maclar", "puan", "kadro", "antrenman"].indexOf(initial) !== -1) showPanel(initial);

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("sw.js").catch(function () { /* çevrimdışı desteği isteğe bağlı */ });
    });
  }

  boot();
})();
