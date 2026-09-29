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

## 2026-09-29 — fix round 3: SHADOW mode (verdict SHIP-SHADOW)

An independent out-of-sample grade on real Finnhub news 2026-06-01..08-15 (80 random healthcare
names) gave strict push precision 0.56 [0.34, 0.75]. The kind now ships in **shadow**:
`catalysts/medical/alerts.SHADOW = True`. Every pass runs the full gate and the same claims
(under the `SHADOW:` prefix, so "once per event / one topline per trial per session" behave as
live), stamps a would-push event `push.state = "shadow"` with a `would_push` record
(`{value, reason, mode, title}`; blocked events get `value: false` and the gate reason), counts
`shadow` and `shadow_mode` on the pass doc, and **never calls the sender**. /alerts shows
`🧬 shadow — nothing is sent` and `🧬 shadow — N would have pushed`. Flipping the switch to False
(Ajay's word only) sends through the identical gate, once per event; an event already stamped
`shadow` is not pending and never rings late. Gate changes in the same round: the repeat block
skips a trial readout whose subject keys (trial acronym / NCT id / drug code / drug name) are
disjoint from the earlier one's, and blocks the SAME trial / drug at any earlier stored date
(`REHASH_SESSIONS = None`, HIS CALL); the stale gate counts regular-session minutes from the
EVENT's first sighting (its own earliest publication and every same-subject, same-kind stored
event), not the newest article. `taxonomy.PUSH_MATERIAL_ONLY` (default False = today's
behaviour, HIS CALL) drops device clearances, dosing / label updates, generic-type formulations
and biosimilars from high impact when switched on — it also drops genuine device clearances.

## 2026-09-29 — fix round 4 (still SHADOW; nothing tuned on the fresh OOS set)

Gate: the repeat block and the stale gate's event lineage use `store.different_story` /
`store.same_subject` — two trials that share only a drug name (ATTAIN-1 / ATTAIN-2) are neither a
recap nor one story's age; FDA approvals of different products split the same way. The topline claim
is made on the event's IDENTITY keys (trial keys, else drug keys) and also yields to any claim in the
same name + session slot that is not a different story (one readout phrased by drug and by trial rings
once). An FDA approval and an FDA acceptance of the SAME drug's NDA / BLA on the same name within
`store.MERGE_SESSIONS` cannot both be new: the approval is stamped `contradicted` and is low impact
(`taxonomy.is_high_impact`), in either arrival order; an approval already sent stays sent. Finnhub
headlines that name only one of the issuer's OWN stored subject keys (a key no other name carries,
capitalised) are kept (`via_subject`) and attributed with that key as an issuer form, rival guards
intact. /alerts: `🧬 shadow — N would have pushed this pass` plus `🧬 shadow — N would have pushed
this session` (`shadow_session`, counted from the stored `push.state = "shadow"` events — the pass
doc is replaced every 5 minutes). Not changed (his call): the 10-minute stale gate on a 55-minute
Finnhub lap; `shadow` in `PUSHED_LIKE` after the switch goes live.
