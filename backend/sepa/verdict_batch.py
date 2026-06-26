"""Batch Cheetah-Verdict lookup — the composite Minervini+Bonde buy verdict for
a list of symbols, for the Auto-Pilot positions table and the Portfolio cards.

The verdict the Analysis tab shows (ENTER/WATCH/AVOID, surfaced as the
PASS/PARTIAL/FAIL buy_verdict) is computed during the scan and cached on each
row. This module slims a row down to just what those tables need and parses the
request — both pure, so they unit-test without a scan or network.

The endpoint (main.py /sepa/verdicts) reads the cached scan first (instant for
universe names) and falls back to a bounded on-demand analyze for held names
that aren't in today's universe.
"""
from __future__ import annotations

from typing import Optional


def parse_symbols(raw: Optional[str], cap: int = 40) -> list[str]:
    """Comma-separated symbols → uppercased, de-duped, capped (preserve order)."""
    seen: set[str] = set()
    out: list[str] = []
    for part in (raw or "").split(","):
        s = part.strip().upper()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
        if len(out) >= cap:
            break
    return out


def slim_verdict(row: Optional[dict]) -> Optional[dict]:
    """Slim a scan row to the verdict + a few display fields. Returns None when
    there's no row or no verdict could be computed (never a fabricated one).

    If the row lacks a precomputed ``buy_verdict`` (e.g. an on-demand analyze
    that skipped the scan's annotate pass), compute it inline so the chip still
    renders — Bonde will read 'pending' when sales weren't enriched, which is
    the honest state, not a guess.
    """
    if not row:
        return None
    bv = row.get("buy_verdict")
    if not bv:
        try:
            from sepa.buyable_verdict import compute
            bv = compute(row)
        except Exception:
            return None
    if not bv:
        return None

    stage = row.get("stage")
    if isinstance(stage, dict):
        stage = stage.get("stage")
    rs = row.get("rs_rank")
    if rs is None:
        rs = row.get("rs")

    return {
        "symbol": row.get("symbol"),
        "status": bv.get("status"),
        "label": bv.get("label"),
        "icon": bv.get("icon"),
        "tone": bv.get("tone"),
        "both_pass": bv.get("both_pass"),
        "buyable_now": bv.get("buyable_now"),
        "sales_pending": bv.get("sales_pending"),
        "minervini": bv.get("minervini"),
        "bonde": bv.get("bonde"),
        "rs": rs,
        "stage": stage,
        "score": row.get("score"),
        "is_etf": bool(row.get("is_etf")),
    }
