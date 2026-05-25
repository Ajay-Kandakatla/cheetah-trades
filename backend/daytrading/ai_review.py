"""AI second-opinion on day-trading setups using local LLM (LM Studio etc).

Configured via LLM_BASE_URL/LLM_MODEL env vars. See backend/llm/__init__.py.
Returns 503 if LLM is not configured.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

log = logging.getLogger("daytrading.ai_review")

_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_SEC = 5 * 60


async def explain_setup(symbol: str) -> dict[str, Any]:
    """Local-LLM review of the current intraday setup for `symbol`."""
    import llm
    from . import data as data_mod
    from .indicators import opening_range, premarket_levels, relative_volume
    from .signals import orb

    if not llm.is_enabled():
        return {"enabled": False,
                "message": "Set LLM_BASE_URL and LLM_MODEL in backend/.env and restart api."}

    today = datetime.utcnow().date()
    df = data_mod.load_intraday(symbol, today, include_premarket=True)
    if df is None or df.empty:
        return {"enabled": True, "symbol": symbol, "review": None,
                "message": "No bars yet today — market may not be open or pre-RTH."}

    # 5-minute cache by (symbol, last-bar-ts)
    last_ts = df.index[-1].isoformat()
    cache_key = f"{symbol}:{last_ts}"
    now = time.time()
    if cache_key in _CACHE:
        ts, val = _CACHE[cache_key]
        if now - ts < _CACHE_TTL_SEC:
            return {**val, "from_cache": True}

    orb_ = opening_range(df, minutes=15)
    pre = premarket_levels(df)
    rel_vol = relative_volume(df)
    signals = orb.detect(df)

    recent = df.tail(30)
    bar_summary = []
    for ts, row in recent.iterrows():
        bar_summary.append(
            f"{ts.strftime('%H:%M')}Z [{row.get('session','')}]: "
            f"O={row['open']:.2f} H={row['high']:.2f} L={row['low']:.2f} "
            f"C={row['close']:.2f} V={int(row['volume']):,}"
        )

    prompt = (
        f"You are a senior day trader reviewing a setup on {symbol}.\n\n"
        f"Today's session context:\n"
        f"  Opening range (first 15min RTH): {orb_}\n"
        f"  Premarket levels: {pre}\n"
        f"  Relative volume vs 10-day avg: {rel_vol}\n"
        f"  Rules-based signals firing: {signals}\n\n"
        f"Last 30 bars:\n" + "\n".join(bar_summary) + "\n\n"
        f"Provide ONLY a JSON object (no markdown, no preamble) with these fields:\n"
        f'  "setup_quality": integer 1-10 (10 = textbook A+ setup)\n'
        f'  "pattern": string identifying the chart pattern (e.g. "bull flag", "failed breakout", "no clean setup")\n'
        f'  "rationale": 2-3 sentences explaining the rating\n'
        f'  "risks": array of 1-3 specific risks for entering NOW\n'
        f'  "veto": boolean — true if you would NOT enter\n'
        f'  "veto_reason": string if veto is true, empty string otherwise\n'
    )

    res = llm.chat(prompt, max_tokens=600, temperature=0.2, json_only=True, timeout=90)
    if not res.get("ok"):
        return {"enabled": True, "symbol": symbol, "error": res.get("error"),
                "latency_sec": res.get("latency_sec")}

    out = {
        "enabled": True,
        "symbol": symbol,
        "as_of": datetime.utcnow().isoformat() + "Z",
        "review": res.get("parsed") or {"raw": res.get("text")},
        "model": res.get("model"),
        "input_tokens": res.get("input_tokens"),
        "output_tokens": res.get("output_tokens"),
        "latency_sec": res.get("latency_sec"),
    }
    _CACHE[cache_key] = (now, out)
    return out
