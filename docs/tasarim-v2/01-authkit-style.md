# Authkit — Style Reference
> Frosted glass cathedral at midnight

**Theme:** dark
**Kaynak:** kullanıcı tarafından paylaşıldı (19.09.2026), 1/4 — design md

AuthKit renders a midnight product-launch aesthetic: a near-black canvas with
frosted-glass surfaces, a grid of faint blueprint lines, and luminous text that
appears lit from behind a glass layer. Type is almost entirely white-on-dark
with one vivid violet as the single functional accent — every interactive
surface wears a soft inset hairline of cool blue-white rather than a hard
border. Components sit on translucent layers stacked above ambient glows, with
cards that look like glass plates lit from below rather than paper panels.
Spacing is generous and rhythmic; the hero is a single full-bleed illuminated
wordmark surrounded by floating glass cards rather than a conventional split
layout.

> Tam metin (renk/tipografi/bileşen tabloları, do's & don'ts, gradient sistemi,
> agent prompt rehberi) sohbet kaydındadır; buradaki özet + `tokens.css`
> uygulamada kullanılan kaynaktır.

## Özet kurallar

- Tek kromatik aksan: **Void Violet `#663af3`**, yalnızca birincil eylem
  düğmesinde. Başka hiçbir yerde renk yok.
- Kenarlık dili: solid çizgi yok; her yerde **1px inset `rgba(186,215,247,0.12)`**.
- Yükseklik: klasik drop-shadow yok; **inset frost highlight + yumuşak dış hale**.
- Yarıçap aileleri karışmaz: düğme `999px`, kart/modal `16px`, rozet/girdi `6px`,
  ikon kabı `9999px`.
- Metin hiyerarşisi: `#d8ecf8` başlık → `#d1e4fa` gövde → `#c7d3ea` sönük →
  `#9da7ba` yardımcı.
- Başlıklar aeonikPro **500** (600+ kullanılmaz), Skywash dikey gradyan
  (`#d8ecf8 → #98c0ef`) yalnızca en büyük başlıkta.
- Eyebrow etiketler: dotDigital 15px, `0.10em` harf aralığı, ortalanmış, iki
  yanında solan yatay çizgi.
- Zemin: blueprint grid (1px `rgba(186,215,247,0.06)`, ~80px) + üstte konik
  gradyan spot.

## Yazı tipleri (lisanslı → ikame)

| Tasarımdaki | İkame (Google Fonts) | Rol |
|---|---|---|
| Untitled Sans | **Inter** | Gövde, arayüz, düğme, girdi, rozet |
| aeonikPro | **Space Grotesk** | Yalnızca display başlıklar |
| dotDigital | **JetBrains Mono** | Büyük harf eyebrow etiketler |
