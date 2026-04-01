"""
app.py — Serveur Flask LOCAL pour développement et tests.
Pour la production, utiliser Vercel (api/*.py).

Lancer :  python app.py
Tester :  http://localhost:5000
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

from flask import Flask, request, jsonify, send_from_directory

# Import des handlers de chaque source
from themealdb   import search_by_name as mdb_search, search_by_category as mdb_cat, CATEGORY_MAP_FR, get_random as mdb_random
from source_750g import _search_urls as g750_search, _list_category_urls as g750_cat, _scrape_recipe as g750_scrape
from marmiton    import _search_urls as marm_search, _scrape_recipe as marm_scrape
from spoonacular import search_recipes as spoon_search, search_by_category as spoon_cat
from local_db    import search_by_category as ldb_cat, search_by_query as ldb_query, is_available as ldb_ok
from cuisineaz   import _search_urls as caz_search, _list_category_urls as caz_cat
from ptitchef    import _search_urls as ptit_search, _list_category_urls as ptit_cat
from utils       import build_ai_context, scrape_url

# Dictionnaire de traduction FR → EN pour TheMealDB
FR_TO_EN = {
    "gateau": "cake",
    "gâteau": "cake",
    "chocolat": "chocolate",
    "tarte": "tart",
    "citron": "lemon",
    "fraise": "strawberry",
    "framboise": "raspberry",
    "pomme": "apple",
    "poire": "pear",
    "cerise": "cherry",
    "poulet": "chicken",
    "bœuf": "beef",
    "boeuf": "beef",
    "agneau": "lamb",
    "porc": "pork",
    "saumon": "salmon",
    "poisson": "fish",
    "crevette": "shrimp",
    "pates": "pasta",
    "pâtes": "pasta",
    "riz": "rice",
    "soupe": "soup",
    "salade": "salad",
    "pain": "bread",
    "fromage": "cheese",
    "oeuf": "egg",
    "œuf": "egg",
    "oeufs": "eggs",
    "œufs": "eggs",
    "vanille": "vanilla",
    "caramel": "caramel",
    "noix": "walnut",
    "amande": "almond",
    "noisette": "hazelnut",
    "banane": "banana",
    "mangue": "mango",
    "ananas": "pineapple",
    "coco": "coconut",
    "curry": "curry",
    "tomate": "tomato",
    "courgette": "courgette",
    "aubergine": "aubergine",
    "champignon": "mushroom",
    "oignon": "onion",
    "ail": "garlic",
    "roti": "roast",
    "rôti": "roast",
    "grille": "grilled",
    "grillé": "grilled",
    "frit": "fried",
    "frite": "fries",
    "crepe": "crepe",
    "crêpe": "crepe",
    "quiche": "quiche",
    "mousse": "mousse",
    "fondant": "fondant",
    "brownie": "brownie",
    "cookie": "cookie",
    "muffin": "muffin",
    "pizza": "pizza",
    "lasagne": "lasagne",
    "risotto": "risotto",
    "burger": "burger",
    "sandwich": "sandwich",
}

# Catégories EN sans équivalent TheMealDB → traduction FR pour 750g
CATEGORY_EN_TO_FR_750G = {
    "salad":        "salade",
    "salads":       "salade",
    "soup":         "soupe",
    "soups":        "soupe",
    "pizza":        "pizza",
    "sandwich":     "sandwich",
    "sandwiches":   "sandwich",
    "burger":       "burger",
    "burgers":      "burger",
    "grilling":     "grill",
    "grill":        "grill",
    "bbq":          "barbecue",
    "barbecue":     "barbecue",
    "snack":        "snack",
    "snacks":       "snack",
    "quick":        "rapide",
    "healthy":      "léger",
    "comfort food": "plat réconfortant",
    "casserole":    "gratin",
    "stew":         "ragoût",
    "curry":        "curry",
    "tacos":        "tacos",
    "wraps":        "wrap",
    "dips":         "sauce",
    "sauce":        "sauce",
    "bread":        "pain",
    "muffin":       "muffin",
    "muffins":      "muffin",
    "brownie":      "brownie",
    "brownies":     "brownie",
    "cheesecake":   "cheesecake",
    "mousse":       "mousse",
    "crepe":        "crêpe",
    "crepes":       "crêpe",
    "quiche":       "quiche",
    "risotto":      "risotto",
    "stir fry":     "sauté",
    "stir-fry":     "sauté",
    "lunch":         "déjeuner",
    "breakfast":     "petit-déjeuner",
    "brunch":        "brunch",
    "dinner":        "dîner",
    "supper":        "dîner",
    "appetizer":     "entrée",
    "appetizers":    "entrée",
    "starter":       "entrée",
    "starters":      "entrée",
    "main course":   "plat principal",
    "main":          "plat principal",
    "main dish":     "plat principal",
    "side dish":     "accompagnement",
    "side dishes":   "accompagnement",
    "vegetarian":    "végétarien",
    "vegan":         "vegan",
    "gluten free":   "sans gluten",
    "low carb":      "léger",
    "high protein":  "protéiné",
    "comfort food":  "plat réconfortant",
}


def _normalize_category(cat):
    """Normalise une catégorie : supprime suffixes EN, lowercase, strip."""
    import re as _re
    c = cat.lower().strip()
    # Supprimer suffixes EN courants : " recipes", " dishes", " recipe", " food", " meals"
    c = _re.sub(r'\s+(recipes?|dishes?|meals?|food|ideas?)\s*$', '', c)
    # Remplacer tirets/underscores par espaces
    c = c.replace('-', ' ').replace('_', ' ').strip()
    return c


def _translate_fr_to_en(query):
    """Traduit une requête française en anglais pour TheMealDB."""
    words = query.lower().split()
    translated = [FR_TO_EN.get(w, w) for w in words]
    return " ".join(translated)

app = Flask(__name__, static_folder="public")


def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


# ============================================================
# PAGE D'ACCUEIL
# ============================================================

@app.route("/")
def index():
    return send_from_directory("public", "index.html")


# ============================================================
# /api/health
# ============================================================

@app.route("/api/health")
def health():
    return _cors(jsonify({
        "status": "ok",
        "service": "recipe-scraper-v4",
        "version": "4.0.0",
        "sources": {
            "themealdb":   "✅ Gratuit, sans clé (5000+ recettes EN)",
            "spoonacular": "✅ Clé active (150/jour, 365k recettes EN)",
            "750g":        "✅ Gratuit, scraping FR (50k+ recettes)",
            "marmiton":    "✅ Gratuit, scraping FR (60k+ recettes)",
            "local":       "✅ Base Kaggle locale (2.2M recettes)" if ldb_ok() else "⚠️ Base locale non créée (lancer setup_local_db.py)",
            "cuisineaz":   "⚠️ JS-rendered (désactivé)",
            "ptitchef":    "⚠️ JS-rendered (désactivé)",
        },
        "endpoints": {
            "recipe":     "/api/recipe?q=gateau+chocolat",
            "themealdb":  "/api/themealdb?q=cake&n=2",
            "750g":       "/api/750g?q=gateau+chocolat",
            "cuisineaz":  "/api/cuisineaz?q=tarte+citron",
            "ptitchef":   "/api/ptitchef?category=dessert",
            "edamam":     "/api/edamam?q=cake (clé requise)",
            "spoonacular":"/api/spoonacular?q=cake (clé requise)",
        }
    }))


# ============================================================
# /api/recipe  (Endpoint UNIFIÉ — auto-cascade)
# ============================================================

@app.route("/api/recipe")
def recipe():
    q        = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    n        = min(int(request.args.get("n", 1)), 3)
    source   = request.args.get("source", "auto").lower()
    lang     = request.args.get("lang", "fr")
    page     = int(request.args.get("page", 1))

    if not q and not category:
        return _cors(jsonify({"error": "Paramètre requis : q ou category"})), 400

    recipes, source_used = [], "none"

    def _scraper(search_fn, cat_fn, scrape_fn, site):
        if q:
            urls = search_fn(q, page=page, n=n)
        elif category:
            urls = cat_fn(category, page=page, n=n)
            if not urls:
                urls = search_fn(category, page=page, n=n)
        else:
            return []
        out = []
        for u in (urls or [])[:n]:
            r = scrape_fn(u) if scrape_fn else scrape_url(u, source_site=site)
            if "error" not in r and r.get("title") and r.get("ingredients"):
                out.append(r)
        return out

    def _mealdb():
        if category:
            cat_norm = _normalize_category(category)
            cat_en = (
                CATEGORY_MAP_FR.get(cat_norm) or
                CATEGORY_MAP_FR.get(cat_norm.replace(" ", "")) or
                CATEGORY_MAP_FR.get(cat_norm.replace(" ", "-")) or
                cat_norm.title()
            )
            results = [r for r in mdb_cat(cat_en, n) if "error" not in r and r.get("title")]
            # Fallback recherche par nom si catégorie inconnue de TheMealDB
            if not results:
                results = [r for r in mdb_search(cat_norm, n) if "error" not in r and r.get("title")]
            if not results:
                cat_en_tr = _translate_fr_to_en(cat_norm)
                if cat_en_tr != cat_norm:
                    results = [r for r in mdb_search(cat_en_tr, n) if "error" not in r and r.get("title")]
            return results
        else:
            results = [r for r in mdb_search(q, n) if "error" not in r and r.get("title")]
            if not results:
                q_en = _translate_fr_to_en(q)
                if q_en != q:
                    results = [r for r in mdb_search(q_en, n) if "error" not in r and r.get("title")]
            return results

    if source == "themealdb":
        recipes, source_used = _mealdb(), "themealdb"
    elif source == "750g":
        recipes, source_used = _scraper(g750_search, g750_cat, g750_scrape, "750g.com"), "750g"
    elif source == "cuisineaz":
        recipes, source_used = _scraper(caz_search, caz_cat, None, "cuisineaz.com"), "cuisineaz"
    elif source == "ptitchef":
        recipes, source_used = _scraper(ptit_search, ptit_cat, None, "ptitchef.com"), "ptitchef"
    else:
        # Pour les catégories EN sans équivalent TheMealDB, utiliser traduction FR pour 750g/Marmiton
        cat_norm = _normalize_category(category) if category else ""
        q_for_fr  = CATEGORY_EN_TO_FR_750G.get(cat_norm, q or category)
        # Cascade auto : TheMealDB → Spoonacular → 750g → Marmiton → Base locale Kaggle
        _q_local = q or cat_norm
        for src_name, fn in [
            ("themealdb",   _mealdb),
            ("spoonacular", lambda: [r for r in (
                spoon_cat(category, n) if category else spoon_search(q, n)
            ) if r.get("title")]),
            ("750g", lambda: _scraper(
                lambda kw, **kw2: g750_search(q_for_fr, **kw2),
                lambda kw, **kw2: g750_cat(q_for_fr, **kw2),
                g750_scrape, "750g.com"
            )),
            ("marmiton", lambda: [
                r for r in [marm_scrape(u) for u in (marm_search(q_for_fr, page=page, n=n) or [])[:n]]
                if r.get("title") and "error" not in r
            ]),
            ("local", lambda: (
                (ldb_cat(cat_norm, n) or ldb_query(cat_norm, n)) if category else ldb_query(_q_local, n)
            ) if ldb_ok() else []),
        ]:
            try:
                result = fn()
                if result:
                    recipes, source_used = result, src_name
                    break
            except Exception:
                continue

    return _cors(jsonify({
        "source_used":    source_used,
        "query":          q or category,
        "count":          len(recipes),
        "recipes":        recipes,
        "context_for_ai": build_ai_context(recipes),
    }))


# ============================================================
# /api/themealdb
# ============================================================

@app.route("/api/themealdb")
def themealdb():
    q        = request.args.get("q", "")
    category = request.args.get("category", "")
    is_rand  = request.args.get("random", "0") == "1"
    n        = min(int(request.args.get("n", 1)), 5)

    if is_rand:
        recipes = mdb_random()
    elif q:
        recipes = mdb_search(q, n)
    elif category:
        cat_en = CATEGORY_MAP_FR.get(category.lower().replace("-", ""), category)
        recipes = mdb_cat(cat_en, n)
    else:
        return _cors(jsonify({"error": "Paramètre requis : q, category ou random=1"})), 400

    good = [r for r in recipes if "error" not in r]
    return _cors(jsonify({
        "source": "themealdb", "count": len(good),
        "recipes": good, "context_for_ai": build_ai_context(good),
    }))


# ============================================================
# /api/750g
# ============================================================

@app.route("/api/750g")
def source_750g():
    q, category = request.args.get("q", ""), request.args.get("category", "")
    n, page     = min(int(request.args.get("n", 1)), 5), int(request.args.get("page", 1))
    if q:
        urls = g750_search(q, page=page, n=n)
    elif category:
        urls = g750_cat(category, page=page, n=n)
        if not urls:
            urls = g750_search(category, page=page, n=n)
    else:
        return _cors(jsonify({"error": "Paramètre requis : q ou category"})), 400
    recipes = []
    for u in (urls or [])[:n]:
        try:
            r = g750_scrape(u)
            if "error" not in r and r.get("title") and r.get("ingredients"):
                recipes.append(r)
        except Exception:
            continue
    return _cors(jsonify({
        "source": "750g", "query": q or category, "page": page,
        "count": len(recipes), "recipes": recipes, "context_for_ai": build_ai_context(recipes),
    }))


# ============================================================
# /api/cuisineaz
# ============================================================

@app.route("/api/cuisineaz")
def cuisineaz():
    q, category = request.args.get("q", ""), request.args.get("category", "")
    n, page     = min(int(request.args.get("n", 1)), 5), int(request.args.get("page", 1))
    if q:
        urls = caz_search(q, page=page, n=n)
    elif category:
        urls = caz_cat(category, page=page, n=n)
    else:
        return _cors(jsonify({"error": "Paramètre requis : q ou category"})), 400
    recipes = []
    for u in (urls or [])[:n]:
        r = scrape_url(u, source_site="cuisineaz.com")
        if "error" not in r and r.get("title") and r.get("ingredients"):
            recipes.append(r)
    return _cors(jsonify({
        "source": "cuisineaz", "query": q or category, "page": page,
        "count": len(recipes), "recipes": recipes, "context_for_ai": build_ai_context(recipes),
    }))


# ============================================================
# /api/ptitchef
# ============================================================

@app.route("/api/ptitchef")
def ptitchef():
    q, category = request.args.get("q", ""), request.args.get("category", "")
    n, page     = min(int(request.args.get("n", 1)), 5), int(request.args.get("page", 1))
    if q:
        urls = ptit_search(q, page=page, n=n)
    elif category:
        urls = ptit_cat(category, page=page, n=n)
    else:
        return _cors(jsonify({"error": "Paramètre requis : q ou category"})), 400
    recipes = []
    for u in (urls or [])[:n]:
        r = scrape_url(u, source_site="ptitchef.com")
        if "error" not in r and r.get("title") and r.get("ingredients"):
            recipes.append(r)
    return _cors(jsonify({
        "source": "ptitchef", "query": q or category, "page": page,
        "count": len(recipes), "recipes": recipes, "context_for_ai": build_ai_context(recipes),
    }))


# ============================================================
# /api/marmiton
# ============================================================

@app.route("/api/marmiton")
def marmiton():
    q, category = request.args.get("q", ""), request.args.get("category", "")
    n, page     = min(int(request.args.get("n", 1)), 5), int(request.args.get("page", 1))
    query = q or category
    if not query:
        return _cors(jsonify({"error": "Paramètre requis : q ou category"})), 400
    urls = marm_search(query, page=page, n=n)
    recipes = []
    for u in (urls or [])[:n]:
        try:
            r = marm_scrape(u)
            if "error" not in r and r.get("title") and r.get("ingredients"):
                recipes.append(r)
        except Exception:
            continue
    return _cors(jsonify({
        "source": "marmiton", "query": query, "page": page,
        "count": len(recipes), "recipes": recipes, "context_for_ai": build_ai_context(recipes),
    }))


# ============================================================
# /api/edamam  /api/spoonacular  — clés requises
# ============================================================

@app.route("/api/edamam")
def edamam_missing():
    return _cors(jsonify({"error": "Clé Edamam requise. Alternative : /api/recipe?q=VOTRE_RECHERCHE"})), 400


# ============================================================
# /api/local  (Base SQLite Kaggle 2.2M recettes)
# ============================================================

@app.route("/api/local")
def local_db_endpoint():
    q        = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    n        = min(int(request.args.get("n", 1)), 5)
    if not ldb_ok():
        return _cors(jsonify({"error": "Base locale non disponible. Lancez setup_local_db.py d'abord."})), 503
    if not q and not category:
        return _cors(jsonify({"error": "Paramètre requis : q ou category"})), 400
    cat_norm = _normalize_category(category) if category else ""
    recipes  = ldb_cat(cat_norm, n) if category else ldb_query(q, n)
    return _cors(jsonify({
        "source": "local", "query": q or category,
        "count": len(recipes), "recipes": recipes, "context_for_ai": build_ai_context(recipes),
    }))


# ============================================================
# LANCEMENT
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🍳 Recipe Scraper v4.0 — http://localhost:{port}")
    print(f"   → Health  : http://localhost:{port}/api/health")
    print(f"   → Auto    : http://localhost:{port}/api/recipe?q=gateau+chocolat")
    print(f"   → MealDB  : http://localhost:{port}/api/themealdb?q=chocolate+cake")
    print(f"   → 750g    : http://localhost:{port}/api/750g?q=tarte+citron")
    print(f"   → CuisineAZ: http://localhost:{port}/api/cuisineaz?category=dessert")
    print(f"   → Ptitchef: http://localhost:{port}/api/ptitchef?q=poulet\n")
    app.run(host="0.0.0.0", port=port, debug=True)
