"""🥇 Luk's tab — Mongo storage (spec §3.4). A SUBCLASS of GG's store: every logical name the Luk pass uses resolves to
its OWN `luk_*` collection, every other GG name resolves to a refusing stub (Luk never reads or writes a `gajjala_*`
collection), and the lease runs on Luk's own numbers.

Collections (all `luk_*`, written ONLY by the Luk pass; the api reads)
  luk_passes   one doc per pass + "latest" / "latest_cron" pointers                           TTL GC.LEDGER_TTL_DAYS on `at`
  luk_reads    _id "{date}|{SYM}" — the detector reads + the 5-minute tile                      TTL GC.READS_TTL_DAYS
  luk_alerts   the shadow claims (demand_alerts.claim_key docs)                                  kept
  luk_state    "lease" + "bars_through" (LC.LUK_STATE_BARS_THROUGH) + "index_state" (LC.LUK_STATE_INDEX)  —
  luk_ledger   🏁 one doc per A+ row, graded by Luk's trade math                                 kept
  luk_daily    _id "{date}|{SYM}" — the daily facts of a session, computed from a TRUSTED frame  TTL GC.LEDGER_TTL_DAYS
  luk_screens  _id "{date}" — the three screens' block of the session's latest pass              TTL GC.LEDGER_TTL_DAYS

Inherited unchanged from `GajjalaStore`: the split lease (claim / release / owner / state), record_pass / latest_pass /
passes, upsert_read / get_read / reads, alerts_coll / alert_rows / alert_dates, ledger_docs, get_daily / upsert_daily,
get_state / set_state. Every write soft-fails (the GG plumbing). Nothing here is a rule or a number of his.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as GS

from . import constants as LC
from .variant import LUK

log = logging.getLogger("chart_maps.luk.store")

PASSES = "luk_passes"
READS = "luk_reads"
ALERTS = "luk_alerts"
STATE = "luk_state"
LEDGER = "luk_ledger"
DAILY = "luk_daily"
SCREENS = "luk_screens"
SCREENS_KEY = "screens"                       # the `colls` key that injects the screens collection
# logical (GG) name → Luk's physical collection
LOGICAL = {GS.PASSES: PASSES, GS.READS: READS, GS.ALERTS: ALERTS, GS.STATE: STATE, GS.LEDGER: LEDGER,
           GS.DAILY: DAILY}
# every GG logical name Luk never touches (scan, ah-carry, post, halts, potentials, overlay, replay)
REFUSED = tuple(n for n in GS.ALL if n not in LOGICAL)
PHYSICAL = tuple(LOGICAL.values()) + (SCREENS,)
TTL_DAYS = {PASSES: GC.LEDGER_TTL_DAYS, READS: GC.READS_TTL_DAYS, DAILY: GC.LEDGER_TTL_DAYS,
            SCREENS: GC.LEDGER_TTL_DAYS}
_DATE_SYMBOL = (READS, DAILY, LEDGER)
_DAY_SEC = 86400


class _Refusing:
    """A stand-in for a GG collection Luk must never touch: any attribute → RuntimeError."""

    def __init__(self, name: str):
        object.__setattr__(self, "_name", name)

    def __getattr__(self, attr):
        raise RuntimeError(f"🥇 Luk never touches {self._name}")

    def __repr__(self) -> str:
        return f"_Refusing({self._name!r})"


class LukStore(GS.GajjalaStore):
    """GajjalaStore over `luk_*`. `colls` keys are the LOGICAL (GG) names, plus `SCREENS_KEY` for luk_screens; an
    injected handle wins. A name not injected resolves lazily to Mongo through `physical()`."""

    def __init__(self, colls: Optional[dict] = None):
        given = dict(colls or {})
        screens = given.pop(SCREENS_KEY, None)
        injected = {n: _Refusing(n) for n in REFUSED}
        injected.update({k: v for k, v in given.items() if k not in REFUSED})
        super().__init__(colls=injected, variant=LUK, shared=None)
        self._screens = screens
        self._screens_given = SCREENS_KEY in (colls or {})

    def physical(self, name: str) -> str:
        return LOGICAL.get(name, name)

    def coll(self, name: str):
        """The handle of a logical name; a REFUSED name raises (never a silent `gajjala_*` read)."""
        if name in REFUSED:
            raise RuntimeError(f"🥇 Luk never touches {name}")
        return super().coll(name)

    @property
    def screens(self):
        if not self._screens_given and self._screens is None:
            self._screens = GS._coll(SCREENS)
        return self._screens

    def _lease_nums(self) -> tuple:
        """(lease_sec, gap_sec) — Luk's own (LC.LUK_LEASE_SEC, LC.LUK_LEASE_MIN_GAP_SEC), read at call time. Load-bearing:
        the GG base returns the 1-minute page's numbers for any non-GG5 variant."""
        return LC.LUK_LEASE_SEC, LC.LUK_LEASE_MIN_GAP_SEC

    # ── indexes ────────────────────────────────────────────────────────────────────────────────────────────────
    def ensure_indexes(self) -> None:
        """Idempotent: TTL on `at` where TTL_DAYS keeps a retention, (date, symbol) keys on reads / daily / ledger,
        `claimed_at` on alerts, `date` on screens. Only the `luk_*` collections — never a refused name."""
        handles = [(LOGICAL[n], self.coll(n)) for n in LOGICAL] + [(SCREENS, self.screens)]
        for phys, c in handles:
            if c is None:
                continue
            try:
                days = TTL_DAYS.get(phys)
                if days:
                    c.create_index([("at", 1)], expireAfterSeconds=int(days * _DAY_SEC))
                if phys in _DATE_SYMBOL:
                    c.create_index([("date", 1), ("symbol", 1)])
                    c.create_index([("symbol", 1), ("date", -1)])
                if phys == ALERTS:
                    c.create_index([("claimed_at", -1)])
                if phys == SCREENS:
                    c.create_index([("date", 1)])
            except Exception as exc:                            # noqa: BLE001
                log.warning("luk.store: index build failed on %s: %s", phys, exc)

    # ── luk_screens ────────────────────────────────────────────────────────────────────────────────────────────
    def upsert_screens(self, session, now: datetime, block: dict) -> None:
        """One doc per session `_id "{date}"` — the latest pass's screens block (replaced each pass)."""
        c = self.screens
        if c is None:
            return
        _id = GS._iso(session)
        try:
            c.replace_one({"_id": _id}, dict(block or {}, _id=_id, date=_id, at=GS._utc(now)), upsert=True)
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk.store: screens write failed: %s", exc)

    def latest_screens(self, session) -> Optional[dict]:
        c = self.screens
        if c is None:
            return None
        try:
            return c.find_one({"_id": GS._iso(session)})
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk.store: screens read failed: %s", exc)
            return None

    # ── luk_ledger ─────────────────────────────────────────────────────────────────────────────────────────────
    def ledger_open(self) -> list:
        """Every luk_ledger doc whose walk has no exit yet (`walk.exit` None / absent). [] on a fault."""
        docs = self._find_or_none(GS.LEDGER, {}) or []
        out = []
        for d in docs:
            walk = d.get("walk") if isinstance(d, dict) else None
            if not isinstance(walk, dict) or walk.get("exit") is None:
                out.append(d)
        return out


_DEFAULT: Optional[LukStore] = None


def default() -> LukStore:
    """The real Luk store (one per process)."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = LukStore()
    return _DEFAULT


def dry_store(real: Optional[LukStore] = None) -> LukStore:
    """A LukStore whose every `luk_*` collection reads through and RECORDS writes (gajjala.run._RecordingColl);
    `.writes` lists (physical name, op), `.dry` is True. The refused names stay refused."""
    from chart_maps.gajjala.run import _RecordingColl
    real = real or default()
    writes: list = []
    colls = {n: _RecordingColl(LOGICAL[n], real.coll(n), writes) for n in LOGICAL}
    colls[SCREENS_KEY] = _RecordingColl(SCREENS, real.screens, writes)
    st = LukStore(colls=colls)
    st.writes = writes
    st.dry = True
    return st
