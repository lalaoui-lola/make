"""
api/local_db.py — Requête la base SQLite locale (recipes.db)
=============================================================
Source locale : 2.2M recettes issues du dataset Kaggle RecipeNLG.
✅ Gratuit, sans clé, sans internet.
✅ Fonctionne hors-ligne.
⚠️  Nécessite d'avoir lancé setup_local_db.py une fois.

Usage :
  from local_db import search_by_category, search_by_query
"""
import sys, os, sqlite3, json, random

sys.path.insert(0, os.path.dirname(__file__))
from utils import make_recipe, error_response

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "recipes.db")


def _db_available():
    return os.path.exists(DB_PATH)


def _parse_row(row):
    """Convertit une ligne SQLite en recette standard."""
    title, ingredients_raw, steps_raw, link, site, category = (
        row[0], row[1], row[2], row[3], row[4], row[5]
    )
    try:
        ingredients = json.loads(ingredients_raw) if ingredients_raw else []
    except Exception:
        ingredients = [ingredients_raw] if ingredients_raw else []
    try:
        steps = json.loads(steps_raw) if steps_raw else []
    except Exception:
        steps = [steps_raw] if steps_raw else []

    return make_recipe(
        title=title,
        description="",
        prep_time="", cook_time="", total_time="", servings="",
        ingredients=ingredients,
        steps=steps,
        image="",
        url=link or "",
        source_site=site or "kaggle-dataset",
        source_type="local_db",
        category=category or "",
        tags=[category] if category else [],
    )


def search_by_category(category, n=3, page=1):
    """Retourne n recettes aléatoires d'une catégorie."""
    if not _db_available():
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        # Cherche par catégorie exacte d'abord
        rows = conn.execute(
            "SELECT title,ingredients,steps,link,site,category FROM recipes WHERE category=? ORDER BY RANDOM() LIMIT ?",
            (category, n)
        ).fetchall()
        # Fallback : recherche par titre si rien trouvé
        if not rows:
            rows = conn.execute(
                "SELECT title,ingredients,steps,link,site,category FROM recipes WHERE title_lower LIKE ? ORDER BY RANDOM() LIMIT ?",
                (f"%{category.lower()}%", n)
            ).fetchall()
        conn.close()
        return [_parse_row(r) for r in rows if r[0]]
    except Exception:
        return []


def search_by_query(query, n=3):
    """Cherche des recettes par mots-clés dans le titre."""
    if not _db_available():
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        words = query.lower().split()
        if len(words) == 1:
            rows = conn.execute(
                "SELECT title,ingredients,steps,link,site,category FROM recipes WHERE title_lower LIKE ? ORDER BY RANDOM() LIMIT ?",
                (f"%{words[0]}%", n)
            ).fetchall()
        else:
            # Cherche recettes contenant tous les mots
            conditions = " AND ".join(["title_lower LIKE ?" for _ in words])
            params = [f"%{w}%" for w in words] + [n]
            rows = conn.execute(
                f"SELECT title,ingredients,steps,link,site,category FROM recipes WHERE {conditions} ORDER BY RANDOM() LIMIT ?",
                params
            ).fetchall()
            # Fallback sur le premier mot si rien
            if not rows:
                rows = conn.execute(
                    "SELECT title,ingredients,steps,link,site,category FROM recipes WHERE title_lower LIKE ? ORDER BY RANDOM() LIMIT ?",
                    (f"%{words[0]}%", n)
                ).fetchall()
        conn.close()
        return [_parse_row(r) for r in rows if r[0]]
    except Exception:
        return []


def is_available():
    return _db_available()
