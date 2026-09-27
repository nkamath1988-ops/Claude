"""Load skincare_dupe_bot/data/dupes_seed.json into the database.

Safe to re-run: matches existing rows on (brand, name) and updates them
instead of duplicating.
"""
import json

from skincare_dupe_bot import config
from skincare_dupe_bot.database.db import get_session, init_db
from skincare_dupe_bot.database.models import DrugstoreDupe, KBeautyProduct


def load_seed_data(path=None):
    path = path or (config.DATA_DIR / "dupes_seed.json")
    with open(path) as f:
        entries = json.load(f)

    init_db()
    created_kbeauty = 0
    created_dupes = 0

    with get_session() as session:
        for entry in entries:
            kb_data = entry["kbeauty"]
            kb = (
                session.query(KBeautyProduct)
                .filter_by(brand=kb_data["brand"], name=kb_data["name"])
                .one_or_none()
            )
            if kb is None:
                kb = KBeautyProduct(**kb_data)
                session.add(kb)
                session.flush()
                created_kbeauty += 1
            else:
                for key, value in kb_data.items():
                    setattr(kb, key, value)

            for raw_dupe_data in entry["dupes"]:
                dupe_data = dict(raw_dupe_data)
                if "typical_price_usd" in dupe_data:
                    dupe_data["last_known_price_usd"] = dupe_data.pop("typical_price_usd")

                dupe = (
                    session.query(DrugstoreDupe)
                    .filter_by(kbeauty_product_id=kb.id, brand=dupe_data["brand"], name=dupe_data["name"])
                    .one_or_none()
                )
                if dupe is None:
                    dupe = DrugstoreDupe(kbeauty_product_id=kb.id, **dupe_data)
                    session.add(dupe)
                    created_dupes += 1
                else:
                    for key, value in dupe_data.items():
                        setattr(dupe, key, value)

    return created_kbeauty, created_dupes


if __name__ == "__main__":
    kb_count, dupe_count = load_seed_data()
    print(f"Seeded {kb_count} new K-beauty products, {dupe_count} new dupes.")
