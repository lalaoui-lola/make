"""
api/cuisineaz.py — GET /api/cuisineaz?q=tarte+citron&n=2
==========================================================
Source 3 : CuisineAZ.com
✅ Grand site français de recettes (groupe Mondadori).
✅ JSON-LD Recipe sur chaque page.
✅ Moteur de recherche accessible.

Params :
  q        — Terme de recherche
  category — Catégorie (ex: "dessert", "plat", "entree")
  n        — Nombre de résultats (max: 5)
  page     — Page de résultats
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import urllib.parse
import requests as req
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from utils import get_headers, scrape_url, build_ai_context, error_response

app = Flask(__name__)

BASE = "https://www.cuisineaz.com"

CATEGORIES_CAZ = {
    "entree":         "/recettes/entrees",
    "plat":           "/recettes/plats-principaux",
    "plat-principal": "/recettes/plats-principaux",
    "dessert":        "/recettes/desserts",
    "gateau":         "/recettes/gateaux",
    "tarte":          "/recettes/tartes",
    "soupe":          "/recettes/soupes",
    "salade":         "/recettes/salades",
    "pates":          "/recettes/pates",
    "pasta":          "/recettes/pates",
    "poisson":        "/recettes/poissons",
    "viande":         "/recettes/viandes",
    "poulet":         "/recettes/poulet",
    "vegetarien":     "/recettes/vegetarien",
    "pain":           "/recettes/pains",
    "aperitif":       "/recettes/aperitifs",
    "sauce":          "/recettes/sauces",
    "biscuit":        "/recettes/biscuits-et-cookies",
    "confiture":      "/recettes/confitures",
}


def _search_urls(query, page=1, n=5):
    """Recherche sur CuisineAZ."""
    encoded = urllib.parse.quote(query)
    url = f"{BASE}/recettes/recherche?q={encoded}&page={page}"
    try:
        resp = req.get(url, headers=get_headers(referer=BASE), timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        urls = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Les URLs recettes cuisineaz commencent par /recettes/ et ont un ID numérique
            if "/recettes/" in href and href.count("/") >= 3 and href not in urls:
                full = href if href.startswith("http") else BASE + href
                # Éviter les pages de liste
                if not href.endswith("/recettes/"):
                    urls.append(full)
            if len(urls) >= n + 3:
                break
        return urls
    except Exception as e:
        return []


def _list_category_urls(slug, page=1, n=5):
    """Liste les recettes d'une catégorie CuisineAZ."""
    path = CATEGORIES_CAZ.get(slug.lower().replace("-", ""), f"/recettes/{slug}")
    url = f"{BASE}{path}?page={page}"
    try:
        resp = req.get(url, headers=get_headers(referer=BASE), timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        urls = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/recettes/" in href and href.count("/") >= 3 and href not in urls:
                full = href if href.startswith("http") else BASE + href
                if not any(x in full for x in ["/recettes/recherche", "/recettes/plats", "/recettes/desserts", "/recettes/entrees", "/recettes/soupes", "/recettes/salades"]):
                    urls.append(full)
            if len(urls) >= n + 3:
                break
        return urls
    except Exception as e:
        return []


@app.route("/api/cuisineaz", methods=["GET"])
def cuisineaz():
    """
    GET /api/cuisineaz?q=tarte+citron&n=2
    GET /api/cuisineaz?category=dessert&n=3
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
        resp = __import__("flask").jsonify({"error": "Paramètre requis : q ou category"})
        resp.status_code = 400
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    if not urls:
        from flask import jsonify
        resp = jsonify({
            "source": "cuisineaz",
            "count": 0,
            "recipes": [],
            "message": f"Aucune recette trouvée pour '{q or category}'",
            "context_for_ai": "Aucune recette trouvée.",
        })
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    from flask import jsonify
    recipes = []
    for url in urls[:n]:
        r = scrape_url(url, source_site="cuisineaz.com")
        if "error" not in r and r.get("title") and r.get("ingredients"):
            recipes.append(r)

    resp = jsonify({
        "source":         "cuisineaz",
        "query":          q or category,
        "page":           page,
        "count":          len(recipes),
        "recipes":        recipes,
        "context_for_ai": build_ai_context(recipes),
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


if __name__ == "__main__":
    app.run(port=5003, debug=True)
