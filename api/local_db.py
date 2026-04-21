"""
api/local_db.py — Requête la base SQLite (locale ou Turso cloud)
=================================================================
- Si TURSO_URL + TURSO_TOKEN sont définis → Turso cloud (2.2M recettes en ligne)
- Sinon → SQLite local recipes.db

Variables d'environnement Turso :
  TURSO_URL   = https://recipe-db-XXXXX.turso.io
  TURSO_TOKEN = eyJhbGc...

Usage :
  from local_db import search_by_category, search_by_query
"""
import sys, os, sqlite3, json
import requests as _req

sys.path.insert(0, os.path.dirname(__file__))
from utils import make_recipe, error_response

_LOCAL  = os.path.join(os.path.dirname(__file__), "..", "recipes.db")
DB_PATH = "/data/recipes.db" if os.path.exists("/data/recipes.db") else _LOCAL

# ── Turso cloud ──────────────────────────────────────────────────────────────
TURSO_URL   = os.environ.get("TURSO_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN", "")


def _use_turso():
    return bool(TURSO_URL and TURSO_TOKEN)


def _turso_query(sql, args=None):
    """Exécute une requête SQL sur Turso via HTTP API."""
    stmt = {"sql": sql}
    if args:
        stmt["args"] = [{"type": "text", "value": str(a)} for a in args]
    payload = {"requests": [{"type": "execute", "stmt": stmt},
                             {"type": "close"}]}
    resp = _req.post(
        f"{TURSO_URL}/v2/pipeline",
        headers={"Authorization": f"Bearer {TURSO_TOKEN}",
                 "Content-Type": "application/json"},
        json=payload,
        timeout=20
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results or results[0].get("type") == "error":
        return []
    rows_data = results[0].get("response", {}).get("result", {}).get("rows", [])
    return [[col.get("value") for col in row] for row in rows_data]


def _turso_random_query(where_sql, args, n):
    """
    Sélectionne n lignes aléatoires sans ORDER BY RANDOM() (trop coûteux).
    Utilise un offset aléatoire basé sur MAX(id) pour lire ~n lignes seulement.
    """
    import random as _rand
    # 1. Obtenir le max id (1 seule ligne lue)
    max_rows = _turso_query("SELECT MAX(id) FROM recipes")
    max_id = int(max_rows[0][0]) if max_rows and max_rows[0][0] else 2500000
    # 2. Choisir un offset aléatoire et sélectionner les lignes correspondantes
    offset = _rand.randint(0, max(1, max_id - n * 10))
    sql = f"SELECT title,ingredients,steps,link,site,category FROM recipes WHERE {where_sql} AND id >= ? LIMIT ?"
    rows = _turso_query(sql, args + [offset, n])
    # 3. Si pas assez de résultats avec cet offset, retenter sans contrainte d'offset
    if not rows:
        sql2 = f"SELECT title,ingredients,steps,link,site,category FROM recipes WHERE {where_sql} LIMIT ?"
        rows = _turso_query(sql2, args + [n])
    return rows


def _db_available():
    if _use_turso():
        return True
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
        if _use_turso():
            rows = _turso_random_query("category=?", [category], n)
            if not rows:
                rows = _turso_random_query("title_lower LIKE ?", [f"%{category.lower()}%"], n)
        else:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(
                "SELECT title,ingredients,steps,link,site,category FROM recipes WHERE category=? ORDER BY RANDOM() LIMIT ?",
                (category, n)
            ).fetchall()
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
        words = query.lower().split()
        if _use_turso():
            if len(words) == 1:
                rows = _turso_random_query("title_lower LIKE ?", [f"%{words[0]}%"], n)
            else:
                # Recherche multi-mots : AND sur les 2 premiers mots
                rows = _turso_random_query(
                    "title_lower LIKE ? AND title_lower LIKE ?",
                    [f"%{words[0]}%", f"%{words[1]}%"], n
                )
                if not rows:
                    rows = _turso_random_query("title_lower LIKE ?", [f"%{words[0]}%"], n)
        else:
            conn = sqlite3.connect(DB_PATH)
            if len(words) == 1:
                rows = conn.execute(
                    "SELECT title,ingredients,steps,link,site,category FROM recipes WHERE title_lower LIKE ? ORDER BY RANDOM() LIMIT ?",
                    (f"%{words[0]}%", n)
                ).fetchall()
            else:
                conditions = " AND ".join(["title_lower LIKE ?" for _ in words])
                params = [f"%{w}%" for w in words] + [n]
                rows = conn.execute(
                    f"SELECT title,ingredients,steps,link,site,category FROM recipes WHERE {conditions} ORDER BY RANDOM() LIMIT ?",
                    params
                ).fetchall()
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
