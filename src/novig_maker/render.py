"""Write docs/data.json and docs/index.html from the edge rows."""

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader

_DOCS = Path(__file__).parents[2] / "docs"
_TEMPLATES = Path(__file__).parent / "templates"
_EASTERN = ZoneInfo("America/New_York")


def _utc_to_et(utc_str: str) -> str:
    """UTC ISO-8601 -> e.g. '05/22 7:30 PM EDT'."""
    try:
        dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        et = dt.astimezone(_EASTERN)
        abbr = "EDT" if et.dst() else "EST"
        return et.strftime(f"%m/%d %I:%M %p {abbr}").lstrip("0")
    except Exception:
        return utc_str[:16]


def render(rows: list[dict], cfg: dict) -> None:
    _DOCS.mkdir(parents=True, exist_ok=True)

    now_et = datetime.now(timezone.utc).astimezone(_EASTERN)
    abbr = "EDT" if now_et.dst() else "EST"
    generated_at = now_et.strftime(f"%Y-%m-%d %H:%M {abbr}")

    hide_live = cfg["thresholds"].get("hide_live", True)
    display_rows = [r for r in rows if not (hide_live and r.get("is_live"))]

    take = [r for r in display_rows if r["kind"] == "TAKE" and r["qualified"]]
    make = [r for r in display_rows if r["kind"] == "MAKE" and r["qualified"]]
    other = [r for r in display_rows if not r["qualified"]]

    data = {
        "generated_at": generated_at,
        "thresholds": cfg["thresholds"],
        "sharp_books": cfg["sharp_books"]["anchors"],
        "rows": display_rows,
    }
    (_DOCS / "data.json").write_text(json.dumps(data, indent=2))

    env = Environment(loader=FileSystemLoader(_TEMPLATES), autoescape=True)
    env.filters["to_et"] = _utc_to_et
    html = env.get_template("index.html.j2").render(
        generated_at=generated_at,
        thresholds=cfg["thresholds"],
        sharp_labels=[cfg["sharp_books"]["labels"].get(a, a) for a in cfg["sharp_books"]["anchors"]],
        book_labels=cfg["sharp_books"]["labels"],
        take=take,
        make=make,
        other=other,
    )
    (_DOCS / "index.html").write_text(html)

    print(f"Novig Maker: {len(take)} TAKE, {len(make)} MAKE, {len(other)} below-threshold.")
    print(f"Output: {_DOCS / 'index.html'}")
