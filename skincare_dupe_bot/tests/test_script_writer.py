from types import SimpleNamespace

from skincare_dupe_bot.video.script_writer import generate_script, has_meaningful_savings


def make_kbeauty(price):
    return SimpleNamespace(brand="TestKB", name="Test Essence", category="essence", typical_price_usd=price)


def make_dupe(price, retailer="cvs", match_notes="shares niacinamide"):
    return SimpleNamespace(
        brand="TestDupe", name="Test Cream", category="moisturizer", key_actives="niacinamide",
        match_notes=match_notes, retailer=retailer, last_known_price_usd=price, typical_price_usd=price,
    )


def test_has_meaningful_savings_true_for_real_gap():
    assert has_meaningful_savings(25.0, 10.0) is True


def test_has_meaningful_savings_false_when_dupe_costs_more():
    assert has_meaningful_savings(19.0, 19.0) is False
    assert has_meaningful_savings(19.0, 22.0) is False


def test_has_meaningful_savings_false_for_trivial_gap():
    # 2% off a $19 item is real money-wise noise, not a claim worth making.
    assert has_meaningful_savings(19.0, 18.65) is False


def test_script_never_claims_savings_when_not_meaningful():
    kb = make_kbeauty(19.0)
    dupe = make_dupe(19.0)  # same price -- this was the real bug found during manual testing
    script = generate_script(kb, dupe)

    assert "cheaper" not in script.full_narration.lower()
    assert "$" not in script.body or "saved" not in script.body.lower()


def test_script_claims_savings_when_meaningful():
    kb = make_kbeauty(25.0)
    dupe = make_dupe(10.0)
    script = generate_script(kb, dupe)

    assert "cheaper" in script.full_narration.lower()
    assert "saved" in script.body.lower()


def test_script_produces_hashtags_and_caption():
    kb = make_kbeauty(25.0)
    dupe = make_dupe(10.0)
    script = generate_script(kb, dupe)

    assert script.hashtags.startswith("#")
    assert len(script.hashtags.split()) == 6
    assert kb.brand in script.caption
    assert dupe.brand in script.caption
