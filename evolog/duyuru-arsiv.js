/* Gelen bildirimlerin TELEFONDAKI arsivi.
 *
 * NEDEN: bildirim kapatilinca metin kayboluyordu. Sunucuda yalnizca
 * antrenorun elle yazdigi duyurular duruyor; mac sonucu, mac saati
 * degisikligi ve antrenman programi bildirimleri hicbir yerde kalmiyordu.
 * Artik servis calisani gelen HER push'u once buraya yaziyor, sonra
 * bildirimi gosteriyor.
 *
 * Neden IndexedDB: servis calisaninda localStorage yok.
 *
 * Bu dosya iki yerden yuklenir ve ikisinde de ayni arayuzu verir:
 *   sw.js    -> importScripts("./duyuru-arsiv.js")
 *   index.html -> <script src="duyuru-arsiv.js"> (app.js'ten ONCE)
 * Tek kopya olmasinin sebebi: yazan ile okuyanin sema konusunda
 * anlasmazliga dusmesi sessiz veri kaybi demek.
 */
(function (kok) {
  "use strict";

  var DB_ADI = "evolog-duyuru";
  var DEPO = "kayit";
  // Telefonda sinirsiz birikmesin. 120 kayit ~ iki sezonluk bildirim.
  var SINIR = 120;

  function ac() {
    return new Promise(function (ok, hata) {
      if (!kok.indexedDB) return hata(new Error("IndexedDB yok"));
      var istek = kok.indexedDB.open(DB_ADI, 1);
      istek.onupgradeneeded = function () {
        var db = istek.result;
        if (!db.objectStoreNames.contains(DEPO)) {
          db.createObjectStore(DEPO, { keyPath: "id" });
        }
      };
      istek.onsuccess = function () { ok(istek.result); };
      istek.onerror = function () { hata(istek.error); };
      // Ozel sekmede ya da depolama kapaliyken acilis hic sonuclanmayabilir.
      istek.onblocked = function () { hata(new Error("IndexedDB engellendi")); };
    });
  }

  function islem(mod, is) {
    return ac().then(function (db) {
      return new Promise(function (ok, hata) {
        var tx = db.transaction(DEPO, mod);
        var depo = tx.objectStore(DEPO);
        var sonuc;
        try { sonuc = is(depo); } catch (e) { hata(e); return; }
        tx.oncomplete = function () { db.close(); ok(sonuc && sonuc.result !== undefined ? sonuc.result : sonuc); };
        tx.onerror = function () { db.close(); hata(tx.error); };
        tx.onabort = function () { db.close(); hata(tx.error); };
      });
    });
  }

  /** Bildirimden arsiv kaydi uretir. Kimlik: etiket + zaman.
   *  Ayni etiketle (ornegin ayni macin) yeni bildirim GELIRSE ayri kayit olur;
   *  "mac saati degisti" iki kez gelirse veli ikisini de gormeli. */
  function kayitYap(d, zaman) {
    var etiket = String((d && d.tag) || "bildirim");
    var z = zaman || new Date().toISOString();
    return {
      id: etiket + "|" + z,
      etiket: etiket,
      baslik: String((d && d.title) || ""),
      metin: String((d && d.body) || ""),
      url: String((d && d.url) || "./"),
      zaman: z,
      kaynak: "yerel"
    };
  }

  /** Bildirimi arsive yazar ve sinirin ustundeki en eskileri siler. */
  function yaz(kayit) {
    if (!kayit || !kayit.id) return Promise.resolve(null);
    return islem("readwrite", function (depo) { depo.put(kayit); })
      .then(buda)
      .then(function () { return kayit; });
  }

  function buda() {
    return hepsi().then(function (liste) {
      if (liste.length <= SINIR) return null;
      var fazla = liste.slice(SINIR);   // hepsi() yeniden eskiye sirali
      return islem("readwrite", function (depo) {
        fazla.forEach(function (k) { depo.delete(k.id); });
      });
    });
  }

  /** Tum kayitlar, YENIDEN ESKIYE. */
  function hepsi() {
    return islem("readonly", function (depo) { return depo.getAll(); })
      .then(function (liste) {
        liste = liste || [];
        liste.sort(function (a, b) {
          return String(b.zaman || "").localeCompare(String(a.zaman || ""));
        });
        return liste;
      })
      .catch(function () { return []; });   // depolama kapali: arsiv bos gorunur
  }

  function sil(id) {
    if (!id) return Promise.resolve(false);
    return islem("readwrite", function (depo) { depo.delete(id); })
      .then(function () { return true; })
      .catch(function () { return false; });
  }

  /** Bir etiketin TUM kayitlarini siler (sunucudaki ayni duyuru silinince
   *  telefondaki push kopyasi geride kalmasin). */
  function etiketiSil(etiket) {
    if (!etiket) return Promise.resolve(0);
    return hepsi().then(function (liste) {
      var hedef = liste.filter(function (k) { return k.etiket === etiket; });
      if (!hedef.length) return 0;
      return islem("readwrite", function (depo) {
        hedef.forEach(function (k) { depo.delete(k.id); });
      }).then(function () { return hedef.length; }).catch(function () { return 0; });
    });
  }

  kok.EvologArsiv = {
    kayitYap: kayitYap,
    yaz: yaz,
    hepsi: hepsi,
    sil: sil,
    etiketiSil: etiketiSil,
    SINIR: SINIR
  };
})(typeof self !== "undefined" ? self : this);
