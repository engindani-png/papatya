#!/usr/bin/env python3
"""evolog/ kaynaklarindan tek dosyalik, kendi kendine yeten onizleme uretir.

Veriyi fetch etmek yerine sayfaya gomer; boylece tek bir HTML olarak
paylasilabilir. Kullanim: python3 scripts/build_artifact.py [cikti.html]
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "evolog", "preview.html")

    css = read("evolog", "styles.css")
    js = read("evolog", "app.js")
    shell = read("evolog", "index.html")

    # index.html'in <body> icerigini al (artifact iskeleti head/body'yi kendi saglar)
    body = shell.split("<body>", 1)[1].split("</body>", 1)[0]
    body = body.replace('<script src="app.js"></script>', "")
    body = body.replace('<link rel="stylesheet" href="styles.css">', "")

    data = {
        "team": json.loads(read("data", "team.json")),
        "training": json.loads(read("data", "training.json")),
        "league": json.loads(read("data", "league.example.json")),
    }

    html = (
        "<title>Evolog U14 Kız</title>\n"
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=Oswald:wght@400;500;600;700&family=Karla:wght@400;500;700&display=swap">\n'
        "<style>\n" + css + "\n</style>\n"
        + body.strip() + "\n"
        '<script id="evolog-data" type="application/json">'
        + json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
        + "</script>\n"
        "<script>\n"
        'window.EVOLOG_INLINE_DATA = JSON.parse(document.getElementById("evolog-data").textContent);\n'
        "</script>\n"
        "<script>\n" + js + "\n</script>\n"
    )

    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"Yazildi: {out} ({len(html)} bayt)")


if __name__ == "__main__":
    main()
