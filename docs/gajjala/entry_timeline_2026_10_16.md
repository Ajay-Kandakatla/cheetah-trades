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
4. (Phase 2 — after commit 2: the D6 replay run, then the same 10d curl — "⏪ Replayed line" → "The D6 run" below.)
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

Ajay, 2026-10-16 ~22:30 ET (verbatim):

> "Would you be able to back test for the past week from his alerts any way to do so?
> build a pre historic timeline or so?"

**Not a backtest and not a measurement.** 2026-10-09 and 2026-10-12 — the two sessions of the past week before the tab
kept records — are **replayed**: today's detectors run again on the minute bars the 2026-10-14 study cached, each A+
graded by the same trade math (`ledger.grade`). These rows **never rang**. They sit on their own ⏪ line
(`ledger.LINES[2]` "replayed", `KIND_TEXT[("aplus", "replayed")]` "⏪ A+ replayed", their own count bucket
`COUNT_LINES[3]` "replayed" whose `pct` is ALWAYS None) and are in **no %** and in no live / shadow / 🎯 entry count. The
2026-10-14 study read NULL; nothing here changes that.

- **Code**: `backend/scripts/gajjala_replay.py` (NEW, offline, outside the source guard — imports the study, the ledger,
  the store and `tape.bars5`); the ledger reads the docs through `store.replay_rows` (`served_block` only —
  `rows_for(…, with_replay=False)` by default, so the nightly `grade_step` and `today_read` never see a replay doc and
  never re-grade one against adjusted bars). Collection `gajjala_replay` (NEW, `store.REPLAY`, kept, no TTL), written
  ONLY by the script's `--write` through `store.upsert_replay` (refuses an id that does not start `REPLAY:` and any key
  outside `store.REPLAY_KEYS`).
- **Ids**: `ledger.replay_id(date, SYM, setup)` = `"REPLAY:{date}|{SYM}|{setup}"` — never a `ledger_id`, so a replay
  doc can never collide with a real record; `alert_of` reads a replay doc only with state `replayed`, kind `aplus`, an
  `alert` block, the exact id and no `#` in it (AMENDMENTS11 F15); a `REPLAY:` id never reads live (C6).
- **What the 🏁 panel serves for it**: the row's Kind "⏪ A+ replayed" and its chip `REPLAY_CHIP` "⏪ replayed"
  (`REPLAY_CHIP_UNGATED` "⏪ replayed · 🎾 ungated" on a 🎾 Reversal Squeeze row — `FLOAT_GATED_SETUPS`, HIS CALL Q4);
  the line `replayed_text` = `REPLAYED_HEAD` "⏪ Replayed with today's detectors (never rang, not in any %)" + the
  same / next counts with NO "% won"; `replayed_note` = `REPLAY_NOTE` "Replayed on the study's same-day universe (a
  subset of what the live scanner lists), no float gate, as-printed bars; these never rang. Not a measurement — the
  2026-10-14 study read NULL."; a replay read fault → `REPLAY_FAULT_TEXT` "⏪ replay not read" (the block serves without
  the line); a column the script could not grade → `REPLAY_NOT_GRADED_TEXT` "not graded (bars not cached)". The 📈 tape
  of a replayed row draws the doc's stored `bars5` (as-printed) with `note` = `REPLAY_NOTE` and never calls a loader.

### The CLI (BUILD_SPEC11 §3.13)

```bash
python -m scripts.gajjala_replay --sessions 2026-10-09 2026-10-12 --cache /cache --out /replay_out/dry
python -m scripts.gajjala_replay --sessions 2026-10-09 2026-10-12 --cache /cache --out /replay_out/offline --offline --types none
```

- `--sessions D [D …]` (required), `--cache DIR` (required — the study cache, opened `offline=True` ALWAYS: it is
  mounted read-only and the replay never writes it), `--out DIR` (required — `events.csv` + `replay.json`, counts only,
  no % / rate / win key), `--write` (upserts one `gajjala_replay` doc per kept event; re-runs replace — idempotent),
  `--sha SHA` (the worktree's git HEAD, 7–40 hex, required with `--write`; the container has no git), `--offline` (no
  as-printed minute fetch for a next session missing from the cache), `--types store|none` (default `store` = the live
  scanner's own type map), `--symbols A,B`.
- Per session: `S.superset` over the cached grouped-daily → per name `S.study_symbol_day(…, scope="live",
  with_pool=False, method="v2")` → keep an event only when `entry_class == "aplus"`, no `variant`, no `grade`, and
  `S.window_reason(…)` is None (≥ 09:45 ET, inside the extended close); every other event is counted in
  `dropped{not_aplus, variant, grade, window}`. The alert time = the study's pass label `pass_t` (ET → aware UTC);
  `same` / `next` graded by `LG.grade` over `LG.bars_from_frame(the cached minutes)` with `LG.session_bounds`; a next
  session missing from the cache → ONE as-printed minute fetch per name at replay time (`adjusted=false`, never
  written; HIS CALL Q8), or with `--offline` → `next` null → "not graded (bars not cached)". A split on file after the
  alert → a split cell (the ledger's own split lookup).
- Exit **0** when at least one session was replayed, **3** when every session was refused, **2** for a refusal before
  anything is read.

### The refusals (listed, never replayed)

- **Regular session**: 09:30–16:00 ET → prints `refused: {HH:MM} ET is inside the regular session — the replay runs after
  16:00 ET` and exits 2 before reading anything (no override, like the study's `refused_window`).
- `--write` without a 7–40 hex `--sha` → 2. A cache directory without the study's layout marker (StaleCache) → 2.
- A session that is not a market day or is after `S.default_end(now)` → "not a completed session".
- A half day the study leaves unlisted (`S.half_day_unlisted`).
- `store.records_on(d)` None → "records unreadable"; > 0 → "{n} gajjala_alerts / gajjala_scan docs on file — the record
  stands, never replayed" (a session with any record is never replayed — no collision by construction; 10-13 on are
  refused by design, HIS CALL Q9).
- The grouped-daily of the session and its prior session not in the cache → "grouped not cached".

### What a replay cannot know — `ledger.REPLAY_CAVEATS` (verbatim, in order; served on every doc as `caveats`)

1. "Universe: the study's same-day list (grouped daily, his three scanner numbers, the first qualifying minute) — a subset of what the live scanner lists (no stay-listed carry, no split hold-outs)."
2. "No float gate: 🎾 Reversal Squeeze rows are ungated structure (no point-in-time float on file)."
3. "As-printed bars (not split-adjusted), graded only on the study cache's own minute bars."
4. "The alert time is the 5-minute pass label (the live pass rang about a minute later); its freshness, halts and after-hours context are not replayed." (the 5 = `GC.PASS_CADENCE_SEC // 60`, built in the f-string, never typed)
5. "A later reverse split unknown to the dated type lookup is not seen."
6. "One break per setup per day: the study keeps the first break of any class — a later A+ behind an earlier stopped or variant break on the same setup is not replayed." (AMENDMENTS11 F10)
7. "These never rang. Not a measurement — the 2026-10-14 study read NULL."

### The D6 run (main session, tonight, outside 09:30–16:00 ET — the ONLY prod write: the NEW `gajjala_replay` collection)

On the throwaway api `cheetah-tmp-gr-api` (`scratchpad/gg_charts/gr_tmp_api.sh`: the study cache read-only at `/cache`,
ONE output mount `/replay_out`, `_mongo_put_day` a no-op — AMENDMENTS11 F18). `--sha` = the worktree's HEAD, read on the
host (the container has no git).

```bash
docker exec cheetah-market-app-mongo-1 mongosh cheetah --quiet --eval 'printjson({replay: db.gajjala_replay.countDocuments({}), alerts: db.gajjala_alerts.countDocuments({}), ledger: db.gajjala_ledger.countDocuments({}), alerts_days: db.gajjala_alerts.countDocuments({date: {$in: ["2026-10-09", "2026-10-12"]}}), scan_days: db.gajjala_scan.countDocuments({date: {$in: ["2026-10-09", "2026-10-12"]}})})'
docker exec -i -w /app cheetah-tmp-gr-api python -m scripts.gajjala_replay --sessions 2026-10-09 2026-10-12 --cache /cache --out /replay_out/dry
docker exec -i -w /app cheetah-tmp-gr-api python -m scripts.gajjala_replay --sessions 2026-10-09 2026-10-12 --cache /cache --out /replay_out/write --write --sha "$(git -C /Users/ajay/clinet-test/wt-ggcharts rev-parse HEAD)"
docker exec cheetah-market-app-mongo-1 mongosh cheetah --quiet --eval 'printjson({replay: db.gajjala_replay.countDocuments({}), alerts: db.gajjala_alerts.countDocuments({}), ledger: db.gajjala_ledger.countDocuments({})})'
```

Check: `alerts_days == scan_days == 0` before; the dry run's kept count == the write run's `written`; after: `replay` =
before + written, `alerts` and `ledger` unchanged.

Then the branch proof (§5.4 step 4) — the same 10d GET and a replayed row's tape (`<SYM>` / `<setup>` from
`replay.json`):

```bash
curl -s -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8007/chart-maps/gajjala?sub=track_record&span=10d"
curl -s -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8007/chart-maps/gajjala/entry-tape?id=REPLAY%3A2026-10-12%7C<SYM>%7C<setup>"
```

Check: the 10-09 / 10-12 rows read `line "replayed"`, `kind_text "⏪ A+ replayed"`, with `replayed_text` /
`replayed_note`; `counts.live|shadow|entry` and `counts_text` byte-equal to the GET before the run (NEGATIVE); the
replayed tape's `note == REPLAY_NOTE`, its bars = the doc's `bars5`.

### Run log (main session — filled after the D6 run)

Run 2026-10-17 00:36 ET (dry) and 00:5x ET (write) on the throwaway api `cheetah-tmp-gr-api` (branch 60aeae5a; the study
cache mounted read-only; `_mongo_put_day` disabled; Massive WS off). Counts read on the live Mongo before and after:

| | before | after |
|---|---|---|
| `gajjala_replay` docs | (no collection) | 7 (2026-10-09: 2 · 2026-10-12: 5) |
| `gajjala_alerts` docs | 22 | 22 |
| `gajjala_ledger` docs | 119 | 119 |
| `gajjala_scan` docs | 105 | 105 |
| `gajjala_alerts` / `gajjala_scan` on 2026-10-09 + 2026-10-12 | 0 / 0 | (n/a) |

- dry run `replay.json` summary (per session: state, superset, listed, events, kept, dropped, same_graded,
  next_graded, next_not_cached, split):
  `2026-10-09: replayed · superset 17 · listed 14 · events 2 · kept 2 · dropped {not_aplus 0, variant 0, grade 0, window 0} · same_graded 2 · next_graded 2 · next_not_cached 0 · split 0 · no_bars 0 · type_unknown_kept 17`
  `2026-10-12: replayed · superset 25 · listed 21 · events 5 · kept 5 · dropped {0, 0, 0, 0} · same_graded 5 · next_graded 5 · next_not_cached 0 · split 0 · no_bars 1 · type_unknown_kept 25`
  cache_stats `grouped_hit 4 · minutes_hit 85 · minutes_offline_miss 9 · minutes_fetch_unwritten 7 · type_offline_miss 84` (the seven
  unwritten fetches = the next-session minutes the study cache did not hold — HIS CALL Q8's default; the dated type lookup
  had no `types/` for these two sessions and the live map did not cover them, so every name was kept as unknown type —
  the live scanner's own `SCAN_UNKNOWN_TYPE_POLICY = "list"`). Events kept: 10-09 WFF 🌀 15:00 (LOSS) · WFF 🎾 16:50 (WIN next
  session); 10-12 CLWT 🎾 17:15 (no entry) · SKYA 🌀 11:00 (open) · TCRT 🚩 16:20 (WIN next session; thin R 0.96%) · WFF 🎾 20:00
  (no entry) · YMAT 🎾 14:50 (open).
- write run `replay.json` summary + `written`: the same two sessions, `kept 2 + 5`, **`written 7`** (every `_id` `REPLAY:{date}|{SYM}|{setup}`, state `replayed`); a dry run before it wrote 0.
- detectors sha / sha256: `60aeae5a` / `519282dd2699b0ad7ab2130441e7d4fdf5fc4e248525e0145604b5ce06df42fc` (chart_maps/gajjala/detectors.py).

## ✅ / ❌ categories and loss facts

Ajay, 2026-10-16 ~22:45 ET (verbatim):

> "I want winners and losers category in his track record and would like us to study the losers"

**Counts are ROWS, never a %.** The chips sort and filter the rows already on the 🏁 Track record; they move no % line,
no count line (`counts`, `counts_text`, `shadow_text`, `entries_text`, `replayed_text` are byte-equal with or without
them — a test monkeypatches `bucket_of` to answer "loss" everywhere and proves it). HONESTY gains one final sentence:
"The winners / losers chips count ROWS (a name that rang on two setups is two rows); the % lines are unchanged."
UNMEASURED — nothing here is an edge, a win rate or an expectancy.

### The buckets — `ledger.BUCKETS`, `BUCKET_TEXT`

| bucket | `BUCKET_TEXT` (served per row) |
|---|---|
| `win` | "✅ winner" |
| `loss` | "❌ loser" |
| `open` | "⏳ open" |
| `flat` | "➖ flat" |
| `out` | "— no fill / not graded" (AMENDMENTS11 F7) |

**The bucket rule** (`ledger.bucket_of(same_state, next_state, next_due=True)`, BUILD_SPEC11 C8 as modified by
AMENDMENTS11 F7 — total, from the two SERVED cell states):

1. the next column win / loss → that;
2. else the same column win / loss → that (next pending / split / the decided same column copied into next);
3. else the next column "flat" → "flat";
4. else the same column "open" AND the next column "pending" AND the next column still due → "open";
5. else "out" — no_entry / no_plan / no_risk / no_time / pending / split, a replayed row whose next session was never
   cached (`served_block` passes `next_due = False` for it — never "⏳ open" forever), same open + next split, any
   unknown string.

A thin-R row keeps its real bucket (win / loss) AND its thin chip — it stays out of the %. Pending rows read "— no fill
/ not graded" until the nightly grades them (HIS CALL Q12, MINE). A provisional today loss reads ❌ and its cell says
"so far · not final".

### The chips — `CATEGORY_KEYS`, `CATEGORY_LABELS`, `cat=`

| key | `CATEGORY_LABELS` |
|---|---|
| `all` | "📋 all" |
| `win` | "✅ winners" |
| `loss` | "❌ losers" |
| `open` | "⏳ open" |
| `flat` | "➖ flat" |
| `out` | "— no fill / not graded" |

- Served `categories` (the 📋 all alerts view) and `categories_timeline` (the 🕰️ entries timeline — only the kinds that
  view lists), each `[{key, text, n, n_replayed}]` in `CATEGORY_KEYS` order. `text` = `"{label} {n}"` — the count is
  INSIDE the served text, the FE composes no number (C10); `n` counts the sent lines live / shadow / entry only, and
  when `r` replayed rows share the bucket the text gains `" +{r} ⏪"` (AMENDMENTS11 F13 — counted APART, HIS CALL Q14,
  MINE).
- The chips count the rows inside the served `days` — the rows the FE can filter — never every built row; the % lines
  still cover every row (AMENDMENTS11 F6, HIS CALL Q17; `LEDGER_ROWS_MAX` 400).
- `CATEGORY_PARAM` = `cat` rides the URL (`cat=loss`), FE-only — a chip click refetches nothing; default all; a span
  or view click keeps it, a sub click drops it. The filter keeps the replayed rows of that bucket (they never vanish
  under a filter). A filter that leaves nothing → `CATEGORY_EMPTY_TEXT` "No row in this category on this span."
- ~~No per-row ✅ / ❌ chip is drawn (AMENDMENTS11 F13, HIS CALL Q11, MINE)~~ — ANSWERED 2026-10-27 by his word ("Can
  you sort the winds in Gajjals I can't seem to tell the difference in that tab or show some greed flags on the wins
  rows"): the served flag (`flag_text` = `BUCKET_TEXT` on win / loss rows, `ledger.FLAG_BUCKETS`) IS drawn in the Ticker
  cell, every row is tinted by its served bucket, and the served sort chips (`ledger.SORT_KEYS`, ✅ wins first = the
  default) reorder each day's rows client-side. See `docs/gajjala/track_record_2026_10_16.md` § "✅ wins first + row
  flags (2026-10-27)".

### Loss facts — `ledger.loss_facts` / `ledger.loss_text` (DECISIONS11 D12)

Every `loss` row serves `loss_text` — plain facts from the STORED grade fields only (never a regrade, never a bar
read), no causal word. The grade read = the column that made the bucket "loss" (next when its state is loss, else
same). A win / open / flat / out row, or a loss without a fill time, → `loss_text` None. Shown as the ❌ row's sub-line
in 📋 all alerts and under the loser's tape in the 🕰️ timeline.

The FROZEN words (`ledger.py`, the only place):

| constant | served word |
|---|---|
| `LOSS_FACT_THIN` | "thin R (not in the %)" — thin rows, FIRST |
| `LOSS_FACT_STOPPED` | "stopped {n} min after the fill" — exit_t − fill_t, whole minutes |
| `LOSS_FACT_BEST` | "high +{x}R through the stop minute" — best_to_exit_pct ÷ 100 × fill_px ÷ the alert's R, one decimal (AMENDMENTS11 F17: best_to_exit includes the stop minute) |
| `LOSS_FACT_FILLED` | "filled {m} min after it rang" — fill_t − the alert time, whole minutes |
| `LOSS_FACT_FILL_MINUTE` | "stop in the fill minute" — reason `stop_fill_minute` |
| `LOSS_FACT_LATE_RTH` | "last {n} min of RTH" — n = `LEDGER_LOSS_LATE_RTH_MIN` |
| `LOSS_FACT_NEXT_MORNING` | "filled next morning (rang AH)" |
| `LOSS_FACT_STALE` | "filled ≥{n} min after the ring" — n = `LEDGER_LOSS_STALE_FILL_MIN`; never a next-morning fill (AMENDMENTS11 F2) |

`loss_text` = " · ".join of: the thin word (thin rows) · stopped · high (when R is known) · filled (when the alert time is
known) · ONE part, the first true of: stop in the fill minute → last 30 min of RTH → filled next morning → filled ≥60 min
after the ring (or none). Example (illustrative): "stopped 3 min after the fill · high +0.2R through the stop minute ·
filled 41 min after it rang · last 30 min of RTH". `ledger.fill_facts` is the same fill clock for ANY decided trade (win
or loss) — `loss_facts` calls it (one engine, AMENDMENTS11 F14); the losers study imports both.

The thresholds (`backend/chart_maps/gajjala/constants.py` — the only number source):

| constant | value | tag |
|---|---|---|
| `LEDGER_LOSS_FAST_MIN` | 5 | TRANSPORT — MINE (class C4: stopped ≤ 5 min after the fill) |
| `LEDGER_LOSS_LATE_RTH_MIN` | 30 | TRANSPORT — MINE (class C2: the last 30 min of RTH) |
| `LEDGER_LOSS_STALE_FILL_MIN` | 60 | TRANSPORT — MINE (class C3: filled ≥ 60 min after the ring) |
| `LEDGER_LOSS_NO_PROGRESS_R` | 0.3 | TRANSPORT — MINE (class C5: high < +0.3R before the stop) |
| `LEDGER_LOSS_GAVE_BACK_R` | 0.8 | TRANSPORT — MINE (class C6: high ≥ +0.8R, then stopped) |
| `LEDGER_LOSS_CLASS_FLAG_N` | 3 | Ajay 2026-09-03 (Rule #9: ≥3 of the same class → propose a rule, never change one) |

The five `LEDGER_LOSS_*` thresholds are MINE (HIS CALL Q13). The losers study that counts them:
`docs/gajjala/losers_study_2026_10_16.md`.

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
- **Q11 The per-row ✅ / ❌ chip** shown in the Kind cell (DEFAULT, D11's served `bucket_text`) vs hidden (the Same /
  Through-next cells already say WIN / LOSS — Rule #5 clutter on a dense table).
  - AMENDMENTS11 F13 (MINE — the planner's default, not his): the shipped default was **hidden** — no per-row chip was
    drawn; `bucket_text` stayed served for later.
  - **ANSWERED 2026-10-27 (his word):** shown — the served flag on win / loss rows, the row tinted, plus the served sort
    chips (wins first by default). His sentence, verbatim: "Can you sort the winds in Gajjals I can't seem to tell the
    difference in that tab or show some greed flags on the wins rows".
- **Q12 The bucket rule** (C8: the later decided column, else next flat, else same open, else "— no fill"; pending rows
  read "— no fill" until graded — DEFAULT) vs a separate "⏱ not graded yet" chip.
  - AMENDMENTS11 F7 (MINE): "open" only while the next column is still due (a replayed row whose next session was never
    cached, or same open + next split → "out"); the "out" word is "— no fill / not graded".
- **Q13 The loss-fact thresholds** `LEDGER_LOSS_FAST_MIN 5`, `LATE_RTH_MIN 30`, `STALE_FILL_MIN 60`, `NO_PROGRESS_R 0.3`,
  `GAVE_BACK_R 0.8` (MINE, D12) and the flag count 3 (his Rule #9); ANY rule drawn from a flagged class (e.g. "no A+
  fills in the last 30 min", "skip after-hours rings") is HIS CALL with the numbers — nothing changes a gate tonight.
- **Q14 Replayed rows inside the category chips** (counted where they filter — DEFAULT, C10) vs excluded from the chips
  (they would then vanish under a chip filter).
  - AMENDMENTS11 F13 (MINE): the shipped default is **counted APART** — a chip's `n` counts the sent lines only and its
    text gains " +{r} ⏪" for the replayed rows of that bucket; the filter keeps them (they never vanish).
- **Q15 The C9 (per setup) and C10 (per rang: pre / rth / ah) splits never flag** in the losers study — they are
  reported as splits only; C1–C8 are the flaggable classes (AMENDMENTS11 F14, MINE; DEFAULT) vs flagging a setup or a
  rang bucket with ≥3 loser trades too.
- **Q16 The mini tape never fetches** — only the 📈 full tape may load a missing day; the mini reads the cache and
  today's memo only (AMENDMENTS11 F8, MINE; DEFAULT) vs the mini loading a missing completed day itself.
- **Q17 The chip counts are of the rows shown** — the rows inside the served days (`LEDGER_ROWS_MAX` 400), while the %
  lines cover every row (AMENDMENTS11 F6, MINE; DEFAULT) vs chips over every built row (a chip could then show a number
  its list does not hold).

Q11, Q12 and Q14 are MINE (the planner's defaults, AMENDMENTS11 F13); D11's "(Ajay)" covers only his sentence.
