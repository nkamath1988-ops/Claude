from trading_bot.scanner.entry_exit import select_new_candidates


def _row(ticker, close, last, atr=1.0, rsi=45.0, adx=25.0):
    return {"ticker": ticker, "columns": {
        "Close": str(close), "Last": str(last), "Average true range": str(atr),
        "RSI": str(rsi), "Average directional index (14)": str(adx),
    }}


def test_skips_already_open_symbols():
    rows = [_row("AAA", 100, 100), _row("BBB", 50, 50)]
    picked = select_new_candidates(rows, open_symbols={"AAA"}, max_new=5)
    symbols = [c["symbol"] for c in picked]
    assert "AAA" not in symbols
    assert "BBB" in symbols


def test_skips_stale_symbols():
    rows = [_row("FRESH", 100, 100.2), _row("STALE", 100, 105)]  # 0.2% vs 5% drift
    picked = select_new_candidates(rows, open_symbols=set(), max_new=5, stale_drift_pct=0.015)
    symbols = [c["symbol"] for c in picked]
    assert "FRESH" in symbols
    assert "STALE" not in symbols


def test_respects_max_new_cap_and_freshest_first():
    rows = [_row("A", 100, 105), _row("B", 100, 100.5), _row("C", 100, 102)]
    picked = select_new_candidates(rows, open_symbols=set(), max_new=2, stale_drift_pct=0.10)
    assert len(picked) == 2
    assert [c["symbol"] for c in picked] == ["B", "C"]  # 0.5% then 2% drift, A (5%) excluded by cap


def test_candidate_shape_matches_advance_day_expectations():
    rows = [_row("AAA", 100, 100, atr=2.0)]
    picked = select_new_candidates(rows, open_symbols=set(), max_new=5)
    assert picked[0] == {
        "symbol": "AAA", "entry_price": 100.0, "stop_price": 97.0, "target_price": 106.0,
    }


def test_max_new_zero_returns_empty():
    rows = [_row("AAA", 100, 100)]
    assert select_new_candidates(rows, open_symbols=set(), max_new=0) == []
