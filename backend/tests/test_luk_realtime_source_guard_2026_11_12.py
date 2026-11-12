"""🥇 Luk realtime cards — source guard (SPEC lukrt §4 WP-B, 2026-11-12).

Ajay 2026-11-12, verbatim: "Luks scan is not realtime I see all dated values can you make it realtime".

The build rides the house 30 s REST card poll (POST /chart-maps/live) and a served next-read time — never a socket, a
stream, the 🛰 hub or GG's live stack (LUK is deliberately not in GG's variant registry; a `stream: true` POST would
answer `on: false` and print a degraded feed word). Guards, each with a planted-string NEGATIVE proving it bites:
  - no `chart_maps/luk/*.py` imports `live_feed`, `live_hub` or `websockets`, or carries `wss://`;
  - `luk/run.py` never imports `chart_maps.live_card` (the pass composes no live words);
  - `LukBoard.tsx` / `LukCard.tsx` / `lib/luk.ts` never contain `WebSocket`, `EventSource`, `useGgLive` or `stream:`;
  - `LukBoard.tsx` calls `useCardLive(` exactly once.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
LUK_DIR = BACKEND / "chart_maps" / "luk"
FE = REPO / "frontend" / "src"
FE_FILES = (FE / "components" / "LukBoard.tsx", FE / "components" / "LukCard.tsx", FE / "lib" / "luk.ts")
LUK_BOARD = FE / "components" / "LukBoard.tsx"

_IMPORT_LINE = re.compile(r"^\s*(?:from\s+\S+\s+import\s+.*|import\s+.*)$", re.M)
_SOCKET_MODULES = re.compile(r"\b(?:live_feed|live_hub|websockets)\b")
_LIVE_CARD = re.compile(r"\blive_card\b")
FE_FORBIDDEN = ("WebSocket", "EventSource", "useGgLive", "stream:")


def socket_offenses(text: str) -> list:
    """Import lines naming live_feed / live_hub / websockets, plus any `wss://`."""
    bad = [ln.strip() for ln in _IMPORT_LINE.findall(text) if _SOCKET_MODULES.search(ln)]
    if "wss://" in text:
        bad.append("wss://")
    return bad


def live_card_imports(text: str) -> list:
    return [ln.strip() for ln in _IMPORT_LINE.findall(text) if _LIVE_CARD.search(ln)]


def fe_offenses(text: str) -> list:
    return [w for w in FE_FORBIDDEN if w in text]


def _luk_py() -> list:
    files = sorted(LUK_DIR.glob("*.py"))
    assert files, "chart_maps/luk/*.py found"
    return files


# ── backend ────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("path", _luk_py(), ids=lambda p: p.name)
def test_no_luk_module_touches_a_socket_or_the_hub(path):
    assert socket_offenses(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("planted", ["from chart_maps import live_hub", "import websockets",
                                     "    from chart_maps.live_feed import client", "URL = 'wss://socket.example'",
                                     "from chart_maps.live_hub import register_interest"])
def test_NEGATIVE_a_planted_socket_import_is_caught(planted):
    assert socket_offenses("x = 1\n" + planted + "\n") != []


def test_NEGATIVE_a_word_in_a_comment_is_not_an_import():
    assert socket_offenses("# the 🛰 live_hub is not used here\nx = 1\n") == []


def test_run_never_imports_live_card():
    assert live_card_imports((LUK_DIR / "run.py").read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("planted", ["from chart_maps import live_card", "from chart_maps.live_card import compose",
                                     "    import chart_maps.live_card as LCARD"])
def test_NEGATIVE_a_planted_live_card_import_in_run_is_caught(planted):
    src = (LUK_DIR / "run.py").read_text(encoding="utf-8")
    assert live_card_imports(src + "\n" + planted + "\n") != []


# ── frontend ───────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("path", FE_FILES, ids=lambda p: p.name)
def test_no_luk_fe_file_streams(path):
    assert fe_offenses(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("planted", ["new WebSocket(url)", "const es = new EventSource('/x')",
                                     "const g = useGgLive(v)", "useCardLive(syms, on, { stream: true })"])
def test_NEGATIVE_a_planted_stream_word_is_caught(planted):
    assert fe_offenses(LUK_BOARD.read_text(encoding="utf-8") + "\n" + planted + "\n") != []


def test_lukboard_calls_usecardlive_exactly_once():
    assert LUK_BOARD.read_text(encoding="utf-8").count("useCardLive(") == 1


def test_NEGATIVE_a_second_usecardlive_call_is_caught():
    src = LUK_BOARD.read_text(encoding="utf-8") + "\nconst again = useCardLive(x, true)\n"
    assert src.count("useCardLive(") != 1
