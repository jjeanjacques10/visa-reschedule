from __future__ import annotations

from dateutil import parser as date_parser


def parse_date_maybe_ptbr(value: str):
    """Parse portal dates, treating DD/MM/YYYY as day-first."""
    raw = (value or "").strip()
    if not raw:
        raise ValueError("empty date")
    if "/" in raw:
        return date_parser.parse(raw, dayfirst=True)
    return date_parser.parse(raw)


def date_string_candidates(value: str) -> list[str]:
    """Return a small set of likely date string formats for the portal."""
    raw = (value or "").strip()
    if not raw:
        return []

    candidates: list[str] = [raw]

    # Common variants:
    # - JSON endpoints often return ISO (YYYY-MM-DD)
    # - Datepicker inputs in pt-BR commonly display DD/MM/YYYY
    try:
        if "-" in raw:
            dt = parse_date_maybe_ptbr(raw)
            candidates.append(dt.strftime("%d/%m/%Y"))
        elif "/" in raw:
            dt = parse_date_maybe_ptbr(raw)
            candidates.append(dt.strftime("%Y-%m-%d"))
    except Exception:
        pass

    # De-dupe while preserving order.
    seen: set[str] = set()
    uniq: list[str] = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq
