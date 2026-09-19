# Tasarım denemesi (demo)

Yeni tasarım stilini **ana uygulamaya dokunmadan** denemek için ayrı kopya.

- Konum: `evolog/demo/` — nginx'in servis ettiği ağacın **içinde** olmalı.
  Repo kökündeki `demo/` sunucu kökünün dışında kaldığı için 404 veriyordu.
- Adres: `/demo/` (nginx kökü `evolog/` ise) ya da `/evolog/demo/`.
  Sayfa hangi yerleşimde olduğunu çalışma anında kendi bulur, ikisinde de çalışır.
- Veri: ana uygulamayla **aynı** (`/data/u14/`) — gerçek kadro, fikstür, puan durumu
- Logolar: `league.json` içindeki yollar sayfa derinliğine göre yazıldığı için
  demoda `logoUrl()` ile çalışma anında hesaplanan tabana bağlanır (kopya tutulmaz)
- **Servis çalışanı yok**, **manifest yok** — demo PWA olarak kurulmaz ve ana
  uygulamanın önbelleğine karışmaz
- `noindex` — arama motorlarına düşmez

Beğenilirse `demo/styles.css` (ve varsa `demo/app.js` içindeki işaretleme
değişiklikleri) `evolog/` altına taşınır.

## Yerelde bakmak

```bash
python3 -m http.server 8788
# ana uygulama : http://localhost:8788/evolog/
# demo         : http://localhost:8788/evolog/demo/
```
