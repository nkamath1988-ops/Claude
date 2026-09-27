import pandas as pd

from trading_bot.strategies.smc_bos_choch import SmcBosChochStrategy
from trading_bot.strategies.smc_structure import find_swing_points, process_structure


def test_find_swing_points_confirms_one_bar_after_the_fractal():
    # swing_length=1 -> a 3-bar window (i-1, i, i+1) decides bar i.
    df = pd.DataFrame({
        "high": [1, 5, 1, 1, 6, 1],
        "low":  [5, 5, 1, 5, 5, 5],
        "close": [3, 3, 3, 3, 3, 3],
    })
    swings = find_swing_points(df, swing_length=1)
    found = {(s["bar_index"], s["confirm_index"], s["kind"]) for s in swings}
    assert (1, 2, "high") in found
    assert (2, 3, "low") in found
    assert (4, 5, "high") in found
    # nothing claims to be knowable before its own confirm_index
    assert all(s["confirm_index"] == s["bar_index"] + 1 for s in swings)


def test_find_swing_points_skips_ties():
    # bars 8 and 9 tie for the window low -> neither registers as *the* swing low.
    df = pd.DataFrame({
        "high": [1, 1, 1],
        "low": [5, 5, 6],
        "close": [3, 3, 3],
    })
    swings = find_swing_points(df, swing_length=1)
    assert swings == []


def _hand_traced_df() -> pd.DataFrame:
    """12-bar series whose swing points, BOS, CHoCH and HL-pullback were traced
    by hand (see the conversation this test was written in) using swing_length=1.
    Encodes one full "bullish BOS -> pullback HL entry -> bearish CHoCH exit" cycle."""
    return pd.DataFrame({
        "high":  [10, 15, 11, 11, 20, 12, 12, 25, 13, 13, 9, 9],
        "low":   [9,  10,  5,  9, 11, 13,  9, 20,  8, 8.5, 6, 9],
        "close": [9.5, 12, 6, 10, 15, 11, 10, 22,  9,   9, 7, 8],
    })


def test_process_structure_matches_hand_trace():
    df = _hand_traced_df()
    structure = process_structure(df, swing_length=1)

    expected_labels = [None, None, "HH", "HL", None, "HH", None, "HL", "HH", "LL", None, "LL"]
    actual_labels = [None if pd.isna(v) else v for v in structure["swing_label"].tolist()]
    assert actual_labels == expected_labels
    assert structure["trend"].tolist() == [
        "unknown", "unknown", "unknown", "unknown", "unknown", "unknown", "unknown",
        "bullish", "bullish", "bullish", "bearish", "bearish",
    ]
    assert structure["bos"].tolist() == [False] * 7 + [True] + [False] * 4
    assert structure["choch"].tolist() == [False] * 10 + [True, False]
    assert structure["hl_confirmed"].tolist() == [False] * 7 + [True] + [False] * 4
    assert structure["strong_low"].iloc[7] == 5.0
    assert structure["strong_high"].iloc[10] == 25.0


def test_bos_choch_strategy_entries_and_exits_match_hand_trace():
    df = _hand_traced_df()
    strategy = SmcBosChochStrategy(swing_length=1)
    signal = strategy.generate_signals(df)
    assert signal.tolist() == [0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0]


def test_no_position_taken_before_any_bos():
    # a bullish-looking run with no prior swing high to break should never
    # produce a signal -- there is nothing to have a BOS *against* yet.
    df = pd.DataFrame({
        "high": [10, 11, 12, 13, 14, 15],
        "low": [9, 10, 11, 12, 13, 14],
        "close": [9.5, 10.5, 11.5, 12.5, 13.5, 14.5],
    })
    strategy = SmcBosChochStrategy(swing_length=1)
    signal = strategy.generate_signals(df)
    assert signal.tolist() == [0] * 6
