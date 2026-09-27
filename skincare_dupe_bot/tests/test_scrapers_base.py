from skincare_dupe_bot.scrapers.base import extract_price_title_pairs, score_title_match

# Real layout captured from target.com's rendered body text during manual
# testing (see base.py's docstring) -- price line, then title on the next
# line, except when a subscribe-and-save annotation sits in between.
SAMPLE_BODY_TEXT = """
Shipping arrives Wed, Sep 30
Ships free - exclusions apply
Add to cart
Highly rated
$14.29
CeraVe Gentle Scalp Care Conditioner - 19 fl oz
Shipping arrives Wed, Sep 30
Ships free - exclusions apply
Add to cart
Highly rated
$16.99
CeraVe Brightening Even Tone Face Moisturizer - 8 fl oz
Ships free - exclusions apply
Add to cart
31k+ bought in last month
$14.99
When purchased online
"""


def test_extract_price_title_pairs_finds_real_pairs():
    pairs = list(extract_price_title_pairs(SAMPLE_BODY_TEXT))
    prices = [p for p, _ in pairs]
    assert 14.29 in prices
    assert 16.99 in prices


def test_extract_price_title_pairs_skips_promo_annotation_line():
    pairs = list(extract_price_title_pairs(SAMPLE_BODY_TEXT))
    titles = [t for _, t in pairs]
    assert "When purchased online" not in titles


def test_score_title_match_prefers_more_overlapping_words():
    query_words = ["cerave", "brightening", "moisturizer"]
    high = score_title_match(query_words, "CeraVe Brightening Even Tone Face Moisturizer - 8 fl oz")
    low = score_title_match(query_words, "CeraVe Gentle Scalp Care Conditioner - 19 fl oz")
    assert high > low
