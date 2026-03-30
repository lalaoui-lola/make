# 🍳 Recipe Scraper v4 — Multi-Sources

API Flask de récupération de recettes avec **6 sources** et auto-cascade.
Déployable sur Vercel gratuitement.

## Sources disponibles

| Source | Type | Clé requise | Volume | Langue |
|--------|------|-------------|--------|--------|
| **TheMealDB** | API officielle | ❌ Non | 5000+ recettes | EN (traduit par GPT) |
| **750g.com** | Scraping JSON-LD | ❌ Non | Illimité | FR |
| **CuisineAZ** | Scraping JSON-LD | ❌ Non | Illimité | FR |
| **Ptitchef** | Scraping JSON-LD | ❌ Non | Illimité | FR |
| **Edamam** | API officielle | 🔑 Optionnel | 1 500/mois | EN |
| **Spoonacular** | API officielle | 🔑 Optionnel | 150/jour | FR+EN |

## Endpoints

```
GET /api/recipe?q=gateau+chocolat        ← PRINCIPAL — auto-cascade toutes sources
GET /api/recipe?category=dessert&n=2
GET /api/recipe?q=tarte&source=750g      ← Source spécifique

GET /api/themealdb?q=chocolate+cake&n=2
GET /api/themealdb?category=dessert&n=3
GET /api/themealdb?random=1

GET /api/750g?q=gateau+chocolat&n=2
GET /api/750g?category=dessert&page=2

GET /api/cuisineaz?q=tarte+citron&n=2
GET /api/cuisineaz?category=plat-principal

GET /api/ptitchef?q=poulet+roti&n=2
GET /api/ptitchef?category=dessert

GET /api/edamam?q=chocolate+cake&n=2    ← Clé EDAMAM_APP_ID + EDAMAM_APP_KEY
GET /api/spoonacular?q=tarte&n=2         ← Clé SPOONACULAR_API_KEY

GET /api/health
```

## Format de réponse standard

```json
{
  "source_used": "750g",
  "query": "gateau chocolat",
  "count": 1,
  "recipes": [
    {
      "title": "Gâteau au chocolat fondant",
      "description": "...",
      "prep_time": "PT20M",
      "cook_time": "PT30M",
      "total_time": "PT50M",
      "servings": "6",
      "ingredients": ["200g chocolat noir", "3 œufs", "..."],
      "steps": ["Préchauffer le four à 180°C", "..."],
      "image": "https://...",
      "url": "https://www.750g.com/...",
      "source_site": "750g.com",
      "source_type": "json-ld",
      "category": "Dessert",
      "tags": []
    }
  ],
  "context_for_ai": "=== RECETTE SOURCE 1 (750g.com) ===\nTitre: ..."
}
```

## Installation locale

```bash
cd recipe-scraper
pip install -r requirements.txt
python app.py
# → http://localhost:5000
```

## Déploiement Vercel

```bash
git init
git add .
git commit -m "v4 - multi-source scraper"
git push origin main
# → Aller sur vercel.com > Import repository
```

## Variables d'environnement (optionnelles)

À configurer dans Vercel > Settings > Environment Variables :

```
EDAMAM_APP_ID      = votre_id_edamam
EDAMAM_APP_KEY     = votre_clé_edamam
SPOONACULAR_API_KEY = votre_clé_spoonacular
```

## Utilisation dans Make.com

Endpoint recommandé dans le module HTTP :
```
https://VOTRE-URL.vercel.app/api/recipe?q={{titre_recette}}&n=1&source=auto
```

Ou par catégorie :
```
https://VOTRE-URL.vercel.app/api/recipe?category={{slug_categorie}}&n=1
```

## Structure du projet

```
recipe-scraper/
├── app.py                ← Serveur local (tests)
├── requirements.txt
├── vercel.json
├── api/
│   ├── utils.py          ← Fonctions communes
│   ├── health.py         ← GET /api/health
│   ├── recipe.py         ← GET /api/recipe (endpoint unifié)
│   ├── themealdb.py      ← GET /api/themealdb
│   ├── source_750g.py    ← GET /api/750g
│   ├── cuisineaz.py      ← GET /api/cuisineaz
│   ├── ptitchef.py       ← GET /api/ptitchef
│   ├── edamam.py         ← GET /api/edamam
│   └── spoonacular.py    ← GET /api/spoonacular
└── public/
    └── index.html        ← Interface de test
```
