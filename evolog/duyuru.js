/* Antrenörün velilere serbest metin bildirimi göndermesi.
 *
 * Gönderim sunucuda `evolog_push.py --duyuru` ile yapılıyor (bildirim
 * göndericisi ayrı sanal ortamda çalışıyor, bkz. deploy/README.md).
 * Gönderilen her duyuru veritabanına yazılır; aşağıdaki liste oradan gelir.
 */
(function () {
  "use strict";

  var P = window.EvologPanel;
  var AGE = "u14";

  function el(id) { return document.getElementById(id); }
  function esc(v) { return P.esc(v); }

  function onizle() {
    var baslik = (el("baslik").value || "").trim() || "Antrenörden duyuru";
    var metin = (el("metin").value || "").trim();
    el("sayac").textContent = (el("metin").value || "").length + " / 280";
    el("onizleme").innerHTML =
      '<div class="b">U14 · ' + esc(baslik) + "</div>" +
      '<div class="m">' + (metin ? esc(metin) : "Mesajınız burada görünecek.") + "</div>" +
      '<div class="u">Telefonda bildirim olarak böyle görünür</div>';
    el("gonderBtn").disabled = metin.length < 3;
  }

  function gecmisiYukle() {
    return P.api("/duyuru?age=" + AGE).then(function (res) {
      var liste = res.duyurular || [];
      el("gecmis").innerHTML = liste.length
        ? liste.map(function (d) {
            var z = String(d.zaman || "").replace("T", " ").slice(0, 16);
            return '<div class="k"><div class="ust"><span class="ad">' + esc(d.baslik) + "</span>" +
              '<span class="z">' + esc(z) + " · " + (d.gonderim || 0) + " kişi</span></div>" +
              '<div class="m">' + esc(d.metin) + "</div></div>";
          }).join("")
        : '<p class="hint">Henüz duyuru gönderilmedi.</p>';
    }).catch(function () {
      el("gecmis").innerHTML = '<p class="hint">Geçmiş okunamadı.</p>';
    });
  }

  function gonder() {
    var baslik = (el("baslik").value || "").trim();
    var metin = (el("metin").value || "").trim();
    if (metin.length < 3) return;
    el("gonderBtn").disabled = true;
    P.note("mesaj", "", "Gönderiliyor…");
    P.api("/duyuru?age=" + AGE, {
      method: "POST",
      body: JSON.stringify({ title: baslik, body: metin })
    }).then(function (res) {
      if (res.gonderim) {
        P.note("mesaj", "ok", "<b>Gönderildi.</b> " + res.gonderim +
          " veliye ulaştı. Bildirimi kapalı olanlar görmez.");
        el("metin").value = "";
        el("baslik").value = "";
        onizle();
      } else {
        P.note("mesaj", "bad", "Duyuru kaydedildi ama <b>kimseye ulaşmadı</b>: " +
          "şu an bildirimi açık veli yok.");
      }
      gecmisiYukle();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }).catch(function (err) {
      P.note("mesaj", "bad", esc(err.message));
    }).then(function () { el("gonderBtn").disabled = false; });
  }

  document.addEventListener("input", function (ev) {
    if (ev.target.id === "metin" || ev.target.id === "baslik") onizle();
  });
  document.addEventListener("click", function (ev) {
    if (!ev.target.closest) return;
    if (ev.target.closest("#gonderBtn")) gonder();
    if (ev.target.closest("#temizleBtn")) {
      el("metin").value = ""; el("baslik").value = ""; onizle();
      el("mesaj").innerHTML = "";
    }
  });

  P.requireLogin(function () {
    onizle();
    gecmisiYukle();
  });
})();
