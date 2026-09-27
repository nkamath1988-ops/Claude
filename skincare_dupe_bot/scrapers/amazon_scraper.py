"""amazon.com scraper -- kept for completeness, but blocked from this
environment's network by an Akamai bot-management interstitial (see
base.py's module docstring for the verified test result). Left in place
because a different origin IP (e.g. a home machine) may not hit the same
block; don't assume it works without testing from wherever it actually runs.
"""
from urllib.parse import quote_plus

from skincare_dupe_bot.scrapers.base import (
    ScrapedPrice,
    browser_page,
    extract_price_title_pairs,
    looks_blocked,
    score_title_match,
)

SEARCH_URL = "https://www.amazon.com/s?k={query}"


def search_product_price(brand: str, name: str) -> ScrapedPrice:
    query_text = f"{brand} {name}"
    url = SEARCH_URL.format(query=quote_plus(query_text))
    query_words = [w.lower() for w in query_text.split() if len(w) > 2]

    with browser_page() as page:
        try:
            page.goto(url, timeout=25000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
        except Exception as exc:
            print(f"[amazon_scraper] navigation failed for {url}: {exc}")
            return ScrapedPrice(price_usd=None, in_stock=False, product_url=url)

        if looks_blocked(page) or "interstitial" in page.content().lower():
            print(f"[amazon_scraper] blocked for query '{query_text}' (expected from this network)")
            return ScrapedPrice(price_usd=None, in_stock=False, product_url=url)

        body_text = page.locator("body").inner_text()

    best_price, best_title, best_score = None, None, -1
    for price, title in extract_price_title_pairs(body_text):
        score = score_title_match(query_words, title)
        if score > best_score:
            best_price, best_title, best_score = price, title, score

    brand_word = brand.lower().split()[0]
    if best_title is None or brand_word not in (best_title or "").lower():
        return ScrapedPrice(price_usd=None, in_stock=False, product_url=url)

    return ScrapedPrice(
        price_usd=best_price,
        in_stock=best_price is not None,
        product_url=url,
        matched_title=best_title,
    )
