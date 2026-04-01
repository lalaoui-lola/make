"""
api/utils.py — Fonctions partagées pour tous les modules du nouveau scraper.
Sources supportées : TheMealDB, 750g, CuisineAZ, Ptitchef, Edamam, Spoonacular
"""
import json
import random
import re
import urllib.parse

import requests as req
from bs4 import BeautifulSoup, Comment

# ============================================================
# USER-AGENTS RÉALISTES
# ============================================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]


def get_headers(referer=None, extra=None):
    """Retourne des headers HTTP réalistes."""
    h = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
    }
    if referer:
        h["Referer"] = referer
    if extra:
        h.update(extra)
    return h


# ============================================================
# FORMAT DE RÉPONSE STANDARD
# ============================================================

def make_recipe(
    title="",
    description="",
    prep_time="",
    cook_time="",
    total_time="",
    servings="",
    ingredients=None,
    steps=None,
    image="",
    url="",
    source_site="",
    source_type="scrape",
    category="",
    tags=None,
):
    """Retourne un dict recette dans le format standard de l'API."""
    return {
        "title": title,
        "description": description,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "total_time": total_time,
        "servings": str(servings),
        "ingredients": ingredients or [],
        "steps": steps or [],
        "image": image,
        "url": url,
        "source_site": source_site,
        "source_type": source_type,   # "api" | "scrape" | "json-ld"
        "category": category,
        "tags": tags or [],
    }


def error_response(msg, code=500):
    """Retourne un dict d'erreur standardisé."""
    return {"error": msg, "code": code}


# ============================================================
# EXTRACTION JSON-LD  (Rich Snippets recette)
# ============================================================

def extract_json_ld(soup):
    """
    Extrait le JSON-LD de type Recipe depuis la soupe BeautifulSoup.
    Appeler AVANT clean_html() car celle-ci supprime les <script>.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = script.string
            if not raw:
                continue
            data = json.loads(raw)
            if isinstance(data, list):
                for item in data:
                    found = _find_recipe_in_dict(item)
                    if found:
                        return found
            elif isinstance(data, dict):
                found = _find_recipe_in_dict(data)
                if found:
                    return found
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
    return None


def _find_recipe_in_dict(data):
    if not isinstance(data, dict):
        return None
    types = data.get("@type", "")
    if isinstance(types, list):
        if "Recipe" in types:
            return data
    elif types == "Recipe":
        return data
    if "@graph" in data:
        for item in data.get("@graph", []):
            found = _find_recipe_in_dict(item)
            if found:
                return found
    return None


def parse_json_ld_recipe(json_ld, url=""):
    """
    Transforme un JSON-LD de type Recipe en dict standard.
    """
    def _image(raw):
        if isinstance(raw, list):
            raw = raw[0] if raw else ""
        if isinstance(raw, dict):
            return raw.get("url", "")
        return raw or ""

    def _yield(raw):
        if isinstance(raw, list):
            return str(raw[0]) if raw else ""
        return str(raw) if raw else ""

    def _ingredients(raw):
        if isinstance(raw, list):
            return [str(i).strip() for i in raw if i]
        if isinstance(raw, str) and raw.strip():
            return [raw.strip()]
        return []

    def _ingredient_groups(json_ld):
        """Parse ingredient groups used by WPRM and other plugins."""
        extra = []
        for key in ("ingredientGroups", "wprm:ingredientGroups", "recipeIngredientGroup"):
            groups = json_ld.get(key, [])
            if isinstance(groups, list):
                for group in groups:
                    if isinstance(group, dict):
                        items = group.get("recipeIngredient", group.get("ingredients", []))
                        extra.extend(_ingredients(items))
        return extra

    def _steps(raw):
        steps = []
        if not isinstance(raw, list):
            return steps
        for step in raw:
            if isinstance(step, str) and step.strip():
                steps.append(step.strip())
            elif isinstance(step, dict):
                text = step.get("text", step.get("name", ""))
                if text:
                    steps.append(text.strip())
            elif isinstance(step, list):
                for sub in step:
                    if isinstance(sub, dict):
                        t = sub.get("text", "")
                        if t:
                            steps.append(t.strip())
        return steps

    return make_recipe(
        title=json_ld.get("name", ""),
        description=json_ld.get("description", ""),
        prep_time=json_ld.get("prepTime", ""),
        cook_time=json_ld.get("cookTime", ""),
        total_time=json_ld.get("totalTime", ""),
        servings=_yield(json_ld.get("recipeYield", "")),
        ingredients=list(dict.fromkeys(
            _ingredients(json_ld.get("recipeIngredient", [])) +
            _ingredient_groups(json_ld)
        )),
        steps=_steps(json_ld.get("recipeInstructions", [])),
        image=_image(json_ld.get("image", "")),
        url=url,
        source_type="json-ld",
        tags=json_ld.get("keywords", "").split(",") if isinstance(json_ld.get("keywords", ""), str) else [],
        category=json_ld.get("recipeCategory", ""),
    )


# ============================================================
# NETTOYAGE HTML
# ============================================================

REMOVE_TAGS   = ["script", "style", "nav", "footer", "header", "aside",
                  "iframe", "noscript", "form", "button", "svg", "video",
                  "audio", "ins", "figure", "figcaption"]
REMOVE_KEYWORDS = ["comment", "sidebar", "widget", "nav", "menu", "footer",
                   "header", " ad ", "pub", "social", "share", "related",
                   "newsletter", "popup", "cookie", "banner", "breadcrumb",
                   "pagination", "rating", "review", "author", "tag"]


def clean_html(soup):
    """Supprime les éléments inutiles du HTML."""
    for tag in REMOVE_TAGS:
        for el in soup.find_all(tag):
            el.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()
    to_remove = []
    for el in soup.find_all(True):
        try:
            cls = " ".join(el.get("class", []) or [])
            eid = el.get("id") or ""
            if isinstance(eid, list):
                eid = " ".join(eid)
            combined = (cls + " " + eid).lower()
            if any(k in combined for k in REMOVE_KEYWORDS):
                to_remove.append(el)
        except Exception:
            continue
    for el in to_remove:
        try:
            el.decompose()
        except Exception:
            pass
    return soup


# ============================================================
# FALLBACKS HTML : INGRÉDIENTS + ÉTAPES
# ============================================================

def extract_ingredients_html(soup):
    results = []
    for section in soup.find_all(True, class_=re.compile(r"ingredient", re.I)):
        for li in section.find_all("li"):
            t = li.get_text(separator=" ", strip=True)
            if t and len(t) > 2:
                results.append(t)
    if results:
        return list(dict.fromkeys(results))

    for el in soup.find_all(["h2", "h3", "h4"]):
        heading = el.get_text().lower()
        if any(kw in heading for kw in ["ingrédient", "ingredient", "ingrédients"]):
            nxt = el.find_next_sibling()
            while nxt and nxt.name in ["ul", "ol", "div", "p"]:
                for li in nxt.find_all("li"):
                    t = li.get_text(separator=" ", strip=True)
                    if t and len(t) > 2:
                        results.append(t)
                nxt = nxt.find_next_sibling()
                if nxt and nxt.name in ["h2", "h3", "h4"]:
                    break
            if results:
                break
    return results


def extract_steps_html(soup):
    results = []
    for section in soup.find_all(True, class_=re.compile(r"(step|instruction|preparation|direction|method|étape)", re.I)):
        for li in section.find_all("li"):
            t = li.get_text(separator=" ", strip=True)
            if t and len(t) > 10:
                results.append(t)
        if not results:
            for p in section.find_all("p"):
                t = p.get_text(separator=" ", strip=True)
                if t and len(t) > 10:
                    results.append(t)
    if results:
        return results

    for el in soup.find_all(["h2", "h3", "h4"]):
        heading = el.get_text().lower()
        if any(kw in heading for kw in ["préparation", "preparation", "instruction", "étape", "step", "method"]):
            nxt = el.find_next_sibling()
            while nxt and nxt.name not in ["h2", "h3"]:
                if nxt.name in ["ol", "ul"]:
                    for li in nxt.find_all("li"):
                        t = li.get_text(separator=" ", strip=True)
                        if t and len(t) > 10:
                            results.append(t)
                elif nxt.name == "p":
                    t = nxt.get_text(separator=" ", strip=True)
                    if t and len(t) > 10:
                        results.append(t)
                nxt = nxt.find_next_sibling()
            if results:
                break
    return results


# ============================================================
# SCRAPER URL GÉNÉRIQUE  (json-ld → fallback html)
# ============================================================

def scrape_url(url, source_site=""):
    """
    Télécharge une page et extrait la recette.
    Essaie JSON-LD d'abord, puis fallback HTML.
    """
    try:
        resp = req.get(url, headers=get_headers(referer="https://www.google.fr/"), timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        html = resp.text
    except Exception as e:
        return error_response(f"Téléchargement impossible : {e}")

    soup = BeautifulSoup(html, "lxml")

    # 1. Essayer JSON-LD
    json_ld = extract_json_ld(soup)
    html_ingredients = None
    if json_ld:
        recipe = parse_json_ld_recipe(json_ld, url)
        recipe["source_site"] = source_site or urllib.parse.urlparse(url).netloc
        if recipe["title"] and recipe["ingredients"]:
            # Try HTML too — use whichever has more ingredients
            soup_clean = BeautifulSoup(str(soup), "lxml")
            html_ingredients = extract_ingredients_html(soup_clean)
            if html_ingredients and len(html_ingredients) > len(recipe["ingredients"]):
                recipe["ingredients"] = list(dict.fromkeys(recipe["ingredients"] + [
                    i for i in html_ingredients if i not in recipe["ingredients"]
                ]))
            return recipe

    # 2. Fallback HTML
    soup = clean_html(soup)
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    ingredients = html_ingredients or extract_ingredients_html(soup)
    steps = extract_steps_html(soup)

    # Titre + ingrédients minimums obligatoires
    if not title or not ingredients:
        return error_response("Impossible d'extraire la recette depuis cette page.")

    full_text = ""
    article = soup.find("article") or soup.find("main") or soup.find("body")
    if article:
        full_text = article.get_text(separator="\n", strip=True)[:4000]

    return make_recipe(
        title=title,
        ingredients=ingredients,
        steps=steps,
        url=url,
        source_site=source_site or urllib.parse.urlparse(url).netloc,
        source_type="html",
    )


# ============================================================
# CONTEXTE IA (pour Make.com → GPT)
# ============================================================

def build_ai_context(recipes):
    """Construit un bloc texte condensé pour GPT depuis les recettes récupérées."""
    parts = []
    for i, r in enumerate(recipes, 1):
        if isinstance(r, dict) and "error" not in r:
            block = [f"=== RECETTE SOURCE {i} ({r.get('source_site', 'inconnu')}) ==="]
            if r.get("title"):        block.append(f"Titre: {r['title']}")
            if r.get("description"):  block.append(f"Description: {r['description'][:300]}")
            if r.get("prep_time"):    block.append(f"Préparation: {r['prep_time']}")
            if r.get("cook_time"):    block.append(f"Cuisson: {r['cook_time']}")
            if r.get("servings"):     block.append(f"Portions: {r['servings']}")
            if r.get("ingredients"):  block.append("Ingrédients:\n- " + "\n- ".join(r["ingredients"]))
            if r.get("steps"):        block.append("Étapes:\n" + "\n".join(f"{j}. {s}" for j, s in enumerate(r["steps"], 1)))
            parts.append("\n".join(block))
    return "\n\n".join(parts) or "Aucune recette trouvée."


# ============================================================
# UTILITAIRES TEXTE
# ============================================================

def clean_title(title):
    """Supprime les suffixes de site des titres."""
    title = re.sub(
        r'\s*[-|–—]\s*(allrecipes|food network|simply recipes|bon appétit|delish|tasty'
        r'|epicurious|bbc good food|serious eats|marmiton|750g|cuisineaz|ptitchef'
        r'|journal des femmes|femme actuelle|doctissimo).*$',
        '', title, flags=re.IGNORECASE
    )
    title = re.sub(r'\s*[-|–—]\s*\w+\.(com|fr|net|org).*$', '', title)
    title = re.sub(r'\brecettes?\b\s*$', '', title, flags=re.IGNORECASE).strip()
    return re.sub(r'\s+', ' ', title).strip()


def iso_to_fr(duration):
    """Convertit PT1H30M → '1h30' pour l'affichage français."""
    if not duration or not duration.startswith("PT"):
        return duration
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', duration)
    if not m:
        return duration
    hours, mins = m.group(1), m.group(2)
    result = ""
    if hours:
        result += f"{hours}h"
    if mins:
        result += f"{mins}min"
    return result or duration
