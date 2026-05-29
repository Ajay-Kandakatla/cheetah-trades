"""Diagnose why the valuation chip isn't rendering for a given symbol.

Walks the same pipeline the /sepa/card-enrichment/{sym} endpoint runs and
prints what's happening at every step so we can pinpoint the failure.

Usage:
    docker compose exec api python -m sepa.diagnose_valuation NVDA
    docker compose exec api python -m sepa.diagnose_valuation DELL AAPL MU

Why this exists (2026-05-28): user reported "valuation chip missing from
cards" after a full frontend redeploy. The same bug fired on 2026-05-27 —
analysis_blob nesting changed and _extract_valuation lost the score. This
script lets you see exactly which step (analysis_for fetch, nesting
lookup, score → signal mapping) is producing the null.
"""
from __future__ import annotations
import asyncio
import json
import sys
from typing import Any


def _pretty(o: Any, indent: int = 2) -> str:
    try:
        return json.dumps(o, indent=indent, default=str)[:2000]
    except Exception:
        return repr(o)[:2000]


async def diagnose(sym: str) -> None:
    print(f"\n{'='*60}\n  DIAGNOSE valuation pipeline for: {sym}\n{'='*60}")

    # ── Step 1: pull the analysis blob ──────────────────────────────────
    print(f"\n[1/4] Calling sepa.stock_analysis.analysis_for({sym!r}, False)…")
    try:
        from sepa.stock_analysis import analysis_for
        analysis = await asyncio.to_thread(analysis_for, sym, False)
    except Exception as exc:
        print(f"  ❌ analysis_for raised: {exc!r}")
        return
    if analysis is None:
        print(f"  ❌ analysis_for returned None — backend has no analysis data for this symbol.")
        return
    print(f"  ✅ analysis_for returned a dict. Top-level keys:")
    for k in sorted((analysis or {}).keys()):
        print(f"     · {k}")

    # ── Step 2: check the nesting that _extract_valuation expects ───────
    print(f"\n[2/4] Looking for .fundamental.valuation …")
    fundamental = (analysis or {}).get("fundamental") or {}
    if not fundamental:
        print(f"  ❌ analysis['fundamental'] is missing/empty.")
        print(f"     This is the bug from 2026-05-27 returning. Where IS valuation?")
        print(f"     Scanning the full blob for any key containing 'valuation'…")
        for path, val in _scan(analysis or {}, "analysis", "valuation"):
            print(f"     → {path}  →  {type(val).__name__}  {_pretty(val, 0)[:120]}")
        return
    print(f"  ✅ fundamental block found. Its keys:")
    for k in sorted(fundamental.keys()):
        print(f"     · {k}")

    val = fundamental.get("valuation") or {}
    if not val:
        print(f"  ❌ fundamental['valuation'] is missing/empty.")
        return
    print(f"  ✅ fundamental.valuation found. Keys: {sorted(val.keys())}")

    # ── Step 3: run the extractor + mapper exactly as production does ───
    print(f"\n[3/4] Running production extractor + signal mapper…")
    try:
        from sepa.card_enrichment import _extract_valuation, _valuation_signal_from_score
        extracted = _extract_valuation(analysis)
        print(f"  Extracted:\n{_pretty(extracted)}")
        score = extracted.get("score")
        signal = _valuation_signal_from_score(score)
        print(f"  Score: {score!r}  →  Signal: {signal!r}")
        if signal is None:
            print(f"  ❌ Signal is None — the chip won't render.")
            print(f"     Cause: score is {score!r}. Either backend didn't populate it,")
            print(f"     or it's outside the buckets (signal needs score in 0–100).")
        else:
            print(f"  ✅ Signal {signal!r} should drive the chip to render in the FE.")
    except Exception as exc:
        print(f"  ❌ Extractor raised: {exc!r}")
        return

    # ── Step 4: simulate the API response shape ─────────────────────────
    print(f"\n[4/4] Simulating /sepa/card-enrichment/{sym} response body…")
    payload = {
        "symbol":     sym.upper(),
        "valuation":  extracted,
        "insider":    {"...": "(elided — not relevant to valuation chip)"},
    }
    print(_pretty(payload))
    print(f"\n  FE check: `data.valuation.signal` is {extracted.get('signal')!r}")
    print(f"  If null, chip won't render (CardEnrichmentChips.tsx line 69).")
    print(f"  If a string, chip should render. Verify network response in DevTools.")


def _scan(obj: Any, path: str, needle: str):
    """Walk a nested dict, yield (path, value) when key contains needle."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            sub = f"{path}.{k}"
            if needle.lower() in str(k).lower():
                yield sub, v
            yield from _scan(v, sub, needle)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:3]):  # only check first 3 entries
            yield from _scan(v, f"{path}[{i}]", needle)


def main():
    syms = sys.argv[1:]
    if not syms:
        print("Usage: python -m sepa.diagnose_valuation NVDA [AAPL DELL ...]")
        sys.exit(1)
    for sym in syms:
        asyncio.run(diagnose(sym.upper()))


if __name__ == "__main__":
    main()
