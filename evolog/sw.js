/* Basit çevrimdışı önbellek: kabuk dosyaları önbellekten, veri dosyaları önce ağdan. */
var CACHE = "evolog-v24";
var SHELL = ["./", "./index.html", "./styles.css", "./app.js", "./icon.svg", "./logo.png",
  "./icon-192.png", "./manifest.webmanifest",
  // Antrenor paneli: salonda sinyal zayif olabiliyor, o da cevrimdisi acilsin.
  "./panel.css", "./panel-auth.js",
  "./yonetim.html", "./yonetim.js", "./parser.js",
  "./yoklama.html", "./yoklama.js",
  "./oyuncular.html", "./oyuncular.js",
  "./macanaliz.html", "./macanaliz.js",
  "./duyuru.html", "./duyuru.js",
  "./rakip.html", "./rakip.js"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () {
    return self.skipWaiting();
  }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; })
      .map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  if (e.request.method !== "GET") return;
  // API'ye hic karisma: oturum cerezi, kaydetme ve taze veri gerektiriyor.
  // (Onbellege alinirsa antrenor kaydettigi programi eski haliyle gorur.)
  if (e.request.url.indexOf("/api/") !== -1) return;
  var isData = e.request.url.indexOf("/data/") !== -1;

  if (isData) {
    // Veri: önce ağ, başarısızsa önbellekteki son kopya (sahada internet zayıf olabilir).
    e.respondWith(
      fetch(e.request).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(e.request, copy); });
        return res;
      }).catch(function () { return caches.match(e.request); })
    );
    return;
  }

  // Kabuk: internet varsa once agdan (eski surum ekranda kalmasin), 3 saniye
  // icinde yanit gelmezse onbellekten. Salonda sinyal zayifken uygulama yine
  // aninda aciliyor; evde ise her acilis guncel surumu gosteriyor.
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then(function (hit) {
    var net = fetch(e.request).then(function (res) {
      if (res && res.ok) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(e.request, copy); });
      }
      return res;
    });
    if (!hit) return net;
    return Promise.race([
      net.catch(function () { return hit; }),
      new Promise(function (ok) { setTimeout(function () { ok(hit); }, 3000); })
    ]);
  }));
});

/* ------------------------------------------------------------- bildirimler */
self.addEventListener("push", function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = {}; }
  // Bildirim, uygulamayi acmadan yeni surumu indirmek icin de bir firsat:
  // telefon zaten uyandi, sw.js'i tazeleyip guncellemeyi hazir ediyoruz.
  try { self.registration.update(); } catch (err) { /* onemsiz */ }
  e.waitUntil(self.registration.showNotification(d.title || "Evolog U14 Kız Siyah", {
    body: d.body || "",
    tag: d.tag || "evolog",
    renotify: true,
    icon: "./icon-192.png",
    badge: "./icon-192.png",
    data: { url: d.url || "./" }
  }));
});

self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var url = (e.notification.data && e.notification.data.url) || "./";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true })
    .then(function (list) {
      for (var i = 0; i < list.length; i++) {
        if (list[i].url.indexOf("/evolog/") !== -1 && "focus" in list[i]) return list[i].focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    }));
});
