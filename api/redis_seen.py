"""
api/redis_seen.py — Déduplication persistante via Upstash Redis REST API
=========================================================================
Stocke les titres de recettes déjà retournés par catégorie.
Fonctionne entre les redémarrages Render (persistant).
Fallback silencieux si Redis non configuré.
"""
import os, urllib.parse, requests as _req

UPSTASH_URL   = os.environ.get("UPSTASH_REDIS_URL",   "https://harmless-slug-104273.upstash.io")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_TOKEN",  "gQAAAAAAAZdRAAIgcDFiNmFjODcwMTc1ZGQ0NjFiYmFmNWRlNmVjZDhmMzY2MQ")

_sess = _req.Session()
_sess.headers.update({"Authorization": f"Bearer {UPSTASH_TOKEN}"})


def _available():
    return bool(UPSTASH_URL and UPSTASH_TOKEN)


def _cmd(*args):
    """Exécute une commande Redis via l'API REST Upstash."""
    if not _available():
        return None
    try:
        path = "/".join(urllib.parse.quote(str(a), safe="") for a in args)
        r = _sess.post(f"{UPSTASH_URL}/{path}", timeout=3)
        return r.json().get("result")
    except Exception:
        return None


def _recipe_key(recipe):
    """Clé unique d'une recette : URL en priorité, sinon titre."""
    url = (recipe.get("url") or recipe.get("link") or "").strip()
    return url if url else recipe.get("title", "").lower().strip()


def is_seen(category, recipe):
    """Retourne True si cette recette (par URL) a déjà été retournée."""
    key = f"seen:{category[:40]}"
    result = _cmd("SISMEMBER", key, _recipe_key(recipe))
    return result == 1


def mark_seen(category, recipe):
    """Enregistre cette recette (par URL) comme vue (permanent)."""
    key = f"seen:{category[:40]}"
    _cmd("SADD", key, _recipe_key(recipe))


def reset_category(category):
    """Efface la liste des recettes vues pour cette catégorie (recommence)."""
    _cmd("DEL", f"seen:{category[:40]}")


def filter_unseen(recipes, category):
    """
    Filtre les recettes déjà vues (comparaison par URL).
    Si toutes vues → reset automatique et retourne quand même les recettes.
    Si Redis indisponible → retourne toutes les recettes sans filtre.
    """
    if not _available():
        return recipes

    unseen = [r for r in recipes if not is_seen(category, r)]

    if not unseen and recipes:
        reset_category(category)
        unseen = recipes

    for r in unseen:
        mark_seen(category, r)

    return unseen
