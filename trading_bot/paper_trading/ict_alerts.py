"""Ledger + level conversion for Robinhood stop/target alerts on the ICT SPX paper trades.

Robinhood alerts can only watch equities/crypto (not the SPX index) and only on price/indicator
conditions, so each paper signal gets two SPY price alerts (stop and target) with the SPX level
converted at the live SPY/SPX ratio. This module only *plans* alerts and records what was
created; the routine performs the actual Robinhood calls. Guardrails: SPY only, price_above /
price_below only, at most `MAX_ACTIVE` routine-created alerts live at once, one pair per signal
(idempotent by signal id), pause-not-delete when the paper trade exits.
"""
from __future__ import annotations

import json
from pathlib import Path

MAX_ACTIVE = 6


def load(path: str) -> dict:
    return json.load(open(path)) if Path(path).exists() else {"alerts": []}


def save(led: dict, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    json.dump(led, open(path, "w"), indent=2, sort_keys=True)


def _cond(side: str, role: str) -> str:
    # long: stop is below, target above; short: mirrored
    below = (side == "long") == (role == "stop")
    return "price_below" if below else "price_above"


def plan(led: dict, event: dict, spx: float, spy: float) -> list[dict]:
    """Alert specs to create for a SIGNAL event ([] if already planned, exit event, or cap reached)."""
    if event.get("type") != "SIGNAL":
        return []
    key = f"{event['variant']}:{event['signal_time']}"
    if any(a["key"] == key for a in led["alerts"]):
        return []
    active = sum(a["active"] for a in led["alerts"])
    if active + 2 > MAX_ACTIVE:
        return []
    ratio = spy / spx
    return [dict(key=key, role=role, symbol="SPY", condition_type=_cond(event["side"], role),
                 threshold=f"{event[role] * ratio:.2f}", spx_level=event[role], ratio=round(ratio, 6))
            for role in ("stop", "target")]


def record(led: dict, spec: dict, alert_id: str) -> None:
    led["alerts"].append(dict(key=spec["key"], role=spec["role"], alert_id=alert_id,
                              condition_type=spec["condition_type"], threshold=spec["threshold"],
                              spx_level=spec["spx_level"], active=True))


def deactivate(led: dict, variant: str, signal_time: str) -> list[str]:
    """Mark a trade's alerts inactive; returns their alert ids so the routine can PAUSE them."""
    key = f"{variant}:{signal_time}"
    ids = []
    for a in led["alerts"]:
        if a["key"] == key and a["active"]:
            a["active"] = False
            ids.append(a["alert_id"])
    return ids
