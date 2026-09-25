import math

import pytest

from trading_bot.options.black_scholes import price


def test_put_call_parity():
    S, K, T, r, sigma = 100.0, 105.0, 0.25, 0.04, 0.30
    call = price(S, K, T, r, sigma, "call")
    put = price(S, K, T, r, sigma, "put")
    # C - P = S - K*exp(-rT)
    assert (call - put) == pytest.approx(S - K * math.exp(-r * T), abs=1e-9)


def test_expired_call_returns_intrinsic_value():
    assert price(110.0, 100.0, 0.0, 0.04, 0.3, "call") == pytest.approx(10.0)
    assert price(90.0, 100.0, 0.0, 0.04, 0.3, "call") == pytest.approx(0.0)
    assert price(90.0, 100.0, -1.0, 0.04, 0.3, "call") == pytest.approx(0.0)  # past expiry too


def test_expired_put_returns_intrinsic_value():
    assert price(90.0, 100.0, 0.0, 0.04, 0.3, "put") == pytest.approx(10.0)
    assert price(110.0, 100.0, 0.0, 0.04, 0.3, "put") == pytest.approx(0.0)


def test_call_price_increases_with_spot():
    prices = [price(s, 100.0, 0.1, 0.04, 0.3, "call") for s in (90, 100, 110, 120)]
    assert prices == sorted(prices)
    assert len(set(prices)) == len(prices)


def test_call_price_increases_with_volatility():
    prices = [price(100.0, 100.0, 0.1, 0.04, v, "call") for v in (0.1, 0.2, 0.3, 0.5)]
    assert prices == sorted(prices)


def test_deep_itm_call_approaches_intrinsic_minus_discounted_strike():
    # far in the money, tiny time/vol: should be very close to S - K*exp(-rT)
    S, K, T, r, sigma = 200.0, 100.0, 0.01, 0.04, 0.05
    c = price(S, K, T, r, sigma, "call")
    assert c == pytest.approx(S - K * math.exp(-r * T), abs=0.5)


def test_rejects_unknown_option_type():
    with pytest.raises(ValueError):
        price(100.0, 100.0, 0.1, 0.04, 0.3, "straddle")


def test_rejects_nonpositive_vol_when_time_remains():
    with pytest.raises(ValueError):
        price(100.0, 100.0, 0.1, 0.04, 0.0, "call")
