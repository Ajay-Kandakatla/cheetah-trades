"""2026-11-11 — the 🥇 doc's "🔄 Scan now (2026-11-11)" FE paragraph must say what LukBoard.tsx renders:
the button in the title row (.luk-topline) right after the title, the pass line holding no button.
Pins the doc against the component so the two cannot drift apart again."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/luk/luk_tab_2026_11_01.md"
BOARD = ROOT / "frontend/src/components/LukBoard.tsx"
HEADING = "## 🔄 Scan now (2026-11-11)"


def _scan_now_section() -> str:
    text = DOC.read_text()
    assert text.count(HEADING) == 1, "the heading is pinned byte for byte by contracts.mjs"
    body = text.split(HEADING, 1)[1]
    return body.split("\n## ", 1)[0]


def _fe_paragraph() -> str:
    sec = _scan_now_section()
    m = re.search(r"\*\*FE\.\*\*(.*?)(?:\n\n|\Z)", sec, re.S)
    assert m, "the Scan now section must keep its **FE.** paragraph"
    return " ".join(m.group(1).split())


def _passline_block(src: str) -> str:
    start = src.index('<div className="luk-passline">')
    return src[start:src.index("</div>", start)]


def test_doc_puts_the_button_in_the_title_row():
    fe = _fe_paragraph()
    assert "luk-topline" in fe
    assert "right after the title" in fe
    assert "holds no button" in fe
    assert "the title row wraps" in fe


def test_NEGATIVE_doc_no_longer_puts_the_button_in_the_pass_line():
    fe = _fe_paragraph()
    assert "in the pass line" not in fe
    assert "the pass line wraps, the button" not in fe
    assert not re.search(r"luk-rescan`\)\s+in\s+the\s+pass\s+line", fe)


def test_component_matches_the_doc():
    src = BOARD.read_text()
    top = src.index('<div className="luk-topline" data-testid="luk-topline">')
    title = src.index('data-testid="luk-title"', top)
    rescan_use = src.index("{rescan}", top)
    assert top < title < rescan_use < src.index('<div className="luk-passline">')


def test_NEGATIVE_component_pass_line_holds_no_button():
    src = BOARD.read_text()
    block = _passline_block(src)
    assert "rescan" not in block
    assert "<button" not in block
    assert src.count('data-testid="luk-rescan"') == 1
