"""Odds conversions and no-vig (fair probability) helpers.

Self-contained (mirrors src/sgp_finder/devig.py) so the module stands alone.
De-vig operates on a FULL two-way market: both outcome prices of one book's
market. Multiplicative is the default; Shin's method falls back to
multiplicative when the market has no overround (e.g. exchange prices).
"""

from __future__ import annotations


def american_to_decimal(american: float | int | str) -> float:
    """'+100' -> 2.0, '-150' -> 1.6667, 300 -> 4.0."""
    if isinstance(american, str):
        american = american.strip().replace("+", "")
        if not american:
            raise ValueError("empty american odds")
        american = float(american)
    a = float(american)
    if a == 0:
        raise ValueError("american odds cannot be 0")
    return 1.0 + a / 100.0 if a > 0 else 1.0 + 100.0 / abs(a)


def decimal_to_american(decimal: float) -> str:
    """Decimal odds -> American odds string (+110, -150)."""
    if decimal >= 2.0:
        return f"+{round((decimal - 1) * 100)}"
    if decimal <= 1.0:
        return "N/A"  # degenerate price (locked/suspended market)
    return str(round(-100.0 / (decimal - 1)))


def implied(decimal: float) -> float:
    """Raw implied probability (vig retained)."""
    return 1.0 / decimal


def devig_multiplicative(prices: list[float]) -> list[float]:
    """Proportional no-vig: p_i = (1/o_i) / Sum(1/o_j) over the full market."""
    raw = [1.0 / o for o in prices]
    total = sum(raw)
    if total <= 0:
        raise ValueError("market has no probability mass")
    return [r / total for r in raw]


def devig_shin(prices: list[float], tol: float = 1e-10, max_iter: int = 200) -> list[float]:
    """Shin's method: models the overround as insider-trading proportion z.

    Pushes more of the vig onto longshots than the multiplicative method.
    Falls back to multiplicative when the market has no overround (exchange prices).
    """
    pi = [1.0 / o for o in prices]
    s = sum(pi)
    if s <= 1.0:
        return devig_multiplicative(prices)

    def probs(z: float) -> list[float]:
        return [
            ((z * z + 4.0 * (1.0 - z) * p * p / s) ** 0.5 - z) / (2.0 * (1.0 - z))
            for p in pi
        ]

    lo, hi = 0.0, 1.0 - 1e-9
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        if sum(probs(mid)) > 1.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    p = probs((lo + hi) / 2.0)
    total = sum(p)
    return [x / total for x in p]


def devig(prices: list[float], method: str = "multiplicative") -> list[float]:
    """Dispatch to the configured de-vig method."""
    if method == "multiplicative":
        return devig_multiplicative(prices)
    if method == "shin":
        return devig_shin(prices)
    raise ValueError(f"unknown devig method: {method}")
