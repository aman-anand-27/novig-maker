"""Fetch MLB odds from The Odds API (eu = Pinnacle/Matchbook, us_ex = Novig)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_BASE = "https://api.the-odds-api.com/v4"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def _get(url: str, params: dict) -> requests.Response:
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp


def _cache_key(sport: str, params: dict) -> str:
    raw = sport + str(sorted((k, v) for k, v in params.items() if k != "apiKey"))
    return hashlib.md5(raw.encode()).hexdigest()


def _fetch_sport(sport: str, params: dict, cache_dir: Path | None) -> tuple[list[dict], dict]:
    """Fetch one sport's odds; serve from disk cache when ODDS_CACHE_DIR is set."""
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        fp = cache_dir / f"{_cache_key(sport, params)}.json"
        if fp.exists():
            logger.info("[cache] %s", sport)
            return json.loads(fp.read_text()), {}

    resp = _get(f"{_BASE}/sports/{sport}/odds", params)
    data: list[dict] = resp.json()
    if cache_dir:
        fp.write_text(json.dumps(data))
    return data, dict(resp.headers)


def fetch_all_odds(cfg: dict) -> list[dict]:
    """Fetch odds for all configured sports; return merged list of games."""
    api_key = os.environ["ODDS_API_KEY"]
    params = {
        "apiKey": api_key,
        "regions": ",".join(cfg["regions"]),
        "markets": ",".join(cfg["markets"]),
        "oddsFormat": cfg["odds_api"].get("oddsFormat", "decimal"),
    }
    cache_dir_env = os.getenv("ODDS_CACHE_DIR")
    cache_dir = Path(cache_dir_env) if cache_dir_env else None

    all_games: list[dict] = []
    for sport in cfg["sports"]:
        games, headers = _fetch_sport(sport, params, cache_dir)
        remaining = headers.get("x-requests-remaining", "?")
        used = headers.get("x-requests-used", "?")
        print(f"[{sport}] {len(games)} games | credits used={used} remaining={remaining}")
        all_games.extend(games)
    return all_games
