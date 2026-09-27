"""target.com scraper -- the one confirmed-working source (see base.py)."""
from urllib.parse import quote_plus

from skincare_dupe_bot.scrapers.base import (
    ScrapedPrice,
    best_match,
    browser_page,
    derive_search_query,
    extract_price_title_pairs,
    looks_blocked,
    query_words_for,
)

SEARCH_URL = "https://www.target.com/s?searchTerm={query}"


def search_product_price(brand: str, name: str) -> ScrapedPrice:
    search_query = derive_search_query(brand, name)
    url = SEARCH_URL.format(query=quote_plus(search_query))
    query_words = query_words_for(brand, name)

    with browser_page() as page:
        try:
            page.goto(url, timeout=25000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
        except Exception as exc:
            print(f"[target_scraper] navigation failed for {url}: {exc}")
            return ScrapedPrice(price_usd=None, in_stock=False, product_url=url)

        if looks_blocked(page):
            print(f"[target_scraper] blocked for query '{search_query}'")
            return ScrapedPrice(price_usd=None, in_stock=False, product_url=url)

        body_text = page.locator("body").inner_text()

    candidates = list(extract_price_title_pairs(body_text))
    price, title = best_match(candidates, brand, query_words)

    if price is None:
        return ScrapedPrice(price_usd=None, in_stock=False, product_url=url)

    return ScrapedPrice(price_usd=price, in_stock=True, product_url=url, matched_title=title)
