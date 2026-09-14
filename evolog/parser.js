/* Evolog U14 — WhatsApp antrenman mesajı çözümleyici.
 *
 * Gerçek mesajlar şu kalıpta geliyor: gün adı kendi satırında, altındaki
 * satırlarda "saat · içerik · salon". Ama her hafta aynı düzende gelmiyor;
 * bu yüzden çözümleyici tahmin ettiği her alanı işaretler, karar veremediği
 * satırı "anlaşılmadı" diye ayırır ve son sözü kullanıcıya bırakır.
 *
 * Tarayıcıda global EvologParse, Node'da module.exports olarak çalışır.
 */
(function (root) {
  "use strict";

  // Türkçe'ye duyarlı sadeleştirme: karşılaştırmalar hep bunun üzerinden.
  function fold(s) {
    return String(s || "")
      .replace(/İ/g, "i").replace(/I/g, "i").replace(/ı/g, "i")
      .replace(/Ş/g, "s").replace(/ş/g, "s")
      .replace(/Ğ/g, "g").replace(/ğ/g, "g")
      .replace(/Ü/g, "u").replace(/ü/g, "u")
      .replace(/Ö/g, "o").replace(/ö/g, "o")
      .replace(/Ç/g, "c").replace(/ç/g, "c")
      .toLowerCase()
      .replace(/[̀-ͯ]/g, "")
      .trim();
  }

  // Uzun karşılık önce denenmeli: "pazartesi" | "pazar" çakışmasın.
  var DAYS = [
    { day: 1, keys: ["pazartesi", "pzt", "pts", "pzts"] },
    { day: 2, keys: ["salı", "sali", "sal"] },
    { day: 3, keys: ["carsamba", "crs", "car", "cars"] },
    { day: 4, keys: ["persembe", "prs", "per", "pers"] },
    { day: 5, keys: ["cuma"] },
    { day: 6, keys: ["cumartesi", "cmt", "cts"] },
    { day: 7, keys: ["pazar", "paz"] }
  ];
  // Eşleşmede önce en uzun anahtar denensin.
  var DAY_KEYS = [];
  DAYS.forEach(function (d) {
    d.keys.forEach(function (k) { DAY_KEYS.push({ key: fold(k), day: d.day }); });
  });
  DAY_KEYS.sort(function (a, b) { return b.key.length - a.key.length; });

  var AYLAR = ["ocak", "subat", "mart", "nisan", "mayis", "haziran",
    "temmuz", "agustos", "eylul", "ekim", "kasim", "aralik"];

  // Satırdaki "ne yapılacak" bilgisi. Anahtar bulunamazsa başlık "Antrenman".
  var KINDS = [
    { kind: "mac", title: "Maç", keys: ["mac", "musabaka", "karsilasma"] },
    { kind: "kuvvet", title: "Kuvvet", keys: ["kuvvet", "fizik", "kondisyon", "atletik", "agirlik"] },
    { kind: "basket", title: "Basketbol", keys: ["basketbol", "basket", "teknik", "taktik", "sut", "oyun", "antrenman", "idman", "calisma"] }
  ];

  var CANCEL = ["yok", "iptal", "tatil", "olmayacak", "yapilmayacak", "yapilmayacaktir", "ara verildi", "izin"];

  var TIME = /(\d{1,2})\s*[:.˙]\s*(\d{2})/g;
  var LOOSE_TIME = /\b(\d{1,2})\s*['’]?\s*(?:de|da|te|ta)\b/i;
  var DATE_DMY = /\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b/;
  var DATE_TEXT = new RegExp("\\b(\\d{1,2})\\s+(" + AYLAR.join("|") + ")\\b");

  function pad(n) { return (n < 10 ? "0" : "") + n; }

  function normTime(h, m) {
    h = parseInt(h, 10); m = parseInt(m, 10);
    if (isNaN(h) || isNaN(m) || h > 23 || m > 59) return null;
    return pad(h) + ":" + pad(m);
  }

  function findDay(folded) {
    for (var i = 0; i < DAY_KEYS.length; i++) {
      var re = new RegExp("(^|[^a-z0-9])" + DAY_KEYS[i].key + "([^a-z0-9]|$)");
      if (re.test(folded)) return DAY_KEYS[i].day;
    }
    return null;
  }

  function findTimes(line) {
    var out = [], m;
    TIME.lastIndex = 0;
    while ((m = TIME.exec(line)) !== null) {
      var t = normTime(m[1], m[2]);
      if (t) out.push({ time: t, start: m.index, end: m.index + m[0].length });
    }
    if (!out.length) {
      var loose = LOOSE_TIME.exec(line);
      if (loose) {
        var lt = normTime(loose[1], 0);
        if (lt) out.push({ time: lt, start: loose.index, end: loose.index + loose[0].length, loose: true });
      }
    }
    return out;
  }

  function findDate(folded, today) {
    var m = DATE_DMY.exec(folded);
    var year = today.getFullYear();
    if (m) {
      var y = m[3] ? parseInt(m[3], 10) : year;
      if (y < 100) y += 2000;
      var d = new Date(y, parseInt(m[2], 10) - 1, parseInt(m[1], 10));
      if (!isNaN(d)) return d;
    }
    m = DATE_TEXT.exec(folded);
    if (m) {
      var mi = AYLAR.indexOf(m[2]);
      if (mi >= 0) {
        var dd = new Date(year, mi, parseInt(m[1], 10));
        // Geçmişte kaldıysa gelecek sezonu kastediyordur.
        if (dd.getTime() < today.getTime() - 120 * 864e5) dd = new Date(year + 1, mi, parseInt(m[1], 10));
        return dd;
      }
    }
    return null;
  }

  function isoDate(d) {
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  }

  // Verilen hafta gününün bu tarihten sonraki ilk oluşumu.
  function nextDate(day, from) {
    var js = day % 7;                       // 7=Pazar -> 0
    var d = new Date(from.getFullYear(), from.getMonth(), from.getDate());
    var delta = (js - d.getDay() + 7) % 7;
    d.setDate(d.getDate() + delta);
    return d;
  }

  function findKind(folded) {
    for (var i = 0; i < KINDS.length; i++) {
      for (var j = 0; j < KINDS[i].keys.length; j++) {
        if (folded.indexOf(KINDS[i].keys[j]) !== -1) return KINDS[i];
      }
    }
    return null;
  }

  function isCancel(folded) {
    return CANCEL.some(function (w) { return folded.indexOf(w) !== -1; });
  }

  // Salonlar bir bakışta ayırt edilsin diye her salona sabit bir renk verilir.
  // Koyu zeminde okunan, birbirinden net ayrılan tonlar.
  var VENUE_COLORS = ["#f2a03d", "#4fd4c0", "#a78bfa", "#f472b6", "#4fd48a", "#60a5fa", "#fbbf24", "#fb7185"];

  function slug(name) {
    return fold(name).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 32) || "salon";
  }

  function titleCase(s) {
    return String(s || "").split(/\s+/).map(function (w) {
      if (!w) return w;
      if (w.length <= 3 && w === w.toUpperCase()) return w;   // BGM, TEV kısaltmaları
      return w.charAt(0).toLocaleUpperCase("tr-TR") + w.slice(1).toLocaleLowerCase("tr-TR");
    }).join(" ");
  }

  // Satırdan saatleri ve tür kelimesini çıkarınca geriye kalan = salon adı.
  function leftover(line, times, kindWord) {
    var out = line;
    times.slice().reverse().forEach(function (t) {
      out = out.slice(0, t.start) + " " + out.slice(t.end);
    });
    if (kindWord) {
      out = out.replace(new RegExp(kindWord, "i"), " ");
    }
    return out
      .replace(/[-–—:;,.()]+/g, " ")
      .replace(/\b(saat|salon|salonu|spor|de|da|te|ta|ile|arasi|arası)\b/gi, function (m) {
        // "Spor Salonu" gerçek adın parçası olabilir; yalnız başınaysa at.
        return /^(saat|de|da|te|ta|ile|arasi|arası)$/i.test(m) ? " " : m;
      })
      .replace(/\s+/g, " ")
      .trim();
  }

  /**
   * @param {string} text  WhatsApp'tan yapıştırılan ham metin
   * @param {Array}  known Bilinen salonlar [{id,name}]
   */
  function parse(text, known) {
    var today = new Date();
    var knownVenues = (known || []).map(function (v) {
      return { id: v.id, name: v.name, color: v.color, folded: fold(v.name) };
    });
    var venues = knownVenues.slice();

    function venueFor(raw) {
      if (!raw) return null;
      var f = fold(raw);
      for (var i = 0; i < venues.length; i++) {
        if (f.indexOf(venues[i].folded) !== -1 || venues[i].folded.indexOf(f) !== -1) {
          return venues[i];
        }
      }
      var v = {
        id: slug(raw), name: titleCase(raw), folded: f, isNew: true,
        color: VENUE_COLORS[venues.length % VENUE_COLORS.length]
      };
      venues.push(v);
      return v;
    }

    var sessions = [], exceptions = [], unparsed = [], matches = [];
    var currentDay = null;
    var lines = String(text || "").split(/\r?\n/);

    lines.forEach(function (rawLine) {
      var line = rawLine
        .replace(/[✀-➿️☀-⛿\ud83c-􏰀-\udfff]/g, " ")  // emoji
        .replace(/\s+/g, " ")
        .trim();
      if (!line) return;

      var f = fold(line);
      var day = findDay(f);
      var times = findTimes(line);
      var date = findDate(f, today);

      // 1) Yalnızca gün adı taşıyan başlık satırı -> sonraki satırlar bu güne ait.
      if (day && !times.length) {
        if (isCancel(f)) {
          exceptions.push({
            date: isoDate(date || nextDate(day, today)),
            type: "iptal",
            reason: line,
            guess: !date,
            src: rawLine
          });
          currentDay = day;
          return;
        }
        currentDay = day;
        return;
      }

      // 2) Selamlama / başlık cümleleri: saat de gün de yoksa ve kısa değilse atla.
      if (!times.length && !day) {
        if (isCancel(f) && date) {
          exceptions.push({ date: isoDate(date), type: "iptal", reason: line, src: rawLine });
          return;
        }
        // Bilgi taşımayan nezaket satırlarını sessizce geç.
        if (/merhaba|selam|deger|program|hafta|iyi ak|kolay gel|sevgi|saygi/.test(f)) return;
        unparsed.push({ line: rawLine, why: "Saat bulunamadı" });
        return;
      }

      var useDay = day || currentDay;
      if (day) currentDay = day;

      if (!times.length) {
        unparsed.push({ line: rawLine, why: "Saat bulunamadı" });
        return;
      }
      if (!useDay) {
        unparsed.push({ line: rawLine, why: "Hangi güne ait olduğu anlaşılmadı" });
        return;
      }

      if (isCancel(f)) {
        exceptions.push({
          date: isoDate(date || nextDate(useDay, today)),
          type: "iptal",
          reason: line,
          guess: !date,
          src: rawLine
        });
        return;
      }

      var kind = findKind(f);
      var kindWord = null;
      if (kind) {
        for (var i = 0; i < kind.keys.length; i++) {
          if (f.indexOf(kind.keys[i]) !== -1) {
            // Ham satırdaki karşılığını bul (Türkçe harfler için gevşek eşleşme)
            var wordRe = new RegExp("[a-zçğıöşüA-ZÇĞİÖŞÜ]*" + kind.keys[i].replace(/[a-z]/g, function (c) {
              return { c: "[cç]", g: "[gğ]", i: "[iı]", o: "[oö]", s: "[sş]", u: "[uü]" }[c] || c;
            }) + "[a-zçğıöşüA-ZÇĞİÖŞÜ]*", "i");
            var m = wordRe.exec(line);
            kindWord = m ? m[0] : kind.keys[i];
            break;
          }
        }
      }

      var venueRaw = leftover(line, times, kindWord);
      // Maç satırında kalan metin rakip + salon karışımıdır ("BGM Galatasaray B");
      // bunu salon listesine sokmak yanlış olur, olduğu gibi not olarak saklanır.
      var isMatch = kind && kind.kind === "mac";
      var venue = isMatch ? null : venueFor(venueRaw);

      var entry = {
        day: useDay,
        start: times[0].time,
        end: times.length > 1 ? times[1].time : null,
        title: kind ? kind.title : "Antrenman",
        kind: kind ? kind.kind : "basket",
        venue: venue ? venue.id : null,
        venueName: venue ? venue.name : null,
        note: isMatch ? venueRaw : null,
        dayGuess: !day,                       // gün başlık satırından devralındı
        kindGuess: !kind,
        venueGuess: !venue || !!venue.isNew,
        src: rawLine
      };

      // "maç" satırı antrenman değildir: programda ayrı gösterilir.
      if (isMatch) {
        entry.title = "Maç";
        matches.push(entry);
      } else {
        sessions.push(entry);
      }
    });

    sessions.sort(function (a, b) {
      return (a.day - b.day) || String(a.start).localeCompare(String(b.start));
    });

    return {
      sessions: sessions,
      matches: matches,
      exceptions: exceptions,
      unparsed: unparsed,
      venues: venues.map(function (v, i) {
        return {
          id: v.id, name: v.name, isNew: !!v.isNew,
          color: v.color || VENUE_COLORS[i % VENUE_COLORS.length]
        };
      })
    };
  }

  var api = { parse: parse, fold: fold, DAYS: DAYS, nextDate: nextDate, isoDate: isoDate, COLORS: VENUE_COLORS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.EvologParse = api;
})(typeof self !== "undefined" ? self : this);
