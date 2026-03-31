"""Demo scraper - categorie DESSERT"""
import sys, json
sys.path.insert(0, "api")

from utils import build_ai_context
from themealdb import search_by_category as mdb_cat, CATEGORY_MAP_FR
from source_750g import _search_urls as g750_search, _scrape_recipe as g750_scrape

CATEGORIE = "dessert"  # << catégorie testée

print("=" * 65)
print(f"SCRAPER v4.0 — TEST CATEGORIE : '{CATEGORIE.upper()}'")
print("=" * 65)

# ─── SOURCE 1 : TheMealDB ───────────────────────────────────────
print("\n[SOURCE 1] TheMealDB...")
cat_en = CATEGORY_MAP_FR.get(CATEGORIE.lower(), CATEGORIE)
print(f"  Traduction FR→EN : '{CATEGORIE}' → '{cat_en}'")
results = mdb_cat(cat_en, 1)
mdb_ok = results and "error" not in results[0] and results[0].get("title")

if mdb_ok:
    r = results[0]
    print(f"  ✅ SUCCÈS")
    print(f"  Titre       : {r['title']}")
    print(f"  Ingrédients : {len(r.get('ingredients', []))} trouvés")
    print(f"  Étapes      : {len(r.get('steps', []))} trouvées")
    print(f"  Exemple ingrédient : {r.get('ingredients', ['?'])[0]}")
    print(f"  Exemple étape      : {str(r.get('steps', ['?'])[0])[:80]}")
    context = build_ai_context(results)
    print(f"\n--- context_for_ai (extrait) ---")
    print(context[:600])
    print("[...]")
else:
    print(f"  ❌ TheMealDB : pas de résultat pour '{cat_en}'")

print()
print("-" * 65)

# ─── SOURCE 2 : 750g.com ────────────────────────────────────────
print("\n[SOURCE 2] 750g.com...")
urls = g750_search(CATEGORIE, page=1, n=2)
print(f"  URLs trouvées : {len(urls)}")

if urls:
    print(f"  URL scraped   : {urls[0]}")
    r750 = g750_scrape(urls[0])
    ok750 = "error" not in r750 and r750.get("title") and r750.get("ingredients")
    if ok750:
        print(f"  ✅ SUCCÈS")
        print(f"  Titre       : {r750['title']}")
        print(f"  Ingrédients : {len(r750.get('ingredients', []))} trouvés")
        print(f"  Étapes      : {len(r750.get('steps', []))} trouvées")
        print(f"  Exemple ingrédient : {r750.get('ingredients', ['?'])[0]}")
    else:
        print(f"  ❌ Scrape échoué : {r750.get('error')}")
else:
    print(f"  ❌ Aucune URL pour '{CATEGORIE}'")

print()
print("=" * 65)
print("RÉSUMÉ FINAL — /api/recipe?category=dessert&n=1")
print("=" * 65)
if mdb_ok:
    print("  → source_used : themealdb")
    print("  → La cascade utilise TheMealDB (dessert = Dessert EN)")
    print("  → context_for_ai prêt pour Groq")
    print("  ✅ ENDPOINT /api/recipe FONCTIONNEL")
elif urls and ok750:
    print("  → source_used : 750g (fallback)")
    print("  ✅ ENDPOINT /api/recipe FONCTIONNEL (via 750g)")
else:
    print("  ❌ Aucune source n'a retourné de résultat")
