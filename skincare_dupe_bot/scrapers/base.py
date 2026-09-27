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
NON_TITLE_NEXT_LINE_PATTERNS = [
    re.compile(r"^coupon:.*off$"),
    re.compile(r"^\+\s*\d+\s*deals?$"),
]
# How many annotation lines can stack between a price and its title -- seen
# up to 2 in practice ("Coupon: $2 off" then "+ 1 deal"); capped so this
# can't wander arbitrarily far and grab an unrelated line as a fake title.
MAX_ANNOTATION_LOOKAHEAD = 4


def _is_annotation_line(line: str) -> bool:
    lowered = line.lower()
    if lowered in NON_TITLE_NEXT_LINES:
        return True
    return any(p.match(lowered) for p in NON_TITLE_NEXT_LINE_PATTERNS)


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

        # Walk forward past any stacked annotation lines (coupon callouts,
        # deal badges, subscription pricing notes) to find the real title.
        # Bail without yielding if we hit another price first, or run out
        # of lookahead -- better to skip a candidate than mis-pair it.
        for offset in range(1, MAX_ANNOTATION_LOOKAHEAD + 1):
            j = i + offset
            if j >= len(lines):
                break
            candidate = lines[j]
            if price_re.match(candidate):
                break
            if _is_annotation_line(candidate):
                continue
            price = float(line.replace("$", ""))
            yield price, candidate
            break


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
_PERCENTAGE_TOKEN_RE = re.compile(r"\b\d+(?:\.\d+)?%")
_LONE_PLUS_RE = re.compile(r"(?<=\s)\+(?=\s)")


def _strip_leading_stopword(brand: str) -> str:
    """Drop a leading 'The'/'A'/'An'/'Dear' from a brand for query purposes.

    Verified live: Target's own search reliably returns zero results for a
    query starting with the literal word "The" (e.g. "The Ordinary
    Niacinamide" -> "No results", "Ordinary Niacinamide" -> 40 results),
    even though "The Ordinary" is a brand Target stocks and filters on
    elsewhere in its UI. Root cause not fully explained (query-parsing quirk
    on their end, possibly inconsistent), but the workaround is simple and
    doesn't cost anything the brand-matching gate still needs -- brand_token()
    handles the stopword separately for scoring purposes.
    """
    words = brand.split()
    if words and words[0].lower() in BRAND_STOPWORDS:
        return " ".join(words[1:]) or brand
    return brand


def derive_search_query(brand: str, name: str) -> str:
    cleaned = _PARENTHETICAL_RE.sub("", name)
    cleaned = _TRAILING_DASH_RE.sub("", cleaned)
    # Ingredient percentages ("10% + Zinc 1%") confuse Target's search --
    # verified live that dropping them turns "No results" into 30-40 real
    # hits for the exact same product, with no loss of match quality since
    # these tokens don't appear in retailers' own listing titles anyway.
    cleaned = _PERCENTAGE_TOKEN_RE.sub("", cleaned)
    cleaned = _LONE_PLUS_RE.sub("", cleaned)
    cleaned = " ".join(cleaned.split())

    query_brand = _strip_leading_stopword(brand)
    return f"{query_brand} {cleaned}".strip()


def query_words_for(brand: str, name: str) -> list:
    cleaned_query = derive_search_query(brand, name)
    return [w for w in normalize(cleaned_query).split() if len(w) > 2]


def score_title_match(query_words, title: str) -> int:
    title_words = set(normalize(title).split())
    return sum(1 for w in query_words if w in title_words)


def best_match(candidates, brand: str, query_words):
    """Pick the best (price, title) candidate for a given brand.

    Requires the brand token to literally appear in the title -- no
    fallback to word-overlap-only matches. An earlier version of this
    function fell back to the best-overlapping candidate when nothing
    contained the brand, meant to rescue cases where a layout quirk mangled
    the pairing. Verified live that this was actively dangerous instead:
    when Target doesn't rank a real "The Ordinary" listing for a search, it
    shows competitor products (Naturium, La Roche Posay, Good Molecules)
    with enough incidental word overlap ("niacinamide", "zinc") to pass the
    old threshold, and the fallback reported their price as if it were The
    Ordinary's. A wrong brand's price flowing into an alert or a video
    script is worse than this dupe just not resolving this run -- so a
    missing brand token is now a hard no-match, not a "best guess."
    """
    token = brand_token(brand)
    if not token:
        return None, None

    branded = [
        (score_title_match(query_words, title), price, title)
        for price, title in candidates
        if token in normalize(title).split()
    ]
    if not branded:
        return None, None

    best = max(branded, key=lambda e: e[0])
    return best[1], best[2]
