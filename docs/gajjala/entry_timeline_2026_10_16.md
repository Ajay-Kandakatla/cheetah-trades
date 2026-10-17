# 🕰️ Gajjala's A+ entries timeline — the Promo Circuit tape per A+ entry (2026-10-16)

Code: `backend/chart_maps/gajjala/tape.py` (NEW — the tape payload and every tape word, `ENTRY_TAPE_WORDS`),
`backend/chart_maps/gajjala/ledger.py` (`today_bars`, `filled_grade`, the "10d" span, `served_block` → `views`),
`backend/chart_maps/gajjala/constants.py` (`LEDGER_SPAN_SESSIONS_LONG`, `LEDGER_TAPE_*`), the route in
`backend/chart_maps/api.py` (`chart_maps_gajjala_entry_tape`), the primitive `frontend/src/components/TapeChart.tsx`
(NEW), `frontend/src/components/PromoTagTape.tsx` (re-implemented on it), `frontend/src/components/GgEntryTape.tsx`
(NEW), `frontend/src/styles/gg_tape.css` (NEW), the 🏁 view toggle + timeline in
`frontend/src/components/GajjalaBoard.tsx` / `frontend/src/lib/gajjala.ts`. Spec: `BUILD_SPEC11.md` + `AMENDMENTS11.md`
F1–F20 / A1–A5 + `DECISIONS11.md` D1–D13 (session scratchpad `gg_charts/`). Contracts: `frontend/scripts/contracts.mjs`
"🕰️ Gajjala entry tape + replay (2026-10-16)". SPECS: the "🕰️ Entries timeline + tape" bullet under "Chart Maps — 🏁
Gajjala's Track record". ✨ `chart-maps-gajjala-entry-timeline-2026-10-16`. Ledger rules: `docs/gajjala/track_record_2026_10_16.md`.

## READ THIS FIRST

1. **UNMEASURED.** This is a picture of what each A+ alert did after it rang, graded by the 🏁 Track record's own math
   (GG's trade math, `ledger.grade`) — **not a study**, no CI, no placebo, no verdict. Nothing on the tape, the timeline
   or this doc quotes an edge, a win rate or an expectancy.
2. **The 2026-10-14 study read NULL.** No setup of the five showed an edge over a risk- and hour-matched placebo
   (`docs/gajjala/study_2026_10_13.md`). The tape does not change that.
3. **The A+ subset is survivor-biased.** An A+ exists only after its entry bar traded through the trigger and closed —
   a row on this timeline has already survived that bar. Do not read the A+ rows as the setups' record.
4. **Every word, number and percent he reads is served by the backend** (`tape.py`, `ledger.py`, `constants.py`); the
   FE types none. The tape's read line is the ledger's own cell texts, never the Promo Circuit verdict words.
5. **The planner's six resolutions (BUILD_SPEC11, each revertible in one place):**
   - **C1 completed days** — the tape reads a completed day through the house loader `daytrading.data.load_intraday`,
     no force: a cached day never fetches, a missing day is fetched once and cached (else every 2026-10-16 tape would be
     empty all weekend — today's session is never cached). Revert = `tape._completed_day` reads `dt_data._mongo_get_day`
     only and serves the `no_bars` note. HIS CALL Q10. (AMENDMENTS11 F8: only the 📈 full tape may fetch; the mini never does.)
   - **C2** `ENTRY_TAPE_WORDS` live in the NEW `chart_maps/gajjala/tape.py`, not ledger.py — still the only place any
     tape word is typed.
   - **C3** `LEDGER_TAPE_SESSIONS` = 3, not 2: an alert at or after the close has its same session on the NEXT market day
     (`ledger.session_bounds`), so its tape = the alert day + the same session + the next. The cap only guards.
   - **C4** ledger.py is edited in both phases, never concurrently (phase 1: `today_bars`, `filled_grade`, the "10d" span,
     `views`; phase 2: the replayed line). Commit 1 = phase-1 paths, commit 2 = phase-2 paths.
   - **C5** `v` (volume) is `null` on bars built from the ledger's 1-minute tuples (today's shared memo keeps o/h/l/c);
     completed-day frames carry it. Nothing draws volume.
   - **C6** `alert_of`'s live rule gains `and not _id.startswith(REPLAY_ID_PREFIX)` (a replayed doc can never read live);
     every shipped live id starts `GG:` — no row moves.

## The ask (Ajay, 2026-10-16 ~22:00 ET, verbatim)

> "We have a Promo Circuit tab in Catalyst tab.
> Can you use the graph component from  that to show what happened to Entries alert of Gajjala with all the 100% criteria satisfier. One you alert it from the alert system you built please"

Reading (DECISIONS11): every A+ ENTRY (all criteria met) the alert system rang — or recorded as shadow before the
18:02 ET flip — gets the Promo Circuit "tape" graph of what the stock did after the alert.

## What he sees

- **The 🏁 Track record gains a view toggle** (served labels, `tape.VIEWS`): "📋 all alerts" | "🕰️ entries timeline".
  The default stays "📋 all alerts" — his ledger as shipped (`VIEW_DEFAULT`, HIS CALL Q7). The choice rides the URL
  (`view=timeline`); the view never rides the GET (no refetch on a toggle). A span click keeps `view`; a sub click drops it.
- **The timeline view** lists ONLY the A+ rows (`views.kinds` = `["aplus"]`): the 🎯 live entries and the shadow
  records (never sent), in the 🏁 served order — days newest first, rows within a day as the panel serves them (HIS CALL
  Q5). The 🧠 potential rows are not in it and get no tape (HIS CALL Q2). The two 🧠 % count lines are hidden in this view
  (HIS CALL Q6); the shadow and 🎯 entries lines stay. No A+ row in the span → the served `TIMELINE_EMPTY_TEXT`: "No A+
  entry in this span — the 🧠 alerts are under 📋 all alerts."
- **Each row carries the Promo pattern**: a "Tape" column (`views.tape_head`) with a lazy mini tape (`GgEntryMiniTape`,
  width 100, drawn when the row scrolls in) and a 📈 button (`views.tape_toggle`, title `views.tape_toggle_title`);
  📈 (or a click on the mini) expands the full tape (`GgEntryTape`, 720 × 110) under the row; a second click folds it.
- **The full tape** = the Promo Circuit's look (5-minute closes, pre / post market shaded, the axis ends, hi / lo) plus
  the lines it lacked:
  - horizontal levels: **trigger** (buy tone) and **stop** (stop tone) when the alert had a plan; **+1R** (target tone)
    when it filled;
  - vertical rules: **the alert ring** (solid) and **the fill minute** (dashed);
  - dots: **the fill** (at the fill price) and **the exit** — at +1R (target tone) on a win, at the stop (stop tone) on a
    loss;
  - under it, **the read line** = the 🏁 cells' own texts: "Same session: …; Through next session: …";
  - the legend: "5-minute closes · shaded = pre / post market · solid line = the alert · dashed = the fill · levels =
    trigger / stop / +1R".
- **A split on file** after the alert (AMENDMENTS11 F9): no levels and no dots are drawn; the note reads "A split is on
  file after this alert — the bars are adjusted, the alert's levels are as printed; the levels are not drawn."
- **The day picker gains "Last 10 sessions"** (`"10d"`, `LEDGER_SPAN_SESSIONS_LONG` 10 — MINE, HIS CALL Q3) so the whole
  past week fits; the default span stays 5d. `LEDGER_ROWS_MAX` widened to 400 (AMENDMENTS11 F6 — transport, the counts
  still cover every row).

## The endpoint — `GET /chart-maps/gajjala/entry-tape?id={id}&lite=0|1`

Handler `chart_maps_gajjala_entry_tape` in `backend/chart_maps/api.py`, right after the scan POST (never inside the
Gajjala GET's slice). Same auth as the Gajjala GET. `id` = a 🏁 A+ row id (`ledger_id` "…|aplus"); `lite=1` = the row's
mini tape. An unknown id, a 🧠 id, junk or an empty id → **404** with `ENTRY_TAPE_WORDS["not_found"]` ("No A+ entry with
that id on the 🏁 Track record."). A raising `entry_tape` → **200** with every payload key and the note
`ENTRY_TAPE_WORDS["fault"]` (AMENDMENTS11 F19) — never a 500.

### The FROZEN payload (BUILD_SPEC11 §3.4; numbers illustrative)

```json
{"id": "2026-10-14|SYM|bull_flag|aplus", "ticker": "SYM", "tf": "5min · pre/post market", "lite": false,
 "bars": [{"t": 1792051500000, "o": 1.0, "h": 1.01, "l": 0.99, "c": 1.0, "v": 12000.0, "s": "premarket"}],
 "n_bars": 336,
 "hlines": [{"key": "trigger", "px": 1.22, "tone": "buy",    "label": "trigger 1.22"},
            {"key": "stop",    "px": 1.16, "tone": "stop",   "label": "stop 1.16"},
            {"key": "target",  "px": 1.28, "tone": "target", "label": "+1R 1.28"}],
 "rules":  [{"key": "alert", "at": "<aware UTC ISO>", "style": "solid",  "tone": "alert", "label": "alert 15:20 ET"},
            {"key": "fill",  "at": "<fill_t>",        "style": "dashed", "tone": "fill",  "label": "fill 15:21"}],
 "dots":   [{"key": "fill", "at": "<fill_t>", "px": 1.22, "tone": "fill",   "label": "fill 1.22 at 15:21"},
            {"key": "exit", "at": "<exit_t>", "px": 1.28, "tone": "target", "label": "+1R 15:22"}],
 "axis": {"bl": "Oct 14 · 4:05a ET", "br": "Oct 15 · 4:00p ET · 1.94", "tl": "lo 0.98", "tr": "hi 4.02"},
 "legend": "5-minute closes · shaded = pre / post market · solid line = the alert · dashed = the fill · levels = trigger / stop / +1R",
 "read": "Same session: WIN · best +18.9% · +1R at 15:22 · close +11.1%; Through next session: WIN · best +214.8% · +1R at 15:22 · close +91.4%",
 "title": "<read>\n📈 click for the full tape", "tone": "up", "note": null,
 "aria": "SYM 5-minute tape around the A+ entry", "as_of": "<aware UTC ISO>"}
```

- Keys = `tape.PAYLOAD_KEYS`; the lite payload = `tape.LITE_KEYS` (bars t / c / s only, every `promo_tape.LITE_STRIDE`-th
  bar + the last, through `promo_tape.lite_payload(…, stride=PROMO.LITE_STRIDE)` — the Promo engine and its constant,
  read at call time; rules = the alert rule only).
- The `target` hline and the `fill` rule / dot only when `ledger.filled_grade` finds a filled column (`target_px`,
  `fill_t`, `fill_px`); the `exit` dot only on a win (at `target_px`) or a loss (at the alert's stop; reason stop or
  stop_fill_minute); no `alert` rule without an alert time; trigger and stop lines only when `plan == "ok"`.
- `read` = the ledger's `_cell` texts only; `axis` = the bars' own lo / hi / ends; `note` null unless one applies:
  `no_bars`, `today_failed`, `lite_today`, `fault`, `split`.
- Bars = 5-minute (`LEDGER_TAPE_TF_MIN`, the house `resample_ohlcv`, left-closed, right-labelled — the 09:35 bar holds
  09:30–09:34) from the alert session's 04:00 ET through the next horizon's end when graded, else through now
  (`tape.bars5` — one engine for the live tape and phase 2's stored bars).

### The cost rules

- **NEVER WRITES a gajjala collection.** Never `force=True`, never a second today memo, never imports `scripts.*`.
- **Completed days**: the house loader `daytrading.data.load_intraday` (no force) — a day in `intraday_cache` never
  fetches; a missing day is fetched once by the 📈 full tape and cached (C1, HIS CALL Q10). A per-(symbol, day) lock
  keeps two rows of one name from double-fetching (AMENDMENTS11 F8).
- **Today**: through the ledger's ONE shared memo (`ledger.today_bars` over `_TODAY_MEMO`, `LEDGER_TODAY_MEMO_SEC`) —
  the minutes the 🏁 today read already loaded are reused, never a second Massive fetch for that name; only closed and
  settled minutes are drawn.
- **The mini never fetches** (AMENDMENTS11 F8): `lite=1` reads completed days from the cache only and today from the
  memo only; a miss → that day absent (`no_bars` note; today's memo miss = the `lite_today` note "Today's bars are not in the mini yet — 📈 loads the full tape.", AMENDMENTS11 A6 — after the 20:15 ET nightly the memo is empty, so the mini says so instead of claiming a failed read). Only the 📈 click may load. The mini itself is
  lazy (drawn when its row scrolls in) and exists only in the timeline view — the default view costs nothing.
- **Memo** `LEDGER_TAPE_MEMO_SEC` (= `PASS_CADENCE_SEC`) per id, the full and the lite payloads under their own keys;
  **cap** `LEDGER_TAPE_BARS_MAX` = `LEDGER_TAPE_SESSIONS` × the 5-minute bars of the 04:00–20:00 ET day (3 × 192 = 576).
- A per-row fault serves the payload with `bars []` and the served note — never a 500.

## The primitive and the byte-identical snapshot

- **One tape engine for both tabs**: `frontend/src/components/TapeChart.tsx` holds the drawing moved VERBATIM from
  `PromoTagTape.tsx` — `etStamp`, `layout`, `miniLayout`, the full chart `TapeChart` and the spark `TapeSpark` — with two
  widenings that are no-ops for the Promo (`layout(…, extraPx)` folds extra prices into lo / hi; a marker carrying a
  finite `px` sits at that price). Every label is passed in; the primitive composes none.
- `PromoTagTape.tsx` re-exports `layout`, `miniLayout`, `etStamp` from './TapeChart' and draws `PromoTagTape` /
  `MiniTape` on the primitive; its read, posts table, legend and fetch paths are unchanged.
- **Byte-identical proof**: the snapshot was cut by the main session on the UNTOUCHED `PromoTagTape.tsx` (main
  `714b7c13`) BEFORE the refactor and is never regenerated after (AMENDMENTS11 F12):
  `frontend/src/components/PromoTagTape.snapshot.test.tsx` renders `<PromoTagTape ticker="C" data={sample} />` and the
  `MiniTape` of the live sample (`__fixtures__/promo_tape_c_2026_10_16.json`, its lite built by the real engine
  `promo_tape_c_lite_2026_10_16.json`) and compares the SVG to `promo_tape_c_svg_2026_10_16.json`; its NEGATIVE (one close
  changed → a different SVG) proves the comparison bites. `PromoTagTape.test.tsx` and `PromoCircuit.test.tsx` pass
  unchanged.
- The four snapshot files' sha256 at the cut:

```
06ff9e2c0ac327a38c6cb18ccc6861c5c5401eb5a7fb1e31c970ca964ae7855a  frontend/src/components/__fixtures__/promo_tape_c_2026_10_16.json
a0b73a9ba48cebe38bc8f827272fc59eb9d1db41eb501bdc0d89edb8d3c8bd90  frontend/src/components/__fixtures__/promo_tape_c_lite_2026_10_16.json
23677d09a6c63904dcff3e46f448b85c409522f57807b5dce53d1f1d7869f334  frontend/src/components/__fixtures__/promo_tape_c_svg_2026_10_16.json
59e186e141d0f21a30cec661532ed42c59471fdc33cf61563f43d5d52c1b41ed  frontend/src/components/PromoTagTape.snapshot.test.tsx
```

```bash
cd /Users/ajay/clinet-test/wt-ggcharts && shasum -a 256 frontend/src/components/__fixtures__/promo_tape_c_2026_10_16.json frontend/src/components/__fixtures__/promo_tape_c_lite_2026_10_16.json frontend/src/components/__fixtures__/promo_tape_c_svg_2026_10_16.json frontend/src/components/PromoTagTape.snapshot.test.tsx
```

- **The Gajjala tape** (`GgEntryTape.tsx`) draws on the same primitive and types no word, number or percent (no
  `toFixed`, `Math.`, `%`, `etStamp(`, `toLocale`, `Intl.`; JSX text is only `…` loading or `—` on an HTTP error) —
  contracts check 2 scans it.

## Verification (BUILD_SPEC11 §5.4 — main session, outside 09:30–16:00 ET)

1. Start the throwaway api with the session launcher `scratchpad/gg_charts/gr_tmp_api.sh` (name `cheetah-tmp-gr-api`,
   port `127.0.0.1:8007:8000`, the worktree backend at `/app`, the study cache read-only at `/cache`, ONE output mount
   `/replay_out`, Massive WS / Finnhub off, the drain and the on-open scan disabled, `_mongo_put_day` a no-op —
   AMENDMENTS11 F18). Health 200.
2. Commit-1 surface, read-only (`_mongo_put_day` disabled inside the probe too, so the throwaway writes no cache):

```bash
docker exec -i -w /app cheetah-tmp-gr-api python - <<'EOF'
from daytrading import data as D
from chart_maps.gajjala import tape as TP, store as ST, ledger as LG
calls = []
real = D._fetch_massive_minute
D._fetch_massive_minute = lambda *a, **k: (calls.append(a), real(*a, **k))[1]
D._mongo_put_day = lambda *a, **k: None
st = ST.default()
for day in ("2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"):
    for d in st.alert_rows([day]) or []:
        r = LG.alert_of(d, "aplus")
        if r:
            p = TP.entry_tape(r["id"], store=st)
            print(r["id"], p["n_bars"], len(p["hlines"]), len(p["dots"]), p["note"])
            print("   ", p["read"])
print("massive minute fetches:", len(calls))
EOF
```

   Check: every 10-13…10-16 A+ row (4 / 4 / 5 / 8) has bars, trigger + stop lines and a read equal to its 🏁 cells;
   fetches = only the days missing from `intraday_cache` (a second run inside 5 min → 0, the memo).
3. The GET and the route:

```bash
curl -s -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8007/chart-maps/gajjala?sub=track_record&span=10d"
curl -s -o /dev/null -w "%{http_code}\n" -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8007/chart-maps/gajjala/entry-tape?id=nope"
```

   Check: `spans` has 10d, `views` equals `tape.views_block()`; `…/chart-maps/gajjala/entry-tape?id=<an aplus id,
   url-encoded>&lite=1` → `LITE_KEYS` only; `?id=nope` → 404.
4. (Phase 2 — after commit 2: the D6 replay run, then the same 10d curl; filled by WP-M2 under "⏪ Replayed line".)
5. His surface — the worktree's Vite preview `ggcharts-frontend-8007` on :5177 (`vite.local.config.ts`, AMENDMENTS11
   A2) proxied to :8007 with `X-User-Email: ajaykandakatla@gmail.com` and the `/api/features/*` + `/api/usage/*` bypass
   (never mark his ✨ seen): `/chart-maps?tab=gajjala&sub=track_record&span=10d&view=timeline` → the toggle, only A+
   rows, minis drawing as they scroll in, 📈 opens the tape with its lines / dots / read;
   `/chart-maps?tab=catalysts&sub=promo` → a Promo row's mini and 📈 tape look exactly as on pounce. DOM scan for NaN /
   undefined / None and the banned words.
6. Cleanup — that exact name only, then stop the preview:

```bash
docker rm -f cheetah-tmp-gr-api
```

LIVE proof after the deploy: https://pounce.ajaykandakatla.dev/chart-maps?tab=gajjala&sub=track_record&span=10d&view=timeline

## ⏪ Replayed line

phase 2 — filled by WP-M2

## ✅ / ❌ categories and loss facts

phase 2 — filled by WP-M2

## HIS CALL (each ships with the default shown; nothing here is decided for him)

- **Q1 The tape** (his ask — the Promo Circuit graph: 5-minute closes + the entry's lines; DEFAULT) vs PatternChart candles (D1).
- **Q2 🧠 potential rows get no tape** in this build (his ask names the entries; DEFAULT) vs a tape on 🧠 rows too (D3).
- **Q3 The "10d" span** (`LEDGER_SPAN_SESSIONS_LONG = 10`, MINE) added; the default span stays 5d (D3).
- **Q4 🎾 replayed rows** shown with "⏪ replayed · 🎾 ungated" (DEFAULT, D10) vs dropped (a replay has no float gate).
- **Q5 Timeline order within a day**: newest first — the 🏁 served order (DEFAULT) vs oldest first.
- **Q6 The timeline view hides the 🧠 % lines** (MINE — an A+-only list under the 🧠 % reads as the A+ %; DEFAULT) vs keeps them.
- **Q7 The default view** 📋 all alerts (DEFAULT, D3) vs 🕰️ entries timeline.
- **Q8 A replayed row's next column** for a name whose next session is not in the study cache: ONE as-printed Massive
  minute fetch per name at replay time (DEFAULT in the D6 run) vs "not graded (bars not cached)".
- **Q9 Replay only 2026-10-09 and 2026-10-12** ("the past week"; 10-13 on have records and are refused by design;
  DEFAULT) vs older sessions the study cache covers (back to 2025-10).
- **Q10 A completed day missing from intraday_cache** is fetched ONCE by the house loader for the tape, then cached
  (DEFAULT, C1) vs cache-only (an empty tape until a nightly caches it).
