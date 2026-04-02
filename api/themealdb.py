"""
api/themealdb.py — GET /api/themealdb?q=chocolate+cake&n=1&lang=fr
=====================================================================
Source 1 : TheMealDB (https://www.themealdb.com/api.php)
✅ Gratuit, sans clé API, 5000+ recettes internationales.
✅ API officielle stable.
✅ Images incluses.

Params :
  q        — Terme de recherche (ex: "chicken", "pasta")
  category — Catégorie MealDB (ex: "Dessert", "Seafood", "Pasta")
  random   — "1" pour obtenir une recette aléatoire
  n        — Nombre de recettes (max: 5)
  lang     — "fr" (les données sont en anglais, traduction indicative dans les tags)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import requests as req
from flask import Flask, request, jsonify
from utils import make_recipe, error_response, build_ai_context

app = Flask(__name__)

BASE = "https://www.themealdb.com/api/json/v1/1"

# Correspondances catégories FR/EN → TheMealDB (catégories exactes TheMealDB)
CATEGORY_MAP_FR = {
    # ── FRANÇAIS ──────────────────────────────────────────────
    "dessert":          "Dessert",
    "desserts":         "Dessert",
    "gateau":           "Dessert",
    "gâteau":           "Dessert",
    "biscuit":          "Dessert",
    "tarte":            "Dessert",
    "glace":            "Dessert",
    "patisserie":       "Dessert",
    "pâtisserie":       "Dessert",
    "poisson":          "Seafood",
    "fruits-de-mer":    "Seafood",
    "fruitsdelaimer":   "Seafood",
    "poulet":           "Chicken",
    "volaille":         "Chicken",
    "boeuf":            "Beef",
    "bœuf":             "Beef",
    "veau":             "Beef",
    "agneau":           "Lamb",
    "mouton":           "Lamb",
    "porc":             "Pork",
    "jambon":           "Pork",
    "pasta":            "Pasta",
    "pates":            "Pasta",
    "pâtes":            "Pasta",
    "vegetarien":       "Vegetarian",
    "végétarien":       "Vegetarian",
    "vegan":            "Vegan",
    "végétalien":       "Vegan",
    "soupe":            "Starter",
    "veloute":          "Starter",
    "velouté":          "Starter",
    "salade":           "Side",
    "salades":          "Side",
    "accompagnement":   "Side",
    "garniture":        "Side",
    "petit-dejeuner":   "Breakfast",
    "petitdejeuner":    "Breakfast",
    "brunch":           "Breakfast",
    "entree":           "Starter",
    "entrée":           "Starter",
    "cote":             "Side",
    "chevre":           "Goat",
    "chèvre":           "Goat",
    "miscellanees":     "Miscellaneous",
    "divers":           "Miscellaneous",
    # ── ANGLAIS ───────────────────────────────────────────────
    "beef":             "Beef",
    "chicken":          "Chicken",
    "dessert":          "Dessert",
    "lamb":             "Lamb",
    "miscellaneous":    "Miscellaneous",
    "misc":             "Miscellaneous",
    "pork":             "Pork",
    "seafood":          "Seafood",
    "side":             "Side",
    "sides":            "Side",
    "starter":          "Starter",
    "starters":         "Starter",
    "appetizer":        "Starter",
    "appetizers":       "Starter",
    "vegetarian":       "Vegetarian",
    "breakfast":        "Breakfast",
    "goat":             "Goat",
    # Pluriels et variantes EN
    "cakes":            "Dessert",
    "cake":             "Dessert",
    "cookies":          "Dessert",
    "cookie":           "Dessert",
    "pies":             "Dessert",
    "pie":              "Dessert",
    "icecream":         "Dessert",
    "ice cream":        "Dessert",
    "pastry":           "Dessert",
    "pastries":         "Dessert",
    "fish":             "Seafood",
    "shrimp":           "Seafood",
    "prawns":           "Seafood",
    "salmon":           "Seafood",
    "tuna":             "Seafood",
    "turkey":           "Chicken",
    "duck":             "Chicken",
    "noodles":          "Pasta",
    "spaghetti":        "Pasta",
    "lasagna":          "Pasta",
    "lasagne":          "Pasta",
    "salad":            "Side",
    "salads":           "Side",
    "sidedish":         "Side",
    "side dish":        "Side",
    "side dishes":      "Side",
    "soup":             "Starter",
    "soups":            "Starter",
    "pork":             "Pork",
    "ribs":             "Pork",
    "bacon":            "Pork",
    "ham":              "Pork",
    "lamb":             "Lamb",
    "mutton":           "Lamb",
    "eggs":             "Breakfast",
    "pancakes":         "Breakfast",
    "waffles":          "Breakfast",
    "lunch":            "Miscellaneous",
    "dinner":           "Miscellaneous",
    "supper":           "Miscellaneous",
    "main course":      "Miscellaneous",
    "main":             "Miscellaneous",
    "main dish":        "Miscellaneous",
    "mains":            "Miscellaneous",
    "snack":            "Miscellaneous",
    "snacks":           "Miscellaneous",
    "comfort food":     "Miscellaneous",
    "quick":            "Miscellaneous",
    "easy":             "Miscellaneous",
    "healthy":          "Vegetarian",
    "vegan":            "Vegan",
    "gluten free":      "Miscellaneous",
    "low carb":         "Miscellaneous",
    "high protein":     "Chicken",
    "finger food":           "Starter",
    "party food":            "Starter",
    "dips":                  "Starter",
    "appetizer finger food": "Starter",
    "breakfast brunch":      "Breakfast",
    "healthy breakfast idea":"Breakfast",
    "healthy breakfast ideas":"Breakfast",
    "pancake waffles":       "Breakfast",
    "smoothies":             "Breakfast",
    "smoothie":              "Breakfast",
    "cakes pastries":        "Dessert",
    "pastries":              "Dessert",
    "light dessert":         "Dessert",
    "quick dessert":         "Dessert",
    "pasta rice":            "Pasta",
    "rice":                  "Pasta",
    "fish seafood":          "Seafood",
    "fresh salad":           "Side",
    "salads":                "Side",
    "meat dishes":           "Beef",
    "meat":                  "Beef",
    "main courses":          "Miscellaneous",
    "mains courses":         "Miscellaneous",
    "meals planning ideas":  "Miscellaneous",
    "meal planning":         "Miscellaneous",
    "international cuisine": "Miscellaneous",
    "world cuisine":         "Miscellaneous",
    "cooking technique":     "Miscellaneous",
    "nutrition tips":        "Vegetarian",
    "nutritions tips":       "Vegetarian",   # typo category (avec s)
    "easy weekday meals":    "Miscellaneous",
    "easy weekday":          "Miscellaneous", # normalize supprime 'meals'
    "ready in 15 minutes":   "Miscellaneous",
    "low calorie meals":     "Vegetarian",
    "low calorie":           "Vegetarian",
    "gluten free recipe":    "Miscellaneous",
    "gluten free receipe":   "Miscellaneous",
    "healthy recipe":        "Vegetarian",
    "healthy receipe":       "Vegetarian",
    "healthy breakfast idea":  "Breakfast",
    "healthy breakfast ideas": "Breakfast",
    "healthy breakfast":     "Breakfast",    # normalize supprime 'idea'
    "appetizer finger food": "Starter",
    "appetizer finger":      "Starter",      # normalize supprime 'food'
    "meals planning ideas":  "Miscellaneous",
    "meals planning":        "Miscellaneous", # normalize supprime 'ideas'
}


def _parse_meal(meal):
    """Transforme un objet TheMealDB en recette standard."""
    # Ingrédients : strIngredient1..20 + strMeasure1..20
    ingredients = []
    for i in range(1, 21):
        ingredient = (meal.get(f"strIngredient{i}") or "").strip()
        measure    = (meal.get(f"strMeasure{i}") or "").strip()
        if ingredient:
            line = f"{measure} {ingredient}".strip() if measure else ingredient
            ingredients.append(line)

    # Étapes (strInstructions : texte libre avec '\r\n')
    raw_steps = meal.get("strInstructions", "") or ""
    steps = []
    for line in raw_steps.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        # Supprimer lignes vides et fausses numérotations
        if line and len(line) > 5:
            # Supprimer numéro de début s'il y en a
            line = __import__("re").sub(r'^STEP\s*\d+\s*', '', line, flags=__import__("re").IGNORECASE).strip()
            if line:
                steps.append(line)

    tags_raw = meal.get("strTags", "") or ""
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    return make_recipe(
        title=meal.get("strMeal", ""),
        description="",
        prep_time="",
        cook_time="",
        total_time="",
        servings="",
        ingredients=ingredients,
        steps=steps,
        image=meal.get("strMealThumb", ""),
        url=meal.get("strSource", f"https://www.themealdb.com/meal/{meal.get('idMeal','')}"),
        source_site="themealdb.com",
        source_type="api",
        category=meal.get("strCategory", ""),
        tags=tags,
    )


def search_by_name(query, n=3):
    """Cherche des recettes par nom."""
    try:
        r = req.get(f"{BASE}/search.php?s={query}", timeout=10)
        r.raise_for_status()
        meals = r.json().get("meals") or []
        return [_parse_meal(m) for m in meals[:n]]
    except Exception as e:
        return [error_response(str(e))]


def search_by_category(category_en, n=5):
    """Liste les recettes d'une catégorie, puis récupère les détails."""
    try:
        r = req.get(f"{BASE}/filter.php?c={category_en}", timeout=10)
        r.raise_for_status()
        meals = r.json().get("meals") or []
        results = []
        import random
        random.shuffle(meals)
        for m in meals[:n]:
            meal_id = m.get("idMeal")
            detail_r = req.get(f"{BASE}/lookup.php?i={meal_id}", timeout=10)
            detail_r.raise_for_status()
            detail_meals = detail_r.json().get("meals") or []
            if detail_meals:
                results.append(_parse_meal(detail_meals[0]))
            if len(results) >= n:
                break
        return results
    except Exception as e:
        return [error_response(str(e))]


def get_random():
    """Retourne une recette aléatoire."""
    try:
        r = req.get(f"{BASE}/random.php", timeout=10)
        r.raise_for_status()
        meals = r.json().get("meals") or []
        if meals:
            return [_parse_meal(meals[0])]
        return [error_response("Aucune recette aléatoire disponible")]
    except Exception as e:
        return [error_response(str(e))]


@app.route("/api/themealdb", methods=["GET"])
def themealdb():
    """
    GET /api/themealdb?q=pasta&n=2
    GET /api/themealdb?category=dessert&n=3
    GET /api/themealdb?random=1
    """
    q        = request.args.get("q", "")
    category = request.args.get("category", "")
    is_rand  = request.args.get("random", "0") == "1"
    n        = min(int(request.args.get("n", 1)), 5)

    if is_rand:
        recipes = get_random()
    elif q:
        recipes = search_by_name(q, n)
    elif category:
        cat_key = category.lower().replace("-", "")
        cat_en  = CATEGORY_MAP_FR.get(cat_key, category)
        recipes = search_by_category(cat_en, n)
    else:
        resp = jsonify({"error": "Paramètre requis : q, category, ou random=1"})
        resp.status_code = 400
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    # Filtrer les erreurs
    good   = [r for r in recipes if "error" not in r]
    errors = [r for r in recipes if "error" in r]

    resp = jsonify({
        "source":   "themealdb",
        "count":    len(good),
        "recipes":  good,
        "errors":   errors,
        "context_for_ai": build_ai_context(good),
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


if __name__ == "__main__":
    app.run(port=5001, debug=True)
