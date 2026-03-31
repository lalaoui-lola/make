"""
setup_local_db.py — Convertit recipes_data.csv (Kaggle) en base SQLite locale.
===============================================================================
Lance UNE SEULE FOIS :  python setup_local_db.py

Crée : recipe-scraper/recipes.db (~800 Mo)
Durée : ~3-5 minutes pour 2.2M recettes
"""
import sqlite3, csv, json, os, sys, time

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "recipes_data.csv")
DB_PATH  = os.path.join(os.path.dirname(__file__), "recipes.db")

# ── Mots-clés pour inférer la catégorie depuis le titre/NER ──────────────────
CATEGORY_KEYWORDS = {
    "Chicken":     ["chicken", "turkey", "duck", "poulet", "volaille"],
    "Beef":        ["beef", "steak", "boeuf", "veal", "ground beef", "hamburger", "meatball", "meatloaf"],
    "Pork":        ["pork", "bacon", "ham", "sausage", "ribs", "chorizo", "lard", "prosciutto"],
    "Seafood":     ["fish", "salmon", "shrimp", "tuna", "seafood", "prawn", "crab", "lobster", "cod", "tilapia", "halibut", "sardine"],
    "Pasta":       ["pasta", "spaghetti", "noodle", "lasagna", "lasagne", "linguine", "fettuccine", "macaroni", "ravioli", "penne"],
    "Dessert":     ["cake", "cookie", "pie", "dessert", "tart", "brownie", "muffin", "pudding", "ice cream", "cheesecake", "frosting", "candy", "fudge", "mousse", "custard", "donut"],
    "Breakfast":   ["breakfast", "pancake", "waffle", "omelette", "omelet", "scrambled egg", "french toast", "granola", "crepe"],
    "Soup":        ["soup", "chowder", "bisque", "broth", "chili", "gazpacho", "ramen", "pho"],
    "Salad":       ["salad", "coleslaw", "vinaigrette"],
    "Bread":       ["bread", "biscuit", "roll", "bun", "bagel", "focaccia", "loaf", "dough", "yeast bread"],
    "Vegan":       ["vegan", "plant-based", "tofu", "tempeh"],
    "Vegetarian":  ["vegetarian", "veggie burger", "quiche", "lentil", "chickpea", "bean dish"],
    "Side":        ["side dish", "mashed potato", "roasted potato", "coleslaw", "rice pilaf", "risotto"],
    "Lamb":        ["lamb", "mutton", "rack of lamb"],
    "Miscellaneous": [],
}

def infer_category(title, ner):
    """Détermine la catégorie d'une recette à partir de son titre et ingrédients."""
    text = (title + " " + ner).lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if cat == "Miscellaneous":
            continue
        for kw in keywords:
            if kw in text:
                return cat
    return "Miscellaneous"


def build_db():
    if os.path.exists(DB_PATH):
        print(f"Base existante : {DB_PATH}")
        ans = input("Recréer ? (o/n) : ").strip().lower()
        if ans != "o":
            print("Abandon.")
            return

    print(f"Lecture : {CSV_PATH}")
    print("Création de la base SQLite...")

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS recipes")
    cur.execute("""
        CREATE TABLE recipes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            ingredients TEXT,
            steps       TEXT,
            link        TEXT,
            site        TEXT,
            category    TEXT,
            title_lower TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_category ON recipes(category)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_title ON recipes(title_lower)")

    batch, total, t0 = [], 0, time.time()
    BATCH_SIZE = 5000

    with open(CSV_PATH, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (row.get("title") or "").strip()
            if not title:
                continue
            ner      = row.get("NER", "") or ""
            category = infer_category(title, ner)
            batch.append((
                title,
                row.get("ingredients", "[]"),
                row.get("directions", "[]"),
                row.get("link", ""),
                row.get("site", ""),
                category,
                title.lower(),
            ))
            total += 1
            if len(batch) >= BATCH_SIZE:
                cur.executemany(
                    "INSERT INTO recipes (title,ingredients,steps,link,site,category,title_lower) VALUES (?,?,?,?,?,?,?)",
                    batch
                )
                conn.commit()
                batch = []
                elapsed = time.time() - t0
                print(f"  {total:,} recettes importées... ({elapsed:.0f}s)", end="\r")

    if batch:
        cur.executemany(
            "INSERT INTO recipes (title,ingredients,steps,link,site,category,title_lower) VALUES (?,?,?,?,?,?,?)",
            batch
        )
        conn.commit()

    conn.close()
    elapsed = time.time() - t0
    size_mb = os.path.getsize(DB_PATH) / 1024 / 1024
    print(f"\n✅ Base créée : {DB_PATH}")
    print(f"   {total:,} recettes | {size_mb:.0f} Mo | {elapsed:.0f}s")

    # Statistiques par catégorie
    conn2 = sqlite3.connect(DB_PATH)
    print("\nRecettes par catégorie :")
    for row in conn2.execute("SELECT category, COUNT(*) as n FROM recipes GROUP BY category ORDER BY n DESC"):
        print(f"  {row[0]:<20} {row[1]:>10,}")
    conn2.close()


if __name__ == "__main__":
    build_db()
