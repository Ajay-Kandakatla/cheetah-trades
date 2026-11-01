"""🥇 Luk's `Variant` — an INSTANCE of GG's frozen dataclass (chart_maps.gajjala.variant.Variant), never a fourth entry in
GG's registry (BUILD SPEC luk-tab §3.3, 2026-11-01).

What it is for: `chart_maps.gajjala.alerts.claim_key / shadow_key / is_fresh / max_entry_age_sec` and
`chart_maps.gajjala.variant.cadence_sec / stale_after_sec / tape_tf_min / tape_bars_max / frame_minutes` take it as-is
(its numbers are GC's PASS_CADENCE_SEC, STALE_AFTER_SEC and the 🏁 tape numbers, read at call time).

What it is NOT for: `gajjala.variant.served_block / word / words` and `gajjala.ledger._record_from` — they read
`getattr(GC, record_from_const)` / GG's words, and GC has no LUK_* name, so they raise or serve GG's sentences. Never
hand the Luk store or this variant to gajjala.ledger / gajjala.tab; Luk serves its own words
(tests/test_luk_variant.py pins the allowed gajjala.ledger names).

Push mode fails CLOSED: `gajjala.variant.push_mode(LUK)` looks up "LUK_PUSH_MODE" on GC, finds nothing, and says
"shadow" whatever LC.LUK_PUSH_MODE holds; `push_mode()` here reads LC and says "live" only for exactly "live". Every Luk
alert is recorded in shadow, never sent (HIS CALL #19 — going live is a code change and his word).
"""
from __future__ import annotations

from chart_maps.gajjala.variant import Variant
from chart_maps.luk import constants as LC

LUK = Variant("luk", LC.LUK_TAB, LC.LUK_TAB_LABEL, "5m", "60m", (("1m", "1min"), ("5m", "5min"), ("60m", "60min")),
              "PASS_CADENCE_SEC", "luk", "LUK", LC.LUK_KIND, "luk_potential", "LUK_PUSH_MODE", "", "",
              "/chart-maps/luk", "LEDGER_TAPE_TF_MIN", "LEDGER_TAPE_BARS_MAX", "STALE_AFTER_SEC", False, (),
              borrows=(), record_from_const="LUK_RECORD_FROM")


def push_mode() -> str:
    """"live" only when LC.LUK_PUSH_MODE is exactly "live" (read at call time); anything else → "shadow"."""
    return "live" if getattr(LC, "LUK_PUSH_MODE", None) == "live" else "shadow"
