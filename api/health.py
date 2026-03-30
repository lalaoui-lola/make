"""
api/health.py — GET /api/health
================================
Vérifie que le serveur tourne et liste tous les endpoints disponibles.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/api/health", methods=["GET"])
def health():
    resp = jsonify({
        "status":  "ok",
        "service": "recipe-scraper-v4",
        "version": "4.0.0",
        "sources": {
            "themealdb":  "✅ Gratuit, sans clé — 5000+ recettes internationales",
            "750g":       "✅ Gratuit, scraping — recettes françaises",
            "cuisineaz":  "✅ Gratuit, scraping — recettes françaises",
            "ptitchef":   "✅ Gratuit, scraping — recettes françaises communautaires",
            "edamam":     "🔑 Clé optionnelle (1500 req/mois) — https://developer.edamam.com",
            "spoonacular":"🔑 Clé optionnelle (150 req/jour) — https://spoonacular.com/food-api",
        },
        "endpoints": {
            "recipe":      "/api/recipe?q=gateau+chocolat&n=1       ← ENDPOINT PRINCIPAL (auto-cascade)",
            "recipe_cat":  "/api/recipe?category=dessert&n=2",
            "recipe_src":  "/api/recipe?q=tarte+citron&source=750g  ← Source spécifique",
            "themealdb":   "/api/themealdb?q=chocolate+cake&n=2",
            "themealdb_c": "/api/themealdb?category=dessert&n=3",
            "themealdb_r": "/api/themealdb?random=1",
            "750g":        "/api/750g?q=gateau+chocolat&n=2",
            "cuisineaz":   "/api/cuisineaz?q=tarte+citron&n=2",
            "ptitchef":    "/api/ptitchef?q=poulet+roti&n=2",
            "edamam":      "/api/edamam?q=chocolate+cake&n=2   ← Clé requise",
            "spoonacular": "/api/spoonacular?q=tarte&n=2        ← Clé requise",
            "health":      "/api/health",
        },
        "env_vars_optional": {
            "EDAMAM_APP_ID":      "ID compte Edamam (gratuit)",
            "EDAMAM_APP_KEY":     "Clé API Edamam (gratuite)",
            "SPOONACULAR_API_KEY":"Clé API Spoonacular (gratuite)",
        },
        "make_com_usage": {
            "endpoint_recommande": "/api/recipe?q={{titre_recette}}&n=1&source=auto",
            "par_categorie":       "/api/recipe?category={{slug_categorie}}&n=1&source=auto",
            "source_forcee":       "/api/recipe?q={{titre}}&source=themealdb",
        }
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


if __name__ == "__main__":
    app.run(port=5099, debug=True)
