# AuthKit stili — kaynak paket (v2 denemesi)

Kullanıcı tarafından 19.09.2026'da dört parça halinde paylaşıldı.

| Dosya | İçerik |
|---|---|
| `01-authkit-style.md` | Stil tanımı, bileşen sözlüğü, do's & don'ts |
| `02-tailwind-theme.css` | Tailwind v4 `@theme` bloğu |
| `03-tokens.css` | Ham CSS `:root` değişkenleri |
| `04-tokens.json` | W3C design-token formatı (`$value`/`$type`) |

Uygulanışı: `demo/` altında, ana uygulamaya dokunmadan.

## Bilinen kaynak hatası

`--surface-steel-plate` değeri `#2f343` — beş haneli, geçersiz renk.
Doğrusu `#2f343e` (Steel Plate). Hem `03-tokens.css` hem `04-tokens.json`
içinde aynı hata var; `demo/` tarafında düzeltilmiş hali kullanılıyor.

## Mobil uyarlama notu

Kaynak bir masaüstü tanıtım sayfası sistemi: 120px bölüm aralığı, 48px
display tipografi, 1200px içerik genişliği. Bizim ekran 390px genişliğinde
yoğun bir araç — fikstür listesi, puan tablosu, box score. Görsel dil
(gece zemini, buzlu cam yüzeyler, inset saç teli kenarlar, tek mor aksan,
Skywash gradyan başlık, eyebrow etiketler, blueprint grid) birebir alındı;
**ritim** (boşluk ve punto ölçeği) mobil yoğunluğa göre ölçeklendi.
