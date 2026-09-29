"""Advance the ICT SPX forward paper-trading state from a window of recent 5-minute bars.
Places NO orders. Prints one `NOTIFY <text>` line per NEW event (signal fired / paper exit)
that has not been reported before; re-running on the same or overlapping data prints none.

The bars come from Robinhood `get_index_historicals` (SPX, interval=5minute). That tool is
only reachable from an agent session, so the scheduled routine fetches the last ~4 days,
and passes the saved tool-result file here (or a glob, newest file wins):

    python -m trading_bot.ict_paper_cli --bars-glob '/root/.claude/projects/*/*/tool-results/mcp-Robinhood-get_index_historicals-*.txt' \\
        --state-file paper_trading_state/ict_spx_5m.json
"""
import argparse
import json
from datetime import datetime, timezone

import pandas as pd

from .paper_trading.ict_engine import (advance, format_event, load_state, new_state, newest_tool_result,
                                        read_bars, save_state, summary)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bars", nargs="*", default=[], help="tool-result JSON or CSV files")
    ap.add_argument("--bars-glob", help="glob; the newest 5-minute get_index_historicals file is used")
    ap.add_argument("--state-file", required=True)
    ap.add_argument("--start", help="ISO UTC start for a NEW state (default: now). Signals before it are ignored.")
    ap.add_argument("--dry-run", action="store_true", help="do not write the state file")
    a = ap.parse_args()

    paths = list(a.bars)
    if a.bars_glob:
        f = newest_tool_result(a.bars_glob)
        if f:
            paths.append(f)
    if not paths:
        raise SystemExit("no bar files given/found")
    bars = read_bars(paths)
    if bars.empty:
        raise SystemExit("DATA PROBLEM: no real (non-interpolated) bars in the input -- the data endpoint "
                         "returns all-interpolated filler when it has no data; nothing was processed")
    last = bars.ts.iat[-1]
    age = (datetime.now(timezone.utc) - last.to_pydatetime()).total_seconds() / 60
    print(f"bars: {len(bars)} real 5m bars, last {last:%Y-%m-%d %H:%MZ} ({age / 60:.1f}h ago)")

    state = load_state(a.state_file)
    if state is None:
        start = a.start or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        state = new_state(start)
        print(f"bootstrapping new paper-trading state, start_ts={start}")
    events = advance(state, bars)
    if not a.dry_run:
        save_state(state, a.state_file)

    for ev in events:
        print("EVENT", json.dumps(ev))
        print("NOTIFY", format_event(ev))
    print("SUMMARY", json.dumps(summary(state)))
    for name, pos in state["open"].items():
        if pos:
            print(f"OPEN[{name}] {pos['side']} entry {pos['entry']} stop {pos['stop']} target {pos['target']}")
    if not events:
        print("no new events")


if __name__ == "__main__":
    main()
