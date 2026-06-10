"""HTTP surface for the flashcard bank.

Exposes the card catalog so the frontend /learn page can render the
full Minervini Learning module. Pushes deliver one card per fire (via
push_history), this endpoint returns the *whole library* organized by
topic so the user can browse on demand.

Endpoints
---------
GET /flashcards/all
    Full card bank grouped by topic + the hourly-topic map +
    today's pick per topic. ~25KB JSON; client caches in memory
    for the session.

GET /flashcards/topic/{topic}
    Just one topic's cards. Used when the Learn page is deep-linked
    via /learn?topic=entry — avoids transferring all 90 cards just
    to show one tab.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse

from auth import current_user_email

from . import flashcards as _fc

log = logging.getLogger("flashcards.api")
router = APIRouter(tags=["flashcards"])


def _decorate_card(card: dict, topic: str, idx: int) -> dict:
    """Add a stable id + topic tag so the frontend can deep-link and
    de-duplicate. The id is topic + index-in-pool — survives renames
    of the human-readable title; only changes if the bank is
    re-ordered (cosmetic, not functional)."""
    out = dict(card)
    out["topic"] = topic
    out["id"]    = f"{topic}-{idx}"
    return out


@router.get("/flashcards/all")
def all_cards(email: str = Depends(current_user_email)):
    """Return the entire flashcard bank grouped by topic."""
    by_topic = {}
    for topic, pool in _fc.TOPIC_POOLS.items():
        by_topic[topic] = [_decorate_card(c, topic, i) for i, c in enumerate(pool)]
    # Today's pick per topic — lets the Learn page highlight which card
    # would have been pushed at this exact hour if the user is browsing.
    today_per_topic = {}
    for topic in _fc.TOPIC_POOLS.keys():
        pick = _fc.pick_for_topic(topic)
        if pick:
            today_per_topic[topic] = pick.get("title")
    return JSONResponse({
        "by_topic":       by_topic,
        "hourly_topic":   _fc.HOURLY_TOPIC,
        "today_per_topic": today_per_topic,
        "total_count":    sum(len(p) for p in _fc.TOPIC_POOLS.values()),
    })


@router.get("/flashcards/chart-quiz")
def chart_quiz_today(email: str = Depends(current_user_email)):
    """Today's chart-identification quiz — 2 real historical charts from the
    scan universe, cut at the pattern's confirmation bar. Answers + the WHY +
    the actual +21-bar outcome ride in the payload; the page hides them until
    the user answers. Deterministic per ET day."""
    from . import chart_quiz
    return JSONResponse(chart_quiz.get_today())


@router.get("/flashcards/topic/{topic}")
def topic_cards(topic: str, email: str = Depends(current_user_email)):
    """Return one topic's cards, with the same decoration as /all."""
    pool = _fc.TOPIC_POOLS.get(topic)
    if pool is None:
        raise HTTPException(404, f"unknown topic: {topic}")
    return JSONResponse({
        "topic":       topic,
        "cards":       [_decorate_card(c, topic, i) for i, c in enumerate(pool)],
        "today_pick":  _fc.pick_for_topic(topic),
    })
