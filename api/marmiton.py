"""
api/marmiton.py — Scraper Marmiton.org
=======================================
Source FR : Marmiton.org — plus grand site de recettes français.
✅ Gratuit, sans clé API.
✅ JSON-LD structuré sur les pages recettes.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import re
import requests
from bs4 import BeautifulSoup
from utils import get_headers, scrape_url, error_response

BASE = "https://www.marmiton.org"


def _search_urls(query, page=1, n=5):
    """Recherche des URLs de recettes Marmiton pour une requête."""
    try:
        url = f"{BASE}/recettes/recherche.aspx?aqt={requests.utils.quote(query)}&page={page}"
        resp = requests.get(url, headers=get_headers(), timeout=12)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r"marmiton\.org/recettes/recette_[a-z0-9\-_]+\.aspx", href):
                if href not in links:
                    links.append(href)
            elif re.search(r"^/recettes/recette_[a-z0-9\-_]+\.aspx", href):
                full = BASE + href
                if full not in links:
                    links.append(full)
        return links[:n]
    except Exception:
        return []


def _list_category_urls(category, page=1, n=5):
    """Cherche des recettes Marmiton par catégorie (via recherche)."""
    return _search_urls(category, page=page, n=n)


def _scrape_recipe(url):
    """Scrape une recette Marmiton — utilise JSON-LD en priorité."""
    return scrape_url(url, source_site="marmiton.org")
