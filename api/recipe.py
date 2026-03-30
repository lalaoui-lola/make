"""
api/recipe.py — GET /api/recipe?q=gateau+chocolat&n=1&source=auto
===================================================================
Endpoint UNIFIÉ — essaie les sources dans l'ordre jusqu'à obtenir une recette.

Ordre de priorité (configurable via &source=) :
  1. themealdb  — API gratuite, sans clé, 5000+ recettes
  2. 750g       — Scraper français fiable (JSON-LD)
  3. cuisineaz  — Scraper français fiable (JSON-LD)
  4. ptitchef   — Scraper français communautaire
  5. edamam     — API officielle (clé optionnelle, 1500/mois)
  6. spoonacular — API officielle (clé optionnelle, 150/jour)

Params :
  q        — Terme de recherche (ex: "gateau chocolat")
  category — Catégorie (ex: "dessert", "plat-principal")
  n        — Nombre de recettes (défaut: 1, max: 3)
  source   — Source spécifique : "themealdb" | "750g" | "cuisineaz" |
             "ptitchef" | "edamam" | "spoonacular" | "auto" (défaut)
  lang     — Langue: "fr" | "en" (défaut: fr)

Retourne le format standard :
  {
    "source_used": "750g",
    "query": "gateau chocolat",
    "count": 1,
    "recipes": [...],
    "context_for_ai": "=== RECETTE SOURCE 1 ==="
  }
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import requests as req
from flask import Flask, request, jsonify
from utils import build_ai_context

# Import des fonctions de chaque source
from themealdb import search_by_name as mdb_search, search_by_category as mdb_cat, CATEGORY_MAP_FR
from source_750g import _search_urls as g750_search_urls, _list_category_urls as g750_cat_urls, _scrape_recipe as g750_scrape
from cuisineaz import _search_urls as caz_search_urls, _list_category_urls as caz_cat_urls
from ptitchef import _search_urls as ptit_search_urls, _list_category_urls as ptit_cat_urls
from utils import scrape_url

app = Flask(__name__)

# Traduction FR → EN pour TheMealDB (qui ne supporte que l'anglais)
_FR_TO_EN = {
    "gateau": "cake", "gâteau": "cake", "chocolat": "chocolate",
    "tarte": "tart", "citron": "lemon", "fraise": "strawberry",
    "framboise": "raspberry", "pomme": "apple", "poire": "pear",
    "cerise": "cherry", "poulet": "chicken", "bœuf": "beef",
    "boeuf": "beef", "agneau": "lamb", "porc": "pork",
    "saumon": "salmon", "poisson": "fish", "crevette": "shrimp",
    "pates": "pasta", "pâtes": "pasta", "riz": "rice",
    "soupe": "soup", "salade": "salad", "pain": "bread",
    "fromage": "cheese", "oeuf": "egg", "œuf": "egg",
    "oeufs": "eggs", "œufs": "eggs", "vanille": "vanilla",
    "caramel": "caramel", "noix": "walnut", "amande": "almond",
    "noisette": "hazelnut", "banane": "banana", "mangue": "mango",
    "ananas": "pineapple", "coco": "coconut", "curry": "curry",
    "tomate": "tomato", "champignon": "mushroom", "oignon": "onion",
    "ail": "garlic", "roti": "roast", "rôti": "roast",
    "crepe": "crepe", "crêpe": "crepe", "mousse": "mousse",
    "fondant": "fondant", "brownie": "brownie", "cookie": "cookie",
    "pizza": "pizza", "lasagne": "lasagne", "risotto": "risotto",
    "burger": "burger",
}

def _translate_fr_en(q):
    words = q.lower().split()
    return " ".join(_FR_TO_EN.get(w, w) for w in words)


# ============================================================
# FONCTIONS PAR SOURCE
# ============================================================

def _get_from_themealdb(q, category, n, lang):
    if category:
        cat_en = CATEGORY_MAP_FR.get(category.lower().replace("-", ""), category)
        results = mdb_cat(cat_en, n)
    else:
        results = mdb_search(q, n)
        if not [r for r in results if "error" not in r and r.get("title")]:
            q_en = _translate_fr_en(q)
            if q_en != q:
                results = mdb_search(q_en, n)
    return [r for r in results if "error" not in r and r.get("title") and r.get("ingredients")]


def _get_from_scraper(search_fn, cat_fn, scrape_fn, q, category, n, page, source_site):
    if q:
        urls = search_fn(q, page=page, n=n)
    elif category:
        urls = cat_fn(category, page=page, n=n)
    else:
        return []

    recipes = []
    for url in (urls or [])[:n]:
        r = scrape_fn(url) if scrape_fn else scrape_url(url, source_site=source_site)
        if "error" not in r and r.get("title") and r.get("ingredients"):
            recipes.append(r)
    return recipes


def _get_from_api_endpoint(endpoint_path, q, category, n, extra_params=None):
    """Appel interne vers un sous-endpoint API (edamam, spoonacular)."""
    # Sur Vercel, les sous-appels ne fonctionnent pas — on importe directement
    # Cette fonction est utilisée uniquement si les imports directs échouent
    return []


def _get_from_edamam(q, category, n):
    try:
        from edamam import _parse_hit, MEALTYPE_MAP, DISHTYPE_MAP
        import os
        app_id  = os.environ.get("EDAMAM_APP_ID", "")
        app_key = os.environ.get("EDAMAM_APP_KEY", "")
        if not app_id or not app_key:
            return []

        params = {"type": "public", "app_id": app_id, "app_key": app_key}
        if q:
            params["q"] = q
        if category:
            slug = category.lower().replace("-", "")
            if slug in MEALTYPE_MAP:
                params["mealType"] = MEALTYPE_MAP[slug]
            elif slug in DISHTYPE_MAP:
                params["dishType"] = DISHTYPE_MAP[slug]
            else:
                params["q"] = category

        r = req.get("https://api.edamam.com/api/recipes/v2", params=params, timeout=15)
        r.raise_for_status()
        hits = r.json().get("hits", [])[:n]
        return [_parse_hit(h) for h in hits if "error" not in _parse_hit(h)]
    except Exception:
        return []


def _get_from_spoonacular(q, category, n, lang):
    try:
        from spoonacular import _parse_recipe, TYPE_MAP
        import os
        api_key = os.environ.get("SPOONACULAR_API_KEY", "")
        if not api_key:
            return []

        BASE = "https://api.spoonacular.com/recipes"
        params = {
            "apiKey": api_key,
            "number": n,
            "addRecipeInformation": True,
            "fillIngredients": True,
            "language": lang,
        }
        if q:
            params["query"] = q
        if category:
            slug = category.lower().replace("-", "")
            params["type"] = TYPE_MAP.get(slug, "main course")

        r = req.get(f"{BASE}/complexSearch", params=params, timeout=15)
        r.raise_for_status()
        results = r.json().get("results", [])

        recipes = []
        for item in results[:n]:
            steps_data = []
            try:
                rs = req.get(
                    f"{BASE}/{item['id']}/analyzedInstructions",
                    params={"apiKey": api_key},
                    timeout=10,
                )
                steps_data = rs.json()
            except Exception:
                pass
            recipe = _parse_recipe(item, steps_data)
            if recipe.get("title") and recipe.get("ingredients"):
                recipes.append(recipe)
        return recipes
    except Exception:
        return []


# ============================================================
# ENDPOINT PRINCIPAL
# ============================================================

@app.route("/api/recipe", methods=["GET"])
def recipe():
    """
    GET /api/recipe?q=gateau+chocolat&n=1
    GET /api/recipe?category=dessert&n=2&source=750g
    GET /api/recipe?q=pasta&source=auto
    """
    q        = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    n        = min(int(request.args.get("n", 1)), 3)
    source   = request.args.get("source", "auto").lower()
    lang     = request.args.get("lang", "fr")
    page     = int(request.args.get("page", 1))

    if not q and not category:
        resp = jsonify({
            "error": "Paramètre requis : q (recherche) ou category (catégorie)",
            "examples": [
                "/api/recipe?q=gateau+chocolat",
                "/api/recipe?category=dessert",
                "/api/recipe?q=tarte+citron&source=750g",
            ],
        })
        resp.status_code = 400
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    recipes     = []
    source_used = "none"

    # ---- Source spécifique demandée ----
    if source == "themealdb":
        recipes = _get_from_themealdb(q, category, n, lang)
        source_used = "themealdb"

    elif source == "750g":
        recipes = _get_from_scraper(
            g750_search_urls, g750_cat_urls, g750_scrape,
            q, category, n, page, "750g.com"
        )
        source_used = "750g"

    elif source == "cuisineaz":
        recipes = _get_from_scraper(
            caz_search_urls, caz_cat_urls, None,
            q, category, n, page, "cuisineaz.com"
        )
        source_used = "cuisineaz"

    elif source == "ptitchef":
        recipes = _get_from_scraper(
            ptit_search_urls, ptit_cat_urls, None,
            q, category, n, page, "ptitchef.com"
        )
        source_used = "ptitchef"

    elif source == "edamam":
        recipes = _get_from_edamam(q, category, n)
        source_used = "edamam"

    elif source == "spoonacular":
        recipes = _get_from_spoonacular(q, category, n, lang)
        source_used = "spoonacular"

    # ---- Mode auto : cascade de sources ----
    else:
        # 1. TheMealDB (toujours disponible, sans clé)
        recipes = _get_from_themealdb(q, category, n, lang)
        if recipes:
            source_used = "themealdb"

        # 2. 750g (scraping JSON-LD fiable)
        if not recipes:
            recipes = _get_from_scraper(
                g750_search_urls, g750_cat_urls, g750_scrape,
                q, category, n, page, "750g.com"
            )
            if recipes:
                source_used = "750g"

        # 3. CuisineAZ
        if not recipes:
            recipes = _get_from_scraper(
                caz_search_urls, caz_cat_urls, None,
                q, category, n, page, "cuisineaz.com"
            )
            if recipes:
                source_used = "cuisineaz"

        # 4. Ptitchef
        if not recipes:
            recipes = _get_from_scraper(
                ptit_search_urls, ptit_cat_urls, None,
                q, category, n, page, "ptitchef.com"
            )
            if recipes:
                source_used = "ptitchef"

        # 5. Edamam (si clé disponible)
        if not recipes:
            recipes = _get_from_edamam(q, category, n)
            if recipes:
                source_used = "edamam"

        # 6. Spoonacular (si clé disponible)
        if not recipes:
            recipes = _get_from_spoonacular(q, category, n, lang)
            if recipes:
                source_used = "spoonacular"

    resp = jsonify({
        "source_used":    source_used,
        "query":          q or category,
        "count":          len(recipes),
        "recipes":        recipes,
        "context_for_ai": build_ai_context(recipes),
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


if __name__ == "__main__":
    app.run(port=5000, debug=True)
