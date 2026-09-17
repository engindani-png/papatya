# Claude Design brief — Evolog U14 uygulaması

Bu dosya, uygulamanın görsel tasarımını Claude Design'da taslaklamak için
hazırlanmış **kopyala-yapıştır** brief'idir. Veriler 17 Eylül 2026 akşamı canlı
sistemden alındı; Claude Design sunucumuza erişemediği için gerçek değerlerin
brief'in içinde olması şart.

Yapıştırmadan önce: mevcut ekranların görüntülerini de ekle (Takım sayfası,
Maçlar, Antrenman, Antrenör paneli). "Neyi koruyalım, neyi değiştirelim"
sorusunun cevabı görselde.

---

## Brief (buradan aşağısını kopyala)

Bir basketbol takımı uygulamasının görsel tasarımını yeniden düşünmeni istiyorum.
Uygulama **canlı ve kullanımda**; bu bir taslak/yön çalışması, kod değil.

**Kim kullanıyor:** 22 kız sporcunun velileri (çoğu 35-50 yaş, telefondan,
çoğunlukla akşam salonda ya da yolda) ve antrenör. Uygulama telefona PWA olarak
kurulu — tarayıcı çerçevesi çizme, tam ekran uygulama gibi tasarla.

**Takım:** Evolog Daçka Şerifali · U14 Kız Siyah · TBF İstanbul U14 Kızlar
(KIZLAR U14A LİGİ) · 2026-2027 sezonu.

**Artboard boyutu:** 390 × 844 (iPhone). Her ekran ayrı artboard. Alt sekme
çubuğu ve üst güvenli alan boşluğunu hesaba kat.

**Dil:** Tüm metinler Türkçe.

### Tasarlamanı istediğim ekranlar

1. **Maçlar (ana ekran)** — sıradaki maç kartı + geri sayım, son maç skoru,
   yaklaşan maçlar listesi.
2. **Puan durumu** — 12 takımlık lig tablosu, kendi takımımız vurgulu.
3. **Kadro** — 22 oyuncu listesi (forma no + ad + fotoğraf).
4. **Oyuncu profili** — sezon ortalamaları + maç maç istatistik.
5. **Antrenman** — bu haftanın programı, sıradaki antrenman, salonlar.
6. **Ayarlar** — bildirim aç/kapa ve uygulama bilgileri.
7. **Antrenör paneli · Yoklama** — antrenman seçilir, kadro tek dokunuşla
   işaretlenir (Geldi / Geç / Yok / İzinli).
8. **Antrenör paneli · Oyuncu analizi** — bir oyuncunun gelişim grafikleri.

### Gerçek veriler (uydurma, bunları kullan)

**Sıradaki maç** (tarihi kulüpten geldiği için "değişti" rozeti taşıyor):
- 23 Eylül 2026 Çarşamba, 20:00 · 2. hafta
- EYÜPSULTAN BELEDİYESİ – EVOLOG DAÇKA ŞERİFALİ (deplasman)
- Ülker Go Ahead Salonu (C2)
- Rozet: "Değişti · önceki: 3 Ekim Cumartesi 18:30"
- Geri sayım: 5 gün 22 saat 8 dakika

**Son maç:**
- 14 Eylül 2026, 20:00 · 1. hafta · Ülker Çizi Salonu (C3)
- EVOLOG DAÇKA ŞERİFALİ **67 – 38** GALATASARAY (B) — galibiyet
- Çeyrekler: 12-9, 21-4, 15-11, 19-14

**Yaklaşan maçlar** (bir kısmının tarihi TBF'de kesinleşmedi — bu ÖNEMLİ bir
durum, tasarımda net görünmeli):
- 25 Eylül 18:30 · EVOLOG – EMLAK KONUT SPOR (B) · **tarih kesin değil**
- 4 Ekim 18:30 · GALATASARAY (A) – EVOLOG · **tarih kesin değil**
- 13 Ekim 18:30 · EVOLOG – ÜMRANİYE BELEDİYESİ · **tarih kesin değil**
- 22 maçın 20'sinin tarihi böyle. Bu maçlarda gün/saat yerine
  "TBF'de kesinleşmedi" yazıyoruz ve geri sayım yapmıyoruz.

**Puan durumu (ilk 6):**

| # | Takım | O | G | M | P |
|---|---|---|---|---|---|
| 1 | EMLAK KONUT SPOR (A) | 2 | 2 | 0 | 4 |
| 2 | FENERBAHÇE (A) | 2 | 2 | 0 | 4 |
| 3 | GALATASARAY (A) | 2 | 2 | 0 | 4 |
| 4 | **EVOLOG DAÇKA ŞERİFALİ** | 1 | 1 | 0 | 2 |
| 5 | GALATASARAY (B) | 2 | 0 | 2 | 2 |
| 6 | FENERBAHÇE (B) | 2 | 0 | 2 | 2 |

**Kadro (örnek isimler, forma numaralarıyla):** 2 Zeynep Danişmen · 5 Yağmur
Gündoğdu · 8 Feyza Bıçakçı · 11 Ela Gülüzar Kartal · 12 Zeynep Taylan ·
14 Ege Özyıldırım · 24 Defne Sencer · 30 Elif Konak · 96 Zeynep Yazıcıoğlu ·
99 Asya Şentürk · 0 Selen Erdem. (Toplam 22 oyuncu, bir kısmının forma
numarası yok.)

**Son maçın istatistikleri (oyuncu profili ekranı için):**

| No | Oyuncu | Süre | Sayı | Ribaund | Asist | Top çalma |
|---|---|---|---|---|---|---|
| 96 | Zeynep Yazıcıoğlu | 21:19 | 14 | 10 | 1 | 3 |
| 0 | Selen Erdem | 24:27 | 9 | 3 | 3 | 7 |
| 24 | Defne Sencer | 21:12 | 9 | 8 | 3 | 8 |
| 5 | Yağmur Gündoğdu | 17:50 | 8 | 3 | 1 | 2 |
| 30 | Elif Konak | 19:37 | 7 | 14 | 0 | 0 |

**Bu haftanın antrenman programı** (14–20 Eylül haftası):
- Cuma 18 Eylül · 19:30 · Basketbol · TEV
- Pazar 20 Eylül · 11:00 · Basketbol ve Kuvvet · Maltepe TOKİ
- Cumartesi antrenman yok.
- Hafta geçtiğinde ekranda "Önümüzdeki haftanın antrenman programı henüz
  açıklanmadı" durumu görünüyor — bu boş durumu da tasarla.

**Bildirim metinleri (push kartı tasarlarsan):**
- "U14 · Maç saati değişti — Eyüpsultan Belediyesi maçı 23 Eylül Çarşamba 20:00
  oynanacak (önceki: 3 Ekim Cumartesi 18:30)"
- "U14 · Antrenman programı güncellendi — Cuma 19:30 Basketbol (TEV) ·
  Cumartesi antrenman yok · Pazar 11:00 Basketbol ve Kuvvet (Maltepe TOKİ)"
- "U14 · Kazandık! 67-38"

**Yoklama ekranı için:** antrenman seçilir (ör. "Cuma · 18 Eylül · 19:30 ·
Basketbol · TEV"), 22 oyuncunun her biri için dört durumdan biri seçilir:
Geldi / Geç / Yok / İzinli. Üstte canlı sayaç: "12 geldi · 2 yok ·
14/22 işaretlendi". Altta sabit "Kaydet" çubuğu.

**Oyuncu analizi için:** bir oyuncunun maçtan maça gelişim grafikleri (sayı,
ribaund, asist, dakika). Şu an tek maç oynandı; tasarımda 5-6 maçlık örnek
eğri göster. Yanında "↗ Yükseliyor / → Sabit / ↘ Düşüyor" gibi bir eğilim
rozeti var.

### Şu anki tasarım

Koyu yeşilimsi-siyah zemin (#0f1e1c), turuncu-amber vurgu (#f2a03d), başlıklarda
Oswald, metinde Karla. Alt sekme çubuğu: Maçlar · Puan · Kadro · Antrenman ·
Takım. Ekran görüntülerini ekliyorum.

### İstediğim

- Mevcut karanlık/spor kimliğini koruyarak **daha okunaklı ve daha sıcak** bir
  yön. Ekran görüntülerindeki bilgi yoğunluğu doğru; sorun görsel hiyerarşide.
- Velinin tek bakışta cevap araması gereken soru şu: **"Maç/antrenman ne zaman,
  nerede, gitmem gerekiyor mu?"** Ana ekran bunu ilk 3 saniyede söylemeli.
- "Tarihi kesinleşmemiş maç" ile "kesin maç" görsel olarak birbirine
  karışmamalı — veli yanlış güne gitmesin. Bunun için net bir dil öner.
- Renk körlüğü ve güneş altında okunabilirlik önemli: durumları yalnız renkle
  anlatma, etiket/ikon da olsun.
- Sonunda kullandığın renk, tipografi ve boşluk değerlerini **liste halinde**
  ver — tasarımı koda o listeden geçireceğim.

Sponsor logosu, sahte istatistik, gerçek olmayan takım adı ekleme. Tasarımda
çocukların fotoğrafı yerine yer tutucu kullan.
