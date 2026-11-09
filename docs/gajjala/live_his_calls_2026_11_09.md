# ⏱ Gajjala LIVE stack — HIS CALL list (2026-11-09), verbatim from the design spec §7

Ajay 2026-11-09: "I would like the autopilot to be continously monitored or live tracked and changed as if Gallalas
makes the trades can you modify and make it more live with websockets or something else where there is a low latency
monitoring on the prices action changes please? same for reuglar Gajjlas tab as well need it to be more live" ·
"I only need this setup for myself the owner of the app.. May be not for others if it permits only one person" ·
"This is becuz we had trouble with the key in the past" · "It was updated after that already continue the build".

Shipped on main `b63f3003` + `6aaf5e36`, deployed api + frontend + cron 02:29 ET 2026-11-09 (before the 04:00
pre-market). **Nothing rings differently:** no gate, rule, threshold, push mode, `OWNER_KEEP_SET` or broker switch
changed; the GG5 goldens are byte-identical; the paper lane still trades 🚩 A+ pushed claims only, paper only.

## Built defaults (every one of them is a HIS CALL below — none decided here)

| Knob | Built | Where |
|---|---|---|
| `GG_STREAM_MODE` | `"shadow"` at the 02:29 ET deploy → **`"live"` since ~10:00 ET 2026-11-09 (his word, #1 below)** — a market order on the first regular print at/over the trigger; env can only lower | `trading/gajjala_stream.py`, `docs/trading_gajjala_lane.md` |
| `GAJJALA_BAR_CLOSE_MODE` | `"probe"` — a detached child reads every listed name at close + settle and again +60 s for `GAJJALA_BAR_FINAL_PROBE_SESSIONS` 5 sessions, then stops (`probe_complete`); the `:x1` pass is unchanged | `chart_maps/gajjala/bar_close.py`, `docs/gajjala/bar_close_pass_2026_11_09.md` |
| `BAR_SETTLE_SEC` | unchanged | `chart_maps/gajjala/constants.py` |
| `live_hub.PRINT_KINDS` | `("regular",)` — includes odd lots and Form T | `live_hub.py` |
| `MASSIVE_WS_KICK_COOLDOWN_SEC` | 30 s (= today's wait; never adds one); yield guard OFF | `live_feed.py`, `docs/realtime/massive_ws_feed.md` |
| `gajjala.update` SSE | owner-only interest; the 30 s card poll stays as the bar splice + fallback | `chart_maps/gajjala/live_events.py`, `docs/gajjala/live_tab_2026_11_09.md` |
| Feed word | `/alerts` always; boards and lane tab only when degraded | `pages/Alerts.tsx`, `GajjalaBoard.tsx`, `GajjalaLaneTab.tsx` |
| `latency.GG_LIVE_FROM` | `"2026-11-09"` — the deploy date; the ⏱ ledger splits before / since there | `chart_maps/gajjala/latency.py`, `docs/gajjala/latency_ledger_2026_11_09.md` |
| dev compose | `MASSIVE_WS_ENABLED=false` — a dev api never opens the second socket that kicks prod | `docker-compose.dev.yml` |
| `scripts/live_feed_canary.py` | written, NEVER run without his word (#10) | `backend/scripts/` |

Measured BEFORE (n 47 pushed live `GG:` A+ since 2026-10-01, p50 seconds after the 5-minute bar closed):
Read 61.0 · Rang 70.6 · Lane saw 122.0 · Ordered 124.0 · Filled 127.0 (`scripts/gajjala_latency_report.py --span all`).

## HIS CALL (never decided here; built default named)

1. **Stream entries LIVE?** Order on the first qualifying print at/over the trigger (sub-second) instead of the next
   minute tick. Built: SHADOW. **ANSWERED 2026-11-09 ~09:25 ET** — Ajay: "to do entries I would like to see it in action
   now" / "With entries realtime like Gajjala does" → `GG_STREAM_MODE = "live"`, deployed api the same morning. Read with
   the ⏱ stream-vs-minute table.
2. **Which prints count as "the tape traded the trigger"** (lane AND screen, `live_hub.PRINT_KINDS`). Built:
   `"regular"` = includes odd lots (37) and Form T (12). Options: exclude odd lots (`trigger_lot` rows already record
   that variant); + `auction_open` / `auction_reopen`. The ⏱ serves the odd-lot-only trigger count.
3. **Intrabar vs closed-bar lane entry.** Keep closed: the lane trades only the pushed A+ (bar CLOSED through the
   trigger); P1 changes only how fast the lane reacts after that. Confirm.
4. **Extended-hours lane** (open since 10-21): unchanged — regular hours, 09:45–15:30.
5. **P2 early pass ON?** Built: `probe` (finality measured 5 sessions, pass stays at `:x1`). `on` = the pass at close +
   30 s (≈ 30 s off every ring and lane entry), only after the "Bar finality" line.
6. **`BAR_SETTLE_SEC` 30 s** (the closed-bar definition). Built: unchanged.
7. **Where P2 runs.** Built: cron container, detached child per slot. Alternatives: api-scheduled subprocess; a new
   long-running service.
8. **Where P1 places orders.** Built: in the api (hub worker, same lane code, same gates, paper only, lane-run mutex
   shared with the cron tick). Alternative: api records, a cron-container runner orders (+~1 s, a long-running runner).
9. **Discovery cadence.** The whole-market snapshot + scanner stays inside the 5-minute pass.
10. **Post-kick policy + canary.** `MASSIVE_WS_KICK_COOLDOWN_SEC` stays 30 s; fast reclaim (~1 s) once he confirms the
    second client is not his; the yield guard numbers (built OFF); may the canary run on a closed window (≤ 2 deliberate
    kicks of the api, each < 30 s); may the 600 s cooldown test run for one closed-day hour.
11. **Second-client suspects he can check:** (a) Massive dashboard → API keys / active connections (every key on the
    account shares the ONE stocks connection); (b) any device, app, notebook, charting tool or person with the key;
    (c) the key printed in plaintext 2026-09-12 (rotated since, his word 11-09) and again in this session's output
    2026-11-09; (d) any other machine running a cheetah checkout or the dev compose; (e) what started 2026-11-08
    ~11:00 ET. Also: our own-drop reconnect → the canary's measured need.
12. **Rotate the stocks key** if the client cannot be found (his dashboard step; then `backend/.env` →
    `./deploy-cheetah-main.sh api cron`).
13. **Plan check.** If `lag_ms_p50` ≈ 900 s: Advanced $199/mo (+$120/mo) — or stop here. If real-time, nothing to buy.
14. **Latency targets.** Proposed: Rang p50 ≤ 40 s after close (now 70.6; needs #5 on); lane order ≤ ring + 2 s (now
    +53.4; needs #1); a waiting doc ordered ≤ 1 s after the first qualifying print (now up to 60 s; needs #1); a finished
    pass on the tab ≤ 2 s (now 0–300 s); card price ≤ 2 s old while live (now ≤ 30 s).
15. **The 30 s card poll** stays as the bar splice + fallback (built) vs stretched while the stream is live.
16. **Household broadcast** of `gajjala.update` (public prices + data-free nudges) to every signed-in tab — OK?
    (Built owner-only, his 11-09 word: "I only need this setup for myself the owner of the app".)
17. **Bar-close lane management** (breakeven / trail / partial at close + 30 s by the hub, LIVE only) — part of #1 or
    its own switch.
18. **Hot mini-pass** for armed 🧠 names before the full pass — partial context; could ring what the full pass would not.
    Not built.
19. **Feed word placement:** /alerts always; boards and lane tab only when degraded (built).

## Served fact found at the deploy check (02:35 ET 11-09), not changed by me

`trading_config.gajjala_floors = true`, `updated_at 2026-11-08T11:01:33Z` (06:01 ET Sunday) — the lane serves
"House safety floors ON for this lane (your switch): share price ≥ $2.00 and a known market cap ≥ $700M. Most of his
names sit under them, so most alerts are skipped and counted." His 2026-10-21 call (HIS CALL #0 in
`docs/trading_gajjala_lane.md`) turned them OFF; HUHU filled at $0.45 on 11-05 with them off. The only writer is
`POST /trading/config` (the dashboard switch). Flipping it back is his: `POST /trading/config {"gajjala_floors": false}`
or the switch on the Auto-Pilot dashboard. With them ON the lane will skip nearly every 🚩 A+ regardless of the live stack.

The design spec and its critique are kept at `eod-audits/research/2026-11-09_gajjala_live/` (spec.md, critique.md).
