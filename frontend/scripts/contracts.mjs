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
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const FRONTEND_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (rel) => readFileSync(join(FRONTEND_ROOT, rel), 'utf8');
/** Does a path (relative to frontend/) exist? Used by the ABSENCE contracts —
 *  a deleted feature that comes back must fail loudly. */
const exists = (rel) => existsSync(join(FRONTEND_ROOT, rel));

/** CM_TABS as a real array. Every tab contract parses the declaration instead
 *  of grepping the file, so neither a reformat nor a comment can decide
 *  whether a contract passes. */
const parseCmTabs = (src) => {
  const m = /export const CM_TABS:\s*CmTab\[\]\s*=\s*\[([^\]]*)\]/.exec(src);
  if (!m) return null;
  // Strip `//` comments FIRST. The array is commented in place — every tab
  // added since 2026-09-06 explains where it sits in the most-used-first
  // order — and without this each comment line split on its own commas and
  // became phantom "tabs", failing contracts that had nothing to do with the
  // change (2026-09-13: adding keltner/amd broke the GnT and growth-chip
  // contracts, neither of which touches those tabs).
  const body = m[1].replace(/\/\/[^\n]*/g, '');
  return body.split(',').map((x) => x.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
};

/** push/subs.OWNER_KEEP_SET as a real list of kind ids. Parsed out of the
 *  frozenset block rather than grepped for, so a kind named only inside a
 *  comment ("# potus_investment moved out") can never satisfy a keep-set
 *  check. The keep-set is what prefs_for() hands a NEWLY registered device:
 *  a kind missing from it is muted again the next time his phone re-subscribes
 *  (memory: cheetah_push_silent_drops). */
const keepSet = (subsSrc) => {
  const m = /OWNER_KEEP_SET[^=]*=\s*frozenset\(\{([\s\S]*?)\}\)/.exec(subsSrc);
  if (!m) return [];
  const body = m[1].replace(/#[^\n]*/g, '');
  return [...body.matchAll(/["']([a-z0-9_]+)["']/g)].map((x) => x[1]);
};

/** A python `NAME: ... = frozenset({...})` block as a real list of ids.
 *  market_hours/gate.py's two sets are long and heavily commented; a windowed
 *  [\s\S]{0,N} regex passes or fails on where in the block a kind happens to
 *  sit, which is not an invariant. */
const pyFrozenSet = (pySrc, name) => {
  const m = new RegExp(`${name}[^=]*=\\s*frozenset\\(\\{([\\s\\S]*?)\\}\\)`).exec(pySrc);
  if (!m) return null;
  return [...m[1].replace(/#[^\n]*/g, '').matchAll(/["']([a-z0-9_]+)["']/g)].map((x) => x[1]);
};

/** The crontab's COMMAND lines only — every `#` line dropped first. The
 *  retirement checks below ask what still RUNS; the retired block names the
 *  deleted modules in prose and must not read as a live job. */
const cronCommands = (cronSrc) =>
  cronSrc.split('\n').filter((l) => l.trim() && !l.trim().startsWith('#'));

const CONTRACTS = [
  {
    name: 'every styled class the member popover uses has a rule that ships (2026-09-10)',
    file: 'src/components/SectorMembersModal.tsx',
    // Ajay 2026-09-10, on a screenshot of the panel rendering as raw
    // full-width page text with a bare ✕ on its own line: "This is how its
    // rendering". The component was correct and every test passed — the
    // stylesheet simply was not in the commit. I staged an explicit file list
    // and missed src/styles.css, so all 20 hsm-* classes resolved to nothing.
    //
    // No render test can catch this: jsdom does not load the stylesheet, so
    // the DOM is identical with and without it. The only thing that catches a
    // class with no rule is looking for the rule.
    checks: (src) => {
      const errs = [];
      const used = new Set();
      for (const m of src.matchAll(/className=(?:"([^"]*)"|\{`([^`]*)`\})/g)) {
        for (const cls of (m[1] || m[2] || '').split(/[\s${}?:'"]+/)) {
          if (cls.startsWith('hsm-')) used.add(cls);
        }
      }
      if (!used.size) return ['no hsm-* classes found — did the panel get renamed?'];
      let css = '';
      try {
        css = read('src/styles.css');
      } catch {
        return ['src/styles.css is unreadable'];
      }
      // A boundary is required, not a substring: `css.includes('.hsm-coname')`
      // is satisfied by `.hsm-conameXX`, so renaming a rule passed this check
      // (found 2026-09-11 while building the same guard for the Hottest table).
      const missing = [...used]
        .filter((c) => !new RegExp(`\\.${c}(?![\\w-])`).test(css)).sort();
      if (missing.length) {
        errs.push(`the popover uses classes with NO rule in styles.css: ${missing.join(', ')}`
          + ' — that ships an unstyled panel, which is what happened on 2026-09-10');
      }
      return errs;
    },
  },
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
      // The wide-table box is the OTHER half, and it was unpinned until
      // 2026-09-11: an `overflow: auto` box only becomes the vertical scroller
      // when its height is bounded, and without that the header sticks to a box
      // that is itself scrolling away with the page — exactly the 2026-09-09
      // failure ("I wanted the headers to be static it broke the logic").
      // Removing the max-height used to pass this contract.
      const wide = src.match(/\.pcw__table\.is-wide \{[^}]*\}/);
      if (!wide) errs.push('.pcw__table.is-wide is gone — the wide promo table has no scroll box');
      else {
        if (!/overflow:\s*auto/.test(wide[0])) errs.push('.pcw__table.is-wide must be `overflow: auto` on both axes');
        if (!/max-height:/.test(wide[0])) errs.push('.pcw__table.is-wide needs a max-height or its static header never engages');
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
      // WIDENED 2026-09-20 — Ajay: "Default on for any change of todays features
      // Bondes or Potus or explosive growth or Earnings I wanna see all of
      // them." The preset is the page's copy of push/subs.OWNER_KEEP_SET, so
      // the on-list is READ from the backend rather than retyped here: the two
      // drifting apart is exactly the silent mute this contract exists for.
      const keep = keepSet(read('../backend/push/subs.py'));
      if (keep.length < 8) errs.push(`push/subs.OWNER_KEEP_SET parsed as ${keep.length} kinds — the 2026-09-20 keep-set is eight`);
      for (const on of keep) {
        if (!new RegExp(`${on}:\\s*true`).test(ess)) errs.push(`Essentials preset drops ${on} — it is in OWNER_KEEP_SET`);
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
      if (keys.join(',') !== '1w,2w,1m,3m,6m,1y,2y,3y,5y,all') {
        errs.push(`FALLBACK_WINDOWS is ${keys.join(',') || '(not found)'} — expected 1w,2w,1m,3m,6m,1y,2y,3y,5y,all`);
      }
      for (const k of ['daily:1w', 'daily:2w', 'daily:2y', 'daily:3y', 'daily:5y']) {
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

      // ── 1-week / 2-week zooms (Ajay 2026-09-18) ────────────────────────
      // "Also a weekly chart for the past week and 2 week inthe charting time
      // frames in all places" — short WINDOWS, not weekly candles. The server
      // list is the source of truth and FALLBACK_WINDOWS is a mirror the
      // server replaces at runtime; if they drift, a deep link silently
      // degrades. The count is asserted BEFORE the comparison so a regex that
      // finds nothing FAILS instead of passing vacuously.
      const be = read('../backend/chart_maps/support.py');
      const blk = be.match(/SUPPORT_WINDOWS: tuple\[dict, \.\.\.\] = \(([\s\S]*?)\n\)/);
      const beKeys = blk ? [...blk[1].matchAll(/\{"key":\s*"([^"]+)"/g)].map((m) => m[1]) : [];
      if (!blk) {
        errs.push('support.py: SUPPORT_WINDOWS tuple not found — the cross-mirror check cannot run');
      } else if (beKeys.length !== 9) {
        errs.push(`support.py SUPPORT_WINDOWS parsed ${beKeys.length} keys, expected 9 — regex drifted`);
      } else if (beKeys.join(',') !== keys.filter((k) => k !== 'all').join(',')) {
        errs.push(`server list ${beKeys.join(',')} != FALLBACK_WINDOWS ${keys.filter((k) => k !== 'all').join(',')}`);
      }
      // The two short zooms are CHART-ONLY: their numbers are the 1-month read.
      for (const k of ['1w', '2w']) {
        if (!new RegExp(`CHART_ONLY_LEVELS_FROM[\\s\\S]*?"${k}":\\s*"1m"`).test(be)) {
          errs.push(`support.py CHART_ONLY_LEVELS_FROM no longer maps ${k} -> 1m`);
        }
      }
      // ── the HOURLY short zooms (Ajay 2026-09-18, second ship) ──────────
      // "Can you increase the bars on the weekly chart please?" -> 1 week of
      // HOURLY bars. The backend shipped first and the picker could not
      // express the pair, so the feature never reached him. These pin the two
      // halves together so that cannot recur.
      for (const k of ['60m:1w', '60m:2w']) {
        if (!src.includes(`key: '${k}'`)) errs.push(`CHART_VIEWS lacks ${k} — the hourly short zoom is unreachable from the picker`);
      }
      // A tf with MORE THAN ONE entry must name exactly one `primary`, which
      // is what a bare `?tf=60m` link resolves to. This replaced an
      // order-dependent check on 2026-09-18: making array position the
      // fallback meant the list could not be ordered for a reader without
      // changing behaviour, and the hourly week had to sit two groups below
      // the entry he was actually on — which is why he reported it missing
      // twice. Order is now free; `primary` carries the contract.
      {
        const views = src.match(/export const CHART_VIEWS[\s\S]*?\n\];/);
        const body = views ? views[0] : '';
        if (!body) errs.push('contracts: CHART_VIEWS block not found');
        const entries = [...body.matchAll(/\{\s*key: '([^']+)'[\s\S]*?tf: '([^']+)'([\s\S]*?)\},/g)]
          .map((m) => ({ key: m[1], tf: m[2], primary: /primary:\s*true/.test(m[3]) }));
        if (entries.length < 10) errs.push(`contracts: parsed only ${entries.length} CHART_VIEWS entries — regex drifted`);
        const byTf = {};
        for (const e of entries) (byTf[e.tf] ||= []).push(e);
        for (const [tf, list] of Object.entries(byTf)) {
          // 'daily' is exempt: viewKeyFor's daily branch matches on WINDOW and
          // never reaches the tf fallback, so a primary there would be dead
          // weight. The contract is only about intraday tf-only links.
          if (tf === 'daily') continue;
          const prim = list.filter((e) => e.primary);
          if (list.length > 1 && prim.length !== 1) {
            errs.push(`CHART_VIEWS: tf '${tf}' has ${list.length} entries and ${prim.length} primary — a bare ?tf=${tf} link needs exactly one`);
          }
          if (list.length === 1 && prim.length) {
            errs.push(`CHART_VIEWS: tf '${tf}' has one entry and does not need primary`);
          }
        }
      }
      // viewKeyFor must consult `primary` before any positional match.
      if (!/v\.tf === t && v\.primary/.test(src)) {
        errs.push('viewKeyFor no longer falls back to the primary entry — the tf fallback is order-dependent again');
      }
      // The SPAN LADDER leads with the hourly week (Ajay 2026-09-18, third
      // round: "I still see the same charts"). If 1w/2w go back to daily here,
      // picking "1 week" draws five candles again.
      for (const k of ['60m:1w', '60m:2w']) {
        const m = src.match(new RegExp(`key: '${k}'[^}]*?group: '([^']+)'`));
        if (!m) errs.push(`CHART_VIEWS ${k} lost its group`);
        else if (m[1] !== 'Zoom') errs.push(`CHART_VIEWS ${k} is in group '${m[1]}' — the hourly short zooms must lead the span ladder`);
      }
      // The component must DERIVE its optgroups, never retype them: a
      // hard-coded list silently dropped a whole group once already.
      {
        const comp = read('src/components/SupportLevels.tsx');
        if (/\[\s*'Daily'\s*,\s*'Intraday'\s*\]\s*as const/.test(comp)) {
          errs.push('SupportLevels.tsx hard-codes its optgroup list again — a new group would render no options');
        }
        if (!/new Set\(CHART_VIEWS\.map\(\(v\) => v\.group\)\)/.test(comp)) {
          errs.push('SupportLevels.tsx no longer derives its optgroups from CHART_VIEWS');
        }
      }
      // viewKeyFor must match the PAIR before falling back to the tf, or the
      // control names a view the chart is not drawing and cannot be re-picked.
      if (!/v\.tf === t && v\.window === window/.test(src)) {
        errs.push('viewKeyFor no longer matches (tf, window) before falling back to tf — the three 60m views collapse to one key');
      }
      // The hourly pairs must NOT be redirected to a daily read, and must not
      // claim to be. CHART_ONLY_LEVELS_FROM is keyed by WINDOW, so the guard is
      // that support.py gates the redirect on `not own_bars`.
      if (!/chart_only = \(not own_bars\) and spec\["key"\] in CHART_ONLY_LEVELS_FROM/.test(be)) {
        errs.push('support.py: chart_only is no longer gated on `not own_bars` — an hourly 1w/2w would claim a 1-month provenance it does not have');
      }
      // The hint on an hourly pair must never borrow the daily wording.
      {
        const views = src.match(/export const CHART_VIEWS[\s\S]*?\n\];/);
        const body = views ? views[0] : '';
        for (const k of ['60m:1w', '60m:2w']) {
          const entry = body.split(`key: '${k}'`)[1] || '';
          const hint = entry.split('},')[0] || '';
          if (/1-month read|month of daily/i.test(hint)) {
            errs.push(`CHART_VIEWS ${k} claims a 1-month read — on an hourly frame the levels are the 1-hour frame's own ~47-session read`);
          }
        }
      }
      const feats2 = read('src/lib/newFeatures.ts');
      if (!/id: 'chart-windows-1w-2w-hourly'/.test(feats2)) errs.push("newFeatures.ts lost the 'chart-windows-1w-2w-hourly' highlight");
      // The S&D evidence floor a 5-bar frame is under. Never lowered for a zoom.
      if (!/MIN_BARS_ABS\s*=\s*12\b/.test(read('../backend/supply_demand/price_zones.py'))) {
        errs.push('price_zones.MIN_BARS_ABS is no longer 12 — a short zoom must not lower the swing floor');
      }
      // Every analytic read runs on read_budget, never on the chart budget: a
      // 5-bar mood scores under MOOD_BUY and would print WAIT where 1m prints BUY.
      if (!/read_budget/.test(be)) errs.push('support.py lost read_budget — the short zooms would compute off 5 bars');
      if (/\.tail\(budget\)/.test(be)) {
        errs.push('support.py still runs an analytic read on the chart budget — a 1w mood/signal would diverge from 1m');
      }
      if (!/id: 'chart-windows-1w-2w'/.test(feats)) errs.push("newFeatures.ts lost the 'chart-windows-1w-2w' highlight");
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
      // ONE room-floor list, two entries, no invented floor (2026-09-17). Both
      // the Chart Maps toolbar and the Back in Demand panel render THIS array;
      // a second copy is how the two surfaces drift into different floors. A
      // WHOLE-TREE scan, not a two-file check — the duplicate this guards
      // against is the one someone adds in a file nobody thought to list.
      const roomDecls = [];
      const scanRoomFloors = (dir) => {
        for (const name of readdirSync(join(FRONTEND_ROOT, dir), { withFileTypes: true })) {
          const rel = `${dir}/${name.name}`;
          if (name.isDirectory()) scanRoomFloors(rel);
          else if (/\.(ts|tsx|js|jsx)$/.test(name.name)
                   && /^\s*(export\s+)?const ROOM_FLOORS\b/m.test(read(rel))) {
            roomDecls.push(rel);
          }
        }
      };
      scanRoomFloors('src');
      if (roomDecls.length !== 1 || roomDecls[0] !== 'src/lib/bounceRoom.ts') {
        errs.push(`ROOM_FLOORS must be declared exactly once, in src/lib/bounceRoom.ts — found [${roomDecls.join(', ')}]`);
      }
      const floors = src.match(/export const ROOM_FLOORS[^=]*=\s*\[([\s\S]*?)\];/);
      if (!floors) errs.push('bounceRoom.ts lost ROOM_FLOORS — the one shared room-floor list');
      else {
        const keys = [...floors[1].matchAll(/key:\s*(?:'([^']*)'|String\(ROOM_MIN_PCT\))/g)]
          .map((k) => (k[1] === undefined ? 'ROOM_MIN_PCT' : k[1]));
        if (keys.length !== 2 || keys[0] !== 'ROOM_MIN_PCT' || keys[1] !== '0') {
          errs.push(`ROOM_FLOORS must be exactly [ROOM_MIN_PCT, '0'] — got [${keys.join(', ')}]. A third floor is a threshold nobody gave.`);
        }
      }
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
      if (/^\s*const ROOM_FLOORS/m.test(panel)) {
        errs.push('DemandReentryPanel re-declares ROOM_FLOORS — it must import the one list from lib/bounceRoom.ts');
      }
      if (!/\bROOM_FLOORS\b[^\n]*from '\.\.\/lib\/bounceRoom'|ROOM_FLOORS,/.test(panel)) {
        errs.push('DemandReentryPanel no longer imports ROOM_FLOORS from lib/bounceRoom');
      }
      if (!/dropped_low_room/.test(panel)) errs.push('DemandReentryPanel no longer reports dropped_low_room');
      const page = read('src/pages/ChartMaps.tsx');
      if (!/aria-label="Room floor"/.test(page)) errs.push('ChartMaps lost the Room floor control');
      const gate = page.slice(Math.max(0, page.indexOf('aria-label="Room floor"') - 260), page.indexOf('aria-label="Room floor"'));
      if (!/\{ROOM_TAB && \(/.test(gate)) errs.push('ChartMaps Room floor control is not gated on ROOM_TAB (zones / deep_demand only)');
      // The toolbar carries the room control, built from the shared list, and
      // the hidden count reaches HIM with a way out of it (2026-09-17). A
      // filter that hides rows silently is the failure this pins against.
      if (!/ROOM_FLOORS\.map\(/.test(page)) {
        errs.push('ChartMaps Room floor control no longer renders from the shared ROOM_FLOORS list (lib/bounceRoom.ts)');
      }
      if (!/import \{ ROOM_FLOORS \} from '\.\.\/lib\/bounceRoom'/.test(page)) {
        errs.push("ChartMaps no longer imports ROOM_FLOORS from '../lib/bounceRoom' — the two surfaces could drift to different floors");
      }
      if (!/hidden_low_room/.test(page)) errs.push('ChartMaps no longer reports hidden_low_room');
      if (!/data-testid="hidden-low-room"/.test(page)) {
        errs.push('ChartMaps lost the hidden-low-room readout — the room floor would hide tiles silently');
      }
      // THE INVARIANT is that the readout names a control that EXISTS on this
      // toolbar — not which module the string came from. The floors are shared
      // so the panel and the tiles cannot offer different ones; the wording is
      // this page's own (its buttons have read "Any room" since 2026-09-05).
      // One labeller feeds both the buttons and the readout, so they cannot
      // disagree; pinning bounceRoom's label here is what sent the readout
      // pointing at a button that did not exist.
      if (!/function cmRoomLabel\(/.test(page)) {
        errs.push('ChartMaps lost cmRoomLabel — the buttons and the hidden-count readout could name the room control differently');
      }
      if (!/const CM_ANY_ROOM_LABEL = cmRoomLabel\(0\)/.test(page)) {
        errs.push('ChartMaps no longer derives its "any room" wording from cmRoomLabel(0)');
      }
      if (!/<em>\{CM_ANY_ROOM_LABEL\}<\/em>/.test(page)) {
        errs.push('ChartMaps hidden-low-room readout no longer names the "any room" control it actually renders');
      }
      if (!/\{cmRoomLabel\(floor\)\}/.test(page)) {
        errs.push('ChartMaps room buttons no longer label themselves through cmRoomLabel');
      }
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
    name: 'The ticker page carries the + Signals button, sized like its siblings (2026-09-10)',
    file: 'src/pages/SepaCandidate.tsx',
    // Ajay 2026-09-10: "add a signals button in individual ticket page, I am
    // using it as a watch list page." Two things can silently break this and
    // neither shows up in jsdom, which loads no stylesheets:
    //   1. `chrome` must REPLACE the look class, never append — .cm-tv sits
    //      BELOW .sepa-btn--ghost in styles.css and both are single-class, so
    //      an appended chrome loses and the button renders as a 10px chip.
    //   2. `cm-watch` must survive the swap in BOTH branches — .cm-watch.is-on
    //      and .cm-watch.is-held are the only rules that paint those states.
    checks: (src) => {
      const errs = [];
      if (!/import\s*\{\s*SignalWatchButton\s*\}\s*from\s*'\.\.\/components\/SignalWatchButton'/.test(src)) errs.push('SepaCandidate.tsx no longer imports SignalWatchButton');
      const mount = /<SignalWatchButton\s+symbol=\{symbol\}\s+chrome="sepa-btn sepa-btn--ghost"/.test(src);
      if (!mount) errs.push('SepaCandidate.tsx must mount <SignalWatchButton symbol={symbol} chrome="sepa-btn sepa-btn--ghost"> — the ticker page is his watchlist page');
      // it has to sit INSIDE the action cluster, not somewhere else on a 5k-line page
      const cluster = src.split('sepa-candidate-page__head-actions')[1] || '';
      if (!/<SignalWatchButton/.test(cluster.slice(0, 2000))) errs.push('the + Signals button left the sepa-candidate-page__head-actions cluster');

      const btn = read('src/components/SignalWatchButton.tsx');
      if (!/chrome = WATCH_CHROME_CARD/.test(btn)) errs.push('SignalWatchButton must default chrome to WATCH_CHROME_CARD so the board/promo mounts keep the chip look');
      if (!/export const WATCH_CHROME_CARD = 'cm-tv';/.test(btn)) errs.push("WATCH_CHROME_CARD must stay 'cm-tv' (the Chart Maps chip chrome)");
      const classAttrs = btn.match(/className=\{`[^`]*`\}/g) || [];
      if (classAttrs.length !== 2) errs.push(`SignalWatchButton should build exactly 2 class strings (held span + button), found ${classAttrs.length}`);
      for (const c of classAttrs) {
        if (!c.includes('${chrome}')) errs.push(`a SignalWatchButton branch hardcodes its chrome instead of taking the prop: ${c}`);
        if (!/cm-watch/.test(c)) errs.push(`a SignalWatchButton branch dropped cm-watch, so .is-on/.is-held stop painting: ${c}`);
      }
      if (/cm-tv cm-watch/.test(btn.replace(/WATCH_CHROME_CARD = 'cm-tv'/, ''))) errs.push('SignalWatchButton still hardcodes "cm-tv cm-watch" somewhere — chrome must replace it');

      // the states it keeps alive must actually exist in the stylesheet
      const css = read('src/styles.css');
      for (const rule of ['.cm-watch.is-on', '.cm-watch.is-held']) {
        if (!css.includes(rule)) errs.push(`styles.css lost ${rule} — the + Signals button has no ${rule.split('.').pop()} state`);
      }
      for (const cls of ['sepa-btn--ghost']) {
        if (!new RegExp(`\\.${cls}\\s*[,{]`).test(css)) errs.push(`styles.css has no rule for .${cls}, which the ticker-page button wears`);
      }

      // the server must still report what the cap actually counts
      const hook = read('src/hooks/useSignalWatchlist.ts');
      if (!/full: watchCount\(s\) >= MAX_SYMBOLS/.test(hook)) errs.push('useSignalWatchlist.full must come from watchCount (the stored list), not the merged watchlist+portfolio length');
      if (!/j\.watch_n/.test(hook)) errs.push("useSignalWatchlist must read the server's watch_n");
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
      if (!(parseCmTabs(src) || []).includes('hot_pullback')) errs.push("CM_TABS no longer lists 'hot_pullback'");
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
    name: 'Chart Maps carries the \u{1F680} Explosive Growth tab, with the no-cap-floor deal visible (2026-09-11)',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-11: 100%+ sales AND 100%+ quarterly EPS, "separately just
    // trackers", "remove the 700M rule for this page". The DEAL is: no cap
    // floor on the board, and the rows the trading engine will refuse say so.
    // If the ⛔ rendering ever disappears, the board silently starts looking
    // like a buy list for names the engine will not touch.
    checks: (src) => {
      const errs = [];
      const tabs = parseCmTabs(src);
      if (!tabs) return ['CM_TABS declaration not found'];
      if (!tabs.includes('growth')) errs.push("CM_TABS no longer lists 'growth'");
      if (!/growth:\s*\{[\s\S]*?label:/.test(src)) errs.push('TAB_META has no growth entry');
      if (!/t !== 'growth'/.test(src)) errs.push('isBoardTab must exclude growth — it has its own endpoint and renderer');
      const meta = /\n  growth:\s*\{[\s\S]*?\n  \},\n/.exec(src);
      if (meta) {
        if (!/NO MARKET-CAP FLOOR/i.test(meta[0])) {
          errs.push('the Explosive Growth blurb must say the board has NO cap floor — that is the whole deal he agreed to');
        }
        if (!/REFUSE/i.test(meta[0])) {
          errs.push('the blurb must say the trading engine still refuses sub-$2 / sub-$700M names');
        }
        if (!/NOTHING HERE IS BACKTESTED|never been measured forward/i.test(meta[0])) {
          errs.push('the blurb must say the 100/100 screen is unmeasured — it is a discovery list');
        }
      }

      const page = read('src/pages/ChartMaps.tsx');
      if (!/<ExplosiveGrowth \/>/.test(page)) errs.push('ChartMaps.tsx no longer mounts <ExplosiveGrowth />');

      const tsx = read('src/components/ExplosiveGrowth.tsx');
      if (!/\/growth\/\$\{refresh \? 'refresh' : 'board'\}/.test(tsx)) {
        errs.push('ExplosiveGrowth must read GET /growth/board (and POST /growth/refresh)');
      }
      // Sectors with the DENOMINATOR (Ajay 2026-09-11: "I wanna see the secorts
      // in the growth.. To show that only some are growing"). A bare count of 9
      // says nothing; "9 of 493" is the statement. If n_scanned stops rendering,
      // the board silently goes back to saying nothing.
      if (!/n_scanned/.test(tsx)) {
        errs.push('the sector rows must print n_scanned — "9 of 493", not just "9"');
      }
      if (!/hit_rate_pct/.test(tsx)) {
        errs.push('the sector rows must print the hit rate');
      }
      if (!/industries\.map\(/.test(tsx)) {
        errs.push('a sector must expand into its industries — he asked for the individual categories');
      }
      // Ajay 2026-09-12: "What are these nymbers no headers" — the tree shipped
      // with five unlabelled columns, so "9 of 493 / 1.8% / +144.0%" read as
      // three unrelated numbers. Never again.
      for (const label of ['Sector', 'Qualified', 'Hit rate', 'Med. sales']) {
        if (!tsx.includes(`>${label}<`)) {
          errs.push(`the sector tree must label its "${label}" column — unlabelled numbers are unreadable`);
        }
      }
      // Ajay 2026-09-12: "I need them to be clickable in to tickers and pick the
      // top 10 in each sector." A ticker printed as plain text is a dead end —
      // he picks names off this tree.
      if (/symbols\.join\(/.test(tsx)) {
        errs.push('the sector tree must not join symbols into plain text — every ticker is a TickerLink');
      }
      if (!/<SymStrip syms=\{i\.symbols\}/.test(tsx) || !/<SymStrip syms=\{g\.symbols\}/.test(tsx)) {
        errs.push('both the sector AND the industry rows must render tickers through <SymStrip> (clickable + "+N more")');
      }
      if (!/\+\{more\} more/.test(tsx)) {
        errs.push('a capped ticker list must say "+N more" — silent truncation under-reports the sector');
      }
      // The board must PRINT the warnings, not merely receive them. Rendering
      // the row without them is the silent-unbuyable-list failure.
      if (!/warns\.map\(/.test(tsx)) {
        errs.push('every row must render its warnings[] — a ⛔ row must never look clean');
      }
      if (!/No market-cap floor on this board/.test(tsx)) {
        errs.push('the board body must state the no-cap-floor deal where he reads it, not only in the tab blurb');
      }
      // intact is the one gate that measured; it must not read the same as a
      // pierced band.
      if (!/intact/.test(tsx)) errs.push('the demand column must distinguish an INTACT floor — the only gate that measured');
      if (!/<SignalWatchButton\s+symbol=\{r\.symbol\}/.test(tsx)) {
        errs.push('every growth row must carry the + Signals button — he picks names off these tables');
      }

      const css = read('src/styles.css');
      // Same sticky-header trap as the Hottest and Catalysts tables.
      const scroll = /\.eg-scroll\s*\{([^}]*)\}/.exec(css);
      if (!scroll) errs.push('styles.css has no .eg-scroll rule — the growth table has no scroll container');
      else {
        if (!/overflow:\s*auto/.test(scroll[1])) errs.push('.eg-scroll must be `overflow: auto` on BOTH axes — overflow-x alone traps the sticky header');
        if (!/max-height:/.test(scroll[1])) errs.push('.eg-scroll needs a max-height or the box never scrolls vertically and the static header never engages');
      }
      const thead = /\.eg-table thead th\s*\{([^}]*)\}/.exec(css);
      if (!thead) errs.push('styles.css lost the .eg-table thead th rule');
      else if (!/position:\s*sticky/.test(thead[1]) || !/top:\s*0/.test(thead[1])) {
        errs.push('.eg-table thead th must stay `position: sticky; top: 0`');
      }
      // every eg-* class the TSX uses must have a rule that SHIPS — jsdom
      // loads no stylesheets, so no render test can catch a missing one.
      const used = new Set((tsx.match(/\beg-[a-z0-9-]+/g) || []));
      for (const c of used) {
        if (!new RegExp('\\.' + c + '(?![\\w-])').test(css)) {
          errs.push(`.${c} is used in ExplosiveGrowth.tsx but has no CSS rule`);
        }
      }

      // \u{1F4E3} "just reported" (Ajay 2026-09-17). A CALENDAR FACT bolted onto rows
      // this board already serves. Three things must stay true or the badge starts
      // implying an edge nobody measured:
      //   1. it renders, and the board carries its own summary;
      //   2. the chip says IN WORDS that it decides nothing;
      //   3. it never formats a date with `new Date(iso)` — that parses a bare ISO
      //      date as UTC and prints the PREVIOUS day in ET ('2026-09-16' -> Sep 15).
      // The eg-* loop above covers .eg-ernote; .cm-badge-earnings is on the shared
      // cm-badge family and needs its own check.
      if (!/<EarningsFreshChip\s/.test(tsx)) {
        errs.push('the growth row must render <EarningsFreshChip /> — he asked for just-reported names to be highlighted here');
      }
      if (!/earnings_fresh_summary/.test(tsx)) {
        errs.push('ExplosiveGrowth must read earnings_fresh_summary — the board states its own just-reported coverage, never another board\'s verdict');
      }
      if (!/no report date on file/.test(tsx)) {
        errs.push('the just-reported note must say "no report date on file" — an unknown calendar must never read as "did not report" (16 of 21 rows the day it shipped)');
      }
      if (!/changes no order/.test(tsx)) {
        errs.push('the just-reported note must say it changes no order — this board sorts by sales growth and a report date is not a ranking reason');
      }
      if (!/\.cm-badge-earnings(?![\w-])/.test(css)) {
        errs.push('.cm-badge-earnings has no CSS rule — the just-reported chip would ship unstyled (jsdom loads no stylesheets, so no render test can catch it)');
      }
      const efc = read('src/components/EarningsFreshChip.tsx');
      if (!/CALENDAR FACT, NOT A SIGNAL/.test(efc)) {
        errs.push('the just-reported chip tooltip must say CALENDAR FACT, NOT A SIGNAL — nothing on this board is measured');
      }
      if (!/does not change this row's order/.test(efc)) {
        errs.push("the just-reported chip tooltip must say it does not change this row's order");
      }
      if (/new Date\(/.test(efc)) {
        errs.push("EarningsFreshChip must not use new Date( — a bare ISO date parses as UTC and renders the previous day in ET; reuse EarningsChip.fmtDate");
      }
      return errs;
    },
  },
  {
    name: 'the \u{1F680} growth chip reaches EVERY Chart Maps tab (2026-09-11)',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-11: "I am hoping this new list will be considerd in all
    // chart maps. Like in Deep demand scan." then, plainly: "ALL TABS IN CHART
    // MAPS". Every board tab renders through PatternChart; the eight non-board
    // tabs each have their own renderer. If a NEW non-board tab is added and
    // its renderer forgets the chip, this fails — that is the whole point.
    checks: (src) => {
      const errs = [];
      const tabs = parseCmTabs(src);
      if (!tabs) return ['CM_TABS declaration not found'];

      // 'growth' IS the list, so it needs no pointer back to itself.
      const RENDERER = {
        hot_pullback: 'src/components/HotPullbackBoard.tsx',
        patterns: 'src/pages/PatternsPage.tsx',
        session: 'src/components/SessionBoard.tsx',
        signals: 'src/components/SignalLabBoard.tsx',
        hot_sectors: 'src/components/HottestSectors.tsx',
        catalysts: 'src/pages/Catalysts.tsx',
        overnight: 'src/components/OvernightGappers.tsx',
        support: 'src/components/SupportLevels.tsx',
        gnt: 'src/components/GntBoard.tsx',
        bonde: 'src/components/BondeBoard.tsx',
        holdings: 'src/components/HoldingsBoard.tsx',
        potus: 'src/components/PotusBoard.tsx',
      };
      const nonBoard = tabs.filter((t) => !/^(zones|deep_demand|quick_bounce|breaking|gabbar|vcp|topping|ict|undervalue|zero_dte|earnings|winners|keltner|amd|ipo)$/.test(t));
      for (const t of nonBoard) {
        if (t === 'growth') continue;
        const file = RENDERER[t];
        if (!file) {
          errs.push(`tab '${t}' has no renderer listed in this contract — add it and give it a <GrowthChip>`);
          continue;
        }
        const tsx = read(file);
        if (!/<GrowthChip\s/.test(tsx)) {
          errs.push(`${file} (tab '${t}') does not render <GrowthChip> — "ALL TABS IN CHART MAPS"`);
        }
      }
      // The board tabs all funnel through the one tile component.
      const tile = read('src/components/PatternChart.tsx');
      if (!/<GrowthChip\s+symbol=\{tile\.symbol\}/.test(tile)) {
        errs.push('PatternChart must render <GrowthChip> — it is the one renderer behind every board tab');
      }
      // The chip is a POINTER to the growth board, never a second screen.
      const chip = read('src/components/GrowthChip.tsx');
      if (/sales_growth_pct\s*>=|100/.test(chip)) {
        errs.push('GrowthChip must not re-implement the 100/100 screen — it reads /growth/tags');
      }
      if (!/refused/.test(chip)) {
        errs.push('the chip must carry the refused tone — good sales must not make an unbuyable row look clean');
      }
      const css = read('src/styles.css');
      for (const c of ['cm-badge-growth', 'cm-badge-bad', 'hs-badge-growth', 'sb-chip-growth']) {
        if (!new RegExp('\\.' + c + '(?![\\w-])').test(css)) {
          errs.push(`.${c} has no CSS rule — the chip would ship unstyled`);
        }
      }
      return errs;
    },
  },
  {
    name: 'the growth board declares its own push kind everywhere (2026-09-11)',
    file: 'src/pages/Notifications.tsx',
    checks: (src) => {
      const errs = [];
      const m = src.match(/key: 'growth_demand_alert'[\s\S]*?\},\n/);
      if (!m) return ['growth_demand_alert must stay listed on the Notifications page'];
      const d = m[0];
      if (!/separately just trackers/.test(d)) errs.push('must quote why it is its own kind');
      if (!/NO MARKET-CAP FLOOR/i.test(d)) errs.push('must say the board has no cap floor');
      if (!/5% of room|5% of the room|at least 5%/.test(d)) errs.push('must say the standing room gate still applies');
      if (!/intact/.test(d)) errs.push('must name the one measured gate');
      if (!/NOTHING HERE IS BACKTESTED|never been measured forward/i.test(d)) {
        errs.push('must say the screen is unmeasured');
      }
      const prefs = read('src/hooks/useNotificationPrefs.ts');
      if (!/growth_demand_alert\?: boolean/.test(prefs)) {
        errs.push('NotificationPrefs must carry growth_demand_alert or the toggle cannot be stored');
      }
      return errs;
    },
  },
  {
    name: 'Chart Maps carries the 🔥 Hottest tab, styled and wired (2026-09-11)',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-11: "find the hottest of the sectors like the most growth
    // and put them in to a new tab ... hottest from a sector in to a table.
    // Like the catalyst and keep sales and other crucial metrics for me."
    // Every hs-* class the TSX uses must have a rule that SHIPS: jsdom loads
    // no stylesheets, so no render test can catch a missing one — the member
    // popover already shipped unstyled once for exactly this reason.
    checks: (src) => {
      const errs = [];
      const tabs = parseCmTabs(src);
      if (!tabs) return ['CM_TABS declaration not found'];
      if (!tabs.includes('hot_sectors')) errs.push("CM_TABS no longer lists 'hot_sectors'");
      if (!/hot_sectors:\s*\{[\s\S]*?label:/.test(src)) errs.push('TAB_META has no hot_sectors entry');
      if (!/t !== 'hot_sectors'/.test(src)) errs.push('isBoardTab must exclude hot_sectors — it has its own endpoint and renderer');
      const meta = /hot_sectors:\s*\{[\s\S]*?\},\n/.exec(src);
      if (meta && !/discovery/i.test(meta[0])) {
        errs.push('the Hottest blurb must say plainly that it is a DISCOVERY list, not a measured signal');
      }
      if (meta && !/ALL ELEVEN|all eleven/.test(meta[0])) {
        errs.push('the Hottest blurb must say every sector is listed — a strong name in a cold sector is the case it exists for');
      }

      const page = read('src/pages/ChartMaps.tsx');
      if (!/<HottestSectors \/>/.test(page)) errs.push('ChartMaps.tsx no longer mounts <HottestSectors />');

      const tsx = read('src/components/HottestSectors.tsx');
      if (!/\/rotation\/hottest/.test(tsx)) errs.push('HottestSectors must read GET /rotation/hottest');
      // the backend owns heat and traction; a second definition here is how
      // this board and the Hot-sectors strip would start disagreeing
      if (/traction\s*[=:]\s*.*pace/.test(tsx)) errs.push('HottestSectors must not recompute traction — the backend owns it');
      // Ajay 2026-09-12: "Add sort in this". Every column he reads, he ranks
      // on — and the sort MUST be a server round-trip: the payload keeps only
      // `names_per_group` rows per group, so a client-side reorder ranks the
      // visible 25 and never reaches the 305th Technology name.
      if (!/sort=\$\{encodeURIComponent\(sort\)\}&dir=\$\{dir\}/.test(tsx)) {
        errs.push('HottestSectors must send BOTH sort and dir to the server — a client-side sort only reorders the truncated 25');
      }
      if (/\.sort\(\(a, b\)|\[\.\.\.(sectors|names)\]\.sort\(/.test(tsx)) {
        errs.push('HottestSectors must not sort rows locally — the server sorts before it truncates');
      }
      for (const key of ['sales_yoy', 'sales_tier', 'q_eps_yoy', 'net_margin',
                         'eq_score', 'next_earnings']) {
        if (!tsx.includes(`key: '${key}'`)) {
          errs.push(`HS_COLS is missing the ${key} column — every printed column must sort`);
        }
      }
      if (!/<GroupFundCells r=\{s\}/.test(tsx) || !/<GroupFundCells r=\{ind\}/.test(tsx)) {
        errs.push('sector AND industry rows must print their fundamental medians — otherwise a sort on one of those columns reorders the tree with nothing visible behind it');
      }

      // REGRESSION 2026-09-12: the five study overlays shipped with their tones
      // absent from CmLineTone, so toneColor had no case and every one of them
      // drew in the SAME grey as the gridlines. He reported it as "Non of these
      // are showing up". A checkbox whose line is invisible is not a feature.
      {
        const cm = read('src/lib/chartMaps.ts');
        for (const tone of ['amd', 'fib', 'meanrev', 'keltner']) {
          if (!new RegExp(`tone === '${tone}'`).test(cm)) {
            errs.push(`toneColor has no case for '${tone}' — that study overlay would draw grid-grey and look like it is not showing up`);
          }
          if (!new RegExp(`\\b${tone}\\b`).test(/CmLineTone = [^;]*/.exec(cm)?.[0] || '')) {
            errs.push(`CmLineTone is missing '${tone}'`);
          }
        }
        const pc = read('src/components/PatternChart.tsx');
        if (!/amd_accumulation:/.test(pc)) {
          errs.push('BAND_FILL has no amd_accumulation — the AMD base would paint as a neutral range');
        }
        const page2 = read('src/pages/ChartMaps.tsx');
        if (/filterForGrid\([^)]*,\s*false\)/.test(page2)) {
          errs.push('ChartMaps passes expanded=false to filterForGrid — that strips fib from the only chart surface the page has');
        }
      }

      const css = read('src/styles.css');

      // Ajay 2026-09-11: "Can you make the table header static for this please?"
      // This broke once already on the Catalysts table for a subtle reason: an
      // `overflow-x: auto` box is a scroll container on BOTH axes, so without a
      // height bound it never scrolls vertically and `top: 0` sticks the header
      // to a box that is itself scrolling away with the page. The header only
      // engages when the box is the vertical scroller. jsdom loads no CSS, so a
      // render test cannot catch a revert — this can.
      const scroll = /\.hs-scroll\s*\{([^}]*)\}/.exec(css);
      if (!scroll) errs.push('styles.css has no .hs-scroll rule — the Hottest table has no scroll container');
      else {
        if (!/overflow:\s*auto/.test(scroll[1])) errs.push('.hs-scroll must be `overflow: auto` on BOTH axes — overflow-x alone still traps the sticky header');
        if (!/max-height:/.test(scroll[1])) errs.push('.hs-scroll needs a max-height or the box never scrolls vertically and the static header never engages');
      }
      const thead = /\.hs-table thead th\s*\{([^}]*)\}/.exec(css);
      if (!thead) errs.push('styles.css lost the .hs-table thead th rule');
      else if (!/position:\s*sticky/.test(thead[1]) || !/top:\s*0/.test(thead[1])) {
        errs.push('.hs-table thead th must stay `position: sticky; top: 0` — he asked for a static header');
      }
      // and the Signals button must stay readable as a button in that table
      if (/<SignalWatchButton[^>]*\bcompact\b/.test(tsx)) {
        errs.push('the Hottest table must NOT use the compact Signals button — a bare "+" beside the ☆ does not read as a control');
      }
      if (!/<SignalWatchButton\s+symbol=\{r\.symbol\}/.test(tsx)) {
        errs.push('every Hottest name row must carry the + Signals button — he picks names off this table');
      }

      const used = new Set();
      for (const m of tsx.matchAll(/(?:className=\{?["'`])([^"'`]+)/g)) {
        for (const c of m[1].split(/[\s${}]+/)) if (/^hs-[a-z0-9-]+$/.test(c)) used.add(c);
      }
      // data-testid values are NOT classes. The ⚠ pair mark (2026-09-20) ships
      // `data-testid={`hs-pair-${r.symbol}`}` with a bd-* className, and the
      // blanket sweep below harvested `hs-pair-` as a class that styles.css
      // has no rule for — a styling failure reported for a test hook.
      const tsxClasses = tsx.replace(/data-testid=\{?[`'"][^`'"]*[`'"]\}?/g, '');
      for (const m of tsxClasses.matchAll(/hs-[a-z0-9-]+/g)) used.add(m[0]);
      if (!used.size) errs.push('no hs-* classes found — did the Hottest table get renamed?');
      for (const c of [...used].sort()) {
        // (?![\w-]) not (?![a-z0-9-]): the narrow class let `.hs-conameXX`
        // satisfy a lookup for `.hs-coname`, so renaming a rule passed.
        if (!new RegExp(`\\.${c}(?![\\w-])`).test(css)) {
          errs.push(`styles.css has no rule for .${c} — the Hottest table would ship unstyled`);
        }
      }
      return errs;
    },
  },
  {
    name: 'Chart Maps carries the Patterns tab and links to the winning charts (2026-09-09)',
    file: 'src/lib/chartMaps.ts',
    checks: (src) => {
      // Parse the ARRAY, do not pin substrings of its formatting. The old
      // spelling tested /'hot_pullback', 'patterns'/ against the whole file,
      // which broke BOTH ways (both reproduced 2026-09-11): a line-wrap of
      // CM_TABS failed a correct file, and a COMMENT carrying the pair
      // satisfied it while the real order was wrong.
      const errs = [];
      const tabs = parseCmTabs(src);
      if (!tabs) return ['CM_TABS declaration not found'];
      const i = tabs.indexOf('hot_pullback');
      if (i < 0 || tabs[i + 1] !== 'patterns') {
        errs.push(`patterns must sit right after hot_pullback in CM_TABS — got ${tabs.join(', ')}`);
      }
      if (!/t !== 'patterns'/.test(src)) {
        errs.push('patterns must be excluded from isBoardTab — it mounts its own page body');
      }
      if (tabs[tabs.length - 1] !== 'winners') {
        errs.push(`winners must stay LAST with the ledger tabs — got ${tabs[tabs.length - 1]}`);
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
  // Ajay 2026-09-12: "this whole thing is super messay" · "I am trying to see
  // what changed if there is no change continously same sectors continue to
  // show the top for example energy has been continous."
  //
  // Energy at #1 for eight days is ONE fact, not eight. The strip must open on
  // the DELTA with the board folded behind it, and when nothing moved it must
  // SAY so — an empty render reads as a broken scan, and re-printing ~35 chips
  // is the thing he called messy.
  {
    name: 'the Hot-sectors strip leads with what CHANGED, board folded (2026-09-12)',
    file: 'src/components/HotSectors.tsx',
    checks: (src) => {
      const errs = [];
      if (!/<RotationChanges \/>/.test(src)) {
        errs.push('the change line must ride above the board');
      }
      if (!/useState\(false\)/.test(src) || !/showAll/.test(src)) {
        errs.push('the chip board must start FOLDED (showAll defaults false)');
      }
      if (!/\{showAll && \(/.test(src)) {
        errs.push('the chip groups must sit behind the fold, not beside it');
      }
      if (!/aria-expanded=\{showAll\}/.test(src)) {
        errs.push('the fold toggle must announce its state to a screen reader');
      }
      // The chips are KEPT — this is a declutter, not a deletion.
      for (const k of ['cohIn', 'indIn', 'thmIn', 'cohOut', 'indOut', 'thmOut']) {
        if (!new RegExp(k).test(src)) errs.push('the fold must still contain ' + k);
      }
      return errs;
    },
  },
  {
    name: 'the change line answers "no change" instead of rendering nothing (2026-09-12)',
    file: 'src/components/RotationChanges.tsx',
    checks: (src) => {
      const errs = [];
      if (!/no rank change since/.test(src)) {
        errs.push('a quiet session must say so in words');
      }
      if (!/still leading/.test(src) || !/streakText/.test(src)) {
        errs.push('the quiet line must carry the streak — "Energy #1 · 8d"');
      }
      if (!/rotation\/changes/.test(src)) {
        errs.push('the line must read the backend change detector, not recompute ranks');
      }
      // grain=all: the board below renders three grains, so a one-grain answer
      // could print a confident "no change" while themes reshuffled under it.
      if (/grain=themes/.test(src) || /grain=\$\{/.test(src)) {
        errs.push('the strip must take the all-grain answer, not one grain');
      }
      if (!/extra/.test(src) || !/Math\.max\(0/.test(src)) {
        errs.push('movers beyond the cap must be COUNTED, never silently dropped');
      }
      if (!/not a reason to trade/i.test(src)) {
        errs.push('the strip must state that a visible shift is not tradeable');
      }
      return errs;
    },
  },
  // Ajay 2026-09-12: "sort this by demand intact". The board ranked by sales
  // growth only, so the four names at an intact demand floor sat 5th to 20th
  // under fifteen that are not at a band at all — the one column carrying a
  // MEASURED gate (+8.6pp over 31,861 events) was the one you could not sort.
  {
    name: 'the growth board sorts by demand, unknown pinned last (2026-09-12)',
    file: 'src/lib/growthSort.ts',
    checks: (src) => {
      const errs = [];
      // The ladder is ordered by distance from the measured gate.
      if (!/DEMAND_INTACT = 3/.test(src) || !/DEMAND_PIERCED = 2/.test(src)
          || !/DEMAND_OUT = 1/.test(src)) {
        errs.push('the demand ladder must stay intact > pierced > out');
      }
      // The rule the whole sort turns on.
      if (!/va\.known !== vb\.known/.test(src)) {
        errs.push('an unknown must be compared BEFORE the direction sign is applied');
      }
      if (/sign \* \(va\.known/.test(src)) {
        errs.push('an unknown must never flip to the top of an ascending sort');
      }
      // in-band + intact null is UNKNOWN, not pierced.
      if (!/z\.intact === false/.test(src) || !/z\.intact === true/.test(src)) {
        errs.push('intact must be tested for true/false explicitly — null is neither');
      }
      if (!/DEFAULT_SORT: GrowthSortKey = 'demand'/.test(src)) {
        errs.push('the board must OPEN on demand — that was the ask');
      }
      if (!/\[\.\.\.rows\]\.sort/.test(src)) {
        errs.push('the sort must copy; sorting the payload in place makes order click-dependent');
      }
      return errs;
    },
  },
  {
    name: 'the growth demand cell never calls an unknown floor pierced (2026-09-12)',
    file: 'src/components/ExplosiveGrowth.tsx',
    checks: (src) => {
      const errs = [];
      if (!/floor \?/.test(src)) {
        errs.push('an unanswered floor check needs its own label, not the pierced one');
      }
      if (!/z\.intact === true/.test(src)) {
        errs.push('a truthy test on intact reads null as pierced — state a fact nobody checked');
      }
      if (!/aria-sort=/.test(src)) {
        errs.push('the live sort column must announce itself');
      }
      if (!/sortRows\(r, sortKey, sortDir\)/.test(src)) {
        errs.push('the sort must run on the FILTERED rows, not the raw payload');
      }
      return errs;
    },
  },
  // Ajay 2026-09-12: "create a tab for me. I wanna track his stocks for
  // investing". He does not post a portfolio — his timeline mixes forward ideas
  // with past-tense recaps of CLOSED trades, several of them PUTS, and one post
  // carries both directions across its own tickers ("caught the upside on $FSLR
  // and downside on $META $TSLA"). A bare ticker list inverts him.
  {
    name: 'the GnT board shows sentences and claims no direction (2026-09-12)',
    file: 'src/components/GntBoard.tsx',
    checks: (src) => {
      const errs = [];
      if (!/last_post/.test(src) || !/gnt-said/.test(src)) {
        errs.push('every row must carry the post that produced it');
      }
      if (!/ageText/.test(src)) {
        errs.push('a row must show its AGE — a 2022 recap must not read as current');
      }
      // The chips are evidence words, never a verdict. Checked against the
      // CODE with comments stripped — the header comment explains at length
      // why there is no direction here, and must not trip its own rule.
      const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
      for (const bad of [/\bdirection\s*[:=]/i, /\bbias\s*[:=]/i, /\bsignal\s*[:=]/i,
                         /t\.direction/i]) {
        if (bad.test(code)) {
          errs.push('the board must not resolve his words into a direction field');
        }
      }
      if (!/BEARISH/.test(src)) {
        errs.push('a put mention must be visibly bearish, or a short reads as a pick');
      }
      if (!/not scanned/.test(src)) {
        errs.push('a name outside the scan universe must say so — it is invisible to every board here');
      }
      if (!/read the sentence, not the ticker/i.test(src)) {
        errs.push('the caveat must ride on the board, not only in a doc');
      }
      return errs;
    },
  },
  {
    name: 'Chart Maps carries the 📌 GnT tab, not as a tile board (2026-09-12)',
    file: 'src/lib/chartMaps.ts',
    checks: (src) => {
      const errs = [];
      if (!/'gnt'/.test(src)) errs.push('the tab key must exist');
      // Parsed, not measured by character distance. The old regex demanded
      // 'gnt' within 400 chars of the CM_TABS declaration, which is a proxy
      // for "is in the list" that breaks the moment a comment is added above
      // it — as one was on 2026-09-13, failing this contract over a change
      // that never touched the GnT tab.
      if (!(parseCmTabs(src) || []).includes('gnt')) errs.push('the tab must be in the tab order');
      if (!/t !== 'gnt'/.test(src)) {
        errs.push('the GnT board is its own table, not a zone-tile board');
      }
      const meta = /gnt:\s*\{[\s\S]*?blurb:\s*'([\s\S]*?)',\n\s*\},/.exec(src);
      if (!meta) errs.push('the tab needs a label and a blurb');
      else {
        const b = meta[1];
        if (!/NOT advice/i.test(b)) errs.push('the blurb must say his calls are not advice');
        if (!/2,115\.1%/.test(b)) errs.push('the cited championship number must be stated');
        if (!/USICOfficial/.test(b)) errs.push('the championship claim must carry its SOURCE');
        if (!/gates a scan, an alert or a lane/i.test(b)) {
          errs.push('the blurb must say the board gates nothing');
        }
      }
      return errs;
    },
  },
  // Ajay 2026-09-13: "create me a Bonde tab … I wanna see his stocks."
  // It shipped that morning on the thesis that his SALES screen is the universe
  // and the EPISODIC PIVOT is the entry, so the intersection is the selection.
  // Two measurement passes the same day — the second an independent audit on
  // ~2x the panel — put that intersection at a 21-day median −3.22% against
  // −0.11% for date-matched non-Pivot names. The board therefore leads with the
  // verdict, and these are the sentences it may not lose.
  {
    name: 'the Bonde tab leads with its INVERTED measurement (2026-09-13)',
    file: 'src/lib/chartMaps.ts',
    checks: (src) => {
      const errs = [];
      if (!(parseCmTabs(src) || []).includes('bonde')) errs.push('the tab must be in the tab order');
      if (!/t !== 'bonde'/.test(src)) errs.push('the Bonde board is its own table, not a zone-tile board');
      const meta = /bonde:\s*\{[\s\S]*?blurb:\s*'([\s\S]*?)',\n\s*\},/.exec(src);
      if (!meta) { errs.push('the tab needs a label and a blurb'); return errs; }
      // The blurb is written with \uXXXX escapes, and reading the file as TEXT
      // leaves those escapes literal — so a check for a real minus sign or an
      // emoji silently never matches. Decode first, then assert on what the
      // reader actually sees.
      const b = meta[1].replace(/\\u([0-9a-fA-F]{4})/g,
                                (_, h) => String.fromCharCode(parseInt(h, 16)));
      if (!/^MEASURED 2026-09-13 AND THIS BOARD\u2019S OWN THESIS IS INVERTED/.test(b)) {
        errs.push('the blurb must OPEN with the verdict — the rules come after it');
      }
      // A rate never ships without its placebo and its interval.
      for (const [re, msg] of [
        [/\u22123\.22%/, 'the measured median must be stated'],
        [/\u22120\.11%/, 'the PLACEBO must be printed beside the rate'],
        [/CI \u22125\.28 to \u22121\.16/, 'the confidence interval must travel with the lift'],
        [/separated nothing at any horizon/, 'the sales gate measuring null on its own must be stated'],
        [/backend\/scripts\/bonde_audit\//, 'the re-runnable script must be named'],
        [/NOT A LICENCE TO SHORT/, 'an inverted result must not read as a short signal'],
        [/MEDIAN of \+0\.45pp and \+0\.37pp/, 'tier lifts must print the MEDIAN, not only the mean'],
        [/never sorts on the 0-100 sales score/, 'the score must be declared as a non-ranking'],
        [/\ud83d\udd0e section/, 'the rejected cohort section must be explained'],
      ]) if (!re.test(b)) errs.push(msg);
      // The struck claims must not come back. The first pass's punchiest
      // sentence did not reproduce (−2.42pp, CI −4.88 to +0.30).
      if (/loses to Pivot\+FAIL \(\u22123\.36/.test(b) || /\u22123\.36pp/.test(b)) {
        errs.push('the struck A-vs-B claim must not be printed');
      }
      if (/BOTH character clauses are inverted(?!\))/.test(b) && !/that BOTH character clauses are inverted,/.test(b)) {
        errs.push('only the consistency clause is inverted — `accelerating` is a null');
      }
      return errs;
    },
  },
  {
    name: 'the Bonde verdict banner is SERVED, never typed into the board (2026-09-13)',
    file: 'src/components/BondeBoard.tsx',
    checks: (src) => {
      const errs = [];
      if (!/measured\?:\s*BondeMeasured/.test(src) && !/measured\?: BondeMeasured/.test(src)) {
        errs.push('the payload must carry the served verdict');
      }
      if (!/m\?\.headline/.test(src) || !/bd-verdict/.test(src)) {
        errs.push('the banner must render from the served object');
      }
      // Numbers typed into TSX are numbers that go stale silently. The tier
      // blurbs are prose written once with the tab; the VERDICT is served.
      const banner = /bd-verdict[\s\S]*?<\/div>\s*\)\}/.exec(src);
      if (banner && /\d\.\d\dpp/.test(banner[0])) {
        errs.push('the banner must not hard-code a measured figure — it comes from sepa/bonde.py::MEASURED');
      }
      if (!/rejected/.test(src) || !/NOT ON HIS SCREEN/.test(src)) {
        errs.push('the cohort his gate rejects must be shown and labelled as not on his screen');
      }
      if (!/k !== SECTION_REJECTED|'rejected'/.test(src)) {
        errs.push('the rejected section must exist as its own key');
      }
      return errs;
    },
  },
  {
    name: 'the \u{1F9E8} explosive chip reaches every renderer, PROP-FED, with no maths in the TSX (2026-09-15)',
    file: 'src/lib/chartMaps.ts',
    // Twin of the \u{1F680} growth-chip contract above, with three extra teeth the
    // explosive read needs and growth does not:
    //   * the batcher / per-chip hook from the rev-1 plan must NOT exist — one
    //     page-level useBounceRoom per list is the whole serving design, and a
    //     batcher would hide a 24-request fan-out behind a tidy import;
    //   * the chip must not re-implement the score. The score is fit and frozen
    //     in backend/supply_demand/explosive.py; a percentile recomputed in TSX
    //     is a second, drifting engine;
    //   * no measured figure may be typed into the banner JSX (the Bonde rule)
    //     — the verdict is SERVED, so a re-run changes the board without a
    //     frontend deploy, and a stale number can never sit on his screen.
    // \u{1F680} Explosive Growth is IN this map, unlike the growth contract that
    // skips it: it is the growth list, but it is not the explosive read.
    checks: (src) => {
      const errs = [];
      const tabs = parseCmTabs(src);
      if (!tabs) return ['CM_TABS declaration not found'];

      const RENDERER = {
        hot_pullback: 'src/components/HotPullbackBoard.tsx',
        patterns: 'src/pages/PatternsPage.tsx',
        session: 'src/components/SessionBoard.tsx',
        signals: 'src/components/SignalLabBoard.tsx',
        hot_sectors: 'src/components/HottestSectors.tsx',
        catalysts: 'src/pages/Catalysts.tsx',
        overnight: 'src/components/OvernightGappers.tsx',
        support: 'src/components/SupportLevels.tsx',
        gnt: 'src/components/GntBoard.tsx',
        bonde: 'src/components/BondeBoard.tsx',
        holdings: 'src/components/HoldingsBoard.tsx',
        potus: 'src/components/PotusBoard.tsx',
        growth: 'src/components/ExplosiveGrowth.tsx',
      };
      const nonBoard = tabs.filter((t) => !/^(zones|deep_demand|quick_bounce|breaking|gabbar|vcp|topping|ict|undervalue|zero_dte|earnings|winners|keltner|amd|ipo)$/.test(t));
      for (const t of nonBoard) {
        const file = RENDERER[t];
        if (!file) {
          errs.push(`tab '${t}' has no renderer listed in the explosive contract — add it and give it an <ExplosiveChip>`);
          continue;
        }
        const tsx = read(file);
        if (!/<ExplosiveChip\s/.test(tsx)) {
          errs.push(`${file} (tab '${t}') does not render <ExplosiveChip>`);
        }
        // The read must come from a list-level bounce-room map, never a fetch
        // the chip makes for itself.
        if (/<ExplosiveChip[^>]*read=\{[^}]*fetch/.test(tsx)) {
          errs.push(`${file} feeds the chip from a fetch — the read rides on the page's one bounce-room map`);
        }
      }

      /* The opt-in ordering checkbox rides on every list renderer EXCEPT two,
       * and both exemptions are deliberate — so each one has to SAY SO in its
       * own file. An absent toggle and a drifted toggle look identical from
       * here; the written reason is the difference.
       *   support — one symbol per tab, there is no list to order (spec §6.4);
       *   hot_sectors — the payload keeps only `names_per_group` rows per group and
       *             the column sorts are a SERVER round-trip for exactly that
       *             reason; a browser reorder would rank the visible 25 and
       *             never reach the 305th Technology name. Ranking these rows
       *             by the explosive read belongs where the truncation happens
       *             (a backend sort key) — HIS CALL, not a silent FE reorder.
       */
      const NO_TOGGLE = {
        support: /no ordering to offer/,
        hot_sectors: /NO \u{1F9E8} ordering toggle on this board, deliberately/u,
        //   potus — the list is drawn in a FIXED editorial order (stake →
        //           contractor → family → inferred); an ordering toggle would
        //           turn a curated disclosure list into a ranking, which is
        //           the one thing the tab says on its face it is not.
        potus: /editorial order, not a ranking/,
      };
      for (const t of nonBoard) {
        const file = RENDERER[t];
        if (!file) continue;
        const tsx = read(file);
        const why = NO_TOGGLE[t];
        if (why) {
          if (/<ExplosiveFirstToggle\s/.test(tsx)) {
            errs.push(`${file} (tab '${t}') mounts <ExplosiveFirstToggle> but is listed as deliberately un-ordered — drop it from NO_TOGGLE in this contract if that is now intended`);
          } else if (!why.test(tsx)) {
            errs.push(`${file} (tab '${t}') has no \u{1F9E8} ordering toggle and no longer states why — an unexplained omission is indistinguishable from drift`);
          }
        } else if (!/<ExplosiveFirstToggle\s/.test(tsx)) {
          errs.push(`${file} (tab '${t}') renders the chip but offers no <ExplosiveFirstToggle> — every list board gets the opt-in ordering`);
        }
      }

      // Every board tab funnels through the one tile component, and its read
      // rides on the tile (chart_maps/board.attach_explosive) — no request.
      const tile = read('src/components/PatternChart.tsx');
      if (!/<ExplosiveChip\s+read=\{tile\.explosive\}/.test(tile)) {
        errs.push('PatternChart must render <ExplosiveChip read={tile.explosive}> — it is the one renderer behind every board tab');
      }

      // The rev-1 batcher / per-chip hook must not exist ANYWHERE.
      for (const gone of ['src/lib/explosiveBatcher.ts', 'src/hooks/useExplosiveRead.ts']) {
        let exists = true;
        try { read(gone); } catch { exists = false; }
        if (exists) errs.push(`${gone} must not exist — one page-level useBounceRoom per list is the serving design`);
      }
      const chip = read('src/components/ExplosiveChip.tsx');
      if (/\bfetch\s*\(/.test(chip) || /useEffect/.test(chip)) {
        errs.push('ExplosiveChip must be PROP-FED — it never fetches and holds no state');
      }
      if (/explosiveBatcher|useExplosiveRead/.test(chip)) {
        errs.push('ExplosiveChip must not import a batcher or a per-chip read hook');
      }
      // No score maths in the TSX: the score is frozen in explosive.py.
      if (/\b(rsi|rvol|quantile|percentile)\b/i.test(chip)) {
        errs.push('ExplosiveChip must not re-implement the score — it renders what explosive.py measured');
      }
      const hook = read('src/hooks/useExplosiveOrder.ts');
      if (/\bfetch\s*\(/.test(hook)) {
        errs.push('useExplosiveOrder must not fetch — it reads the map the page already has');
      }

      // The verdict banner is SERVED. A typed figure goes stale in silence.
      const page = read('src/pages/ChartMaps.tsx');
      if (!/explosive_study\?\.headline/.test(page)) {
        errs.push('ChartMaps must render the served explosive_study headline');
      }
      if (!/<RulesInfo section="explosive"/.test(page)) {
        errs.push('the \u{1F9E8} rules section must be mounted where RulesInfo already sits');
      }
      const banner = /cm-explosive-study[\s\S]*?<\/div>\s*\)\}/.exec(page);
      if (banner && (/\d\.\d\dpp/.test(banner[0]) || /\d+\.\d%/.test(banner[0]))) {
        errs.push('the explosive banner must not hard-code a measured figure — it comes from explosive.py::MEASURED');
      }

      const css = read('src/styles.css');
      for (const c of ['cm-badge-explosive', 'cm-badge-explosive-muted', 'hs-badge-explosive',
                       'sb-chip-explosive', 'bd-gchip-explosive', 'eg-explosive', 'ex-toggle']) {
        if (!new RegExp('\\.' + c + '(?![\\w-])').test(css)) {
          errs.push(`.${c} has no CSS rule — the chip would ship unstyled`);
        }
      }
      return errs;
    },
  },
  {
    name: 'the \u{1FA9C} band-structure read: one ordering key, PROP-FED chips, no maths in the TSX (2026-09-16)',
    file: 'src/lib/bandStructure.ts',
    // Ajay 2026-09-16, two messages one minute apart: "prioritize stock by the
    // thinnest over head or Supply zone where ever is applicable" and "the
    // support bands are bigger and atleast another one very close if its falls
    // below the first support level. Something like CRDO had at 149."
    //
    // Same teeth as the \u{1F9E8} contract above, plus the two this read needs:
    //   * the ordering key is MIRRORED, not re-derived — the fixture both
    //     suites sort must exist and must be the one this file names;
    //   * the chip prints the SERVED sentence. A percentage formatted in TSX
    //     is a second engine, and a `gap_pct` of null rendered as 0 would turn
    //     "no second catch" into "the second catch touches the first".
    //
    // SINCE 2026-09-16 the ROW boards are checked too (check 7). His ask was
    // "in all chartmaps tabs", and ten of them are row boards fed by
    // POST /supply-demand/bounce-room, which now serves `band_structure` on the
    // row the way it serves `enterable`. They were the one gap the \u{1F3AF}
    // contract's own "every \u{1F9E8} mount also mounts \u{1F3AF}" rule would not
    // have caught, because the chip was simply never mounted there at all.
    //
    // WHAT IS STILL DELIBERATELY NOT CHECKED: a row-board ORDERING. Re-ranking
    // a row board is HIS call; the chip is a read, and nothing on that path
    // applies `compareBandStructure`.
    checks: (src) => {
      const errs = [];

      // 1. The ordering key is a mirror of a file both suites read.
      const FIXTURE = 'backend/tests/fixtures/band_structure_order_mirror_2026_09_16.json';
      if (!src.includes(FIXTURE)) {
        errs.push(`src/lib/bandStructure.ts must name ${FIXTURE} — the ordering is pinned against the file the backend suite sorts`);
      }
      let fx = null;
      try {
        fx = JSON.parse(readFileSync(join(FRONTEND_ROOT, '..', FIXTURE), 'utf8'));
      } catch {
        errs.push(`${FIXTURE} is missing — the frontend/backend ordering mirror has nothing to pin against`);
      }
      if (fx && !(Array.isArray(fx.expected_no_signal) && Array.isArray(fx.expected_separates))) {
        errs.push(`${FIXTURE} must carry BOTH expected orders — only one branch will ever be live and both must be pinned`);
      }
      if (!/backend\/supply_demand\/band_structure\.py/.test(src)) {
        errs.push('src/lib/bandStructure.ts must name the backend module it mirrors');
      }

      // 2. No maths. Every number is served inside `read.stat`; a threshold,
      //    a quantile or a percentage assembled here is a second engine.
      if (/\btoFixed\s*\(\s*[12]\s*\)\s*\+\s*'%'|`\$\{[^`]*\}%`/.test(src)) {
        errs.push('src/lib/bandStructure.ts must not format a percentage — the stat sentence is served by band_structure.py::stat_line');
      }
      for (const banned of ['quantile', 'percentile', 'MIN_PCT', 'THRESHOLD']) {
        if (new RegExp(`\\b${banned}\\b`).test(src)) {
          errs.push(`src/lib/bandStructure.ts must not carry a ${banned} — no threshold is invented on this side`);
        }
      }

      // 3. The chip is PROP-FED and renders nothing rather than guessing.
      const chip = read('src/components/BandStructureChip.tsx');
      if (/\bfetch\s*\(/.test(chip) || /useEffect|useState/.test(chip)) {
        errs.push('BandStructureChip must be PROP-FED — it never fetches and holds no state');
      }
      if (/toFixed\s*\(|\*\s*100|\/\s*100/.test(chip)) {
        errs.push('BandStructureChip must not compute a number — it prints the served stat');
      }

      // 4. The one tile renderer behind every board tab carries it, fed off
      //    the tile (chart_maps/board.attach_band_structure) — no request.
      const tile = read('src/components/PatternChart.tsx');
      if (!/<BandStructureChip\s+read=\{tile\.band_structure\}/.test(tile)) {
        errs.push('PatternChart must render <BandStructureChip read={tile.band_structure}> — it is the one renderer behind every board tab and the Support tab');
      }

      // 5. The verdict banner is SERVED, and so is the scope note. A typed
      //    figure goes stale in silence (the Bonde rule).
      const page = read('src/pages/ChartMaps.tsx');
      if (!/band_structure_study\?\.headline/.test(page)) {
        errs.push('ChartMaps must render the served band_structure_study headline');
      }
      if (!/band_structure_scope/.test(page)) {
        errs.push('ChartMaps must render the served band_structure_scope — the sort runs after the board was cut to its page size and has to say so');
      }
      if (!/sort_unavailable/.test(page)) {
        errs.push('ChartMaps must render sort_unavailable — a board with no band read keeps its served order and shows the reason');
      }
      const banner = /cm-band-study[\s\S]*?<\/div>\s*\)\}/.exec(page);
      if (banner && (/\d\.\d\dpp/.test(banner[0]) || /\d+\.\d%/.test(banner[0]))) {
        errs.push('the band-structure banner must not hard-code a measured figure — it comes from band_structure.py::MEASURED');
      }

      // 6. Styled, or it ships invisible.
      const css = read('src/styles.css');
      for (const c of ['cm-badge-band', 'cm-badge-band-muted', 'sb-chip-band',
                       'sb-chip-band-muted', 'hs-badge-band', 'hs-badge-band-muted',
                       'cm-band-study']) {
        if (!new RegExp('\\.' + c + '(?![\\w-])').test(css)) {
          errs.push(`.${c} has no CSS rule — the chip would ship unstyled`);
        }
      }

      // 7. THE TEN ROW BOARDS (2026-09-16). Ajay: "Now in all chartmaps tabs".
      //    These tabs are not tiles — they are lists fed by the bounce-room
      //    route — so the \u{1FA9C} read reaches them only if each renderer mounts
      //    the chip off the served row AND prints the served no-read sentence
      //    when nothing on the list came back with one. Silence on a tab is
      //    exactly what this check exists to stop: the six `n/a` tabs say why,
      //    and these ten used to say nothing at all.
      //
      //    NOT in this list, each for a written reason:
      //      HoldingsBoard / SupportLevels — they render through PatternChart,
      //        which check 4 already pins (tile.band_structure).
      //      Alerts.tsx — a push-time verdict, not a live band read.
      //      Sepa.tsx / DemandReentryPanel — bounce-room consumers that are not
      //        Chart Maps tabs.
      const ROW_BOARDS = [
        'src/components/BondeBoard.tsx', 'src/components/GntBoard.tsx',
        'src/components/SessionBoard.tsx', 'src/components/HotPullbackBoard.tsx',
        'src/components/OvernightGappers.tsx', 'src/components/HottestSectors.tsx',
        'src/components/SignalLabBoard.tsx', 'src/components/ExplosiveGrowth.tsx',
        'src/pages/PatternsPage.tsx', 'src/pages/Catalysts.tsx',
      ];
      for (const rel of ROW_BOARDS) {
        const tsx = read(rel);
        if (!tsx) { errs.push(`${rel} is unreadable — the \u{1FA9C} row check cannot run`); continue; }
        const mounts = /<BandStructureChip\s/.test(tsx);
        // SessionBoard and SignalLabBoard put the served read on the TILE the
        // one renderer (PatternChart) already reads it from, rather than a
        // second chip mount with its own rules — either is the read reaching
        // the tab, neither is a re-derivation.
        const onTile = /band_structure:\s*room\.map\.get/.test(tsx);
        if (!mounts && !onTile) {
          errs.push(`${rel} never shows the \u{1FA9C} read — Ajay asked for it "in all chartmaps tabs" and this is one of the ten row boards`);
        }
        if (!/\?\.band_structure\b/.test(tsx)) {
          errs.push(`${rel} must read the SERVED bounce-room row field \`band_structure\` — never a second derivation`);
        }
        if (!/band_structure_coverage\?\.note|ex\?\.bandNote/.test(tsx)) {
          errs.push(`${rel} must render the served band_structure_coverage.note — a board with no read anywhere has to SAY so, the way the \u{1F3AF} n/a tabs do`);
        }
        if (!/data-testid="band-structure-note"/.test(tsx)) {
          errs.push(`${rel} must tag the no-read line data-testid="band-structure-note" so its own suite can pin that it appears`);
        }
        if (/compareBandStructure|bandStructureOrderKey/.test(tsx)) {
          errs.push(`${rel} applies a \u{1FA9C} ORDERING — ordering on row boards is HIS call and was not asked for`);
        }
      }
      return errs;
    },
  },
  {
    name: 'the \u{1F3AF} enterable read reaches every renderer, hides nothing silently (2026-09-15)',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-15: "I only wanna see the stocks that are enterable ... I do
    // not want to see not enterable alerts or stocks in any of the chart maps."
    //
    // A filter that is ON by default is the one kind of feature that can lose
    // him a name without ever showing an error, so the teeth here are about
    // absence rather than correctness:
    //   * a renderer that shows the \u{1F9E8} chip but not the \u{1F3AF} one is a tab where
    //     the read silently stops — the two ride the same list;
    //   * the count line and the escape hatch must exist on the page, because
    //     "30 hidden" with no way back is indistinguishable from an empty board;
    //   * the three exemptions (a position, a one-symbol tab, a server-cut
    //     list) must SAY SO in their own file — an absent partition and a
    //     dropped one look identical from here;
    //   * no verdict maths in the library or the chip: READY / WATCH / BLOCKED
    //     and every reason word are built in supply_demand/enterable.py from
    //     the enforcing constants (ALERT_MIN_ROOM_PCT, ALERT_MAX_ABOVE_DEMAND_PCT,
    //     FLOOR_HELD_STATES, premarket_entry's measured drags). A second copy in
    //     TSX drifts the first time one of them moves;
    //   * ENTERABLE_KIND must equal the backend's KIND_BY_TAB key for key — the
    //     same fixture both suites read. A tab that silently changes kind on one
    //     side only is a tab that hides rows for a reason nobody served.
    checks: (src) => {
      const errs = [];

      /* 1. Every file that mounts the 🧨 chip mounts the 🎯 chip. */
      const dirs = ['src/components', 'src/pages'];
      const mounts = [];
      for (const dir of dirs) {
        let names = [];
        try {
          names = readdirSync(join(FRONTEND_ROOT, dir));
        } catch {
          errs.push(`${dir} is unreadable`);
          continue;
        }
        for (const n of names) {
          if (!n.endsWith('.tsx') || n.endsWith('.test.tsx')) continue;
          const rel = `${dir}/${n}`;
          const tsx = read(rel);
          if (/<ExplosiveChip\s/.test(tsx)) mounts.push([rel, tsx]);
        }
      }
      if (!mounts.length) errs.push('no renderer mounts <ExplosiveChip> — did the chip get renamed?');
      for (const [rel, tsx] of mounts) {
        if (!/<EnterableChip\s/.test(tsx)) {
          errs.push(`${rel} shows the \u{1F9E8} chip but not <EnterableChip> — the \u{1F3AF} read stops on that surface`);
        }
      }

      /* 2. The chip renders, it does not decide. */
      const chip = read('src/components/EnterableChip.tsx');
      if (/\bfetch\s*\(/.test(chip) || /useEffect/.test(chip)) {
        errs.push('EnterableChip must be PROP-FED — it never fetches and holds no state');
      }
      if (/room_pct|ALERT_MIN|\d+(\.\d+)?\s*(?:<=|>=|<|>)|(?:<=|>=|<|>)\s*\d/.test(chip)) {
        errs.push('EnterableChip must not compare a number — the verdict is served by enterable.py');
      }

      /* 3. The library mirrors; it never grades. The regex is ANCHORED to an
       *    assignment so the `type EnterableVerdict = 'READY'|…` line passes. */
      const lib = read('src/lib/enterable.ts');
      if (/verdict\s*[:=]\s*'(READY|WATCH)'/.test(lib)) {
        errs.push('lib/enterable.ts assigns a verdict — READY/WATCH/BLOCKED come from the backend, always');
      }
      const libTest = read('src/lib/enterable.test.ts');
      if (!/\.\.\/\.\.\/\.\.\/backend\/tests\/fixtures\/enterable_mirror_2026_09_15\.json/.test(libTest)) {
        errs.push('lib/enterable.test.ts must pin the partition against the SHARED backend fixture');
      }

      /* 4. ENTERABLE_KIND == the backend's KIND_BY_TAB, key for key. */
      const m = /export const ENTERABLE_KIND\s*=\s*\{([\s\S]*?)\}\s*as\s/.exec(src);
      if (!m) {
        errs.push('ENTERABLE_KIND declaration not found in lib/chartMaps.ts');
      } else {
        const fe = {};
        for (const pair of m[1].replace(/\/\/[^\n]*/g, '').matchAll(/([A-Za-z_][\w]*)\s*:\s*'([^']+)'/g)) {
          fe[pair[1]] = pair[2];
        }
        let fx = null;
        try {
          fx = JSON.parse(read('../backend/tests/fixtures/enterable_mirror_2026_09_15.json'));
        } catch {
          errs.push('backend/tests/fixtures/enterable_mirror_2026_09_15.json is unreadable — the mirror is the contract');
        }
        const be = fx && fx.kind_by_tab;
        if (be) {
          const keys = new Set([...Object.keys(fe), ...Object.keys(be)]);
          const bad = [...keys].filter((k) => fe[k] !== be[k]).sort();
          if (bad.length) {
            errs.push(`ENTERABLE_KIND disagrees with the backend KIND_BY_TAB on: ${bad.join(', ')}`);
          }
        }
      }

      /* 5. The page: the toggle, the count line, the rules section, the served
       *    banner — and no measured figure typed into it. */
      const page = read('src/pages/ChartMaps.tsx');
      for (const [re, msg] of [
        [/<EnterableOnlyToggle\s/, 'ChartMaps must mount <EnterableOnlyToggle> — the filter is ON by default and he must be able to turn it off'],
        [/<HiddenCount\s/, 'ChartMaps must mount <HiddenCount> — a hidden row is never allowed to be silent'],
        [/<RulesInfo section="enterable"/, 'the \u{1F3AF} rules section must be mounted where RulesInfo already sits'],
        [/enterable_study\?\.headline/, 'ChartMaps must render the SERVED enterable_study headline'],
      ]) {
        if (!re.test(page)) errs.push(msg);
      }
      const banner = /cm-enterable-study[\s\S]*?<\/div>\s*\)\}/.exec(page);
      if (banner && (/\d\.\d\dpp/.test(banner[0]) || /\d+\.\d%/.test(banner[0]))) {
        errs.push('the \u{1F3AF} banner must not hard-code a measured figure — it comes from enterable.py::MEASURED');
      }

      /* 6. The three exemptions say so in their own file. */
      for (const [rel, phrase] of [
        ['src/components/HoldingsBoard.tsx', 'never hides a position'],
        ['src/components/SupportLevels.tsx', 'one symbol'],
        ['src/components/HottestSectors.tsx', 'server-cut'],
      ]) {
        if (!read(rel).includes(phrase)) {
          errs.push(`${rel} must say "${phrase}" — an exemption without a written reason is indistinguishable from a drop`);
        }
      }

      /* 7. The Alerts page carries the push-time verdict and names the counter. */
      const alerts = read('src/pages/Alerts.tsx');
      if (!/<EnterableChip\s+read=\{row\.enterable\}/.test(alerts)) {
        errs.push('the Alerts page must show the PUSH-TIME verdict from row.enterable');
      }
      if (!alerts.includes('skipped_not_enterable')) {
        errs.push('the Alerts page must label skipped_not_enterable — it is a divergence guard and must read as one');
      }

      /* 8. The count line says both halves of what it offers. */
      const count = read('src/components/HiddenCount.tsx');
      if (!/hidden/.test(count) || !/show all/.test(count)) {
        errs.push('HiddenCount must print both the hidden count and the "show all" way back');
      }

      /* 9. Every class ships a rule. */
      const css = read('src/styles.css');
      for (const c of ['cm-badge-enterable-ready', 'cm-badge-enterable-watch',
                       'cm-badge-enterable-blocked', 'cm-badge-enterable-na',
                       'hs-badge-enterable-ready', 'sb-chip-enterable-ready',
                       'bd-gchip-enterable-ready', 'eg-enterable-ready',
                       'en-toggle', 'cm-hidden-count']) {
        if (!new RegExp('\\.' + c + '(?![\\w-])').test(css)) {
          errs.push(`.${c} has no CSS rule — the chip would ship unstyled`);
        }
      }

      /* 10. The ✨ entry. */
      if (!read('src/lib/newFeatures.ts').includes('enterable-read-2026-09-15')) {
        errs.push('newFeatures.ts is missing the ✨ entry for the enterable read');
      }

      return errs;
    },
  },
  // ── 🎯 Un-hide by reason (Ajay 2026-09-17: "Can you give me a toggle for the
  //    room too? I am not seeing all stocks on the selected filter due to this
  //    now") ──────────────────────────────────────────────────────────────────
  {
    name: 'every hidden-count line offers its reason chips, and the chips say only what was SERVED (2026-09-17)',
    file: 'src/components/HiddenCount.tsx',
    // The words the count line prints are now buttons. Two failure modes are
    // worth a build break:
    //   * a <HiddenCount> that is mounted without `reasons` / `onToggleReason`
    //     inside the provider is a filter he can SEE but not reach — and a new
    //     board added later would inherit the page ignore set silently, which is
    //     exactly what the no-localStorage rule exists to prevent. So the list of
    //     call sites is ENUMERATED, not shape-matched: a new one has to be added
    //     here on purpose.
    //   * a reason string typed into this component is a second definition of a
    //     gate's wording. Every label comes from the served `reason_short`.
    checks: () => {
      const errs = [];

      /* 1. No reason wording lives in the component. */
      const count = read('src/components/HiddenCount.tsx');
      for (const lit of ['room <', 'not at band', 'no band', 'no lid break',
                         'floor swept', 'floor broken', 'break >']) {
        if (count.includes(lit)) {
          errs.push(`HiddenCount.tsx contains the literal reason string "${lit}" — every chip label is the SERVED reason_short, passed in as a prop`);
        }
      }

      /* 2. Every one of the thirteen call sites is wired. */
      const SITES = [
        ['src/pages/ChartMaps.tsx', 1],
        ['src/components/BondeBoard.tsx', 1],
        ['src/components/HottestSectors.tsx', 1],
        ['src/components/ExplosiveGrowth.tsx', 1],
        ['src/components/SessionBoard.tsx', 1],
        ['src/components/SignalLabBoard.tsx', 1],
        ['src/components/OvernightGappers.tsx', 1],
        ['src/components/HotPullbackBoard.tsx', 1],
        ['src/components/GntBoard.tsx', 1],
        ['src/pages/Catalysts.tsx', 2],
        ['src/pages/PatternsPage.tsx', 2],
      ];
      const expected = new Map(SITES);
      for (const [rel, want] of SITES) {
        const tsx = read(rel);
        const blocks = tsx.split(/<HiddenCount\s/).slice(1);
        if (blocks.length !== want) {
          errs.push(`${rel} has ${blocks.length} <HiddenCount> mounts, the contract lists ${want} — add the new one to this rule WITH its chips, or it inherits the page ignore set in silence`);
        }
        for (const b of blocks) {
          const el = b.slice(0, b.indexOf('/>') + 2);
          for (const prop of ['reasons=', 'onToggleReason=', 'unhidden=', 'unhideCount=']) {
            if (!el.includes(prop)) {
              errs.push(`${rel}: a <HiddenCount> is missing \`${prop}\` — a count line without its chips is a filter he cannot reach`);
            }
          }
        }
      }

      /* 3. No <HiddenCount> anywhere the list does not know about. */
      for (const dir of ['src/components', 'src/pages']) {
        let names = [];
        try {
          names = readdirSync(join(FRONTEND_ROOT, dir));
        } catch {
          errs.push(`${dir} is unreadable`);
          continue;
        }
        for (const n of names) {
          if (!n.endsWith('.tsx') || n.endsWith('.test.tsx')) continue;
          const rel = `${dir}/${n}`;
          if (expected.has(rel)) continue;
          if (/<HiddenCount\s/.test(read(rel))) {
            errs.push(`${rel} mounts <HiddenCount> but is not in this rule's list — add it WITH reasons/onToggleReason`);
          }
        }
      }

      /* 4. The URL param is named once, as the exported constant. */
      const lib = read('src/lib/chartMaps.ts');
      const hits = (lib.match(/'unhide'/g) || []).length;
      if (hits !== 1) {
        errs.push(`lib/chartMaps.ts spells the 'unhide' param ${hits} times — it must appear exactly once, as UNHIDE_PARAM`);
      }
      if (!/export const UNHIDE_PARAM = 'unhide';/.test(lib)) {
        errs.push('lib/chartMaps.ts must export UNHIDE_PARAM');
      }
      if (!/FAILS CLOSED/.test(lib)) {
        errs.push('parseUnhide must document that it FAILS CLOSED — an unreadable URL lands on the shipped filter, never on "show everything"');
      }

      /* 5. The rule stays a VIEW filter: no verdict, no ignore set on the wire. */
      const en = read('src/lib/enterable.ts');
      if (/verdict\s*[:=]\s*'(READY|WATCH)'/.test(en)) {
        errs.push('lib/enterable.ts assigns a verdict — the ignore set decides what is DRAWN, never what is enterable');
      }
      const page = read('src/pages/ChartMaps.tsx');
      if (/min_room=\$\{[^}]*unhide|unhide=\$\{/.test(page) || /boardQuery\([^)]*unhide/.test(page)) {
        errs.push('the un-hide selection must never reach the board query — it is a browser-side view filter');
      }

      /* 6. The classes ship a rule, and the ✨ entry exists. */
      const css = read('src/styles.css');
      for (const c of ['cm-hidden-reason', 'cm-hidden-reason-on']) {
        if (!new RegExp('\\.' + c + '(?![\\w-])').test(css)) {
          errs.push(`.${c} has no CSS rule — the chips would ship unstyled`);
        }
      }
      if (!read('src/lib/newFeatures.ts').includes('enterable-reason-unhide-2026-09-17')) {
        errs.push('newFeatures.ts is missing the ✨ entry for the un-hide chips');
      }
      return errs;
    },
  },
  // ── Deep Demand level filter (Ajay 2026-09-16: "can you do level 4 and
  //    give me filters for that") ────────────────────────────────────────────
  {
    name: 'the level chips count the board, never overstate the page (2026-09-16)',
    file: 'src/pages/ChartMaps.tsx',
    checks(src) {
      const errs = [];
      if (/would show under the current/i.test(src))
        errs.push('the chip tooltip still claims the count is what the level WOULD SHOW — it is counted before the 24-tile page cut');
      if (!/how many names sit at each level/i.test(src))
        errs.push('the chip tooltip must say the count is names AT that level on this board');
      if (!/shows the first 24/i.test(src))
        errs.push('the chip tooltip must say the page shows only the first 24 of them');
      if (!/levels/.test(src))
        errs.push('the deep_demand level filter is missing from ChartMaps');
      return errs;
    },
  },
  {
    name: 'the level-4 ✨ card keeps the store population out of the chip claim (2026-09-16)',
    file: 'src/lib/newFeatures.ts',
    checks(src) {
      const start = src.indexOf('deep-demand-level-4-filter');
      if (start < 0) return ['the deep-demand-level-4-filter ✨ entry is missing'];
      const next = src.indexOf("{ id: '", start);
      const entry = src.slice(start, next > start ? next : undefined);
      // Only the SERVED label — the comment above it quotes Ajay verbatim,
      // and his own words ("the returning bounce") are never rewritten.
      const lq = entry.indexOf('label:');
      const aq = entry.indexOf(', addedAt', lq);
      const card = lq < 0 ? entry : entry.slice(lq, aq > lq ? aq : undefined);
      const errs = [];
      if (/would show RIGHT NOW/i.test(card))
        errs.push('the card still claims the chip shows the store population');
      if (!/not of the whole store/i.test(card))
        errs.push('the card must say the chip counts the BOARD, not the store');
      if (!/2nd = 280, 3rd = 232, 4th = 56/.test(card))
        errs.push('the card must quote the measured store population, labelled as such');
      if (!/closest 60/.test(card))
        errs.push('the card must say the board carries only the closest 60 in-band / 40 approaching per level');
      if (/\bbounce\b/i.test(card))
        errs.push('house rule: the word is "reversal", never "bounce"');
      if (/CRDO[^.]{0,200}now (appears|shows)/i.test(card))
        errs.push('CRDO does NOT appear — it is blocked by the band-quality bar');
      return errs;
    },
  },
  {
    name: '🧭 the SPY/QQQ strip is pinned on the zones tab, says nothing about an edge, and never says "bounce" (2026-09-16)',
    file: 'src/pages/ChartMaps.tsx',
    // Ajay 2026-09-16, verbatim: "Can you create a SPY demand and supply zone
    // please for me? and also QQQ supply and demand zone and keep them always
    // in the in demand zone page. I need everything calculation overnight."
    //
    // "KEEP THEM ALWAYS" is a MOUNT-POINT fact, and a mount point is exactly
    // the kind of thing a rebase moves silently: dropped one level down into
    // the board branch, the strip would still render in every test that draws
    // a populated board and would vanish on the warming / erroring / empty
    // board — which is the only state he complained about. So the contract
    // pins that it sits OUTSIDE the board-tab branch, gated on `zones` alone.
    checks(src) {
      const errs = [];
      if (!/import IndexZones from '\.\.\/components\/IndexZones'/.test(src))
        errs.push('ChartMaps no longer imports IndexZones');
      const mount = /\{tab === 'zones' && <IndexZones data=\{data\?\.index_zones\} \/>\}/.exec(src);
      if (!mount) {
        errs.push("the pinned strip is not mounted as {tab === 'zones' && <IndexZones data={data?.index_zones} />}");
      } else {
        // It must come BEFORE the board-tab ternary — everything after that
        // line is the universe pass and its warming / error / empty branches.
        // Anchored on the JSX arm, not on the bare call: `!isBoardTab(tab)`
        // also appears in the loader, hundreds of lines above the render.
        const branch = src.indexOf(') : !isBoardTab(tab) ? (');
        if (branch < 0)
          errs.push('the board-tab ternary arm moved — re-anchor this contract');
        else if (mount.index > branch)
          errs.push('the strip is mounted INSIDE the board branch — it would vanish while the board is warming, erroring or empty');
      }
      let strip = '';
      try {
        strip = read('src/components/IndexZones.tsx');
      } catch {
        return [...errs, 'src/components/IndexZones.tsx is missing'];
      }
      // Every copy check runs on the source with its COMMENTS REMOVED and its
      // whitespace flattened. Comments removed because this file's header
      // explains the rules in the same words the copy uses — a contract a
      // comment can satisfy protects nothing (caught by mutating the live
      // sentence and watching the contract still pass). Whitespace flattened
      // because JSX text wraps across lines, so a re-indent would otherwise
      // disarm it in the other direction.
      const flat = strip
        .replace(/\/\*[\s\S]*?\*\//g, ' ')
        .replace(/(^|[^:])\/\/[^\n]*/g, '$1 ')
        .replace(/\s+/g, ' ');
      if (/\bbounce\b/i.test(strip))
        errs.push('house rule: the word is "reversal", never "bounce"');
      for (const [re, why] of [
        [/\b(an|the|its|our|measured|proven|real)\s+edge\b/i, 'the strip claims an edge'],
        [/\boutperform/i, 'the strip claims outperformance'],
        [/\b(buy|sell)\s+(signal|here|now|zone|the)\b/i, 'the strip reads as a buy/sell instruction'],
        [/\b(will|should)\s+(bounce|reverse|rally|hold|break)\b/i, 'the strip forecasts'],
      ]) {
        if (re.test(strip)) errs.push(why);
      }
      // …and it must say plainly what it is not.
      if (!/gates nothing, orders nothing, alerts nothing and enters nothing/.test(flat))
        errs.push('the strip must say it gates, orders, alerts and enters nothing');
      // The two bases have to stay separately labelled — this is the
      // 2026-09-16 hot-sectors correction, and it is one careless edit away.
      if (!/closed daily bars/.test(flat))
        errs.push('the strip must label the bands as closed-bar structure');
      if (!/it does not move a band/.test(flat))
        errs.push('the live overlay must say it does not move a band');

      /* ── 2026-09-16, the follow-up: "I wanna see charts with multiple
       * zones" · "For both QQQ and SPY". The picture IS the ask, so a
       * refactor that quietly leaves the text ladder alone on the card has
       * undone the feature even though every copy check above still passes. */
      if (!/import \{ PatternChart \} from '\.\/PatternChart'/.test(strip))
        errs.push('the strip no longer imports PatternChart — the chart is his headline ask');
      if (!/<PatternChart tile=\{tile\}/.test(strip))
        errs.push('the chart is not mounted — the card must lead with the picture, not the ladder');
      if (!/index-zone-chart-/.test(strip))
        errs.push('the chart has no testId — it cannot be pinned');
      // The chart is drawn from the SERVED closed bars, never from a live
      // print: `bars` comes off the read and nothing appends to it.
      if (!/Array\.isArray\(read\?\.bars\)/.test(strip))
        errs.push('the chart must draw the SERVED closed bars');
      if (/live_px[^\n]{0,80}bars|bars[^\n]{0,40}live_px/.test(strip))
        errs.push('a live print must never reach the chart bars');

      // The resolution toggle, and the labelling that keeps a FINE band from
      // being read as the BOARD band the rest of the page is drawn with.
      if (!/IZ_RES_KEYS/.test(strip) || !/'fine'/.test(strip) || !/'board'/.test(strip))
        errs.push('the fine/board resolution keys are gone');
      if (!/aria-pressed=\{value === k\}/.test(strip))
        errs.push('the resolution toggle is not a pressed-state control');
      if (!/index-zone-res-/.test(strip))
        errs.push('the resolution toggle has no testId');
      if (!/the set the demand engine and every tile under this strip are drawn with/.test(flat))
        errs.push('the Board arm must say it is the set the rest of the page is drawn with');
      if (!/Both are the same closed daily bars/.test(flat))
        errs.push('the toggle must say both resolutions sit on the same closed bars');

      // F1: the strip owns a FALLBACK request, because the board's load()
      // only setData()s on success — a 500 there used to make this card
      // announce an empty store about a doc that was sitting there fine.
      if (!/\/supply-demand\/index-zones/.test(strip))
        errs.push("the strip has no fallback fetch — a board 500 would blank it");
      if (!/the overnight job has not written one/.test(flat))
        errs.push('the empty-store placeholder copy is gone');
      if (!/request failure, not an empty store/.test(flat))
        errs.push('a failed request and an empty store must not share one sentence');

      // F2: sessions are counted with the SESSIONS key. `stale_days` is
      // calendar days and must never be printed beside the word "session".
      if (!/stale_sessions/.test(strip))
        errs.push('the header must print stale_sessions for the session count');
      if (/stale_days[^;]{0,120}session\b/.test(strip))
        errs.push('calendar days are being printed as sessions');

      // F7: the edges print their KIND — that is his source note's
      // broken-zone flip made visible on the page.
      if (!/e\.kind === 'supply'/.test(strip))
        errs.push('the ceiling/floor no longer print which kind of band they are');
      if (!/broken through is overhead from/.test(flat))
        errs.push('the card must explain that either nearest band can be either kind');

      // …and none of the new copy may claim the strip is worth anything.
      for (const [re, why] of [
        [/\bwin rate\b/i, 'the strip quotes a win rate'],
        [/\bbacktest(ed)?\b/i, 'the strip claims it was backtested'],
        [/\bhigh[- ]probability\b/i, 'the strip claims a probability'],
      ]) {
        if (re.test(strip)) errs.push(why);
      }
      return errs;
    },
  },
  {
    name: 'the ⌘K ticker ✨ card claims no edge and never says "bounce" (2026-09-18)',
    file: 'src/lib/newFeatures.ts',
    // Ajay 2026-09-18, verbatim: "can you make global search help find ickers
    // also directly in the same field". The palette merges pages and tickers;
    // the ranking is a UX choice, so the card must not dress it as a study.
    checks(src) {
      const start = src.indexOf('global-search-tickers');
      if (start < 0) return ['the global-search-tickers ✨ entry is missing'];
      const next = src.indexOf("{ id: '", start);
      const entry = src.slice(start, next > start ? next : undefined);
      const lq = entry.indexOf('label:');
      const aq = entry.indexOf(', addedAt', lq);
      const card = lq < 0 ? entry : entry.slice(lq, aq > lq ? aq : undefined);
      const errs = [];
      if (!/same field/i.test(card))
        errs.push('the card must say the tickers are in the SAME field');
      if (!/no mode switch/i.test(card))
        errs.push('the card must say there is no mode switch');
      if (!/UNLESS one of your pages is named that word/.test(card))
        errs.push('the card must state the pin block — an exact symbol loses to a page named that word');
      if (!/never wait|instantly/i.test(card))
        errs.push('the card must say the pages never wait on the ticker lookup');
      if (/\bbounce\b/i.test(card))
        errs.push('house rule: the word is "reversal", never "bounce"');
      for (const [re, why] of [
        [/\bbacktest(ed)?\b/i, 'the card claims it was backtested'],
        [/\bwin rate\b/i, 'the card quotes a win rate'],
        [/\bhigh[- ]probability\b/i, 'the card claims a probability'],
        [/\bedge\b(?![^.]{0,30}(is claimed|no edge))/i, 'the card claims an edge'],
      ]) {
        if (re.test(card)) errs.push(why);
      }
      if (!/no edge is claimed and nothing here is measured/i.test(card))
        errs.push('the card must say out loud that no edge is claimed and nothing is measured');
      return errs;
    },
  },
  {
    name: 'the IPO tab says nothing is measured (2026-09-20)',
    file: 'src/components/IpoUpcomingStrip.tsx',
    // Ajay 2026-09-19: "IPO of hot sector theme of stocks and then add them
    // as a tab in Chart maps." The only cited thing on the tab is the ≤2y
    // recency bound (TLSW Ch.11 via sepa/ipo_age); everything else is a list.
    // The served note and the strip's own sentence are what stop a newest-
    // first list of listings from reading as a ranking.
    checks: (src) => {
      const errs = [];
      if (!/Nothing here is measured and nothing here is a signal\./.test(src)) {
        errs.push('IpoUpcomingStrip must say "Nothing here is measured and nothing here is a signal."');
      }
      const py = read('../backend/chart_maps/ipo.py');
      // The served NOTE is built from adjacent string literals, so the sentence
      // may straddle a quote + newline in the source; match it piecewise.
      if (!/Nothing here is ["\s]*measured or claims an edge\./.test(py)) {
        errs.push('backend/chart_maps/ipo.py must serve the note "Nothing here is measured or claims an edge."');
      }
      if (!/sepa\/ipo_age/.test(py) || !/TLSW Ch\.11/.test(py)) {
        errs.push('backend/chart_maps/ipo.py must cite where the ≤2y bound lives: sepa/ipo_age and TLSW Ch.11');
      }
      // Ajay 2026-09-20, asked whether the uncorroborated rows should go:
      // "Yes for #1 and #2 and #3". A DROP has to be visible or the tab just
      // gets quietly shorter — the served note says it and the strip counts it.
      if (!/Listings the calendar does not carry are ["\s]*dropped/.test(py)) {
        errs.push('ipo.py NOTE must say the uncorroborated listings are dropped (2026-09-20, his "Yes #3")');
      }
      const tabLib = read('src/lib/ipoTab.ts');
      if (!/dropped_uncorroborated/.test(tabLib)) {
        errs.push('ipoTab.ts must carry counts.dropped_uncorroborated — a silent drop is a shorter list with no reason');
      }
      const board = read('../backend/chart_maps/board.py');
      if (!/IPO\.NOTE/.test(board)) {
        errs.push('board.py::ipo_tiles must serve IPO.NOTE — the note is the tab\'s honesty line');
      }
      const tabs = parseCmTabs(read('src/lib/chartMaps.ts'));
      if (!tabs || !tabs.includes('ipo')) errs.push("CM_TABS must carry 'ipo'");
      const page = read('src/pages/ChartMaps.tsx');
      if (!/tab === 'ipo' && <IpoUpcomingStrip/.test(page)) {
        errs.push('ChartMaps.tsx must pin <IpoUpcomingStrip> above the grid on the ipo tab');
      }
      return errs;
    },
  },
  {
    name: 'the IPO drill-in is a fact sheet, not a read (2026-09-20)',
    file: 'src/components/IpoUpcomingModal.tsx',
    // Ajay 2026-09-20: "gather similar info about these … make them clicable
    // the onesin IPO tab that are future". A fact sheet from the registration
    // filing: served note, no parsed number, no chip, no verdict, no model.
    checks: (src) => {
      const errs = [];
      const strip = read('src/components/IpoUpcomingStrip.tsx');
      if (!/data-testid=\{`ipo-upcoming-open-/.test(strip)) errs.push('the strip symbols must be the open buttons');
      if (!/lazyWithReload\(/.test(strip) || !/IpoUpcomingModal/.test(strip)) errs.push('the modal must be lazy-loaded from the strip');
      if (/\blazy\(/.test(strip)) errs.push('the strip must not use a raw lazy() — lazyWithReload survives a redeploy');
      if (/Nothing here is measured/.test(src)) errs.push('the not-measured note is SERVED — never typed into the modal');
      if (!/\.note\b/.test(src)) errs.push('the modal must render the served note');
      const py = read('../backend/chart_maps/ipo_upcoming.py');
      if (!/Nothing here is ["\s]*measured, nothing here is a signal/.test(py)) errs.push('the backend must serve the not-measured note');
      if (!/dates move ["\s]*and deals are withdrawn/.test(py)) errs.push('the note must say an expected deal is a plan');
      for (const bad of ['className="chip', 'READY', 'WATCH', 'BLOCKED', 'verdict', 'score', 'signal_', 'Number(', 'parseFloat(', 'toFixed(']) {
        if (src.includes(bad)) errs.push(`the modal must not carry "${bad}" — a fact sheet has no read and parses no number`);
      }
      const lib = read('src/lib/ipoTab.ts');
      if (!/IPO_HEADLINE_EPOCH_S_MAX/.test(lib)) errs.push('ipoTab.ts must name the epoch bound');
      const libCode = lib.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
      if (/\b1e1[12]\b/.test(libCode)) errs.push('the epoch bound must be named, not a bare 1e11/1e12');
      if (!/revenue_units_line/.test(src) || !/net_loss_units_line/.test(src)) errs.push('each quoted table carries its own units line');
      const css = read('src/styles.css');
      for (const f of ['src/components/IpoUpcomingModal.tsx', 'src/components/IpoUpcomingStrip.tsx']) {
        const t = read(f);
        const used = new Set();
        for (const m of t.matchAll(/className=\{?["'`]([^"'`]+)/g)) {
          for (const c of m[1].split(/[\s${}]+/)) if (/^ipo-(?:drill|up)-[a-z0-9-]+$|^ipo-drill$/.test(c)) used.add(c);
        }
        for (const c of [...used].sort()) {
          if (!new RegExp(`\\.${c}(?![\\w-])`).test(css)) errs.push(`styles.css has no rule for .${c} (${f})`);
        }
      }
      for (const f of ['../backend/chart_maps/ipo.py', '../backend/chart_maps/board.py']) {
        if (/ipo_upcoming/.test(read(f))) errs.push(`${f} must never touch the drill-in — it is on-demand, never on the board build`);
      }
      if (!/from sepa\.insider import _edgar_get/.test(py)) errs.push('the drill-in must reuse the one EDGAR getter (UA + pacing)');
      if (!/"html\.parser"/.test(py)) errs.push('the drill-in must parse with html.parser (lxml is not in the image)');
      const pyCode = py.split('\n').filter((l) => !/^\s*#/.test(l)).join('\n');
      for (const bad of ['requests.get(', 'httpx.', 'import lxml', '"lxml"', "'lxml'", 'ollama', 'anthropic', 'two_sided', 'import llm', 'from llm']) {
        if (pyCode.includes(bad)) errs.push(`ipo_upcoming.py must not carry "${bad}"`);
      }
      if (!/id: 'ipo-upcoming-drill-2026-09-20'/.test(read('src/lib/newFeatures.ts'))) errs.push('the drill-in needs its ✨ entry');
      return errs;
    },
  },
  {
    name: 'the \u{1F3DB}\uFE0F POTUS kind declares itself everywhere, and ships ON (2026-09-20)',
    file: 'src/pages/Notifications.tsx',
    // Ajay 2026-09-20: "Anytime POTUS does new investments show me those."
    // Then, the same day: "Default on for any change of todays features Bondes
    // or Potus or explosive growth or Earnings I wanna see all of them." — so
    // the kind that shipped registered-and-silent that morning ships ON. What
    // moved is which KINDS reach him, NOT what the kind requires to fire: the
    // headline gate (a named agency AND a stated size in the same headline) is
    // untouched, and the page still has to call the watch a HEURISTIC.
    checks: (src) => {
      const errs = [];
      const m = src.match(/key: 'potus_investment'[\s\S]*?\},\n/);
      if (!m) return ['potus_investment must stay listed on the Notifications page'];
      const d = m[0];
      if (!/ON BY DEFAULT/.test(d)) errs.push('the Notifications entry must say it is ON BY DEFAULT since 2026-09-20');
      if (/OFF BY DEFAULT/.test(d)) errs.push('the Notifications entry still says OFF BY DEFAULT \u2014 he flipped it ON 2026-09-20');
      if (!/Default on for any change of todays features/.test(d)) {
        errs.push('the Notifications entry must carry his 2026-09-20 sentence verbatim \u2014 it is the reason the kind is on');
      }
      if (!/HEURISTIC/.test(d)) errs.push('the Notifications entry must call the watch a HEURISTIC');
      const kinds = read('src/lib/alertKinds.ts');
      if (!/potus_investment/.test(kinds)) errs.push('alertKinds.ts must register potus_investment');
      const prefs = read('src/hooks/useNotificationPrefs.ts');
      if (!/potus_investment\?: boolean/.test(prefs)) {
        errs.push('NotificationPrefs must carry potus_investment or the toggle cannot be stored');
      }
      const subs = read('../backend/push/subs.py');
      const dm = subs.match(/["']potus_investment["']\s*:\s*(True|False)/);
      if (!dm) errs.push('push/subs.py default_prefs must list potus_investment');
      else if (dm[1] !== 'True') errs.push('potus_investment must ship ON (True) in push/subs.py default_prefs — his 2026-09-20 "Yes for #1"');
      if (!keepSet(subs).includes('potus_investment')) {
        errs.push('potus_investment must sit in push/subs.OWNER_KEEP_SET — prefs_for() re-reads owner_prefs() on every re-registration and would mute it again');
      }
      const board = read('src/components/PotusBoard.tsx');
      if (!/editorial order, not a ranking/.test(board)) {
        errs.push('PotusBoard.tsx must state that the list order is editorial, not a ranking');
      }
      if (!/unnamed/.test(board)) {
        errs.push('PotusBoard.tsx must keep the "unnamed — needs a ticker" rows — dropping them hides the stories the ask is about');
      }
      return errs;
    },
  },
  {
    name: 'the Bonde tab is a PICK LIST of HIS cited static criteria, and the retracted quotes never come back (2026-09-20)',
    file: 'src/components/BondeBoard.tsx',
    // Ajay 2026-09-20: "I need bonde for stock picks rather than deciding to
    // enter … show me other things like EPS, Sales and other things … He
    // looks at earnings surprise too" — then "momentum does not need to be a
    // criteria for his pics … I am looking fro static info" — then "check it
    // out. and validate it". The validation (four Stockbee posts read
    // verbatim) found the sales module quoting sentences he never wrote.
    // Two sweep rules mirror backend/tests/test_sepa_contracts.py:
    //   R1 — the retracted first-person phrases are never quoted, not even
    //        to say they were wrong (they are built from fragments here so
    //        this file cannot trip its own sweep);
    //   R2 — the token 39 and a failed-word never share one source line.
    checks: (src) => {
      const errs = [];
      const FILES = [
        'src/components/BondeBoard.tsx', 'src/components/BondePickChips.tsx',
        'src/components/BondeCriteriaLegend.tsx', 'src/lib/bondePicks.ts',
        'src/lib/chartMaps.ts', 'src/lib/newFeatures.ts',
        'src/components/SalesPanel.tsx', 'src/components/SepaCandidateCard.tsx',
      ];
      const retracted = [
        ['you can use ', '25% plus'], ['I take ', '5%'], ['25% ', 'preferred'],
        ['his ', 'preferred'], ['revenue growth that ', 'investors focus on'],
        ['Sales ', 'Acceleration'],
      ].map((f) => f.join(''));
      const failedWord = /\b(failed|FAILED|forgery|not verified)\b/;
      // R2 is scoped to the Bonde entry inside newFeatures.ts — the older
      // highlights are history (a Keltner claim that FAILED next to a −0.39pp
      // lift is not about his figure) and are never rewritten after the fact.
      const nfAll = read('src/lib/newFeatures.ts');
      const nfEntry = ['bonde-pick-list-2026-09-20', 'bonde-video-cites-2026-09-20']
        .map((id) => (new RegExp(`\\{ id: '${id}'[\\s\\S]*?route: '\\/chart-maps\\?tab=bonde' \\}`).exec(nfAll) || [''])[0])
        .join('\n');
      for (const f of FILES) {
        const t = read(f);
        for (const ph of retracted) {
          if (t.includes(ph)) errs.push(`${f} quotes a retracted phrase: "${ph}"`);
        }
        const scope = f === 'src/lib/newFeatures.ts' ? nfEntry : t;
        scope.split('\n').forEach((line, i) => {
          if (/\b39\b/.test(line) && failedWord.test(line)) {
            errs.push(`${f}${scope === t ? `:${i + 1}` : ' (✨ entry)'} puts the token 39 on a line with a failed-word — his 2025 figure is HIS`);
          }
        });
      }
      // The legend renders ONCE for the tab (Rule #5), never per row.
      const legendUses = (src.match(/<BondeCriteriaLegend\b/g) || []).length;
      if (legendUses !== 1) errs.push(`the criteria legend must render exactly once on the tab — found ${legendUses}`);
      if (!/<BondePickChips\b/.test(src)) errs.push('every row must carry the pick chips');
      // A list of facts with cites, never a rank: no count of ticks, no
      // momentum leg, anywhere in the pick surface.
      for (const f of ['src/components/BondeBoard.tsx', 'src/components/BondePickChips.tsx',
                       'src/components/BondeCriteriaLegend.tsx', 'src/lib/bondePicks.ts']) {
        const t = read(f);
        if (/\b(n_fail|n_unknown|pickCounts|legsPassed|passCount)\b/.test(t)) {
          errs.push(`${f} derives a count from the legs — the pick line is facts with cites, not a rank`);
        }
        if (/\/14\b/.test(t) || /\/18\b/.test(t)) errs.push(`${f} prints an x/N tally of the legs`);
      }
      const lib = read('src/lib/bondePicks.ts');
      if (/\b(today_pct|rs_rank|rel_[a-z]|persistence|momentum)\b/.test(lib)) {
        errs.push('bondePicks.ts carries a momentum leg — his correction: static info only');
      }
      // WHY_TEXT keys == the backend's WHY_CODES literal — ONE vocabulary.
      const py = read('../backend/sepa/bonde_picks.py');
      const m = /WHY_CODES = frozenset\(\{([\s\S]*?)\}\)/.exec(py);
      if (!m) errs.push('backend/sepa/bonde_picks.py must define WHY_CODES as a frozenset literal');
      else {
        const be = new Set([...m[1].matchAll(/"([a-z0-9_]+)"/g)].map((x) => x[1]));
        const fe = new Set([...(/WHY_TEXT: Record<WhyCode, string> = \{([\s\S]*?)\n\};/.exec(lib) || ['', ''])[1]
          .matchAll(/^\s{2}([a-z0-9_]+):/gm)].map((x) => x[1]));
        for (const k of be) if (!fe.has(k)) errs.push(`WHY_TEXT lacks the backend why-code "${k}"`);
        for (const k of fe) if (!be.has(k)) errs.push(`WHY_TEXT carries "${k}", which the backend never serves`);
        if (be.size === 0) errs.push('WHY_CODES parsed as empty');
      }
      // Every bd-pick-* class the two new components use has a rule that ships.
      const css = read('src/styles.css');
      for (const f of ['src/components/BondePickChips.tsx', 'src/components/BondeCriteriaLegend.tsx']) {
        const t = read(f);
        const used = new Set();
        for (const mm of t.matchAll(/(?:className=\{?["'`])([^"'`]+)/g)) {
          for (const c of mm[1].split(/[\s${}]+/)) if (/^bd-[a-z0-9-]+$/.test(c)) used.add(c);
        }
        for (const c of [...used].sort()) {
          if (!new RegExp(`\\.${c}(?![\\w-])`).test(css)) errs.push(`styles.css has no rule for .${c} (${f})`);
        }
      }
      // The tab blurb says what the tab became, and whose numbers are whose.
      const cm = read('src/lib/chartMaps.ts');
      const meta = /bonde:\s*\{[\s\S]*?blurb:\s*'([\s\S]*?)',\n\s*\},/.exec(cm);
      const b = meta ? meta[1].replace(/\\u([0-9a-fA-F]{4})/g, (_, h) => String.fromCharCode(parseInt(h, 16))) : '';
      if (!/SINCE 2026-09-20 THIS TAB IS A PICK LIST of his STATIC criteria/.test(b)) errs.push('the Bonde blurb must say the tab is a pick list of his static criteria');
      if (!/entries are yours \(S&D, momentum\)/.test(b)) errs.push('the blurb must say entries are his (S&D, momentum)');
      if (!/the 25% mid-tier and the character clause[\s\S]*are THIS APP’S, mis-attributed to him until 2026-09-20/.test(b)) {
        errs.push('the blurb must state that the 25% mid-tier and the character clause are this app’s, not his');
      }
      if (!/a rule change is Ajay’s call/.test(b)) errs.push('the blurb must say the gate is unchanged because a rule change is his call');
      if (!/Nothing on the pick line is measured or a signal/.test(b)) errs.push('the blurb must say the pick line is not measured and not a signal');
      // The ✨ entry rides with the feature and carries his words.
      const nf = read('src/lib/newFeatures.ts');
      const e = /id: 'bonde-pick-list-2026-09-20'[\s\S]*?addedAt: '2026-09-20', route: '\/chart-maps\?tab=bonde' \}/.exec(nf);
      if (!e) errs.push('newFeatures.ts needs the bonde-pick-list-2026-09-20 entry routed to the Bonde tab');
      else {
        const d = e[0];
        for (const [re, msg] of [
          [/I need bonde for stock picks rather than deciding to enter/, 'his ask, verbatim'],
          [/I am looking fro static info/, 'his correction, verbatim'],
          [/NO MOMENTUM ON THE PICK LINE/, 'the no-momentum rule'],
          [/It is not measured, it is not a signal/, 'the not-measured line'],
          [/IN WORDING ONLY/, 'the validation fix must be described as wording-only'],
          [/not warmed/, 'the short-interest warm caveat'],
          [/uncorroborated/, 'the listing-date caveat'],
        ]) if (!re.test(d)) errs.push(`the ✨ entry must carry ${msg}`);
      }
      // ── the interview (2026-09-20): cites on tape, four FACT rows ───────
      // Ajay sent the video link after the list shipped; Bonde himself on
      // tape, so every sentence is linked at the second it starts.
      if (!/export type BondeCite\b/.test(lib)) errs.push('bondePicks.ts must export the BondeCite type');
      if (!/cites\?:\s*BondeCite\[\]/.test(lib)) errs.push('BondeCriterion must carry the optional extra cites');
      const legendSrc = read('src/components/BondeCriteriaLegend.tsx');
      if (!/data-testid="bonde-tape-header"/.test(legendSrc)) errs.push('the legend must render the tape header line');
      if (!/bd-pick-cite/.test(legendSrc)) errs.push('the legend must render the extra cites with their own class');
      if (!/TAPE_URL = "https:\/\/www\.youtube\.com\/watch\?v=fjox2hapu98"/.test(py)) {
        errs.push('bonde_picks.py must pin TAPE_URL to the interview');
      }
      const deepLinks = (py.match(/&t=/g) || []).length;
      if (deepLinks !== 1) errs.push(`the &t= deep link must be built in exactly one place — found ${deepLinks}`);
      const v = /id: 'bonde-video-cites-2026-09-20'[\s\S]*?addedAt: '2026-09-20', route: '\/chart-maps\?tab=bonde' \}/.exec(nf);
      if (!v) errs.push('newFeatures.ts needs the bonde-video-cites-2026-09-20 entry routed to the Bonde tab');
      else for (const [re, msg] of [
        [/\[1:07:04\]/, 'the three-sectors timestamp'],
        [/never a tick or a cross/, 'the fact-row rule'],
        [/NOTHING MEASURED/, 'the not-measured line'],
        [/your call/, 'the his-call closer'],
      ]) if (!re.test(v[0])) errs.push(`the interview ✨ entry must carry ${msg}`);
      const whyLine = /no_threshold_in_his_writing:\s*\n?\s*'([^']*)'/.exec(lib);
      if (whyLine && /fund holding/i.test(whyLine[1])) {
        errs.push('the no_threshold_in_his_writing hover is shared by five fact legs — it must not name fund holding');
      }
      for (const f of ['src/lib/bondePicks.ts', 'src/components/BondePickChips.tsx', 'src/components/BondeCriteriaLegend.tsx']) {
        if (/theme[^\n]*['"]none['"]/.test(read(f))) errs.push(`${f} prints a theme of "none" — a miss on the app's map is unmapped, not themeless`);
      }
      return errs;
    },
  },
  {
    name: 'every tab blurb folds to its first sentence (2026-09-20)',
    file: 'src/pages/ChartMaps.tsx',
    // Ajay 2026-09-20, on the Bonde tab's 5,000-character blurb: "Collapse all
    // of this info". The first sentence carries the verdict and stays in view;
    // the rest sits behind the same ▸ fold every study verdict uses. The TEXT
    // in TAB_META is untouched, so every blurb pin above keeps its meaning.
    checks: (src) => {
      const errs = [];
      if (/<p className="cm-blurb">\s*\{tab === 'ict'/.test(src)) errs.push('the blurb is drawn whole again — it must fold');
      if (!/splitBlurb\(TAB_META\[tab\]\.blurb\)/.test(src)) errs.push('the blurb must split through splitBlurb');
      if (!/<StudyNote id=\{`blurb-\$\{tab\}`\}[^>]*headline=\{head\}/.test(src)) errs.push('the blurb must render as a StudyNote fold keyed per tab, headline = the first sentence');
      if (!/export function splitBlurb/.test(read('src/lib/chartMaps.ts'))) errs.push('chartMaps.ts must export splitBlurb');
      const nf = read('src/lib/newFeatures.ts');
      if (!/id: 'blurbs-folded-2026-09-20'/.test(nf)) errs.push('the fold needs its ✨ entry');
      return errs;
    },
  },
  {
    name: 'the Bonde tab carries + Signals and the live basis line (2026-09-20)',
    file: 'src/components/BondeBoard.tsx',
    // Ajay 2026-09-20: "can you improve Bondes page a lil bit more and add
    // trackers and also make his page more live".
    //
    // jsdom loads no stylesheet, so no render test can catch a bd-* rule that
    // never shipped — the class sweep at the bottom is the only guard there is.
    checks: (src) => {
      const errs = [];

      // ── trackers ────────────────────────────────────────────────────────
      if (!/<SignalWatchButton\s+symbol=\{r\.symbol\}/.test(src)) {
        errs.push('every Bonde row must carry the + Signals button — he tracks names off this board');
      }
      if (/<SignalWatchButton[^>]*\bcompact\b/.test(src)) {
        errs.push('the Bonde table must NOT use the compact Signals button — a bare "+" does not read as a control');
      }
      if (!/tracked only/.test(src)) {
        errs.push('the 📡 tracked-only filter must stay on the tab');
      }

      // ── the live leg ────────────────────────────────────────────────────
      if (!/data-testid="bonde-basis"/.test(src)) {
        errs.push('the basis line must stay on the page — a Today column that does not say which session it is on is a different measurement wearing the same header');
      }
      if (!/data-testid="bonde-rescan"/.test(src)) errs.push('the ↻ Live prices button is gone');
      if (!/↻ Live prices/.test(src)) {
        errs.push('the button label must say what it does — this board never scans on the request path');
      }
      if (/↻ Re-scan/.test(src)) {
        errs.push('the Bonde button must not say "Re-scan" — it re-reads the Today column only');
      }
      if (!/rescanBlockedReason/.test(src) || !/rescanQuietReason/.test(src)) {
        errs.push('the disabled / warned reasons must be IMPORTED (the market calendar and the RTH clock own those sentences)');
      }
      if (/RESCAN_COST_SENTENCE/.test(src)) {
        errs.push("Bonde must not import Hottest's cost sentence — that is 7/13 calls over 1,721 names; this board is 2 calls over 260");
      }
      if (!/BONDE_LIVE_COST_SENTENCE/.test(src)) {
        errs.push('the ⓘ must state what one ↻ click costs, from BONDE_LIVE_COST_SENTENCE');
      }
      const lib = read('src/lib/bondeLive.ts');
      if (!/2 Massive snapshot calls/.test(lib)) {
        errs.push('BONDE_LIVE_COST_SENTENCE must name the call count — it is pinned by backend/tests/test_bonde_live.py');
      }
      if (/1,721/.test(lib)) errs.push("bondeLive.ts carries Hottest's name count");

      // ── the held-out footnote and the tri-state ─────────────────────────
      if (!/data-testid="bonde-heldout"/.test(src)) {
        errs.push('the held-out list must stay — a board that refuses to tier a passer has to say which rows');
      }
      if (!/periodMark\(/.test(src)) {
        errs.push('period_ok must render through periodMark — false, null and true are three states, not two');
      }
      if (/r\.period_ok\s*\?/.test(src) || /!r\.period_ok/.test(src)) {
        errs.push('period_ok must never be read as a bool — null means "could not be checked", not "fine"');
      }
      if (!/tierText\(/.test(src)) {
        errs.push('a withheld tier must print an em-dash through tierText, never an empty cell');
      }

      // ── "reversal", never "bounce", on a surface he reads ───────────────
      for (const m of src.matchAll(/>[^<>{}]*\bbounce\b[^<>{}]*</gi)) {
        errs.push(`the Bonde tab must not print "bounce": ${m[0].slice(0, 60)}`);
      }

      // ── every bd-* class the TSX uses must have a rule that SHIPS ───────
      const css = read('src/styles.css');
      const used = new Set();
      for (const m of src.matchAll(/(?:className=\{?["'`])([^"'`]+)/g)) {
        for (const c of m[1].split(/[\s${}]+/)) if (/^bd-[a-z0-9-]+$/.test(c)) used.add(c);
      }
      for (const c of ['bd-today', 'bd-basis', 'bd-tier', 'bd-pair-warn',
                       'bd-unverified', 'bd-heldout', 'bd-heldout-row',
                       'bd-heldout-rows']) used.add(c);
      for (const c of [...used].sort()) {
        if (!new RegExp(`\\.${c}(?![\\w-])`).test(css)) {
          errs.push(`styles.css has no rule for .${c} — the Bonde board would ship unstyled`);
        }
      }
      return errs;
    },
  },
  {
    name: 'the \u{1F4E3} earnings-reaction kind declares itself everywhere, and ships ON (2026-09-20)',
    file: 'src/pages/Notifications.tsx',
    // Ajay 2026-09-20: "Also don't forget to alert me on earnings surprises I
    // think stock witz also has it. I wanna make sure we are catching those in
    // alerts as well." + "Default on for any change of todays features ... or
    // Earnings I wanna see all of them." A kind missing from ANY of the five
    // registries below sends to zero devices and says nothing while it does it.
    checks: (src) => {
      const errs = [];
      const m = src.match(/key: 'earnings_reaction'[\s\S]*?\},\n/);
      if (!m) return ['earnings_reaction must be listed on the Notifications page — a kind the page cannot show cannot be muted'];
      const d = m[0];
      if (!/ON BY DEFAULT/.test(d)) errs.push('the Notifications entry must say it is ON BY DEFAULT');
      if (!/alert me on earnings surprises/.test(d)) errs.push('the Notifications entry must carry the ask verbatim');
      if (!/NOT MEASURED/.test(d)) errs.push('the Notifications entry must say NOT MEASURED — beat + institutional buying has no forward record here');
      if (!/A miss never pushes/.test(d)) errs.push('the Notifications entry must say a miss never pushes — the kind is one-sided by design');
      if (!/Not a recommendation/i.test(d)) errs.push('the Notifications entry must say it is not a recommendation');
      const kinds = read('src/lib/alertKinds.ts');
      if (!/earnings_reaction/.test(kinds)) errs.push('alertKinds.ts must register earnings_reaction or the bell renders a raw id');
      const prefs = read('src/hooks/useNotificationPrefs.ts');
      if (!/earnings_reaction\?: boolean/.test(prefs)) errs.push('NotificationPrefs must carry earnings_reaction or the toggle cannot be stored');
      const subs = read('../backend/push/subs.py');
      const dm = subs.match(/["']earnings_reaction["']\s*:\s*(True|False)/);
      if (!dm) errs.push('push/subs.py default_prefs must list earnings_reaction');
      else if (dm[1] !== 'True') errs.push('earnings_reaction must ship ON (True) in push/subs.py default_prefs');
      if (!keepSet(subs).includes('earnings_reaction')) {
        errs.push('earnings_reaction must sit in push/subs.OWNER_KEEP_SET — otherwise a re-registration mutes it');
      }
      const gate = read('../backend/market_hours/gate.py');
      const market = pyFrozenSet(gate, 'MARKET_ALERT_KINDS') || [];
      if (!market.includes('earnings_reaction')) {
        errs.push('market_hours/gate.py must treat earnings_reaction as a MARKET kind — it reads a closed reaction bar');
      }
      if ((pyFrozenSet(gate, 'PERSONAL_KINDS') || []).includes('earnings_reaction')) {
        errs.push('earnings_reaction must NOT be a PERSONAL kind — a closed day has no reaction bar');
      }
      const cron = cronCommands(read('../backend/crontab'))
        .filter((l) => /chart_maps\.earnings_alerts/.test(l));
      if (cron.length !== 2) errs.push(`backend/crontab must run chart_maps.earnings_alerts exactly twice (08:25 + 17:35 ET) — found ${cron.length}`);
      for (const l of cron) {
        if (!/market_hours\.gate/.test(l)) errs.push(`an earnings_alerts cron line bypasses market_hours.gate: ${l.trim().slice(0, 70)}`);
      }
      // The owner's address is a backend fact. It has leaked into the bundle
      // before; every kind that ships ON for him gets re-checked here.
      const scanEmail = (dir) => {
        for (const name of readdirSync(join(FRONTEND_ROOT, dir), { withFileTypes: true })) {
          const rel = `${dir}/${name.name}`;
          if (name.isDirectory()) scanEmail(rel);
          else if (/\.(ts|tsx|js|jsx)$/.test(name.name) && /ajaykandakatla@/.test(read(rel))) {
            errs.push(`${rel} carries the owner's email — it must never reach the JS bundle`);
          }
        }
      };
      scanEmail('src');
      return errs;
    },
  },
  {
    name: 'the ✨ board_arrival kind declares itself everywhere, and ships ON (2026-09-20)',
    file: 'src/pages/Notifications.tsx',
    // Ajay 2026-09-20: "Default on for any change of todays features Bondes or
    // Potus or explosive growth or Earnings I wanna see all of them."
    //
    // The honesty this contract exists for: an ARRIVAL is a list event. 📈
    // Bonde's own rule measured INVERTED (-3.11pp vs placebo) and the 🚀
    // 100/100 screen has never been measured forward — the page has to say
    // both, beside a toggle that is on.
    checks: (src) => {
      const errs = [];
      const m = src.match(/key: 'board_arrival'[\s\S]*?\},\n/);
      if (!m) return ['board_arrival must be listed on the Notifications page'];
      const d = m[0];
      if (!/ON BY DEFAULT/.test(d)) errs.push('the Notifications entry must say it is ON BY DEFAULT');
      if (!/Default on for any change of todays features/.test(d)) {
        errs.push('the Notifications entry must carry his 2026-09-20 sentence verbatim');
      }
      if (!/one push per name per board/i.test(d)) errs.push('the entry must say one push per name per board');
      if (!/leaves a board and comes back is not rung again/i.test(d)) {
        errs.push('the entry must say a name that leaves and returns is NOT rung again — the claim never expires (his call, §7.11)');
      }
      if (!/never the first cohort/i.test(d)) errs.push('the entry must say the first pass records a baseline and pushes nothing');
      if (!/arrival on a list, not an entry/i.test(d)) errs.push('the entry must say an arrival is not an entry');
      // Notifications.tsx spells non-ASCII as \uXXXX escapes, so the minus sign
      // reaches this check as the six characters `\u2212`, never as −.
      if (!/INVERTED/.test(d) || !/(?:\\u2212|[−-])\s?3\.11\s*pp/.test(d)) {
        errs.push("the entry must carry Bonde's measured INVERTED record (-3.11pp) — the board's own number rides with its push");
      }
      if (!/100\/100 screen[\s\S]{0,60}?never been measured forward/.test(d)) {
        errs.push('the entry must say the 100/100 growth screen has never been measured forward');
      }
      if (!/17:42/.test(d) || !/08:08/.test(d)) errs.push('the entry must name both passes: 17:42 ET (Bonde) and 08:08 ET (growth)');
      if (!/Not a recommendation/i.test(d)) errs.push('the entry must say it is not a recommendation');
      const kinds = read('src/lib/alertKinds.ts');
      if (!/board_arrival/.test(kinds)) errs.push('alertKinds.ts must register board_arrival');
      const prefs = read('src/hooks/useNotificationPrefs.ts');
      if (!/board_arrival\?: boolean/.test(prefs)) errs.push('NotificationPrefs must carry board_arrival');
      const subs = read('../backend/push/subs.py');
      const dm = subs.match(/["']board_arrival["']\s*:\s*(True|False)/);
      if (!dm) errs.push('push/subs.py default_prefs must list board_arrival');
      else if (dm[1] !== 'True') errs.push('board_arrival must ship ON (True) in push/subs.py default_prefs');
      if (!keepSet(subs).includes('board_arrival')) {
        errs.push('board_arrival must sit in push/subs.OWNER_KEEP_SET');
      }
      const gate = read('../backend/market_hours/gate.py');
      if (!(pyFrozenSet(gate, 'MARKET_ALERT_KINDS') || []).includes('board_arrival')) {
        errs.push('market_hours/gate.py must treat board_arrival as a MARKET kind — both boards are built from closed bars');
      }
      if ((pyFrozenSet(gate, 'PERSONAL_KINDS') || []).includes('board_arrival')) {
        errs.push('board_arrival must NOT be a PERSONAL kind — a board built on Sunday rings the next TRADING morning');
      }
      const cron = cronCommands(read('../backend/crontab'))
        .filter((l) => /sepa\.board_arrival/.test(l));
      if (cron.length !== 2) errs.push(`backend/crontab must run sepa.board_arrival exactly twice (bonde 17:42, growth 08:08) — found ${cron.length}`);
      for (const b of ['bonde', 'growth']) {
        if (!cron.some((l) => new RegExp(`sepa\\.board_arrival\\s+${b}\\b`).test(l))) {
          errs.push(`backend/crontab has no sepa.board_arrival pass for the ${b} board`);
        }
      }
      for (const l of cron) {
        if (!/market_hours\.gate/.test(l)) errs.push(`a board_arrival cron line bypasses market_hours.gate: ${l.trim().slice(0, 70)}`);
      }
      return errs;
    },
  },
  {
    name: 'retired kinds gone from every toggle and cron; flashcards deleted (2026-09-20)',
    file: 'src/pages/Notifications.tsx',
    // Ajay 2026-09-20: "Remove volleyball and learning of stocks I do dont
    // wanna see them they are spamming too much."
    //
    // Removed from where it FIRES and where it is OFFERED — not from where it
    // is READ. The labels stay in alertKinds.ts on purpose: ~1,900 flashcard
    // and volleyball rows sit in push_history under a 90-day TTL, and dropping
    // the labels would render them in the bell as raw ids.
    checks: (src) => {
      const errs = [];
      const retired = ['minervini_flashcards', 'vb_workout', 'vb_supplement', 'vb_education'];
      const prefs = read('src/hooks/useNotificationPrefs.ts');
      const kinds = read('src/lib/alertKinds.ts');
      for (const k of retired) {
        if (new RegExp(`key:\\s*'${k}'`).test(src)) errs.push(`Notifications.tsx still offers a toggle for ${k} — he asked for it gone`);
        if (new RegExp(`${k}\\?:\\s*boolean`).test(prefs)) errs.push(`NotificationPrefs still declares ${k}`);
        if (!new RegExp(`${k}`).test(kinds)) {
          errs.push(`alertKinds.ts dropped the ${k} label — the push_history rows still on the 90-day TTL would render a raw id`);
        }
      }
      for (const l of cronCommands(read('../backend/crontab'))) {
        if (/\b(flashcards|volleyball)\b/.test(l)) errs.push(`backend/crontab still RUNS a retired job: ${l.trim().slice(0, 70)}`);
      }
      // Ajay 2026-09-20, second ask: "Delete Flashcards please". The feature
      // left the tree — assert the ABSENCE, so nothing quietly reintroduces it.
      for (const gone of ['../backend/flashcards/flashcards.py', '../backend/flashcards/chart_quiz.py',
        '../backend/flashcards/api.py', '../backend/flashcards/__init__.py',
        'src/pages/Learn.tsx', 'src/pages/ChartSchool.tsx']) {
        if (exists(gone)) errs.push(`${gone} is back — the flashcards feature was DELETED 2026-09-20`);
      }
      const app = read('src/App.tsx');
      for (const dead of ['path="/learn"', 'path="/chart-school"']) {
        if (app.includes(dead)) errs.push(`App.tsx still routes ${dead} — the page is deleted`);
      }
      // `pages/LearningPath` legitimately starts with `pages/Learn` — anchor on
      // the closing quote so the study-plan import is not a false positive.
      for (const dead of [/pages\/Learn['"]/, /pages\/ChartSchool['"]/]) {
        if (dead.test(app)) errs.push(`App.tsx still imports ${dead} — the page is deleted`);
      }
      if (!app.includes('path="/learning"')) errs.push('App.tsx dropped /learning — Learning Path was NOT part of the delete');
      const mainPy = read('../backend/main.py');
      if (/from flashcards import|flashcards_router/.test(mainPy)) errs.push('main.py still includes the deleted flashcards router');
      if (!/from volleyball import router as volleyball_router/.test(mainPy)) errs.push('main.py dropped the volleyball router — volleyball stays, dark');
      const nav = read('src/lib/navSearch.ts');
      if (/'chart-school'\s*:/.test(nav)) errs.push("navSearch.ts still carries a 'chart-school' synonym row — the route is gone");
      if (!/feature deleted 2026-09-20/.test(kinds)) errs.push('alertKinds.ts must say why the minervini_flashcards label outlives the feature');

      const subs = read('../backend/push/subs.py');
      if (!/RETIRED_2026_09_20/.test(subs)) errs.push('push/subs.py must declare RETIRED_2026_09_20');
      if (!/DISABLED_ALERT_KINDS[\s\S]{0,400}?RETIRED_2026_09_20/.test(subs)) {
        errs.push('DISABLED_ALERT_KINDS must fold in RETIRED_2026_09_20 — the crontab is bind-mounted from the main tree and keeps firing until it is re-read');
      }
      for (const k of retired) {
        if (!keepSet(subs).every((x) => x !== k)) errs.push(`${k} is in OWNER_KEEP_SET and retired at the same time`);
      }
      return errs;
    },
  },
  {
    name: 'every alert surface renders per-ticker anchors (2026-09-20)',
    file: 'src/pages/Alerts.tsx',
    // Ajay 2026-09-20: "I need the stock tickers to be clickables in alerts
    // individually if there are multiple in one alert by command click."
    //
    // ⌘-click only works on a real <a href>, and an <a> inside an <a> is
    // hoisted out by the browser — so the card-wide <Link> on the panel and
    // the bell had to become a <div> with the link on the TITLE. One shared
    // component renders the chips on all three surfaces.
    checks: (src) => {
      const errs = [];
      const surfaces = [
        ['src/pages/Alerts.tsx', 'alert-tk'],
        ['src/components/PushHistoryPanel.tsx', 'ph-tk'],
        ['src/components/NotificationBell.tsx', 'bell-tk'],
      ];
      for (const [rel, prefix] of surfaces) {
        const f = rel === 'src/pages/Alerts.tsx' ? src : read(rel);
        if (!/import \{ TickerChips \}/.test(f)) errs.push(`${rel} must render names through the shared TickerChips`);
        if (!new RegExp(`testIdPrefix="${prefix}"`).test(f)) errs.push(`${rel} must pass testIdPrefix="${prefix}" so the chips are addressable in a test`);
      }
      for (const rel of ['src/components/PushHistoryPanel.tsx', 'src/components/NotificationBell.tsx']) {
        const f = read(rel);
        if (/<Link\s+key=\{r\._id\}/.test(f)) {
          errs.push(`${rel} still wraps the whole row in a <Link> — the ticker anchors inside it would be hoisted out and ⌘-click would open the card's page instead`);
        }
      }
      const chips = read('src/components/TickerChips.tsx');
      if (!/TickerLink/.test(chips)) errs.push('TickerChips must render TickerLink — a <span> with an onClick cannot be ⌘-clicked');
      // Comments stripped first: the component's own header explains the
      // nested-anchor trap it exists to avoid, and naming `<Link>` there is
      // the documentation, not the defect.
      const chipsCode = chips.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '');
      if (/<Link[\s>/]/.test(chipsCode)) errs.push('TickerChips must not use react-router <Link> — TickerLink already emits the real href');
      const recent = read('../backend/push/recent.py');
      if (!/DIGEST_KINDS/.test(recent) || !/derive_tickers/.test(recent)) {
        errs.push('push/recent.py must derive tickers for the digest kinds — the rows already in push_history carry no list');
      }
      const hist = read('../backend/push/history.py');
      if (!/tickers/.test(hist)) errs.push('push/history.py::record must store the payload tickers, or every NEW row needs deriving too');
      return errs;
    },
  },
  {
    name: 'HottestSectors renders periodMark (2026-09-20)',
    file: 'src/components/HottestSectors.tsx',
    // Ajay 2026-09-20, on the ⚠ pair mark reaching 🔥 Hottest too: "#6 what
    // ever". Same three states as the Bonde tab: false = the year-over-year
    // pair is not four fiscal quarters apart, null = no period keys on file
    // and it could not be checked, true = checked. `!period_ok` would collapse
    // null into false and claim a check that never ran.
    checks: (src) => {
      const errs = [];
      if (!/periodMark\(/.test(src)) errs.push('HottestSectors must render period_ok through periodMark — three states, not two');
      if (!/from '\.\.\/lib\/bondeLive'/.test(src)) errs.push('periodMark must be IMPORTED from lib/bondeLive — one mark, one wording, two boards');
      if (/!r\.period_ok/.test(src) || /r\.period_ok\s*\?/.test(src)) {
        errs.push('period_ok must never be read as a bool on Hottest — null means "could not be checked", not "fine"');
      }
      if (!/data-testid=\{`hs-pair-\$\{/.test(src)) errs.push('each marked name row needs a hs-pair-<SYM> testid');
      const lib = read('src/lib/bondeLive.ts');
      if (!/PAIR_WARN_TITLE/.test(lib)) errs.push('bondeLive.ts must export PAIR_WARN_TITLE — the mark explains itself on hover');
      return errs;
    },
  },
  {
    name: '🔥 Hottest carries the ☀️ Pre-market scan (2026-09-21)',
    file: 'src/components/HottestSectors.tsx',
    // Ajay 2026-09-21: "In the hot sector table can I get a pre market scan
    // please". The button is enabled by the SERVED `pre.open` — the backend's
    // clock — never this browser's: a browser clock would hand a laptop in
    // London a board that thinks the New York pre-market is open. The served
    // sort is what the "ranked on" line and the header mark print; the FE
    // never composes a clock string, never coerces a number, never sorts.
    checks: (tsx) => {
      const errs = [];
      // The body of `export function <name>(...) { ... }` by brace count.
      const bodyOf = (name) => {
        const i = tsx.indexOf(`export function ${name}(`);
        if (i < 0) return null;
        // The body brace is the one that opens a line — a `{ a: b }` return type sits inline.
        const open = tsx.indexOf('{\n', tsx.indexOf(')', i));
        let depth = 0;
        for (let j = open; j < tsx.length; j++) {
          if (tsx[j] === '{') depth++;
          else if (tsx[j] === '}' && --depth === 0) return tsx.slice(open, j + 1);
        }
        return null;
      };
      if (!/data-testid="hs-premarket"/.test(tsx)) errs.push('the ☀️ button needs data-testid="hs-premarket"');
      if (!/data-testid="hs-premarket"\s+disabled=\{loading \|\| !preState\.enabled\}/.test(tsx)) {
        errs.push('the ☀️ button must be disabled by preState.enabled — the served pre.open, nothing else');
      }
      for (const fn of ['premarketState', 'showPreCol', 'visibleCols', 'preCell', 'shownSortKey']) {
        const body = bodyOf(fn);
        if (!body) { errs.push(`export function ${fn} is missing`); continue; }
        if (/new Date\(|Date\.now\(/.test(body)) errs.push(`${fn} must not read the browser clock — the server says whether pre-market is open`);
      }
      const shown = bodyOf('shownSortKey') || '';
      if (/\bset[A-Z]\w*\(/.test(shown)) errs.push('shownSortKey must be pure — a set* call there is a second fan-out');
      if (!/\bp\?\.open !== true\b|\bpre\?\.open\b|\.open === true/.test(bodyOf('premarketState') || '')) {
        errs.push('premarketState must gate on the served pre.open');
      }
      if (!/PRE_COL\.label/.test(bodyOf('colLabel') || '')) errs.push('colLabel must print PRE_COL.label ("Pre-mkt"), never the raw key');
      const preCol = tsx.slice(tsx.indexOf('export const PRE_COL'), tsx.indexOf('};', tsx.indexOf('export const PRE_COL')));
      if (!/members that printed/.test(preCol)) errs.push('the Pre-mkt column title must say the group cell is the median of the members that printed');
      if (!/shownSort === c\.key/.test(tsx)) errs.push('the header mark must follow the SERVED sort (shownSortKey), not the requested one');
      if (!/ranked on <b>\{colLabel\(shownSort, data\)\}/.test(tsx)) errs.push('the "ranked on" line must print the served sort — under a demotion the rows are on 5 days');
      if (/colLabel\(sort, data\)/.test(tsx)) errs.push('no surface line may print the REQUESTED sort while the rows are ranked on the served one');
      if (!/'&basis=premarket'/.test(tsx)) errs.push('the ☀️ read must add &basis=premarket to the one fetch');
      if (!/sort=\$\{encodeURIComponent\(sort\)\}&dir=\$\{dir\}/.test(tsx)) errs.push('the fetch must still carry sort and dir — the pre-market read is the same server-sorted read');
      if (!tsx.includes("'One click is the same provider read as reloading the page — 7 snapshot calls, '")) {
        errs.push('RESCAN_COST_SENTENCE changed — the ☀️ tooltip quotes it; re-measure the call count before rewording');
      }
      if (/Number\(/.test(tsx)) errs.push('no Number( coercion on the Hottest table — the server serves numbers or null, never strings');
      if (/colSpan=\{10\}/.test(tsx)) errs.push('colSpan must come from colSpanOf(data) — the Pre-mkt column changes the width');
      if (/'0\d:\d\d ET'|"0\d:\d\d ET"/.test(tsx)) errs.push('the FE never composes a clock string — it prints the server\'s "7:42 ET"');
      const lib = read('src/lib/chartMaps.ts');
      const tab = lib.indexOf('\n  hot_sectors: {');
      const bAt = tab < 0 ? -1 : lib.indexOf("blurb: '", tab);
      const blurb = bAt < 0 ? '' : lib.slice(bAt, lib.indexOf('\n', bAt));
      if (!/Pre-market/.test(blurb)) errs.push('the hot_sectors blurb must mention the Pre-market scan');
      if (!/NOT measured/.test(blurb)) errs.push('the hot_sectors blurb must say the pre-market read is NOT measured');
      const css = read('src/styles.css');
      for (const c of ['hs-pre-thin', 'hs-pre-n']) {
        if (!new RegExp(`\\.${c}(?![\\w-])`).test(css)) errs.push(`styles.css has no rule for .${c}`);
      }
      if (!/id: 'hottest-premarket-scan-2026-09-21'/.test(read('src/lib/newFeatures.ts'))) errs.push('the scan needs its ✨ entry');
      const py = read('../backend/rotation/hottest.py');
      const pyCode = py.split('\n').filter((l) => !/^\s*#/.test(l)).join('\n');
      if (!/PRE_PRIVATE_KEYS\s*=\s*\(/.test(pyCode)) errs.push('hottest.py must strip PRE_PRIVATE_KEYS from the wire');
      if (!/def _served\(/.test(pyCode)) errs.push('hottest.py must re-clock a stored read through _served — a 07:20 doc must not leave the button live at 10:05');
      const api = read('../backend/rotation/api.py');
      if (!/basis: str = Query\(/.test(api)) errs.push('GET /rotation/hottest must take basis as a Query param');
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
