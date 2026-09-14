# Veli üyelik sistemi — tasarım

**Tarih:** 2026-09-15 · **Durum:** onaylandı, uygulanıyor

## Amaç

Uygulama bugüne kadar herkese açıktı ve 18 yaş altı sporcuların adı, doğum
yılı, fotoğrafı ve maç istatistiklerini içeriyor. Erişim, yönetici onayından
geçmiş velilerle sınırlandırılacak; kimin ne zaman girdiği kayda geçecek.

## Güvenlik sınırı

Veri (`league.json`, `team.json`, `training.json`) artık nginx'in servis ettiği
açık dosyalar değil, **oturum kontrolünden geçen API uçları**. Uygulama kabuğu
(HTML/JS/CSS) açık kalır — içinde veri yok. Giriş yapılmamışsa uygulama giriş
ekranını gösterir; asıl koruma sunucudadır, ekranda değil.

Kuralın **tek bir yerde** (API) uygulanması bilinçli tercih: iki yerde yarım
uygulanan kuraldan güvenli.

## Depolama — SQLite (`/var/lib/evolog/evolog.db`)

| Tablo | İçerik |
|---|---|
| `users` | kullanıcı adı (tekil), şifre özeti + tuz, rol, ad soyad, oyuncu, e-posta, telefon, durum, KVKK sürümü/zamanı/IP |
| `sessions` | oturum anahtarının **özeti**, kullanıcı, oluşturma, son görülme, bitiş, cihaz, IP |
| `audit` | zaman, kullanıcı, eylem, ayrıntı, IP, cihaz |

- **Roller:** `yonetici`, `antrenor`, `veli`
- **Durumlar:** `bekliyor`, `onayli`, `reddedildi`
- **Şifre:** `hashlib.scrypt` (n=2^14, r=8, p=1), düz metin hiçbir yerde durmaz
- **Oturum:** 32 baytlık rastgele anahtar; veritabanında yalnızca SHA-256 özeti
  saklanır. Çerez `HttpOnly; Secure; SameSite=Lax`, 90 gün, her kullanımda uzar.
- **Kaba kuvvet:** kullanıcı adı başına 15 dakikada 10, IP başına 20 başarısız
  deneme sonrası geçici kilit.

## Kayıt akışı

1. Veli: Ad Soyad · **velisi olduğu oyuncu** (kadrodan açılır liste, "listede
   yok" serbest metne düşer) · e-posta · telefon · kullanıcı adı · şifre ·
   KVKK onayı
2. Kayıt `bekliyor` durumunda oluşur; onaylanana kadar şifre doğru olsa da
   giriş reddedilir
3. Yönetici panelden onaylar/reddeder; veliye WhatsApp grubundan haber verilir
   (e-posta gönderimi bilinçli olarak kapsam dışı — sunucuda SMTP yok)

## Roller ve panel

| Sekme | yonetici | antrenor |
|---|---|---|
| Antrenman programı | ✓ | ✓ |
| Veliler (onayla · reddet · sil · geçici şifre) | ✓ | — |
| Kayıtlar (giriş/işlem dökümü) | ✓ | — |

Ortak `1313` şifresi kaldırılır. Başlangıç hesapları: `admin` (yönetici),
`antrenor` (antrenör). **Bilinen sınır:** bunlar ortak hesap olduğu için
loglar kişiyi değil hesabı ayırt eder; kişiye özel hesap sonradan eklenebilir.

## KVKK

Onam metni sürümlü (`kvkk.json`: `version` + `text`). Onay kaydında sürüm,
zaman ve IP saklanır. Sürüm artarsa mevcut kullanıcılar bir sonraki girişte
yeniden onay verir. Metnin hukuki uygunluğu kulübün sorumluluğundadır.

## Etkilenmeyenler

TBF senkronu, push bildirimi, antrenman çözümleyici, PWA kurulumu. Yalnızca
`app.js`'in veri okuma katmanı ve nginx yapılandırması değişir.

## Doğrulama

`server/test_auth.py`: kayıt → onaysız giriş reddi → onay → giriş → veri
erişimi → çıkış → silinen kullanıcının reddi → log kayıtlarının oluşması.
Testler geçmeden yayına alınmaz.
