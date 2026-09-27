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

# Real layout captured from a Cetaphil search -- up to two annotation lines
# ("Coupon: $2 off", "+ 1 deal") stack between the price and the title,
# sometimes with a third ("When purchased online") on top of those two.
STACKED_ANNOTATIONS_BODY_TEXT = """
Ships free - exclusions apply
Add to cart
$16.99
Coupon: $2 off
+ 1 deal
Cetaphil Nourishing Body Cream with Vitamin E - 16oz
4.8
Ships free - exclusions apply
Add to cart
$19.79
Coupon: $2 off
+ 1 deal
When purchased online
Cetaphil Deep Hydration Water Gel Moisturizer - Travel Size - 1.7oz
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


def test_extract_price_title_pairs_skips_multiple_stacked_annotations():
    # This is the exact bug found live: a naive "next line" pairing grabbed
    # "Coupon: $2 off" as the title for every Cetaphil result, so nothing
    # ever matched the brand and the whole product line up looked absent.
    pairs = list(extract_price_title_pairs(STACKED_ANNOTATIONS_BODY_TEXT))
    assert (16.99, "Cetaphil Nourishing Body Cream with Vitamin E - 16oz") in pairs
    assert (19.79, "Cetaphil Deep Hydration Water Gel Moisturizer - Travel Size - 1.7oz") in pairs
    titles = [t for _, t in pairs]
    assert not any("coupon" in t.lower() for t in titles)
    assert not any("deal" in t.lower() for t in titles)


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


def test_brand_token_skips_leading_stopwords():
    # Retailers routinely drop the article from their own listing titles
    # ("Ordinary Niacinamide..." not "The Ordinary Niacinamide...") --
    # gating on "the" rejected the correct match instead of a wrong one.
    assert brand_token("The Ordinary") == "ordinary"
    assert brand_token("Dear, Klairs") == "klairs"


def test_derive_search_query_strips_parentheticals_and_trailing_size():
    q = derive_search_query("Aquaphor", "Healing Ointment (thin layer as occlusive overnight)")
    assert "(" not in q
    assert "thin layer" not in q
    assert q == "Aquaphor Healing Ointment"

    q2 = derive_search_query("CeraVe", "Gentle Scalp Care Conditioner - 19 fl oz")
    assert q2 == "CeraVe Gentle Scalp Care Conditioner"


def test_derive_search_query_drops_leading_brand_stopword():
    # Verified live: Target returns zero results for any query starting
    # with the literal word "The", even for a brand it stocks.
    q = derive_search_query("The Ordinary", "Niacinamide 10% + Zinc 1%")
    assert not q.lower().startswith("the ")
    assert q.startswith("Ordinary")


def test_derive_search_query_strips_percentages_and_lone_plus():
    q = derive_search_query("The Ordinary", "Niacinamide 10% + Zinc 1%")
    assert "%" not in q
    assert "+" not in q
    assert "Niacinamide" in q
    assert "Zinc" in q


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


def test_best_match_returns_none_when_brand_missing_from_every_title():
    # Regression test for a real false positive found live: when Target
    # didn't rank a genuine "The Ordinary" listing, a since-removed
    # word-overlap fallback reported a Naturium product's price as if it
    # were The Ordinary's, because "niacinamide"/"zinc" overlapped enough.
    # A missing brand token must be a hard no-match, never a best guess.
    candidates = [
        (11.49, "CeraVe Baby Body Gentle Moisturizing Body Cream - 5 fl oz"),
        (13.59, "Naturium Niacinamide Serum 12% Plus Zinc 2% - 1 fl oz"),
    ]
    query_words = query_words_for("Cetaphil", "Moisturizing Cream")
    price, title = best_match(candidates, "Cetaphil", query_words)
    assert price is None
    assert title is None


def test_best_match_returns_none_on_zero_overlap():
    candidates = [(3.50, "Completely Unrelated Snack Chips - Family Size")]
    query_words = query_words_for("Cetaphil", "Moisturizing Cream")
    price, title = best_match(candidates, "Cetaphil", query_words)
    assert price is None
    assert title is None
