"""📅 Long Term — `GET /chart-maps/long-term` (spec §3.10, WP-RUN, 2026-11-12).

Ajay 2026-11-12, verbatim: "Save this entire list for me. In a New tab - Long Term - …" and "Yeah I wanna find out the
ones that are actually great in fundamentals and growth and sales and no debt but not growing in price action yet.."

PRIMARY OWNER ONLY (critique C10, HIS CALL §7 #11): `ollama_chat.api.is_primary_admin` of the forwarded X-User-Email
(`auth.maybe_current_user`), the `chart_maps/api.py` gajjala pattern. Anyone else — another email, no email, or a
direct call that receives the `Depends` OBJECT — gets exactly `{state: "owner_only", reason, title}` with HTTP 200 and
nothing is read for them: no seed, no Mongo, no cached close.

The owner's GET reads stored docs only (the weekly runs + the forward record) plus ONE request-time cache read: the 🧭
names' closed cached closes (`sources.pankaj_closes`, a single `bulk_cached_frames` find, never a fetch). It never
builds a week (`weekly.run` / `sources.load_all` are not called here). Every failure answers HTTP 200 with a reason.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends

from auth import maybe_current_user

from . import constants as C

log = logging.getLogger("long_term_list.api")
ET = ZoneInfo("America/New_York")

router = APIRouter(tags=["chart-maps"])


def _owner_only() -> dict:
    from . import payload as PL
    return PL.owner_only_payload()


def _is_owner(email) -> bool:
    if not isinstance(email, str) or not email.strip():
        return False
    from ollama_chat.api import is_primary_admin                 # lazy: tests monkeypatch it
    try:
        return bool(is_primary_admin(email))
    except Exception:                                           # noqa: BLE001
        return False


def owner_payload(now: Optional[datetime] = None, *, db=None) -> dict:
    """The owner's payload. Never raises (state "error" + reason)."""
    from . import payload as PL
    from . import seed as SEED
    from . import sources as SRC
    from . import store as ST
    now = now or datetime.now(ET)
    try:
        try:
            seed = SEED.load()
        except SEED.SeedChanged as exc:
            return PL.error_payload(f"The saved list file changed: {exc}")
        except Exception as exc:                                # noqa: BLE001
            return PL.error_payload(f"The saved list file could not be read: {type(exc).__name__}")
        baseline = SEED.load_baseline()
        cs = ST.colls(db)
        runs = ST.runs_desc(cs["runs"]) if cs else []
        fwd = ST.forward_docs(cs["forward"]) if cs else []
        try:
            closes = SRC.pankaj_closes(sorted(SEED.pankaj_entries(seed)), now)
        except Exception as exc:                                # noqa: BLE001
            log.warning("chart-maps/long-term: 🧭 closes unreadable: %s", exc)
            closes = {}
        return PL.build_payload(seed, baseline, runs, fwd, closes, now=now, owner=True)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("chart-maps/long-term: payload failed: %s", exc)
        return PL.error_payload(f"The Long Term list could not be built: {type(exc).__name__}")


@router.get(C.API_PATH)
async def long_term(email: Optional[str] = Depends(maybe_current_user)):
    """📅 Long Term — owner-only, stored docs + the 🧭 request-time close read. UNMEASURED; none of these lists is a
    signal. A direct call (container smoke test) receives the Depends OBJECT and is served as a non-owner."""
    if not _is_owner(email):
        return _owner_only()
    from growth.api import _scrub
    return _scrub(await asyncio.to_thread(owner_payload))
