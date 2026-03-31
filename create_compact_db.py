"""
create_compact_db.py — Extrait 500 recettes/catégorie de recipes.db
====================================================================
Crée recipes_online.db (~10MB) — déployable sur Render/GitHub.
Lance : python create_compact_db.py
"""
import sqlite3, os, time

SRC = os.path.join(os.path.dirname(__file__), "recipes.db")
DST = os.path.join(os.path.dirname(__file__), "recipes_online.db")

PER_CATEGORY = 500  # recettes gardées par catégorie

def build():
    if not os.path.exists(SRC):
        print("❌ recipes.db introuvable. Lance setup_local_db.py d'abord.")
        return

    if os.path.exists(DST):
        os.remove(DST)

    src = sqlite3.connect(SRC)
    dst = sqlite3.connect(DST)
    d   = dst.cursor()

    d.execute("""
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
    d.execute("CREATE INDEX idx_category ON recipes(category)")
    d.execute("CREATE INDEX idx_title    ON recipes(title_lower)")

    cats = [r[0] for r in src.execute("SELECT DISTINCT category FROM recipes")]
    total = 0

    for cat in cats:
        rows = src.execute(
            "SELECT title,ingredients,steps,link,site,category,title_lower FROM recipes WHERE category=? ORDER BY RANDOM() LIMIT ?",
            (cat, PER_CATEGORY)
        ).fetchall()
        d.executemany(
            "INSERT INTO recipes (title,ingredients,steps,link,site,category,title_lower) VALUES (?,?,?,?,?,?,?)",
            rows
        )
        dst.commit()
        total += len(rows)
        print(f"  {cat:<20} {len(rows):>5} recettes")

    src.close()
    dst.close()

    size_kb = os.path.getsize(DST) / 1024
    print(f"\n✅ {DST}")
    print(f"   {total:,} recettes | {size_kb:.0f} KB ({size_kb/1024:.1f} MB)")

if __name__ == "__main__":
    build()
