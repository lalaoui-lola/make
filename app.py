from flask import Flask, request, jsonify, send_from_directory
import json
import requests as http_requests
from bs4 import BeautifulSoup, Comment
import random
import urllib.parse
import re
import os

app = Flask(__name__, static_folder="public")


# ============================================================
# SHARED
# ============================================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

REMOVE_TAGS = ["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript", "form", "button", "svg", "video", "audio", "figure", "figcaption", "ins"]
REMOVE_CLASSES = ["comment", "sidebar", "widget", "nav", "menu", "footer", "header", "ad", "pub", "social", "share", "related", "newsletter", "popup", "cookie", "banner", "breadcrumb", "pagination"]


def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


# ============================================================
# SCRAPING HELPERS
# ============================================================

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
        if any(keyword in combined for keyword in REMOVE_CLASSES):
            el.decompose()
    return soup


def extract_json_ld(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "Recipe":
                        return item
                    if isinstance(item, dict) and "@graph" in item:
                        for g in item["@graph"]:
                            if isinstance(g, dict) and g.get("@type") == "Recipe":
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
    ingredients = []
    for section in soup.find_all(True, class_=re.compile(r"ingredient", re.I)):
        for li in section.find_all("li"):
            text = li.get_text(strip=True)
            if text and len(text) > 2:
                ingredients.append(text)
    if not ingredients:
        for el in soup.find_all(["h2", "h3", "h4"]):
            if "ingredient" in el.get_text().lower():
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
    steps = []
    for section in soup.find_all(True, class_=re.compile(r"(step|instruction|preparation|direction)", re.I)):
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
            if any(kw in heading_text for kw in ["preparation", "instruction", "direction", "step", "method"]):
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


def extract_recipe_content(html, url):
    soup = BeautifulSoup(html, "html.parser")
    recipe = {"url": url, "title": "", "description": "", "prep_time": "", "cook_time": "", "servings": "", "ingredients": [], "steps": [], "full_text": ""}

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

    soup = clean_html(soup)
    if not recipe["title"]:
        h1 = soup.find("h1")
        recipe["title"] = h1.get_text(strip=True) if h1 else ""
    if not recipe["ingredients"]:
        recipe["ingredients"] = extract_ingredients_from_html(soup)
    if not recipe["steps"]:
        recipe["steps"] = extract_steps_from_html(soup)

    article = soup.find("article") or soup.find("main") or soup.find("body")
    if article:
        recipe["full_text"] = article.get_text(separator="\n", strip=True)[:5000]

    return recipe


def scrape_url(url):
    headers = {"User-Agent": random.choice(USER_AGENTS), "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"}
    try:
        response = http_requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return extract_recipe_content(response.text, url)
    except Exception as e:
        return {"url": url, "error": str(e)}


# ============================================================
# SEARCH HELPERS
# ============================================================

def search_google(query, num_results=3):
    encoded_query = urllib.parse.quote(f"recipe {query}")
    url = f"https://www.google.com/search?q={encoded_query}&num={num_results + 5}&hl=en"
    headers = {"User-Agent": random.choice(USER_AGENTS), "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9", "DNT": "1"}
    try:
        response = http_requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for g in soup.select("div.g"):
            link = g.select_one("a")
            if link and link.get("href", "").startswith("http"):
                href = link["href"]
                title_el = g.select_one("h3")
                title = title_el.get_text() if title_el else ""
                snippet_el = g.select_one("div.VwiC3b, span.aCOpRe")
                snippet = snippet_el.get_text() if snippet_el else ""
                results.append({"url": href, "title": title, "snippet": snippet})
                if len(results) >= num_results:
                    break
        return results
    except Exception as e:
        return {"error": str(e)}


def search_duckduckgo(query, num_results=3):
    encoded_query = urllib.parse.quote(f"recipe {query}")
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    headers = {"User-Agent": random.choice(USER_AGENTS), "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"}
    try:
        response = http_requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for r in soup.select(".result"):
            link = r.select_one("a.result__a")
            if link:
                href = link.get("href", "")
                title = link.get_text(strip=True)
                snippet_el = r.select_one(".result__snippet")
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                results.append({"url": href, "title": title, "snippet": snippet})
                if len(results) >= num_results:
                    break
        return results
    except Exception as e:
        return {"error": str(e)}


def clean_title(title):
    title = re.sub(r'\s*[-|–—]\s*(allrecipes|food network|simply recipes|bon app[eé]tit|delish|tasty|epicurious|bbc good food|serious eats|cooking light|recipe).*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*[-|–—]\s*\w+\.com.*$', '', title)
    title = re.sub(r'\brecipe\b\s*$', '', title, flags=re.IGNORECASE).strip()
    title = re.sub(r'\s+', ' ', title).strip()
    return title


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def index():
    return send_from_directory("public", "index.html")


@app.route("/api/health")
def health():
    return add_cors(jsonify({
        "status": "ok",
        "service": "recipe-scraper",
        "version": "2.0.0",
        "endpoints": {
            "health": "/api/health",
            "titles": "/api/titles?category=desserts&n=2",
            "search": "/api/search?q=chocolate+cake&n=3",
            "scrape": "/api/scrape?url=https://example.com/recipe",
            "full": "/api/full?q=banana+bread&n=2"
        }
    }))


@app.route("/api/titles")
def titles():
    category = request.args.get("category")
    num_results = int(request.args.get("n", 2))

    if not category:
        resp = jsonify({"error": "Parameter 'category' missing. Usage: /api/titles?category=desserts&n=2"})
        resp.status_code = 400
        return add_cors(resp)

    # Google titles
    query = f"best {category} recipes"
    encoded_query = urllib.parse.quote(query)
    results = []
    seen_titles = set()

    # Try Google
    try:
        url = f"https://www.google.com/search?q={encoded_query}&num={num_results + 10}&hl=en"
        headers = {"User-Agent": random.choice(USER_AGENTS), "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9", "DNT": "1"}
        response = http_requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for g in soup.select("div.g"):
            link = g.select_one("a")
            if link and link.get("href", "").startswith("http"):
                href = link["href"]
                title_el = g.select_one("h3")
                if not title_el:
                    continue
                title = clean_title(title_el.get_text())
                if not title or len(title) < 5 or title.lower() in seen_titles:
                    continue
                if any(skip in title.lower() for skip in ["best", "top 10", "top 20", "list of", "collection"]):
                    continue
                seen_titles.add(title.lower())
                results.append({"title": title, "url": href, "source": urllib.parse.urlparse(href).netloc})
                if len(results) >= num_results:
                    break
    except Exception:
        pass

    # Fallback DuckDuckGo
    if not results:
        try:
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            headers = {"User-Agent": random.choice(USER_AGENTS), "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"}
            response = http_requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for r in soup.select(".result"):
                link = r.select_one("a.result__a")
                if link:
                    href = link.get("href", "")
                    title = clean_title(link.get_text(strip=True))
                    if not title or len(title) < 5 or title.lower() in seen_titles:
                        continue
                    if any(skip in title.lower() for skip in ["best", "top 10", "top 20", "list of", "collection"]):
                        continue
                    seen_titles.add(title.lower())
                    results.append({"title": title, "url": href, "source": urllib.parse.urlparse(href).netloc})
                    if len(results) >= num_results:
                        break
        except Exception:
            pass

    return add_cors(jsonify({"category": category, "count": len(results), "titles": results}))


@app.route("/api/search")
def search():
    query = request.args.get("q")
    num_results = int(request.args.get("n", 3))

    if not query:
        resp = jsonify({"error": "Parameter 'q' missing. Usage: /api/search?q=chocolate+cake"})
        resp.status_code = 400
        return add_cors(resp)

    results = search_google(query, num_results)
    if isinstance(results, dict) and "error" in results:
        results = search_duckduckgo(query, num_results)

    if isinstance(results, dict) and "error" in results:
        resp = jsonify(results)
        resp.status_code = 500
        return add_cors(resp)

    return add_cors(jsonify({"query": query, "count": len(results), "results": results}))


@app.route("/api/scrape")
def scrape():
    url = request.args.get("url")
    if not url:
        resp = jsonify({"error": "Parameter 'url' missing. Usage: /api/scrape?url=https://example.com/recipe"})
        resp.status_code = 400
        return add_cors(resp)

    result = scrape_url(url)
    return add_cors(jsonify(result))


@app.route("/api/full")
def full():
    query = request.args.get("q")
    num = int(request.args.get("n", 2))

    if not query:
        resp = jsonify({"error": "Parameter 'q' missing. Usage: /api/full?q=banana+bread"})
        resp.status_code = 400
        return add_cors(resp)

    # Search
    google_results = search_google(query, num)
    if isinstance(google_results, dict) and "error" in google_results:
        google_results = []
    urls = [r["url"] if isinstance(r, dict) else r for r in google_results]

    if not urls:
        ddg_results = search_duckduckgo(query, num)
        if isinstance(ddg_results, dict) and "error" in ddg_results:
            ddg_results = []
        urls = [r["url"] if isinstance(r, dict) else r for r in ddg_results]

    if not urls:
        return add_cors(jsonify({
            "query": query, "count": 0, "recipes": [],
            "context_for_ai": f"No recipes found for '{query}'. Generate the recipe based on your knowledge."
        }))

    # Scrape
    recipes = []
    for url in urls[:num]:
        recipe = scrape_url(url)
        if "error" not in recipe:
            recipes.append(recipe)

    # Build AI context
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

    return add_cors(jsonify({
        "query": query, "count": len(recipes), "recipes": recipes,
        "context_for_ai": "\n\n".join(context_parts)
    }))


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
