"""
api/spoonacular.py — GET /api/spoonacular?q=gateau+chocolat&n=2
=================================================================
Source 6 : Spoonacular API
✅ 150 recettes/jour GRATUITES.
✅ Recettes complètes avec étapes.
✅ Clé API requise (gratuite sur spoonacular.com).

Inscription gratuite : https://spoonacular.com/food-api

Variable d'environnement Vercel :
  SPOONACULAR_API_KEY — ex: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

Params :
  q        — Terme de recherche
  category — Catégorie / type de plat
  n        — Nombre de résultats (max: 5)
  lang     — Langue (fr ou en, défaut: fr)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import requests as req
from flask import Flask, request, jsonify
from utils import make_recipe, build_ai_context, error_response

app = Flask(__name__)

SPOON_BASE   = "https://api.spoonacular.com/recipes"
_DEFAULT_KEY = "12534348bd9348a7ab9d3fc037afe38f"


def _get_key():
    return os.environ.get("SPOONACULAR_API_KEY", _DEFAULT_KEY)


# Mapping catégories FR → type de plat Spoonacular
TYPE_MAP = {
    "entree":         "appetizer",
    "plat":           "main course",
    "plat-principal": "main course",
    "dessert":        "dessert",
    "gateau":         "dessert",
    "tarte":          "dessert",
    "soupe":          "soup",
    "salade":         "salad",
    "pasta":          "main course",
    "pates":          "main course",
    "poisson":        "main course",
    "viande":         "main course",
    "poulet":         "main course",
    "vegetarien":     "main course",
    "pain":           "bread",
    "aperitif":       "appetizer",
    "sauce":          "sauce",
    "petit-dejeuner": "breakfast",
    "biscuit":        "snack",
}


def _parse_recipe(data, steps_data=None):
    """Transforme une réponse Spoonacular en recette standard."""
    ingredients = [
        ing.get("original", "").strip()
        for ing in data.get("extendedIngredients", [])
        if ing.get("original", "").strip()
    ]

    steps = []
    if steps_data and isinstance(steps_data, list):
        for section in steps_data:
            for step in section.get("steps", []):
                t = step.get("step", "").strip()
                if t:
                    steps.append(t)

    prep_min = data.get("preparationMinutes")
    cook_min = data.get("cookingMinutes")
    total_min = data.get("readyInMinutes")

    return make_recipe(
        title=data.get("title", ""),
        description=data.get("summary", "").replace("<b>", "").replace("</b>", "")[:400] if data.get("summary") else "",
        prep_time=f"{prep_min}min" if prep_min and prep_min > 0 else "",
        cook_time=f"{cook_min}min" if cook_min and cook_min > 0 else "",
        total_time=f"{total_min}min" if total_min else "",
        servings=str(data.get("servings", "")),
        ingredients=ingredients,
        steps=steps,
        image=data.get("image", ""),
        url=data.get("sourceUrl", ""),
        source_site="spoonacular.com",
        source_type="api",
        category=", ".join(data.get("dishTypes", [])),
        tags=data.get("diets", []) + data.get("dishTypes", []),
    )


def search_recipes(query, n=3, meal_type=""):
    """Fonction standalone — appelable depuis app.py."""
    api_key = _get_key()
    try:
        params = {
            "apiKey": api_key, "number": n,
            "addRecipeInformation": True, "fillIngredients": True,
            "query": query,
        }
        if meal_type:
            params["type"] = meal_type
        r = req.get(f"{SPOON_BASE}/complexSearch", params=params, timeout=15)
        r.raise_for_status()
        results = r.json().get("results", [])
        recipes = []
        for item in results[:n]:
            recipe = _parse_recipe(item, [])
            if recipe.get("title") and recipe.get("ingredients"):
                recipes.append(recipe)
        return recipes
    except Exception:
        return []


def search_by_category(category, n=3):
    """Recherche par catégorie FR/EN — standalone."""
    cat_slug = category.lower().replace("-", "").replace(" ", "")
    meal_type = TYPE_MAP.get(cat_slug, "")
    query = category if not meal_type else ""
    return search_recipes(query, n=n, meal_type=meal_type)


@app.route("/api/spoonacular", methods=["GET"])
def spoonacular():
    """
    GET /api/spoonacular?q=gateau+chocolat&n=2
    GET /api/spoonacular?category=dessert&n=3

    Nécessite SPOONACULAR_API_KEY en variable d'environnement.
    """
    api_key = os.environ.get("SPOONACULAR_API_KEY", "")

    if not api_key:
        resp = jsonify({
            "error": "Clé Spoonacular manquante. Inscrivez-vous sur https://spoonacular.com/food-api et configurez SPOONACULAR_API_KEY dans les variables Vercel.",
            "signup_url": "https://spoonacular.com/food-api",
            "free_plan": "150 requêtes / jour",
        })
        resp.status_code = 503
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    q        = request.args.get("q", "")
    category = request.args.get("category", "")
    n        = min(int(request.args.get("n", 1)), 5)
    lang     = request.args.get("lang", "fr")

    if not q and not category:
        resp = jsonify({"error": "Paramètre requis : q ou category"})
        resp.status_code = 400
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    # Construire la recherche
    search_params = {
        "apiKey": api_key,
        "number": n,
        "addRecipeInformation": True,
        "fillIngredients": True,
        "language": lang,
    }
    if q:
        search_params["query"] = q
    if category:
        slug = category.lower().replace("-", "")
        search_params["type"] = TYPE_MAP.get(slug, "main course")

    try:
        r_search = req.get(f"{SPOON_BASE}/complexSearch", params=search_params, timeout=15)
        r_search.raise_for_status()
        results = r_search.json().get("results", [])
    except req.exceptions.HTTPError as e:
        if r_search.status_code == 402:
            err = "Quota Spoonacular dépassé (150/jour). Revenez demain ou passez à un plan payant."
        elif r_search.status_code == 401:
            err = "Clé Spoonacular invalide."
        else:
            err = f"Erreur Spoonacular : {e}"
        resp = jsonify({"error": err})
        resp.status_code = 502
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as e:
        resp = jsonify({"error": str(e)})
        resp.status_code = 500
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    if not results:
        resp = jsonify({
            "source": "spoonacular",
            "count": 0,
            "recipes": [],
            "message": f"Aucune recette Spoonacular pour '{q or category}'.",
            "context_for_ai": "Aucune recette trouvée.",
        })
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    # Récupérer les étapes pour chaque recette
    recipes = []
    for item in results[:n]:
        recipe_id = item.get("id")
        steps_data = []
        try:
            r_steps = req.get(
                f"{SPOON_BASE}/{recipe_id}/analyzedInstructions",
                params={"apiKey": api_key},
                timeout=10,
            )
            r_steps.raise_for_status()
            steps_data = r_steps.json()
        except Exception:
            pass  # Les étapes sont optionnelles

        recipe = _parse_recipe(item, steps_data)
        if recipe.get("title") and recipe.get("ingredients"):
            recipes.append(recipe)

    resp = jsonify({
        "source":         "spoonacular",
        "query":          q or category,
        "count":          len(recipes),
        "recipes":        recipes,
        "context_for_ai": build_ai_context(recipes),
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


if __name__ == "__main__":
    app.run(port=5006, debug=True)
