# 🧬 `med_catalyst` — the medical-catalyst push (2026-09-29)

Ajay, 2026-09-29: "…sector them separatively like new fdaapprovals or break throughs like mrnaresearch how to catch thsse sectorsand companiesand add right setup and alerts".

**UNMEASURED.** A push says what happened, never "buy". Positive kinds end `UNMEASURED, not a buy signal`; negative kinds (CRL, Phase 3 negative, clinical hold) end `UNMEASURED, not a sell signal`. No entry, stop or target is ever sent — setup: pending study.

## Who gets it

- **ON for Ajay's phone** — `med_catalyst` is in `push.subs.OWNER_KEEP_SET` (the `key_level_alert` precedent), because he asked for alerts.
- **OFF for everyone else** — `default_prefs()["med_catalyst"] is False`. It must stay in `default_prefs`: a kind missing there targets zero devices and renders no toggle.
- His already-registered phones keep their stored prefs until `scripts/owner_prefs_apply.py` runs after the promote (a prod data write, main session only). `OWNER_KEEP_SET` alone only covers a device that registers again (the `price_alert` 2026-09-21 precedent).
- **Turning it off (HIS CALL #1)**: one toggle at /notifications, or drop `"med_catalyst"` from `OWNER_KEEP_SET` (then the Notifications entry and the Essentials preset flip to OFF BY DEFAULT — the contract checks both).

It is a MARKET kind (`market_hours.gate.MARKET_ALERT_KINDS`): nothing rings on a weekend or an NYSE holiday. `push.recent.DIGEST_KINDS` carries it (its digest body lists names). The wrapper is `push.hooks.notify_med_catalyst(owner=, payload=)` → `sender.send_to_user(owner, payload, kind="med_catalyst")`, so quiet hours and the pref toggle apply at the sender.

## What rings (`taxonomy.is_high_impact` — the only definition)

| Type | Rings when |
|---|---|
| FDA approval | not tentative / generic, regulator FDA |
| FDA rejection | complete response letter, refuse-to-file, rejection (a withdrawn application does NOT ring) |
| Topline | Phase 3 / 2-3 / pivotal AND clearly positive or clearly negative |
| Designation | Breakthrough Therapy only |
| Clinical hold | placed (full or partial) |

Never rings: Phase 1–2 results, mixed results (every secondary-endpoint miss is "mixed"), undirected toplines, pulled / revoked approvals, Breakthrough Device, Fast Track, orphan, PDUFA dates, filings, advisory-committee votes, conference data, scheduled readouts, trial starts / halts, deals, offerings, ex-US approvals. They all stay on the board.

## The gate, in plain words (catalysts/medical/alerts.py)

1. Not one of the kinds above → board only.
2. No resolved ticker (an FDA release naming a private company; a Massive story tagged only with a partner) → board only.
3. **Baseline**: until the routine has read every roster name once (~50 minutes after the first deploy), and on each discovery feed's first run, and for a roster name's first-ever fetch, events are recorded, never rung — otherwise a 96-hour backlog would ring at once.
4. **Recap guard (HIS CALL #8)**: the same name already rang (or was muted / baselined) for the same kind within the last 21 sessions → board only. This also holds back a genuine second approval (another drug) inside 21 sessions.
5. **Closed day**: checked BEFORE any claim — the event stays pending and is re-checked on the next trading-day pass (weekend news rings Monday pre-market).
6. **Freshness cap (HIS CALL #7)**: only while the regular session has traded the news for at most 10 minutes (two 5-minute passes). Pre-market and after-hours news qualifies until the open. A 06:00 release seen at 09:20 rings; seen at 13:00 it does not. Tail-of-roster names whose news only the Finnhub lap finds rarely ring during RTH; the discovery feeds (SEC, Massive) are read every pass.
7. Base close unknown or ADV unknown → blocked (fails closed).
8. Prior close under **$2** (`trading.safety_floor.MIN_SHARE_PRICE`) → blocked.
9. 50-session median dollar volume under **$5M** (`trading.safety_floor.THIN_DOLLAR_VOL`) → blocked (HIS CALL #2).
10. **One topline push per name per session**: claim `MC:{TICKER}|topline|{session}` — a contradictory second topline on the same name and session can never ring.
11. **Once per event**: claim `MC:{event_key}`.

Send outcome: a transport failure releases both claims (retried next pass); delivered → `pushed`; nobody targeted (pref off, quiet hours, no device) → `muted` and the claims are KEPT — house semantics: an event that lands in quiet hours never rings later.

Three events ring individually per pass; the rest go in one digest.

## Wording (exact, pinned by tests)

- Title: `🧬 {SYM} · {event label} · {area} · {move vs prior close at detection} · UNMEASURED, not a buy signal`
  — KOD 2026-09-28: `🧬 KOD · Phase 3 topline positive · ophthalmology · +72% · UNMEASURED, not a buy signal` (the pre-market print; the +178% is the close).
- Body: `{company} · {trial or —} · vs ${base} prior close, {session} print ${price} at HH:MM ET · first seen HH:MM ET via {provider} ({n} sources)`.
- Opens `/sepa/{SYM}?tab=catalyst`. Digest: `🧬 {n} more medical catalysts`, up to 6 lines `{SYM} · {label} · {move}`, then `+k more on Chart Maps ▸ Catalysts ▸ 🧬 Medical`, opening `/chart-maps?tab=catalysts&sub=medical`.

## /alerts

`supply_demand.alert_status` records a `med_catalyst` pass doc every pass (`cadence_sec` 300 — derived from promo_live's `*/5` crontab minute field by `test_cadence_sec_matches_the_crontab`), with the counters (roster, sliced, events_new, high_impact, pushed, muted, stale, recap, blocked_price, blocked_dollar_vol, closed_day, baseline, budget_exhausted, call_timeouts…), so the page can say why the phone was quiet.

The ℹ️ rules panel carries one 🧬 line built from the enforcing constants (`supply_demand/rules_info.py`, right after the 📣 line).
