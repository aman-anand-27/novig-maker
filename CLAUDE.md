# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Line-setting edge finder for **Novig**, the peer-to-peer sports betting exchange.
Because Novig is peer-to-peer you can both *take* existing lines and *post* (set)
your own. This tool fetches odds from The Odds API, computes a blended SHARP fair
value (Pinnacle + Matchbook, both devigged, median), compares it to Novig's
prices, and surfaces two edge types. MLB main lines only (h2h / spreads / totals).
Publishes a static dashboard to GitHub Pages; run on-demand via GitHub Actions
`workflow_dispatch`.

It is a clean spin-off of the cno_odds low-hold scanner — they share no code.

## The two edges

For every side Novig quotes, `fair_prob` = median of each sharp anchor's devigged
probability on that exact line, and `fair_dec = 1 / fair_prob`.

- **TAKE** — `novig_dec > fair_dec`: Novig already pays *longer* than fair, so
  backing it now is +EV. `take_ev_pct = fair_prob × novig_dec − 1`.
- **MAKE** — `novig_dec < fair_dec`: Novig's price is short of fair. Post a new
  best-in-market order just above the **+EV floor** (= fair price) — it beats
  Novig's current best (top-of-book, likely to fill) yet stays +EV.
  `book_gap_pct` = how far fair sits above Novig's current best (shading room).

**The trap:** a back order is +EV *only above* sharp-fair odds. Posting between
Novig's current best and fair beats the book but is −EV. The MAKE recommendation
always pads past fair by `make_post_edge_pct`, so it never points below the floor.

The tool cannot predict whether a posted MAKE order actually fills — it guarantees
the +EV floor and shows the shading room; the fill is the user's judgment call.
`make_max_book_gap_pct` hides MAKEs whose gap is too large to realistically fill.

## Commands

```bash
# Run tests
python3 -m pytest tests/

# End-to-end (~6 credits: eu + us_ex × 3 markets)
ODDS_API_KEY=your_key python3 -m src.novig_maker.main
open docs/index.html

# Local dev without burning credits — cache on first run, replay after
ODDS_API_KEY=your_key ODDS_CACHE_DIR=.novig_cache python3 -m src.novig_maker.main
```

## Pipeline

```
config/novig.yaml
      │
      ▼
fetch.py     → The Odds API (one request, regions eu + us_ex, 3 markets)
      │
      ▼
edges.py     → blended sharp fair value per side; classify TAKE / MAKE; EV math
      │
      ▼
qualify.py   → stamp qualified=True/False + disqualify_reasons[] vs thresholds
      │
      ▼
render.py    → writes docs/data.json and docs/index.html (Jinja2 template)
      │
      ▼
GitHub Pages (gh-pages branch, deployed by peaceiris/actions-gh-pages)
```

Each run is a full stateless snapshot — no persistent state.

## Key design decisions

**Sharp fair value** (`edges.py:_sharp_fair_prob`): for each anchor book that
prices both the side and its opposite at the *same* line, devig the two-way market
and keep the side's fair prob. The blend is the median across anchors (Pinnacle +
Matchbook). Requires `min_anchors` books (default 1).

**Line matching** (`edges.py:_find_opposite`): spreads need an exact handicap flip
(−1.5 ↔ +1.5); totals need same point, opposite Over/Under; mismatched lines are
skipped — they are different bets. 3-way h2h markets are skipped.

**Devig** (`odds.py`): multiplicative by default; Shin's method optional (pushes
more vig onto longshots, falls back to multiplicative on no-overround markets).

## Tuning knobs (`config/novig.yaml`)

- `thresholds.take_min_edge_pct` — min EV to surface a TAKE (default 1.0)
- `thresholds.make_min_edge_pct` — min shading room to surface a MAKE (default 1.5)
- `thresholds.make_max_book_gap_pct` — drop MAKEs whose gap is too big to fill (8.0)
- `make_post_edge_pct` — how far past the +EV floor the suggested post price sits
- `sharp_books.anchors` / `min_anchors` — the fair-value sources
- `devig.method` — `multiplicative` or `shin`

## Book availability (live free-key probe 2026-06-20, `scripts/probe_novig_maker.py`)

- Sharp anchors for MLB: **pinnacle** + **matchbook**, both in `eu`, both cover
  h2h/spreads/totals → one eu fetch serves fair value.
- **Novig** is in `us_ex` (alongside kalshi/polymarket/prophetx).
- **Circa** (`circasports`/`circa`) and betcris/bookmaker do NOT return on the
  free key.
- Budget: `eu` + `us_ex` × 3 markets = 6 credits/run. Free tier = 500/month.

## Deployment

GitHub Actions workflow (`.github/workflows/deploy.yml`) is `workflow_dispatch`
only. Builds `docs/` and deploys it to the orphan `gh-pages` branch. The dashboard
is served at the Pages root: `https://<username>.github.io/<repo>/`.
`ODDS_API_KEY` must be set as a GitHub Actions secret.
