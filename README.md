# Novig Maker

Line-setting edge finder for [Novig](https://novig.com), the peer-to-peer sports
betting exchange. Compares Novig's prices against a blended **sharp fair value**
(Pinnacle + Matchbook, devigged) and surfaces two kinds of +EV opportunities for
MLB main lines:

- **TAKE** — Novig already pays *longer* than sharp fair → back it now (+EV).
- **MAKE** — Novig's price is short of fair → **post a new best-in-market order**
  just above the +EV floor (= fair price). It beats Novig's current best
  (top-of-book, likely to fill) while staying +EV.

> A back order is +EV **only above** sharp-fair odds. Posting between Novig's
> current best and fair beats the book but is −EV — the tool always recommends a
> price padded past fair so you stay on the right side of that line. It does not
> predict whether a posted order fills; that's your call.

## Quick start

```bash
pip install -r requirements.txt

# Build the dashboard (~6 API credits: regions eu + us_ex × 3 markets)
ODDS_API_KEY=your_key python3 -m src.novig_maker.main
open docs/index.html

# Replay from cache without spending credits
ODDS_API_KEY=your_key ODDS_CACHE_DIR=.novig_cache python3 -m src.novig_maker.main

# Tests
python3 -m pytest tests/
```

## How it works

`fetch → edges → qualify → render`. For every side Novig quotes, fair probability
is the median of each sharp book's devigged price on that exact line; TAKE/MAKE is
decided by whether Novig's price is longer or shorter than fair. Thresholds and
sharp anchors live in [`config/novig.yaml`](config/novig.yaml). See
[`CLAUDE.md`](CLAUDE.md) for the full design.

## Deployment

The `Build Novig Maker Dashboard` GitHub Action (`workflow_dispatch`) builds
`docs/` and publishes it to the `gh-pages` branch. Set `ODDS_API_KEY` as a repo
secret and enable Pages on the `gh-pages` branch.
