"""
upload_to_turso.py — Importe recipes.db (SQLite local) vers Turso cloud
========================================================================
Prérequis :
  1. Créer une DB sur app.turso.tech
  2. Récupérer l'URL et le token
  3. Renseigner TURSO_URL et TURSO_TOKEN ci-dessous ou en variable d'env

Lance : python upload_to_turso.py
Durée : ~30-60 minutes pour 2.2M recettes (envoi par lots de 200)
"""
import sqlite3, json, os, time, sys
import requests

# ── Config — remplace par tes valeurs Turso ──────────────────────────────────
TURSO_URL   = os.environ.get("TURSO_URL",   "")   # ex: https://recipes-db-xxx.turso.io
TURSO_TOKEN = os.environ.get("TURSO_TOKEN", "")   # ex: eyJhbGciOi...

DB_PATH     = os.path.join(os.path.dirname(__file__), "recipes.db")
BATCH_SIZE  = 200  # recettes par requête HTTP

# ── Helpers ───────────────────────────────────────────────────────────────────

def turso_exec(statements):
    """Envoie une liste de statements SQL à Turso."""
    requests_list = [{"type": "execute", "stmt": s} for s in statements]
    requests_list.append({"type": "close"})
    resp = requests.post(
        f"{TURSO_URL}/v2/pipeline",
        headers={"Authorization": f"Bearer {TURSO_TOKEN}",
                 "Content-Type": "application/json"},
        json={"requests": requests_list},
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def create_table():
    """Crée la table sur Turso."""
    turso_exec([{
        "sql": """
            CREATE TABLE IF NOT EXISTS recipes (
                id          INTEGER PRIMARY KEY,
                title       TEXT NOT NULL,
                ingredients TEXT,
                steps       TEXT,
                link        TEXT,
                site        TEXT,
                category    TEXT,
                title_lower TEXT
            )
        """
    }, {
        "sql": "CREATE INDEX IF NOT EXISTS idx_category ON recipes(category)"
    }, {
        "sql": "CREATE INDEX IF NOT EXISTS idx_title ON recipes(title_lower)"
    }])
    print("✅ Table créée sur Turso")


def upload():
    if not TURSO_URL or not TURSO_TOKEN:
        print("❌ Configure TURSO_URL et TURSO_TOKEN dans ce fichier ou en variables d'environnement.")
        sys.exit(1)

    if not os.path.exists(DB_PATH):
        print(f"❌ {DB_PATH} introuvable.")
        sys.exit(1)

    create_table()

    conn  = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    print(f"📦 {total:,} recettes à importer...")

    sent, t0, errors = 0, time.time(), 0
    batch = []

    for row in conn.execute("SELECT title,ingredients,steps,link,site,category,title_lower FROM recipes"):
        title, ingredients, steps, link, site, category, title_lower = row

        stmt = {
            "sql": "INSERT OR IGNORE INTO recipes (title,ingredients,steps,link,site,category,title_lower) VALUES (?,?,?,?,?,?,?)",
            "args": [
                {"type": "text", "value": title        or ""},
                {"type": "text", "value": ingredients  or "[]"},
                {"type": "text", "value": steps        or "[]"},
                {"type": "text", "value": link         or ""},
                {"type": "text", "value": site         or ""},
                {"type": "text", "value": category     or ""},
                {"type": "text", "value": title_lower  or ""},
            ]
        }
        batch.append(stmt)

        if len(batch) >= BATCH_SIZE:
            try:
                turso_exec(batch)
                sent += len(batch)
                elapsed = time.time() - t0
                speed   = sent / elapsed if elapsed > 0 else 0
                eta     = (total - sent) / speed if speed > 0 else 0
                print(f"  {sent:>9,}/{total:,}  ({speed:.0f}/s)  ETA: {eta/60:.0f}min  erreurs: {errors}", end="\r")
            except Exception as e:
                errors += 1
                if errors > 50:
                    print(f"\n❌ Trop d'erreurs ({errors}). Arrêt.")
                    break
            batch = []

    # Dernier lot
    if batch:
        try:
            turso_exec(batch)
            sent += len(batch)
        except Exception:
            pass

    conn.close()
    elapsed = time.time() - t0
    print(f"\n✅ Import terminé : {sent:,} recettes en {elapsed/60:.0f} min")
    print(f"\nAjoute ces variables sur Render :")
    print(f"  TURSO_URL   = {TURSO_URL}")
    print(f"  TURSO_TOKEN = {TURSO_TOKEN}")


if __name__ == "__main__":
    upload()
