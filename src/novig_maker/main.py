"""Orchestrator: fetch -> sharp fair value + TAKE/MAKE edges -> qualify -> render."""

import logging
from pathlib import Path

import yaml

from .edges import compute_edges
from .fetch import fetch_all_odds
from .qualify import qualify_rows
from .render import render

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    cfg_path = Path(__file__).parents[2] / "config" / "novig.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    games = fetch_all_odds(cfg)
    rows = compute_edges(games, cfg)
    rows = qualify_rows(rows, cfg)
    render(rows, cfg)


if __name__ == "__main__":
    main()
