"""Black-Scholes European option pricing, with no external dependency beyond math.erf.

This exists because real historical option premium data is unusable in this
environment for any period that overlaps real underlying price data (see
trading_bot/options/synthetic_bracket.py's module docstring for the full story).
A model price is not a measured market price: it ignores the bid-ask spread,
assumes European exercise (fine for SPX, an approximation for SPY's American-style
contracts), and is only as good as the volatility fed into it.
"""
import math


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def price(spot: float, strike: float, years_to_expiry: float, rate: float,
          vol: float, option_type: str) -> float:
    """Black-Scholes price. `years_to_expiry` <= 0 returns intrinsic value (expired)."""
    if option_type not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type!r}")

    if years_to_expiry <= 0:
        return max(spot - strike, 0.0) if option_type == "call" else max(strike - spot, 0.0)
    if vol <= 0:
        raise ValueError(f"vol must be positive, got {vol!r}")

    sqrt_t = math.sqrt(years_to_expiry)
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol ** 2) * years_to_expiry) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    discounted_strike = strike * math.exp(-rate * years_to_expiry)

    if option_type == "call":
        return spot * _norm_cdf(d1) - discounted_strike * _norm_cdf(d2)
    return discounted_strike * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
