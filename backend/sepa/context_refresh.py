"""Market context refreshed AS PART OF THE SCANS.

Ajay 2026-09-06: "Can you make VIX, IV and Hot sectors part of the scans
please? For full scans" — after learning that the IV badge read a VIX close
from whatever the 20-hour price cache held, and that the Hot sectors strip
was rebuilt on demand by the first page visit (89 s cold, measured that day).

Three reads, refreshed at the end of every `sepa.cli scan` / `fast-scan`
(and on their own via `python -m sepa.context_refresh`):

  * VIX family price frames (^VIX, ^VIX9D, ^VIX3M, ^VVIX) — force-refetched
    so the IV badge and the gauge's volatility pillar read the session's
    close, not a frame the cache kept from yesterday;
  * the IV read (sepa.iv_read.compute) — persisted to Mongo `scan_context`
    `_id: iv`, so /market/iv answers a cold process from the last scan at
    once (16 s cold compute measured 2026-09-06) and refreshes live behind it;
  * the sector rotation map (rotation.tracker.build) — persisted as
    `_id: rotation`, so /rotation and /rotation/hot open on the last scan's
    build instead of paying the cold build on a page view.

Fenced end to end: a failure in any part is recorded (ok / error / seconds)
in the `summary` doc and never fails the scan; the health audit reads that
summary (observability.health_audit.check_scan_context, WARN only).
Not advice — plumbing for reads that already exist.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Callable, Optional

log = logging.getLogger("sepa.context_refresh")

VIX_FAMILY = ("^VIX", "^VIX9D", "^VIX3M", "^VVIX")
VIX_PERIOD = "2y"                 # one frame serves the gauge (2y) and the IV read (1y tail)
COLL = "scan_context"
IV_ID, ROTATION_ID, SUMMARY_ID = "iv", "rotation", "summary"
PARTS = ("vix", "iv", "rotation")
# A persisted read this fresh replaces a cold on-demand build in the API.
PERSIST_FRESH_SEC = 20 * 3600
# Health: a summary older than this on a weekday means the scans stopped
# refreshing the context (the 16:30 fast-scan is the daily writer).
STALE_AFTER_H = 30.0


def _et_iso() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds")
    except Exception:                                          # pragma: no cover
        return datetime.utcnow().isoformat(timespec="seconds")


def _coll(coll=None):
    if coll is not None:
        return coll
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[os.getenv("MONGO_DB", "cheetah")][COLL]
    except Exception:
        return None


# ── persistence ──────────────────────────────────────────────────────────────
def save_doc(doc_id: str, payload: dict, *, meta: Optional[dict] = None, coll=None) -> bool:
    c = _coll(coll)
    if c is None:
        return False
    try:
        doc = {"_id": doc_id, "payload": payload, "built_at": time.time(),
               "built_at_iso": _et_iso(), **(meta or {})}
        c.update_one({"_id": doc_id}, {"$set": doc}, upsert=True)
        return True
    except Exception as exc:
        log.warning("context_refresh: persist %s failed: %s", doc_id, exc)
        return False


def load_doc(doc_id: str, *, coll=None, max_age_sec: Optional[float] = None) -> Optional[dict]:
    """The stored doc with `age_sec`, or None when missing, unreadable, or
    older than `max_age_sec`."""
    c = _coll(coll)
    if c is None:
        return None
    try:
        doc = c.find_one({"_id": doc_id})
    except Exception as exc:
        log.warning("context_refresh: read %s failed: %s", doc_id, exc)
        return None
    if not doc or not isinstance(doc.get("payload"), dict):
        return None
    age = time.time() - float(doc.get("built_at") or 0)
    if max_age_sec is not None and age > max_age_sec:
        return None
    return dict(doc, age_sec=round(age, 1))


# ── the three parts ──────────────────────────────────────────────────────────
def refresh_vix_frames(load: Optional[Callable] = None) -> dict:
    """Force-refetch every VIX-family frame. {symbol: last bar date | None}."""
    if load is None:
        from sepa import prices
        load = prices.load_prices
    out = {}
    for sym in VIX_FAMILY:
        try:
            df = load(sym, period=VIX_PERIOD, force=True)
            out[sym] = str(df.index[-1])[:10] if df is not None and len(df) else None
        except Exception as exc:
            log.warning("context_refresh: %s refetch failed: %s", sym, exc)
            out[sym] = None
    return out


def refresh_iv(*, coll=None) -> dict:
    from sepa import iv_read
    payload = iv_read.get(force=True)
    saved = save_doc(IV_ID, payload, meta={"vix_as_of": payload.get("as_of")}, coll=coll)
    return {"saved": saved, "vix": payload.get("vix"), "as_of": payload.get("as_of"),
            "term_source": (payload.get("term") or {}).get("source")}


def refresh_rotation(*, coll=None) -> dict:
    from rotation import api as RA, tracker as T
    data = T.build(start=RA.DEFAULT_START)
    saved = save_doc(ROTATION_ID, data, meta={"start": RA.DEFAULT_START}, coll=coll)
    RA.warm_cache(RA.DEFAULT_START, data, source="scan", built_at_iso=_et_iso())
    # Keep the SESSION's ranking (Ajay 2026-09-12: "I am trying to see what
    # changed ... energy has been continous"). Nothing stored a rotation
    # history before this — `scan_context` holds three latest-only documents,
    # so yesterday's ranking died the moment today's scan finished and the
    # strip could never say "no change". Fenced: a history write must never be
    # able to fail the scan refresh that produced the data.
    stored = None
    try:
        from rotation import history as RH
        stored = RH.store(data)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("context_refresh: rotation history not stored: %s", exc)
    hot = data.get("hot") or {}
    return {"saved": saved, "as_of": data.get("as_of"), "history": stored,
            "in": [r.get("group") for r in (hot.get("in") or [])],
            "out": [r.get("group") for r in (hot.get("out") or [])]}


def refresh_all(*, parts=PARTS, coll=None) -> dict:
    """Run every part, each fenced; the summary is persisted for the audit."""
    summary = {"started_at": time.time(), "started_at_iso": _et_iso(), "parts": {}}
    steps = {"vix": lambda: {"frames": refresh_vix_frames()},
             "iv": lambda: refresh_iv(coll=coll),
             "rotation": lambda: refresh_rotation(coll=coll)}
    for name in parts:
        t0 = time.time()
        try:
            r = steps[name]() or {}
            summary["parts"][name] = {"ok": True, "sec": round(time.time() - t0, 1), **r}
        except Exception as exc:                               # noqa: BLE001
            summary["parts"][name] = {"ok": False, "sec": round(time.time() - t0, 1),
                                      "error": f"{type(exc).__name__}: {exc}"[:200]}
            log.warning("context_refresh: %s failed: %s", name, exc)
    summary["finished_at"] = time.time()
    summary["ok"] = all(p.get("ok") for p in summary["parts"].values()) and bool(summary["parts"])
    save_doc(SUMMARY_ID, summary, coll=coll)
    return summary


def after_scan(kind: str) -> Optional[dict]:
    """The scan hook (sepa.cli scan / fast-scan). Never raises."""
    try:
        s = refresh_all()
        parts = s.get("parts") or {}
        log.info("SCAN CONTEXT after %s — %s", kind,
                 " · ".join(f"{k} {'ok' if v.get('ok') else 'FAILED'} {v.get('sec', 0)}s"
                            for k, v in parts.items()))
        return s
    except Exception as exc:                                   # noqa: BLE001
        log.warning("context_refresh: after_scan(%s) failed: %s", kind, exc)
        return None


def status(*, coll=None) -> dict:
    """For the health audit: {built: bool, age_h, ok, failed: [parts], summary}."""
    doc = load_doc(SUMMARY_ID, coll=coll)
    if not doc:
        return {"built": False, "age_h": None, "ok": False, "failed": []}
    parts = (doc.get("payload") or {}).get("parts") or {}
    failed = [k for k, v in parts.items() if not v.get("ok")]
    return {"built": True, "age_h": round(float(doc.get("age_sec") or 0) / 3600.0, 1),
            "ok": not failed and bool(parts), "failed": failed,
            "built_at_iso": doc.get("built_at_iso"), "parts": parts}


if __name__ == "__main__":                                     # pragma: no cover
    import json
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    print(json.dumps(refresh_all(), indent=2, default=str))
