"""Helper the routine calls around Robinhood alert creation for ICT paper signals.

  plan  --event '<EVENT json>' --spx <SPX level> --spy <SPY price>   -> JSON list of alert specs to create
  record --spec '<one spec json>' --alert-id <id>                     -> log a created alert
  exit  --variant spec9 --signal-time <iso>                           -> JSON list of alert ids to PAUSE
"""
import argparse
import json

from .paper_trading import ict_alerts as L

LEDGER = "paper_trading_state/ict_spx_robinhood_alerts.json"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ledger", default=LEDGER)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("--event", required=True)
    p.add_argument("--spx", type=float, required=True); p.add_argument("--spy", type=float, required=True)
    r = sub.add_parser("record"); r.add_argument("--spec", required=True); r.add_argument("--alert-id", required=True)
    x = sub.add_parser("exit"); x.add_argument("--variant", required=True); x.add_argument("--signal-time", required=True)
    a = ap.parse_args()
    led = L.load(a.ledger)
    if a.cmd == "plan":
        print(json.dumps(L.plan(led, json.loads(a.event), a.spx, a.spy)))
        return
    if a.cmd == "record":
        L.record(led, json.loads(a.spec), a.alert_id)
    else:
        print(json.dumps(L.deactivate(led, a.variant, a.signal_time)))
    L.save(led, a.ledger)


if __name__ == "__main__":
    main()
