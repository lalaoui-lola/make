"""
api/ptitchef.py — GET /api/ptitchef?q=gateau+chocolat&n=2
===========================================================
Source 4 : Ptitchef.com
✅ Site français avec de nombreuses recettes maison.
✅ JSON-LD Recipe sur chaque fiche.
✅ Moteur de recherche simple et accessible.

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
from utils import get_headers, scrape_url, build_ai_context

app = Flask(__name__)

BASE = "https://www.ptitchef.com"

CATEGORIES_PTIT = {
    "entree":         "/recettes/entree",
    "plat":           "/recettes/plat",
    "plat-principal": "/recettes/plat",
    "dessert":        "/recettes/dessert",
    "gateau":         "/recettes/dessert/gateau",
    "tarte":          "/recettes/dessert/tarte",
    "soupe":          "/recettes/entree/soupe",
    "salade":         "/recettes/entree/salade",
    "pates":          "/recettes/plat/pates",
    "pasta":          "/recettes/plat/pates",
    "poisson":        "/recettes/plat/poisson",
    "viande":         "/recettes/plat/viande",
    "poulet":         "/recettes/plat/volaille",
    "vegetarien":     "/recettes/plat/vegetarien",
    "pain":           "/recettes/pain-et-viennoiserie",
    "aperitif":       "/recettes/aperitif",
    "biscuit":        "/recettes/dessert/biscuits-et-cookies",
    "confiture":      "/recettes/dessert/confiture",
    "sauce":          "/recettes/accompagnement/sauce",
}


def _search_urls(query, page=1, n=5):
    """Recherche sur Ptitchef."""
    encoded = urllib.parse.quote(query)
    url = f"{BASE}/recettes/recherche?q={encoded}&page={page}"
    try:
        resp = req.get(url, headers=get_headers(referer=BASE), timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        urls = []
        # Ptitchef : les URLs recettes ont /recettes/XXXX-aid-XXXXXX.html
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "-aid-" in href and href.endswith(".html") and href not in urls:
                full = href if href.startswith("http") else BASE + href
                urls.append(full)
            if len(urls) >= n + 3:
                break
        return urls
    except Exception as e:
        return []


def _list_category_urls(slug, page=1, n=5):
    """Liste les recettes d'une catégorie Ptitchef."""
    path = CATEGORIES_PTIT.get(slug.lower().replace("-", ""), f"/recettes/{slug}")
    url = f"{BASE}{path}?page={page}"
    try:
        resp = req.get(url, headers=get_headers(referer=BASE), timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        urls = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "-aid-" in href and href.endswith(".html") and href not in urls:
                full = href if href.startswith("http") else BASE + href
                urls.append(full)
            if len(urls) >= n + 3:
                break
        return urls
    except Exception as e:
        return []


@app.route("/api/ptitchef", methods=["GET"])
def ptitchef():
    """
    GET /api/ptitchef?q=gateau+chocolat&n=2
    GET /api/ptitchef?category=dessert&n=3
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
            "source": "ptitchef",
            "count": 0,
            "recipes": [],
            "message": f"Aucune recette trouvée pour '{q or category}'",
            "context_for_ai": "Aucune recette trouvée.",
        })
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    recipes = []
    for url in urls[:n]:
        r = scrape_url(url, source_site="ptitchef.com")
        if "error" not in r and r.get("title") and r.get("ingredients"):
            recipes.append(r)

    resp = jsonify({
        "source":         "ptitchef",
        "query":          q or category,
        "page":           page,
        "count":          len(recipes),
        "recipes":        recipes,
        "context_for_ai": build_ai_context(recipes),
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


if __name__ == "__main__":
    app.run(port=5004, debug=True)
