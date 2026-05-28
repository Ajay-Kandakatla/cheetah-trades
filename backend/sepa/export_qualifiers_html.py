"""Export the latest SEPA scan as a standalone Minervini-style HTML report.

Reads ~/.cheetah/scans/latest.json inside the api container, filters to
Trend Template qualifiers (book p.79 watchlist tier — trend.pass_all AND
liquidity.liquid), and writes a single self-contained HTML file to stdout.

Pipe to a file on the host:

    docker compose exec -T api python -m sepa.export_qualifiers_html > sepa.html
    open sepa.html

The output is intentionally dependency-free — no JS, no external CSS, no
framework. Open it in any browser, print it to PDF if you want a paper
copy at the desk. Sorted by composite score descending.

Columns are the fields Minervini actually screens against in the book:
symbol, name, score + rating, RS rank, trend (X/8), stage, key MAs +
distance, base count, setup, day change, ADR, volume strength.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

LATEST_PATH = Path.home() / ".cheetah" / "scans" / "latest.json"


def _is_qualifier(row: dict) -> bool:
    if "qualifier" in row:
        return bool(row["qualifier"])
    trend = row.get("trend") or {}
    liq = row.get("liquidity") or {}
    return bool(trend.get("pass_all") and liq.get("liquid"))


def _fmt(v, prec=2, default="—"):
    if v is None:
        return default
    if isinstance(v, float):
        return f"{v:.{prec}f}"
    return str(v)


def _rating_class(rating: str) -> str:
    return {
        "STRONG_BUY": "r-strong",
        "BUY":        "r-buy",
        "WATCH":      "r-watch",
        "NEUTRAL":    "r-neutral",
        "AVOID":      "r-avoid",
    }.get(rating, "r-neutral")


def _stage_class(stage: int | None) -> str:
    return {2: "s-2", 3: "s-3", 4: "s-4"}.get(stage, "s-1")


def render(payload: dict) -> str:
    rows = payload.get("all_results") or payload.get("candidates") or []
    quals = [r for r in rows if _is_qualifier(r)]
    quals.sort(key=lambda r: r.get("score") or 0, reverse=True)

    from datetime import datetime, timezone
    gen_ts = payload.get("generated_at") or 0
    gen_dt = datetime.fromtimestamp(gen_ts, tz=timezone.utc).astimezone() if gen_ts else None
    gen_str = gen_dt.strftime("%Y-%m-%d %H:%M %Z") if gen_dt else "unknown"

    mkt = payload.get("market_context") or {}
    mkt_label = mkt.get("label", "—")
    mkt_safe = "safe to long" if mkt.get("safe_to_long") else "NOT safe to long"

    out: list[str] = []
    out.append("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SEPA Qualifiers — Minervini Watchlist</title>
<style>
:root {
  --bg:#0f1115; --panel:#161a22; --line:#2a2f3a; --text:#e6e7eb;
  --mute:#8a8f9c; --gold:#d4a85f; --green:#4ad29a; --red:#e26b6b;
  --amber:#e8b25b; --blue:#7aa9e6;
}
* { box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
       background:var(--bg); color:var(--text); margin:0; padding:32px;
       font-size:14px; line-height:1.4; }
header { display:flex; gap:32px; align-items:baseline; margin-bottom:24px;
         padding-bottom:16px; border-bottom:1px solid var(--line); }
h1 { font-size:20px; margin:0; font-weight:600; letter-spacing:0.02em; }
.eyebrow { color:var(--mute); font-size:11px; text-transform:uppercase;
           letter-spacing:0.08em; margin-bottom:4px; }
.stat { display:inline-block; margin-right:24px; }
.stat__num { font-family:"SF Mono","Menlo",monospace; font-size:18px;
             color:var(--gold); font-weight:600; }
.stat__lbl { color:var(--mute); font-size:11px; }
.mkt--ok { color:var(--green); }
.mkt--warn { color:var(--amber); }
.mkt--bad { color:var(--red); }
table { width:100%; border-collapse:collapse; font-size:13px; }
th { text-align:left; color:var(--mute); font-weight:500;
     border-bottom:1px solid var(--line); padding:8px 10px;
     font-size:11px; text-transform:uppercase; letter-spacing:0.06em; }
td { padding:10px; border-bottom:1px solid var(--line);
     font-family:"SF Mono","Menlo",monospace; }
tr:hover td { background:var(--panel); }
.sym { color:var(--gold); font-weight:600; font-size:14px; }
.name { color:var(--mute); font-size:11px; font-family:inherit; }
.r-strong { color:var(--green); font-weight:600; }
.r-buy    { color:var(--green); }
.r-watch  { color:var(--amber); }
.r-neutral{ color:var(--mute); }
.r-avoid  { color:var(--red); }
.s-2 { color:var(--green); }
.s-3 { color:var(--amber); }
.s-4 { color:var(--red); }
.s-1 { color:var(--mute); }
.trend-pass { color:var(--green); font-weight:600; }
.trend-miss { color:var(--amber); }
.up   { color:var(--green); }
.down { color:var(--red); }
.buyable { background:rgba(74,210,154,0.08); }
.buyable .sym::before { content:"★ "; color:var(--green); }
.footnote { color:var(--mute); font-size:11px; margin-top:24px;
            padding-top:16px; border-top:1px solid var(--line);
            line-height:1.6; }
.kbd { background:var(--panel); border:1px solid var(--line); padding:1px 6px;
       border-radius:3px; font-family:inherit; font-size:11px; }
</style>
</head>
<body>
""")

    n_buyable = sum(1 for r in quals if r.get("is_candidate"))
    mkt_class = "mkt--ok" if mkt.get("safe_to_long") else "mkt--warn"

    out.append(f"""<header>
  <div>
    <div class="eyebrow">Minervini SEPA</div>
    <h1>Qualifier Watchlist · book p.79 Trend Template</h1>
  </div>
  <div class="stat"><div class="stat__num">{len(quals)}</div><div class="stat__lbl">qualifiers</div></div>
  <div class="stat"><div class="stat__num">{n_buyable}</div><div class="stat__lbl">buyable (★)</div></div>
  <div class="stat"><div class="stat__num">{payload.get('analyzed', '—')}</div><div class="stat__lbl">analyzed</div></div>
  <div class="stat"><div class="stat__num">{payload.get('universe_size', '—')}</div><div class="stat__lbl">universe</div></div>
  <div class="stat">
    <div class="stat__num {mkt_class}">{html.escape(str(mkt_label))}</div>
    <div class="stat__lbl">{html.escape(mkt_safe)}</div>
  </div>
  <div class="stat" style="margin-left:auto;">
    <div class="stat__num" style="font-size:12px;">{html.escape(gen_str)}</div>
    <div class="stat__lbl">scan time</div>
  </div>
</header>
""")

    out.append("""<table>
<thead><tr>
  <th>Symbol</th>
  <th>Score</th>
  <th>Rating</th>
  <th>RS</th>
  <th>Trend</th>
  <th>Stage</th>
  <th>Price</th>
  <th>Day %</th>
  <th>52w</th>
  <th>vs 50DMA</th>
  <th>vs 200DMA</th>
  <th>Base#</th>
  <th>Setup</th>
  <th>ADR%</th>
  <th>Vol</th>
</tr></thead>
<tbody>
""")

    for r in quals:
        sym = html.escape(str(r.get("symbol", "")))
        name = html.escape(str(r.get("name") or "")[:30])
        score = _fmt(r.get("score"), 1)
        rating = r.get("rating") or ""
        rating_cls = _rating_class(rating)
        rs = r.get("rs_rank") or "—"
        trend = r.get("trend") or {}
        passed = trend.get("passed", 0)
        trend_cls = "trend-pass" if passed == 8 else "trend-miss"
        stage = r.get("stage") or {}
        stage_n = stage.get("stage")
        stage_lbl = stage.get("label", "—")
        stage_cls = _stage_class(stage_n)
        price = _fmt(r.get("last_close"), 2)
        day_pct = r.get("day_change_pct")
        day_str = (f"{day_pct:+.2f}%" if day_pct is not None else "—")
        day_cls = "up" if (day_pct or 0) >= 0 else "down"
        pct_below_high = trend.get("pct_below_high")
        pct_above_low = trend.get("pct_above_low")
        from52 = (f"-{pct_below_high:.0f}% / +{pct_above_low:.0f}%"
                  if pct_below_high is not None and pct_above_low is not None else "—")

        last_close = r.get("last_close") or 0
        ma50 = trend.get("ma50") or 0
        ma200 = trend.get("ma200") or 0
        vs_ma50  = ((last_close / ma50 - 1) * 100) if ma50 else None
        vs_ma200 = ((last_close / ma200 - 1) * 100) if ma200 else None
        vs50_str  = f"{vs_ma50:+.1f}%"  if vs_ma50 is not None else "—"
        vs200_str = f"{vs_ma200:+.1f}%" if vs_ma200 is not None else "—"

        base = r.get("base_count") or {}
        base_n = base.get("base_count", "—")
        base_late = base.get("is_late_stage")
        base_cls = "r-avoid" if base_late else ("r-buy" if base_n in (1, 2) else "")

        entry = r.get("entry_setup")
        setup_str = entry.get("type") if entry else "—"

        adr = _fmt(r.get("adr_pct"), 1)

        vol = r.get("volume") or {}
        vol_strength = vol.get("accumulation_strength") or "—"
        vol_cls = {
            "strong":        "trend-pass",
            "accumulating":  "up",
            "distributing":  "down",
            "neutral":       "r-neutral",
        }.get(vol_strength, "r-neutral")

        is_buyable = bool(r.get("is_candidate"))
        row_cls = " class=\"buyable\"" if is_buyable else ""

        out.append(f"""<tr{row_cls}>
  <td><span class="sym">{sym}</span><br><span class="name">{name}</span></td>
  <td>{score}</td>
  <td><span class="{rating_cls}">{html.escape(rating)}</span></td>
  <td>{rs}</td>
  <td><span class="{trend_cls}">{passed}/8</span></td>
  <td><span class="{stage_cls}">S{stage_n} {html.escape(stage_lbl)}</span></td>
  <td>{price}</td>
  <td><span class="{day_cls}">{day_str}</span></td>
  <td>{from52}</td>
  <td>{vs50_str}</td>
  <td>{vs200_str}</td>
  <td><span class="{base_cls}">{base_n}</span></td>
  <td>{html.escape(str(setup_str))}</td>
  <td>{adr}</td>
  <td><span class="{vol_cls}">{html.escape(str(vol_strength))}</span></td>
</tr>
""")

    out.append("</tbody></table>")

    out.append(f"""
<div class="footnote">
<b>Reading the table.</b>
Rows highlighted with <span class="sym">★</span> have <span class="r-buy">is_candidate=True</span>
— passed all 8 Trend Template gates AND Stage 2 AND have a VCP or PowerPlay setup AND
not in a late-stage base AND liquid. Other rows are Minervini's <b>qualifier tier</b>
(book p.79) — passed the Trend Template + liquid; deserve fundamentals + chart review
before entry.
<br><br>
<b>Column reference.</b>
<span class="kbd">Trend</span> = how many of the 8 Trend Template gates passed (book p.79).
<span class="kbd">Stage</span> = Weinstein 4-stage classifier (book pp. 65-77; Stage 2 = advancing).
<span class="kbd">52w</span> = % below 52w high / % above 52w low.
<span class="kbd">vs 50DMA / 200DMA</span> = % distance from those moving averages.
<span class="kbd">Base#</span> = which base on the Stage 2 run (book pp. 80-83); 1-2 best, 4+ late.
<span class="kbd">Setup</span> = VCP or POWER_PLAY entry setup if detected.
<span class="kbd">ADR%</span> = Average Daily Range, 20-bar.
<span class="kbd">Vol</span> = accumulation strength (strong / accumulating / neutral / distributing).
<br><br>
<b>Source.</b> Generated from <code>{html.escape(str(LATEST_PATH))}</code> · {len(quals)} qualifiers · scan at {html.escape(gen_str)}.
Pure read of the persisted scan output; no live API calls during render.
</div>
</body>
</html>
""")

    return "".join(out)


def main() -> int:
    if not LATEST_PATH.exists():
        print(f"ERROR: no scan found at {LATEST_PATH}", file=sys.stderr)
        print("Run a scan first: docker compose exec api python -m sepa.cli scan", file=sys.stderr)
        return 2
    try:
        payload = json.loads(LATEST_PATH.read_text())
    except Exception as exc:
        print(f"ERROR: could not parse {LATEST_PATH}: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(render(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
