# 📌 Trader names on 🚩 Gajjala's list — 2026-10-27

Module: `backend/chart_maps/gajjala/trader_names.py` (BUILD_SPEC26 §3.3, §4 WP-B, AMENDMENTS A2).
Tests: `backend/tests/test_gajjala_trader_names_2026_10_27.py`.

## The ask, verbatim

Ajay, 2026-10-27 ~08:45 ET, two messages:

1. "Can you track this guy please? and his tickers" + https://stocktwits.com/algo888
2. "Add them to Gajjals, they are pretty good"

His call — a gate change he made himself. The traders board (📌, `traders/`) tracks algo888 on StockTwits; this page
is the Gajjala side: the names an account flagged in `traders/registry.py` (`"gajjala": True` — only algo888) posted
join Gajjala's scan as candidates.

**UNMEASURED.** No study in this app has read his names. The closest class this app measured — promo-account first
tags — read **INVERTED** (−4.78pp median 5-session vs a matched placebo, CI [−7.19, −3.41],
`docs/catalysts/promo_tag_study_2026_09_21.md`). In his own post on 2026-10-27 he wrote "@WC25 That;s how I pump.... LOL";
his bio says "DO NOT FOLLOW ME". Nothing here claims an edge.

## What joins — and what does not

Every pass (the 5-minute cron pass and the on-open pass):

1. His scanner runs first, untouched (`scanner.scan_rows` — byte-identical, pinned; it never says "trader").
2. Then `trader_names.run_step`: his stored posts (`traders.feed.stored(trader=key)`) → the names he posted in the last
   `TRADER_NAMES_FRESH_SESSIONS` (2) market sessions, today included (from 00:00 ET of the previous market day; a
   Saturday post counts for Monday), newest mention first, at most `TRADER_NAMES_MAX` (10) a pass. Index / volatility
   tickers (`traders.feed.MARKET_TICKERS`) never join.
3. Each name is resolved on THIS pass's whole-market snapshot (class shares by `sepa.symbols.for_yahoo`):
   - already on GG's list → that row is **tagged** (`trader`, `trader_text`), never a second row;
   - else it is **added** (`source: "trader"`) when it printed today, has a prior regular close, passes Ajay's
     instrument rule (`scanner.type_verdict` — the same rule) and sits inside GG's price band;
   - else it is **skipped** with its reason (below).
4. Then the split hold-out and the `gajjala_scan` write run on GG's names AND the adds (`scanner.record_scan`), so
   listing, `STAY_LISTED_SESSIONS`, the detectors, K1–K11, the no-risk guard, both push gates and the 🏁 ledger read
   them unchanged.

**Without GG's change and volume floors** (the +25% and the 1M) — that IS the add (HIS CALL #1). OTC never appears (the
snapshot excludes it). One post can keep a name listed up to 4 sessions (2 fresh + STAY_LISTED 2), then 🪦.

**GG's 1M floor stays on every push (A2).** A 📌 add is listed, read, tracked and carded, but:
- an **A+** needs today's volume over GG's floor — K11, unchanged (`detectors.k11_gate`);
- its **🧠 potential push is HELD** while the session volume the pass read (the number K11 reads) is under
  `SCAN_MIN_VOLUME`. The 📈 Track row says, verbatim: `held: 📌 under GG's 1M volume floor — listed and read, not rung`.
  On the pass the volume clears the floor the push rings like any other first sighting (the same unbroken structure —
  potential.py's D3 rule), never a re-ring of a sent push (K3). An unknown volume holds (fail closed).
- a name his scanner lists that he also posted (tagged, not added) passed the floors — never held.

Not done: no 📌 sub-tab (the ask is the same list); no new crontab line; no StockTwits read every pass; reshared inner
messages are never read; the curator (`traders/curate.py`) skips him (`"curate": False`, AMENDMENTS A1) — his names do
not enter the `full` universe.

## The re-read

The cron pass re-reads a flagged **StockTwits** account at most every `TRADER_REFRESH_SEC` (= 3 × PASS_CADENCE_SEC =
900 s; state doc `gajjala_state._id "trader_refresh"` = `{at, ok, stored}`), one page (`TRADER_FETCH_PAGES`), a
`TRADER_FETCH_TIMEOUT_SEC` (5 s) timeout, through `traders.feed.refresh` only. A dark or raising fetch never fails the
pass — the stored posts are used. An x-sourced account is never fetched by the pass. Tests, `--now` replays,
`--dry-run` and the on-open pass never re-read (`run.Deps.trader_fetch` is None there; `main()`'s cron path passes
`trader_names.default_fetch`).

## The funnel words (served, FROZEN)

Strip line (`strip.trader_text`), when n > 0:

> 📌 {n} of {who}'s posted names on this pass's list — your call 2026-10-27; GG's rules decide every read and every A+,
> and no push rings on one until today's volume clears GG's 1M floor

Skip line (`strip.trader_skip_text`): `📌 not on the list: ` + `SYM — reason` joined by `; `. The reasons:

| reason | words |
|---|---|
| not_in_snapshot | not in today's market snapshot (OTC, or no trade yet) |
| not_dated_session | no print dated today yet |
| no_prev_close | no prior regular close on file |
| type_out | not common stock or an ADR (your instrument rule) |
| out_of_band | outside GG's $0.10–$100 band |
| over_cap | past the 10-name cap a pass |

Every row that names a symbol (tiles, 🧠 / 🎯 rows, 📈 track rows, 👀 watch, 🌙 recap, 🏁 rows) carries
`trader_text` = `📌 algo888` when tagged, null otherwise — served to every viewer (HIS CALL #10). The A+ and 🧠 push
bodies carry `📌 algo888`; the titles are unchanged (HIS CALL #4). The A+ claim doc and the 🧠 tracker doc carry
`trader: "algo888"`.

The counts legend's last row (verbatim, generated from `tab.count_legend()`; keep in sync):

| word | text |
|---|---|
| 📌 trader | a name a trader you flagged posted in the last 2 market sessions (today included) — on the list by your call without GG's change and volume floors, inside GG's price band and your instrument rule; GG's rules read it like any other name, and no push rings on one until today's volume clears GG's 1M floor |

ℹ️ Rules — the scanner pick ends with:

> 📌 Trader names (your call — “Add them to Gajjals, they are pretty good”): the names algo888 posted in the last 2
> market sessions (today included), newest first, at most 10 a pass, join this list without GG's change and volume
> floors — inside GG's $0.10–$100 band and your instrument rule, never OTC; the pass re-reads his posts every 15
> minutes. A 📌 tag on every card, row and push; GG's rules decide every read, and no push rings on one until today's
> volume clears GG's 1M floor. The window, the cap and the re-read are Cheetah defaults (yours, not GG's).

## Worked example (pinned in the tests)

Session 2026-10-13, pass 10:41 ET, his post at 08:30 ET naming GPUS, MXCT, NOPE, TQQQ, BIGC, STALE:

| name | snapshot | result |
|---|---|---|
| GPUS | 0.19 vs 0.15 (+26.67%), 40M shares | GG qualifier → **tagged** (one row, `trader` set, no `source`) |
| MXCT | 2.10 vs 2.00 (+5%), 300k shares | **added** (`source "trader"`) |
| NOPE | absent | skipped — not_in_snapshot |
| TQQQ | an ETF | skipped — type_out |
| BIGC | 150.00 | skipped — out_of_band |
| STALE | last print the previous session | skipped — not_dated_session |

Counts: qualifiers 1, trader_added 1, trader_tagged 1, trader_skipped 4; strip "📌 2 of algo888's posted names on this
pass's list — …". MXCT read on bull-flag bars is **never A+** (K11 `k11_volume` ok False, 300,000 < 1,000,000) and its
🧠 potential is held. A posted GG qualifier that reads A+ rings with "📌 algo888" in the body, the title unchanged,
and its claim doc carries `trader: "algo888"`.

## HIS CALL (shipped as stated; none decided here)

1. His names join WITHOUT GG's +25% change and 1M-volume floors; the price band, the instrument rule and OTC-off apply. Keep?
2. The 🚩 Auto-Pilot PAPER lane trades an A+ on a 📌 name like any other A+ (it reads every pushed `GG:` claim). Exclude 📌 names?
3. Let 🧠 ring below GG's floor on a 📌 name? (A2 shipped the hold.)
4. A 📌 in the A+ / 🧠 push TITLE? (Body only today.)
5. Cheetah defaults: fresh = since the previous market session (2), cap 10 a pass, re-read every 15 min.
6. Names join whatever his own Bullish/Bearish label says (the scan is long-only).
7. Put him in the curator too (the `full` universe)? (A1: not today.)
8. Also put algo888 on the 🎪 Promo Circuit roster? Not done.
9. Semantics widened: the traders DISCLAIMER, the feed docstring and the GnT blurb no longer say "gates nothing" without
   the dated exception — wording above.
10. The 📌 tag is served to every viewer (🚫 is owner-only). Owner-only instead?

## Verification recipe

Hermetic tests (purge bytecode first):

```bash
/usr/bin/find backend -name __pycache__ -type d -prune -exec rm -rf {} +
docker run --rm --network none --name cheetah-tmp-pytest-ggtr -v "$PWD":/repo -w /repo/backend -e PYTHONDONTWRITEBYTECODE=1 cheetah-api:latest python -m pytest -q -p no:cacheprovider tests/test_gajjala_trader_names_2026_10_27.py
```

Real payload, pre-deploy, read-only, through the CRON container (it runs the pass), never at :01/:06 past (a pass
start). The container runs origin/main, where `trader_names.py`, `feed.parse_stocktwits` and
`stocktwits_client.fetch_user_stream` do not exist yet, so the probe re-implements the parse / names / resolve steps
on what main already has (`stocktwits_client._get_page` on the user stream URL, `feed._clean` / `cashtags` /
`MARKET_TICKERS`, `scanner.row_type` / `_volume` / `scan_rows`, `prices.extended_print`). It reads the live stream
once, takes ONE `prices.market_snapshot_with_meta(include_otc=False)` and the stored type map, writes nothing and
sends nothing. Its functions equal the repo's on the real fixture and the worked example
(`test_the_doc_probe_equals_the_repo_on_the_fixture_and_the_worked_example`, critic F3 2026-10-27):

```bash
docker exec -i -w /app cheetah-market-app-cron-1 python - <<'EOF'
import html
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from catalysts.medical.reaction import prev_market_day
from chart_maps.gajjala import constants as GC, scanner as SC
from sepa import prices, symbols
from traders import feed
import stocktwits_client as STC

ET = ZoneInfo("America/New_York")
WHO, FRESH, MAX = "algo888", 2, 10
URL = "https://api.stocktwits.com/api/2/streams/user/algo888.json"


def parse(messages, handle):
    out = []
    for m in messages or []:
        if not isinstance(m, dict) or m.get("id") is None:
            continue
        if str((m.get("user") or {}).get("username") or "").lower() != handle.lower():
            continue
        text = feed._clean(html.unescape(m.get("body") or ""))
        if not text:
            continue
        ep = STC.parse_created_at(m.get("created_at"))
        syms = [str(x.get("symbol") or "").upper() for x in m.get("symbols") or [] if isinstance(x, dict) and x.get("symbol")]
        out.append({"id": f"st{m['id']}", "cashtags": [t for t in dict.fromkeys(syms + feed.cashtags(text)) if t],
                    "created_at": datetime.fromtimestamp(ep, timezone.utc).isoformat() if ep is not None else None})
    return out


def names(now, session, posts):
    d = session
    for _ in range(FRESH - 1):
        d = prev_market_day(d)
    lo, hi, best = datetime.combine(d, time.min, tzinfo=ET).astimezone(timezone.utc), now.astimezone(timezone.utc), {}
    for p in posts:
        at = datetime.fromisoformat(p["created_at"]) if p.get("created_at") else None
        if at is None or not (lo <= at <= hi):
            continue
        for s in p.get("cashtags") or []:
            s = str(s).strip().upper().lstrip("$")
            if s and s not in feed.MARKET_TICKERS and (s not in best or at > best[s]):
                best[s] = at
    order = sorted(best, key=lambda s: (-best[s].timestamp(), s))
    return order[:MAX], order[MAX:]


def type_out(k, types):
    if GC.SCAN_INSTRUMENT_TYPES is None:
        return False
    t = SC.row_type(k, types)
    if t == GC.SCAN_UNKNOWN_TYPE:
        return GC.SCAN_UNKNOWN_TYPE_POLICY == "drop"
    return t not in GC.SCAN_INSTRUMENT_TYPES


def resolve(syms, rows, session, types, quals):
    iso, gg, added, tagged, skips = session.isoformat(), {q["symbol"] for q in quals}, [], [], []
    for s in syms:
        k = symbols.for_yahoo(s)
        if k in gg:
            tagged += [] if k in tagged else [k]
            continue
        if k in [a[0] for a in added]:
            continue
        row = rows.get(k)
        ep = prices.extended_print(row) if isinstance(row, dict) else None
        prev = SC._f(row.get("prev_day_close")) if isinstance(row, dict) else None
        if not isinstance(row, dict):
            why = "not_in_snapshot"
        elif not ep or ep["date"] != iso:
            why = "not_dated_session"
        elif not prev or prev <= 0:
            why = "no_prev_close"
        elif type_out(k, types):
            why = "type_out"
        elif not (GC.SCAN_MIN_PRICE <= float(ep["price"]) <= GC.SCAN_MAX_PRICE):
            why = "out_of_band"
        else:
            added.append((k, float(ep["price"]), SC._volume(row, iso, ep["session"])[0]))
            continue
        skips.append((k, why))
    return added, tagged, skips


if __name__ == "__main__":
    from chart_maps.gajjala.store import GajjalaStore
    et = datetime.now(ET)
    r, why, code = STC._get_page(URL, 8.0)
    posts = parse((r.json() or {}).get("messages") if r is not None else [], WHO)
    keep, over = names(et, et.date(), posts)
    rows, meta = prices.market_snapshot_with_meta(include_otc=False)
    doc = GajjalaStore().types_map() or {}
    types = {p[0]: p[1] for p in doc.get("pairs") or [] if isinstance(p, (list, tuple)) and len(p) == 2}
    quals = SC.scan_rows(rows or {}, et, et.date(), types=types)["qualifiers"]
    added, tagged, skips = resolve(keep, rows or {}, et.date(), types, quals)
    print("stream", code, why, "posts", len(posts), "snapshot", (meta or {}).get("http"), (meta or {}).get("n"))
    print("added", added)
    print("tagged", tagged)
    print("skips", skips + [(s, "over_cap") for s in over])
EOF
```

After `./deploy-cheetah-main.sh api frontend cron` (the pass runs in the cron image): `GET /chart-maps/gajjala?sub=potential`
serves `strip.trader_text` / `strip.trader_skip_text` and tiles with `trader_text`; a `gajjala_scan` doc of today has
`last.trader == "algo888"`.
