"""⚡ The feed word pinned for every GG5 golden (2026-11-11, T-PINS #3).

`push_break.text` (tab.push_break_block → break_watch.status) ends with live_feed.state_word()'s word, which reads the
env (MASSIVE_WS_ENABLED / a configured key) and the socket — a golden built on one machine differed on another. Every
golden builder that serves a GG5 board builds inside `feed_pinned()`: the word is the "off" state's own served word
(live_feed.FEED_WORDS["off"], read by name, never retyped), so the golden is the same bytes on every machine.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest import mock

import live_feed

FEED_PIN = ("off", live_feed.FEED_WORDS["off"])


def _pinned_state_word(*_a, **_k) -> tuple:
    return FEED_PIN


@contextmanager
def feed_pinned():
    """live_feed.state_word answers FEED_PIN inside the block, whatever the env or the socket says."""
    with mock.patch.object(live_feed, "state_word", _pinned_state_word):
        yield
