"""Desk report API — read-only views over the cron-built daily report."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from auth import current_user_email
from desk import report as desk_report

log = logging.getLogger("desk.api")
router = APIRouter(tags=["desk"])


@router.get("/desk/report")
async def get_report(date: Optional[str] = None,
                     user_email: str = Depends(current_user_email)):
    """Latest desk report, or a specific ET day via ?date=YYYY-MM-DD."""
    coll = desk_report._coll()
    doc = None
    if coll is not None:
        try:
            q = {"date": date} if date else {}
            doc = coll.find_one(q, sort=[("date", -1)])
            if doc:
                doc.pop("_id", None)
        except Exception as exc:
            log.warning("desk api: read failed: %s", exc)
    if not doc:
        return JSONResponse({"ok": False, "report": None,
                             "note": "no desk report yet — the cron writes "
                                     "one at 8:40am ET on weekdays"},
                            status_code=404)
    return {"ok": True, "report": doc}


@router.get("/desk/history")
async def get_history(limit: int = 20,
                      user_email: str = Depends(current_user_email)):
    """Slim run list for the date picker: date, verdict, book size, and
    how the carried-forward grading went."""
    coll = desk_report._coll()
    rows = []
    if coll is not None:
        try:
            for d in coll.find({}, {"_id": 0, "date": 1, "regime.verdict": 1,
                                    "book.symbol": 1, "nothing_qualifies": 1,
                                    "carried_forward.status": 1},
                               sort=[("date", -1)], limit=max(1, min(limit, 60))):
                rows.append({
                    "date": d.get("date"),
                    "verdict": (d.get("regime") or {}).get("verdict"),
                    "book": [b.get("symbol") for b in d.get("book") or []],
                    "nothing_qualifies": d.get("nothing_qualifies"),
                    "carried_statuses": [c.get("status") for c in
                                         d.get("carried_forward") or []],
                })
        except Exception as exc:
            log.warning("desk api: history read failed: %s", exc)
    return {"ok": True, "runs": rows}
