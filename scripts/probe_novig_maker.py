"""Focused live probe for the Novig Maker (line-setting edge finder).

Answers, from real API responses (never memory):
  (a) which SHARP books return for MLB on the free key, and in which region —
      pinnacle, circa (circasports/circa), bookmaker/betcris, exchanges;
  (b) confirms Novig returns (us_ex) and which markets it covers;
  (c) confirms Pinnacle covers all three main-line markets (h2h/spreads/totals);
  (d) prints a ready-to-paste shortlist of sharp books available to you.

Budget: ~8 credits. h2h across regions (1cr each) + one spreads/totals call.

Usage:  ODDS_API_KEY=... python3 scripts/probe_novig_maker.py
"""

import json
import os
import sys
from collections import defaultdict

import requests

BASE = "https://api.the-odds-api.com/v4"
SPORT = "baseball_mlb"

# Regions to sweep for h2h (1 credit each). us_ex = Novig + other US exchanges,
# us2 = circa, eu = pinnacle, us = retail anchor, uk/au = exchanges.
REGIONS = ["us", "us_ex", "us2", "eu", "uk", "au"]

# Books we care about for fair value (sharp / line-setting) + the exchange.
SHARP_CANDIDATES = [
    "pinnacle", "circasports", "circa", "bookmaker", "bookmakereu", "betcris",
    "betonlineag", "lowvig", "betfair_ex_uk", "betfair_ex_eu", "betfair_ex_au",
    "betfair", "matchbook", "smarkets",
]
EXCHANGE = "novig"


def get(path: str, params: dict) -> tuple[object, dict, int]:
    full = dict(params)
    full["apiKey"] = os.environ["ODDS_API_KEY"]
    r = requests.get(f"{BASE}{path}", params=full, timeout=30)
    try:
        body = r.json()
    except ValueError:
        body = {"_text": r.text[:300]}
    return body, dict(r.headers), r.status_code


def books_markets(games: object) -> dict:
    """{book_key: set(market_keys)} unioned across games."""
    out: dict[str, set] = defaultdict(set)
    if isinstance(games, list):
        for g in games:
            for bm in g.get("bookmakers", []):
                out[bm["key"]].update(m["key"] for m in bm.get("markets", []))
    return out


def main() -> None:
    if "ODDS_API_KEY" not in os.environ:
        sys.exit("Set ODDS_API_KEY in the environment first.")

    region_books: dict[str, dict] = {}
    last_remaining = last_used = "?"

    print(f"=== MLB sharp-book probe ({SPORT}) ===\n")
    for region in REGIONS:
        body, headers, st = get(
            f"/sports/{SPORT}/odds",
            {"regions": region, "markets": "h2h", "oddsFormat": "decimal"},
        )
        last_remaining = headers.get("x-requests-remaining", last_remaining)
        last_used = headers.get("x-requests-used", last_used)
        if st != 200:
            print(f"[{region:6}] status={st}  {json.dumps(body)[:160]}")
            region_books[region] = {}
            continue
        bm = books_markets(body)
        region_books[region] = bm
        n = len(body) if isinstance(body, list) else 0
        print(f"[{region:6}] games={n:3}  books={sorted(bm)}")

    # Which sharp candidates appeared, and where
    print("\n=== Sharp / exchange book availability (MLB h2h) ===")
    found: dict[str, list] = {}
    for cand in SHARP_CANDIDATES + [EXCHANGE]:
        regs = [r for r, bm in region_books.items() if cand in bm]
        if regs:
            found[cand] = regs
            print(f"  {cand:16} -> regions {regs}")
    missing = [c for c in SHARP_CANDIDATES if c not in found]
    print(f"  (not returned: {missing})")

    # Confirm Pinnacle + Novig cover all three main-line markets.
    print("\n=== Main-line market coverage (h2h/spreads/totals) ===")
    pin_regions = found.get("pinnacle", [])
    nov_regions = found.get(EXCHANGE, [])
    probe_regions = sorted(set((pin_regions[:1] if pin_regions else [])
                               + (nov_regions[:1] if nov_regions else [])))
    if probe_regions:
        body, headers, st = get(
            f"/sports/{SPORT}/odds",
            {"regions": ",".join(probe_regions),
             "markets": "h2h,spreads,totals", "oddsFormat": "decimal"},
        )
        last_remaining = headers.get("x-requests-remaining", last_remaining)
        last_used = headers.get("x-requests-used", last_used)
        if st == 200:
            bm = books_markets(body)
            for key in ("pinnacle", EXCHANGE, "circasports", "matchbook"):
                if key in bm:
                    print(f"  {key:16} markets={sorted(bm[key])}")
        else:
            print(f"  spreads/totals probe status={st} {json.dumps(body)[:160]}")
    else:
        print("  Pinnacle and/or Novig not found in any region — cannot confirm.")

    print(f"\nCredits: used={last_used} remaining={last_remaining}")
    print("\nPaste the 'Sharp book availability' block back to Claude.")


if __name__ == "__main__":
    main()
