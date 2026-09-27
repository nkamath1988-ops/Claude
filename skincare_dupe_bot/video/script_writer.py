"""Template-based script/caption generation for a K-beauty-vs-dupe reel.

Deliberately not LLM-generated at runtime: this is a zero-capital project,
and calling a paid API per video would break that. Variety comes from
randomized phrasing pools, not a language model.
"""
import random
from dataclasses import dataclass


HOOKS_WITH_SAVINGS = [
    "This ${kb_price:.0f} K-beauty {category} has a dupe at {retailer} for ${dupe_price:.2f}.",
    "Why pay ${kb_price:.2f} for {kb_brand} when {dupe_brand} does something close for ${dupe_price:.2f}?",
    "K-beauty {category} alert: {kb_brand} {kb_name} versus the ${dupe_price:.2f} {retailer} pick.",
    "Skip the ${kb_price:.0f} K-beauty version. {retailer} has this for ${dupe_price:.2f}.",
]

# Used when the "dupe" isn't actually cheaper (or we have no confirmed
# scraped price yet) -- never claim savings that aren't real.
HOOKS_NO_SAVINGS = [
    "{kb_brand} {kb_name} and {retailer}'s {dupe_brand} {dupe_name} lean on the same actives.",
    "K-beauty {category} versus a {retailer} pick with a similar formula: {kb_brand} vs. {dupe_brand}.",
    "Same core actives, different shelf: {kb_brand} {kb_name} next to {dupe_brand} at {retailer}.",
]

CTAS = [
    "Follow for more Korean skincare dupes you can actually find at the drugstore.",
    "Save this for your next {retailer} run.",
    "More drugstore K-beauty dupes coming -- follow so you don't miss them.",
    "Comment your skin type and I'll find your next dupe.",
]

HASHTAG_POOL = [
    "#kbeauty", "#kbeautydupes", "#skincaredupes", "#drugstoreskincare",
    "#koreanskincare", "#affordableskincare", "#skintok", "#glowup",
    "#skincareroutine", "#budgetskincare",
]


@dataclass
class Script:
    hook: str
    body: str
    cta: str
    full_narration: str
    caption: str
    hashtags: str


MEANINGFUL_SAVINGS_PCT = 5.0
MEANINGFUL_SAVINGS_USD = 0.50


def savings_pct(kb_price: float, dupe_price: float) -> float:
    if not kb_price or kb_price <= 0:
        return 0.0
    return (kb_price - dupe_price) / kb_price * 100


def has_meaningful_savings(kb_price: float, dupe_price: float) -> bool:
    pct = savings_pct(kb_price, dupe_price)
    savings = (kb_price or 0.0) - dupe_price
    return pct >= MEANINGFUL_SAVINGS_PCT and savings >= MEANINGFUL_SAVINGS_USD


def _savings_line(kb_price: float, dupe_price: float) -> str:
    if not has_meaningful_savings(kb_price, dupe_price):
        return ""
    pct = savings_pct(kb_price, dupe_price)
    savings = kb_price - dupe_price
    return f"That's {pct:.0f}% cheaper, about ${savings:.2f} saved."


def _actives_line(kbeauty, dupe) -> str:
    if dupe.match_notes:
        return dupe.match_notes
    return f"Both lean on {dupe.key_actives or 'similar actives'} for the same core job."


def generate_script(kbeauty, dupe) -> Script:
    kb_price = kbeauty.typical_price_usd or 0.0
    dupe_price = dupe.last_known_price_usd or dupe.typical_price_usd or 0.0
    retailer_display = (dupe.retailer or "the drugstore").title()

    hook_pool = HOOKS_WITH_SAVINGS if has_meaningful_savings(kb_price, dupe_price) else HOOKS_NO_SAVINGS
    hook = random.choice(hook_pool).format(
        kb_price=kb_price,
        dupe_price=dupe_price,
        category=kbeauty.category or "product",
        kb_brand=kbeauty.brand,
        kb_name=kbeauty.name,
        dupe_brand=dupe.brand,
        dupe_name=dupe.name,
        retailer=retailer_display,
    )

    body_parts = [_actives_line(kbeauty, dupe)]
    savings = _savings_line(kb_price, dupe_price)
    if savings:
        body_parts.append(savings)
    body = " ".join(body_parts)

    cta_template = random.choice(CTAS)
    cta = cta_template.format(retailer=retailer_display)

    full_narration = f"{hook} {body} {cta}"

    caption_core = f"{kbeauty.brand} {kbeauty.name} vs. {dupe.brand} {dupe.name}."
    caption = f"{caption_core} {savings}".strip() if savings else caption_core
    hashtags = " ".join(random.sample(HASHTAG_POOL, k=6))

    return Script(hook=hook, body=body, cta=cta, full_narration=full_narration, caption=caption, hashtags=hashtags)
