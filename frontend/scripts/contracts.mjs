#!/usr/bin/env node
/* Frontend source contracts — lightweight invariant checks on the FE source so
 * behaviours that have regressed via rebases can't silently drop again.
 *
 * No dependencies: it just reads source files and asserts patterns. This is the
 * frontend analogue of backend/tests/test_sepa_contracts.py, wired into
 * `make contracts` (so the pre-commit gate covers it) and `npm run contracts`.
 *
 * Add a new entry to CONTRACTS below whenever you ship a frontend behaviour
 * that would be expensive to lose silently.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const FRONTEND_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (rel) => readFileSync(join(FRONTEND_ROOT, rel), 'utf8');

const CONTRACTS = [
  {
    name: 'ticker page passes BOTH halves of the chart view to SupportLevels',
    file: 'src/pages/SepaCandidate.tsx',
    // The component's onChange falls back to onWindow(v.window) when onView is
    // absent, silently dropping the tf half — so "15 min · today from the
    // open" snapped straight back to "1 month" on the ticker page (Ajay
    // 2026-08-31, on ACN). A render test cannot catch a MISSING prop on a
    // different page, so the mount itself is pinned here.
    checks: (src) => {
      const errs = [];
      const i = src.indexOf('<SupportLevels');
      if (i < 0) return ['SupportLevels mount missing from SepaCandidate'];
      const tag = src.slice(i, src.indexOf('/>', i));
      if (!/\btf=\{/.test(tag)) {
        errs.push('SupportLevels mount lacks tf= — intraday picks cannot render as selected');
      }
      if (!/\bonView=\{/.test(tag)) {
        errs.push('SupportLevels mount lacks onView= — the fallback drops the tf half of every intraday pick');
      }
      return errs;
    },
  },
  {
    name: 'breakout-alert banner caps the visible alert count',
    file: 'src/components/BreakoutAlertBanner.tsx',
    // On a broad down day the scanner fires dozens of stage-breakdown alerts.
    // Without the cap the fixed banner became a full-height wall of red strips
    // that buried the page. This guard locks the cap so it can't vanish again.
    checks: (src) => {
      const errs = [];
      const m = src.match(/const\s+VISIBLE_MAX\s*=\s*(\d+)/);
      if (!m) {
        errs.push('VISIBLE_MAX constant missing — the stack would render ALL alerts and flood the page');
      } else if (Number(m[1]) > 12) {
        errs.push(`VISIBLE_MAX=${m[1]} is too high — the cap should keep the stack compact (<= 12)`);
      }
      if (!/\.slice\(\s*0\s*,\s*VISIBLE_MAX\s*\)/.test(src)) {
        errs.push('alerts.slice(0, VISIBLE_MAX) missing — the cap is defined but never applied');
      }
      if (!/hiddenCount/.test(src) || !/more/.test(src)) {
        errs.push('the "+N more" overflow footer is missing');
      }
      return errs;
    },
  },
  {
    name: 'pivot-meter locks the book entry-timing thresholds',
    file: 'src/lib/pivotTiming.ts',
    // The meter's GO/COILING/EXTENDED states + the "tight pivot" badge encode
    // Minervini's buy rule (pp.198-205): final right-side contraction ≤5%
    // (FSII 5% handle, VIVO 3%) and a volume-confirmed breakout ≥1.5× avg
    // (p.203, "on expanding volume"). Lock the constants so a refactor can't
    // silently loosen them away from the book.
    checks: (src) => {
      const errs = [];
      const tight = src.match(/TIGHT_PIVOT_MAX_PCT\s*=\s*([\d.]+)/);
      if (!tight) errs.push('TIGHT_PIVOT_MAX_PCT missing (the ≤5% textbook-tight pivot, book pp.198/202)');
      else if (Number(tight[1]) !== 5) errs.push(`TIGHT_PIVOT_MAX_PCT=${tight[1]} — should be 5 (book pivot is 3-5%)`);
      const vmult = src.match(/BREAKOUT_VOL_MULT\s*=\s*([\d.]+)/);
      if (!vmult) errs.push('BREAKOUT_VOL_MULT missing (the 1.5× volume breakout threshold, book p.203)');
      else if (Number(vmult[1]) !== 1.5) errs.push(`BREAKOUT_VOL_MULT=${vmult[1]} — should be 1.5 to match backend volume.py`);
      // GO must require BOTH price ≥ pivot AND a confirmed breakout.
      if (!/above\s*&&\s*breakingOut/.test(src)) {
        errs.push("GO state must require `above && breakingOut` (price at pivot AND volume expanding)");
      }
      // Stage-2 gate (2026-06-02, book pp.39-71 stage analysis): a name at/above
      // the pivot but NOT a confirmed Stage 2 setup must NOT flash a green GO —
      // it downgrades to NOT_STAGE2. Mirrors backend entry_exit `_decide`.
      if (!/above\s*&&\s*!eligible/.test(src)) {
        errs.push("meter must gate the buy states on Stage-2 eligibility (`above && !eligible` → NOT_STAGE2)");
      }
      if (!/NOT_STAGE2/.test(src)) {
        errs.push("NOT_STAGE2 state missing — the Stage-2 downgrade for at-pivot non-Stage-2 names");
      }
      return errs;
    },
  },
  {
    name: 'leveraged/inverse ETF guardrail flags 2x/3x products',
    file: 'src/lib/leveragedEtf.ts',
    // Minervini's framework is for individual STOCKS; leveraged/inverse ETFs
    // (TECL, USD, TQQQ, SOXL…) have no fundamentals + daily-rebalance decay +
    // 2–3× drawdowns. Lock the detector so the badge can't silently drop and let
    // a 3× ETF read as a clean SEPA buy (TECL showed up Primed/#2, USD 100%).
    checks: (src) => {
      const errs = [];
      if (!/export function leveragedEtfInfo/.test(src)) {
        errs.push('leveragedEtfInfo export missing — the shared detector is gone');
      }
      for (const t of ['TECL', 'TQQQ', 'SOXL', 'USD', 'SPXL']) {
        if (!src.includes(`'${t}'`)) errs.push(`curated leveraged ticker ${t} missing`);
      }
      if (!/Leveraged ETF/.test(src)) errs.push('"Leveraged ETF" label missing');
      if (!/\[23\]/.test(src)) errs.push('the 2×/3× name pattern is missing');
      return errs;
    },
  },
  {
    name: 'promo board column headers stick until the table ends',
    file: 'src/styles.css',
    // Ajay 2026-09-02: "Keep the headers static on scroll until the end of the
    // table". Two halves, both silent when lost: the sticky rule itself, and the
    // phone-width `.app` / `.main` overflow — `overflow-x: hidden` turns the
    // ancestor into a scroll container and every sticky header inside stops
    // sticking, with no error anywhere.
    checks: (src) => {
      const errs = [];
      const rule = src.match(/\.pcw \.og__table thead th \{[^}]*\}/);
      if (!rule) return ['sticky header rule for .pcw .og__table thead th is missing'];
      if (!/position:\s*sticky/.test(rule[0]) || !/top:\s*calc\(var\(--sticky-top, 0px\) \+ var\(--pcw-title-h\)\)/.test(rule[0])) {
        errs.push('promo table headers are no longer position: sticky under the phone nav (top: var(--sticky-top, 0))');
      }
      const nav = read('src/components/NavBar.tsx');
      if (!/useStickyTop\(mobileBarRef, isMobile\)/.test(nav) || !/cm-nav--mobile" ref=\{mobileBarRef\}/.test(nav)) {
        errs.push('NavBar no longer publishes the phone nav height as --sticky-top — headers slide behind it');
      }
      if (!/background:\s*var\(--bg\)/.test(rule[0])) {
        errs.push('sticky promo headers have no page background — rows show through them');
      }
      // <body> must never be a scroll container either: with <html> already
      // overflow-x:hidden, body's own overflow stops propagating to the
      // viewport and `hidden` there killed every sticky element on the site
      // (2026-09-03, seen on the real page after the replica had passed).
      const bodyRule = src.replace(/\/\*[\s\S]*?\*\//g, '').match(/\nbody \{[^}]*\}/);
      if (!bodyRule || !/overflow-x:\s*clip/.test(bodyRule[0]) || /overflow(-x)?:\s*hidden/.test(bodyRule[0])) {
        errs.push('body must use overflow-x: clip (not hidden) — a body scroll container disables every sticky header');
      }
      if (!/\.pcw \.pcw__table > \.day-section__h \{[^}]*position:\s*sticky/.test(src)) {
        errs.push('promo table titles no longer stick above their headers — a scrolled table cannot be told apart');
      }
      const mq = src.slice(src.indexOf('@media (max-width: 720px)'));
      const block = mq.slice(0, mq.indexOf('}\n}') + 3).replace(/\/\*[\s\S]*?\*\//g, '');   // comments may name the trap
      if (/overflow-x:\s*hidden/.test(block)) {
        errs.push('phone-width .app/.main use overflow-x: hidden — that ancestor scroll container disables sticky headers');
      }
      return errs;
    },
  },
  {
    name: 'notifications page carries the 2026-09-09 keep-set (hot pullback + patterns)',
    file: 'src/pages/Notifications.tsx',
    // Ajay 2026-09-09: "Kill all other.. I just wanna these alerts". A kind the
    // page cannot show cannot be muted, and a kind missing from the backend's
    // default_prefs sends to ZERO devices silently.
    checks: (src) => {
      const errs = [];
      for (const k of ['hot_pullback_alert', 'pattern_alert']) {
        if (!new RegExp(`key:\\s*'${k}'`).test(src)) errs.push(`CATEGORIES lacks ${k} — it cannot be muted from the page`);
      }
      const ess = src.slice(src.indexOf("id: 'essentials'"), src.indexOf("id: 'trading_only'"));
      for (const on of ['hot_pullback_alert', 'pattern_alert', 'demand_alert', 'position_alert']) {
        if (!new RegExp(`${on}:\\s*true`).test(ess)) errs.push(`Essentials preset drops ${on} — it is in the keep-set`);
      }
      for (const off of ['zone_bounce_alert', 'supply_break_alert', 'promo_alert', 'todo_reminder']) {
        if (!new RegExp(`${off}:\\s*false`).test(ess)) errs.push(`Essentials preset must mute ${off} — he killed it`);
      }
      // the honest record must ride on the page, not just in the push
      if (!/INCLUDES ZERO/.test(src)) errs.push('Hot Pullback detail drops the interval that includes zero');
      if (!/NOT ONE BEATS CHANCE/.test(src)) errs.push('Chart-pattern detail drops the placebo comparison');
      return errs;
    },
  },
  {
    name: 'notifications page registers the demand_alert kind (2026-09-03)',
    file: 'src/pages/Notifications.tsx',
    // backend/push/subs.py defaults the kind on; a kind the page cannot show
    // cannot be muted, and a muted-by-accident kind is a silent drop
    // (memory: cheetah_push_silent_drops). Essentials must keep it on — it is
    // an enter-zone alert, the preset's whole meaning.
    checks: (src) => {
      const errs = [];
      if (!/key:\s*'demand_alert'/.test(src)) errs.push("CATEGORIES lacks the demand_alert kind — it cannot be muted from the page");
      const ess = src.slice(src.indexOf("id: 'essentials'"), src.indexOf("id: 'trading_only'"));
      if (!/demand_alert:\s*true/.test(ess)) errs.push('Essentials preset drops demand_alert');
      return errs;
    },
  },
  {
    name: 'SEPA page defaults to the Supply / Demand tab (2026-09-03)',
    file: 'src/pages/SepaCandidate.tsx',
    // Ajay 2026-09-03: "when ever I click on SEPA I need it to go Supply and
    // Demand tab in all pages." The rule lives in lib/sepaTabs.ts
    // (DEFAULT_TAB = 'supply'); the page must use it and must not regrow the
    // old `?? 'chart'` fallback beside it.
    checks: (src) => {
      const errs = [];
      if (!/import\s*\{[^}]*\bresolveSepaTab\b[^}]*\}\s*from\s*'\.\.\/lib\/sepaTabs'/.test(src)) {
        errs.push("SepaCandidate.tsx no longer imports resolveSepaTab from '../lib/sepaTabs'");
      }
      if (src.includes("?? 'chart'")) errs.push("SepaCandidate.tsx has regrown the `?? 'chart'` tab fallback");
      return errs;
    },
  },
  {
    name: 'notifications page registers the zone_bounce_alert kind (2026-09-03)',
    file: 'src/pages/Notifications.tsx',
    // Same trap as demand_alert: a push kind the page cannot show cannot be
    // muted, and a muted-by-accident kind is a silent drop
    // (memory: cheetah_push_silent_drops).
    checks: (src) => {
      const errs = [];
      if (!/key:\s*'zone_bounce_alert'/.test(src)) errs.push("CATEGORIES lacks the zone_bounce_alert kind — it cannot be muted from the page");
      return errs;
    },
  },
  {
    name: 'Back in Demand panel opens with the zone-edge board (2026-09-03)',
    file: 'src/components/DemandReentryPanel.tsx',
    // Ajay 2026-09-03: "add #1 stocks in to Demand zone too". The board is a
    // separate component with its own minute clock; drop the mount in a rebase
    // and the page still renders with nothing failing — so the mount is pinned,
    // with its mode (the near-demand side belongs on the Demand board) and its
    // place (on top, before the Back-in-demand help block).
    checks: (src) => {
      const errs = [];
      if (!/import\s*\{[^}]*\bZoneEdgeBoard\b[^}]*\}\s*from\s*'\.\/ZoneEdgeBoard'/.test(src)) {
        errs.push("DemandReentryPanel.tsx no longer imports ZoneEdgeBoard from './ZoneEdgeBoard'");
      }
      const i = src.indexOf('<ZoneEdgeBoard');
      if (i < 0) return [...errs, 'ZoneEdgeBoard mount missing from DemandReentryPanel'];
      const tag = src.slice(i, src.indexOf('/>', i));
      if (!/\bmode="both"/.test(tag)) errs.push('DemandReentryPanel must mount ZoneEdgeBoard with mode="both"');
      const help = src.indexOf('Back in demand</strong>');
      if (help >= 0 && i > help) errs.push('ZoneEdgeBoard must render ABOVE the Back-in-demand help block');
      return errs;
    },
  },
  {
    name: 'Chart Maps Deep Demand is cards only; the zone-edge list stays on the Demand board (2026-09-06)',
    file: 'src/pages/ChartMaps.tsx',
    // Replaces "Deep Demand opens with the breaking-resistance board
    // (2026-09-03)". Ajay 2026-09-06: "change the deep demand to be like In
    // Demand with charts and cards" — the ~200-row text list left this page
    // for the 🚀 Breaking card tab. It must not come back on ANY chart tab,
    // and it must still open the Demand board on /supply-demand (mode="both"),
    // which is where the minute-by-minute list belongs.
    checks: (src) => {
      const errs = [];
      if (/ZoneEdgeBoard/.test(src)) errs.push('ChartMaps.tsx imports or mounts ZoneEdgeBoard again — the text list is back on a chart tab');
      const panel = read('src/components/DemandReentryPanel.tsx');
      if (!/<ZoneEdgeBoard\s+mode="both"/.test(panel)) {
        errs.push('DemandReentryPanel.tsx no longer mounts <ZoneEdgeBoard mode="both"> — the zone-edge list would be gone everywhere');
      }
      return errs;
    },
  },
  {
    name: 'notifications page registers the supply_break_alert kind (2026-09-03)',
    file: 'src/pages/Notifications.tsx',
    // Same trap as demand_alert / zone_bounce_alert: a push kind the page
    // cannot show cannot be muted, and a muted-by-accident kind is a silent
    // drop (memory: cheetah_push_silent_drops). Essentials must keep it on —
    // it is the enter-zone read from the other side of the band.
    checks: (src) => {
      const errs = [];
      if (!/key:\s*'supply_break_alert'/.test(src)) errs.push("CATEGORIES lacks the supply_break_alert kind — it cannot be muted from the page");
      const ess = src.slice(src.indexOf("id: 'essentials'"), src.indexOf("id: 'trading_only'"));
      // 2026-09-09: he killed this kind ("Kill all other"), so Essentials
      // now MUTES it. The kind must still be listed on the page — a kind
      // the page cannot show is a kind he cannot turn back on.
      if (!/supply_break_alert:\s*false/.test(ess)) errs.push('Essentials must mute supply_break_alert since 2026-09-09');
      const hook = read('src/hooks/useNotificationPrefs.ts');
      if (!/supply_break_alert\?:\s*boolean/.test(hook)) errs.push('NotificationPrefs type lacks supply_break_alert — the toggle cannot type-check');
      return errs;
    },
  },
  {
    name: 'service worker re-subscribes on pushsubscriptionchange (2026-09-03)',
    file: 'public/sw.js',
    // The phone's endpoint was purged after a 410 on 2026-09-02 and nothing
    // re-registered it. Endpoints rotate; the worker must heal itself.
    checks: (src) => {
      const errs = [];
      if (!/addEventListener\('pushsubscriptionchange'/.test(src)) errs.push('sw.js has no pushsubscriptionchange listener');
      if (!/\/push\/subscribe/.test(src)) errs.push('sw.js never re-registers with /push/subscribe');
      return errs;
    },
  },
  {
    name: 'app load self-heals the push registration (2026-09-03)',
    file: 'src/App.tsx',
    checks: (src) => (/ensurePushSubscription\(/.test(src) ? [] : ['App.tsx never calls ensurePushSubscription']),
  },
  {
    // Ajay 2026-09-03: "I wanna see the execution time comparison between you
    // and I" — the paper Auto-Pilot's race ledger must stay on the Trading page.
    name: 'Trading page renders the execution race (2026-09-03)',
    file: 'src/pages/Trading.tsx',
    checks: (src) => {
      const errs = [];
      if (!/import\s*\{[^}]*\bExecutionRace\b[^}]*\}\s*from\s*'\.\.\/components\/ExecutionRace'/.test(src)) {
        errs.push("Trading.tsx no longer imports ExecutionRace from '../components/ExecutionRace'");
      }
      if (!/<ExecutionRace\s*\/>/.test(src)) errs.push('Trading.tsx never renders <ExecutionRace />');
      return errs;
    },
  },
  {
    // Ajay 2026-09-03: "Please make a rule to add feedback and analysis of
    // failed trades" — the autopsy table must stay on the Trading page, right
    // under the execution race.
    name: 'Trading page renders the failed-trade autopsies (2026-09-03)',
    file: 'src/pages/Trading.tsx',
    checks: (src) => {
      const errs = [];
      if (!/import\s*\{[^}]*\bTradeAutopsies\b[^}]*\}\s*from\s*'\.\.\/components\/TradeAutopsies'/.test(src)) {
        errs.push("Trading.tsx no longer imports TradeAutopsies from '../components/TradeAutopsies'");
      }
      if (!/<TradeAutopsies\s*\/>/.test(src)) errs.push('Trading.tsx never renders <TradeAutopsies />');
      return errs;
    },
  },
  {
    name: 'Trading page reads the zone-edge paper entry status (2026-09-03)',
    file: 'src/pages/Trading.tsx',
    checks: (src) => (/status\.zone_edge_entry/.test(src) ? [] : ['Trading.tsx never reads status.zone_edge_entry']),
  },
  {
    name: 'Chart Maps carries the ICT tab in the old supply slot (2026-09-03)',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-03 (late): "create a new chart maps tab for ICT Strategy,
    // replace supply tab with this new tab." A rebase that restores the old
    // CM_TABS line would silently bring Into Supply back and drop ICT with
    // every test still green if the ICT describe were lost with it — so the
    // tab list, the slot, the copy and the bookmark redirect are pinned here.
    checks: (src) => {
      const errs = [];
      const m = src.match(/export const CM_TABS:\s*CmTab\[\]\s*=\s*\[([^\]]*)\]/);
      if (!m) return ['CM_TABS declaration not found'];
      const tabs = m[1].split(',').map((s) => s.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
      if (!tabs.includes('ict')) errs.push("CM_TABS lacks 'ict'");
      if (tabs.includes('supply')) errs.push("CM_TABS still lists 'supply' — ICT replaced that slot");
      // 2026-09-06 (most-used first): ICT is a study board that measured no
      // edge (2026-09-04) — it must never lead the strip again.
      if (tabs.indexOf('ict') < tabs.indexOf('quick_bounce')) {
        errs.push("'ict' must sit behind the demand boards (most-used-first order, 2026-09-06)");
      }
      if (!/\n\s*ict:\s*\{/.test(src)) errs.push('TAB_META.ict is missing');
      if (!/if \(t === 'supply'\) return 'ict';/.test(src)) {
        errs.push("parseTab no longer sends ?tab=supply to 'ict' — old bookmarks would fall back to VCP");
      }
      if (!/youtube\.com\/watch\?v=Q7Ryv1M7CvI/.test(src)) {
        errs.push('the ICT source video URL is gone from chartMaps.ts');
      }
      if (/\b(ema|sma|vwap)\b/i.test(src.slice(src.indexOf('ict: {'), src.indexOf('topping: {')))) {
        errs.push('the ICT blurb mentions a moving average — the strategy is purely price action');
      }
      return errs;
    },
  },
  {
    name: 'Chart Maps runs most-used first and counts every tab open (2026-09-06)',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-06: "Move most used tabs to the beginning of the list." No
    // per-tab use had ever been recorded (page views log the pathname only),
    // so the order is a first cut from the boards his alerts and asks land
    // on, and the page now counts every tab open so the next cut is measured.
    // Four halves a rebase could lose one at a time: the leading three, the
    // bare-link default following the first tab, the tracking call, and the
    // highlight that told him the strip moved.
    checks: (src) => {
      const errs = [];
      const m = src.match(/export const CM_TABS:\s*CmTab\[\]\s*=\s*\[([^\]]*)\]/);
      if (!m) return ['CM_TABS declaration not found'];
      const tabs = m[1].split(',').map((s) => s.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
      if (tabs.slice(0, 3).join(',') !== 'zones,deep_demand,quick_bounce') {
        errs.push(`CM_TABS must lead with zones, deep_demand, quick_bounce — got ${tabs.slice(0, 3).join(', ')}`);
      }
      if (!/export const DEFAULT_TAB: CmTab = CM_TABS\[0\];/.test(src)) errs.push('DEFAULT_TAB no longer follows CM_TABS[0]');
      if (!/\? \(t as CmTab\) : DEFAULT_TAB;/.test(src)) {
        errs.push("parseTab's fallback is no longer DEFAULT_TAB — a bare /chart-maps would open elsewhere");
      }
      if (!/export function tabUsageKey\(/.test(src)) errs.push('tabUsageKey helper is gone');
      const page = read('src/pages/ChartMaps.tsx');
      if (!/trackFeature\(tabUsageKey\(tab\)\)/.test(page)) {
        errs.push('ChartMaps.tsx no longer counts tab opens — the order could never be re-cut from use');
      }
      const feats = read('src/lib/newFeatures.ts');
      if (!/id: 'chart-maps-most-used-first'/.test(feats)) errs.push("newFeatures.ts lost the 'chart-maps-most-used-first' highlight");
      return errs;
    },
  },
  {
    name: 'Deep Demand is cards only; the 🚀 breaking read has its own card tab (2026-09-06)',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-06: "Can you change the deep demand to be like In Demand
    // with charts and cards?" The zone-edge breaking list (~200 text rows)
    // used to open the Deep Demand tab above its cards. It is the Breaking
    // tab now, drawn by the backend as the same tile. A rebase that restores
    // the ZoneEdgeBoard mount on ChartMaps.tsx, or drops the tab, would put
    // the text list back with every test green if the describe were lost.
    checks: (src) => {
      const errs = [];
      const m = src.match(/export const CM_TABS:\s*CmTab\[\]\s*=\s*\[([^\]]*)\]/);
      if (!m) return ['CM_TABS declaration not found'];
      const tabs = m[1].split(',').map((s) => s.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
      if (tabs.indexOf('breaking') !== tabs.indexOf('quick_bounce') + 1) {
        errs.push("'breaking' must sit directly after 'quick_bounce'");
      }
      if (!/\n\s*breaking:\s*\{/.test(src)) errs.push('TAB_META.breaking is missing');
      if (!/export function breakingPassText\(/.test(src)) errs.push('chartMaps.ts lost breakingPassText');
      const page = read('src/pages/ChartMaps.tsx');
      if (/ZoneEdgeBoard/.test(page)) errs.push('ChartMaps.tsx mounts ZoneEdgeBoard again — the text list is back on a chart tab');
      if (!/data-testid="breaking-pass"/.test(page)) errs.push('ChartMaps.tsx no longer prints the pass stamp on the Breaking tab');
      const feats = read('src/lib/newFeatures.ts');
      if (!/id: 'breaking-cards-tab'/.test(feats)) errs.push("newFeatures.ts lost the 'breaking-cards-tab' highlight");
      const nav = read('src/lib/navSearch.ts');
      if (!/\/chart-maps\?tab=breaking/.test(nav)) errs.push('navSearch.ts lost the Chart Maps ▸ Breaking entry');
      return errs;
    },
  },
  {
    name: 'Chart Maps time frames carry 2 / 3 / 5 years (2026-09-06)',
    file: 'src/lib/supportLevels.ts',
    // Ajay 2026-09-06: "add 2 years to the time frame ... also add 3 years
    // and then keep 5 years. make sure we have this in all the chart map
    // calculations and dropdown time frames." Three lists a rebase could
    // trim one at a time: the Support zoom fallback, the merged chart views,
    // and the board tabs' Window dropdown.
    checks: (src) => {
      const errs = [];
      const fb = src.match(/export const FALLBACK_WINDOWS[^=]*=\s*\[([\s\S]*?)\];/);
      const keys = fb ? [...fb[1].matchAll(/key:\s*'([^']+)'/g)].map((m) => m[1]) : [];
      if (keys.join(',') !== '1m,3m,6m,1y,2y,3y,5y,all') {
        errs.push(`FALLBACK_WINDOWS is ${keys.join(',') || '(not found)'} — expected 1m,3m,6m,1y,2y,3y,5y,all`);
      }
      for (const k of ['daily:2y', 'daily:3y', 'daily:5y']) {
        if (!src.includes(`key: '${k}'`)) errs.push(`CHART_VIEWS lacks ${k}`);
      }
      const page = read('src/pages/ChartMaps.tsx');
      for (const [v, l] of [['504', '2 years'], ['756', '3 years'], ['1260', '5 years']]) {
        if (!page.includes(`<option value="${v}">${l}</option>`)) errs.push(`ChartMaps.tsx Window dropdown lacks ${l} (${v})`);
      }
      const feats = read('src/lib/newFeatures.ts');
      if (!/id: 'chart-maps-2y-3y-windows'/.test(feats)) errs.push("newFeatures.ts lost the 'chart-maps-2y-3y-windows' highlight");
      // Ajay 2026-09-06 (later): "make support default to 1 year on all the
      // tabs? I think its safer and more accurate." Three constants, one value.
      if (!/export const DEFAULT_WINDOW = '1y';/.test(src)) errs.push("DEFAULT_WINDOW is not '1y' — the Support tab would open on another zoom");
      if (!/export const SEPA_SUPPLY_WINDOW = '1y';/.test(src)) errs.push("SEPA_SUPPLY_WINDOW is not '1y' — the ticker page would open on another zoom");
      if (!/export const DEFAULT_VIEW = 'daily:1y';/.test(src)) errs.push("DEFAULT_VIEW is not 'daily:1y'");
      if (!/id: 'support-default-1y'/.test(feats)) errs.push("newFeatures.ts lost the 'support-default-1y' highlight");
      return errs;
    },
  },
  {
    name: 'Chart Maps carries the Quick Bounce tab with its study strip (2026-09-06)',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-06: "quick bounce potential list ... in one place under
    // chartmaps ... sort them by nearest of the Demand zones again with 5%
    // supply zone." The tab sits right after Deep Demand (the demand boards
    // cluster), is room-gated like them, the page prints the study's own
    // numbers + persistence under the blurb, and the search palette finds it.
    checks: (src) => {
      const errs = [];
      const m = src.match(/export const CM_TABS:\s*CmTab\[\]\s*=\s*\[([^\]]*)\]/);
      if (!m) return ['CM_TABS declaration not found'];
      const tabs = m[1].split(',').map((s) => s.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
      if (tabs.indexOf('quick_bounce') !== tabs.indexOf('deep_demand') + 1) {
        errs.push("'quick_bounce' must sit directly after 'deep_demand'");
      }
      if (!/\n\s*quick_bounce:\s*\{/.test(src)) errs.push('TAB_META.quick_bounce is missing');
      if (!/export function quickBounceStudyText\(/.test(src) || !/export function quickBouncePersistenceText\(/.test(src)) {
        errs.push('chartMaps.ts lost the study / persistence wording helpers');
      }
      const page = read('src/pages/ChartMaps.tsx');
      if (!/data-testid="quick-bounce-study"/.test(page)) errs.push('ChartMaps.tsx no longer prints the study strip');
      if (!/tab === 'quick_bounce'\)\s*&&\s*\(/.test(page)) errs.push('ChartMaps.tsx no longer mounts the ℹ️ Rules pill on the Quick Bounce tab');
      const nav = read('src/lib/navSearch.ts');
      if (!/\/chart-maps\?tab=quick_bounce/.test(nav)) errs.push('navSearch.ts lost the Chart Maps ▸ Quick Bounce entry');
      const feats = read('src/lib/newFeatures.ts');
      if (!/id: 'quick-bounce-tab'/.test(feats)) errs.push("newFeatures.ts lost the 'quick-bounce-tab' highlight");
      return errs;
    },
  },
  {
    name: 'Chart Maps carries the Catalysts tab; /catalysts redirects there (2026-09-05)',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-05: "also move catalyst tab in to Chart maps" + "sort stocks
    // by bigger gaps in to supply" on Catalysts and "bouncing off of demand
    // zone ... big gap in to supply" on the Demand board. Four halves, each
    // silent when lost in a rebase: the tab slot (right after Overnight — both
    // movers boards), the page mounting the board, the old route redirecting
    // (push taps still go to /catalysts?tab=promo), and the Demand board's
    // default sort being the shared bounce·room rule.
    checks: (src) => {
      const errs = [];
      const m = src.match(/export const CM_TABS:\s*CmTab\[\]\s*=\s*\[([^\]]*)\]/);
      if (!m) return ['CM_TABS declaration not found'];
      const tabs = m[1].split(',').map((s) => s.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
      if (!tabs.includes('catalysts')) errs.push("CM_TABS lacks 'catalysts'");
      if (Math.abs(tabs.indexOf('catalysts') - tabs.indexOf('overnight')) !== 1) {
        errs.push("'catalysts' must sit beside 'overnight' (both are movers boards)");
      }
      if (!/\n\s*catalysts:\s*\{/.test(src)) errs.push('TAB_META.catalysts is missing');
      if (!/t !== 'catalysts'/.test(src)) errs.push("isBoardTab still treats 'catalysts' as a board — /chart-maps would be fetched for it");
      const page = read('src/pages/ChartMaps.tsx');
      if (!/import\s*\{[^}]*\bCatalystsBoard\b[^}]*\}\s*from\s*'\.\.\/pages\/Catalysts'/.test(page)) {
        errs.push("ChartMaps.tsx no longer imports CatalystsBoard from '../pages/Catalysts'");
      }
      if (!/tab === 'catalysts'\s*\?\s*\(/.test(page) || !/<CatalystsBoard\s+embedded\s*\/>/.test(page)) {
        errs.push("ChartMaps.tsx does not mount <CatalystsBoard embedded /> for tab === 'catalysts'");
      }
      const cat = read('src/pages/Catalysts.tsx');
      const i = cat.indexOf('export function CatalystsPage()');
      if (i < 0) errs.push('Catalysts.tsx lost the CatalystsPage export — App.tsx route breaks');
      else {
        const body = cat.slice(i, cat.indexOf('\n}\n', i));
        if (!/<Navigate\s+replace/.test(body) || !/\/chart-maps\?tab=catalysts/.test(body)) {
          errs.push('CatalystsPage no longer redirects to /chart-maps?tab=catalysts — old deep links 404 on the moved page');
        }
        if (!/&sub=/.test(body)) errs.push('CatalystsPage drops the sub-tab on redirect — /catalysts?tab=promo would lose promo');
      }
      if (!/export function CatalystsBoard\(/.test(cat)) errs.push('Catalysts.tsx lost the CatalystsBoard export');
      const panel = read('src/components/DemandReentryPanel.tsx');
      if (!/useState<string>\('bounce_room'\)/.test(panel)) {
        errs.push("DemandReentryPanel default sortKey is no longer 'bounce_room' — Ajay asked for bouncing-off-demand first");
      }
      if (!/compareBounceRoom\(/.test(panel)) errs.push('DemandReentryPanel no longer sorts with the shared compareBounceRoom rule');
      return errs;
    },
  },
  {
    name: 'Alerts page exists and the boards carry the alerted-today chip (2026-09-05)',
    file: 'src/App.tsx',
    // Ajay 2026-09-05: "Do we have the same logic in back end demand for the
    // ones that I get alerts. Would it be the same list of stocks.. Also can I
    // go to a dedicated page to see the list of alerts?" The answer is NO (the
    // board is a closed-bar scan with an R:R floor; the phone is gated), and
    // the deliverable is the /alerts page plus the 🔔 overlap chip on both
    // boards. Kind labels must come from ONE registry — the panel's private
    // map is exactly how the three zone kinds went unlabelled for two days.
    checks: (src) => {
      const errs = [];
      if (!/<Route\s+path="\/alerts"\s+element=\{<FeatureRoute\s+feature="alerts">/.test(src)) {
        errs.push('App.tsx does not route /alerts behind <FeatureRoute feature="alerts">');
      }
      if (!/import\('\.\/pages\/Alerts'\)/.test(src)) errs.push('App.tsx no longer lazy-loads pages/Alerts');
      for (const rel of ['src/components/DemandReentryPanel.tsx', 'src/components/ZoneEdgeBoard.tsx']) {
        const s = read(rel);
        if (!/import\s*\{[^}]*\buseAlertedToday\b[^}]*\}\s*from\s*'\.\.\/hooks\/useAlertHistory'/.test(s)) {
          errs.push(`${rel} no longer imports useAlertedToday — the 🔔 alerted-today chip is gone from that board`);
        }
        if (!/<AlertedTodayChip\b/.test(s)) errs.push(`${rel} does not render <AlertedTodayChip>`);
      }
      const panel = read('src/components/PushHistoryPanel.tsx');
      if (!/import\s*\{[^}]*\bkindLabel\b[^}]*\}\s*from\s*'\.\.\/lib\/alertKinds'/.test(panel)) {
        errs.push("PushHistoryPanel.tsx does not import kindLabel from '../lib/alertKinds'");
      }
      if (/const\s+KIND_LABEL\b/.test(panel)) errs.push('PushHistoryPanel.tsx has regrown a private KIND_LABEL map — labels must come from lib/alertKinds');
      const kinds = read('src/lib/alertKinds.ts');
      for (const k of ['demand_alert', 'zone_bounce_alert', 'supply_break_alert']) {
        if (!new RegExp(`^\\s*${k}:\\s*\\{`, 'm').test(kinds)) errs.push(`lib/alertKinds.ts lacks the ${k} kind`);
      }
      if (!/ZONE_KINDS[^=]*=\s*\['demand_alert',\s*'zone_bounce_alert',\s*'supply_break_alert'\]/.test(kinds)) {
        errs.push('ZONE_KINDS is not exactly the three phone-gated zone kinds');
      }
      const nav = read('src/lib/navSource.ts');
      if (!/^\s*alerts:\s*\{\s*path:\s*'\/alerts'/m.test(nav)) errs.push("navSource.ts lacks the 'alerts' back-source — ticker links from /alerts would fall back to /sepa");
      // Review 2026-09-05: the chip claims the phone RANG. A send_to_user call
      // with nobody targeted (muted kind, dead subscription) is recorded too,
      // so the reducer must drop undelivered rows; and the chip poll must
      // actually re-read each minute (TTL below the poll interval).
      const hook = read('src/hooks/useAlertHistory.ts');
      const reducer = hook.slice(hook.indexOf('export function useAlertedToday'));
      if (!/if\s*\(!wasDelivered\(r\)\)\s*continue;/.test(reducer)) errs.push('useAlertedToday no longer skips undelivered rows (wasDelivered) — the 🔔 chip would mark names whose push reached zero devices');
      const ttl = Number((hook.match(/ALERTED_TODAY_TTL_MS\s*=\s*([\d_]+)/) || [])[1]?.replace(/_/g, ''));
      const poll = Number((hook.match(/ALERTED_TODAY_POLL_MS\s*=\s*([\d_]+)/) || [])[1]?.replace(/_/g, ''));
      if (!(ttl > 0 && poll > 0 && ttl < poll)) errs.push(`ALERTED_TODAY_TTL_MS (${ttl}) must be below ALERTED_TODAY_POLL_MS (${poll}) or the minute tick skips the fetch`);
      // The status strip must render each pass's own `reason` and judge stamps
      // against cadence — "in_session" is the clock, not proof the crons live.
      const page = read('src/pages/Alerts.tsx');
      if (!/pass\?\.reason\b/.test(page) || !/data-testid="pass-reason"/.test(page)) errs.push("Alerts.tsx no longer renders a pass's `reason` — a cold store would read as a quiet day");
      if (!/export function passHealth\(/.test(page) || !/'stale'/.test(page)) errs.push('Alerts.tsx lost the cadence-based stale read (passHealth) — a dead cron would read as "passes running"');
      if (/In session — passes running/.test(page)) errs.push('Alerts.tsx says "In session — passes running" — that is inferred from the clock, never from evidence');
      return errs;
    },
  },
  {
    name: 'Room floor on the boards + three Auto-Pilot lanes on the Trading page (2026-09-05)',
    file: 'src/lib/bounceRoom.ts',
    // Ajay 2026-09-05, three asks in one afternoon: (1) "What ever rules I
    // created for the alerts are the ideal conditions for a stock to be bough
    // in Autopilot. Keep the minervini entries but also make sure you have
    // demand zone and catalyst based entries time to time and journal it
    // appropriately." (2) "I need the same logic in Demand and deep demand
    // zone. So that there are stocks that have more room atleast >5%".
    // (3) TRU: "It already gapped up very close to the resistance. Why is it
    // still in in Demand page? There is only 0.5% room". Each half is silent
    // when lost in a rebase: the FE floor drifting from the alert gate's 5,
    // the Demand panel or Chart Maps no longer asking the server for the
    // floor, the Trading page dropping the per-lane table or the catalyst
    // card. Owner settings for the Supply & Demand strategy — no book cites.
    checks: (src) => {
      const errs = [];
      const m = src.match(/export const ROOM_MIN_PCT\s*=\s*([\d.]+)\s*;/);
      if (!m) errs.push('bounceRoom.ts lost ROOM_MIN_PCT');
      else if (Number(m[1]) !== 5) errs.push(`ROOM_MIN_PCT is ${m[1]} — must mirror ALERT_MIN_ROOM_PCT = 5.0 (backend/supply_demand/alert_gates.py)`);
      if (!/export function roomGroup\(/.test(src) || !/export function roomOk\(/.test(src)) {
        errs.push('bounceRoom.ts lost roomOk / roomGroup — the sort no longer puts bounces INTO supply under room-ok rows');
      }
      const cmp = src.slice(src.indexOf('export function compareBounceRoom'));
      if (!/roomGroup\(a\)/.test(cmp.slice(0, 400))) errs.push('compareBounceRoom no longer keys on roomGroup first');
      const cm = read('src/lib/chartMaps.ts');
      const dm = cm.match(/export const DEFAULT_MIN_ROOM\s*=\s*([\d.]+)\s*;/);
      if (!dm || Number(dm[1]) !== 5) errs.push('chartMaps.ts DEFAULT_MIN_ROOM must be 5 (same owner setting)');
      if (!/export const ROOM_TABS:\s*CmTab\[\]\s*=\s*\['zones',\s*'deep_demand',\s*'quick_bounce',\s*'breaking'\]/.test(cm)) {
        errs.push("chartMaps.ts ROOM_TABS is not exactly ['zones', 'deep_demand', 'quick_bounce', 'breaking'] (Quick Bounce joined the room-gated boards 2026-09-06)");
      }
      if (!/q\.set\('min_room'/.test(cm)) errs.push('boardQuery no longer sends min_room');
      const panel = read('src/components/DemandReentryPanel.tsx');
      if (!/&min_room=\$\{encodeURIComponent\(minRoom\)\}/.test(panel)) {
        errs.push('DemandReentryPanel no longer sends min_room on the demand-reentry GET / POST');
      }
      if (!/aria-label="Room floor"/.test(panel)) errs.push('DemandReentryPanel lost the Room floor selector');
      if (!/dropped_low_room/.test(panel)) errs.push('DemandReentryPanel no longer reports dropped_low_room');
      const page = read('src/pages/ChartMaps.tsx');
      if (!/aria-label="Room floor"/.test(page)) errs.push('ChartMaps lost the Room floor control');
      const gate = page.slice(Math.max(0, page.indexOf('aria-label="Room floor"') - 260), page.indexOf('aria-label="Room floor"'));
      if (!/\{ROOM_TAB && \(/.test(gate)) errs.push('ChartMaps Room floor control is not gated on ROOM_TAB (zones / deep_demand only)');
      if (!/hidden_low_room/.test(page)) errs.push('ChartMaps no longer reports hidden_low_room');
      if (!/minRoom:\s*ROOM_TAB \? minRoom : undefined/.test(page)) errs.push('ChartMaps no longer passes minRoom into boardQuery for the two demand boards');
      const tr = read('src/pages/Trading.tsx');
      if (!/import\s*\{[^}]*\bJournalByStrategy\b[^}]*\}\s*from\s*'\.\.\/components\/JournalByStrategy'/.test(tr)) {
        errs.push("Trading.tsx no longer imports JournalByStrategy from '../components/JournalByStrategy'");
      }
      if (!/<JournalByStrategy\s+byStrategy=\{j\.summary\?\.by_strategy\}/.test(tr)) errs.push('Trading.tsx JournalView does not mount <JournalByStrategy byStrategy={j.summary?.by_strategy}>');
      if (!/<StrategyChip\s+strategy=\{t\.entry\?\.strategy\}/.test(tr)) errs.push('TradeCard lost its lane chip (StrategyChip from trade.entry.strategy)');
      if (!/import\s*\{[^}]*\bCatalystEntryCard\b[^}]*\}\s*from\s*'\.\.\/components\/CatalystEntryCard'/.test(tr)) {
        errs.push("Trading.tsx no longer imports CatalystEntryCard from '../components/CatalystEntryCard'");
      }
      if (!/status\.catalyst_entry\s*&&\s*\(\s*<CatalystEntryCard\s+c=\{status\.catalyst_entry\}/.test(tr)) {
        errs.push('Trading.tsx does not mount <CatalystEntryCard c={status.catalyst_entry}> gated on the object');
      }
      const card = read('src/components/CatalystEntryCard.tsx');
      if (!/catalyst_entry:\s*enabled/.test(card) || !/\/trading\/config/.test(card)) {
        errs.push('CatalystEntryCard no longer POSTs {catalyst_entry} to /trading/config');
      }
      if (/TLSW|TTLAC|Minervini p\./.test(card) || /TLSW|TTLAC|Minervini p\./.test(src)) {
        errs.push('owner-rule files (bounceRoom.ts / CatalystEntryCard.tsx) must carry no book cites');
      }
      const nf = read('src/lib/newFeatures.ts');
      for (const id of ['autopilot-three-lanes', 'demand-room-floor', 'chart-maps-room-floor']) {
        if (!new RegExp(`id:\\s*'${id}'`).test(nf)) errs.push(`newFeatures.ts lacks the '${id}' highlight`);
      }
      return errs;
    },
  },
  {
    name: 'Trading page carries the Options lane tab (2026-09-06)',
    file: 'src/pages/Trading.tsx',
    // Ajay 2026-09-06: "create a new tab on the Auto pilot on options trading
    // and paper trade with it." The tab is a paper OPTIONS lane on the demand-
    // zone touch (owner rules, S/D scope — no book cites). Pinned: the View
    // union + VIEWS carry `options`, the page mounts <OptionsLaneTab> on that
    // view, the tab's two writes are exactly {options_entry} on /trading/config
    // and /trading/options/close/{underlying}, and the Journal's by-lane table
    // labels the lane's `options_zone` key "🎛️ Options".
    checks: (src) => {
      const errs = [];
      if (!/import\s*\{[^}]*\bOptionsLaneTab\b[^}]*\}\s*from\s*'\.\.\/components\/OptionsLaneTab'/.test(src)) {
        errs.push("Trading.tsx no longer imports OptionsLaneTab from '../components/OptionsLaneTab'");
      }
      if (!/export\s+type\s+View\s*=[^;]*'options'/.test(src)) errs.push("Trading.tsx View type lost 'options'");
      if (!/\{\s*key:\s*'options'\s*,\s*label:\s*'Options'\s*\}/.test(src)) errs.push("VIEWS no longer carries { key: 'options', label: 'Options' }");
      if (!/view\s*===\s*'options'\s*&&\s*<OptionsLaneTab\b/.test(src)) errs.push("Trading.tsx does not mount <OptionsLaneTab> on view === 'options'");
      if (!/parseView\(params\.get\('view'\)\)/.test(src)) errs.push('Trading.tsx no longer reads ?view= from the URL (deep links / the ✨ NEW route break)');
      if (!/options_lane\?:\s*OptionsLaneStatus\s*\|\s*null/.test(src)) errs.push('Status type lost the optional options_lane block');
      const tab = read('src/components/OptionsLaneTab.tsx');
      if (!/options_entry:\s*enabled/.test(tab) || !/\/trading\/config/.test(tab)) {
        errs.push('OptionsLaneTab no longer POSTs {options_entry} to /trading/config');
      }
      if (!/\/trading\/options\/close\/\$\{encodeURIComponent\(symbol\)\}/.test(tab)) {
        errs.push('OptionsLaneTab no longer POSTs /trading/options/close/{underlying}');
      }
      if (!/\$\{API\}\/trading\/options`/.test(tab)) errs.push('OptionsLaneTab no longer polls GET /trading/options');
      if (!/setClosing\(p\.symbol\)/.test(tab) || !/role="dialog"\s+aria-label=\{`Close \$\{closing\} options\?`\}/.test(tab)) {
        errs.push('the Close button lost its confirm dialog — a close must never fire on one click');
      }
      if (/TLSW|TTLAC|Minervini p\./.test(tab)) errs.push('OptionsLaneTab is S/D scope — it must carry no book cites');
      const jbs = read('src/components/JournalByStrategy.tsx');
      if (!/options_zone:\s*\{\s*glyph:\s*'🎛️',\s*label:\s*'Options'/.test(jbs)) {
        errs.push("JournalByStrategy no longer labels options_zone as '🎛️ Options'");
      }
      if (!/'options_zone'/.test(jbs.slice(jbs.indexOf('export type StrategyKey'), jbs.indexOf('export type StrategyKey') + 200))) {
        errs.push('StrategyKey lost options_zone');
      }
      const nf = read('src/lib/newFeatures.ts');
      if (!/id:\s*'autopilot-options-lane'[^}]*route:\s*'\/trading\?view=options'/.test(nf)) {
        errs.push("newFeatures.ts lacks the 'autopilot-options-lane' highlight routed to /trading?view=options");
      }
      return errs;
    },
  },
  {
    name: 'Trading page carries the 0DTE paper lane tab (2026-09-08)',
    file: 'src/pages/Trading.tsx',
    // Ajay 2026-09-08: "Did you start the ODTE options". A paper SAME-DAY
    // options lane on Signal Lab tags (owner rules, day-trading scope — no
    // book cites). Pinned: View + VIEWS carry `zero_dte`, the page mounts
    // <ZeroDteLaneTab> on that view, the tab's two writes are exactly
    // {zero_dte_entry} on /trading/config and /trading/zero-dte/close/{symbol},
    // the close has a confirm dialog, and the highlight routes to the tab.
    checks: (src) => {
      const errs = [];
      if (!/import\s*\{[^}]*\bZeroDteLaneTab\b[^}]*\}\s*from\s*'\.\.\/components\/ZeroDteLaneTab'/.test(src)) {
        errs.push("Trading.tsx no longer imports ZeroDteLaneTab from '../components/ZeroDteLaneTab'");
      }
      if (!/export\s+type\s+View\s*=[^;]*'zero_dte'/.test(src)) errs.push("Trading.tsx View type lost 'zero_dte'");
      if (!/\{\s*key:\s*'zero_dte'\s*,\s*label:\s*'0DTE'\s*\}/.test(src)) errs.push("VIEWS no longer carries { key: 'zero_dte', label: '0DTE' }");
      if (!/view\s*===\s*'zero_dte'\s*&&\s*<ZeroDteLaneTab\b/.test(src)) errs.push("Trading.tsx does not mount <ZeroDteLaneTab> on view === 'zero_dte'");
      const tab = read('src/components/ZeroDteLaneTab.tsx');
      if (!/zero_dte_entry:\s*next/.test(tab) || !/\/trading\/config/.test(tab)) {
        errs.push('ZeroDteLaneTab no longer POSTs {zero_dte_entry} to /trading/config');
      }
      if (!/\/trading\/zero-dte\/close\/\$\{encodeURIComponent\(symbol\)\}/.test(tab)) {
        errs.push('ZeroDteLaneTab no longer POSTs /trading/zero-dte/close/{symbol}');
      }
      if (!/\$\{API\}\/trading\/zero-dte`/.test(tab)) errs.push('ZeroDteLaneTab no longer polls GET /trading/zero-dte');
      if (!/setClosing\(p\.symbol\)/.test(tab) || !/role="dialog"\s+aria-label=\{`Close \$\{closing\} 0DTE\?`\}/.test(tab)) {
        errs.push('the Close button lost its confirm dialog — a close must never fire on one click');
      }
      if (/TLSW|TTLAC|Minervini p\./.test(tab)) errs.push('ZeroDteLaneTab is day-trading scope — it must carry no book cites');
      const nf = read('src/lib/newFeatures.ts');
      if (!/id:\s*'autopilot-zero-dte-lane'[^}]*route:\s*'\/trading\?view=zero_dte'/.test(nf)) {
        errs.push("newFeatures.ts lacks the 'autopilot-zero-dte-lane' highlight routed to /trading?view=zero_dte");
      }
      return errs;
    },
  },
  {
    name: 'NavBar carries the global search palette (2026-09-06)',
    file: 'src/components/NavBar.tsx',
    // Ajay 2026-09-06: "give me a global search navigation like if I wanna
    // search or related like notification I want them to show up from all the
    // navigational menu." The palette must stay mounted in BOTH nav layouts
    // (desktop meta cluster + phone action bar), and the synonym map must keep
    // the two-way notification ↔ alerts bridge that motivated the feature.
    checks: (src) => {
      const errs = [];
      if (!/import\s*\{[^}]*\bGlobalSearch\b[^}]*\}\s*from\s*'\.\/GlobalSearch'/.test(src)) {
        errs.push("NavBar.tsx no longer imports GlobalSearch from './GlobalSearch'");
      }
      const mounts = src.match(/<GlobalSearch\b/g) || [];
      if (mounts.length < 2) {
        errs.push(`NavBar.tsx mounts <GlobalSearch> ${mounts.length}× — needs the desktop meta cluster AND the phone action bar`);
      }
      if (!/<GlobalSearch\s+compact\b/.test(src)) {
        errs.push('the phone action bar lost its compact <GlobalSearch compact> mount');
      }
      const ns = read('src/lib/navSearch.ts');
      if (!/export\s+const\s+NAV_SYNONYMS\s*:/.test(ns)) {
        errs.push('navSearch.ts no longer exports NAV_SYNONYMS');
      }
      if (!/^\s*notifications\s*:\s*\[/m.test(ns)) errs.push("NAV_SYNONYMS lacks the 'notifications' key");
      if (!/^\s*alerts\s*:\s*\[/m.test(ns)) errs.push("NAV_SYNONYMS lacks the 'alerts' key");
      if (!/notifications\s*:\s*\[[^\]]*'alerts'/.test(ns)) errs.push("'notifications' synonyms no longer include 'alerts'");
      if (!/alerts\s*:\s*\[[^\]]*'notification'/.test(ns)) errs.push("'alerts' synonyms no longer include 'notification'");
      const nf = read('src/lib/newFeatures.ts');
      if (!/id:\s*'global-search'/.test(nf)) errs.push("newFeatures.ts lacks the 'global-search' highlight");
      return errs;
    },
  },
  {
    name: 'NavBar carries the IV badge beside the Market Gauge (2026-09-06)',
    file: 'src/components/NavBar.tsx',
    // Ajay 2026-09-06: "Do we have an IV indicator in our pages? can you add
    // that to our regular used pages as a global indicator? May be beside
    // Market gauge metric?" The badge must stay mounted in BOTH nav layouts
    // (desktop meta cluster + phone action bar, compact there), and the
    // stress regime must keep its own colour rule so a hot tape reads red.
    checks: (src) => {
      const errs = [];
      if (!/import\s*\{[^}]*\bIvBadge\b[^}]*\}\s*from\s*'\.\/IvBadge'/.test(src)) {
        errs.push("NavBar.tsx no longer imports IvBadge from './IvBadge'");
      }
      const mounts = src.match(/<IvBadge\b/g) || [];
      if (mounts.length < 2) {
        errs.push(`NavBar.tsx mounts <IvBadge> ${mounts.length}× — needs the desktop meta cluster AND the phone action bar`);
      }
      if (!/<IvBadge\s+compact\b/.test(src)) {
        errs.push('the phone action bar lost its compact <IvBadge compact> mount');
      }
      if (!/hasGauge\s*&&\s*<IvBadge\b/.test(src)) {
        errs.push('IvBadge is no longer gated by hasGauge — it must follow the Market Gauge badge');
      }
      const css = read('src/styles.css');
      if (!/\.iv-badge--stress\s*\{/.test(css)) {
        errs.push('styles.css lacks the .iv-badge--stress rule — the stress regime would render unstyled');
      }
      return errs;
    },
  },

  {
    name: 'Breaking tab prints the last-lid-break study (2026-09-07)',
    file: 'src/pages/ChartMaps.tsx',
    // Ajay 2026-09-07: "I would like to understand when the last resistance
    // break will the price go to ATH." The weekly study (supply_demand/
    // lid_break.py) is printed under the 🚀 Breaking pass line with its
    // placebo and n, and the page must say the 2-year frame high stands in
    // for the all-time high — a study line, never a rule.
    checks: (src) => {
      const errs = [];
      if (!/\blidBreakStudyText\b/.test(src)) errs.push('ChartMaps.tsx no longer imports lidBreakStudyText');
      if (!/data-testid="lid-break-study"/.test(src)) errs.push('the lid-break study line (data-testid="lid-break-study") is gone');
      if (!/tab === 'breaking' && data\?\.lid_break/.test(src)) errs.push('the study line must be gated on the breaking tab + data.lid_break');
      if (!/stands in for the all-time high/.test(src)) errs.push('the page must say the frame high stands in for the all-time high');
      const lib = read('src/lib/chartMaps.ts');
      if (!/export function lidBreakStudyText/.test(lib)) errs.push('chartMaps.ts lost lidBreakStudyText');
      if (!/from any up-day/.test(lib)) errs.push('the study text must print the up-day placebo');
      return errs;
    },
  },

  {
    name: 'Every board card and the promo list carry the one-click + Signals button (2026-09-07)',
    file: 'src/components/PatternChart.tsx',
    // Ajay 2026-09-07: "One click and add to signals tab ... Same from
    // Gabbars and strong VCP and from Quick Bounce ... signals is like my
    // watch list." One store (useSignalWatchlist) behind the cards, the promo
    // rows AND the Signals board, so a click anywhere shows up on the tab.
    checks: (src) => {
      const errs = [];
      if (!/import\s*\{\s*SignalWatchButton\s*\}\s*from\s*'\.\/SignalWatchButton'/.test(src)) errs.push('PatternChart.tsx no longer imports SignalWatchButton');
      if (!/<SignalWatchButton symbol=\{tile\.symbol\}/.test(src)) errs.push('PatternChart.tsx no longer mounts <SignalWatchButton symbol={tile.symbol}>');
      const promo = read('src/components/PromoCircuit.tsx');
      if (!/<SignalWatchButton symbol=\{ticker\}/.test(promo)) errs.push('PromoCircuit.tsx ticker cell lost its + Signals button');
      const board = read('src/components/SignalLabBoard.tsx');
      if (!/useSignalWatchlist\(\)/.test(board)) errs.push('SignalLabBoard.tsx must render the shared store (useSignalWatchlist), not its own list');
      const hook = read('src/hooks/useSignalWatchlist.ts');
      if (!/export const MAX_SYMBOLS = 12;/.test(hook)) errs.push('useSignalWatchlist MAX_SYMBOLS must stay 12 (backend daytrading/signal_lab.MAX_SYMBOLS)');
      if (!/export const LS_KEY = 'signal-lab-symbols';/.test(hook)) errs.push("useSignalWatchlist must keep the board's localStorage key 'signal-lab-symbols'");
      return errs;
    },
  },

  {
    name: '"/" lands on Chart Maps for everyone (2026-09-07)',
    file: 'src/App.tsx',
    // Ajay 2026-09-07: "Make chart maps default loading page for me on the
    // app load. Also for everyone." SmartLanding must resolve through
    // lib/landing.pickLanding, and Chart Maps must lead BOTH chains (the
    // backend catalog grants it to every account by default since v24).
    checks: (src) => {
      const errs = [];
      if (!/pickLanding\(f\.features, !!menu\.is_admin\)/.test(src)) errs.push('SmartLanding no longer resolves through pickLanding');
      if (/PREFERRED_ORDER/.test(src)) errs.push('the old inline PREFERRED_ORDER is back in App.tsx');
      const lib = read('src/lib/landing.ts');
      if (!/admin: \['chart-maps'/.test(lib)) errs.push("landing.ts: 'chart-maps' must lead the admin chain");
      if (!/user: \['chart-maps'/.test(lib)) errs.push("landing.ts: 'chart-maps' must lead the user chain");
      return errs;
    },
  },
  {
    name: 'Chart Maps names the extended-hours tape under every board (2026-09-08)',
    file: 'src/pages/ChartMaps.tsx',
    // Ajay 2026-09-08 (ORCL): "show real time premarket and extended hours
    // trading info as well in all the chart maps." Outside RTH the backend
    // moves every tile's now line to the live print; the page must say so on
    // EVERY tab (not only Breaking) and the wording must state the push window
    // (4:00–20:00 ET since the same afternoon: "Make phone push also pre and post market").
    checks: (src) => {
      const errs = [];
      if (!/data-testid="session-note"/.test(src)) errs.push('the session note is gone from ChartMaps.tsx');
      if (!/sessionNoteText\(data\.tape_session\)/.test(src)) errs.push('the session note must read data.tape_session via sessionNoteText');
      const lib = read('src/lib/chartMaps.ts');
      if (!/phone pushes are on from 4:00 ET/.test(lib)) errs.push('the pre-market note must say pushes are on from 4:00 ET');
      if (!/phone pushes stay on until 20:00 ET/.test(lib)) errs.push('the after-hours note must say pushes run until 20:00 ET');
      return errs;
    },
  },
  {
    name: 'Signals tab leads with the Ready-to-enter section (2026-09-09)',
    file: 'src/components/SignalLabBoard.tsx',
    // Ajay 2026-09-09: "I wanna see this category in the signals page with a
    // section for it." Pinned: the board imports PremarketEntry and mounts it
    // BEFORE the watchlist controls, so it leads the tab rather than trailing
    // the tiles.
    checks: (src) => {
      const errs = [];
      if (!/import\s*\{[^}]*\bPremarketEntry\b[^}]*\}\s*from\s*'\.\/PremarketEntry'/.test(src)) {
        errs.push("SignalLabBoard.tsx no longer imports PremarketEntry from './PremarketEntry'");
      }
      if (!/<PremarketEntry\s*\/>/.test(src)) errs.push('SignalLabBoard.tsx no longer mounts <PremarketEntry />');
      const mount = src.indexOf('<PremarketEntry');
      const controls = src.indexOf('slab-controls');
      if (mount < 0 || controls < 0 || mount > controls) {
        errs.push('PremarketEntry must mount BEFORE the slab-controls block so the section leads the tab');
      }
      return errs;
    },
  },
  {
    name: 'Ready-to-enter grades never read mood (2026-09-09)',
    file: 'src/components/PremarketEntry.tsx',
    // The mood watcher was DELETED on 2026-09-08 after a wrong DYN sell. Mood
    // came back as context only. The frontend must not reintroduce it as a
    // decision: grading happens in the backend, and this file may only render
    // `mood_txt`. Pinned: no grade is computed here from a mood value.
    checks: (src) => {
      const errs = [];
      if (!/mood_txt/.test(src)) errs.push('PremarketEntry.tsx no longer renders mood_txt (mood must stay visible as context)');
      if (/context only/.test(src) === false) errs.push("PremarketEntry.tsx no longer labels mood 'context only'");
      // An ASSIGNMENT to a grade (`grade =`, not the comparison `grade ===`)
      // whose right-hand side mentions mood, on the same line. The greedy
      // `[^;]*` version matched `grade === 'READY'` and then ran forward to an
      // unrelated `mood_txt` several lines later.
      const badGrade = src.split('\n').some((ln) => /\bgrade\s*=(?!=)/.test(ln) && /mood/i.test(ln));
      if (badGrade) errs.push('PremarketEntry.tsx derives a grade from mood — mood is context, never a gate');
      if (!/GRADES\s*=\s*\['READY',\s*'WATCH',\s*'BLOCKED'\]/.test(src)) {
        errs.push('PremarketEntry.tsx lost the three-grade vocabulary');
      }
      return errs;
    },
  },
  {
    name: 'Hot Pullback prints its expectancy AND the interval (2026-09-09, corrected)',
    file: 'src/components/HotPullbackBoard.tsx',
    // This board shipped on 2026-09-09 advertising 58% win / +0.27R off a
    // backtest whose event window started at bar 300 instead of 252, deleting
    // the sample's worst week. Corrected the same day to 51.8% / +0.10R with a
    // 95% interval of [-0.18R, +0.40R] — which INCLUDES ZERO.
    //
    // A point estimate with no interval is precisely what let the wrong number
    // sit on a board he sizes real money off. So the interval is pinned to the
    // screen, the correction must be stated rather than quietly applied, and
    // the invalidated figures may never reappear.
    checks: (src) => {
      const errs = [];
      if (!/studyLine/.test(src)) errs.push('HotPullbackBoard.tsx lost studyLine — the measured line must lead the board');
      if (!/NO MEASURED EDGE/.test(src)) errs.push('the study line no longer leads with the null result');
      if (!/includes zero/.test(src)) errs.push('the study line no longer says the interval includes zero');
      if (!/ci_lo_r/.test(src) || !/ci_hi_r/.test(src)) errs.push('the confidence interval is no longer rendered');
      if (!/correctionLine/.test(src)) errs.push('the correction notice was removed — a silent correction is how this happened');
      // Strip comments and the correction notice itself: both are allowed to
      // name the old figures, because explaining the correction is the point.
      const live = src
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/^\s*\/\/.*$/gm, '')
        .replace(/CORRECTION_TEXT[\s\S]*?;/, '');
      for (const gone of ['2\\.40', '2\\.85', '0\\.27R', 'gone by day five']) {
        if (new RegExp(gone).test(live)) {
          errs.push(`an invalidated 2026-09-09 figure (${gone}) is back outside the correction notice`);
        }
      }
      if (!/plan\.horizon/.test(src)) errs.push('the row no longer prints plan.horizon beside the entry');
      if (!/data\?\.study/.test(src) && !/data\.study/.test(src)) {
        errs.push('the study block must come from the payload, not be typed into the component');
      }
      // no hard-coded strategy thresholds in the UI
      if (/const\s+(FALL|UNDER_MA|OFF_LOW|RANGE_POS)/.test(src)) {
        errs.push('a strategy threshold is hard-coded in the component — it belongs in supply_demand/hot_pullback.py');
      }
      return errs;
    },
  },
  {
    name: 'Chart Maps carries the Hot Pullback tab (2026-09-09)',
    file: 'src/lib/chartMaps.ts',
    checks: (src) => {
      const errs = [];
      if (!/'hot_pullback'/.test(src)) errs.push("CmTab union lost 'hot_pullback'");
      if (!/CM_TABS[^=]*=\s*\[[^\]]*'hot_pullback'/.test(src)) errs.push("CM_TABS no longer lists 'hot_pullback'");
      if (!/hot_pullback:\s*\{[\s\S]*?label:/.test(src)) errs.push('TAB_META has no hot_pullback entry');
      if (!/t !== 'hot_pullback'/.test(src)) errs.push('isBoardTab must exclude hot_pullback — it has its own endpoint and renderer');
      const meta = /hot_pullback:\s*\{[\s\S]*?\},/.exec(src);
      if (meta && !/gone by day five|GONE by day five|by day five/i.test(meta[0])) {
        errs.push('the Hot Pullback blurb must state that the edge dies by day five');
      }
      return errs;
    },
  },
  // Ajay 2026-09-09: "Instead of bounce use the word reversal from Demand zone
  // or something I have trauma with that word now cuz I caught falliing knives
  // with it". The kind KEY stays zone_bounce_alert on purpose — that is the
  // stored value on both devices' prefs and in push_history; only the words he
  // reads moved. This pins the words.
  {
    name: 'no zone alert label says "bounce" to him (2026-09-09)',
    file: 'src/lib/alertKinds.ts',
    checks: (src) => {
      const errs = [];
      const m = src.match(/zone_bounce_alert:\s*\{[^}]*\}/);
      if (!m) return ['zone_bounce_alert must stay registered under its own key'];
      if (/bounce/i.test(m[0].replace('zone_bounce_alert', ''))) {
        errs.push('the zone_bounce_alert LABEL still says bounce');
      }
      // 2026-09-10: this used to also demand the word "reversal" HERE. That was
      // over-specified and it backfired — it pinned the word onto the MUTED
      // kind while the live one read "approach", which is exactly why he said
      // he saw no reversal alerts. Which kind owns the word is now pinned by
      // its own contract below; this one only guards against "bounce".
      return errs;
    },
  },
  {
    name: 'the Alerts page explains a direction skip in his words (2026-09-09)',
    file: 'src/pages/Alerts.tsx',
    checks: (src) => {
      const errs = [];
      if (!/skipped: no reversal off demand/.test(src)) {
        errs.push('skipped_direction must read "no reversal off demand"');
      }
      if (/skipped: not bouncing/.test(src)) errs.push('the old "not bouncing" copy is back');
      return errs;
    },
  },
  {
    name: 'pattern alerts declare the demand gate on the Notifications page (2026-09-09)',
    file: 'src/pages/Notifications.tsx',
    checks: (src) => {
      const errs = [];
      const m = src.match(/key: 'pattern_alert'[\s\S]*?\},/);
      if (!m) return ['pattern_alert must stay listed'];
      const d = m[0];
      if (!/INSIDE a demand band/.test(d)) errs.push('must say the name has to be IN a demand band');
      if (!/reversing off one/.test(d)) errs.push('must say the reversal half of the gate');
      if (!/FAILS CLOSED/.test(d)) errs.push('must say no zone coverage means silence');
      if (!/does NOT beat chance|NOT ONE BEATS CHANCE/.test(d)) {
        errs.push('the honest record must not be dropped from the pattern detail');
      }
      return errs;
    },
  },
  // Ajay 2026-09-09: "Can you move chart patterns in to the Chartmaps page
  // please and show the winning charts". The tab is half of it; the link into
  // 🏆 Past Winners is the other half and is the only honest way to use a board
  // whose patterns do not beat a coin flip.
  {
    name: 'Chart Maps carries the Patterns tab and links to the winning charts (2026-09-09)',
    file: 'src/lib/chartMaps.ts',
    checks: (src) => {
      const errs = [];
      if (!/'hot_pullback', 'patterns'/.test(src)) {
        errs.push('patterns must sit right after hot_pullback in CM_TABS');
      }
      if (!/t !== 'patterns'/.test(src)) {
        errs.push('patterns must be excluded from isBoardTab — it mounts its own page body');
      }
      if (!/'winners'\];/.test(src)) {
        errs.push('winners must stay LAST with the ledger tabs');
      }
      return errs;
    },
  },
  {
    name: 'the Patterns board keeps its door into Past Winners (2026-09-09)',
    file: 'src/pages/PatternsPage.tsx',
    checks: (src) => {
      const errs = [];
      if (!/export function winnersHref/.test(src)) errs.push('winnersHref must stay exported');
      if (!/tab=winners/.test(src)) errs.push('the winners link is gone');
      if (!/Show the winning charts/.test(src)) errs.push('the board-level winners door is gone');
      if (!/export function PatternsBoard/.test(src)) {
        errs.push('PatternsBoard must stay exported for the Chart Maps tab');
      }
      if (!/Navigate replace to="\/chart-maps\?tab=patterns"/.test(src)) {
        errs.push('/patterns must redirect to the tab');
      }
      if (!/features\.has\('chart-maps'\)/.test(src)) {
        errs.push('the redirect must respect the separate chart-maps feature gate');
      }
      return errs;
    },
  },
  // Ajay 2026-09-09: "increase our sectors ... atleast give me an indicator
  // that its in hot sector or not". The finer grain is the half that measured
  // TRUE; the edge is the half that measured flat. The strip must keep the
  // finer rows, and must survive a payload that has none.
  {
    name: 'the Hot-sectors strip carries the finer industry rows (2026-09-09)',
    file: 'src/components/HotSectors.tsx',
    checks: (src) => {
      const errs = [];
      if (!/industries_in/.test(src) || !/industries_out/.test(src)) {
        errs.push('the industry cohorts must ride the strip');
      }
      if (!/industries_in \|\| \[\]/.test(src) && !/industries_in \?\?/.test(src)) {
        errs.push('a payload with no industry keys must not break the strip');
      }
      if (!/inside \$\{r\.sector\}/.test(src)) {
        errs.push('an industry chip must say which sector it sits inside');
      }
      // 2026-09-09: "robotics, energy and optic fiber, constructipn like for
      // data centers add these" — three were already tracked and invisible.
      if (!/themes_in/.test(src) || !/themes_out/.test(src)) {
        errs.push('the build-out theme rosters must be rendered, not just computed');
      }
      if (!/thin/.test(src)) {
        errs.push('a thin cohort (rare_earth n=4) must be marked as thin');
      }
      return errs;
    },
  },
  // 2026-09-10, after "I do not see any reversal alerts today": he HAD five,
  // from the 🧲 kind. The 🪃 kind — muted since the keep-set — was the one
  // wearing the word "reversal", so the live kind looked absent. The live kind
  // must own that word and the muted one must not.
  {
    name: 'the LIVE demand kind owns the word "reversal" (2026-09-10)',
    file: 'src/lib/alertKinds.ts',
    checks: (src) => {
      const errs = [];
      const live = src.match(/demand_alert:\s*\{[^}]*\}/);
      const muted = src.match(/zone_bounce_alert:\s*\{[^}]*\}/);
      if (!live || !muted) return ['both zone kinds must stay registered'];
      if (!/reversal/i.test(live[0])) {
        errs.push('demand_alert is the kind that sends reversals — its label must say so');
      }
      if (/reversal/i.test(muted[0].replace('zone_bounce_alert', ''))) {
        errs.push('the MUTED zone_bounce_alert label must not claim the word "reversal"');
      }
      return errs;
    },
  },
];

let failed = 0;
for (const c of CONTRACTS) {
  let src;
  try {
    src = read(c.file);
  } catch {
    console.error(`✗ ${c.name}\n    cannot read ${c.file}`);
    failed++;
    continue;
  }
  const errs = c.checks(src);
  if (errs.length) {
    failed++;
    console.error(`✗ ${c.name}`);
    for (const e of errs) console.error(`    ${e}`);
  } else {
    console.log(`✓ ${c.name}`);
  }
}

if (failed) {
  console.error(`\n${failed} frontend contract(s) FAILED.`);
  process.exit(1);
}
console.log(`\nAll ${CONTRACTS.length} frontend contract(s) passed.`);
