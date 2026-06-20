"""Core: pair Novig sides vs blended sharp fair value; classify TAKE / MAKE edges.

For every side Novig quotes we compute a sharp fair probability by de-vigging
Pinnacle and Matchbook on that exact line and taking the median (the "blend").
Then:

  fair_dec   = 1 / fair_prob          (zero-vig fair decimal odds for the side)
  novig_dec  = Novig's current best price to BACK that side

  TAKE  novig_dec > fair_dec   -> Novig already pays longer than fair, so backing
                                  it now is +EV. ev = fair_prob*novig_dec - 1.
  MAKE  novig_dec < fair_dec   -> Novig's price is short of fair. You can POST a
                                  new best-in-market order at odds just above
                                  fair_dec (the +EV floor) and still profit; soft
                                  money laying the other side may fill it.

A back order is +EV only when its decimal odds exceed fair_dec — posting BELOW
fair (even if it beats Novig's current book) is the classic trap, so MAKE always
recommends a price padded just past fair.
"""

from datetime import datetime, timezone
from statistics import median
from typing import Optional

from .odds import american_to_decimal, decimal_to_american, devig  # noqa: F401


def _same_side(outcome: dict, ref: dict, market_key: str) -> bool:
    """True if `outcome` is the same side/line as `ref`."""
    if market_key == "h2h":
        return outcome["name"] == ref["name"]
    return outcome["name"] == ref["name"] and abs(
        outcome.get("point", 0.0) - ref.get("point", 0.0)
    ) < 0.01


def _find_opposite(ref: dict, outcomes: list[dict], market_key: str) -> Optional[dict]:
    """Find the outcome on the opposite side from `ref` (for de-vigging a 2-way market).

    Spreads: TeamA -1.5 pairs with TeamB +1.5 (exact flip).
    Totals:  Over 8.5 pairs with Under 8.5 (same point, opposite label).
    """
    if market_key == "h2h":
        return next((o for o in outcomes if o["name"] != ref["name"]), None)
    if market_key == "spreads":
        target = -ref.get("point", 0.0)
        return next(
            (o for o in outcomes
             if o["name"] != ref["name"] and abs(o.get("point", 0.0) - target) < 0.01),
            None,
        )
    if market_key == "totals":
        target_name = "Under" if ref["name"] == "Over" else "Over"
        target_point = ref.get("point", 0.0)
        return next(
            (o for o in outcomes
             if o["name"] == target_name and abs(o.get("point", 0.0) - target_point) < 0.01),
            None,
        )
    return None


def _side_label(outcome: dict, market_key: str) -> str:
    if market_key == "spreads":
        return f"{outcome['name']} {outcome.get('point', 0.0):+.1f}"
    if market_key == "totals":
        return f"{outcome['name']} {outcome.get('point', 0.0)}"
    return outcome["name"]


def _sharp_fair_prob(
    bm_by_key: dict, anchors: list[str], ref_side: dict, market_key: str, method: str
) -> tuple[Optional[float], list[dict]]:
    """Blended sharp fair probability for `ref_side`.

    For each anchor book that prices both `ref_side` and its opposite at the same
    line, de-vig the two-way market and keep the fair prob of ref_side. The blend
    is the median across anchors. Returns (blend_prob_or_None, per_book_details).
    """
    details: list[dict] = []
    for key in anchors:
        bm = bm_by_key.get(key)
        if not bm:
            continue
        mkt = next((m for m in bm.get("markets", []) if m["key"] == market_key), None)
        if not mkt:
            continue
        outcomes = mkt["outcomes"]
        side = next((o for o in outcomes if _same_side(o, ref_side, market_key)), None)
        opp = _find_opposite(ref_side, outcomes, market_key)
        if side is None or opp is None:
            continue
        fair = devig([side["price"], opp["price"]], method)[0]
        details.append({
            "book": key,
            "fair_prob": fair,
            "fair_american": decimal_to_american(1.0 / fair) if fair > 0 else "N/A",
            "raw_american": decimal_to_american(side["price"]),
        })
    if not details:
        return None, []
    return median(d["fair_prob"] for d in details), details


def _is_live(game: dict) -> bool:
    if game.get("in_progress"):
        return True
    try:
        commence = datetime.fromisoformat(game["commence_time"].replace("Z", "+00:00"))
        return commence < datetime.now(timezone.utc)
    except Exception:
        return False


def compute_edges(games: list[dict], cfg: dict) -> list[dict]:
    """Build one row per Novig-quoted side with sharp fair value and TAKE/MAKE edge.

    Each row carries qualified=False / disqualify_reasons=[] for qualify.py to set.
    Sorted by edge_score descending (best opportunity first).
    """
    exchange = cfg["target_books"]["exchange"]
    anchors = cfg["sharp_books"]["anchors"]
    min_anchors = cfg["sharp_books"].get("min_anchors", 1)
    method = cfg.get("devig", {}).get("method", "multiplicative")
    post_edge = cfg.get("make_post_edge_pct", 1.0) / 100.0

    rows: list[dict] = []

    for game in games:
        bm_by_key = {bm["key"]: bm for bm in game.get("bookmakers", [])}
        novig_bm = bm_by_key.get(exchange)
        if not novig_bm:
            continue
        novig_mkts = {m["key"]: m for m in novig_bm.get("markets", [])}
        is_live = _is_live(game)

        for market_key in cfg.get("markets", []):
            novig_mkt = novig_mkts.get(market_key)
            if not novig_mkt:
                continue
            if market_key == "h2h" and len(novig_mkt["outcomes"]) != 2:
                continue  # 3-way markets unsupported

            for nv_out in novig_mkt["outcomes"]:
                fair_prob, fair_details = _sharp_fair_prob(
                    bm_by_key, anchors, nv_out, market_key, method
                )
                if fair_prob is None or len(fair_details) < min_anchors:
                    continue

                novig_dec = nv_out["price"]
                fair_dec = 1.0 / fair_prob

                # Novig's price on the opposite side (counterparty context).
                opp_nv = _find_opposite(nv_out, novig_mkt["outcomes"], market_key)
                opp_american = decimal_to_american(opp_nv["price"]) if opp_nv else None

                take_ev_pct = (fair_prob * novig_dec - 1.0) * 100.0
                # How far sharp fair sits above Novig's current best (>0 = MAKE room).
                book_gap_pct = (fair_dec / novig_dec - 1.0) * 100.0

                # Recommended MAKE post price: fair padded past breakeven.
                post_dec = fair_dec * (1.0 + post_edge)
                make_ev_pct = (fair_prob * post_dec - 1.0) * 100.0

                if take_ev_pct >= 0:
                    kind = "TAKE"
                    edge_score = take_ev_pct
                else:
                    kind = "MAKE"
                    edge_score = book_gap_pct

                rows.append({
                    "game_id": game["id"],
                    "sport": game.get("sport_title", game.get("sport_key", "")),
                    "game": f"{game['away_team']} @ {game['home_team']}",
                    "commence_time": game["commence_time"],
                    "market": market_key,
                    "side": _side_label(nv_out, market_key),
                    "kind": kind,
                    "fair_prob_pct": round(fair_prob * 100.0, 2),
                    "fair_american": decimal_to_american(fair_dec),
                    "fair_details": fair_details,
                    "fair_book_count": len(fair_details),
                    "novig_american": decimal_to_american(novig_dec),
                    "novig_dec": round(novig_dec, 4),
                    "novig_opp_american": opp_american,
                    "take_ev_pct": round(take_ev_pct, 2),
                    "book_gap_pct": round(book_gap_pct, 2),
                    "post_american": decimal_to_american(post_dec),
                    "post_floor_american": decimal_to_american(fair_dec),
                    "make_ev_pct": round(make_ev_pct, 2),
                    "edge_score": round(edge_score, 2),
                    "is_live": is_live,
                    "qualified": False,
                    "disqualify_reasons": [],
                })

    rows.sort(key=lambda r: r["edge_score"], reverse=True)
    return rows
