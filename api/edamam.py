"""
api/edamam.py — GET /api/edamam?q=chocolate+cake&n=2
======================================================
Source 5 : Edamam Recipe Search API
✅ API officielle — 1 500 requêtes/mois GRATUITES.
✅ Données nutritionnelles incluses.
✅ Recettes en anglais (GPT traduira).
✅ Clé API OPTIONNELLE (sans clé = erreur 401 — il faut s'inscrire sur edamam.com).

Inscription gratuite : https://developer.edamam.com/edamam-recipe-api

Variables d'environnement à définir sur Vercel :
  EDAMAM_APP_ID  — ex: "a1b2c3d4"
  EDAMAM_APP_KEY — ex: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

Params :
  q        — Terme de recherche (en anglais ou français)
  category — Catégorie (ex: "dessert", "chicken", "pasta")
  n        — Nombre de résultats (max: 5)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import requests as req
from flask import Flask, request, jsonify
from utils import make_recipe, build_ai_context, error_response

app = Flask(__name__)

EDAMAM_BASE = "https://api.edamam.com/api/recipes/v2"

# Mapping catégories FR → meal type Edamam
MEALTYPE_MAP = {
    "petit-dejeuner": "breakfast",
    "dejeuner":       "lunch",
    "diner":          "dinner",
    "snack":          "snack",
    "aperitif":       "snack",
}

DISHTYPE_MAP = {
    "dessert":        "desserts",
    "gateau":         "desserts",
    "tarte":          "pie",
    "soupe":          "soups",
    "salade":         "salad",
    "pasta":          "pasta",
    "pates":          "pasta",
    "pain":           "bread",
    "sandwich":       "sandwich",
    "sauce":          "condiments and sauces",
    "biscuit":        "cookies",
    "pizza":          "pizza",
    "omelette":       "egg",
}

CUISINE_MAP = {
    "francaise": "French",
    "italiana":  "Italian",
    "mexicaine": "Mexican",
    "asiatique": "Asian",
    "americaine":"American",
}


def _parse_hit(hit):
    """Transforme un résultat Edamam en recette standard."""
    recipe = hit.get("recipe", {})

    ingredients = [
        line.get("text", "").strip()
        for line in recipe.get("ingredients", [])
        if line.get("text", "").strip()
    ]

    # Edamam ne fournit pas les étapes — juste l'URL source
    source_url = recipe.get("url", "")
    steps = []  # On renverra l'URL source pour scraping ultérieur si besoin

    tags = recipe.get("dishType", []) + recipe.get("mealType", []) + recipe.get("cuisineType", [])

    return make_recipe(
        title=recipe.get("label", ""),
        description="",
        prep_time="",
        cook_time=f"{int(recipe.get('totalTime', 0))}min" if recipe.get("totalTime") else "",
        total_time=f"{int(recipe.get('totalTime', 0))}min" if recipe.get("totalTime") else "",
        servings=str(int(recipe.get("yield", ""))),
        ingredients=ingredients,
        steps=steps,
        image=recipe.get("image", ""),
        url=source_url,
        source_site="edamam.com",
        source_type="api",
        category=", ".join(recipe.get("dishType", [])),
        tags=tags,
    )


@app.route("/api/edamam", methods=["GET"])
def edamam():
    """
    GET /api/edamam?q=chocolate+cake&n=2
    GET /api/edamam?category=dessert&n=3

    Nécessite EDAMAM_APP_ID et EDAMAM_APP_KEY en variables d'environnement.
    Sans clé → retourne un message d'erreur explicite.
    """
    app_id  = os.environ.get("EDAMAM_APP_ID", "")
    app_key = os.environ.get("EDAMAM_APP_KEY", "")

    if not app_id or not app_key:
        resp = jsonify({
            "error": "Clés Edamam manquantes. Inscrivez-vous sur https://developer.edamam.com et configurez EDAMAM_APP_ID + EDAMAM_APP_KEY dans les variables d'environnement Vercel.",
            "signup_url": "https://developer.edamam.com/edamam-recipe-api",
            "free_plan": "1 500 requêtes / mois",
        })
        resp.status_code = 503
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    q        = request.args.get("q", "")
    category = request.args.get("category", "")
    n        = min(int(request.args.get("n", 1)), 5)

    if not q and not category:
        resp = jsonify({"error": "Paramètre requis : q ou category"})
        resp.status_code = 400
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    params = {
        "type":    "public",
        "app_id":  app_id,
        "app_key": app_key,
    }

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

    try:
        resp_api = req.get(EDAMAM_BASE, params=params, timeout=15)
        resp_api.raise_for_status()
        data = resp_api.json()
    except req.exceptions.HTTPError as e:
        if resp_api.status_code == 401:
            resp = jsonify({"error": "Clés Edamam invalides. Vérifiez EDAMAM_APP_ID et EDAMAM_APP_KEY."})
        else:
            resp = jsonify({"error": f"Erreur Edamam API : {e}"})
        resp.status_code = 502
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as e:
        resp = jsonify({"error": str(e)})
        resp.status_code = 500
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    hits    = data.get("hits", [])[:n]
    recipes = [_parse_hit(h) for h in hits]
    good    = [r for r in recipes if "error" not in r and r.get("title")]

    resp = jsonify({
        "source":         "edamam",
        "query":          q or category,
        "count":          len(good),
        "recipes":        good,
        "context_for_ai": build_ai_context(good),
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


if __name__ == "__main__":
    app.run(port=5005, debug=True)
