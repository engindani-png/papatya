/* Antrenör paneli sayfalarının ortak giriş/istek katmanı.
 *
 * Şifre sessionStorage'da durur (sekme kapanınca gider) ve her istekte
 * Authorization başlığıyla gönderilir. Asıl kontrol sunucuda; buradaki
 * giriş kutusu yalnızca şifreyi bir kez sormak için.
 */
window.EvologPanel = (function () {
  "use strict";

  var KEY = "evolog_admin_pass";
  var pass = "";
  try { pass = sessionStorage.getItem(KEY) || ""; } catch (e) { pass = ""; }

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function el(id) { return document.getElementById(id); }

  function note(where, kind, msg) {
    var box = el(where);
    if (box) box.innerHTML = '<div class="note ' + kind + '"><div>' + msg + "</div></div>";
  }

  function api(path, opts) {
    opts = opts || {};
    opts.headers = Object.assign({ "Content-Type": "application/json" },
      opts.headers || {}, pass ? { Authorization: "Bearer " + pass } : {});
    return fetch("/api" + path, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (body) {
        if (r.status === 401) { forget(); throw new Error("Şifre gerekli"); }
        if (!r.ok) throw new Error(body.error || ("Sunucu " + r.status));
        return body;
      });
    });
  }

  function forget() {
    pass = "";
    try { sessionStorage.removeItem(KEY); } catch (e) { /* özel sekme */ }
  }

  /** Giriş kutusunu yönetir; şifre doğrulanınca onReady() çağrılır. */
  function requireLogin(onReady) {
    var box = el("loginBox");
    var app = el("adminBox");

    function ac() {
      if (box) box.hidden = true;
      if (app) app.hidden = false;
      onReady();
    }

    function dene(deger) {
      pass = deger;
      return api("/auth", { method: "POST", body: "{}" }).then(function () {
        try { sessionStorage.setItem(KEY, pass); } catch (e) { /* özel sekme */ }
        ac();
        return true;
      });
    }

    if (el("loginBtn")) {
      el("loginBtn").addEventListener("click", function () {
        var deger = (el("pass").value || "").trim();
        if (!deger) return;
        el("loginBtn").disabled = true;
        dene(deger).catch(function (err) {
          note("loginMsg", "bad", esc(err.message));
        }).then(function () { el("loginBtn").disabled = false; });
      });
      el("pass").addEventListener("keydown", function (e) {
        if (e.key === "Enter") el("loginBtn").click();
      });
    }

    // Aynı oturumda daha önce girilmişse şifreyi tekrar sormayız.
    if (pass) dene(pass).catch(function () { /* geçersizmiş, kutu açık kalsın */ });
  }

  return { api: api, esc: esc, el: el, note: note, requireLogin: requireLogin, forget: forget };
})();
