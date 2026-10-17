# 🎯 Gajjala's A+ entry push goes LIVE — all five setups (2026-10-16)

Code: `backend/chart_maps/gajjala/constants.py` (`GAJJALA_PUSH_MODE`), `backend/chart_maps/gajjala/alerts.py`
(`ENTRY_WORDS`, `entry_words`, `potential_rang_at`, `compose`, `run_pass`), `backend/chart_maps/gajjala/tab.py`
(`ENTRY_SENT_TEXT`, `_entry_times`, `_track_row`), `backend/chart_maps/gajjala/ledger.py` (`KIND_TEXT`, `HONESTY`,
`served_block` → `entries_text`), `frontend/src/pages/Notifications.tsx`, `frontend/src/lib/chartMaps.ts`,
`frontend/src/lib/newFeatures.ts`, `frontend/src/components/GajjalaBoard.tsx` (TrackRows). Spec: `BUILD_SPEC10.md` +
`AMENDMENTS10.md` F1–F11 + `DECISIONS10.md` D1–D11 (session scratchpad `gg_entry/`). Contracts:
`frontend/scripts/contracts.mjs` "🎯 Gajjala entry live (2026-10-16)". SPECS: the "🎯 A+ entry LIVE" bullet under
"Chart Maps — Gajjala's tab". ✨ `chart-maps-gajjala-entry-live-2026-10-16`. Line cites below are as of main `9be9b5eb`
unless a function name is given; the function name is the stable cite.

## READ THIS FIRST

1. **This rings his phone.** It is the first A+ push that ever reaches a device, and he ACTS on these pushes. Before
   2026-10-16 every A+ was recorded on /alerts as "shadow — not sent" and nothing was sent.
2. **UNMEASURED.** The 2026-10-14 study of the five setups (method v2) read **NULL**: no setup shows an edge over a
   risk- and hour-matched placebo (`docs/gajjala/study_2026_10_13.md`). Nothing on the tab, in a push or in this doc
   quotes an edge, a win rate or an expectancy. Every push still ends "UNMEASURED — his setup, not a buy signal".
3. **The flip is HIS call, not a measurement.** His words: "you alert me when that happens" (the clarification below).
   `GAJJALA_PUSH_MODE = "live"` carries `# Ajay 2026-10-16` on its line.
4. **C1 (default_prefs) — resolved the house way (AMENDMENTS10 F1).** `default_prefs["gajjala_setup"]` stays `False`:
   default off for everyone else, the 🧠 `gajjala_potential` / 🎚️ `tape_control` precedent ("everyone else starts
   off"). His devices are ON through `OWNER_KEEP_SET` + `scripts/owner_prefs_apply.py`. The send is owner-only
   (`alerts._default_send` → `push.hooks.notify_gajjala_setup` → `sender.send_to_user(owner, …)`), so the default
   never reaches anyone else either way. HIS CALL Q2 below is marked answered.
5. **Nothing about the gate changed.** Only the mode word flipped; the window, freshness, once-per-day claim,
   refusals and the dry on-open pass are exactly as shipped and tested on 2026-10-13.

## The ask (Ajay, verbatim)

2026-10-16 ~16:1x ET (two lines):

> "can you add liver tracker for Gajjala's entry.
> Also in the after market movers under Gajjala's can you make sure I can click on them."

Clarified (AskUserQuestion answer, ~16:10 ET):

> "Dont understand the question I amlooking for Entry of his stocks from all 5 tabs. When every they satisfy all his
> criteria.. LIke for some he says we need to make sure EMA is kissed you alert me when that happens 5 mins track of it
> when there are potentials and also look for new potentials"

Click target answer: **"Same place as other Gajjala rows (Recommended)"** (the ☀️ / 🌙 movers part ships in commit 2).

Reading: the A+ ENTRY push (kind `gajjala_setup`) goes LIVE for all five setups — one push the moment a name meets
ALL of GG's criteria (for 💋 Kiss & Fly: the pullback kissed and honored the 9 EMA, then the entry bar broke the
trigger). "5 mins track of it when there are potentials and also look for new potentials" = the existing 5-minute
pass, the 🧠 potential tracker and the 🧠 potential pushes stay exactly as they are; the entry push closes the loop
("the potential you were told about at HH:MM just entered").

## What rings (the shipped gate, unchanged)

| Step | Where | What |
|---|---|---|
| mode | `constants.GAJJALA_PUSH_MODE` → `alerts.push_mode()` | "live" only on the exact string "live"; any other value runs as shadow (fail closed). A flip back is one word. |
| A+ only | `alerts.run_pass` (`not_aplus_variant`) | a read with `variant` (long flag, near-kiss) or `grade` (VCP "B — imperfect") is refused. A+ = `detectors._resolve_break`: every rule met, the entry bar's HIGH traded through the trigger, not stopped, the entry bar is the last closed bar. |
| fresh | `alerts.pushable`, `MAX_ENTRY_AGE_SEC` = `PASS_CADENCE_SEC` + `BAR_SETTLE_SEC` | the entry bar must be the latest closed bar of the read's own frame, closed within one pass; else `late`. |
| closed day | `alerts._closed_reason` | `suppressed_closed`; the sender also drops on closed days. |
| window | `alerts.window_reason`, `alerts._closes` | bar judged by its START: before 09:30 → `suppressed_premarket`; before 09:30 + `NO_TRADE_AFTER_OPEN_MIN` (09:45) → `suppressed_first15`; label after the extended close (20:00, 17:00 on `HALF_DAYS`) → `suppressed_window`. |
| refusals | `{key}#{state}` | recorded, never consume the day's claim — counted on that pass's /alerts row, never rung. |
| dry | `run.py` `push_dry = bool(dry or on_demand)` | an on-open or dry pass returns before compose / claim / any read of the potential: an open of the tab never rings. |
| claim | `alerts.claim_key` `GG:{date}\|{SYM}\|{setup}` | once per (symbol, setup, ET day); the claim upsert is atomic, so two passes on the same key send once. |
| no double ring | live branch of `alerts.run_pass` | a live claim first checks the `SHADOW:` twin: an A+ recorded in shadow earlier that day never rings after the flip (today's seven 10-16 shadow keys never ring). |
| send | `push.hooks.notify_gajjala_setup` → `sender.send_to_user(owner, payload, kind="gajjala_setup")` | owner only; the device toggle, quiet hours and the market-day drop sit at the sender. Settles `pushed` / `no_target` / `failed` + `result`. |
| replay | `run.py` main | a manual `--now` replay that is not `--dry-run` refuses to run (AMENDMENTS10 F7) — a replay never rings the real sender. The guard is `args.now and not args.dry_run and not args.on_demand`: `--on-demand` is exempt because the on-open pass is dry by construction (`run_pass` sets `push_dry = bool(dry or on_demand)`), so a `--now --on-demand` replay never sends, claims or records a row either. |

Window as served: 09:45–16:00 and 16:00–20:00 ET (09:45–13:00 and 13:00–17:00 on NYSE half days), never 09:30–09:45
(his first 15 minutes), never pre-market, silent on closed days, every A+ its own push (no digest).

## The push (E1–E5)

Order = numbers first on the lock screen (AMENDMENTS10 F9, HIS CALL Q11): he ACTS on the trigger and the stop, and the
lock screen clips the body to about 180 characters (`push/sender.py`).

| # | Where | Exact text (`{…}` computed; prices `tab._px`; % one decimal; ET) |
|---|---|---|
| E1 | title | `{emoji} {SYM} · {label} A+ entry` — e.g. `💋 PMI · EMA Kiss & Fly A+ entry`. WIDENED 2026-10-17: + ` · 🚫` on the title when the name is on his list (2026-10-17, DECISIONS12 D4 / AMENDMENTS12 A1); unflagged titles unchanged |
| E2 | body | `broke {T} on the {frame} bar closing {HH:MM} ET · stop {S} (−{r}%) · {ENTRY} · 🧠 potential rang {HH:MM} ET · {float_text} · after-hrs · he uses limit orders and less size outside RTH (S8 1:16:35) · UNMEASURED — his setup, not a buy signal` — the 🧠 clause only with a pushed potential, the after-hrs clause only for an entry bar starting at or after the regular close; empty bits dropped. WIDENED 2026-10-17: + ` · 🚫 not eligible at Fidelity` before UNMEASURED and ` · 🚫` on the title when the name is on his list (2026-10-17, DECISIONS12 D4 / AMENDMENTS12 A1); `docs/gajjala/broker_flags_2026_10_17.md` |
| E3 | items[0].text | `{SYM} · {emoji} {label} A+ entry · broke {T} · stop {S} (−{r}%) · {ENTRY}` |
| E4 | `{ENTRY}` | `alerts.entry_words(setup)` — the per-setup table below |
| E5 | 🧠 clause | `🧠 potential rang {HH:MM} ET` (`alerts.POTENTIAL_RANG_TEXT`) |

url: `/chart-maps?tab=gajjala&sub={setup}&focus={SYM}` (unchanged; = `potential.deep_link`).

### `{ENTRY}` — the setup's entry in the words of his rules (`alerts.ENTRY_WORDS`)

One clause per setup, in `constants.SETUPS` order, from `backend/chart_maps/gajjala/verified_rules.json`. The EMA
lengths are filled at call time from `orderflow.signals` `EMA_FAST` / `EMA_SLOW` (9 / 21 today) — never typed. The FE
composes none of them. 🎾 has no first-hand entry rule on file, so its clause is the detector criteria in plain words.

| Setup | `{ENTRY}` (EMA 9 / 21) | Rule ids | Status (verified_rules.json) | His words on file (quote, else rule text) | What the detector checked |
|---|---|---|---|---|---|
| 🚩 bull_flag | `Quiet shallow flag; entry = the top of the pullback bar` | BF2, BF7 | BF2 confirmed_first_hand; BF7 confirmed_multi_source (his S9 1:59:24 source is first-hand) | BF2 "almost sideways or very shallow pullback with less volume compared to the left side" (S8 21:45–24:37); BF7 "entry at the top of the pullback bar, exit [stop] at the bottom of it" (S9 1:59:24) | `_bull_flag_leg`: K2 / K3 / K4, trigger = the pullback bar's high |
| 💋 kiss_fly | `Kissed and honored the 9 EMA; entry = the kiss bar's high` | KF1, KF2 | both confirmed_first_hand | KF1 "it waits more and honors the 9 EMA whenever it pulls back" (S8 31:33); KF2 rule text "Entry = the high of the kiss bar" (S8 31:33–32:41, no captured quote) | kiss = a touch within `K5_KISS_TOL_PCT` of the 9 EMA AND a close above it; every pullback close ≥ the 9 EMA (`KF_HONOR_ALL_PULLBACK_CLOSES` True); trigger = the kiss bar's high; no touch → near-kiss variant, never A+ |
| ➖ horizontal_fade | `9 and 21 EMA merged on a quiet sideways base; entry = the new highs` | HF1, HF3 | both confirmed_first_hand | HF1 "when the 9 EMA and 21 EMA merge around that area then slowly the momentum starts" (S8 32:49–33:50); HF3 rule text "once you see it takes the new highs … this would be my entry" (S8 33:27) | `_fade_checks` k4 / k3_vol / k6_tight / k6_merge / k6_decay; trigger = the base high (`HF_TRIGGER` "base_high") |
| 🌀 intraday_vcp | `Each cycle tighter, holding the 21 EMA; entry = the top of the previous cycle highs` | VCP1, VCP2 | both confirmed_first_hand | VCP1 "it honors the 21 EMA when it pulls back with less volume … the volatility contracts in each cycle" (S8 33:50–34:37); VCP2 rule text: entry at the "top of the previous cycle highs" (S8 33:50–34:37) | k4_cycles / k7_ratio / k7_ema21 / k3_vol; grade B excluded; trigger = the previous cycle high |
| 🎾 reversal_squeeze | `Tennis-ball reversal after a failed try at the highs; entry = the highs after the quiet base` | RS2, RS4 | **no first-hand entry rule on file**: RS2 and RS4 are confirmed_multi_source (2+ sources); RS4 has no quote | RS2 "whenever there is a drop it tries to squeeze up, whenever it hits the ground it [reverses] hard" (S8 35:02); RS4 rule text "Entry = takes the highs after the quiet base; stop = the base low" (S8 34:43, no quote) | `k8_tennis` (tennis ball), `k8_failed` (failed attempt at the highs), `k8_base_len` (quiet base); trigger = the high after the base |

Wording notes (AMENDMENTS10 F5): the 🚩 clause dropped "after the pole"; the ➖ clause says "quiet sideways base", not
"tight" (`K6_TIGHT_PCT` is Ajay's number, not GG's words). Two clauses assume a constant: 💋 "honored" assumes
`KF_HONOR_ALL_PULLBACK_CLOSES = True`; ➖ "the new highs" assumes `HF_TRIGGER = "base_high"`. The contracts and
`backend/tests/test_gajjala_entry_words.py` fail if either changes, so the words get revisited. Each `ENTRY_WORDS`
line cites its rule ids in a comment; the contracts check every cited id belongs to that setup's topic.

### Example (💋 Kiss & Fly, regular hours, a 🧠 potential that rang)

```
title   💋 GGA · EMA Kiss & Fly A+ entry
body    broke 11.00 on the 5m bar closing 10:35 ET · stop 10.81 (−1.7%) · Kissed and honored the 9 EMA; entry = the kiss bar's high · 🧠 potential rang 10:05 ET · Float 3.2M · UNMEASURED — his setup, not a buy signal
item    GGA · 💋 EMA Kiss & Fly A+ entry · broke 11.00 · stop 10.81 (−1.7%) · Kissed and honored the 9 EMA; entry = the kiss bar's high
url     /chart-maps?tab=gajjala&sub=kiss_fly&focus=GGA
```

WIDENED 2026-10-17: + ` · 🚫 not eligible at Fidelity` before UNMEASURED and ` · 🚫` on the title when the name is on his list (2026-10-17, DECISIONS12 D4 / AMENDMENTS12 A1) — the flagged example is in `docs/gajjala/broker_flags_2026_10_17.md`. The example above is unflagged and stays exact.

### The 🧠 clause (`alerts.potential_rang_at`)

`store.get_potential(session, SYM, setup)` — the 🧠 potential doc of the SAME key `{date}|{SYM}|{setup}`. The clause
appears only when its `push.state` is "pushed" and `push.at_et` is a "HH:MM" string. The read sits in `run_pass` AFTER
every refusal and AFTER the dry gate (an open / dry / refused pass reads nothing), in its own try: a read fault means
no clause, never a skipped push. A 🧠 potential of another setup, of another day, or one that went `no_target` /
`failed` / `claimed` gives no clause. `compose` stays pure (it takes `potential_at_et=`, never a store).

## 📈 Track row: `entry_text` (DECISIONS10 D4)

On the 🧠 Potential sub, each 📈 Track row serves `entry_text` = `🎯 entry sent {HH:MM} ET` (`tab.ENTRY_SENT_TEXT`)
when the A+ entry of the same (date, symbol, setup) RANG — a `GG:` claim in state pushed — and `None` otherwise. One
read per 🧠 build: `tab._entry_times(st, [session, prev])` = `store.alert_rows` classified by `ledger.alert_of` (the
ledger's own engine — no new store helper); each doc in its own try, so one malformed doc never blanks the others
(AMENDMENTS10 F8); a read fault serves the board with every `entry_text` None. Shadow docs, `#` refusals, `claimed` /
`failed` / `no_target` claims are never entries (HIS CALL Q7). The FE prints the served string next to `push_text`
(`data-testid="gg-track-entry-{SYM}-{setup}"`) and types no entry word.

## 🏁 Track record change (E7 / E8, AMENDMENTS10 F3)

- A pushed `GG:` doc is already line "live" in `ledger.alert_of`; `KIND_TEXT[("aplus", "live")]` = `🎯 A+ entry`.
- **Live A+ entries are counted on their OWN 🎯 line, never pooled into the 🧠 headline %.** An A+ exists only once
  the trade survived its entry bar (`_resolve_break` `stopped_after`), while a 🧠 potential push carries no such
  survivorship — pooling them would lift the % by construction. `served_block` counts `kind == "aplus"` live rows under
  `counts["entry"]` and serves `entries_text` = `🎯 A+ entries sent (their own line, not pooled with the 🧠 %): same
  session … ; through next session …` (None when the span has no such row). The headline `counts.live` holds 🧠 rows only.
- A live entry and its 🧠 potential are two rows (different alert times, different fills) — on two different lines.
- Shadow-period A+ rows (2026-10-13 … 16) stay on the shadow line, "A+ shadow — never sent", out of the %; `shadow_text`
  is unchanged.
- `HONESTY` (served verbatim): "A ledger of the alerts as sent, graded by GG's own trade math — not a backtest of a
  strategy, and small n early. A+ rows from the shadow period (never sent) stay out of the %; A+ entries sent live are
  counted on their own 🎯 line, not pooled with the 🧠 pushes — an A+ exists only once the trade survived its entry bar.
  The 2026-10-14 study of the five setups read NULL — no edge over a matched placebo (docs/gajjala/study_2026_10_13.md);
  this record does not change that."
- The 🏁 chip still counts 🧠 rows only (HIS CALL Q5).

## Surfaces that flip with the mode (served)

`tab.push_block` (live text "📲 Every A+ rings your phone — every rule met and the entry bar closed; never the first
{N} minutes, never pre-market, once per name, setup and day. UNMEASURED."), `rules_info._gajjala_section` live line,
`alert_status` live pass rows (`read_gajjala_shadow` keeps listing the pre-flip shadow docs), /alerts 🚩 chips (a live
pass wears no shadow chip). Hard-coded texts updated: the Notifications 🚩 / 🧠 / Essentials details, the
`TAB_META.gajjala` blurb, and the older ✨ entries (🚩 10-13, 🧠 10-15, 🏁 10-16) each gained "A+ entries went live
2026-10-16" — an old entry must not lie.

## Volume on file (Mongo read-only, 2026-10-16 16:17 ET)

- A+ shadow docs per day: 10-13: 4 · 10-14: 4 · 10-15: 5 (+1 `#suppressed_premarket`) · 10-16: 7 (+1
  `#suppressed_premarket`) — PMI 10:35, TGL 10:45, HCAI 11:05, GP 14:15 (R 0.3%, under `LEDGER_MIN_R_PCT`), LHSW 15:30,
  CDT 16:00, + 1.
- **7 of 7** 10-16 A+ had a 🧠 potential push first (3 of 5 on 10-15) → most entry bodies carry the 🧠 clause.
- 🧠 potential pushes: 46 (10-15), 59 (10-16). The entry push adds about 4–7 a day on that tape.
- Nothing in this build measures anything: no number, no CI, no placebo. The 🏁 ledger stays accounting.

## ☀️ / 🌙 movers clickable

Commit 2 (DECISIONS10 D7, BUILD_SPEC10 §4 WP-D). Ajay, 2026-10-16: *"Also in the after market movers under Gajjala's
can you make sure I can click on them."* — click target: *"Same place as other Gajjala rows (Recommended)"* (his
answer).

Before: a ☀️ / 🌙 mover WITH bars was a `PatternChart` tile (a router link to `tile.href` = `/sepa/{SYM}?tab=supply`),
but a mover WITHOUT bars (the usual case for movers — the name is not in `gajjala_reads`) printed a plain anchor, a
full-page reload and the only non-router in-app link in `GajjalaBoard.tsx`; the 🌙 "Today's A+ recap" rows linked
nowhere.

Now (`frontend/src/components/GajjalaBoard.tsx`):
- **Bar-less tile** → a router `<Link>` to `withSource(ggHref(t.href), 'chart-maps', location.search)` with the back
  state `{from: /chart-maps?<the tab's own query>, label: 'Chart Maps'}` — the `PatternChart.tsx:235-236` glue, so the
  charted and the bar-less tile land on the same page and ← Back returns to the same ☀️ / 🌙 sub (Ajay 2026-08-25: "back
  button do not take me to the same place in these tabs"). testid `gg-tile-link-{SYM}`. An href `ggHref` rejects (not
  an in-app path: `//host`, `https://…`, empty, null) renders the symbol as plain bold text.
- **🌙 recap row** → a router `<Link to={ggHref(r.href)}>` around the unchanged row text; `href` is SERVED by
  `tab.recap` = `potential.deep_link(sym, setup)` = `/chart-maps?tab=gajjala&sub={setup}&focus={SYM}` (the A+ push url,
  what a 🏁 Track-record A+ row links). testid `gg-recap-row-{SYM}-{setup}`. No served href (an older API) or an unsafe
  one → the row stays text.
- **CardExtras lines** (the ☀️ / 🌙 served text under a tile) stay text — the tile is the link (D7c).
- The FE composes no href; `lib/gajjala.ts` recap rows gained `setup?` / `href?`.

Tests: `frontend/src/components/GajjalaBoard.movers_links.test.tsx` (clones of the hand fixture
`gajjala_board_2026_10_13.json`, never edited; MemoryRouter + a location probe — a plain anchor never moves a
MemoryRouter, so a landed pathname proves the router link). NEGATIVES: unsafe tile / recap hrefs render text, the
unmodified fixture renders no recap link, the CardExtras lines carry no link, the 📓 external sources stay
`target="_blank"` anchors. `GajjalaBoard.test.tsx` (the `gg-recap` text pin) passes untouched. Contracts 🎯 block
check 11: the ✨ entry quotes the movers line verbatim; no in-app anchor in `GajjalaBoard.tsx` (comments stripped first,
AMENDMENTS10 F10; only `target="_blank"` anchors allowed); the tile / recap testids + `withSource(ggHref(t.href)` +
`ggHref(r.href)`; `tab.recap` serves `"href": PT.deep_link(sym, setup)`. HIS CALL Q10 (the back state, MINE).

## Deploy order (main session, after both commits are on main — DECISIONS10 D10, the LIVE-kind order)

Step 1 — api + frontend, then the owner prefs DRY run:

```bash
./deploy-cheetah-main.sh api frontend
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.owner_prefs_apply
```

Step 2 — ONLY if the dry diff is non-empty AND every change in it is `gajjala_setup` (AMENDMENTS10 F6); otherwise skip
it and report (the 16:21 ET dry run read 4 devices, 0 changes → skip). It would otherwise un-mute any keep-set kind he
muted.

```bash
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.owner_prefs_apply --apply
```

Step 3 — verify every one of his devices reads `prefs.gajjala_setup: true` (a False device returns `no_target`), and
find the last pass line:

```bash
docker exec cheetah-market-app-mongo-1 mongosh cheetah --quiet --eval 'db.push_subscriptions.find({user_email:"ajaykandakatla@gmail.com"},{label:1,endpoint_short:1,"prefs.gajjala_setup":1}).toArray()'
docker logs --since 3m cheetah-market-app-cron-1 2>&1 | grep "gajjala pass:" | tail -1
```

Step 4 — cron, right after the `gajjala pass:` summary line of a :x1 / :x6 pass (never mid-pass — a killed pass leaves
a key "claimed"), and never 20:15–20:25 ET (the nightly grade runs in the cron container):

```bash
./deploy-cheetah-main.sh cron
docker exec cheetah-market-app-cron-1 python -c 'from chart_maps.gajjala import constants as GC; print(GC.GAJJALA_PUSH_MODE)'
```

Do steps 1 and 4 back to back: between them the tab says live while the cron still records shadow. The crontab is NOT
redeployed and NOT edited.

### The stale crontab comment

`backend/crontab:1246-1247` still says the push gate is "in SHADOW until Ajay flips constants.GAJJALA_PUSH_MODE:
recorded on /alerts, nothing sent". That file is host-mounted into the cron container; a deploy never ships it and this
build never edits it. The comment is stale since 2026-10-16 — the cron line itself is unchanged and correct.

## Verification

### Branch proof on the live DB, read-only (main session; after commit 1; after 16:00 ET)

1. Throwaway api = `scratchpad/gg_ledger/gl_tmp_api.sh` with the name `cheetah-tmp-ge-api`, the port
   `127.0.0.1:8006:8000`, the mount `/Users/ajay/clinet-test/wt-ggentry/backend:/app`, the same WS / drain flags, plus
   the BUILD_SPEC9 §5.4 `od.request` override (an open never starts a pass on the live DB). This api never runs
   `alerts.run_pass`. Health 200.
2. The real payloads through the real compose (writes nothing):

```bash
docker exec -i -w /app cheetah-tmp-ge-api python - <<'EOF'
from datetime import date
from chart_maps.gajjala import alerts as AL, store as ST
st = ST.default()
day = date(2026, 10, 16)
coll = st.alerts_coll()
before = coll.count_documents({})
docs = sorted(coll.find({"date": day.isoformat(), "state": "shadow"}), key=lambda d: d.get("entry_bar_t") or "")
for d in docs:
    r = {k: d.get(k) for k in ("setup", "frame", "entry_bar_t", "trigger", "stop", "risk_pct")}
    r["state"] = "aplus"
    body = (d.get("would_push") or {}).get("body") or ""
    flt = next((b for b in body.split(" · ") if b.lower().startswith("float")), "")
    pot = AL.potential_rang_at(st, day, d["symbol"], d["setup"])
    p = AL.compose(r, d["symbol"], {"float_text": flt}, session=day, potential_at_et=pot)
    print(p["title"])
    print("   ", p["body"])
    print("   ", p["items"][0]["text"])
print("gajjala_alerts docs before / after:", before, coll.count_documents({}))
EOF
```

   Should show the seven 10-16 entries (PMI, TGL, HCAI, GP, LHSW, CDT + 1), each title "… A+ entry", each body starting
   "broke …" with its setup's `{ENTRY}` clause after the stop and ending "UNMEASURED — his setup, not a buy signal",
   **7 of 7 with "🧠 potential rang HH:MM ET"**; before == after.
3. `curl -s -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8006/chart-maps/gajjala?sub=potential"` →
   `push.mode "live"`, `push.text` starts "📲 Every A+ rings your phone"; every `track.today.rows[].entry_text` is null
   (NEGATIVE: no `GG:` claim is pushed yet — only shadow docs exist).
4. `…?sub=track_record&span=5d` → `honesty` == the HONESTY text above; `entries_text` null; the PMI / TGL / HCAI rows
   `kind_text "A+ shadow — never sent"`; no row "🎯 A+ entry" yet.
5. `…?sub=postmarket` → every `postmarket.recap.rows[].href` == `/chart-maps?tab=gajjala&sub={setup}&focus={SYM}`.
6. His surface — the Vite preview on :5178 proxied to :8006 with `X-User-Email: ajaykandakatla@gmail.com` and the
   `/api/features/*` + `/api/usage/*` bypass (never mark his ✨ seen): `/notifications` 🚩 detail "LIVE SINCE
   2026-10-16"; `/chart-maps?tab=gajjala` blurb sentence; the ✨ list shows the 🎯 entry first. DOM scan for NaN /
   undefined / None / the b-word.
7. Cleanup: `docker rm -f cheetah-tmp-ge-api` (that exact name only); stop the preview.

### LIVE proof (after the deploy)

The first in-window A+ — tonight 16:00–20:00 ET if the cron deploy landed before 20:00, else Monday 2026-10-19 from
09:45 ET:

```bash
docker exec cheetah-market-app-mongo-1 mongosh cheetah --quiet --eval 'db.gajjala_alerts.find({_id:/^GG:2026-10-1[69]\|/,state:"pushed"},{_id:1,at:1,result:1}).toArray()'
docker exec cheetah-market-app-mongo-1 mongosh cheetah --quiet --eval 'db.push_history.find({kind:"gajjala_setup"}).sort({_id:-1}).limit(3).toArray()'
```

→ `result.sent ≥ 1`; the bodies start "broke …" and carry the setup's `{ENTRY}` clause;
https://pounce.ajaykandakatla.dev/chart-maps?tab=gajjala&sub=potential → that row "🎯 entry sent HH:MM ET"; /alerts 🚩
row "push calls N", no shadow chip; 🏁 Track record → the row "🎯 A+ entry" and the `entries_text` line. Report LIVE.

## HIS CALL (each ships with the default shown; nothing here is decided for him)

- **Q1 Pre-market A+ entries stay suppressed** (GG: "I don't take trades for the first 15 minutes"; the gate's
  pre-market rule since 2026-10-13) — 1/day on file, counted on that pass's /alerts row, never rung; the 🧠 potential
  still rings from 04:00 (DEFAULT). Alternative: ring pre-market entries with the after-hrs limit-order line.
- **Q2 `default_prefs` True for everyone else** (DECISIONS10 D1) vs `False` (the 🧠 / 🎚️ house precedent; "everyone
  else starts off"). No effect on his phone either way. **ANSWERED — the house way (AMENDMENTS10 F1):** `False` for
  everyone else; his devices ON through `OWNER_KEEP_SET` + `scripts/owner_prefs_apply.py`. DECISIONS10 D1's
  default_prefs clause is withdrawn.
- **Q3 Thin-R entries ring** (R under `LEDGER_MIN_R_PCT` 0.5% of the trigger, e.g. GP 10-16 14:15 R 0.3%) — DEFAULT, no
  new gate; vs hold them back (a new gate).
- **Q4 Live A+ entries in the 🏁 %** (AMENDMENTS10 F3): their own 🎯 line, never pooled with the 🧠 % (DEFAULT) vs pool
  them into one % (biased upward — an A+ exists only once the trade survived its entry bar). A 🧠 potential and its 🎯
  entry stay two rows either way (BUILD_SPEC9 Q13).
- **Q5 The 🏁 chip counts 🧠 rows only** (MINE, unchanged); vs add today's live A+ entries (one more read per build).
- **Q6 The ENTRY_WORDS wording** (MINE, from his rules in verified_rules.json, the table above) — the 🎾 clause has no
  first-hand entry rule on file (RS2 / RS4 are 2+ sources); any clause is edited in one place (`alerts.ENTRY_WORDS`).
- **Q7 `entry_text` only for an entry that was SENT** (DEFAULT, D4) — a found-but-held A+ (pre-market, first 15, late, no
  device) shows nothing on the 🧠 Track row; vs "🎯 A+ HH:MM ET — not sent: <why>".
- **Q8 Once per name, setup and session** (shipped HIS CALL 11) — a second A+ of the same setup later that day never
  rings (DEFAULT).
- **Q9 The first live window**: tonight's 16:00–20:00 if the cron deploy lands before 20:00 ET (DEFAULT on a prompt
  deploy) vs Monday 09:45 (deploy cron after 20:25 tonight).
- **Q10 The ✨ route** `/chart-maps?tab=gajjala` (MINE) and the bar-less tile link carrying the house back-to-tab state
  (`withSource`, MINE — the charted tile's own convention).
- **Q11 Body order** (AMENDMENTS10 F9): numbers first — trigger, stop, then the entry words (DEFAULT; the lock screen
  shows about 180 characters) vs the entry words first.
