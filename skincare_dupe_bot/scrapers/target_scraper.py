"""target.com scraper -- the one confirmed-working source (see base.py)."""
from urllib.parse import quote_plus

from skincare_dupe_bot.scrapers.base import (
    ScrapedPrice,
    browser_page,
    extract_price_title_pairs,
    looks_blocked,
    score_title_match,
)

SEARCH_URL = "https://www.target.com/s?searchTerm={query}"


def search_product_price(brand: str, name: str) -> ScrapedPrice:
    query_text = f"{brand} {name}"
    url = SEARCH_URL.format(query=quote_plus(query_text))
    query_words = [w.lower() for w in query_text.split() if len(w) > 2]

    with browser_page() as page:
        try:
            page.goto(url, timeout=25000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
        except Exception as exc:
            print(f"[target_scraper] navigation failed for {url}: {exc}")
            return ScrapedPrice(price_usd=None, in_stock=False, product_url=url)

        if looks_blocked(page):
            print(f"[target_scraper] blocked for query '{query_text}'")
            return ScrapedPrice(price_usd=None, in_stock=False, product_url=url)

        body_text = page.locator("body").inner_text()

    best_price, best_title, best_score = None, None, -1
    for price, title in extract_price_title_pairs(body_text):
        score = score_title_match(query_words, title)
        if score > best_score:
            best_price, best_title, best_score = price, title, score

    # Require at least the brand word to match -- otherwise we're just
    # reporting whatever unrelated item happened to be first on the page.
    brand_word = brand.lower().split()[0]
    if best_title is None or brand_word not in best_title.lower():
        return ScrapedPrice(price_usd=None, in_stock=False, product_url=url)

    return ScrapedPrice(
        price_usd=best_price,
        in_stock=best_price is not None,
        product_url=url,
        matched_title=best_title,
    )
