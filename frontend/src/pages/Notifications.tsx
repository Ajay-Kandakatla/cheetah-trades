/* Notifications settings — manage every registered push device + every
   notification category. One row per device (iPhone PWA, Mac native app,
   Android PWA, etc.) with toggles per category, quiet hours, test push,
   and unsubscribe.

   Replaced the old single-device manager. The hook does optimistic
   updates so toggles feel instant — they revert only if the server fails.
*/
import { useState } from 'react';
import { useNotificationPrefs, type DeviceRow, type NotificationPrefs } from '../hooks/useNotificationPrefs';
import { subscribePush, pushSupported, isStandalone } from '../lib/pushSubscribe';
import { useCurrentUser } from '../hooks/useUser';
import { useAlertSettings } from '../hooks/useAlertSettings';
import { InstallToHomeScreen, clearInstallDismissal, isIPhone } from '../components/InstallToHomeScreen';
import { PushHistoryPanel } from '../components/PushHistoryPanel';

/* ── Category catalogue — keys match backend default_prefs() ─────────── */
type CategoryDef = {
  key:    keyof NotificationPrefs;
  label:  string;
  detail: string;
  group:  'trading' | 'household' | 'admin';
  emoji:  string;
};

export const CATEGORIES: CategoryDef[] = [
  // Trading alerts pared to the essentials (Ajay 2026-06-13). The breakout /
  // momentum / new-candidate / stage-breakdown / product-launch / tape-watch /
  // morning-brief pushes were retired here AND hard-stopped server-side
  // (backend/push/subs.py DISABLED_ALERT_KINDS — they can't fire even for a
  // device that still has an old toggle on).
  // price_alert was PAUSED here 2026-06-13 and returned 2026-09-21 ("Yes to all..") — see its entry.
  { key: 'pivot_alert', label: 'Buyable / Enter-zone alerts', emoji: '🎯', group: 'trading',
    detail: 'At-the-pivot (buyable names only) and approaching-pivot buy-stop alerts from the 5-min market-hours cron. Once per name per kind per day.' },
  { key: 'position_alert', label: 'Portfolio alerts', emoji: '💼', group: 'trading',
    detail: 'Stop / target hit on the positions you hold — the up/down moves on your portfolio that need action.' },
  { key: 'price_alert', label: 'Price alerts', emoji: '🔔', group: 'trading',
    detail: 'ON BY DEFAULT for you since 2026-09-21 — asked "Price alerts are retired in the push switch and off in your Notifications, so even a real crossing will not reach your phone. Turn them back on?", you said "Yes to all..". '
      + 'WHAT FIRES: a rule YOU set on a ticker page — a level (above / below a price) or a percent move — when the live print crosses its line. '
      + 'It fires ONCE per crossing and re-arms only when price crosses back over the line (shipped 2026-09-21); a price that just sits past the line never rings again. '
      + 'The percent kinds measure from the price on the day you set the alert, and the message says so ("vs $… when you set it", with that date). '
      + 'Paused 2026-06-13 with the retired market-scan kinds; turned back on 2026-09-21 at your ask. It is in the owner keep-set, so a re-registered device cannot quietly mute it. '
      + 'Turning it on widened WHICH KINDS reach you — it did not loosen what a rule needs to fire. Not a signal: a line you drew.' },
  { key: 'promo_alert', label: 'Promo-circuit movers', emoji: '🎪', group: 'trading',
    detail: 'A name tagged by the caught pump accounts moves ±8% vs the prior close — pre-market, regular and after-hours. Once per direction per day. The tag is the promotion: a do-not-chase radar.' },
  { key: 'demand_alert', label: 'Reversal at demand', emoji: '🧲', group: 'trading',
    detail: 'ONLY A REVERSAL REACHES YOU (since 2026-09-09): the day\'s low touched the band and price is already lifting off it. Falling into, settling into, reclaiming from below and resting inside all still LIST on the boards and send nothing. On top of that: not a falling knife, the turn\u2019s mood bullish, and the band floor never pierced. A $1B+ name from the demand board ARRIVES inside, or within 1% of, a tested demand band today (yesterday it closed outside) — one push per band per day — plus one digest per 5-min check of names newly 1–3% above a band and falling. Names that have been sitting in a band are the board\'s business, not a buzz. Gabbar-level names get the same "nearing" tier under Buyable alerts. Unknown market cap is skipped. Phone gate (Ajay 2026-09-05: \"Need only alerts on stocks that have atleast 5% to Supply and also <1% bounce from demand zone\"): the push fires only when the first band overhead is at least 5% above the print (nothing overhead passes) and the print sits between the band floor and 1% above its top; the boards still list every name.' },
  { key: 'growth_demand_alert', label: 'Explosive growth at demand', emoji: '\u{1F680}', group: 'trading',
    detail: 'ON BY DEFAULT for you since 2026-09-20 (same words: "Default on for any change of todays features Bondes or Potus or explosive growth or Earnings I wanna see all of them."). '
      + 'A name from the \u{1F680} Explosive Growth board \u2014 sales up 100%+ AND quarterly EPS up 100%+ year-over-year, with the quarter before it also growing \u2014 is INSIDE a tested demand band whose floor has never been pierced. You asked for this separately from regular supply and demand: \"I wanna know when ever these are in demand, separately just trackers.\" THE BOARD HAS NO MARKET-CAP FLOOR (your call, \"remove the 700M rule for this page\"), but the PUSH still passes your 2026-09-05 standing gates \u2014 at least 5% of room to the first band overhead, and the print between the band floor and 1% above its top \u2014 because a 100% sales grower with 2% of room is still a bad entry. The third gate is `intact`, the only one that ever measured (+8.6pp win rate over 31,861 events); an order block is carried in the body as a DISPLAY note and gates nothing, because the ICT study measured +0.03R over 6,004 signals. A name the trading engine will REFUSE to buy (under $2 a share, or a known cap under $700M) still reaches you \u2014 labelled \u26D4 in the push body rather than silently dropped. One push per symbol per band per day; 4 ring individually, the rest share a digest. THE 100/100 SCREEN WAS MEASURED 2026-09-21 \u2014 a lean, not a finding; the \u{1F680} board carries the numbers. Treat it as a watchlist ping.' },
  { key: 'hot_pullback_alert', label: 'Hot Pullback', emoji: '🔥', group: 'trading',
    detail: 'A name that had been HOT takes one hard flush into a tested demand band and turns the same day — pushed at 08:15 ET from the CLOSED session recorded the evening before, never a live re-scan (mid-day the board repaints). One push per name per signal day; 4 ring individually, the rest share a digest. HONEST RECORD, and the push repeats it: 51.8% win over 83 trades on 50 dates, expectancy +0.10R with a 95% interval of −0.19R to +0.41R that INCLUDES ZERO, and no gate inside the rule separates (the demand band itself measures p=0.198). You asked for this as a watchlist ping after seeing those numbers — treat it as one. The edge, such as it is, is gone by day 5.' },
  { key: 'pattern_alert', label: 'Chart patterns', emoji: '📐', group: 'trading',
    detail: 'A named bullish reversal pattern CONFIRMS on the daily frame — cup-with-handle, double bottom, triple bottom, inverse head-and-shoulders — pushed at 08:15 ET off the 17:05 scan. One push per symbol per pattern per confirmation day (the scan can carry the same row twice \u2014 that is one push, not two). AND IT MUST BE AT A LEVEL: the name is either standing INSIDE a demand band (or a broken-supply shelf now acting as support) or reversing off one \u2014 a session low in the last 5 touched it, price is now at least 3% / one ATR above the low, and no more than 5% above the band top, so a name that already ran does not ring. Both reads are the same ones behind the \u{1FA83} chip and the Back in Demand sort, and the gate FAILS CLOSED: no zone coverage means silence, counted apart from \u201Ccovered but not at a level\u201D. HONEST RECORD, carried in every push beside the pattern: across 669 resolved observations in your own ledger, cup-with-handle closed up 45% of the time over 434, double bottom 43% over 248, triple bottom 37% over 68 and inverse head-and-shoulders 10% over 10 — against a 50% placebo. NOT ONE BEATS CHANCE. flat_top is excluded outright: it fired on 120 of 120 random names. A watchlist ping, not a signal this app stands behind.' },
  { key: 'zone_bounce_alert', label: 'Intraday demand turn', emoji: '🪃', group: 'trading',
    detail: 'A $1B+ name touched a demand band — or a BROKEN supply shelf now acting as support — intraday and is already REVERSING off it: back above the band and at least 3% (or one ATR) off the day\'s low, with yesterday\'s close more than 3% above the band (arrivals only). Every band counts, even single-touch shelves the demand board ignores (NTAP 2026-09-03: -10% gap to 161, +6% by 09:33). Strong reversals (5% / 2 ATR, max 3 per check) get their own push; the rest share one digest per 5-min check. Once per band per day. Unknown market cap is skipped. Phone gate (Ajay 2026-09-05: \"Need only alerts on stocks that have atleast 5% to Supply and also <1% bounce from demand zone\"): the push fires only when the first band overhead is at least 5% above the print (nothing overhead passes) and the print sits between the band floor and 1% above its top; the boards still list every name.' },
  { key: 'supply_break_alert', label: 'Breaking resistance → new highs', emoji: '🚀', group: 'trading',
    detail: 'A $1B+ name within 1% under the ceiling of its LAST supply band — nothing overhead, or the band sits at the 52-week high — or that broke it today (up to 3% through). Once per band per day; the strongest 3 per minute get their own push, the rest share one digest. Bands tested 2+ times only (the board on SEPA → Supply / Demand and Chart Maps → Deep Demand lists every band with its touch count). The near-demand side of the same every-minute check reuses the 🧲 demand-zone approach kind above. Unknown market cap is skipped. Phone gate (Ajay 2026-09-05): pushes only when the NEXT band above the one being broken is at least 5% away (nothing overhead passes); the boards still list every name.' },
  { key: 'potus_investment', label: 'Federal stake reported', emoji: '\u{1F3DB}\uFE0F', group: 'trading',
    detail: 'ON BY DEFAULT since 2026-09-20 \u2014 you said: "Default on for any change of todays features Bondes or Potus or explosive growth or Earnings I wanna see all of them." '
      + 'You asked for the kind itself earlier the same day: "Anytime POTUS does new investments show me those." It is in the owner keep-set, so a re-registered device cannot quietly mute it. '
      + 'Turning it on widened WHICH KINDS reach you; it did not loosen what this one needs to fire \u2014 the gate below is unchanged. '
      + 'THIS IS A HEURISTIC, not a signal: a daily cron runs seven keyword searches and matches a REGEX over the headline TITLES. It has no measured record and nothing behind it has been backtested. '
      + 'The push gate is deliberately the tightest class and nothing looser \u2014 an EQUITY STAKE (not an award, not a contract, not "the administration is weighing a stake"), a NAMED federal agency (Commerce, DoD/Pentagon, DOE, Treasury) and a STATED size (a dollar figure or a percentage) in the SAME headline, plus a ticker that actually resolves. '
      + 'Everything looser \u2014 a federal award, a stake with no agency named, a headline whose company we could not turn into a ticker \u2014 still LISTS on Chart Maps \u2192 \u{1F3DB}\uFE0F POTUS as a candidate you read, and sends nothing. '
      + 'The watch NEVER edits the curated list: promoting a candidate onto it is a human edit of backend/political/disclosures.json. One push per ticker per headline url.' },
  { key: 'earnings_reaction', label: 'Earnings beat with institutional buying', emoji: '\u{1F4E3}', group: 'trading',
    detail: 'ON BY DEFAULT \u2014 an owner setting, from 2026-09-20: "Also don\'t forget to alert me on earnings surprises I think stock witz also has it. I wanna make sure we are catching those in alerts as well." '
      + 'WHAT FIRES: the REACTED half of the Chart Maps \u25B8 Earnings Flow tab. A beat \u2014 this quarter\'s surprise above zero \u2014 whose reaction bar traded at least 1.5\u00D7 its 60-day median volume, closed in the top 40% of the bar\'s range, turned over at least $50M and finished up on the day. '
      + 'A miss never pushes, however violently the stock reacts, and neither does a pre-report run-up \u2014 the bar has to have printed. Once per report. Two slots: 08:25 and 17:35 ET. '
      + 'StockTwits has no earnings-surprise feed, so this reads your own earnings calendar and the filed surprise, not social chatter. '
      + 'The room to the first supply band is shown as context and does not gate this kind. '
      + 'NOT MEASURED: no forward study stands behind "beat + institutions bought". Not a recommendation \u2014 a watchlist ping.' },
  { key: 'board_arrival', label: 'New on \u{1F4C8} Bonde / \u{1F680} Explosive Growth', emoji: '\u2728', group: 'trading',
    detail: 'ON BY DEFAULT \u2014 you said: "Default on for any change of todays features Bondes or Potus or explosive growth or Earnings I wanna see all of them." '
      + 'WHAT FIRES: a name ARRIVES on one of the two boards \u2014 \u{1F4C8} Bonde at 17:42 ET on a trading day, \u{1F680} Explosive Growth at 08:08 ET after the Sunday rebuild. '
      + 'It is one push per name per board, ever: a name that leaves a board and comes back is not rung again (the arrival ledger stamps a name once and keeps it). '
      + 'It is never the first cohort \u2014 the first pass after this ships records the baseline and sends nothing, so you are told about what is NEW, not about the 1,054 names already there. '
      + 'THIS IS AN ARRIVAL ON A LIST, NOT AN ENTRY. Bonde\'s own rule was measured INVERTED (\u22123.11pp against a matched placebo) and the 100/100 screen behind Explosive Growth measured 2026-09-21 as a lean, not a finding (the board carries the numbers). Not a recommendation.' },
  { key: 'capital_quality_upgrade', label: 'Capital quality improved', emoji: '\u{1F48E}', group: 'trading',
    detail: 'OFF BY DEFAULT — deliberately; with \u{1F511} key levels below, one of the two trading kinds here that ship muted. You asked for it ("Filter and have alerts and new look out for such companies where whcih have very high quality", 2026-09-22), but it is a kind you have not seen fire yet, so nothing turned it on for you. Flip it here when you want it. '
      + 'WHAT FIRES: a name on the \u{1F680} Explosive Growth board crosses a BALANCE-SHEET line on a NEW FISCAL QUARTER — it went net cash (cash now exceeds debt), it turned free-cash-flow positive, its share count stopped rising, or its return on capital turned positive. '
      + 'It is a CROSSING, not a state: "this name is high quality" is true for months and would either repeat until you muted it or say nothing at all. Only the transition rings. '
      + 'WHAT NEVER FIRES, on purpose: a figure that merely became KNOWN (that is the app learning, not the company improving — and the next metrics warm will make ~15 of 21 names \"improve\" at once for exactly that reason); the two sector-relative checks (those can move because a PEER filed); the same quarter twice (the claim is per name per fiscal quarter, forever — the \u{1F514} price-alert lesson, where 2,022 stale re-fires all delivered to nobody); and a DETERIORATION — you asked for a look-out, not a sell signal, and turning the downgrade side on is your call, not mine. '
      + 'The first pass records a baseline and sends nothing, the same rule the ✨ arrival ledgers use: "we only just started watching" must never read as "something just improved". '
      + 'NOTHING GATES IT. Your 2026-09-05 standing gates — at least 5% of room overhead, the print within 1% of the band — are about a PRICE at a ZONE; this reports a filing and names no price, so applying them would quietly turn a fundamentals notice into an entry signal. Whether a fundamentals push should carry a gate at all is an open question for you; no gate was invented for it. '
      + 'Once per name per quarter; 4 ring individually, the rest share a digest. Passes 17:52 ET on trading days, after the evening balance-sheet refresh. '
      + 'NOT MEASURED: nobody has measured whether a balance sheet improving predicts anything on your universe — and nobody can yet, because this alert’s own state is the first per-quarter history of these figures the app has ever kept. It is a screen, not an edge. Not a recommendation.' },
  /* 🔑 supply_demand/key_level_alerts.py (2026-09-25, Ajay: "I wanna know when
     key levels are broken for a stock"). Ships OFF and outside the owner
     keep-set, like 💎 above — turning it on is his call. The backend
     default_prefs() stamps it False on every stored device, so the toggle
     reads OFF. */
  { key: 'key_level_alert', label: 'Key level closed through', emoji: '🔑', group: 'trading',
    detail: 'your holdings and Signals list: one push after the close when a name closed through its prior-week, prior-month or 52-week high or low. Unmeasured.' },
  /* 🧬 catalysts/medical (2026-09-29, Ajay: "… add right setup and alerts").
     ON for him: in backend push/subs.OWNER_KEEP_SET (the key_level_alert
     precedent) and False in default_prefs for everyone else — HIS CALL #1
     flips it off with one word. The numbers below are the build's defaults
     (HIS CALLs #2 / #7 / #8); the contract re-reads the keep-set. */
  { key: 'med_catalyst', label: 'Medical catalyst (FDA, Phase 3, hold)', emoji: '🧬', group: 'trading',
    detail: 'ON FOR YOUR PHONE — you asked for alerts; everyone else starts off. You said: "can you add a new routine to scan for … amd trails or other medi cal nws and sector them separatively like new fdaapprovals or break throughs like mrnaresearch how to catch thsse sectorsand companiesand add right setup and alerts". '
      + 'WHAT FIRES: an FDA approval (not a tentative or generic one); a complete response letter, refuse-to-file or rejection; a Phase 3 or pivotal topline read that is clearly positive or clearly negative; a Breakthrough Therapy designation; a clinical hold placed. '
      + 'Only on a name whose prior close is at least $2 and whose 50-session median dollar volume is at least $5M a day, and only while the news is fresh — pre-market, after hours, or while the regular session has traded it for 10 minutes or less. '
      + 'One topline push per name per session, never a repeat of the same kind on the same name within 21 sessions, once per event. Every 5 minutes, 04:00–19:55 ET on trading days; weekend news rings Monday pre-market. '
      + 'A name whose news only the rolling company-news read finds (not an 8-K or a wire release) can be found after the open and then stays on the board without ringing. '
      + 'WHAT NEVER FIRES: Phase 2 results, mixed results including every secondary-endpoint miss, pulled or revoked approvals, filings, PDUFA dates, adcom votes, conference data, scheduled readouts, deals and offerings — all of them still list on Chart Maps \u25B8 Catalysts \u25B8 \u{1F9EC} Medical. '
      + 'Negative events end "not a sell signal", positive ones "not a buy signal". '
      + 'NOT MEASURED: events are sorted by fixed word rules and nobody has measured what a stock does after one on your universe — setup: pending study. Not a recommendation.' },
  /* 🚩 chart_maps/gajjala (2026-10-13, DECISIONS "Pushes: YES — owner-only kind
     gajjala_setup, A+ triggers only"). ON for him: in backend
     push/subs.OWNER_KEEP_SET and False in default_prefs for everyone else. It
     shipped in SHADOW (backend constants.GAJJALA_PUSH_MODE) and is LIVE since
     2026-10-16 (Ajay: "you alert me when that happens" — DECISIONS10 D1, his
     call; the 2026-10-14 study read NULL). The contracts.mjs 🚩 block re-reads
     the mode and the keep-set; the 🎯 block pins it (AMENDMENTS10 F1 / F4 / F5 / F9:
     everyone else starts off, refusals are counted on the pass row, the entry words
     are his rules' words, numbers first). */
  { key: 'gajjala_setup', label: 'Gajjala A+ setup (his five setups)', emoji: '🚩', group: 'trading',
    detail: 'ON FOR YOUR PHONE — you said "Pushes: YES" for his setups (2026-10-13) and "you alert me when that happens" (2026-10-16); everyone else starts off. '
      + 'LIVE SINCE 2026-10-16, your call: every A+ entry in the window is its own push; mute it here. A+ found before the switch were recorded on /alerts as "shadow — not sent" and stay listed that way; the \u{1F3C1} Track record counts the entries that were sent on their own \u{1F3AF} line, never pooled with the \u{1F9E0} alerts. '
      + 'WHAT FIRES: an A+ entry — every rule of one of Goverdhan Gajjala\u2019s five setups (\u{1F6A9} Bull Flag, \u{1F48B} EMA Kiss & Fly, \u2796 Horizontal Fade, \u{1F300} Intraday VCP, \u{1F3BE} Reversal Squeeze) met and the 5-minute (or 15-minute Fade) entry bar traded above its trigger (the break — his \u201CI\u2019ll enter right at the break\u201D, S8) and that bar has closed — the bar may close back under the trigger, a close above it is not required — on a name his scanner listed; the \u{1F48B} Kiss & Fly only after the pullback kissed and honored the 9 EMA. '
      + 'The push leads with the trigger and the stop, then the setup\u2019s entry in the words of his rules (\u{1F3BE}: 2+ sources, no first-hand entry rule on file), the time the \u{1F9E0} potential rang when one did, and the float. '
      + '09:45–16:00 and 16:00–20:00 ET (13:00 and 17:00 on NYSE half days), never 09:30–09:45 (his first 15 minutes), never pre-market, silent on closed days, once per name, setup and session, every A+ its own push. '
      + 'WHAT NEVER FIRES: a near-kiss, a "B — imperfect" VCP, a break that missed a rule, an A+ found late (its entry bar closed more than one 5-minute pass ago), an A+ in his first 15 minutes or pre-market (counted on that pass\'s /alerts row, never rung), or an open of the tab — those stay on Chart Maps \u25B8 Gajjala\u2019s. '
      + 'NOT MEASURED: his rules as he described them; the 2026-10-14 study of his setups read no edge. Not a recommendation.' },
  /* 🧠 chart_maps/gajjala/potential.py (2026-10-15). Ajay: "Give me an alert
     all continous tracker on these specifically when I get alert I will jump on
     to ride the wave". A NEW kind, LIVE, owner-only: in backend
     push/subs.OWNER_KEEP_SET and False in default_prefs for everyone else (the
     tape-burst precedent — so the entry never says shadow). The 04:00–20:00 /
     09:30–09:45 are daytrading/data.py's clock + NO_TRADE_AFTER_OPEN_MIN, the 5
     the gajjala.run crontab step; the three "Cheetah default, not his" sentences
     exist iff POTENTIAL_NEEDS_BASE / POTENTIAL_DEFER_REFUSED /
     POTENTIAL_FRESH_TAPE are True — the contracts.mjs 🧠 block pins all of it.
     UNMEASURED — a potential, not an entry. */
  { key: 'gajjala_potential', label: 'Gajjala potential (forming, trigger not printed)', emoji: '\u{1F9E0}', group: 'trading',
    detail: 'ON FOR YOUR PHONE — you said: "Give me an alert all continous tracker on these specifically when I get alert I will jump on to ride the wave"; everyone else starts off. It rings live — there is no later switch to flip. '
      + 'WHAT FIRES: the first time a name his scanner listed is a potential in one of Goverdhan Gajjala’s five setups (\u{1F6A9} Bull Flag, \u{1F48B} EMA Kiss & Fly, ➖ Horizontal Fade, \u{1F300} Intraday VCP, \u{1F3BE} Reversal Squeeze): the read is forming, the demand leg is in, the quiet sideways part has started ("building") or is complete ("trigger armed"), and the reclaim of the highs has not printed (needing at least one sideways bar is a Cheetah default, not his). The push says which, with the trigger and stop the read carries, the float and the float rotation. '
      + 'Once per name, setup and session, every one its own push, every one listed on /alerts with its ticker linked to the tab. Every 5 minutes, 04:00–20:00 ET on trading days (earlier on NYSE half days), never 09:30–09:45 (his first 15 minutes) — a name first seen in them rings on the next pass if it is still a potential (a Cheetah default, not his); silent on closed days. A name with no print in the 5-minute bar that just closed waits for its next print (a Cheetah default, not his). '
      + 'WHAT NEVER FIRES: a read that already broke (A+ — those ring under \u{1F6A9} as an A+ entry since 2026-10-16), a partial (a rule failed), a near-kiss, a "B — imperfect" VCP, a second sighting the same session. '
      + 'UNMEASURED — a potential, not an entry; GG enters on the reclaim of the highs. The study of his A+ setups read no edge (2026-10-14); nobody has measured potentials. Not a recommendation.' },
  /* 🎢 🗺️ orderflow/tape_burst_kinds.py (2026-10-14). Ajay: "I need a tape
     burst notification specific for High Beta stocks from the reselinet
     separately and also other tape bursts from the Chart Maps page". Two
     owner-only kinds, ON for him: in backend push/subs.OWNER_KEEP_SET and False
     in default_prefs for everyone else (the med_catalyst precedent). They ring
     LIVE — nothing about them is shadow. The burst numbers are pinned by the
     contracts.mjs tape-burst block to orderflow/tape.py, the 150s to
     tape_burst_kinds.py, the window to trade_flash.WATCH_OPEN_ET / WATCH_CLOSE_ET,
     the $2 to trading/safety_floor.MIN_SHARE_PRICE. "Rings live" is not "every
     burst is sent": the NOT READ sentence names what never reaches the push
     (cold first poll, the house floor, the poll budget, ⚡'s own record). */
  { key: 'tape_burst_highbeta', label: 'Tape burst \u2014 High Beta', emoji: '\u{1F3A2}', group: 'trading',
    detail: 'ON FOR YOUR PHONE \u2014 you said: "I need a tape burst notification specific for High Beta stocks from the reselinet separately and also other tape bursts from the Chart Maps page"; everyone else starts off. It rings live \u2014 nothing is held for a later switch-on. '
      + 'WHAT IT WATCHES: every name on Chart Maps \u25B8 \u{1F3A2} High Beta, biggest drop today first, up to 150 names. '
      + 'NOT READ: the first poll after a cold start can watch nothing; names under the house share-price floor ($2) are not read; names the poll\u2019s time budget cuts are not read that poll; a burst \u26A1 trade flash already recorded is not sent again. '
      + 'WHAT FIRES: the same burst rule as \u26A1 trade flash \u2014 inside a 10-second window, $250K or more traded, 75% or more of it on one side, across 15+ regular prints (auction crosses, average-price and busted prints are left out) \u2014 anywhere in the day\u2019s range, no zone needed. '
      + 'A burst on a High-Beta name rings here even at a zone (\u26A1 trade flash is muted on your phone since 2026-09-08); each burst is one row on /alerts, never two. '
      + 'Every 5 minutes, 09:32\u201316:00 ET on trading days, silent on closed days; one push per poll, every burst listed on /alerts with each ticker linked to its tape. '
      + 'UNMEASURED \u2014 a description of prints, not a signal. Not advice.' },
  { key: 'tape_burst_chartmaps', label: 'Tape burst \u2014 Chart Maps', emoji: '\u{1F5FA}\uFE0F', group: 'trading',
    detail: 'ON FOR YOUR PHONE \u2014 the same ask: "I need a tape burst notification specific for High Beta stocks from the reselinet separately and also other tape bursts from the Chart Maps page"; everyone else starts off. It rings live \u2014 nothing is held for a later switch-on. '
      + 'NOT READ: names under the house share-price floor ($2) are not read; names the poll\u2019s time budget cuts are not read that poll. '
      + 'WHAT IT WATCHES: the names the Chart Maps tabs served at their last load (today or the last session), a few from each tab in turn, up to 150 names \u2014 minus the names \u26A1 trade flash already watches at their zones and the names on the \u{1F3A2} High-Beta list (those ring as \u{1F3A2}). '
      + 'WHAT FIRES: the same burst rule as \u26A1 trade flash \u2014 inside a 10-second window, $250K or more traded, 75% or more of it on one side, across 15+ regular prints (auction crosses, average-price and busted prints are left out) \u2014 anywhere in the day\u2019s range, no zone needed. '
      + 'A burst already recorded by \u26A1 trade flash or \u{1F3A2} High Beta is not sent again; each burst is one row on /alerts, never two. '
      + 'Every 5 minutes, 09:32\u201316:00 ET on trading days, silent on closed days; one push per poll, every burst listed on /alerts with each ticker linked to its tape. '
      + 'UNMEASURED \u2014 a description of prints, not a signal. Not advice.' },
  /* 🎚️ tape_control (orderflow/tape_control.py, 2026-10-16). Ajay: "Can you add
     a watcher tape for IREN please." then "I wwant you to alert me when the
     Buyers are winning in tape for IREN today." One owner-only kind, ON for him
     (backend push/subs.OWNER_KEEP_SET; False in default_prefs for everyone
     else). LIVE — never shadow. The 30 minutes is tape.LATE_WINDOW_MIN, the
     window trade_flash.WATCH_OPEN_ET / WATCH_CLOSE_ET, the 5 minutes the
     trade-flash crontab step, IREN and its date tape_control.WATCH — all pinned
     by the contracts.mjs 🎚️ block. UNMEASURED. */
  { key: 'tape_control', label: 'Buyers in control on the tape — pinned names', emoji: '\u{1F39A}\uFE0F', group: 'trading',
    detail: 'ON FOR YOUR PHONE — you said: "I wwant you to alert me when the Buyers are winning in tape for IREN today."; everyone else starts off. It rings live. '
      + 'WHAT IT WATCHES: IREN — pinned for 2026-10-16, through that session’s close. '
      + 'WHAT FIRES: the Tape tab’s own buyers-in-control check — the session’s cumulative delta above zero AND the last 30 minutes’ delta at or above zero, regular prints only, pre-market counted, sides by the tick rule (the Tape tab classifies against the quote where it can, so the two can disagree). One push when it turns to buyers in control — the first poll that reads it — never again while it holds (a ring that reached no device is tried once more on the next poll), again only after a poll reads it lost. '
      + 'NOT READ: a poll that cannot read the tape (no prints, a provider failure, a pull cut off at the page cap, the poll’s time budget) never rings and never re-arms. '
      + 'Every 5 minutes, 09:32–16:00 ET on trading days, silent on closed days; every ring listed on /alerts with its ticker linked to its tape. '
      + 'UNMEASURED — the Tape verdict’s forward ledger measures the five-check verdict, not this check alone. Not advice.' },
  /* 🌙 overnight_movers (overnight/push.py, 2026-10-19). Ajay: "Can you do an
     over night scan for all the stocks they are all growing over night". SHIPS
     OFF — False in backend push/subs.default_prefs and NOT in OWNER_KEEP_SET
     (BUILD_SPEC16 D8, AMENDMENTS16 A2 — his call), so the Essentials preset
     does not carry it. The figures ($2 = trading.safety_floor.MIN_SHARE_PRICE,
     $250K = PUSH_MIN_ON_DOLLAR, top 5 = PUSH_TOP_N, 06:45 = SLOT_ET, 9:30 =
     daytrading.data.ET_RTH_OPEN, 04:00 = overnight.session.SESSION_CLOSE_ET) are
     pinned to those constants by the contracts.mjs 🌙 block. UNMEASURED. */
  { key: 'overnight_movers', label: 'Overnight movers', emoji: '🌙', group: 'trading',
    detail: 'OFF — switch it on here. You asked for the scan (\u201CCan you do an over night scan for all the stocks they are all growing over night\u201D), not an alert, so it ships off until you say on. '
      + 'WHAT FIRES: once per overnight session, at 06:45 ET on trading days — never 20:00–06:44, never after the 9:30 open — the index line (SPY, QQQ, IWM, DIA against the last regular close) and the top 5 overnight gainers that pass: price at least $2, at least $250K traded overnight, not a leveraged or inverse ETF (a name whose leverage could not be read is left out too). '
      + 'No name passes \u2192 no push; /alerts says why. Every name it lists is linked on /alerts. '
      + 'It reports the session that ended at 04:00 ET — its last stored read, timed in the push. '
      + 'UNMEASURED — what moved overnight, not what to buy. Not advice.' },
  { key: 'market_hours_reminder', label: 'Market open / close reminders', emoji: '🔔', group: 'trading',
    detail: '15 min before the bell each weekday — 9:15 AM ET (open) and 3:45 PM ET (close). Skips US market holidays. Open ping routes to /morning brief; close ping routes to /sepa for position management.' },
  // The three volleyball kinds and Minervini learning were retired 2026-09-20
  // — Ajay: "Remove volleyball and learning of stocks I do dont wanna see
  // them they are spamming too much". The crons are gone, the kinds are in
  // push.subs.RETIRED_2026_09_20 (hard-stopped at the delivery chokepoint), and
  // a toggle for a kind that can never fire would be a lie. Old push_history
  // rows still render, via lib/alertKinds.ts.
  { key: 'todo_reminder',          label: 'Todo reminders',         emoji: '📌', group: 'household',
    detail: 'Personal todo list reminders fired at the time you set per task.' },
  { key: 'todo_daily_digest',      label: 'Todo daily digest',      emoji: '📋', group: 'household',
    detail: '7 AM ET daily summary of all open todos for the day.' },
  // 'macbook_deal' category removed 2026-05-15 along with the lifeboard
  // Mac deal scraper module.

  // Real-estate (house) notifications — only delivered to HOUSE_OWNER_EMAIL
  // because the daily_scrape cron pushes via send_to_user(owner, ...).
  // Toggles still render for non-owners (no harm) but they'd never fire.
  { key: 'house_daily',            label: 'House · daily summary',  emoji: '🏡', group: 'household',
    detail: '8 AM ET listing summary — views, saves, tours, offers, day-over-day delta. Pulled from Redfin/Zillow/Realtor.' },
  { key: 'house_scrape_failed',    label: 'House · scrape failed',  emoji: '⚠️', group: 'household',
    detail: 'Fires only when all three scrapers (Redfin, Zillow, Realtor) come back empty so you know to enter numbers manually.' },
  { key: 'house_stagnant',         label: 'House · engagement stalled', emoji: '📉', group: 'household',
    detail: '3+ consecutive days without any new views. Nudge to consider a price drop, fresh photos, or an open-house push.' },

  // Admin-only category — only visible to ADMIN_EMAILS.
  { key: 'user_signin',            label: 'New user signed in',     emoji: '👋', group: 'admin',
    detail: 'One-time push when a new email signs in for the first time. Fires exactly once per user. Visible only to admins.' },
  // 🩺 2026-10-06 — Ajay approved the Docker watchdog push (ops/docker_watchdog.py).
  { key: 'ops_alert',              label: 'Docker / host watch',    emoji: '🩺', group: 'admin',
    detail: 'Pushes from the Mac\'s Docker watchdog: the network forwarder at 2,000+ open flows or +500 in 24 h, Docker\'s backend down / back / restarted, the Mac on battery under 20% and 10%. While Docker is down the push waits and the Mac shows a notification. Visible only to admins.' },
];

const GROUP_LABELS: Record<CategoryDef['group'], string> = {
  trading:   'Trading signals',
  household: 'Household & deals',
  admin:     'Admin',
};

export default function NotificationsPage() {
  const { rows, error, busy, refresh, togglePref, setManyPrefs, setQuietHours, unsubscribe, sendTest } = useNotificationPrefs();
  const { user } = useCurrentUser();
  const isAdmin = !!user?.is_admin;
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [addOk, setAddOk] = useState(false);
  // When a user wants to re-read the iOS / Android install steps —
  // typically after they tapped "Got it" on the first-run prompt and
  // need a refresher. Clearing the dismissal flag too so a phone
  // restart-and-revisit also re-triggers the prompt if they still
  // haven't installed.
  const [showInstall, setShowInstall] = useState(false);
  const openInstallGuide = () => {
    clearInstallDismissal();
    setShowInstall(true);
  };

  const addThisDevice = async () => {
    setAdding(true); setAddError(null); setAddOk(false);
    try {
      if (!pushSupported()) {
        setAddError('This browser does not support web push. Use Chrome / Safari (iOS as PWA).');
        return;
      }
      const r = await subscribePush('Pounce · ' + (navigator.userAgent.slice(0, 100)));
      if (!r.ok) {
        setAddError(r.reason || 'Subscription failed');
        return;
      }
      setAddOk(true);
      await refresh();
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="cm-page" style={{ padding: '1.2rem 1.4rem', maxWidth: 920, margin: '0 auto' }}>
      <header className="cm-pagehead" style={{ marginBottom: '1rem' }}>
        <div className="cm-pagehead__col">
          <div className="eyebrow">Notifications · subscribe / unsubscribe</div>
          <h1 className="display cm-pagehead__title" style={{ margin: '0.25rem 0 0' }}>Notifications</h1>
          <p className="lede">
            One card per device. Toggle each category to control what pings what. Changes save instantly.
          </p>
        </div>
      </header>

      {/* Recent pushes — full untruncated bodies. Lives at the TOP so the
          user lands on the most-asked-for info ("what was that notification
          that just got clipped on my lock screen?") before scrolling
          through pref toggles. */}
      <PushHistoryPanel limit={25} />

      {/* Add this device card */}
      <section style={{
        marginBottom: '1rem', padding: '0.9rem 1.1rem',
        border: '1px solid var(--rule, #ddd)', borderLeft: '4px solid var(--positive, #10b981)',
        borderRadius: 5, background: 'var(--bg-raised)',
      }}>
        <div className="eyebrow" style={{ color: 'var(--positive)' }}>Add this device</div>
        <p style={{ fontSize: '0.84rem', margin: '0.4rem 0 0.6rem' }}>
          If this browser / PWA isn't in the list below, subscribe it now. Android works in Chrome directly.
          iOS needs the app installed as a PWA first (Share → Add to Home Screen).
        </p>
        <button
          onClick={addThisDevice}
          disabled={adding}
          className="sepa-btn sepa-btn--primary"
          style={{ minHeight: 40 }}
        >
          {adding ? '…subscribing' : '🔔 Subscribe this device'}
        </button>
        {!isStandalone() && /iPhone|iPad/.test(navigator.userAgent) && (
          <div style={{ fontSize: '0.78rem', color: 'var(--warn, #d97706)', marginTop: '0.5rem' }}>
            ⚠ iOS: install as PWA first (Safari Share → Add to Home Screen), then open the PWA and subscribe from there. Subscribing in Safari directly won't deliver pushes.
          </div>
        )}
        {/* Walkthrough — iPhone only. Android Chrome and desktop browsers
            deliver push to a regular tab; they don't need this guide, and
            showing the button there is confusing. The auto-show prompt
            uses the same gate (see shouldAutoShowInstallPrompt). */}
        {isIPhone() && (
          <button
            onClick={openInstallGuide}
            style={{
              marginTop: '0.6rem',
              background: 'none',
              border: '1px dashed var(--rule, #555)',
              color: 'var(--ink, inherit)',
              padding: '0.5rem 0.75rem',
              borderRadius: 4,
              cursor: 'pointer',
              fontSize: '0.82rem',
              fontFamily: 'inherit',
            }}
          >
            📱 Show install instructions (Add to Home Screen)
          </button>
        )}
        {addError && <div style={{ color: 'var(--negative)', fontSize: '0.8rem', marginTop: '0.4rem' }}>{addError}</div>}
        {addOk && <div style={{ color: 'var(--positive)', fontSize: '0.8rem', marginTop: '0.4rem' }}>✓ Subscribed — see the device card below.</div>}
      </section>

      {/* The modal is force-opened from the button above, so it bypasses
          the auto-show gates (won't refuse to render on desktop or in
          standalone mode). User explicitly asked to see it. */}
      {showInstall && (
        <InstallToHomeScreen forceOpen onClose={() => setShowInstall(false)} />
      )}

      {error && (
        <div style={{ padding: '0.5rem 0.8rem', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 4, color: 'var(--negative)', marginBottom: '1rem', fontSize: '0.85rem' }}>
          {error} · <button onClick={refresh} style={{ color: 'inherit', background: 'none', border: 0, textDecoration: 'underline', cursor: 'pointer' }}>retry</button>
        </div>
      )}

      {rows === null && <div style={{ color: 'var(--cm-slate)' }}>Loading devices…</div>}

      {rows && rows.length === 0 && (
        <div style={{ padding: '1rem 1.2rem', border: '1px dashed var(--rule, #444)', borderRadius: 6, color: 'var(--cm-slate)', textAlign: 'center' }}>
          No devices subscribed yet. Tap "Subscribe this device" above.
        </div>
      )}

      {/* Alert thresholds — global to the user. Drives the -12% intraday
          chip on every SEPA card; tightening it (e.g. to -10%) flows
          through all cards instantly via the cached settings store. */}
      <AlertThresholdsSection />

      {rows && rows.map((row) => (
        <DeviceCard
          key={row.endpoint}
          row={row}
          busy={busy === row.endpoint}
          isAdmin={isAdmin}
          onToggle={(k) => togglePref(row.endpoint, k)}
          onMany={(updates) => setManyPrefs(row.endpoint, updates)}
          onQuietHours={(fields) => setQuietHours(row.endpoint, fields)}
          onTest={() => sendTest(row)}
          onRemove={() => {
            if (confirm(`Remove ${row.label || row.endpoint_short}? Notifications will stop on this device.`)) {
              unsubscribe(row);
            }
          }}
        />
      ))}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────── */
/* ────────────────────────────────────────────────────────────────────── */
function AlertThresholdsSection() {
  const { settings, update, busy } = useAlertSettings();

  // Preset chips for the intraday emergency — most users want a one-tap
  // pick, not a slider. The custom input is below for fine-tuning.
  const EMERGENCY_PRESETS: { value: number; label: string; sub: string }[] = [
    { value: 8,  label: '−8%',  sub: 'tight · low volatility names' },
    { value: 10, label: '−10%', sub: 'moderate · most growth stocks' },
    { value: 12, label: '−12%', sub: 'Minervini default' },
    { value: 15, label: '−15%', sub: 'loose · high-vol / leveraged' },
  ];

  return (
    <section style={{
      marginBottom: '1rem', padding: '0.9rem 1.1rem',
      border: '1px solid var(--rule, #ddd)', borderLeft: '4px solid var(--warn, #d97706)',
      borderRadius: 5, background: 'var(--bg-raised)',
    }}>
      <div className="eyebrow" style={{ color: 'var(--warn, #d97706)' }}>
        ⚙️ Alert thresholds
      </div>
      <p style={{ fontSize: '0.82rem', margin: '0.4rem 0 0.8rem' }}>
        Customize the <strong>⚠ Exit</strong> level shown on every SEPA card.
        Tightening to −8% means earlier alerts at the cost of more shakeouts;
        loosening to −15% gives volatile names breathing room.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '0.45rem', marginBottom: '0.7rem' }}>
        {EMERGENCY_PRESETS.map(p => {
          const active = Math.abs(settings.intraday_emergency_pct - p.value) < 0.01;
          return (
            <button
              key={p.value}
              onClick={() => update({ intraday_emergency_pct: p.value })}
              disabled={busy}
              style={{
                padding: '0.55rem 0.5rem',
                background: active ? 'rgba(217, 119, 6, 0.12)' : 'transparent',
                border: '2px solid',
                borderColor: active ? 'var(--warn, #d97706)' : 'var(--rule, #555)',
                borderRadius: 5,
                cursor: 'pointer', fontFamily: 'inherit',
                color: 'inherit',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: active ? 'var(--warn)' : 'inherit' }}>
                {p.label}
              </div>
              <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: 2 }}>
                {p.sub}
              </div>
            </button>
          );
        })}
      </div>

      {/* Fine-tune slider */}
      <div style={{ marginTop: '0.5rem' }}>
        <label style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ flexShrink: 0, color: 'var(--cm-slate)' }}>Fine tune:</span>
          <input
            type="range"
            min="5"
            max="20"
            step="0.5"
            value={settings.intraday_emergency_pct}
            onChange={(e) => update({ intraday_emergency_pct: Number(e.target.value) })}
            style={{ flex: 1 }}
          />
          <span className="mono" style={{ minWidth: 50, textAlign: 'right', color: 'var(--warn)' }}>
            −{settings.intraday_emergency_pct}%
          </span>
        </label>
      </div>

      {/* Secondary thresholds — collapsed under a "More" disclosure to
          avoid overwhelming the casual user. */}
      <details style={{ marginTop: '0.7rem' }}>
        <summary style={{ cursor: 'pointer', fontSize: '0.75rem', color: 'var(--cm-slate)' }}>
          More thresholds
        </summary>
        <div style={{ marginTop: '0.5rem', display: 'grid', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ flexShrink: 0, color: 'var(--cm-slate)', width: 130 }}>Early warning:</span>
            <input
              type="range" min="3" max="15" step="0.5"
              value={settings.intraday_warning_pct}
              onChange={(e) => update({ intraday_warning_pct: Number(e.target.value) })}
              style={{ flex: 1 }}
            />
            <span className="mono" style={{ minWidth: 50, textAlign: 'right' }}>−{settings.intraday_warning_pct}%</span>
          </label>
          <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginLeft: 130 }}>
            Push fires when an intraday move crosses this threshold — earlier signal before the structural emergency.
          </div>

          <label style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ flexShrink: 0, color: 'var(--cm-slate)', width: 130 }}>Stop buffer:</span>
            <input
              type="range" min="0" max="5" step="0.25"
              value={settings.stop_close_buffer_pct}
              onChange={(e) => update({ stop_close_buffer_pct: Number(e.target.value) })}
              style={{ flex: 1 }}
            />
            <span className="mono" style={{ minWidth: 50, textAlign: 'right' }}>{settings.stop_close_buffer_pct}%</span>
          </label>
          <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginLeft: 130 }}>
            Notify when price closes within this % of your stop level.
          </div>
        </div>
      </details>
    </section>
  );
}

/* Presets — one-tap configurations of the per-category toggles. */
export const PRESETS: { id: string; label: string; emoji: string; detail: string; pref: Partial<NotificationPrefs> }[] = [
  {
    id: 'all_on', label: 'All on', emoji: '🟢',
    detail: 'Every trading + household notification enabled.',
    pref: Object.fromEntries(CATEGORIES.map(c => [c.key, true])) as any,
  },
  {
    id: 'all_off', label: 'All off', emoji: '🔇',
    detail: 'Mute everything. Subscription stays active but no pushes will fire.',
    pref: Object.fromEntries(CATEGORIES.map(c => [c.key, false])) as any,
  },
  {
    // Ajay 2026-09-09: "Can you give me hot pull back alerts and chart pattern
    // Alerts and also Sameday deman alerts please... Kill all other.. I just
    // wanna these alerts.. Default turn these on from tomorrow." Asked whether
    // the stops on stocks he OWNS counted as "other", he kept those and dropped
    // the todo reminders. Mirrors backend/push/subs.OWNER_KEEP_SET exactly.
    id: 'essentials', label: 'Essentials only', emoji: '🎯',
    detail: 'The 2026-09-20 keep-set: 🔥 Hot Pullback, 📐 chart patterns, 🧲 same-day demand arrivals and 💼 stops on stocks you own, plus 🏛️ federal stake, 🚀 explosive growth at demand, 📣 earnings beat, ✨ board arrivals, 🔔 the price alerts you set (2026-09-21), 🔑 a close through a key level on a holding or Signals name (2026-09-25), and 🧬 medical catalysts (2026-09-29), and 🩺 Docker / host watch (2026-10-06), and 🚩 Gajjala A+ entries (2026-10-13, live since 2026-10-16), and 🧠 Gajjala potentials (2026-10-15, live), and 🎢 / 🗺️ tape bursts on the High Beta and Chart Maps names (2026-10-14, they ring live), and 🎚️ buyers in control on the tape for your pinned names (2026-10-16, it rings live). Everything else muted.',
    pref: {
      hot_pullback_alert: true, pattern_alert: true,
      demand_alert: true, position_alert: true,
      price_alert: true, key_level_alert: true,
      med_catalyst: true,
      ops_alert: true,
      gajjala_setup: true,
      gajjala_potential: true,
      tape_burst_highbeta: true, tape_burst_chartmaps: true,
      tape_control: true,
      potus_investment: true, growth_demand_alert: true,
      earnings_reaction: true, board_arrival: true,
      pivot_alert: false, promo_alert: false,
      zone_bounce_alert: false, supply_break_alert: false,
      market_hours_reminder: false,
      todo_reminder: false, todo_daily_digest: false,
    },
  },
  {
    id: 'trading_only', label: 'Trading only', emoji: '📈',
    detail: 'All trading alerts on, household off.',
    pref: Object.fromEntries(CATEGORIES.map(c => [c.key, c.group === 'trading'])) as any,
  },
  {
    id: 'household_only', label: 'Household only', emoji: '🏠',
    detail: 'All household + deals on, no market noise.',
    pref: Object.fromEntries(CATEGORIES.map(c => [c.key, c.group === 'household'])) as any,
  },
];

function DeviceCard({ row, busy, isAdmin, onToggle, onMany, onQuietHours, onTest, onRemove }: {
  row: DeviceRow;
  busy: boolean;
  isAdmin: boolean;
  onToggle: (key: keyof NotificationPrefs) => void;
  onMany: (updates: Partial<NotificationPrefs>) => void;
  onQuietHours: (fields: Partial<NotificationPrefs>) => void;
  onTest: () => void;
  onRemove: () => void;
}) {
  const created = row.created_at ? new Date(row.created_at * 1000).toLocaleDateString() : '?';
  const prefs = row.prefs || {};
  const kindLabel = row.kind === 'mac' ? '🖥️ Mac native' : '🌐 Web/PWA';
  // Guess platform from UA label
  const platform =
    row.label?.includes('iPhone') ? '📱 iPhone' :
    row.label?.includes('Android') ? '📱 Android' :
    row.label?.includes('Macintosh') ? '🖥️ Mac' :
    row.label?.includes('Windows') ? '🖥️ Windows' :
    null;

  return (
    <section style={{
      marginBottom: '1rem', padding: '0.9rem 1.1rem',
      border: '1px solid var(--rule, #ddd)', borderRadius: 6, background: 'var(--bg-raised)',
      opacity: busy ? 0.6 : 1, transition: 'opacity 0.15s',
    }}>
      {/* Device header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.8rem' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem', flexWrap: 'wrap' }}>
            <strong style={{ fontSize: '1rem' }}>{platform || kindLabel}</strong>
            <span className="mono" style={{ fontSize: '0.66rem', color: 'var(--cm-slate)' }}>
              {kindLabel} · added {created}
            </span>
          </div>
          {row.label && (
            <div style={{ fontSize: '0.72rem', color: 'var(--cm-slate)', marginTop: 2, wordBreak: 'break-word' }}>
              {row.label.slice(0, 120)}
            </div>
          )}
          <div className="mono" style={{ fontSize: '0.62rem', color: 'var(--cm-slate)', marginTop: 2 }}>
            …{row.endpoint_short}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.4rem', flexShrink: 0 }}>
          <button onClick={onTest} className="sepa-btn" style={{ fontSize: '0.78rem' }} title="Send a test notification to this device">
            🔔 Test
          </button>
          <button onClick={onRemove} className="sepa-btn" style={{ fontSize: '0.78rem', color: 'var(--negative)' }} title="Unsubscribe this device entirely">
            ✕ Remove
          </button>
        </div>
      </div>

      {/* Preset bar — one-tap multi-category sets */}
      <div style={{
        marginBottom: '0.8rem', padding: '0.5rem 0.6rem',
        background: 'rgba(255,255,255,0.02)',
        border: '1px dashed var(--rule, #444)', borderRadius: 4,
      }}>
        <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.35rem' }}>
          Presets — one-tap configurations
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
          {PRESETS.map((p) => (
            <button
              key={p.id}
              onClick={() => onMany(p.pref)}
              title={p.detail}
              style={{
                padding: '4px 10px', fontSize: '0.72rem',
                background: 'transparent',
                border: '1px solid var(--rule, #555)',
                borderRadius: 3, color: 'inherit',
                cursor: 'pointer', fontFamily: 'inherit',
              }}
            >
              {p.emoji} {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Category toggles, grouped. Admin group only shown to admins. */}
      {(['trading', 'household', 'admin'] as const).map((group) => {
        if (group === 'admin' && !isAdmin) return null;
        const cats = CATEGORIES.filter(c => c.group === group);
        if (cats.length === 0) return null;
        const onCount = cats.filter(c => prefs[c.key] !== false).length;
        const allOn = onCount === cats.length;
        const allOff = onCount === 0;
        return (
          <div key={group} style={{ marginBottom: '0.7rem' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginBottom: '0.3rem', flexWrap: 'wrap' }}>
              <h4 style={{ margin: 0, fontSize: '0.78rem', color: 'var(--cm-slate)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                {GROUP_LABELS[group]}
              </h4>
              <span style={{ fontSize: '0.7rem', color: 'var(--cm-slate)' }}>{onCount} of {cats.length} on</span>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.3rem' }}>
                <button
                  onClick={() => onMany(Object.fromEntries(cats.map(c => [c.key, true])) as any)}
                  disabled={allOn}
                  style={{
                    fontSize: '0.66rem', padding: '2px 8px',
                    background: 'none', border: '1px solid var(--rule, #555)',
                    color: allOn ? 'var(--cm-slate)' : 'inherit',
                    borderRadius: 3, cursor: allOn ? 'default' : 'pointer',
                    opacity: allOn ? 0.5 : 1,
                  }}
                  title={`Turn on all ${cats.length} ${group} notifications`}
                >✓ all</button>
                <button
                  onClick={() => onMany(Object.fromEntries(cats.map(c => [c.key, false])) as any)}
                  disabled={allOff}
                  style={{
                    fontSize: '0.66rem', padding: '2px 8px',
                    background: 'none', border: '1px solid var(--rule, #555)',
                    color: allOff ? 'var(--cm-slate)' : 'inherit',
                    borderRadius: 3, cursor: allOff ? 'default' : 'pointer',
                    opacity: allOff ? 0.5 : 1,
                  }}
                  title={`Turn off all ${cats.length} ${group} notifications`}
                >✕ none</button>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '0.3rem' }}>
              {cats.map((c) => {
                const on = prefs[c.key] !== false;
                return (
                  <button
                    key={c.key}
                    onClick={() => onToggle(c.key)}
                    title={c.detail}
                    style={{
                      display: 'flex', alignItems: 'flex-start', gap: '0.5rem',
                      padding: '0.55rem 0.7rem',
                      background: on ? 'rgba(16, 185, 129, 0.06)' : 'transparent',
                      border: '1px solid',
                      borderColor: on ? 'rgba(16, 185, 129, 0.3)' : 'var(--rule, #444)',
                      borderRadius: 4,
                      color: 'inherit',
                      textAlign: 'left',
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                    }}
                  >
                    {/* iOS-style toggle */}
                    <div style={{
                      width: 28, height: 18, borderRadius: 9,
                      background: on ? 'var(--positive, #10b981)' : 'var(--rule, #555)',
                      position: 'relative', flexShrink: 0,
                      transition: 'background 0.15s',
                      marginTop: 1,
                    }}>
                      <div style={{
                        position: 'absolute',
                        width: 14, height: 14, borderRadius: 7,
                        background: '#fff', top: 2, left: on ? 12 : 2,
                        transition: 'left 0.15s',
                      }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '0.86rem', fontWeight: 600 }}>
                        <span style={{ marginRight: '0.3rem' }}>{c.emoji}</span>
                        {c.label}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: 1, lineHeight: 1.4 }}>
                        {c.detail}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Quiet hours */}
      <div style={{
        marginTop: '0.5rem', paddingTop: '0.7rem',
        borderTop: '1px dashed var(--hairline, #444)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
          <strong style={{ fontSize: '0.85rem' }}>🌙 Quiet hours</strong>
          <button
            onClick={() => onQuietHours({ quiet_hours_enabled: !prefs.quiet_hours_enabled })}
            style={{
              padding: '2px 10px', fontSize: '0.72rem',
              border: '1px solid', borderColor: prefs.quiet_hours_enabled ? 'var(--positive)' : 'var(--rule, #444)',
              color: prefs.quiet_hours_enabled ? 'var(--positive)' : 'var(--cm-slate)',
              background: 'none', borderRadius: 3, cursor: 'pointer',
            }}
          >
            {prefs.quiet_hours_enabled ? 'ON' : 'OFF'}
          </button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.78rem', flexWrap: 'wrap' }}>
          <label>
            from{' '}
            <input
              type="time"
              value={prefs.quiet_hours_start || '22:00'}
              onChange={(e) => onQuietHours({ quiet_hours_start: e.target.value })}
              disabled={!prefs.quiet_hours_enabled}
              style={{ padding: '3px 6px', fontSize: '0.78rem' }}
            />
          </label>
          <label>
            until{' '}
            <input
              type="time"
              value={prefs.quiet_hours_end || '08:00'}
              onChange={(e) => onQuietHours({ quiet_hours_end: e.target.value })}
              disabled={!prefs.quiet_hours_enabled}
              style={{ padding: '3px 6px', fontSize: '0.78rem' }}
            />
          </label>
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: 4 }}>
          During quiet hours, non-urgent notifications are silenced. Position stop/target alerts still fire.
        </div>
      </div>
    </section>
  );
}
