"""Tests for the Novig Maker edge logic."""

from src.novig_maker.edges import _find_opposite, _sharp_fair_prob, compute_edges
from src.novig_maker.odds import american_to_decimal, decimal_to_american, devig


CFG = {
    "target_books": {"exchange": "novig"},
    "sharp_books": {"anchors": ["pinnacle", "matchbook"], "min_anchors": 1,
                    "labels": {"pinnacle": "Pinnacle", "matchbook": "Matchbook"}},
    "devig": {"method": "multiplicative"},
    "markets": ["h2h"],
    "make_post_edge_pct": 1.0,
}


def _book(key, outcomes, market="h2h"):
    return {"key": key, "markets": [{"key": market, "outcomes": outcomes}]}


def _game(bookmakers, away="Away", home="Home"):
    return {
        "id": "g1", "sport_title": "MLB", "sport_key": "baseball_mlb",
        "away_team": away, "home_team": home,
        "commence_time": "2099-01-01T00:00:00Z", "bookmakers": bookmakers,
    }


def test_odds_roundtrip():
    assert american_to_decimal("+100") == 2.0
    assert abs(american_to_decimal("-150") - 1.6667) < 1e-3
    assert decimal_to_american(2.0) == "+100"
    assert decimal_to_american(1.6667) == "-150"


def test_devig_removes_overround():
    # -110 / -110 two-way market -> 50/50 fair.
    probs = devig([american_to_decimal("-110"), american_to_decimal("-110")])
    assert abs(probs[0] - 0.5) < 1e-9


def test_find_opposite_spread_flip():
    outcomes = [{"name": "A", "point": -1.5, "price": 2.0},
                {"name": "B", "point": 1.5, "price": 1.9}]
    opp = _find_opposite(outcomes[0], outcomes, "spreads")
    assert opp["name"] == "B" and opp["point"] == 1.5


def test_sharp_fair_blend_is_median():
    # Pinnacle fair(A) from -120/+100 ; Matchbook fair(A) from -110/-110.
    pin = _book("pinnacle", [{"name": "A", "price": american_to_decimal("-120")},
                             {"name": "B", "price": american_to_decimal("+100")}])
    mb = _book("matchbook", [{"name": "A", "price": american_to_decimal("-110")},
                             {"name": "B", "price": american_to_decimal("-110")}])
    bm_by_key = {b["key"]: b for b in (pin, mb)}
    fair, details = _sharp_fair_prob(bm_by_key, ["pinnacle", "matchbook"],
                                     {"name": "A"}, "h2h", "multiplicative")
    assert len(details) == 2
    # Pinnacle A fair ~0.5217, Matchbook A fair 0.5 -> median ~0.5109
    assert 0.50 < fair < 0.523


def test_take_edge_when_novig_longer_than_fair():
    # Sharp fair A = 50% (fair +100). Novig pays A at +110 -> +EV to take.
    pin = _book("pinnacle", [{"name": "A", "price": 2.0}, {"name": "B", "price": 2.0}])
    mb = _book("matchbook", [{"name": "A", "price": 2.0}, {"name": "B", "price": 2.0}])
    nv = _book("novig", [{"name": "A", "price": american_to_decimal("+110")},
                         {"name": "B", "price": american_to_decimal("-110")}])
    rows = compute_edges([_game([pin, mb, nv])], CFG)
    a = next(r for r in rows if r["side"] == "A")
    assert a["kind"] == "TAKE"
    assert abs(a["take_ev_pct"] - 5.0) < 0.01  # 0.5*2.10 - 1 = 5%


def test_make_edge_when_novig_shorter_than_fair():
    # Sharp fair A = 50% (fair +100). Novig only pays A at -110 -> short of fair.
    pin = _book("pinnacle", [{"name": "A", "price": 2.0}, {"name": "B", "price": 2.0}])
    mb = _book("matchbook", [{"name": "A", "price": 2.0}, {"name": "B", "price": 2.0}])
    nv = _book("novig", [{"name": "A", "price": american_to_decimal("-110")},
                         {"name": "B", "price": american_to_decimal("+100")}])
    rows = compute_edges([_game([pin, mb, nv])], CFG)
    a = next(r for r in rows if r["side"] == "A")
    assert a["kind"] == "MAKE"
    assert a["book_gap_pct"] > 0          # fair longer than Novig's best
    assert a["post_floor_american"] == "+100"  # floor = fair
    # Recommended post clears the floor (still +EV).
    assert a["make_ev_pct"] > 0


def test_skipped_when_no_sharp_anchor():
    nv = _book("novig", [{"name": "A", "price": 2.0}, {"name": "B", "price": 2.0}])
    rows = compute_edges([_game([nv])], CFG)
    assert rows == []
