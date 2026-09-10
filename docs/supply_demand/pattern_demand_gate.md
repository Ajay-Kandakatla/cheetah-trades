# 📐 Chart-pattern pushes must be AT a demand level

Ajay, 2026-09-09:

> Also on the Patterns you know the deal, we need make sure they need to be in
> demand zone or bouncing off demand zone.

and, the same day:

> Instead of bounce use the word reversal from Demand zone or something I have
> trauma with that word now cuz I caught falliing knives with it.

## What changed

`patterns/pattern_alerts.check_once` gained one gate, run **after** the dedupe
(so a name already pushed never pays for a zone build) and **before** the
singles/digest split (so the split only ever sees names that passed).

A confirmation reaches the phone only when the name is standing at a level:

| state       | rule                                                                                       | source                        |
|-------------|--------------------------------------------------------------------------------------------|-------------------------------|
| `in_zone`   | the print sits inside an eligible demand band                                                | `bounce_room.in_demand_read`  |
| `reversal`  | a session low in the last 5 touched such a band, the print is now ≥ max(3%, 1 ATR) above that low, **and** ≤ 5% above the band top | `bounce_room.bounce_read` + `NEAR_MAX_PCT` |

"Eligible" is the one definition the whole app already uses
(`zone_bounce_alerts.is_eligible`): demand bands always, supply bands only once
**broken** (top under yesterday's close), and never on a gap day
(`alert_gates.gap_day`, the DYN 2026-09-08 rule).

### Nothing here is a new number

Both reads are the ones already behind the 🪃 SEPA chip, the Back-in-Demand
sort and the Catalysts sort. The one bound that had to be *chosen* — how far
above a band still counts as standing at it — is
`quick_bounce.NEAR_MAX_PCT` (5%), the Quick Reversal board's own live rule,
pinned equal in `tests/test_supply_demand_contracts.py`. If one moves the other
must move with it, or "at demand" means two things again.

### Why the ceiling exists

`bounce_room.bounce_read` deliberately has **no** upper bound: it powers
FILTERS, where a name that touched a band and ran is still a true answer. A
push is not a filter. The first dry run of this gate passed **SIG** at **+28%
above** the band it last touched — the exact "late by the time it reaches me"
alert the demand kinds already guard with `ALERT_MAX_ABOVE_DEMAND_PCT`.

### It fails closed, and says which kind of quiet it is

| counter             | meaning                                                        |
|---------------------|----------------------------------------------------------------|
| `skipped_no_zone`   | no zone coverage anywhere, and none buildable → **silence**     |
| `skipped_no_demand` | covered, and simply not at a level                              |
| `skipped_dup`       | the scan carried the identical row twice (real: HGBL 2026-09-09)|

Two counters, not one, so a **blind** morning can never be mistaken for a
**quiet** one. Missing coverage is built on demand
(`bounce_room.default_builder`, capped at `MAX_ZONE_BUILDS = 40`); anything past
the cap stays quiet and is logged.

### The reference price

Pre-market — and the cron runs at **08:15 ET** — `prices.bulk_snapshot` is
empty. The first dry run therefore failed **every** name closed, on a plumbing
detail rather than on structure. The scan row's own `last_close` (the close the
pattern confirmed on) is the fallback; a live print still wins when there is one.

## Measured on the live scan, 2026-09-09

    200 scan rows
    → 188 not fresh/confirmed
    →  12 fresh confirmations
    →   1 duplicate row
    →   4 not at a level  (SIG +28%, ABM ×2, TK — all already ran)
    →   7 pushed          (4 singles + a digest of 3)

Re-runnable: `scratchpad/gate_dry.py` shape — `PA._demand_pass(fresh, now=now)`
against `patterns_scan._id="latest"`.

## What did NOT change

This gate does not make the patterns work. His own ledger, 669 resolved
observations graded 21 sessions forward: cup-with-handle 45% (n=434), double
bottom 43% (n=248), triple bottom 37% (n=68), inverse H&S 10% (n=10), against a
**50% placebo**. **Not one beats chance.** Every push still carries its own rate
next to the placebo and the words "does NOT beat chance"; contract tests fail if
either is dropped. The demand gate says *where* a name is standing, not that the
pattern has an edge.

## The wording

`approach_read` now returns `tag: "↑ reversal off"` and
`text: "↑ reversal off the band, …"`; `zone_bounce_alerts` says
"reversed +6.3% off demand" and "Reversal off demand levels"; the SEPA chip is
"🪃 Reversal from Demand"; the Chart Maps tab is "🪃 Quick Reversal"; the Alerts
page skip line reads "no reversal off demand".

**Display only.** The internal `dir` value stays `"bouncing"` — it is what
`PUSH_DIRECTIONS`, `direction_gate`, the board tones and the stored dedupe keys
all match on, and two names for one state is how a gate drifts. The rules panel
renders the phone rule through `alert_gates.direction_label` so the panel can
never re-type the old word behind our backs. Pinned by
`test_no_push_title_or_chip_says_bounce_to_him` and
`test_the_rules_panel_renders_the_phone_rule_through_the_label_map`.
