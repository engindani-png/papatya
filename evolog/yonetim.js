/* Evolog U14 — antrenman programı yönetim ekranı.
 * Çözümleyici (parser.js) tahmin eder, bu ekran son sözü kullanıcıya bırakır.
 */
(function () {
  "use strict";

  var API = "/api";
  var GUNLER = ["", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];
  var KEY = "evolog_admin_pass";

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
      loadCurrent();
    }).catch(function (err) {
      pass = "";
      note("loginMsg", "bad", esc(err.message));
    }).then(function () { el("loginBtn").disabled = false; });
  }

  // --------------------------------------------------------------- yükleme
  function loadCurrent() {
    api("/training").then(function (data) {
      if (!data || !(data.sessions || []).length) return;
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
  function daySelect(value, onChange) {
    var s = document.createElement("select");
    for (var d = 1; d <= 7; d++) {
      var o = document.createElement("option");
      o.value = String(d); o.textContent = GUNLER[d];
      if (d === Number(value)) o.selected = true;
      s.appendChild(o);
    }
    s.addEventListener("change", function () { onChange(Number(s.value)); });
    return s;
  }

  function venueSelect(value, onChange) {
    var s = document.createElement("select");
    var none = document.createElement("option");
    none.value = ""; none.textContent = "— salon yok —";
    s.appendChild(none);
    state.venues.forEach(function (v) {
      var o = document.createElement("option");
      o.value = v.id; o.textContent = v.name;
      if (v.id === value) o.selected = true;
      s.appendChild(o);
    });
    s.addEventListener("change", function () { onChange(s.value || null); });
    return s;
  }

  // Saat girişi 24 saatlik. <input type="time"> cihazın diline göre AM/PM
  // gösterebiliyor; bu yüzden maskeli metin alanı kullanılıyor.
  function timeField(value, placeholder, onChange) {
    var i = document.createElement("input");
    i.type = "text";
    i.inputMode = "numeric";
    i.autocomplete = "off";
    i.maxLength = 5;
    i.pattern = "([01][0-9]|2[0-3]):[0-5][0-9]";
    i.value = value == null ? "" : value;
    i.placeholder = placeholder || "19:30";
    i.addEventListener("input", function () {
      var digits = i.value.replace(/\D/g, "").slice(0, 4);
      var out = digits.length > 2 ? digits.slice(0, 2) + ":" + digits.slice(2) : digits;
      if (out !== i.value) {
        var atEnd = i.selectionStart === i.value.length;
        i.value = out;
        if (atEnd) i.setSelectionRange(out.length, out.length);
      }
      onChange(out.length === 5 ? out : (out || null));
    });
    i.addEventListener("blur", function () {
      // "9" -> "09:00", "930" -> "09:30" gibi eksik girişleri tamamla.
      var d = i.value.replace(/\D/g, "");
      if (!d) { i.value = ""; onChange(null); i.classList.remove("bad"); return; }
      if (d.length <= 2) d = ("0" + d).slice(-2) + "00";
      else if (d.length === 3) d = "0" + d;
      var hh = Math.min(23, parseInt(d.slice(0, 2), 10));
      var mm = Math.min(59, parseInt(d.slice(2, 4), 10));
      var out = ("0" + hh).slice(-2) + ":" + ("0" + mm).slice(-2);
      i.value = out;
      i.classList.remove("bad");
      onChange(out);
    });
    return i;
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
      var del = document.createElement("button");
      del.className = "del"; del.title = "Sil"; del.textContent = "✕";
      del.addEventListener("click", function () {
        state.sessions.splice(i, 1); renderSessions(); mark(true);
      });
      head.appendChild(del);
      card.appendChild(head);

      var grid = document.createElement("div");
      grid.className = "grid";
      grid.appendChild(daySelect(s.day, function (v) { s.day = v; s.dayGuess = false; renderSessions(); mark(true); }));
      grid.appendChild(timeField(s.start, "Başlangıç 19:30", function (v) { s.start = v; mark(true); }));
      grid.appendChild(timeField(s.end, "Bitiş (isteğe bağlı)", function (v) { s.end = v; mark(true); }));
      grid.appendChild(venueSelect(s.venue, function (v) { s.venue = v; s.venueGuess = false; mark(true); }));
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
        state.venues.splice(i, 1); renderVenues(); renderSessions(); mark(true);
      });
      head.appendChild(del);
      card.appendChild(head);

      var grid = document.createElement("div");
      grid.className = "grid";
      var name = field("text", v.name, "Salon adı", function (val) { v.name = val; mark(true); });
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
    api("/training", {
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
      el("saveMsg").textContent = res.sessions + " antrenman kaydedildi. Uygulama birkaç saniyede güncellenir.";
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
