/* Basit çevrimdışı önbellek: kabuk dosyaları önbellekten, veri dosyaları önce ağdan. */
// v37: daha once v36 kullanilmisti, sonra bir surum v31e DUSURULDU.
// Geriye gitmek karisiklik yaratiyor; bir daha ileri gidiyoruz ve
// buradan sonra HEP artar.
var CACHE = "evolog-v43";

// Gelen bildirimleri telefonda saklayan katman. sw.js ile app.js AYNI
// dosyayi kullanir; yazan ile okuyanin semasi ayrismasin diye.
importScripts("./duyuru-arsiv.js");
var SHELL = ["./", "./index.html", "./styles.css", "./skin.css", "./app.js", "./icon.svg", "./logo.png",
  "./icon-192.png", "./manifest.webmanifest",
  // Antrenor paneli: salonda sinyal zayif olabiliyor, o da cevrimdisi acilsin.
  "./panel.css", "./panel-auth.js", "./duyuru-arsiv.js",
  "./yonetim.html", "./yonetim.js", "./parser.js",
  "./yoklama.html", "./yoklama.js",
  "./oyuncular.html", "./oyuncular.js",
  "./macanaliz.html", "./macanaliz.js",
  "./duyuru.html", "./duyuru.js",
  "./rakip.html", "./rakip.js",
  "./panel-analiz.js"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () {
    return self.skipWaiting();
  }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    // CacheStorage KOKEN basinadir, servis calisani kapsami basina degil.
    // Ayni koken (evologsiyah.com) altinda /parke2/ adresinde Coach's
    // Playground kendi onbellegini ("parke2-vNN") tutuyor. Onek suzgeci
    // olmadan burada ONUN onbellegini de siliyorduk: Evolog her
    // guncellendiginde kocun CP'si cevrimdisi acilmaz hale geliyordu.
    // Yalnizca KENDI eski surumlerimizi sil.
    return Promise.all(keys.filter(function (k) {
      return k.indexOf("evolog-") === 0 && k !== CACHE;
    }).map(function (k) { return caches.delete(k); }));
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

  var baslik = d.title || "Şerifali Spor Kulübü U14 Kız Siyah";
  var goster = self.registration.showNotification(baslik, {
    body: d.body || "",
    tag: d.tag || "evolog",
    renotify: true,
    icon: "./icon-192.png",
    badge: "./icon-192.png",
    data: { url: d.url || "./" }
  });

  // GELEN HER BILDIRIM ARSIVE. Bildirim kapatilinca metin kayboluyordu;
  // mac sonucu / saat degisikligi / antrenman programi bildirimleri
  // sunucuda hic tutulmuyor, tek kopyasi buydu. Arsive yazma BASARISIZ
  // olsa bile bildirim gosterilmeli, o yuzden hata yutuluyor.
  var arsivle = Promise.resolve();
  if (self.EvologArsiv) {
    arsivle = self.EvologArsiv
      .yaz(self.EvologArsiv.kayitYap({ tag: d.tag, title: baslik, body: d.body, url: d.url }))
      .then(haberVer)
      .catch(function () { /* depolama kapali olabilir; bildirim yine gider */ });
  }

  e.waitUntil(Promise.all([goster, arsivle]));
});

/** Uygulama ACIKKEN gelen bildirim: liste ve rozet aninda tazelensin. */
function haberVer() {
  return self.clients.matchAll({ type: "window", includeUncontrolled: true })
    .then(function (list) {
      list.forEach(function (c) {
        try { c.postMessage({ tip: "duyuru-geldi" }); } catch (err) { /* onemsiz */ }
      });
    });
}

self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var url = (e.notification.data && e.notification.data.url) || "./";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true })
    .then(function (list) {
      // Uygulama artik KOK adreste (evologsiyah.com). Eski kontrol
      // url.indexOf("/evolog/") hicbir zaman tutmuyordu, bu yuzden bildirime
      // her dokunusta YENI pencere aciliyordu. Kapsam (scope) ile karsilastir.
      var kapsam = self.registration.scope;
      for (var i = 0; i < list.length; i++) {
        if (list[i].url.indexOf(kapsam) === 0 && "focus" in list[i]) {
          if ("navigate" in list[i]) { try { list[i].navigate(url); } catch (err) { /* onemsiz */ } }
          return list[i].focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    }));
});
