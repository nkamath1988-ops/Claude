"""Shared Playwright scraping helpers.

Honest finding from testing this from this environment's network (2026-09-27):
- target.com: works. Server-renders enough for a headless browser to read
  after JS runs; no block encountered across multiple test queries.
- cvs.com: blocked at the CDN/WAF edge (Akamai "Access Denied", HTTP 403)
  before the app even loads. A headless browser doesn't help — this isn't a
  JS challenge to solve, it's an IP-level deny. Only a residential proxy or
  a different origin IP would get past it, and that costs money.
- amazon.com: blocked by an Akamai bot-management interstitial (a
  proof-of-work JS challenge page, not real search results) from this
  environment's IP.
- walgreens.com: returned a near-empty page (likely PerimeterX or similar),
  no usable content.

So this scraper is built around target.com as the confirmed-working source.
The amazon module is kept and still attempted (a different network, e.g.
running this from a home machine, may not be blocked the same way) but its
failure is expected, not a bug. Do not spend effort trying to "fix" cvs.com
or walgreens.com scraping without a paid proxy service — that would break
the zero-capital constraint this project was built under.
"""
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import sync_playwright

from skincare_dupe_bot import config

CHROMIUM_PATH = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

BLOCK_TITLE_SIGNALS = [
    "access denied",
    "are you a human",
    "robot check",
    "pardon our interruption",
    "request unsuccessful",
]

# Body-text price lines are frequently followed by a subscription/promo
# annotation instead of the product title; skip those rather than mis-pairing.
NON_TITLE_NEXT_LINES = {
    "when purchased online",
    "with target circle",
    "clip coupon",
}


@dataclass
class ScrapedPrice:
    price_usd: Optional[float]
    in_stock: bool
    product_url: str
    matched_title: Optional[str] = None


@contextmanager
def browser_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROMIUM_PATH,
            headless=True,
            # Scoped to this scraper's own traffic only, hitting public retail
            # search pages with no credentials involved. Needed because Chromium's
            # built-in root store doesn't pick up the proxy CA the way curl/requests
            # do via SSL_CERT_FILE. See module docstring for why plain requests
            # (which does trust the CA) still fails on these specific sites (js
            # challenges / CDN-level blocks, not a cert problem).
            args=["--ignore-certificate-errors"],
        )
        page = browser.new_page(user_agent=config.SCRAPE_USER_AGENT)
        try:
            yield page
        finally:
            browser.close()


def looks_blocked(page) -> bool:
    title = (page.title() or "").lower()
    return any(signal in title for signal in BLOCK_TITLE_SIGNALS)


def extract_price_title_pairs(body_text: str):
    """Yield (price, title) pairs from a retail search page's rendered text.

    Retail search-result pages reliably put the price on its own line
    immediately followed by the product title line, once promo/subscription
    annotation lines are skipped. This is a text-layout heuristic, not real
    DOM parsing, so it will break if a site's layout changes -- that's an
    accepted tradeoff for not hand-maintaining CSS selectors per retailer.
    """
    lines = [l.strip() for l in body_text.split("\n") if l.strip()]
    price_re = re.compile(r"^\$\d{1,3}\.\d{2}$")

    for i, line in enumerate(lines):
        if not price_re.match(line):
            continue
        if i + 1 >= len(lines):
            continue
        next_line = lines[i + 1]
        if next_line.lower() in NON_TITLE_NEXT_LINES:
            continue
        price = float(line.replace("$", ""))
        yield price, next_line


def normalize(text: str) -> str:
    """Lowercase and strip punctuation so 'e.l.f.' matches 'ELF', 'Dear,
    Klairs' matches 'Dear Klairs', etc. Both sides of every comparison in
    this module go through this before comparing."""
    return re.sub(r"[^a-z0-9\s]", " ", text.lower()).strip()


BRAND_STOPWORDS = {"the", "a", "an", "dear"}


def brand_token(brand: str) -> str:
    """First meaningful normalized word of a brand name, used as a loose
    sanity check that a matched title is actually for the right brand.

    Skips leading stopwords like "the" (as in "The Ordinary") -- retailers
    routinely drop the article from their own listing titles ("Ordinary
    Niacinamide..."), so gating on "the" rejects the correct match instead
    of a wrong one. Falls back to the raw first word if every word is a
    stopword, rather than returning an empty (always-failing) token.
    """
    words = normalize(brand).split()
    for word in words:
        if word not in BRAND_STOPWORDS:
            return word
    return words[0] if words else ""


# Trailing descriptive text ("(thin layer as occlusive overnight)", "- 8 fl
# oz", "(unscented)") belongs in captions and match notes, not in a search
# box -- sending it as a literal query returns worse or no results. Strip it
# for the query only; the original name still drives all display text.
_PARENTHETICAL_RE = re.compile(r"\([^)]*\)")
_TRAILING_DASH_RE = re.compile(r"\s+-\s+.*$")


def derive_search_query(brand: str, name: str) -> str:
    cleaned = _PARENTHETICAL_RE.sub("", name)
    cleaned = _TRAILING_DASH_RE.sub("", cleaned)
    cleaned = " ".join(cleaned.split())
    return f"{brand} {cleaned}".strip()


def query_words_for(brand: str, name: str) -> list:
    cleaned_query = derive_search_query(brand, name)
    return [w for w in normalize(cleaned_query).split() if len(w) > 2]


def score_title_match(query_words, title: str) -> int:
    title_words = set(normalize(title).split())
    return sum(1 for w in query_words if w in title_words)


def best_match(candidates, brand: str, query_words):
    """Pick the best (price, title) candidate for a given brand.

    Prefers candidates whose title actually contains the brand name (the
    common case); if none do -- e.g. the brand token got mangled by a
    layout quirk -- falls back to the single strongest word-overlap match
    rather than giving up outright, as long as it shares at least one real
    word with the query (never return a match on zero overlap).
    """
    token = brand_token(brand)
    branded, unbranded = [], []
    for price, title in candidates:
        score = score_title_match(query_words, title)
        entry = (score, price, title)
        if token and token in normalize(title).split():
            branded.append(entry)
        else:
            unbranded.append(entry)

    if branded:
        best = max(branded, key=lambda e: e[0])
        return best[1], best[2]

    if unbranded:
        best = max(unbranded, key=lambda e: e[0])
        if best[0] >= 1:
            return best[1], best[2]

    return None, None
