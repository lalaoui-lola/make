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
    "figcaption", "ins"
]

REMOVE_CLASSES = [
    "comment", "sidebar", "widget", "nav", "menu", "footer", "header",
    "ad", "pub", "social", "share", "related", "newsletter", "popup",
    "cookie", "banner", "breadcrumb", "pagination"
]


def clean_html(soup):
    for tag in REMOVE_TAGS:
        for el in soup.find_all(tag):
            el.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    for el in soup.find_all(True):
        class_list = " ".join(el.get("class", []))
        id_val = el.get("id", "")
        combined = f"{class_list} {id_val}".lower()
        if any(kw in combined for kw in REMOVE_CLASSES):
            el.decompose()
    return soup


def extract_json_ld(soup):
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


def extract_recipe_content(html, url):
    soup = BeautifulSoup(html, "lxml")
    recipe = {"url": url, "title": "", "ingredients": [], "steps": [], "full_text": ""}

    # JSON-LD d'abord
    json_ld = extract_json_ld(BeautifulSoup(html, "lxml"))
    if json_ld:
        recipe["title"] = json_ld.get("name", "")
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

    soup = clean_html(soup)

    if not recipe["title"]:
        h1 = soup.find("h1")
        recipe["title"] = h1.get_text(strip=True) if h1 else ""

    article = soup.find("article") or soup.find("main") or soup.find("body")
    if article:
        recipe["full_text"] = article.get_text(separator="\n", strip=True)[:5000]

    return recipe


def search_duckduckgo(query, num_results=3):
    encoded_query = urllib.parse.quote(f"recipe {query}")
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        results = []
        for r in soup.select(".result"):
            link = r.select_one("a.result__a")
            if link:
                href = link.get("href", "")
                results.append(href)
                if len(results) >= num_results:
                    break
        return results
    except Exception:
        return []


def search_google(query, num_results=3):
    encoded_query = urllib.parse.quote(f"recipe {query}")
    url = f"https://www.google.com/search?q={encoded_query}&num={num_results + 5}&hl=en"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html",
        "Accept-Language": "en-US,en;q=0.9",
        "DNT": "1",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        results = []
        for g in soup.select("div.g"):
            link = g.select_one("a")
            if link and link.get("href", "").startswith("http"):
                results.append(link["href"])
                if len(results) >= num_results:
                    break
        return results
    except Exception:
        return []


def scrape_url(url):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html",
        "Accept-Language": "en-US,en;q=0.9",
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
        """
        GET /api/full?q=tarte+aux+pommes&n=2
        Recherche + scrape en un seul appel.
        Retourne les recettes scrapées prêtes à envoyer à l'IA.
        """
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        query = params.get("q", [None])[0]
        num = int(params.get("n", [2])[0])

        if not query:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Paramètre 'q' manquant. Usage: /api/full?q=tarte+aux+pommes"
            }).encode())
            return

        # Recherche
        urls = search_google(query, num)
        if not urls:
            urls = search_duckduckgo(query, num)

        if not urls:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "query": query,
                "count": 0,
                "recipes": [],
                "context_for_ai": f"No recipes found for '{query}'. Generate the recipe based on your knowledge."
            }, ensure_ascii=False).encode())
            return

        # Scrape chaque URL
        recipes = []
        for url in urls[:num]:
            recipe = scrape_url(url)
            if "error" not in recipe:
                recipes.append(recipe)

        # Préparer le contexte pour l'IA
        context_parts = []
        for i, r in enumerate(recipes, 1):
            parts = [f"=== SOURCE RECIPE {i} ==="]
            if r.get("title"):
                parts.append(f"Title: {r['title']}")
            if r.get("ingredients"):
                parts.append("Ingredients: " + ", ".join(r["ingredients"]))
            if r.get("steps"):
                parts.append("Steps: " + " | ".join(r["steps"]))
            elif r.get("full_text"):
                parts.append(f"Content: {r['full_text'][:2000]}")
            context_parts.append("\n".join(parts))

        context_for_ai = "\n\n".join(context_parts)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({
            "query": query,
            "count": len(recipes),
            "recipes": recipes,
            "context_for_ai": context_for_ai
        }, ensure_ascii=False).encode())

    def do_POST(self):
        """POST /api/full avec body JSON {"query": "tarte aux pommes", "num_results": 2}"""
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

        query = data.get("query")
        num = data.get("num_results", 2)

        if not query:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Champ 'query' manquant"}).encode())
            return

        urls = search_google(query, num)
        if not urls:
            urls = search_duckduckgo(query, num)

        recipes = []
        for url in urls[:num]:
            recipe = scrape_url(url)
            if "error" not in recipe:
                recipes.append(recipe)

        context_parts = []
        for i, r in enumerate(recipes, 1):
            parts = [f"=== SOURCE RECIPE {i} ==="]
            if r.get("title"):
                parts.append(f"Title: {r['title']}")
            if r.get("ingredients"):
                parts.append("Ingredients: " + ", ".join(r["ingredients"]))
            if r.get("steps"):
                parts.append("Steps: " + " | ".join(r["steps"]))
            elif r.get("full_text"):
                parts.append(f"Content: {r['full_text'][:2000]}")
            context_parts.append("\n".join(parts))

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({
            "query": query,
            "count": len(recipes),
            "recipes": recipes,
            "context_for_ai": "\n\n".join(context_parts)
        }, ensure_ascii=False).encode())
