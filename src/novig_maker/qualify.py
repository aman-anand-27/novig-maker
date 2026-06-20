"""Apply qualification thresholds to TAKE/MAKE edge rows."""


def qualify_rows(rows: list[dict], cfg: dict) -> list[dict]:
    """Set qualified=True/False + disqualify_reasons on each row in-place.

    TAKE qualifies when its EV >= take_min_edge_pct.
    MAKE qualifies when there is >= make_min_edge_pct of room between Novig's
    current best and sharp fair (book_gap_pct), AND that gap is within
    make_max_book_gap_pct (a huge gap means the post would have to beat the book
    by too much to fill).
    """
    t = cfg["thresholds"]
    take_min = t["take_min_edge_pct"]
    make_min = t["make_min_edge_pct"]
    max_gap = t.get("make_max_book_gap_pct")

    for row in rows:
        reasons: list[str] = []

        if row["kind"] == "TAKE":
            if row["take_ev_pct"] < take_min:
                reasons.append(f"take EV {row['take_ev_pct']:.1f}% < {take_min}%")
        else:  # MAKE
            if row["book_gap_pct"] < make_min:
                reasons.append(f"shading room {row['book_gap_pct']:.1f}% < {make_min}%")
            if max_gap is not None and row["book_gap_pct"] > max_gap:
                reasons.append(f"gap {row['book_gap_pct']:.1f}% > {max_gap}% (unlikely fill)")

        row["qualified"] = not reasons
        row["disqualify_reasons"] = reasons

    return rows
