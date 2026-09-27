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


def score_title_match(query_words, title: str) -> int:
    title_lower = title.lower()
    return sum(1 for w in query_words if w in title_lower)
