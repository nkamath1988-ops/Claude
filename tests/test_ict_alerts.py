from trading_bot.paper_trading import ict_alerts as L

SHORT = dict(type="SIGNAL", variant="spec9", side="short", signal_time="2026-10-01T15:00:00Z", stop=7021.5, target=6960.0)
LONG = dict(SHORT, side="long", signal_time="2026-10-01T16:00:00Z", stop=6960.0, target=7021.5)


def test_conditions_are_mirrored_and_levels_converted():
    s = {x["role"]: x for x in L.plan({"alerts": []}, SHORT, 7000.0, 700.0)}
    assert (s["stop"]["condition_type"], s["stop"]["threshold"]) == ("price_above", "702.15")
    assert (s["target"]["condition_type"], s["target"]["threshold"]) == ("price_below", "696.00")
    g = {x["role"]: x for x in L.plan({"alerts": []}, LONG, 7000.0, 700.0)}
    assert g["stop"]["condition_type"] == "price_below" and g["target"]["condition_type"] == "price_above"
    assert all(x["symbol"] == "SPY" for x in list(s.values()) + list(g.values()))


def test_idempotent_capped_and_pause_on_exit():
    led = {"alerts": []}
    for spec, i in zip(L.plan(led, SHORT, 7000.0, 700.0), "ab"):
        L.record(led, spec, i)
    assert L.plan(led, SHORT, 7000.0, 700.0) == []                       # same signal: no duplicates
    assert L.plan(led, dict(SHORT, type="EXIT"), 7000.0, 700.0) == []    # exits never create alerts
    for n in range(2):                                                    # fill to the cap
        for spec, i in zip(L.plan(led, dict(LONG, signal_time=f"t{n}"), 7000.0, 700.0), "cd"):
            L.record(led, spec, f"{n}{i}")
    assert sum(a["active"] for a in led["alerts"]) == L.MAX_ACTIVE
    assert L.plan(led, dict(LONG, signal_time="t9"), 7000.0, 700.0) == []  # cap reached
    assert L.deactivate(led, "spec9", SHORT["signal_time"]) == ["a", "b"]
    assert L.deactivate(led, "spec9", SHORT["signal_time"]) == []          # already paused
    assert L.plan(led, dict(LONG, signal_time="t9"), 7000.0, 700.0) != []  # freed capacity
