from flask import Flask, Response
import os
import json
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone

app = Flask(__name__)

WHATSAPP = "12064396261"
LOGO = "/static/assets/logo.png"

def fetch_json(url, headers=None, timeout=12):
    req = urllib.request.Request(
        url,
        headers=headers or {
            "User-Agent": "NexPlayTVUSA/1.0 (catalog website)"
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None

def wikidata_query(query):
    params = urllib.parse.urlencode({"query": query, "format": "json"})
    url = "https://query.wikidata.org/sparql?" + params
    data = fetch_json(url, {
        "User-Agent": "NexPlayTVUSA/1.0 catalog/1.0",
        "Accept": "application/sparql-results+json",
    })
    return data or {}

def commons_image(filename):
    if not filename:
        return ""
    return "https://commons.wikimedia.org/wiki/Special:Redirect/file/" + urllib.parse.quote(filename.replace(" ", "_"))

def get_wikidata_catalog(kind="movie", limit=12):
    if kind == "movie":
        type_filter = "?item wdt:P31/wdt:P279* wd:Q11424."
        heading = "Filmes recentes"
    else:
        type_filter = """{
          ?item wdt:P31/wdt:P279* wd:Q5398426.
        } UNION {
          ?item wdt:P31/wdt:P279* wd:Q15416.
        }"""
        heading = "Séries recentes"

    query = f"""
    SELECT ?item ?itemLabel ?date ?image WHERE {{
      {type_filter}
      ?item wdt:P577 ?date.
      OPTIONAL {{ ?item wdt:P18 ?image. }}
      FILTER(YEAR(?date) >= 2025)
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,pt". }}
    }}
    ORDER BY DESC(?date)
    LIMIT {limit * 4}
    """
    data = wikidata_query(query)
    rows = data.get("results", {}).get("bindings", [])
    result = []
    seen = set()
    for row in rows:
        title = row.get("itemLabel", {}).get("value", "").strip()
        date = row.get("date", {}).get("value", "")[:10]
        image = row.get("image", {}).get("value", "")
        item = row.get("item", {}).get("value", "")
        if not title or item in seen:
            continue
        seen.add(item)
        # Wikimedia-hosted images are used only when a public image exists.
        if image:
            image_url = commons_image(image.split("/")[-1])
        else:
            image_url = ""
        result.append({
            "title": title,
            "date": date,
            "image": image_url,
            "url": item,
            "kind": heading
        })
        if len(result) >= limit:
            break
    return result

def get_tvmaze():
    # TVmaze is public and does not require an API key.
    data = fetch_json("https://api.tvmaze.com/schedule?country=US")
    result = []
    if not isinstance(data, list):
        return result
    seen = set()
    for ep in data:
        show = ep.get("show") or {}
        sid = show.get("id")
        if not sid or sid in seen:
            continue
        seen.add(sid)
        image = (show.get("image") or {}).get("original") or (show.get("image") or {}).get("medium") or ""
        result.append({
            "title": show.get("name") or "Série",
            "date": ep.get("airdate") or "",
            "image": image,
            "kind": "Em exibição nos EUA",
            "network": ((show.get("network") or {}).get("name") or (show.get("webChannel") or {}).get("name") or "")
        })
        if len(result) >= 14:
            break
    return result

def catalog_data():
    # Use TVmaze first for a lively, frequently changing US TV rail.
    tv = get_tvmaze()
    movies = get_wikidata_catalog("movie", 12)
    series = get_wikidata_catalog("series", 12)
    if not series:
        series = tv
    return movies, series, tv

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;"))

def cards(items):
    out = []
    for x in items:
        img = x.get("image", "")
        if img:
            visual = f'<img src="{esc(img)}" alt="{esc(x["title"])}" loading="lazy">'
        else:
            visual = '<div class="no-poster"><span>▶</span></div>'
        meta = x.get("date", "")
        if meta:
            meta = meta[:4] if len(meta) >= 4 else meta
        out.append(f"""
        <article class="card">
          <div class="poster">{visual}<div class="shine"></div></div>
          <div class="card-info">
            <strong>{esc(x["title"])}</strong>
            <small>{esc(meta or x.get("kind",""))}</small>
          </div>
        </article>""")
    return "".join(out)

def page():
    movies, series, tv = catalog_data()
    movie_cards = cards(movies)
    series_cards = cards(series)
    tv_cards = cards(tv)
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#05070c">
<title>NexPlay TV USA — Entretenimento onde você estiver</title>
<link rel="icon" type="image/png" href="{LOGO}">
<style>
:root{{--bg:#05070c;--panel:#0b101a;--panel2:#101722;--blue:#19a8ff;--blue2:#006eff;--text:#f7fbff;--muted:#91a0b5;--line:rgba(255,255,255,.09);--shadow:0 24px 70px rgba(0,0,0,.45)}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:radial-gradient(circle at 70% 0%,rgba(0,126,255,.16),transparent 30%),var(--bg);color:var(--text);font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;overflow-x:hidden}}
a{{color:inherit;text-decoration:none}}.wrap{{width:min(1180px,92%);margin:auto}}
header{{position:sticky;top:0;z-index:20;background:rgba(5,7,12,.78);backdrop-filter:blur(18px);border-bottom:1px solid var(--line)}}
.nav{{height:76px;display:flex;align-items:center;justify-content:space-between;gap:20px}}.brand img{{height:52px;width:auto;display:block}}
nav{{display:flex;gap:25px;align-items:center;font-size:14px;color:#c9d3e0}}nav a:hover{{color:#fff}}
.lang{{border:1px solid var(--line);border-radius:999px;padding:9px 14px;background:#0c121c}}
.hero{{min-height:640px;display:grid;place-items:center;position:relative;overflow:hidden}}
.hero:before{{content:"";position:absolute;inset:-20%;background:radial-gradient(circle at 72% 45%,rgba(0,144,255,.24),transparent 25%),radial-gradient(circle at 20% 50%,rgba(0,88,255,.10),transparent 30%);filter:blur(10px)}}
.hero-inner{{position:relative;text-align:center;padding:90px 0 70px;max-width:850px}}
.kicker{{display:inline-flex;gap:8px;align-items:center;border:1px solid rgba(25,168,255,.35);background:rgba(25,168,255,.08);padding:8px 13px;border-radius:999px;color:#80d1ff;font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}}
h1{{font-size:clamp(48px,8vw,92px);line-height:.95;margin:22px 0 20px;letter-spacing:-.055em}}h1 span{{color:var(--blue);text-shadow:0 0 35px rgba(25,168,255,.28)}}
.hero p{{font-size:19px;color:var(--muted);max-width:650px;margin:0 auto 30px;line-height:1.65}}
.btns{{display:flex;justify-content:center;gap:12px;flex-wrap:wrap}}.btn{{padding:14px 22px;border-radius:12px;font-weight:800;border:1px solid var(--line);background:#101722}}.primary{{background:linear-gradient(135deg,#12a8ff,#006eff);box-shadow:0 12px 35px rgba(0,110,255,.25);border:0}}
.trust{{display:flex;justify-content:center;gap:28px;flex-wrap:wrap;margin-top:28px;color:#9ba9bc;font-size:13px}}
section{{padding:78px 0}}.section-head{{display:flex;justify-content:space-between;align-items:end;gap:20px;margin-bottom:25px}}.eyebrow{{font-size:12px;color:var(--blue);font-weight:900;letter-spacing:.14em;text-transform:uppercase}}h2{{font-size:36px;margin:7px 0 0;letter-spacing:-.035em}}.section-head p{{color:var(--muted);margin:0}}
.catalog{{position:relative}}.rail{{display:flex;gap:16px;overflow-x:auto;padding:4px 2px 18px;scrollbar-width:thin;scrollbar-color:#167fff transparent;scroll-snap-type:x mandatory}}
.card{{min-width:170px;width:170px;scroll-snap-align:start;background:var(--panel);border:1px solid var(--line);border-radius:15px;overflow:hidden;transition:.25s;box-shadow:0 8px 30px rgba(0,0,0,.2)}.card:hover{{transform:translateY(-6px);border-color:rgba(25,168,255,.45);box-shadow:0 15px 35px rgba(0,0,0,.35)}}
.poster{{height:250px;background:#0e1520;position:relative;overflow:hidden}}.poster img{{width:100%;height:100%;object-fit:cover;display:block}}.shine{{position:absolute;inset:0;background:linear-gradient(115deg,transparent 35%,rgba(255,255,255,.12),transparent 60%);transform:translateX(-120%);animation:shine 5s infinite}}@keyframes shine{{75%,100%{{transform:translateX(120%)}}}}
.no-poster{{height:100%;display:grid;place-items:center;color:#1daaff;font-size:42px;background:radial-gradient(circle,#102d47,#09101a)}}
.card-info{{padding:12px}}.card-info strong{{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:14px}}.card-info small{{display:block;color:#718198;margin-top:5px;font-size:11px}}
.live{{border:1px solid rgba(25,168,255,.2);background:linear-gradient(180deg,#0c1420,#080d15);border-radius:24px;padding:30px;box-shadow:var(--shadow)}}.live-top{{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:18px}}.dot{{display:inline-flex;align-items:center;gap:7px;color:#72d1ff;font-weight:800;font-size:12px}}.dot i{{width:8px;height:8px;background:#19a8ff;border-radius:50%;box-shadow:0 0 15px #19a8ff}}
.features{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}}.feature,.plan,.faq{{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:26px}}.feature b{{font-size:17px}}.feature p,.faq p{{color:var(--muted);line-height:1.6}}
.plans{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}.plan{{position:relative}}.plan.best{{border-color:rgba(25,168,255,.7);box-shadow:0 0 40px rgba(0,110,255,.12)}}.badge{{position:absolute;top:14px;right:14px;background:var(--blue);color:#00101b;font-size:10px;font-weight:900;padding:6px 8px;border-radius:999px}}.price{{font-size:36px;font-weight:900;margin:14px 0}}.price small{{font-size:13px;color:var(--muted);font-weight:600}}.plan p{{color:var(--muted);font-size:13px;line-height:1.55}}.plan .btn{{display:block;text-align:center;margin-top:20px}}
.reseller{{display:grid;grid-template-columns:1.15fr .85fr;gap:20px;align-items:stretch}}.res-box{{background:linear-gradient(145deg,#0d1a28,#080d14);border:1px solid rgba(25,168,255,.2);border-radius:22px;padding:35px}}.res-list{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:20px}}.res-list div{{padding:13px;border:1px solid var(--line);border-radius:12px;color:#cbd5e1;background:#0a111b}}
.faqs{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
footer{{padding:35px 0;border-top:1px solid var(--line);color:#718198;font-size:13px}}footer .wrap{{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}}
@media(max-width:900px){{nav a{{display:none}}.plans{{grid-template-columns:1fr 1fr}}.features,.reseller,.faqs{{grid-template-columns:1fr}}}}
@media(max-width:520px){{.hero{{min-height:570px}}.plans{{grid-template-columns:1fr}}.card{{min-width:150px;width:150px}}.poster{{height:225px}}h2{{font-size:29px}}}}
</style>
</head>
<body>
<header><div class="wrap nav"><a class="brand" href="#top"><img src="{LOGO}" alt="NexPlay TV USA"></a>
<nav><a href="#catalogo">Catálogo</a><a href="#planos">Planos</a><a href="#vantagens">Vantagens</a><a href="#revenda">Revendedores</a><a href="#faq">FAQ</a><a class="lang" href="#contato">🇧🇷 PT</a></nav></div></header>

<main id="top">
<section class="hero"><div class="wrap hero-inner">
<div class="kicker">✦ NexPlay TV USA • atualizado automaticamente</div>
<h1>Seu entretenimento.<br><span>Do seu jeito.</span></h1>
<p>Planos flexíveis, atendimento em português e um catálogo que acompanha novidades de filmes e séries.</p>
<div class="btns"><a class="btn primary" href="https://wa.me/{WHATSAPP}?text=Olá!%20Quero%20conhecer%20a%20NexPlay%20TV%20USA." target="_blank">Pedir teste grátis</a><a class="btn" href="#planos">Ver planos</a></div>
<div class="trust"><span>✓ Atendimento em português</span><span>✓ Pix e cartão</span><span>✓ Teste 6h ou 12h</span></div>
</div></section>

<section id="catalogo"><div class="wrap">
<div class="section-head"><div><div class="eyebrow">Catálogo</div><h2>Filmes que estão chegando</h2></div><p>Dados públicos atualizados automaticamente</p></div>
<div class="catalog"><div class="rail">{movie_cards}</div></div>
<div class="section-head" style="margin-top:45px"><div><div class="eyebrow">Séries</div><h2>Séries recentes</h2></div><p>Novidades e títulos em destaque</p></div>
<div class="catalog"><div class="rail">{series_cards}</div></div>
</div></section>

<section><div class="wrap"><div class="live">
<div class="live-top"><div><div class="eyebrow">Agora</div><h2 style="margin-top:5px">O que está em exibição</h2></div><div class="dot"><i></i> ATUALIZAÇÃO AUTOMÁTICA</div></div>
<div class="rail">{tv_cards}</div>
<div style="color:#66758b;font-size:11px;margin-top:8px">Última atualização do catálogo: {esc(now)}</div>
</div></div></section>

<section id="vantagens"><div class="wrap"><div class="section-head"><div><div class="eyebrow">NexPlay</div><h2>Uma experiência simples e direta.</h2></div></div>
<div class="features"><div class="feature"><b>01 • Planos flexíveis</b><p>Escolha mensal, trimestral, semestral ou anual conforme sua necessidade.</p></div><div class="feature"><b>02 • Teste grátis</b><p>Fale conosco e consulte a disponibilidade do teste de 6h ou 12h.</p></div><div class="feature"><b>03 • Suporte em português</b><p>Atendimento pelo WhatsApp para tirar suas dúvidas.</p></div></div></div></section>

<section id="planos"><div class="wrap"><div class="section-head"><div><div class="eyebrow">Planos</div><h2>Escolha seu plano</h2></div><p>Valores em dólares</p></div>
<div class="plans">
<div class="plan"><h3>Mensal</h3><div class="price">US$ 10 <small>/ sem adulto</small></div><p>Com adulto: <b>US$ 15</b></p><a class="btn primary" href="https://wa.me/{WHATSAPP}?text=Olá!%20Quero%20assinar%20o%20plano%20mensal." target="_blank">Assinar</a></div>
<div class="plan"><h3>Trimestral</h3><div class="price">US$ 25 <small>/ sem adulto</small></div><p>Com adulto: <b>US$ 40</b></p><a class="btn primary" href="https://wa.me/{WHATSAPP}?text=Olá!%20Quero%20assinar%20o%20plano%20trimestral." target="_blank">Assinar</a></div>
<div class="plan"><h3>Semestral</h3><div class="price">US$ 55 <small>/ sem adulto</small></div><p>Com adulto: <b>US$ 85</b></p><a class="btn primary" href="https://wa.me/{WHATSAPP}?text=Olá!%20Quero%20assinar%20o%20plano%20semestral." target="_blank">Assinar</a></div>
<div class="plan best"><span class="badge">MELHOR OFERTA</span><h3>Anual</h3><div class="price">US$ 90 <small>/ sem adulto</small></div><p>Com adulto: <b>US$ 100</b></p><a class="btn primary" href="https://wa.me/{WHATSAPP}?text=Olá!%20Quero%20assinar%20o%20plano%20anual." target="_blank">Assinar</a></div>
</div></div></section>

<section id="revenda"><div class="wrap reseller"><div class="res-box"><div class="eyebrow">Revenda</div><h2>Quer saber mais sobre revenda?</h2><p style="color:#9aa9bb;line-height:1.7">Conheça as modalidades disponíveis e fale diretamente com nossa equipe para receber valores e condições.</p><a class="btn primary" href="https://wa.me/{WHATSAPP}?text=Olá!%20Quero%20saber%20mais%20sobre%20revenda." target="_blank">Falar no WhatsApp</a></div>
<div class="res-box"><div class="res-list"><div>PRÉ-PAGO</div><div>PÓS-PAGO</div><div>PAINEL MENSALISTA</div><div>PAINEL ILIMITADO</div></div></div></div></section>

<section id="faq"><div class="wrap"><div class="section-head"><div><div class="eyebrow">FAQ</div><h2>Perguntas frequentes</h2></div></div>
<div class="faqs"><div class="faq"><b>Como solicito o teste grátis?</b><p>Clique em qualquer botão de teste e fale conosco pelo WhatsApp. A disponibilidade e duração serão confirmadas no atendimento.</p></div><div class="faq"><b>Quais formas de pagamento são aceitas?</b><p>Aceitamos Pix e cartão. Fale com o suporte para receber as instruções de pagamento.</p></div><div class="faq"><b>O atendimento é em português?</b><p>Sim. Nosso suporte é realizado em português pelo WhatsApp.</p></div><div class="faq"><b>O catálogo é atualizado?</b><p>Esta página consulta fontes públicas de metadados e imagens e renova os cards automaticamente.</p></div></div></div></section>
</main>

<footer id="contato"><div class="wrap"><span>© 2026 NexPlay TV USA. Todos os direitos reservados.</span><span>WhatsApp: +1 (206) 439-6261</span></div></footer>
<script>
(function(){const rails=document.querySelectorAll('.rail');rails.forEach((rail,i)=>{if(!rail.children.length)return;let dir=i%2?-1:1;setInterval(()=>{if(rail.scrollWidth<=rail.clientWidth)return;const max=rail.scrollWidth-rail.clientWidth;if(rail.scrollLeft>=max-5)dir=-1;if(rail.scrollLeft<=5)dir=1;rail.scrollBy({left:dir*185,behavior:'smooth'});},3200);});})();
</script>
</body></html>"""
    return html

@app.route("/")
def home():
    return Response(page(), mimetype="text/html")

@app.route("/health")
def health():
    return {"status": "ok", "service": "NexPlay TV USA", "catalog": "public-metadata"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
