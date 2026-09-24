"""🧠 Model read on the 📰 News tab — the local abliterated model's two-sided
briefing, written in the background and served from Mongo (Ajay 2026-09-24).

Ajay 2026-09-24, verbatim: "Please promote the News tab. You can use the
abliterated model we have via hermes. For this tab".

WHICH MODEL, AND WHY NOT THROUGH A HERMES TURN
──────────────────────────────────────────────
Hermes runs ``huihui_ai/Qwen3.8-abliterated:27b`` through Ollama (see
``ollama_chat/hermes.py``). This module calls THAT model on the same Ollama
endpoint through ``llm.chat(provider="local")``, the app's one local-model
path. It does NOT open a Hermes agent turn: a Hermes turn carries the
``hermes-cli`` + ``web`` toolsets with a LOCAL terminal backend and no
approval mode, and the input here is third-party headline text. An unattended
turn that reads untrusted text with a shell attached is a prompt-injection
path onto his Mac. Same model, no tools.

LOCAL ONLY. No hosted fallback: he named the model. If Ollama is down the tab
says so and serves the last read it has. ``provider`` and ``model`` are
stored on every read so the surface prints who actually wrote it.

THE DIVISION OF LABOUR (desk.report's, and sector_news_tags')
─────────────────────────────────────────────────────────────
The app owns every NUMBER; the model owns only PROSE. ``facts()`` builds the
input from the tab's own served blocks — gauge words, T1/T2 releases, sector
rows vs RSP, headlines. ``clean()`` refuses a read that:
  * is missing either side (half a briefing reads as a recommendation),
  * leans anything but bullish / bearish / mixed,
  * writes a number that is not in the facts it was handed.
Sector and macro names it returns are kept only when they match the facts
EXACTLY; a sector named on both sides is dropped from both.

NOT A SIGNAL. The lean is the model's opinion of the headlines against the
gauge — UNMEASURED, not a forecast. It gates nothing, pushes nothing, sizes
nothing, enters no lane and reorders no table. The market word at the top of
the tab stays the Market Gauge's.

WHEN IT RUNS (Ollama has ONE generation slot)
─────────────────────────────────────────────
Never on the request. A GET serves the newest stored read and, when that read
is older than ``REFRESH_MIN_SEC`` and the facts changed, starts ONE daemon
thread to write the next one (single-flight lock; the api runs one uvicorn
worker). ~145 s per call on this model (measured for the day tags, same
budget), so the first view after a quiet spell shows the previous read with a
"writing a fresh one" line. Nothing runs while nobody opens the tab.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from typing import Optional

log = logging.getLogger("chart_maps.news_model_read")

COLLECTION = "news_model_reads"
PROVIDER = "local"
LEANS = ("bullish", "bearish", "mixed")
# ── COST KNOBS, NOT SIGNAL THRESHOLDS ──────────────────────────────────────
REFRESH_MIN_SEC = 30 * 60        # at most one model call per half hour of viewing
MAX_HEADLINES_TO_MODEL = 8
MIN_HEADLINES = 2                # fewer than this is not "the news"
MIN_SIDE_CHARS = 40              # sector_news_tags._usable's floor for one side
MAX_SECTORS_PER_SIDE = 4
MAX_WATCH = 3
UNMEASURED_NOTE = ("Written by the local model from this tab's own facts — its opinion of the headlines "
                   "against the Market Gauge. UNMEASURED, not a forecast; gates nothing. The market word "
                   "above is the gauge's, not the model's.")

_SYSTEM = (
    "You write a two-sided US stock-market briefing for a swing trader, from FACTS and HEADLINES only.\n"
    "Return ONLY one JSON object, no prose around it:\n"
    '{"lean": "bullish" | "bearish" | "mixed", "bull": string, "bear": string, '
    '"sectors_bullish": [string], "sectors_bearish": [string], "watch": [string]}\n'
    "Rules:\n"
    "- bull: the strongest honest case the market rises over the next few sessions, 2-4 sentences.\n"
    "- bear: the strongest honest case it falls, 2-4 sentences. ALWAYS write both sides.\n"
    "- Refer to headlines by their gist. Write NO number, percentage, price or date that is not "
    "written in FACTS or HEADLINES exactly as given; prefer no numbers at all.\n"
    "- sectors_bullish / sectors_bearish: sector names the news supports on that side, copied EXACTLY "
    "from FACTS.sectors[].sector; a sector goes on one side or neither.\n"
    "- watch: up to 3 releases copied EXACTLY from FACTS.macro[].label.\n"
    "- lean: your one-word read of the headlines weighed against FACTS.market. It is an opinion, "
    "not a forecast.\n"
    "- No advice, no position sizing, no ticker that is not in the input."
)

_LOCK = threading.Lock()
_NUM = re.compile(r"\d+(?:\.\d+)?")


def _r2(v):
    """2-dp floats so a rounded number the model repeats is one it was handed."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return round(f, 2) if f == f and f not in (float("inf"), float("-inf")) else None


# ---------------------------------------------------------------------------
# Facts — built ONLY from the served tab payload. PURE.
# ---------------------------------------------------------------------------
def _card(c) -> Optional[dict]:
    if not isinstance(c, dict):
        return None
    return {"word": c.get("word"), "label": c.get("state_label"), "score": _r2(c.get("score"))}


def facts(payload: Optional[dict]) -> Optional[dict]:
    """The model's whole input, or None when any block is missing.

    A read written off three of the four blocks would be a read of less than
    the tab shows, so it is not written at all."""
    p = payload if isinstance(payload, dict) else {}
    v, m, s, h = (p.get(k) if isinstance(p.get(k), dict) else {} for k in
                  ("verdict", "macro", "sectors", "headlines"))
    if not (v.get("ok") and m.get("ok") and s.get("ok") and h.get("ok")):
        return None
    items = [it for it in (h.get("items") or []) if isinstance(it, dict) and (it.get("title") or "").strip()]
    if len(items) < MIN_HEADLINES:
        return None
    live = (s.get("d1") or {}).get("live") is True
    sectors = []
    for r in s.get("rows") or []:
        if not isinstance(r, dict) or not r.get("sector"):
            continue
        sectors.append({
            "sector": r["sector"],
            "vs_rsp_day_pp": _r2(r.get("rel_1d")), "vs_rsp_5d_pp": _r2(r.get("rel_5d")),
            "vs_rsp_21d_pp": _r2(r.get("rel_21d")),
            "heat": (r.get("heat") or {}).get("tone") if isinstance(r.get("heat"), dict) else None,
            "hot_but_lagging_day": bool(r.get("hot_lagging_1d")),
            "cold_but_leading_day": bool(r.get("cold_leading_1d")),
        })
    if not sectors:
        return None
    return {
        "market": {"daily": _card(v.get("daily")), "weekly": _card(v.get("weekly")),
                   "drivers": [d for d in (v.get("drivers") or []) if isinstance(d, str)][:6]},
        "day_basis": "today" if live else "last close",
        "macro": [{"label": e.get("label"), "tier": e.get("tier"), "when": e.get("when_label")}
                  for e in (m.get("events") or []) if isinstance(e, dict) and e.get("label")],
        "sectors": sectors,
        "headlines": [{"title": it.get("title"), "source": it.get("source")}
                      for it in items[:MAX_HEADLINES_TO_MODEL]],
    }


def facts_hash(f: dict) -> str:
    return hashlib.sha1(json.dumps(f, sort_keys=True, default=str).encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Clean — the model's output, refused or trimmed. PURE.
# ---------------------------------------------------------------------------
def _norm(tok: str) -> str:
    """One spelling per number: 84.0 → 84, 0.430 → 0.43, 09 → 9."""
    whole, _, frac = tok.partition(".")
    frac = frac.rstrip("0")
    whole = whole.lstrip("0") or "0"
    return f"{whole}.{frac}" if frac else whole


def _numbers(text: str) -> list:
    return [_norm(t) for t in _NUM.findall((text or "").replace(",", ""))]


def stray_numbers(text: str, f: dict) -> list:
    """Numbers in `text` that appear nowhere in the facts, in order."""
    allowed = set(_numbers(json.dumps(f, default=str, ensure_ascii=False)))
    return [n for n in _numbers(text) if n not in allowed]


def clean(parsed, f: dict) -> tuple[Optional[dict], Optional[str]]:
    """(read, None) when usable, (None, reason) when refused."""
    if not isinstance(parsed, dict):
        return None, "model returned no JSON object"
    lean = str(parsed.get("lean") or "").strip().lower()
    if lean not in LEANS:
        return None, f"lean {lean or 'missing'!r} is not bullish / bearish / mixed"
    bull = str(parsed.get("bull") or "").strip()
    bear = str(parsed.get("bear") or "").strip()
    if len(bull) < MIN_SIDE_CHARS or len(bear) < MIN_SIDE_CHARS:
        return None, "one side of the briefing is missing — half a briefing reads as a recommendation"
    stray = stray_numbers(bull + " " + bear, f)
    if stray:
        return None, f"model wrote numbers not in its facts ({', '.join(stray[:3])})"
    names = [s["sector"] for s in f.get("sectors") or []]
    labels = [e["label"] for e in f.get("macro") or []]

    def pick(key, allowed, cap):
        raw = parsed.get(key)
        out = []
        for x in raw if isinstance(raw, list) else []:
            if isinstance(x, str) and x.strip() in allowed and x.strip() not in out:
                out.append(x.strip())
        return out[:cap]

    up = pick("sectors_bullish", names, MAX_SECTORS_PER_SIDE)
    dn = pick("sectors_bearish", names, MAX_SECTORS_PER_SIDE)
    both = set(up) & set(dn)
    return {
        "lean": lean, "bull": bull, "bear": bear,
        "sectors_bullish": [x for x in up if x not in both],
        "sectors_bearish": [x for x in dn if x not in both],
        "watch": pick("watch", labels, MAX_WATCH),
    }, None


# ---------------------------------------------------------------------------
# Model + store
# ---------------------------------------------------------------------------
def _budget() -> tuple[int, int]:
    """The day tags' budget, MEASURED on this model (2500 tokens / 300 s)."""
    from rotation import sector_news_tags as SNT
    return SNT.MAX_TOKENS, SNT.MODEL_TIMEOUT_SEC


def _coll():
    try:
        from sepa.prices import _get_mongo
        pc = _get_mongo()
        return None if pc is None else pc.database[COLLECTION]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("model read: mongo unavailable: %s", exc)
        return None


def generate(f: dict, fh: Optional[str] = None, *, now: Optional[float] = None) -> dict:
    """One LOCAL model call → one stored doc (a read, or a refusal with its
    reason). Returns the doc. Never raises."""
    now = time.time() if now is None else now
    doc = {"generated_at_epoch": now,
           "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
           "facts_hash": fh or facts_hash(f), "provider": PROVIDER, "measured": False}
    try:
        import llm
        max_tokens, timeout = _budget()
        resp = llm.chat(json.dumps(f, default=str, ensure_ascii=False), system=_SYSTEM,
                        provider=PROVIDER, json_only=True, max_tokens=max_tokens,
                        temperature=0.3, timeout=timeout)
        doc["model"] = resp.get("model")
        doc["latency_sec"] = resp.get("latency_sec")
        if not resp.get("ok"):
            doc.update(ok=False, reason=f"local model unavailable — {str(resp.get('error'))[:160]}")
        else:
            read, why = clean(resp.get("parsed"), f)
            doc.update(ok=read is not None, reason=why, **(read or {}))
    except Exception as exc:                                   # noqa: BLE001
        doc.update(ok=False, reason=f"model read failed — {str(exc)[:160]}")
    coll = _coll()
    if coll is not None:
        try:
            coll.insert_one(dict(doc))
        except Exception as exc:                               # noqa: BLE001
            log.warning("model read: save failed: %s", exc)
    return doc


def _latest(coll, only_ok: bool) -> Optional[dict]:
    try:
        cur = coll.find({"ok": True} if only_ok else {}).sort("generated_at_epoch", -1).limit(1)
        for d in cur:
            d.pop("_id", None)
            return d
    except Exception as exc:                                   # noqa: BLE001
        log.warning("model read: load failed: %s", exc)
    return None


def _run(f: dict, fh: str) -> None:
    try:
        generate(f, fh)
    finally:
        _LOCK.release()


def should_refresh(last: Optional[dict], fh: str, now: float) -> bool:
    """PURE. No attempt yet → yes. Inside the interval → no. Same facts as a
    read that worked → no (nothing new to say). Otherwise yes."""
    if not last:
        return True
    if now - float(last.get("generated_at_epoch") or 0) < REFRESH_MIN_SEC:
        return False
    return not (last.get("ok") and last.get("facts_hash") == fh)


def served(payload: dict, *, now: Optional[float] = None, start=True) -> dict:
    """The block the tab prints, and — at most — one background refresh."""
    now = time.time() if now is None else now
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "model read store unavailable", "read": None,
                "refreshing": False, "note": UNMEASURED_NOTE}
    read = _latest(coll, only_ok=True)
    last = _latest(coll, only_ok=False)
    f = facts(payload)
    waiting = None
    if f is None:
        waiting = "waiting for all four blocks to load before the model reads them"
    else:
        fh = facts_hash(f)
        if start and should_refresh(last, fh, now) and _LOCK.acquire(blocking=False):
            try:
                threading.Thread(target=_run, args=(f, fh), daemon=True,
                                 name="news-model-read").start()
            except Exception:                                  # noqa: BLE001
                _LOCK.release()
                raise
    out = {"ok": read is not None, "read": read, "refreshing": _LOCK.locked(),
           "age_sec": None if read is None else max(0, int(now - float(read.get("generated_at_epoch") or now))),
           "last_error": (last or {}).get("reason") if last and not last.get("ok") else None,
           "waiting": waiting, "refresh_min_sec": REFRESH_MIN_SEC, "note": UNMEASURED_NOTE}
    if read is None:
        out["reason"] = out["last_error"] or waiting or "no model read written yet"
    return out


if __name__ == "__main__":                                     # pragma: no cover
    import asyncio
    from chart_maps import news_tab
    body = asyncio.run(news_tab.build())
    got = facts(body)
    if got is None:
        print("facts incomplete — a block did not load; not calling the model")
    else:
        d = generate(got)
        print(json.dumps({k: d.get(k) for k in ("ok", "reason", "lean", "model", "latency_sec")}, default=str))
