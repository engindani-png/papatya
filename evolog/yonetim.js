/* Evolog U14 — antrenman programı yönetim ekranı.
 * Çözümleyici (parser.js) tahmin eder, bu ekran son sözü kullanıcıya bırakır.
 */
(function () {
  "use strict";

  var API = "/api";
  var GUNLER = ["", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];
  var KISA = ["", "Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
  var KEY = "evolog_admin_pass";

  // Uygulamayla ayni secimi paylasiyoruz: yonetimde takim degistirilince
  // uygulama da o takimla aciliyor.
  var AGES = [
    { key: "u14", title: "U14 Kızlar" },
    { key: "u16", title: "U16 Kızlar" },
    { key: "u18", title: "U18 Kızlar" }
  ];
  var AGE_STORE = "evolog.age";

  function knownAge(key) {
    for (var i = 0; i < AGES.length; i++) if (AGES[i].key === key) return key;
    return null;
  }

  var age = null;
  try { age = knownAge(localStorage.getItem(AGE_STORE)); } catch (e) { /* depolama yok */ }
  age = age || AGES[0].key;

  var state = { venues: [], sessions: [], exceptions: [], matches: [] };
  var pass = "";
  var dirty = false;

  function el(id) { return document.getElementById(id); }
  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function note(where, kind, msg) {
    el(where).innerHTML = '<div class="note ' + kind + '"><div>' + msg + "</div></div>";
  }
  function mark(changed) {
    dirty = changed;
    el("saveMsg").textContent = changed
      ? "Kaydedilmemiş değişiklik var."
      : "Tüm değişiklikler kaydedildi.";
  }

  function api(path, opts) {
    opts = opts || {};
    opts.headers = Object.assign({ "Content-Type": "application/json" },
      opts.headers || {}, pass ? { Authorization: "Bearer " + pass } : {});
    return fetch(API + path, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (body) {
        if (!r.ok) throw new Error(body.error || ("Sunucu " + r.status));
        return body;
      });
    });
  }

  // ------------------------------------------------------------------ giriş
  function login() {
    var value = el("pass").value.trim();
    if (!value) return;
    pass = value;
    el("loginBtn").disabled = true;
    api("/auth", { method: "POST", body: "{}" }).then(function () {
      try { sessionStorage.setItem(KEY, pass); } catch (e) { /* özel sekme */ }
      el("loginBox").hidden = true;
      el("adminBox").hidden = false;
      el("bar").hidden = false;
      renderTeamStrip();
      loadCurrent();
    }).catch(function (err) {
      pass = "";
      note("loginMsg", "bad", esc(err.message));
    }).then(function () { el("loginBtn").disabled = false; });
  }

  // --------------------------------------------------------------- yükleme
  function renderTeamStrip() {
    var box = el("teamStrip");
    box.innerHTML = "";
    AGES.forEach(function (a) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = a.title;
      b.setAttribute("aria-pressed", a.key === age ? "true" : "false");
      b.addEventListener("click", function () { switchAge(a.key); });
      box.appendChild(b);
    });
  }

  // Kaydedilmemis degisiklikle takim degistirmek veri kaybettirir; onun
  // yerine uyariyoruz (tarayici penceresi acmadan).
  function switchAge(key) {
    if (key === age || !knownAge(key)) return;
    if (dirty) {
      note("parseMsg", "bad", "Önce kaydedin ya da <b>Kayıtlıyı getir</b> ile vazgeçin; " +
        "sonra takımı değiştirin.");
      window.scrollTo(0, 0);
      return;
    }
    age = key;
    try { localStorage.setItem(AGE_STORE, age); } catch (e) { /* yoksay */ }
    state.venues = []; state.sessions = []; state.exceptions = []; state.matches = [];
    renderTeamStrip();
    renderAll();
    el("parseMsg").innerHTML = "";
    loadCurrent();
  }

  function loadCurrent() {
    api("/training?age=" + age).then(function (data) {
      if (!data || !(data.sessions || []).length) { renderAll(); mark(false); return; }
      state.venues = data.venues || [];
      state.sessions = (data.sessions || []).map(function (s) {
        return Object.assign({}, s, { kind: s.kind || "basket" });
      });
      state.exceptions = data.exceptions || [];
      renderAll();
      mark(false);
    }).catch(function () { /* henüz kayıt yok, boş başla */ });
  }

  // -------------------------------------------------------------- çözümleme
  function doParse() {
    var text = el("raw").value;
    if (!text.trim()) { note("parseMsg", "bad", "Önce mesajı yapıştırın."); return; }

    var r = EvologParse.parse(text, state.venues);

    // Yeni salonları mevcut listeye ekle (aynı id varsa dokunma).
    r.venues.forEach(function (v) {
      if (!state.venues.some(function (x) { return x.id === v.id; })) {
        state.venues.push({ id: v.id, name: v.name, address: null, maps: null, color: v.color });
      }
    });

    state.sessions = r.sessions;
    state.matches = r.matches;
    // Yeni gelen istisnaları mevcutlarla birleştir (aynı tarih tekrar etmesin).
    r.exceptions.forEach(function (e) {
      if (!state.exceptions.some(function (x) { return x.date === e.date; })) state.exceptions.push(e);
    });

    var parts = ["<b>" + r.sessions.length + " antrenman</b> çözümlendi"];
    if (r.matches.length) parts.push(r.matches.length + " maç satırı ayrıldı");
    if (r.exceptions.length) parts.push(r.exceptions.length + " iptal/değişiklik bulundu");
    var kind = "ok";
    var extra = "";
    if (r.unparsed.length) {
      kind = "";
      extra = "<br><b>Anlaşılmayan satırlar</b> — bunları elle ekleyin:<br>" +
        r.unparsed.map(function (u) {
          return "· " + esc(u.line) + " <span class=\"pill\">" + esc(u.why) + "</span>";
        }).join("<br>");
    }
    note("parseMsg", kind, parts.join(", ") + "." + extra);

    renderAll();
    mark(true);
  }

  // ----------------------------------------------------------------- çizim
  // Gun: yatay serit, dokun-sec. Acilir liste yok.
  function dayStrip(value, onChange) {
    var box = document.createElement("div");
    box.className = "days full";
    for (var d = 1; d <= 7; d++) {
      (function (day) {
        var b = document.createElement("button");
        b.type = "button";
        b.textContent = KISA[day];
        b.setAttribute("aria-label", GUNLER[day]);
        b.setAttribute("aria-pressed", day === Number(value) ? "true" : "false");
        b.addEventListener("click", function () { onChange(day); });
        box.appendChild(b);
      })(d);
    }
    return box;
  }

  // --------------------------------------------------- saat tekerlegi
  var ITEM = 38;          // .wheel .wi yuksekligi (styles ile ayni olmali)
  var HOURS = [];
  for (var h = 6; h <= 23; h++) HOURS.push(("0" + h).slice(-2));
  var STEPS = ["00", "15", "30", "45"];
  var timeTarget = null;  // { get, set, allowEmpty }

  function wheelFill(box, values, current) {
    box.innerHTML = '<div class="wpad"></div>' +
      values.map(function (v) { return '<div class="wi">' + v + "</div>"; }).join("") +
      '<div class="wpad"></div>';
    var at = values.indexOf(current);
    if (at < 0) at = 0;
    box.scrollTop = at * ITEM;
    wheelMark(box);
  }

  function wheelIndex(box) {
    return Math.max(0, Math.round(box.scrollTop / ITEM));
  }

  function wheelMark(box) {
    var items = box.querySelectorAll(".wi");
    var at = wheelIndex(box);
    for (var i = 0; i < items.length; i++) {
      if (i === at) items[i].classList.add("on");
      else items[i].classList.remove("on");
    }
  }

  function wheelValue(box, values) {
    return values[Math.min(values.length - 1, wheelIndex(box))];
  }

  function minutesFor(mm) {
    // Kayitli saat 15'lik adimda degilse (orn. 18:20) kaybolmasin diye eklenir.
    var list = STEPS.slice();
    if (mm && list.indexOf(mm) === -1) {
      list.push(mm);
      list.sort();
    }
    return list;
  }

  var minuteList = STEPS.slice();

  function openTime(title, value, allowEmpty, onPick) {
    var parts = /^(\d{2}):(\d{2})$/.exec(value || "");
    var hh = parts ? parts[1] : "19";
    var mm = parts ? parts[2] : "00";
    minuteList = minutesFor(mm);
    timeTarget = { onPick: onPick, allowEmpty: allowEmpty };
    el("timeTitle").textContent = title;
    wheelFill(el("wheelH"), HOURS, hh);
    wheelFill(el("wheelM"), minuteList, mm);
    el("timeSheet").hidden = false;
  }

  function closeTime() {
    el("timeSheet").hidden = true;
    timeTarget = null;
  }

  // Saat/salon dugmesi: uzerinde etiket ve secili deger yazar.
  function pickButton(label, value, placeholder, onOpen) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "pickbtn";
    b.innerHTML = '<span><span class="lbl">' + esc(label) + '</span>' +
      '<span class="val' + (value ? "" : " empty") + '">' +
      esc(value || placeholder) + "</span></span><span>›</span>";
    b.addEventListener("click", onOpen);
    return b;
  }

  function timeButton(label, value, placeholder, allowEmpty, onChange) {
    return pickButton(label, value, placeholder, function () {
      openTime(label, value, allowEmpty, onChange);
    });
  }

  // --------------------------------------------------------- salon secimi
  var venueTarget = null;

  function venueName(id) {
    for (var i = 0; i < state.venues.length; i++) {
      if (state.venues[i].id === id) return state.venues[i].name;
    }
    return null;
  }

  function renderVenueList() {
    var box = el("venueList");
    box.innerHTML = "";
    var current = venueTarget ? venueTarget.value : null;

    var none = document.createElement("button");
    none.type = "button";
    none.setAttribute("aria-checked", current ? "false" : "true");
    none.innerHTML = "<span>— salon yok —</span><span>" + (current ? "" : "✓") + "</span>";
    none.addEventListener("click", function () { pickVenue(null); });
    box.appendChild(none);

    state.venues.forEach(function (v) {
      var b = document.createElement("button");
      b.type = "button";
      var on = v.id === current;
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.innerHTML = '<span style="display:flex;align-items:center;gap:.55rem">' +
        '<span class="dot2" style="background:' + esc(v.color || "#f2a03d") + '"></span>' +
        esc(v.name) + "</span><span>" + (on ? "✓" : "") + "</span>";
      b.addEventListener("click", function () { pickVenue(v.id); });
      box.appendChild(b);
    });

    var add = document.createElement("button");
    add.type = "button";
    add.className = "add";
    add.innerHTML = "<span>+ Yeni salon</span><span></span>";
    add.addEventListener("click", function () {
      var v = {
        id: "salon-" + (Date.now().toString(36)),
        name: "Yeni salon", address: null, maps: null,
        color: EvologParse.COLORS[state.venues.length % EvologParse.COLORS.length]
      };
      state.venues.push(v);
      renderVenues();
      pickVenue(v.id);
    });
    box.appendChild(add);
  }

  function pickVenue(id) {
    if (venueTarget) venueTarget.onPick(id);
    el("venueSheet").hidden = true;
    venueTarget = null;
  }

  function openVenue(value, onPick) {
    venueTarget = { value: value, onPick: onPick };
    renderVenueList();
    el("venueSheet").hidden = false;
  }

  function field(type, value, placeholder, onChange) {
    var i = document.createElement("input");
    i.type = type; i.value = value == null ? "" : value;
    if (placeholder) i.placeholder = placeholder;
    i.addEventListener("input", function () { onChange(i.value.trim() || null); });
    return i;
  }

  function renderSessions() {
    var box = el("sessions");
    box.innerHTML = "";
    if (!state.sessions.length) {
      box.innerHTML = '<div class="note"><div>Henüz antrenman yok. Mesajı çözümleyin ya da elle satır ekleyin.</div></div>';
      return;
    }
    state.sessions.forEach(function (s, i) {
      var card = document.createElement("div");
      card.className = "card";

      var head = document.createElement("div");
      head.className = "head";
      head.innerHTML = "<strong>" + esc(GUNLER[s.day] || "?") + " · " + esc(s.start) + "</strong>" +
        (s.dayGuess ? '<span class="pill guess">gün devralındı</span>' : "") +
        (s.venueGuess ? '<span class="pill guess">salon tahmin</span>' : "");
      var copy = document.createElement("button");
      copy.className = "copy"; copy.title = "Bu seansı kopyala"; copy.textContent = "⧉";
      copy.style.marginLeft = "auto";
      copy.addEventListener("click", function () {
        var next = Object.assign({}, s, { day: s.day >= 7 ? 1 : s.day + 1, src: null });
        state.sessions.splice(i + 1, 0, next);
        renderSessions(); mark(true);
      });
      head.appendChild(copy);

      var del = document.createElement("button");
      del.className = "del"; del.title = "Sil"; del.textContent = "✕";
      del.addEventListener("click", function () {
        state.sessions.splice(i, 1); renderSessions(); mark(true);
      });
      head.appendChild(del);
      card.appendChild(head);

      var grid = document.createElement("div");
      grid.className = "grid";
      grid.appendChild(dayStrip(s.day, function (v) {
        s.day = v; s.dayGuess = false; renderSessions(); mark(true);
      }));

      var row = document.createElement("div");
      row.className = "pickrow full";
      row.appendChild(timeButton("Başlangıç", s.start, "Seçin", false, function (v) {
        s.start = v; renderSessions(); mark(true);
      }));
      row.appendChild(timeButton("Bitiş", s.end, "İsteğe bağlı", true, function (v) {
        s.end = v; renderSessions(); mark(true);
      }));
      grid.appendChild(row);

      var vbtn = pickButton("Salon", venueName(s.venue), "Seçin", function () {
        openVenue(s.venue, function (id) {
          s.venue = id; s.venueGuess = false; renderSessions(); mark(true);
        });
      });
      vbtn.classList.add("full");
      grid.appendChild(vbtn);

      var title = field("text", s.title, "İçerik (Basketbol / Kuvvet …)", function (v) { s.title = v; mark(true); });
      title.className = "full";
      grid.appendChild(title);
      card.appendChild(grid);

      if (s.src) card.innerHTML += '<div class="src">Kaynak: ' + esc(s.src) + "</div>";
      box.appendChild(card);
    });
  }

  function renderMatches() {
    var box = el("parseMsg");
    if (!state.matches.length) return;
    var html = '<div class="note"><div><b>Mesajdaki maç satırları</b> (programa yazılmaz — ' +
      "maçlar zaten TBF'den geliyor):<br>" +
      state.matches.map(function (m) {
        return "· " + esc(GUNLER[m.day]) + " " + esc(m.start) + " — " + esc(m.note || "");
      }).join("<br>") + "</div></div>";
    box.insertAdjacentHTML("beforeend", html);
  }

  function renderExceptions() {
    var box = el("exceptions");
    box.innerHTML = "";
    if (!state.exceptions.length) {
      box.innerHTML = '<div class="note"><div>Program değişikliği yok.</div></div>';
      return;
    }
    state.exceptions.forEach(function (e, i) {
      var card = document.createElement("div");
      card.className = "card";
      var head = document.createElement("div");
      head.className = "head";
      head.innerHTML = "<strong>" + esc(e.date) + "</strong>" +
        (e.guess ? '<span class="pill guess">tarih tahmin</span>' : "");
      var del = document.createElement("button");
      del.className = "del"; del.textContent = "✕";
      del.addEventListener("click", function () {
        state.exceptions.splice(i, 1); renderExceptions(); mark(true);
      });
      head.appendChild(del);
      card.appendChild(head);

      var grid = document.createElement("div");
      grid.className = "grid";
      grid.appendChild(field("date", e.date, "Tarih", function (v) { e.date = v; e.guess = false; mark(true); }));
      grid.appendChild(field("text", e.type, "Tür (iptal / tatil)", function (v) { e.type = v; mark(true); }));
      var reason = field("text", e.reason, "Açıklama", function (v) { e.reason = v; mark(true); });
      reason.className = "full";
      grid.appendChild(reason);
      card.appendChild(grid);
      box.appendChild(card);
    });
  }

  function renderVenues() {
    var box = el("venues");
    box.innerHTML = "";
    if (!state.venues.length) {
      box.innerHTML = '<div class="note"><div>Salon yok.</div></div>';
      return;
    }
    state.venues.forEach(function (v, i) {
      var used = state.sessions.some(function (s) { return s.venue === v.id; });
      var card = document.createElement("div");
      card.className = "card";
      var head = document.createElement("div");
      head.className = "head";
      head.innerHTML = '<span class="swatch" style="background:' + esc(v.color || "#f2a03d") + '"></span>' +
        "<strong>" + esc(v.name) + "</strong>" +
        (used ? "" : '<span class="pill">kullanılmıyor</span>');
      var del = document.createElement("button");
      del.className = "del"; del.textContent = "✕";
      del.addEventListener("click", function () {
        state.venues.splice(i, 1); renderVenues(); renderSessions();
        if (!el("venueSheet").hidden) renderVenueList();
        mark(true);
      });
      head.appendChild(del);
      card.appendChild(head);

      var grid = document.createElement("div");
      grid.className = "grid";
      var name = field("text", v.name, "Salon adı", function (val) {
        v.name = val; renderSessions(); mark(true);
      });
      name.className = "full";
      grid.appendChild(name);
      var addr = field("text", v.address, "Adres (ilçe / İstanbul)", function (val) { v.address = val; mark(true); });
      addr.className = "full";
      grid.appendChild(addr);
      var maps = field("url", v.maps, "Google Haritalar bağlantısı (isteğe bağlı)", function (val) { v.maps = val; mark(true); });
      maps.className = "full";
      grid.appendChild(maps);

      // Salon rengi: programda bir bakışta ayırt etmek için.
      var colorWrap = document.createElement("label");
      colorWrap.className = "full colorrow";
      colorWrap.innerHTML = "<span>Salon rengi</span>";
      var color = document.createElement("input");
      color.type = "color";
      color.value = v.color || "#f2a03d";
      color.addEventListener("input", function () { v.color = color.value; mark(true); });
      colorWrap.appendChild(color);
      grid.appendChild(colorWrap);
      card.appendChild(grid);
      box.appendChild(card);
    });
  }

  function renderAll() {
    renderSessions();
    renderExceptions();
    renderVenues();
    renderMatches();
  }

  // ---------------------------------------------------------------- kaydet
  function save() {
    var bad = state.sessions.filter(function (s) {
      return !s.start || !/^([01]?\d|2[0-3]):[0-5]\d$/.test(s.start) || !(s.day >= 1 && s.day <= 7);
    });
    if (bad.length) {
      note("parseMsg", "bad", bad.length + " satırda gün ya da saat eksik. Düzeltip tekrar deneyin.");
      window.scrollTo(0, 0);
      return;
    }
    el("saveBtn").disabled = true;
    el("saveMsg").textContent = "Kaydediliyor…";
    api("/training?age=" + age, {
      method: "POST",
      body: JSON.stringify({
        venues: state.venues,
        sessions: state.sessions.map(function (s) {
          return { day: s.day, start: s.start, end: s.end, venue: s.venue, title: s.title, coach: s.coach };
        }),
        exceptions: state.exceptions
      })
    }).then(function (res) {
      mark(false);
      el("saveMsg").textContent = res.sessions + " antrenman kaydedildi (" +
        (knownAge(res.age) || age).toUpperCase() + "). Uygulama birkaç saniyede güncellenir.";
    }).catch(function (err) {
      el("saveMsg").textContent = "Kaydedilemedi: " + err.message;
    }).then(function () { el("saveBtn").disabled = false; });
  }

  // ------------------------------------------------------------------ bağla
  el("loginBtn").addEventListener("click", login);
  el("pass").addEventListener("keydown", function (e) { if (e.key === "Enter") login(); });
  el("parseBtn").addEventListener("click", doParse);
  el("saveBtn").addEventListener("click", save);
  el("reloadBtn").addEventListener("click", loadCurrent);

  // Saat tekerlegi: kaydirinca ortadaki satir vurgulanir.
  ["wheelH", "wheelM"].forEach(function (id) {
    el(id).addEventListener("scroll", function () { wheelMark(el(id)); }, { passive: true });
  });
  el("timeCancel").addEventListener("click", closeTime);
  el("timeSheet").addEventListener("click", function (ev) {
    if (ev.target === el("timeSheet")) closeTime();
  });
  el("timeOk").addEventListener("click", function () {
    if (!timeTarget) return closeTime();
    var value = wheelValue(el("wheelH"), HOURS) + ":" + wheelValue(el("wheelM"), minuteList);
    var pick = timeTarget.onPick;
    closeTime();
    pick(value);
  });
  el("venueCancel").addEventListener("click", function () {
    el("venueSheet").hidden = true; venueTarget = null;
  });
  el("venueSheet").addEventListener("click", function (ev) {
    if (ev.target === el("venueSheet")) { el("venueSheet").hidden = true; venueTarget = null; }
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    if (!el("timeSheet").hidden) closeTime();
    if (!el("venueSheet").hidden) { el("venueSheet").hidden = true; venueTarget = null; }
  });

  el("addBtn").addEventListener("click", function () {
    state.sessions.push({ day: 1, start: "19:00", end: null, title: "Basketbol", kind: "basket", venue: null });
    renderSessions(); mark(true);
  });
  el("addExcBtn").addEventListener("click", function () {
    var d = new Date();
    state.exceptions.push({
      date: d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2),
      type: "iptal", reason: ""
    });
    renderExceptions(); mark(true);
  });
  el("addVenueBtn").addEventListener("click", function () {
    state.venues.push({
      id: "salon-" + (state.venues.length + 1), name: "Yeni salon", address: null, maps: null,
      color: EvologParse.COLORS[state.venues.length % EvologParse.COLORS.length]
    });
    renderVenues(); mark(true);
  });

  window.addEventListener("beforeunload", function (e) {
    if (dirty) { e.preventDefault(); e.returnValue = ""; }
  });

  // Oturum boyunca şifreyi hatırla (sekme kapanınca silinir).
  try {
    var saved = sessionStorage.getItem(KEY);
    if (saved) { el("pass").value = saved; login(); }
  } catch (e) { /* yoksay */ }
})();
