from flask import Flask, render_template, jsonify
import os
import time
from datetime import datetime, timedelta, timezone
import requests

app = Flask(__name__)

CATALOG_CACHE = {"timestamp": 0, "data": None}
CATALOG_TTL = 30 * 60  # refresh every 30 minutes


def _wikidata_movies():
    """Recent/upcoming films with poster artwork from Wikidata/Wikimedia Commons."""
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=120)
    end = today + timedelta(days=60)
    query = f"""
    SELECT ?item ?itemLabel ?date ?image WHERE {{
      ?item wdt:P31/wdt:P279* wd:Q11424;
            wdt:P577 ?date;
            wdt:P18 ?image.
      FILTER(?date >= "{start}T00:00:00Z"^^xsd:dateTime)
      FILTER(?date <= "{end}T23:59:59Z"^^xsd:dateTime)
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    ORDER BY DESC(?date)
    LIMIT 24
    """
    r = requests.get(
        "https://query.wikidata.org/sparql",
        params={"query": query, "format": "json"},
        headers={"User-Agent": "NexPlay-TV-USA/1.0 (catalog metadata)", "Accept": "application/sparql-results+json"},
        timeout=18,
    )
    r.raise_for_status()
    rows = r.json().get("results", {}).get("bindings", [])
    out = []
    seen = set()
    for row in rows:
        title = row.get("itemLabel", {}).get("value", "").strip()
        image = row.get("image", {}).get("value", "").strip()
        date = row.get("date", {}).get("value", "")[:10]
        item = row.get("item", {}).get("value", "")
        if not title or not image or title in seen:
            continue
        seen.add(title)
        if image.startswith("http://"):
            image = "https://" + image[7:]
        out.append({
            "title": title,
            "year": date[:4] if date else "",
            "date": date,
            "image": image,
            "type": "movie",
            "source": "Wikidata / Wikimedia Commons",
            "source_url": item,
        })
    return out[:12]


def _tvmaze_series():
    """Series airing in the US over the next few days, with TVmaze artwork."""
    today = datetime.now(timezone.utc).date()
    shows = {}
    for offset in range(3):
        date = today + timedelta(days=offset)
        try:
            r = requests.get(
                "https://api.tvmaze.com/schedule",
                params={"country": "US", "date": date.isoformat()},
                headers={"User-Agent": "NexPlay-TV-USA/1.0"},
                timeout=10,
            )
            r.raise_for_status()
            for ep in r.json():
                show = ep.get("show") or {}
                sid = show.get("id")
                if not sid or sid in shows:
                    continue
                image = show.get("image") or {}
                poster = image.get("medium") or image.get("original")
                if not poster:
                    continue
                shows[sid] = {
                    "title": show.get("name", ""),
                    "year": (show.get("premiered") or "")[:4],
                    "date": ep.get("airdate", ""),
                    "image": poster,
                    "type": "series",
                    "source": "TVmaze",
                    "source_url": show.get("url", "https://www.tvmaze.com/"),
                }
        except requests.RequestException:
            continue
    return list(shows.values())[:12]


def get_catalog():
    now = time.time()
    if CATALOG_CACHE["data"] is not None and now - CATALOG_CACHE["timestamp"] < CATALOG_TTL:
        return CATALOG_CACHE["data"]

    movies = []
    series = []
    try:
        movies = _wikidata_movies()
    except Exception:
        movies = []
    try:
        series = _tvmaze_series()
    except Exception:
        series = []

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "movies": movies,
        "series": series,
        "attribution": {
            "wikidata": "https://www.wikidata.org/",
            "commons": "https://commons.wikimedia.org/",
            "tvmaze": "https://www.tvmaze.com/",
        },
    }
    CATALOG_CACHE.update({"timestamp": now, "data": data})
    return data


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/catalog")
def catalog():
    return jsonify(get_catalog())


@app.route("/health")
def health():
    return {"status": "ok", "service": "NexPlay TV USA"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
