# 🧬 Medical catalysts — routine, store, reaction, push (2026-09-29)

**UNMEASURED — setup: pending study.** Nothing here is a buy or sell signal. No entry, stop or target is served anywhere.

## The ask (verbatim)

Ajay, 2026-09-29 00:40 ET:

> "can you add a new routine to scan for https://pounce.ajaykandakatla.dev/sepa/KOD?tab=catalyst amd trails or other medi cal nws and sector them separatively like new fdaapprovals or break throughs like mrnaresearch how to catch thsse sectorsand companiesand add right setup and alerts"

Context: KOD ran +178% on 2026-09-28 (RVOL 57) on its Phase 3 DAYBREAK readout; MRNA rose 29% in the week to 09-25 on its cancer vaccine (ESMO) and the 2026-27 COVID shot clearance.

## Architecture

```
backend/catalysts/medical/
  taxonomy.py   (WP-CLS) labels, families, is_high_impact, event_label, type_dir, UNMEASURED_NOTE
  classify.py   (WP-CLS) the deterministic rule engine — docs/catalysts/medical_classifier.md
  sources.py    Finnhub per-ticker, SEC 8-K EX-99.1, Massive market-wide, FDA press RSS -> articles
  reaction.py   session mapping, base close, liquidity, detection / close / forward blocks (pure)
  store.py      Mongo: articles, events (merge), state, claims
  alerts.py     the med_catalyst gate, wording, claims, send
  board.py      API payloads + the 🔥 roll-up
  routine.py    run_tick (one pass), lease, roster, cursor, budget, CLI
```

One pass (`routine.run_tick`): window check (04:00–20:00 ET) → lease → discovery (EDGAR, Massive, FDA RSS) → the next roster slice from Finnhub → classify, dedupe, store → detection reaction for new events → close / forward fills (Mongo only) → push → `alert_status.record_pass("med_catalyst", …)`.

## Sources and their traps

| Source | Role | Trap |
|---|---|---|
| Finnhub `/company-news` via `finnhub_client.client.company_news` | per-ticker trigger over the medical roster, `FINNHUB_PER_MIN = 20` own pacing on top of the house token bucket | `related` is the ASKED ticker even on other companies' stories — the title must name the company (`news_search.relevance_filter` on the suffix-stripped name, or the classifier's name forms). The KOD 06:30 Yahoo copy of the press release ("Zenkuda and tabirafusp-ted Meet Primary Endpoints…") never names Kodiak in its title and is dropped here; the same release arrives via SEC. |
| SEC EDGAR full-text 8-K + EX-99.1 via `sepa.insider._edgar_get` | market-wide discovery, healthcare SICs only (`HEALTHCARE_SICS`) | Full-text hits boilerplate (VKTX / GRML "clinical hold" inside a credit agreement). Only the EX-99.1 lead is classified, cut at the first forward-looking / safe-harbor marker and at `EXHIBIT_LEAD_CHARS`; no EX-99.1 → skipped for good (`no_exhibit`); a failed fetch → retried next pass. The issuer is the filer (first ticker in `display_names`). Publication time = the filing's `acceptanceDateTime` (KOD: 08:53:56 ET = 12:53:56Z; the EDGAR filing index says "Accepted 2026-09-28 08:53:56"). |
| Massive `v2/reference/news` market-wide, 1 call per pass | discovery (GlobeNewswire PRs) | `tickers[]` carries partners (Elevar's approval is tagged RLAY) — the issuer is the tagged ticker whose name forms are attributed in the title, earliest mention first; none → unresolved. A medical gate runs at ingestion (issuer in `MEDICAL_ISSUERS` or a medical word in the title) — FTAI's aircraft deal and the SAN-tagged SPAC IPO are dropped (`non_medical_dropped`). `insights[]` (provider sentiment) is never read. |
| FDA press-release RSS | discovery / confirmation | The python-requests UA gets a 404 — the browser UA `FDA_RSS_UA` is sent. Only items that yield `fda_approval`, `fda_crl`, `fda_revoked`, `clinical_hold` or `safety` are kept (policy items dropped). The company comes from the release page (≤ 3 page fetches per pass) by the v1 rule `(granted|approved|awarded) to <Company>` matched against the SEC `company_tickers.json` titles; no match → unresolved (shown on the board, never pushed). |

Every stored or logged exception text is `observability.logsetup.redact(f"{type}: {exc}")` — Finnhub `token=` and Massive `apiKey=` ride in request URLs.

Not used in v1: openFDA drugsfda (2–6 days late), ClinicalTrials.gov v2 (months behind; `catalysts/calendar.py` is unchanged), Google / Yahoo RSS.

## Storage

| Collection | `_id` | Notes |
|---|---|---|
| `med_catalyst_articles` | `fh:…` / `sec:…` / `mv:…` / `fda:…` | `$setOnInsert` — a repeat key is `articles_dup`. The same story via another provider (same `TICKER|title key` within ±1 day) is ONE article with an `also_via` entry. |
| `med_catalyst_events` | `{TICKER or UNRESOLVED:slug}|{type_dir}|{session_date}` | e.g. `KOD|topline_positive|2026-09-28`. Merge: same ticker + `type_dir` within `MERGE_SESSIONS = 3` market days (the ±3-day window of the 2026-09-01 8-K study); a `topline_unknown` merges into a topline of any direction; a topline with a trial merges into the same trial + direction at any earlier date; a price story (`from_commentary`) may merge, never create. The key never changes after creation, so the push claim is stable. Phase on merge = the highest; a numbered Phase 3 wins a tie with "pivotal". |
| `med_catalyst_state` | `lease`, `cursor`, `baseline`, `massive_hwm`, `edgar_seen`, `fda_seen`, `sec_tickers` | |
| `med_catalyst_alerts` | `MC:{event_key}`, `MC:{TICKER}|topline|{session}` | `supply_demand.demand_alerts.claim_key` docs |

Never written: `catalysts_cache` (the catalyst paper lane reads it; no lane may consume a medical event).

## Reaction without lookahead

- **Session date**: a market day before its RTH close (13:00 on `HALF_DAYS`) → that day; else the next market day (after hours, weekend, holiday).
- **Base close**: the closed bar of the market day before the session; else the snapshot (`snapshot_day_close` / `snapshot_prev_close`, stamped); else unknown → the push gate fails closed.
- **Liquidity**: only bars dated before the session — `adv50_usd` = median(close × volume) of the last 50, `avg_vol50` = mean volume, `pre_ret_20d_pct`.
- **Live-bar overlay trap**: the price cache carries today's in-progress bar; `reaction.closed_frame` drops a today-dated bar before 16:45 ET and every future bar, so `at_close` exists only once the session's bar is closed.
- **Detection**: one `bulk_live_prices` call per pass for the new events (extended-hours last trade first) — what he could have acted on; `latency_min` = first seen − published.
- **Forward**: `ret_5d_pct` / `ret_21d_pct` vs the base, `drift_5d_pct` vs the session close; filled every pass from Mongo frames for events up to 45 days old.
- KOD check (prod frames): base $32.35, `at_close.day_pct` +178.0%, RVOL 57.1, ADV $22.7M.

## The push gate (`med_catalyst`)

See `docs/notifications/med_catalyst.md`. In order: not high impact → unresolved ticker → baseline → recap (21 sessions) → closed day (checked BEFORE any claim) → stale (regular-session minutes since publication > 10) → unknown liquidity → price < $2 → 50-session median $ volume < $5M → one topline claim per name per session → one claim per event → send.

## Schedule — no crontab line

The pass rides `*/5 4-19 * * 1-5 /usr/local/bin/python -m catalysts.promo_live` (`backend/crontab:459`). `promo_live.__main__` runs `check_alerts()`, `warm_zones()`, then `_run_medical_hook()` inside a `finally` — a raising promo pass no longer skips the medical pass, and its exception still propagates afterwards (the JSON result line prints before the traceback).

**The supercronic overlap trap**: supercronic runs WITHOUT `-overlapping`, so a job still running at its next tick makes that tick SKIP. The hook is bounded: `HOOK_BUDGET_SEC = 150`; every network await goes through `routine._call` = `asyncio.wait_for(min(CALL_CAP_SEC = 20, remaining))`; a call never starts with less than `CALL_MIN_SEC = 3` left; a timed-out leg stops for the pass (the next pass resumes from the cursor); the two sync calls (`bulk_live_prices`, `load_prices`, 15 s timeouts) start only with `SYNC_RESERVE_SEC = 20` left. Worst tick ≈ promo 59 s + 150 + 15 < 300 s. No thread (a daemon thread dies with `__main__`; a non-daemon one holds the process past the tick). One `asyncio.run` per process.

Roster: full universe ∩ `companies` (sector Healthcare, industry ∈ `MEDICAL_INDUSTRIES`) ∪ `THEME_UNIVERSE['biotech']` (362 names on 2026-09-29); holdings + Signals watchlist first, then the biotech theme, then the rest. `SLICE_MAX = 36` names per pass → a full lap in ~10 passes (~50 minutes). The cursor restarts at 0 on the first pass of each ET day (the 04:00 morning sweep).

Weekend / holiday news is not scanned until Monday 04:00 (the host line is 1-5); the 96-hour lookback catches it and the push fires Monday pre-market (0 regular-session minutes since publication).

## API

- `GET /catalysts/medical?days=30&type=&modality=&area=&high_only=` → `board.board_payload` (declared ABOVE `/catalysts/{ticker}` — below it `deep_dive` would serve it).
- `GET /catalysts/medical/{symbol}?days=180` → `board.symbol_payload`.

Both carry `labels = {measured: false, status: "unmeasured", setup: "pending study", note}`. The 🔥 roll-up (`by_modality`, `by_area`) is descriptive: medians of the day / 5-session / 21-session moves with ONE observation per (ticker, session) per group, `small_n` when fewer than 5 unique tickers, an event with two areas counted once in each.

## UI (WP-FE, spec §3.11)

Chart Maps ▸ Catalysts ▸ 🧬 Medical (`/chart-maps?tab=catalysts&sub=medical`): family chips, modality / area selects, High-impact-only, 7/30/90 days, the 🔥 roll-up (By modality / By area), one section per family. The ticker page's Catalyst tab (`/sepa/{SYM}?tab=catalyst`) lists that name's events. Both render the served UNMEASURED note and "Setup: pending study".

## Verification

```bash
cd backend
.venv/bin/python -m pytest tests/test_med_sources.py tests/test_med_reaction.py tests/test_med_store.py tests/test_med_alerts.py tests/test_med_routine.py tests/test_med_api.py -q -p no:cacheprovider
python -m catalysts.medical.routine --no-push --budget 900
python -m catalysts.medical.routine --explain KOD
```

`--dry-run` still stores articles and events (it is a scan) but claims nothing, sends nothing, stamps no push state and writes no pass doc. `--explain SYM` prints each event's gate reason and the exact title / body the phone would get.

## The follow-up study that will choose "the right setup" (sketch, not built)

Pre-registration first (`docs/catalysts/medical_setup_study_prereg.md`, hypotheses, setups, stats, verdict rule, the `classify.py` SHA) before any outcome is joined. Event spine 2023-10-01 → 2026-08-31 from EDGAR 8-K EX-99.1 over a survivorship-free healthcare-SIC roster (delisted names included) plus Massive news; the same `classify()` at the pinned `RULES_VERSION`; ≤ 3 long-only setup SHAPES (day-2 open after a high-impact positive; buy the close of a strong event session; negatives as an AVOID read). No stop, exit or entry threshold is proposed — HIS CALL #9. Outcomes with expectancy and the stop-out rate beside the win rate; same-ticker placebo sessions and industry twins; bootstrap clustered by ticker; hold-out 2026-03-01 → 2026-08-31. Prior (8-K study, board-growth study): expect `no_signal`.

## HIS CALL (never decided by the build)

1. 🧬 push on your phone — ships ON for you (`OWNER_KEEP_SET`), off for everyone else. Alternative: OFF.
2. Push floors — $2 (`MIN_SHARE_PRICE`) and $5M/day median (`THIN_DOLLAR_VOL`), no cap floor. Alternatives: $20M (`MIN_DOLLAR_VOL`) and/or $700M cap (`MIN_CAP_USD`).
3. What rings — FDA approval (not tentative/generic), CRL / refuse-to-file / rejection, Phase 3 / pivotal topline positive or negative, Breakthrough Therapy, clinical hold placed.
4. Schedule — rides promo_live (no weekend passes, last pass 19:55). Alternative: a host crontab line you install: `2-57/5 4-19 * * * /usr/local/bin/python -m catalysts.medical.routine` (the lease stops double runs).
5. Local-model assist for `unclassified` headlines — not built.
6. Placement — Chart Maps ▸ Catalysts ▸ 🧬 Medical. Alternative: its own Chart Maps tab.
7. Freshness cap — 10 regular-session minutes. Alternatives: 30 / 60 minutes.
8. Recap guard — 21 sessions. Alternative: only the 3-session merge window.
9. The study's stop / exit / entry rules and roster.
10. (build question) The FDA-page company rule is the v1 regex `(granted|approved|awarded) to <Company>`. FDA releases often read "granted approval of <drug> to <Company>", which that rule does not match → the event stays unresolved (board only, never pushed). Widening the pattern is your call.
11. Device clearances (510(k) / "FDA Clears …") count as high impact under the §3.8 table (only tentative / generic approvals are excluded) — QGEN's bloodstream-panel clearance would ring. Alternative: drop `device_clearance` from high impact.
12. Two different approvals of the same type on one name within ±3 sessions (`MERGE_SESSIONS`) collapse into one event (LLY), and the 21-session recap guard then keeps a second one off the phone. Alternative: split by product name.
13. Recall gap, not widened: "Misses Primary Goal" / "Misses Main Endpoint" give no topline (the NEG rule needs *primary … endpoint*).

## Fix round 2026-09-29 (critic findings)

- **Classifier landed** (`taxonomy.py`, `classify.py`, `__init__.py`; `tests/test_med_classify.py` over `tests/fixtures/medical/headlines.json`, 137 labelled rows + 18 attribution rows; see `docs/catalysts/medical_classifier.md`). Replaying the 710 articles the live pass stored through it: 51 events, 10 high impact (KOD Ph3 +, MIRM Ph3 +, MRK Ph2/3 +, FDA approvals ABBV / INCY / LLY / MIRM / MRK / QGEN, MCT8 unresolved); the stand-in's false highs (Charles River "(CRL)", PRME IND, LNTH / MRK valuation pieces) are gone.
- **Keys out of the cron log**: `promo_live.__main__` and `routine.main` call `observability.logsetup.install_redaction()` right after `logging.basicConfig` — httpx logs every request URL (Finnhub `token=`, Massive `apiKey=`) at INFO and supercronic ships job output to `docker logs cheetah-market-app-cron-1`.
- **An impact upgrade re-arms the push**: when a merge lifts an event to high impact (a no-phase price story first, the Phase 3 release later) and its push says `not_high_impact`, it goes back to `pending`; the `stale` gate still guards lateness. No other push state is ever re-armed.
- **Session date = the earliest article's session**: the pass classifies its queue OLDEST first, and a merge whose earliest publication maps to an earlier session moves the event there (same `_id`, the push claim stays stable) and nulls its reaction so the fill recomputes base / liquidity / close on the right day (ABBV 09-28 04:02 was keyed 09-29).
- **KOD 8-K time**: accepted **08:53:56 ET** (12:53:56Z — the EDGAR filing index says "Accepted 2026-09-28 08:53:56"); the fixture is now the real submissions JSON and the KOD replay runs at 09:00 ET, after the 8-K and before the open.
