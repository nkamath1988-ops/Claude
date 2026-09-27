from skincare_dupe_bot.scrapers.base import (
    best_match,
    brand_token,
    derive_search_query,
    extract_price_title_pairs,
    normalize,
    query_words_for,
    score_title_match,
)

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


def test_normalize_strips_punctuation():
    assert normalize("e.l.f.") == "e l f"
    assert normalize("Dear, Klairs") == "dear  klairs"


def test_brand_token_handles_punctuated_brands():
    assert brand_token("e.l.f.") == "e"  # first normalized token, punctuation stripped
    assert brand_token("CeraVe") == "cerave"
    assert brand_token("The Ordinary") == "the"


def test_derive_search_query_strips_parentheticals_and_trailing_size():
    q = derive_search_query("Aquaphor", "Healing Ointment (thin layer as occlusive overnight)")
    assert "(" not in q
    assert "thin layer" not in q
    assert q == "Aquaphor Healing Ointment"

    q2 = derive_search_query("CeraVe", "Gentle Scalp Care Conditioner - 19 fl oz")
    assert q2 == "CeraVe Gentle Scalp Care Conditioner"


def test_query_words_for_uses_cleaned_query():
    words = query_words_for("Aquaphor", "Healing Ointment (thin layer as occlusive overnight)")
    assert "thin" not in words
    assert "layer" not in words
    assert "healing" in words


def test_best_match_prefers_branded_candidate_even_with_lower_word_overlap():
    candidates = [
        (16.99, "CeraVe Brightening Even Tone Face Moisturizer - 8 fl oz"),
        (9.99, "Neutrogena Brightening Boost Serum"),  # more word overlap but wrong brand
    ]
    query_words = query_words_for("CeraVe", "Brightening Even Tone Face Moisturizer")
    price, title = best_match(candidates, "CeraVe", query_words)
    assert price == 16.99
    assert "CeraVe" in title


def test_best_match_falls_back_to_word_overlap_when_brand_missing_from_any_title():
    candidates = [(11.49, "CeraVe Baby Body Gentle Moisturizing Body Cream - 5 fl oz")]
    query_words = query_words_for("Cetaphil", "Moisturizing Cream")
    price, title = best_match(candidates, "Cetaphil", query_words)
    # brand never appears, but "moisturizing" overlaps -- weak fallback, not nothing
    assert price == 11.49


def test_best_match_returns_none_on_zero_overlap():
    candidates = [(3.50, "Completely Unrelated Snack Chips - Family Size")]
    query_words = query_words_for("Cetaphil", "Moisturizing Cream")
    price, title = best_match(candidates, "Cetaphil", query_words)
    assert price is None
    assert title is None
