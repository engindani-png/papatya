# Tasarım denemesi (demo)

Yeni tasarım stilini **ana uygulamaya dokunmadan** denemek için ayrı kopya.

- Adres: `/demo/`  ·  ana uygulama `/evolog/` olduğu gibi kalır
- Veri: ana uygulamayla **aynı** (`../data/u14/`) — gerçek kadro, fikstür, puan durumu
- Logolar: `../evolog/logos/` (kopya tutulmaz)
- **Servis çalışanı yok**, **manifest yok** — demo PWA olarak kurulmaz ve ana
  uygulamanın önbelleğine karışmaz
- `noindex` — arama motorlarına düşmez

Beğenilirse `demo/styles.css` (ve varsa `demo/app.js` içindeki işaretleme
değişiklikleri) `evolog/` altına taşınır.

## Yerelde bakmak

```bash
python3 -m http.server 8788
# ana uygulama : http://localhost:8788/evolog/
# demo         : http://localhost:8788/demo/
```
