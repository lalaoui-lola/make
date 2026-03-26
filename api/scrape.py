from http.server import BaseHTTPRequestHandler
import json
import requests
from bs4 import BeautifulSoup, Comment
import random
import urllib.parse
import re

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

REMOVE_TAGS = [
    "script", "style", "nav", "footer", "header", "aside", "iframe",
    "noscript", "form", "button", "svg", "video", "audio", "figure",
    "figcaption", "advertisement", "ins"
]

REMOVE_CLASSES = [
    "comment", "sidebar", "widget", "nav", "menu", "footer", "header",
    "ad", "pub", "social", "share", "related", "newsletter", "popup",
    "cookie", "banner", "breadcrumb", "pagination"
]


def clean_html(soup):
    """Supprime les éléments non pertinents du HTML."""
    for tag in REMOVE_TAGS:
        for el in soup.find_all(tag):
            el.decompose()

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    for el in soup.find_all(True):
        class_list = " ".join(el.get("class", []))
        id_val = el.get("id", "")
        combined = f"{class_list} {id_val}".lower()
        if any(keyword in combined for keyword in REMOVE_CLASSES):
            el.decompose()

    return soup


def extract_recipe_content(html, url):
    """Extrait le contenu structuré d'une recette depuis le HTML."""
    soup = BeautifulSoup(html, "lxml")
    soup = clean_html(soup)

    recipe = {
        "url": url,
        "title": "",
        "description": "",
        "prep_time": "",
        "cook_time": "",
        "servings": "",
        "ingredients": [],
        "steps": [],
        "full_text": ""
    }

    # Extraire depuis JSON-LD (schema.org) si disponible
    json_ld = extract_json_ld(soup)
    if json_ld:
        recipe["title"] = json_ld.get("name", "")
        recipe["description"] = json_ld.get("description", "")
        recipe["prep_time"] = json_ld.get("prepTime", "")
        recipe["cook_time"] = json_ld.get("cookTime", "")
        yield_val = json_ld.get("recipeYield", "")
        if isinstance(yield_val, list):
            yield_val = yield_val[0] if yield_val else ""
        recipe["servings"] = str(yield_val)

        ingredients = json_ld.get("recipeIngredient", [])
        if isinstance(ingredients, list):
            recipe["ingredients"] = ingredients

        instructions = json_ld.get("recipeInstructions", [])
        if isinstance(instructions, list):
            for step in instructions:
                if isinstance(step, str):
                    recipe["steps"].append(step)
                elif isinstance(step, dict):
                    recipe["steps"].append(step.get("text", ""))

    # Fallback : extraction depuis le HTML
    if not recipe["title"]:
        h1 = soup.find("h1")
        recipe["title"] = h1.get_text(strip=True) if h1 else ""

    if not recipe["ingredients"]:
        recipe["ingredients"] = extract_ingredients_from_html(soup)

    if not recipe["steps"]:
        recipe["steps"] = extract_steps_from_html(soup)

    # Texte complet comme fallback
    article = soup.find("article") or soup.find("main") or soup.find("body")
    if article:
        recipe["full_text"] = article.get_text(separator="\n", strip=True)
        # Limiter la taille
        if len(recipe["full_text"]) > 5000:
            recipe["full_text"] = recipe["full_text"][:5000]

    return recipe


def extract_json_ld(soup):
    """Extrait les données JSON-LD (schema.org Recipe) si présentes."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)

            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "Recipe":
                        return item
                    if "@graph" in item:
                        for g in item["@graph"]:
                            if g.get("@type") == "Recipe":
                                return g

            if isinstance(data, dict):
                if data.get("@type") == "Recipe":
                    return data
                if "@graph" in data:
                    for g in data["@graph"]:
                        if isinstance(g, dict) and g.get("@type") == "Recipe":
                            return g
        except (json.JSONDecodeError, AttributeError):
            continue

    return None


def extract_ingredients_from_html(soup):
    """Extraction fallback des ingrédients depuis le HTML."""
    ingredients = []

    ingredient_sections = soup.find_all(
        True,
        class_=re.compile(r"ingredient", re.I)
    )
    for section in ingredient_sections:
        for li in section.find_all("li"):
            text = li.get_text(strip=True)
            if text and len(text) > 2:
                ingredients.append(text)

    if not ingredients:
        for el in soup.find_all(["h2", "h3", "h4"]):
            if "ingrédient" in el.get_text().lower() or "ingredient" in el.get_text().lower():
                next_el = el.find_next_sibling()
                while next_el and next_el.name in ["ul", "ol", "div", "p"]:
                    for li in next_el.find_all("li"):
                        text = li.get_text(strip=True)
                        if text and len(text) > 2:
                            ingredients.append(text)
                    next_el = next_el.find_next_sibling()
                    if next_el and next_el.name in ["h2", "h3", "h4"]:
                        break
                break

    return ingredients


def extract_steps_from_html(soup):
    """Extraction fallback des étapes depuis le HTML."""
    steps = []

    step_sections = soup.find_all(
        True,
        class_=re.compile(r"(step|instruction|preparation|etape|préparation)", re.I)
    )
    for section in step_sections:
        for li in section.find_all("li"):
            text = li.get_text(strip=True)
            if text and len(text) > 10:
                steps.append(text)
        if not steps:
            for p in section.find_all("p"):
                text = p.get_text(strip=True)
                if text and len(text) > 10:
                    steps.append(text)

    if not steps:
        for el in soup.find_all(["h2", "h3", "h4"]):
            heading_text = el.get_text().lower()
            if any(kw in heading_text for kw in ["préparation", "preparation", "étape", "instruction", "recette"]):
                next_el = el.find_next_sibling()
                while next_el and next_el.name not in ["h2", "h3"]:
                    if next_el.name in ["ol", "ul"]:
                        for li in next_el.find_all("li"):
                            text = li.get_text(strip=True)
                            if text and len(text) > 10:
                                steps.append(text)
                    elif next_el.name == "p":
                        text = next_el.get_text(strip=True)
                        if text and len(text) > 10:
                            steps.append(text)
                    next_el = next_el.find_next_sibling()
                break

    return steps


def scrape_url(url):
    """Scrape une URL et extrait le contenu de la recette."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return extract_recipe_content(response.text, url)
    except Exception as e:
        return {"url": url, "error": str(e)}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """GET /api/scrape?url=https://example.com/recette"""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        url = params.get("url", [None])[0]

        if not url:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Parameter 'url' missing. Usage: /api/scrape?url=https://example.com/recipe"
            }).encode())
            return

        result = scrape_url(url)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(result, ensure_ascii=False).encode())

    def do_POST(self):
        """POST /api/scrape avec body JSON {"url": "..."} ou {"urls": ["...", "..."]}"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "JSON invalide"}).encode())
            return

        # Scrape une seule URL
        if "url" in data:
            result = scrape_url(data["url"])
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode())
            return

        # Scrape plusieurs URLs
        if "urls" in data:
            urls = data["urls"][:5]  # Max 5 URLs pour éviter les timeouts
            results = []
            for url in urls:
                results.append(scrape_url(url))

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "count": len(results),
                "recipes": results
            }, ensure_ascii=False).encode())
            return

        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "error": "Champ 'url' ou 'urls' manquant"
        }).encode())
