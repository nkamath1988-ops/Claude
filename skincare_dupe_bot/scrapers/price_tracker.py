"""Orchestrates price checks across all seeded dupes.

Regardless of which retailer a dupe's seed data names, this always tries
target.com first (the confirmed-working source) and falls back to amazon.com
as a best-effort second attempt. See base.py's docstring for why cvs.com and
walgreens.com aren't wired in here at all -- they're blocked from this
environment's network and there's no free fix for that.
"""
import time
from dataclasses import dataclass
from typing import List

from skincare_dupe_bot import config
from skincare_dupe_bot.database.db import get_session
from skincare_dupe_bot.database.models import DrugstoreDupe, PriceHistory
from skincare_dupe_bot.scrapers import amazon_scraper, target_scraper


@dataclass
class PriceDrop:
    dupe_id: int
    brand: str
    name: str
    old_price: float
    new_price: float
    drop_pct: float
    product_url: str


def check_one_dupe(dupe: DrugstoreDupe):
    result = target_scraper.search_product_price(dupe.brand, dupe.name)
    if result.price_usd is None:
        result = amazon_scraper.search_product_price(dupe.brand, dupe.name)
    return result


def run_price_check(limit: int = None) -> List[PriceDrop]:
    drops: List[PriceDrop] = []

    with get_session() as session:
        dupes = session.query(DrugstoreDupe).all()
        if limit:
            dupes = dupes[:limit]

        for dupe in dupes:
            result = check_one_dupe(dupe)
            time.sleep(1.5)  # be polite between requests even to the working source

            if result.price_usd is None:
                print(f"[price_tracker] no price found for {dupe.brand} {dupe.name}")
                continue

            old_price = dupe.last_known_price_usd
            session.add(
                PriceHistory(
                    dupe_id=dupe.id,
                    price_usd=result.price_usd,
                    in_stock=1 if result.in_stock else 0,
                )
            )
            dupe.last_known_price_usd = result.price_usd
            dupe.product_url = result.product_url

            if old_price and old_price > 0:
                drop_pct = (old_price - result.price_usd) / old_price * 100
                if drop_pct >= config.PRICE_DROP_ALERT_THRESHOLD_PCT:
                    drops.append(
                        PriceDrop(
                            dupe_id=dupe.id,
                            brand=dupe.brand,
                            name=dupe.name,
                            old_price=old_price,
                            new_price=result.price_usd,
                            drop_pct=drop_pct,
                            product_url=result.product_url,
                        )
                    )

    return drops


if __name__ == "__main__":
    found_drops = run_price_check()
    print(f"Checked dupes. {len(found_drops)} price drop(s) found.")
    for d in found_drops:
        print(f"  {d.brand} {d.name}: ${d.old_price:.2f} -> ${d.new_price:.2f} ({d.drop_pct:.0f}% off)")
