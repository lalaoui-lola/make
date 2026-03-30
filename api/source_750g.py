"""
api/750g.py — GET /api/750g?q=gateau+chocolat&n=2
===================================================
Source 2 : 750g.com
✅ Grand site français de recettes.
✅ JSON-LD bien structuré sur chaque page recette.
✅ Pas de protection anti-bot agressive.

Params :
  q        — Terme de recherche (ex: "gateau chocolat", "tarte citron")
  category — Catégorie 750g (ex: "dessert", "plat", "entree")
  n        — Nombre de résultats (max: 5)
  page     — Page de résultats (1, 2, 3...)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import re
import urllib.parse

import requests as req
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from utils import get_headers, scrape_url, build_ai_context, error_response, make_recipe

app = Flask(__name__)

BASE = "https://www.750g.com"

# Catégories 750g
CATEGORIES_750G = {
    "entree":          "/recettes-entree.htm",
    "entree-chaude":   "/recettes-entree-chaude.htm",
    "entree-froide":   "/recettes-entree-froide.htm",
    "plat":            "/recettes-plat.htm",
    "plat-principal":  "/recettes-plat.htm",
    "dessert":         "/recettes-dessert.htm",
    "gateau":          "/recettes-gateau.htm",
    "tarte":           "/recettes-tarte.htm",
    "soupe":           "/recettes-soupe.htm",
    "salade":          "/recettes-salade.htm",
    "pasta":           "/recettes-pates.htm",
    "pates":           "/recettes-pates.htm",
    "poisson":         "/recettes-poisson.htm",
    "viande":          "/recettes-viande.htm",
    "poulet":          "/recettes-poulet.htm",
    "vegetarien":      "/recettes-vegetarien.htm",
    "pain":            "/recettes-pain.htm",
    "aperitif":        "/recettes-aperitif.htm",
    "confiture":       "/recettes-confiture.htm",
    "sauce":           "/recettes-sauce.htm",
    "biscuit":         "/recettes-biscuits.htm",
}


def _search_urls(query, page=1, n=5):
    """Cherche des recettes sur 750g via la recherche du site."""
    encoded = urllib.parse.quote(query)
    url = f"{BASE}/recherche/?q={encoded}&page={page}"
    try:
        resp = req.get(url, headers=get_headers(referer=BASE), timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        urls = []
        # Les résultats de recherche 750g : liens avec /recette_ dans l'URL
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full = href if href.startswith("http") else BASE + href
            if re.search(r'-r\d+\.htm$', full) and full not in urls:
                urls.append(full)
            if len(urls) >= n + 3:
                break
        return urls
    except Exception as e:
        return []


def _list_category_urls(slug, page=1, n=5):
    """Liste les recettes d'une catégorie 750g."""
    path = CATEGORIES_750G.get(slug.lower().replace("-", ""), f"/recettes-{slug}.htm")
    url = f"{BASE}{path}?page={page}"
    try:
        resp = req.get(url, headers=get_headers(referer=BASE), timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        urls = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full = href if href.startswith("http") else BASE + href
            if re.search(r'-r\d+\.htm$', full) and full not in urls:
                urls.append(full)
            if len(urls) >= n + 3:
                break
        return urls
    except Exception as e:
        return []


def _scrape_recipe(url):
    """Scrape une page recette 750g (JSON-LD privilégié)."""
    recipe = scrape_url(url, source_site="750g.com")
    return recipe


@app.route("/api/750g", methods=["GET"])
def source_750g():
    """
    GET /api/750g?q=gateau+chocolat&n=2
    GET /api/750g?category=dessert&n=3&page=2
    """
    q        = request.args.get("q", "")
    category = request.args.get("category", "")
    n        = min(int(request.args.get("n", 1)), 5)
    page     = int(request.args.get("page", 1))

    if q:
        urls = _search_urls(q, page=page, n=n)
    elif category:
        urls = _list_category_urls(category, page=page, n=n)
    else:
        resp = jsonify({"error": "Paramètre requis : q ou category"})
        resp.status_code = 400
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    if not urls:
        resp = jsonify({
            "source": "750g",
            "count": 0,
            "recipes": [],
            "message": f"Aucune recette trouvée pour '{q or category}' page {page}",
            "context_for_ai": "Aucune recette trouvée.",
        })
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    recipes = []
    for url in urls[:n]:
        r = _scrape_recipe(url)
        if "error" not in r and r.get("title") and r.get("ingredients"):
            recipes.append(r)

    resp = jsonify({
        "source":         "750g",
        "query":          q or category,
        "page":           page,
        "count":          len(recipes),
        "recipes":        recipes,
        "context_for_ai": build_ai_context(recipes),
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


if __name__ == "__main__":
    app.run(port=5002, debug=True)
