"""Turn a saved Robinhood scan result (JSON) into a swing-trade suggestion table:
entry, stop, target, reward:risk, and a staleness flag per symbol.

Like synthetic_options_cli.py, this does NOT run the scan itself -- creating and
running a Robinhood scanner (create_scan / run_scan) requires live MCP tool calls
only an agent session can make. Point this at a JSON dump of a run_scan/create_scan
result (`{"results": [{"ticker": ..., "columns": {...}}, ...]}`).

Example:
    python -m trading_bot.scanner_cli --scan-json data_cache_scanner/swing_scan_20260924.json
"""
import argparse
import dataclasses
import json
from pathlib import Path

import pandas as pd

from .scanner.entry_exit import suggest_entry_exit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-json", required=True)
    parser.add_argument("--atr-stop-mult", type=float, default=1.5)
    parser.add_argument("--atr-target-mult", type=float, default=3.0)
    parser.add_argument("--stale-drift-pct", type=float, default=0.015,
                         help="flag a symbol as stale if |last/close - 1| exceeds this")
    parser.add_argument("--out-csv", default=None)
    args = parser.parse_args()

    with open(args.scan_json) as f:
        data = json.load(f)

    rows = []
    for r in data["results"]:
        s = suggest_entry_exit(r, args.atr_stop_mult, args.atr_target_mult)
        row = dataclasses.asdict(s)
        row["name"] = r["columns"].get("Name", "")
        row["stale"] = abs(row["drift_pct"]) > args.stale_drift_pct
        rows.append(row)

    df = pd.DataFrame(rows)[[
        "symbol", "name", "entry_price", "stop_price", "target_price",
        "stop_pct", "target_pct", "last_price", "drift_pct", "stale", "rsi", "adx", "atr",
    ]].sort_values("drift_pct", key=abs)

    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", lambda x: f"{x:0.2f}")
    print(f"{data.get('scan_title', args.scan_json)}: {len(df)} candidates "
          f"({df['stale'].sum()} flagged stale, signal-vs-live drift > {args.stale_drift_pct:.1%})\n")
    print(df.to_string(index=False))

    out_csv = args.out_csv or str(Path(args.scan_json).with_suffix("")) + "_suggestions.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved to {out_csv}")


if __name__ == "__main__":
    main()
