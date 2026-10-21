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
  // Anchored at COLUMN 0 (2026-09-21): the definition is the only line that
  // starts with the name. A comment paragraph above it that mentions
  // OWNER_KEEP_SET used to be a valid start for this match, so a prose
  // sentence could have steered which set the contracts read.
  const m = /^OWNER_KEEP_SET[^=]*=\s*frozenset\(\{([\s\S]*?)\}\)/m.exec(subsSrc);
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
      /* 2026-09-23 — THE MECHANISM CHANGED, THE REQUIREMENT DID NOT.
       * These zooms used to be pinned as `daily:2y`-style rows in a 17-entry
       * CHART_VIEWS list. Ajay: "Just simpliyfy this drop down ... at any
       * giving point This has been useless". The picker is now five frames
       * plus a zoom that offers what the chosen frame can answer — the same
       * reach, two controls instead of one flattened list. So the check is
       * REACHABILITY, which is what he actually asked for in the first place,
       * and it is stricter than the old one: it reads the real table. */
      const fw = src.match(/export const FRAME_WINDOWS[^=]*=\s*\{([\s\S]*?)\n\};/);
      if (!fw) {
        errs.push('FRAME_WINDOWS not found — no way to check a zoom is reachable');
      } else {
        const rowFor = (tf) => {
          const m = fw[1].match(new RegExp(`'?${tf}'?:\\s*\\[([^\\]]*)\\]`));
          return m ? [...m[1].matchAll(/'([^']+)'/g)].map((x) => x[1]) : null;
        };
        const dailyZooms = rowFor('daily');
        if (!dailyZooms) errs.push('FRAME_WINDOWS has no daily row');
        else for (const k of ['1w', '2w', '1m', '3m', '6m', '1y', '2y', '3y', '5y', 'all']) {
          if (!dailyZooms.includes(k)) errs.push(`the big-picture frame can no longer reach the ${k} zoom`);
        }
        // Ajay 2026-09-18, THIRD time of asking: "Can you increase the bars on
        // the weekly chart please?" -> 1 week of HOURLY bars. It shipped
        // backend-first and the picker could not express the pair, so it never
        // reached him; then the five-row picker dropped it the same way. This
        // is the check that catches it, whatever the picker looks like.
        const hourly = rowFor('60m');
        if (!hourly) errs.push('FRAME_WINDOWS has no 60m row — the hourly short zooms are unreachable');
        else for (const k of ['1w', '2w']) {
          if (!hourly.includes(k)) {
            errs.push(`the hourly ${k} chart is unreachable from the picker — this is the THIRD time this regressed`);
          }
        }
        // and a frame must never offer a zoom its own bars cannot fill
        for (const k of ['1y', '2y', '5y', 'all']) {
          if (hourly && hourly.includes(k)) errs.push(`60m offers ${k}, which is more bars than the frame has`);
        }
      }
      // the 5-minute frames ARE their window; a zoom there would do nothing,
      // which is exactly how "1 month" + "15 min" came to mean nothing.
      if (!/'5m_today':\s*\[\]/.test(src) || !/'24h':\s*\[\]/.test(src)) {
        errs.push('a 5-minute frame offers a zoom — its window is fixed by definition');
      }
      if (!/windowsForFrame\(tf\)\.length > 1/.test(src)) {
        errs.push('zoomApplies no longer derives from FRAME_WINDOWS — a dead control can come back');
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
      // `DEFAULT_VIEW = 'daily:1y'` was the merged-key spelling of the pair.
      // The pair is what matters and it is unchanged.
      if (!/export const DEFAULT_TF = 'daily';/.test(src)) errs.push("DEFAULT_TF is not 'daily'");
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
      // (The hourly short zooms are pinned above, against FRAME_WINDOWS —
      //  the table that decides reachability since 2026-09-23.)
      /* The CHART_VIEWS mechanism (17 flattened rows, optgroups, `primary`,
       * `viewKeyFor`) was retired on 2026-09-23 when the picker went to five
       * frames plus a per-frame zoom. What those checks PROTECTED still has to
       * hold, so it is re-pinned here against the mechanism that replaced it. */
      {
        const comp = read('src/components/SupportLevels.tsx');
        // FIVE rows, not seventeen. He asked for this twice.
        const tfs = src.match(/export const FALLBACK_TIMEFRAMES[\s\S]*?\n\];/);
        const n = tfs ? [...tfs[0].matchAll(/key:\s*'([^']+)'/g)].length : 0;
        if (!tfs) errs.push('FALLBACK_TIMEFRAMES not found');
        else if (n > 5) errs.push(`the frame picker is back to ${n} rows — he asked twice for fewer`);
        // A retired key must still land somewhere real, and SAY it moved.
        for (const k of ['15m_open', '5m_live']) {
          if (!new RegExp(`'${k}'`).test(src)) errs.push(`the retired frame ${k} no longer resolves — an old link would break`);
        }
        if (!/retiredTo/.test(comp)) errs.push('a retired frame retargets silently — the page must say it moved');
        // The zoom must render from the frame's own allowance, never the
        // whole ladder, or a nonsense pair becomes reachable again.
        if (!/windowsForFrame\(curTf\)\.includes\(w\.key\)/.test(comp)) {
          errs.push('the zoom control no longer filters to what the frame can answer');
        }
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
        // 2026-10-13 (Ajay "yes" to rewording): the 100/100 screen WAS measured
        // on 2026-09-21 (cell G100 of board_growth_measured.json) — the blurb
        // says so, quotes NO number (the board's served MEASURED line does), and
        // never again calls the screen unmeasured.
        if (!/MEASURED 2026-09-21[\s\S]{0,160}?a lean, not a finding/.test(meta[0])) {
          errs.push('the blurb must say the 100/100 screen was MEASURED 2026-09-21 — a lean, not a finding');
        }
        if (/NOTHING HERE IS BACKTESTED|never been measured forward/i.test(meta[0])) {
          errs.push('the blurb must not call the 100/100 screen unmeasured — it was measured 2026-09-21');
        }
        const measuredSentence = /MEASURED 2026-09-21[^.]*\./.exec(meta[0]);
        if (measuredSentence && /\d+(?:\.\d+)?\s?(?:pp|%)|\bCI\b/.test(measuredSentence[0].replace('100/100', ''))) {
          errs.push('the blurb must not retype a measured number — the board serves them');
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
      // A template-literal id like `eg-since-${sym}` matches this scan as the
      // token "eg-since-", which is not a class and has no rule. Trim the
      // trailing hyphen an interpolation leaves behind before looking it up,
      // so a legitimate per-row testid cannot fail a STYLE contract.
      const used = new Set((tsx.match(/\beg-[a-z0-9-]+/g) || [])
        .map((c) => c.replace(/-+$/, ''))
        .filter(Boolean));
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
        ema_frames: 'src/components/EmaFramesBoard.tsx',
        news: 'src/components/NewsTabBoard.tsx',
        gajjala: 'src/components/GajjalaBoard.tsx',
      };
      /* A tab whose rows are not TICKERS has nothing for the chip to read.
       * Exempt only in writing, the NO_TOGGLE way below: the file must SAY so,
       * because an absent chip and a dropped chip look identical from here.
       *   news (2026-09-24) — its rows are sectors, macro releases and
       *        headlines; the one per-ticker surface it points at is 🔥 Hottest,
       *        which carries the chip. */
      const NO_CHIP = { news: /no ticker rows on this tab/ };
      // WIDENED 2026-10-16 — 🕯️ doji_sweep is a board tab after 🚩
      const nonBoard = tabs.filter((t) => !/^(zones|deep_demand|quick_bounce|breaking|gabbar|vcp|topping|ict|undervalue|zero_dte|earnings|winners|keltner|amd|ipo|key_levels|dual_momentum|ath|resiliency|fallen|drop10|high_beta|doji_sweep)$/.test(t));
      for (const t of nonBoard) {
        if (t === 'growth') continue;
        const file = RENDERER[t];
        if (!file) {
          errs.push(`tab '${t}' has no renderer listed in this contract — add it and give it a <GrowthChip>`);
          continue;
        }
        const tsx = read(file);
        if (NO_CHIP[t]) {
          if (/<GrowthChip\s/.test(tsx)) {
            errs.push(`${file} (tab '${t}') renders <GrowthChip> but is listed as having no ticker rows — drop it from NO_CHIP in this contract`);
          } else if (!NO_CHIP[t].test(tsx)) {
            errs.push(`${file} (tab '${t}') has no <GrowthChip> and no longer states why — an unexplained omission is indistinguishable from drift`);
          }
          continue;
        }
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
      if (!/MEASURED 2026-09-21/.test(d) || !/a lean, not a finding/.test(d)) {
        errs.push('must say the 100/100 screen was MEASURED 2026-09-21 — a lean, not a finding (2026-10-13)');
      }
      if (/NOTHING HERE IS BACKTESTED|never been measured forward/i.test(d)) {
        errs.push('must not call the screen unmeasured — it was measured 2026-09-21');
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
        ema_frames: 'src/components/EmaFramesBoard.tsx',
        news: 'src/components/NewsTabBoard.tsx',
        gajjala: 'src/components/GajjalaBoard.tsx',
      };
      /* Same written-exemption rule as the growth contract: a tab with no
       * ticker rows has nothing for the 🧨 read to attach to, and must say so
       * in its own file. news (2026-09-24) — sectors, macro, headlines. */
      const NO_CHIP = { news: /no ticker rows on this tab/ };
      // WIDENED 2026-10-16 — 🕯️ doji_sweep is a board tab after 🚩
      const nonBoard = tabs.filter((t) => !/^(zones|deep_demand|quick_bounce|breaking|gabbar|vcp|topping|ict|undervalue|zero_dte|earnings|winners|keltner|amd|ipo|key_levels|dual_momentum|ath|resiliency|fallen|drop10|high_beta|doji_sweep)$/.test(t));
      for (const t of nonBoard) {
        const file = RENDERER[t];
        if (!file) {
          errs.push(`tab '${t}' has no renderer listed in the explosive contract — add it and give it an <ExplosiveChip>`);
          continue;
        }
        const tsx = read(file);
        if (NO_CHIP[t]) {
          if (/<ExplosiveChip\s/.test(tsx)) {
            errs.push(`${file} (tab '${t}') renders <ExplosiveChip> but is listed as having no ticker rows — drop it from NO_CHIP in this contract`);
          } else if (!NO_CHIP[t].test(tsx)) {
            errs.push(`${file} (tab '${t}') has no <ExplosiveChip> and no longer states why — an unexplained omission is indistinguishable from drift`);
          }
          continue;
        }
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
        //   ema_frames — the cohort IS his ⚡ Signals watchlist and the tab
        //           draws it in that list's own order. There is no read on
        //           this board to rank BY: a 9 EMA on weekly bars has never
        //           been measured here, so any ordering toggle would be the
        //           board inventing a preference it cannot defend.
        ema_frames: /no read on this board to rank by/,
        //   news (2026-09-24) — rows are sectors in the 🔥 Hottest board's own
        //           served order, macro releases by date, headlines by time.
        //           None carries a 🧨 read, so there is nothing to rank by.
        news: /no read on this board to rank by/,
        //   gajjala (2026-10-13) — his setup state (A+ → forming → partial)
        //           orders this board; a 🧨 daily S&D ordering would rank his
        //           5-minute setups by a read he does not use (HIS CALL 19).
        gajjala: /his setup state orders this board/,
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
    name: '🧭 macro rows — TLT / UUP / GLD beside SPY · QQQ, served numbers only (2026-10-15)',
    file: 'src/components/IndexZones.tsx',
    // Ajay 2026-10-15, verbatim: "how can.I check us bonds and us dollar and
    // gold can you add them to the SPY and QQQ please? I wanna see their
    // progress". Three compact rows under the SPY / QQQ cards, each opening the
    // SAME card in place via ?iz_open=. Every move is SERVED (number + text,
    // index_zones.progress_read); the page formats none. Copy checks run on the
    // comment-stripped, whitespace-flattened source, as the 🧭 block above.
    checks(src) {
      const errs = [];
      const flat = src
        .replace(/\/\*[\s\S]*?\*\//g, ' ')
        .replace(/(^|[^:])\/\/[^\n]*/g, '$1 ')
        .replace(/\s+/g, ' ');
      for (const [needle, why] of [
        ['export const IZ_MACRO', 'IZ_MACRO (the mirror of index_zones.MACRO) is gone'],
        ['IZ_OPEN_PARAM', 'the open row is no longer keyed on IZ_OPEN_PARAM'],
        ['useSearchParams', 'the open row must live in the URL (useSearchParams)'],
        ['index-macro-', 'the macro rows have no testIds'],
        ['aria-expanded', 'the row toggle must carry aria-expanded'],
        ['izMacroThrough', 'izMacroThrough is gone — one stale row would print with no date of its own'],
        ['index-macro-through-', 'the per-row "through {date}" cell is gone'],
        ['index-macro-note-', 'the opened row no longer draws the served note'],
        ['🧭 SPY · QQQ · macro zones', 'the strip title must be "🧭 SPY · QQQ · macro zones"'],
        ['aria-label="SPY, QQQ and macro zones"', 'the strip aria-label must be "SPY, QQQ and macro zones"'],
        ['computes overnight with SPY and QQQ', 'the pending row must say it computes overnight with SPY and QQQ'],
      ]) {
        if (!flat.includes(needle)) errs.push(why);
      }
      // The open row is the SAME card, not a second renderer.
      if (!/iz-macro-card[\s\S]{0,600}<IndexCard /.test(flat))
        errs.push('the opened macro row must mount <IndexCard inside iz-macro-card');
      // No arithmetic on a move: the served text is printed as is.
      if (/(today_pct|ret_5d|ret_21d)[^\n]{0,60}(toFixed|\*\s*100)/.test(src))
        errs.push('a move is being formatted on the page — print the served progress.text');
      if (/\bedge\b/i.test(flat))
        errs.push('the strip copy says "edge" — the row says "nearest band"');
      if (/\bbounce\b/i.test(src))
        errs.push('house rule: the word is "reversal", never "bounce"');

      let feats = '';
      try {
        feats = read('src/lib/newFeatures.ts');
      } catch {
        return [...errs, 'src/lib/newFeatures.ts is missing'];
      }
      const id = 'index-zones-macro-2026-10-15';
      const start = feats.indexOf(`id: '${id}'`);
      if (start < 0) return [...errs, `the ${id} ✨ entry is missing`];
      const next = feats.indexOf("{ id: '", start + 1);
      const entry = feats.slice(start, next > start ? next : undefined);
      const lm = /label: '([^']*)'/.exec(entry);
      if (!lm) return [...errs, `the ${id} ✨ entry has no single-quoted label`];
      const label = lm[1];
      const ask = 'how can.I check us bonds and us dollar and gold can you add them to the SPY and QQQ please? I wanna see their progress';
      if (!label.includes(ask)) errs.push('the ✨ label must quote the ask verbatim');
      for (const w of ['TLT', 'UUP', 'GLD', 'PROXIES', 'official when the snapshot carries it']) {
        if (!label.includes(w)) errs.push(`the ✨ label must say "${w}"`);
      }
      if (label.includes('against the official prior close'))
        errs.push('the ✨ label must not say "against the official prior close" — it is official only when the snapshot carries it');
      if (/\bbounce\b/i.test(entry)) errs.push('house rule: the ✨ entry says "bounce"');
      if (label.length > 700) errs.push(`the ✨ label is ${label.length} chars — AMENDMENTS3 C3 caps it at 700`);
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
      if (!/100\/100 screen[\s\S]{0,80}?measured 2026-09-21[\s\S]{0,40}?a lean, not a finding/.test(d)) {
        errs.push('the entry must say the 100/100 growth screen was measured 2026-09-21 as a lean, not a finding (2026-10-13)');
      }
      if (/never been measured forward|NOTHING HERE IS BACKTESTED/i.test(d)) {
        errs.push('the entry must not call the 100/100 screen unmeasured — it was measured 2026-09-21');
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
      // 2026-09-28: `basisPlan.sort` = sortBasis(shownSort, …) — the SERVED
      // sorted_by once landed (a superset of the shownSortKey demotion rule).
      if (!/(shownSort|basisPlan\.sort) === c\.key/.test(tsx)) errs.push('the header mark must follow the SERVED sort (shownSortKey / basisPlan.sort), not the requested one');
      if (!/ranked on <b>\{colLabel\((shownSort|basisPlan\.sort), data\)\}/.test(tsx)) errs.push('the "ranked on" line must print the served sort — under a demotion the rows are on 5 days');
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
  {
    name: '\u{1F300} AMD chips: a served pre-market state and a stale-grid signal (2026-09-21)',
    file: 'src/pages/ChartMaps.tsx',
    // Ajay 2026-09-21: "These chips are not working" — a pre-market screenshot
    // where two of the three in-flight chips carried counts built from a day
    // aggregate that had not started, and where a chip click looked dead for
    // ~60 s because nothing on screen changed.
    //
    // Two rules, both the SERVER's: which states are unreadable this request
    // (`flight_scope.unknowable`) and the sentence that says why, counts
    // already in it (`reason_line`). The page prints them. It never coerces a
    // count (a `Number(` turns an absent key into a `0` chip, which is a claim
    // that the state is empty), never composes the reason, and never decides
    // any of it from this browser's clock.
    checks: (tsx) => {
      const errs = [];
      const lib = read('src/lib/chartMaps.ts');
      const css = read('src/styles.css');
      // The body of `export function <name>(...) { ... }` by brace count.
      const bodyOf = (src, name) => {
        const i = src.indexOf(`export function ${name}(`);
        if (i < 0) return null;
        const open = src.indexOf('{\n', src.indexOf(')', i));
        let depth = 0;
        for (let j = open; j < src.length; j++) {
          if (src[j] === '{') depth++;
          else if (src[j] === '}' && --depth === 0) return src.slice(open, j + 1);
        }
        return null;
      };

      /* ── the stale grid ─────────────────────────────────────────────────── */
      const grid = tsx.slice(tsx.indexOf('className={`cm-grid'), tsx.indexOf('className={`cm-grid') + 200);
      if (!/cm-grid-stale/.test(grid)) {
        errs.push('the tile grid must carry cm-grid-stale while a board is in the air — a click that changes nothing reads as broken');
      }
      if (!/aria-busy=\{stale/.test(grid)) {
        errs.push('the tile grid must say aria-busy while it is stale — the dim is a colour, not an announcement');
      }
      if (!/const stale = loading && tiles\.length > 0/.test(tsx)) {
        errs.push('stale must mean "a board is in the air AND there are old tiles" — the first load is the "Loading charts…" note, not a dim');
      }
      if (!/data-testid="cm-fetching"/.test(tsx)) errs.push('the receipt line needs data-testid="cm-fetching"');
      if ((tsx.match(/data-testid="cm-fetching"/g) || []).length !== 2) {
        errs.push('exactly two cm-fetching slots may exist in the source (control row / note), gated so only ONE renders');
      }
      if (!/stale && !PHASE_ROW/.test(tsx)) {
        errs.push('the note-slot receipt must be gated on !PHASE_ROW — two receipts on screen is two answers to one click');
      }
      if (!/fetchingLabel\(gradeSel, flightSel\)/.test(tsx)) {
        errs.push('the receipt must name the SELECTED chips through fetchingLabel, never a hand-built string');
      }

      /* ── the in-flight chips ────────────────────────────────────────────── */
      const a = tsx.indexOf('aria-label="In flight"');
      const b = tsx.indexOf('aria-label="AMD grade"');
      const chips = a < 0 || b < 0 ? '' : tsx.slice(a, b);
      if (!chips) errs.push('cannot find the In flight chip row — did the aria-label change?');
      if (!/flightChip\(/.test(chips)) {
        errs.push('the in-flight chips must read through flightChip() — one place decides what a chip says');
      }
      if (/Number\(data\.flight_counts/.test(tsx)) {
        errs.push('no Number( on flight_counts — an absent count would render as "· 0", which claims the state is empty');
      }
      if (!/unknowable \? ' · —'/.test(chips)) {
        errs.push('a state the server could not read must render · —, never a number');
      }
      if (!/title=\{title \?\? undefined\}/.test(chips)) {
        errs.push('the — chip must hover the SERVED line — that sentence is where the count reaches him');
      }
      if (!/aria-disabled=\{dim \|\| undefined\}/.test(chips) || /(?<!aria-)disabled=\{/.test(chips)) {
        errs.push('an unreadable chip stays CLICKABLE — dimmed and aria-disabled, never a dead control (spec §7.7)');
      }
      if (!/flight_scope\?\.note/.test(chips)) {
        errs.push('the flight tablist title must append the served cost note — the FE never retypes what the counts cost');
      }
      if (!/not closed|unconfirmed|forming/i.test(chips)) {
        errs.push('the flight tooltip must keep saying nothing here is confirmed until the close');
      }

      /* ── nothing textual is composed on the page ────────────────────────── */
      for (const [name, src] of [['ChartMaps.tsx', tsx], ['lib/chartMaps.ts', lib]]) {
        if (/no session low/.test(src)) {
          errs.push(`${name} holds a literal of the served reason — that sentence has ONE home, chart_maps/board.py`);
        }
        if (/ of \$\{[^}]*\} priced names| of .{0,40} priced names/.test(src)) {
          errs.push(`${name} composes a count line — the server serves reason_line already counted`);
        }
      }
      for (const fn of ['flightChip', 'fetchingLabel']) {
        const body = bodyOf(lib, fn);
        if (!body) { errs.push(`export function ${fn} is missing from lib/chartMaps.ts`); continue; }
        if (/new Date\(|Date\.now\(|tape_session/.test(body)) {
          errs.push(`${fn} must not decide from a clock or the tape — the server says which states it could read`);
        }
        if (/Number\(/.test(body)) errs.push(`${fn} must not coerce — an absent count is null, not 0`);
      }
      const chip = bodyOf(lib, 'flightChip') || '';
      for (const k of ['flight_scope', 'unknowable', 'reason_line']) {
        if (!chip.includes(k)) errs.push(`flightChip must read ${k} — it is the server's own answer`);
      }
      if (!/reason_line \?\? b\.flight_scope\?\.reason \?\? null/.test(chip)) {
        errs.push('flightChip must fall back reason_line → reason → null, never to a string of its own');
      }

      /* ── the two new classes exist and are styled ───────────────────────── */
      // data-testid values are NOT classes (the Hottest sweep learned this).
      const tsxClasses = tsx.replace(/data-testid=\{?[`'"][^`'"]*[`'"]\}?/g, '');
      for (const c of ['cm-grid-stale', 'cm-phase-fetching']) {
        if (!new RegExp(`\\b${c}(?![\\w-])`).test(tsxClasses)) {
          errs.push(`ChartMaps.tsx no longer uses .${c} — the stale board would ship unmarked`);
        }
        if (!new RegExp(`\\.${c}(?![\\w-])`).test(css)) {
          errs.push(`styles.css has no rule for .${c} — the signal would ship invisible`);
        }
      }
      if (!/\.cm-grid-stale\s*\{[^}]*opacity/.test(css)) {
        errs.push('.cm-grid-stale must dim the grid');
      }
      if (/\.cm-grid-stale\s*\{[^}]*pointer-events/.test(css)) {
        errs.push('.cm-grid-stale must NOT make the tiles inert — he clicks through a refetch');
      }
      if (!/id: 'amd-chips-fixed-2026-09-21'/.test(read('src/lib/newFeatures.ts'))) errs.push('the chip fix needs its ✨ entry');
      return errs;
    },
  },
  {
    name: '🔔 price-alert state line is SERVED, never composed (2026-09-21)',
    file: 'src/components/TickerAlertPresets.tsx',
    // Ajay 2026-09-21: "Yes please stop them". An alert now fires once per
    // crossing and re-arms when price crosses back; the backend builds the
    // whole "triggered <day> at $x — re-arms when…" sentence. The page prints
    // it verbatim: no date math, no composed wording, no browser clock.
    checks: (tsx) => {
      const errs = [];
      if (!/a\.state_line/.test(tsx)) errs.push('the active-alert row must print the served state_line');
      if (!/pa-state-line/.test(tsx)) errs.push('the state line needs its pa-state-line hook');
      if (/new Date\(|Date\.now\(/.test(tsx)) errs.push('TickerAlertPresets must not read the browser clock — the day label is served');
      if (/re-arms/.test(tsx)) errs.push('the "re-arms when…" sentence is the SERVER\'s — never typed into the component');
      if (/triggered /.test(tsx)) errs.push('the "triggered <day>" wording is the SERVER\'s — never typed into the component');
      const hook = read('src/hooks/usePriceAlerts.ts');
      for (const k of ['armed', 'triggered_at', 'state_line']) {
        if (!new RegExp(`\\b${k}\\??:`).test(hook)) errs.push(`usePriceAlerts.ts must type the served ${k} field`);
      }
      const py = read('../backend/sepa/price_alerts.py');
      const pyCode = py.split('\n').filter((l) => !/^\s*#/.test(l)).join('\n');
      if (!/def _state_line\(/.test(pyCode)) errs.push('price_alerts.py must build the state line server-side');
      if (!/"armed"/.test(pyCode)) errs.push('price_alerts.py must carry the armed latch');
      if (!/ALERT_COOLDOWN_SEC = 6 \* 3600/.test(pyCode)) errs.push('ALERT_COOLDOWN_SEC moved — a threshold change is his call');
      if (!/id: 'price-alerts-once-per-crossing-2026-09-21'/.test(read('src/lib/newFeatures.ts'))) errs.push('the latch needs its ✨ entry');
      return errs;
    },
  },
  {
    name: '🔔 price alerts reach the phone again; repeated rows fold (2026-09-21)',
    file: 'src/pages/Notifications.tsx',
    // Ajay 2026-09-21, "Yes to all..": (1) turn price alerts back on — he asked,
    // and a notification pref is never flipped without him; (2) collapse the
    // repeated rows on the Alerts page. The fold is SERVER-side: push/recent
    // builds the whole "N more like this · first … , last …" sentence and the
    // three surfaces print it. None of them recomposes it.
    checks: (src) => {
      const errs = [];
      const subs = read('../backend/push/subs.py');
      if (!keepSet(subs).includes('price_alert')) {
        errs.push('price_alert left OWNER_KEEP_SET — a re-registered device would mute it again');
      }
      for (const retired of ['_RETIRED_2026_06_13', 'RETIRED_2026_09_20']) {
        const set = pyFrozenSet(subs, retired) || [];
        if (set.includes('price_alert')) errs.push(`price_alert is back in ${retired} — he asked for it ON (2026-09-21)`);
      }
      if (!/key: 'price_alert'/.test(src)) errs.push('Notifications.tsx must offer the 🔔 Price alerts toggle');
      if (/price_alert is PAUSED/.test(src)) errs.push('the PAUSED note is stale — price alerts came back 2026-09-21');
      const ess = src.slice(src.indexOf("id: 'essentials'"), src.indexOf("id: 'trading_only'"));
      if (!/price_alert:\s*true/.test(ess)) errs.push('Essentials preset must keep price_alert on — it is in OWNER_KEEP_SET');
      const py = read('../backend/push/recent.py');
      const pyCode = py.split('\n').filter((l) => !/^\s*#/.test(l)).join('\n');
      if (!/def collapse_repeats\(/.test(pyCode)) errs.push('push/recent.py must build the fold server-side');
      if (!/def repeat_line\(/.test(pyCode)) errs.push('push/recent.py must build the repeat SENTENCE — the page never composes it');
      if (!/collapse: bool = True/.test(pyCode)) errs.push('the fold must default ON and stay defeatable with collapse=false');
      for (const f of ['src/pages/Alerts.tsx', 'src/components/NotificationBell.tsx',
                       'src/components/PushHistoryPanel.tsx']) {
        const tsx = read(f);
        if (!/repeat\?\.line/.test(tsx)) errs.push(`${f} must print the served repeat.line`);
        if (/more like this/.test(tsx)) errs.push(`${f} types the served fold sentence — it is the SERVER's wording`);
        if (/first .*ET, last/.test(tsx)) errs.push(`${f} composes the fold stamps — the server already did`);
      }
      if (!/id: 'price-alerts-on-and-feed-fold-2026-09-21'/.test(read('src/lib/newFeatures.ts'))) {
        errs.push('the un-pause + fold needs its ✨ entry');
      }
      return errs;
    },
  },
  {
    name: '🔋 energy, nuclear and critical-minerals rosters (2026-09-21)',
    file: 'src/lib/newFeatures.ts',
    // Ajay 2026-09-21: "can you add x energy and then other small energy
    // companies in to our list please", "Do we have critical minerals in our
    // list?", "Also greenland minerals or greenland related mineral companies".
    // THEME_UNIVERSE is the real "our list". The rosters are data; what this
    // contract defends is that the two names validation REFUSED never come back
    // and that the derived index stays derived.
    checks: (src) => {
      const errs = [];
      const uni = read('../backend/sepa/universe.py');
      if (!/^\s*"critical_minerals":/m.test(uni)) {
        errs.push('the critical_minerals roster is gone from THEME_UNIVERSE');
      }
      for (const sym of ['XE', 'CCJ', 'CRML']) {
        if (!new RegExp(`"${sym}"`).test(uni)) errs.push(`${sym} left the rosters — he asked for it by name`);
      }
      // PEN reads like a uranium ticker and is Penumbra, a medical-device
      // company; SRUUF is a commodity trust, not an operating company. Both
      // were caught in validation and must never be re-added by a later sweep.
      for (const [sym, why] of [['PEN', 'Penumbra, a medical-device company'],
                                ['SRUUF', 'a commodity trust, not an operating company']]) {
        if (new RegExp(`"${sym}"`).test(uni)) errs.push(`${sym} is back in the universe — it is ${why}`);
      }
      if (!/THEME_BY_TICKER\s*(:[^=]*)?=\s*\{[\s\S]{0,200}?for /.test(uni)) {
        errs.push('THEME_BY_TICKER must stay DERIVED from THEME_UNIVERSE, never hand-written');
      }
      if (!/_assert_themes_disjoint\(\)/.test(uni)) {
        errs.push('the disjoint check must still run at import — it is what makes a double-listing a crash');
      }
      if (!/id: 'energy-minerals-rosters-2026-09-21'/.test(src)) {
        errs.push('the roster additions need their ✨ entry');
      }
      return errs;
    },
  },
  {
    name: '🗄️ data_infra theme — his three anchors, the cloud_infra move (2026-09-28)',
    file: 'src/lib/newFeatures.ts',
    // Ajay 2026-09-28: "Can you create a new sector for DATA driven companies
    // like DATA DOG, Mongo DB and Snow flake in to the add them accross board
    // where we have sectors". Matched INSIDE the extracted roster blocks, never
    // the whole file: universe.py's curated UNIVERSE list quotes SNOW, DDOG,
    // MDB and PLTR too. ORCL and PLTR are deliberately NOT guarded — both are
    // HIS CALL, and a guard would block his answer.
    checks: (src) => {
      const errs = [];
      const uni = read('../backend/sepa/universe.py');
      const di = uni.match(/^\s*"data_infra":\s*\[([^\]]*)\]/m);
      if (!di) {
        errs.push('the data_infra roster is gone from THEME_UNIVERSE');
      } else {
        for (const s of ['DDOG', 'MDB', 'SNOW']) {
          if (!new RegExp(`"${s}"`).test(di[1])) errs.push(`${s} left data_infra — he named it`);
        }
        if (/"CFLT"/.test(di[1])) errs.push('CFLT is delisted (sepa.symbols.DELISTED)');
      }
      const ci = uni.match(/^\s*"cloud_infra":\s*\[([^\]]*)\]/m);
      if (ci) {
        for (const s of ['MDB', 'TDC']) {
          if (new RegExp(`"${s}"`).test(ci[1])) errs.push(`${s} is back in cloud_infra — a ticker lives in one roster`);
        }
      }
      if (!/data_infra:\s*'Data infra'/.test(read('src/components/HottestSectors.tsx'))) {
        errs.push('the Hottest row needs its readable label');
      }
      if (!/id: 'data-infra-theme-2026-09-28'/.test(src)) {
        errs.push('the theme needs its ✨ entry');
      }
      return errs;
    },
  },
  {
    name: '🎪 promo-circuit names enter the universe through a GATE, and every board says so (2026-09-21)',
    file: 'src/components/PromoOriginChip.tsx',
    // Ajay 2026-09-21: "We have this page that pull data from social media and
    // chatter the keeps pulling new stocks.. Can you please check if we can use
    // them and make sure to do some research and add them to our lis tas they
    // come through please?"
    //
    // Being tagged is the INPUT, never the test. What this contract defends:
    // the gate order (an ETF is refused before anything fetches bars), the
    // fail-CLOSED reference lookup, the fail-EMPTY universe fetcher, floors
    // that are IMPORTED objects rather than retyped numbers, and the origin
    // label travelling with the name onto every board that shows a 🚀 chip.
    checks: (src) => {
      const errs = [];
      const cur = read('../backend/catalysts/promo_curate.py');
      const uni = read('../backend/sepa/universe.py');

      if (!/"promo"/.test(uni)) errs.push('the promo component left the `full` universe tuple');
      if (!/_EXPECTED_COUNTS\[["']promo["']\]|["']promo["']\s*:\s*\(/.test(uni)) {
        errs.push('the promo component has no size band in _EXPECTED_COUNTS');
      }
      if (!/def fetch_promo_adds\(/.test(uni)) errs.push('universe.py must own the promo fetcher');

      // fail CLOSED on the reference lookup: an unknown security type is refused.
      if (!/ADD_TYPES\s*=\s*frozenset\(\{\s*["']CS["']\s*\}\)/.test(cur)) {
        errs.push('ADD_TYPES must stay {"CS"} — an ADR, ETF or unknown type is refused');
      }
      if (!/MAJOR_EXCHANGES/.test(cur)) errs.push('the listing-exchange gate must reuse universe.MAJOR_EXCHANGES, not a new list');
      if (!/PERMANENT_REJECTS/.test(cur)) errs.push('a refused ADR must not be re-probed every morning');

      // floors are imported objects, never retyped numbers.
      for (const name of ['MIN_SHARE_PRICE', 'MIN_DOLLAR_VOL_USD', 'MAX_ADDS_PER_RUN']) {
        if (!new RegExp(`import[^\\n]*${name}|${name}`).test(cur)) {
          errs.push(`${name} must be imported from the module that enforces it`);
        }
      }

      // the chip: renders NOTHING for a name that did not come through the lane,
      // and never composes a verdict the backend did not serve.
      if (!/if \(!chip\) return null/.test(src)) {
        errs.push('PromoOriginChip must render nothing for the common case');
      }
      if (/\bbounce\b/i.test(src)) errs.push('every surface he reads says "reversal", never "bounce"');

      // parity: every board that shows a 🚀 GrowthChip shows the origin label.
      for (const f of ['src/components/BondeBoard.tsx', 'src/components/HottestSectors.tsx',
                       'src/components/ExplosiveGrowth.tsx', 'src/pages/Catalysts.tsx',
                       'src/pages/SepaCandidate.tsx', 'src/components/SepaCandidateCard.tsx']) {
        if (!/<PromoOriginChip/.test(read(f))) {
          errs.push(`${f} shows board rows without the promo-origin label`);
        }
      }

      if (!/id: 'promo-curation-2026-09-21'/.test(read('src/lib/newFeatures.ts'))) {
        errs.push('the curation lane needs its ✨ entry');
      }
      return errs;
    },
  },
  {
    name: '\u{1F4C5} Since report: a FACT between two dates, on the REPORT date, never flat (2026-09-21)',
    file: 'src/lib/sinceReport.ts',
    // Ajay 2026-09-21, answering "Should the boards print a 'since qualifying
    // filing' column?" with "Yes". The 2026-09-21 replay found the typical name
    // on both boards had already had its run before the board could see it
    // (growth +46.40% before the qualifying filing, \u22122.21% since).
    //
    // Three things must stay true or the column starts lying:
    //   1. it is a FACT between two dates \u2014 it sorts, filters and gates nothing;
    //   2. the anchor is the EARNINGS REPORT date, never the SEC filing date the
    //      study measured from, and every surface says which;
    //   3. a blank is never 0% and never a bare dash that reads as flat.
    checks: (src) => {
      const errs = [];
      const py = read('../backend/sepa/since_report.py');
      const pyCode = py.split('\n').filter((l) => !/^\s*#/.test(l)).join('\n');

      if (!/RUN_MEASURED\s*=\s*\{/.test(pyCode)) {
        errs.push('since_report.py must keep the run\u2019s numbers in ONE constant');
      }
      if (/board_growth_measured/.test(py)) {
        errs.push('a served module must not read the research artifact \u2014 pin it in a test instead');
      }
      if (!/def honesty_line\(/.test(pyCode)) {
        errs.push('the board\u2019s honesty sentence must be BUILT from RUN_MEASURED, not typed');
      }
      for (const needle of ['no_report', 'bad_date', 'not_traded_yet', 'no_bars',
                            'before_first_bar', 'insufficient_history']) {
        if (!new RegExp(`["']${needle}["']`).test(pyCode)) {
          errs.push(`since_report.py lost the ${needle} refusal \u2014 a blank must always say why`);
        }
      }

      // the FE never re-derives the number and never invents a date
      if (/new Date\(/.test(src)) {
        errs.push('sinceReport.ts must not use the Date constructor \u2014 it prints the PREVIOUS ET day');
      }
      if (!/SINCE_REPORT_BLANK/.test(src)) errs.push('every blank needs its worded reason');
      if (!/Not measured:/.test(src)) {
        errs.push('a blank cell must open "Not measured:" \u2014 never a dash that reads as flat');
      }
      if (!/REPORT\s*'?\s*\+?\s*'?date/i.test(src) || !/SEC filing date/.test(src)) {
        errs.push('the column head must say it uses the REPORT date, not the SEC filing date');
      }
      if (!/sorts,\s*\n?\s*'?\s*\+?\s*'?filters and gates nothing|sorts, filters and gates nothing/.test(src)) {
        errs.push('the column head must say in words that it decides nothing');
      }
      if (/\bbounce\b/i.test(src)) errs.push('every surface he reads says "reversal", never "bounce"');

      // both boards render it, and neither sorts on it
      for (const f of ['src/components/ExplosiveGrowth.tsx', 'src/components/BondeBoard.tsx']) {
        const tsx = read(f);
        if (!/sinceReportCell\(/.test(tsx)) errs.push(`${f} must render the served cell`);
        if (!/sinceReportCoverage\(/.test(tsx)) errs.push(`${f} must print how many rows are known`);
        // Strip comments first: the file's own banner says "it sorts, filters
        // and gates nothing", which is the disclaimer, not a violation.
        const code = tsx.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
        if (/\.sort\([^)]*since_report|since_report[^\n;]*\.sort\(/i.test(code)) {
          errs.push(`${f} sorts on the new column \u2014 it is a fact, not a ranking (Rule #10)`);
        }
      }
      if (!/id: 'since-report-column-2026-09-21'/.test(read('src/lib/newFeatures.ts'))) {
        errs.push('the Since report column needs its \u2728 entry');
      }
      return errs;
    },
  },
  {
    name: '\u{1F4C8} the Bonde steady tier carries its measurement, and stays on the board (2026-09-21)',
    file: 'src/components/BondeBoard.tsx',
    // He was offered leave / label / drop and answered "Yes"; the main session
    // read that as LABEL. The tier stays, nothing is hidden or re-sorted, and
    // the served line states the weaker reading as plainly as the stronger one:
    // the h=21 interval sits below zero symbol-clustered and SPANS zero
    // date-clustered, so it is a lean, not a finding.
    checks: (src) => {
      const errs = [];
      const py = read('../backend/sepa/bonde.py');
      const pyCode = py.split('\n').filter((l) => !/^\s*#/.test(l)).join('\n');

      if (!/STEADY_MEASURED\s*=/.test(pyCode)) {
        errs.push('bonde.py must keep the steady numbers in ONE constant, pinned to the artifact');
      }
      if (!/def steady_verdict\(/.test(pyCode)) {
        errs.push('the steady line must be BUILT from that constant, never typed');
      }
      if (/board_growth_measured/.test(py)) {
        errs.push('a served module must not read the research artifact \u2014 pin it in a test instead');
      }
      if (!/data-testid="bd-steady-measured"/.test(src)) {
        errs.push('the steady section must render the served line');
      }
      if (!/m\?\.steady|measured\?\.steady/.test(src)) {
        errs.push('the line must come from the SERVED measured block, never composed on the page');
      }
      // the tier is labelled, NOT removed
      if (!/'steady'/.test(src)) errs.push('the steady section left the board \u2014 he said label, not drop');
      if (/steady[^\n]*(hidden|hide|filterOut|exclude)/i.test(src)) {
        errs.push('the steady tier must not be hidden or filtered \u2014 label only');
      }
      // The standing rule bans the WORD on a surface he reads. The engine's own
      // identifiers (useBounceRoom, bounceRoom, bounce_room) keep it on purpose,
      // so strip comments and imports and exempt the room forms.
      const visible = src
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/^\s*\/\/.*$/gm, '')
        .replace(/^\s*import[\s\S]*?from\s+'[^']*';$/gm, '')
        .replace(/[Bb]ounce[-_]?[Rr]oom/g, '');
      if (/\bbounce\b/i.test(visible)) {
        errs.push('every surface he reads says "reversal", never "bounce"');
      }
      if (!/id: 'bonde-steady-measured-2026-09-21'/.test(read('src/lib/newFeatures.ts'))) {
        errs.push('the steady-tier label needs its \u2728 entry');
      }
      return errs;
    },
  },
  {
    name: '\u{1F300} the AMD column on \u{1F525} Hottest: a STATE, never a ranking (2026-09-22)',
    file: 'src/lib/hottestAmd.ts',
    // Ajay 2026-09-22, on a screenshot of the Defense roster: "Add an AMD tag
    // for these. like a column for me to see which one are getting
    // manipulated."
    //
    // The read he asked for is MEASURED INVERTED on its own claim (2026-09-14,
    // 3,712 names / 1,592,057 bars: 51.9% vs 56.1% like-for-like, -4.2pp
    // [-6.92,-1.89], negative in all seven distance buckets). So the column
    // ships colourless, unsortable, and carrying that verdict. Three things
    // must stay true or it starts implying an edge nobody measured:
    //   1. every word is SERVED -- the page composes no verdict;
    //   2. it does not sort and it is not coloured, each with a served reason;
    //   3. a blank is UNKNOWN and never wears the words of a real read.
    checks: (src) => {
      const errs = [];
      const py = read('../backend/rotation/hottest_amd.py');
      const pyCode = py.split('\n').filter((l) => !/^\s*#/.test(l)).join('\n');

      if (!/AMD_MEASURED\s*=\s*\{/.test(pyCode)) {
        errs.push('hottest_amd.py must keep the measured verdict in ONE constant');
      }
      for (const needle of ['sortable', 'coloured', 'no_sort_reason', 'no_colour_reason']) {
        if (!new RegExp(`["']${needle}["']`).test(pyCode)) {
          errs.push(`the payload must declare ${needle} \u2014 the page never decides it`);
        }
      }
      if (!/["']sortable["']:\s*False/.test(pyCode)) {
        errs.push('the column must ship NOT sortable \u2014 ranking on a read measured inverted');
      }
      if (!/["']coloured["']:\s*False/.test(pyCode)) {
        errs.push('the column must ship colourless \u2014 colour would paint "raided" green');
      }
      // the refusal sentences must never wear the words of a real read
      for (const m of pyCode.matchAll(/REASON_TEXT\s*=\s*\{([\s\S]*?)\n\}/g)) {
        const body = m[1].toLowerCase();
        if (/no cycle/.test(body)) errs.push('a blank sentence says "no cycle" \u2014 those are a real read\u2019s words');
        if (/clean/.test(body)) errs.push('a blank sentence says "clean" \u2014 a blank is UNKNOWN, not clean');
      }
      // the FE prints the served cell and invents nothing
      if (!/sortable:\s*false/.test(src)) errs.push('AMD_COL must declare itself unsortable');
      if (/new Date\(/.test(src)) {
        errs.push('hottestAmd.ts must not use the Date constructor \u2014 it prints the PREVIOUS ET day');
      }
      if (/\bbounce\b/i.test(src)) errs.push('every surface he reads says "reversal", never "bounce"');

      const tsx = read('src/components/HottestSectors.tsx');
      if (!/amdCell\(/.test(tsx)) errs.push('HottestSectors.tsx must render the served cell');
      if (!/amdCoverageNote\(/.test(tsx)) errs.push('the board must print how many names the sweep covered');
      const code = tsx.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
      if (/\.sort\([^)]*amd|amd[^\n;]*\.sort\(/i.test(code)) {
        errs.push('HottestSectors.tsx sorts on the AMD column \u2014 it is a state, not a ranking');
      }
      if (!/id: 'hottest-amd-column-2026-09-22'/.test(read('src/lib/newFeatures.ts'))) {
        errs.push('the AMD column needs its \u2728 entry');
      }
      return errs;
    },
  },
  {
    name: '\u229E \u{1F525} Hottest opens every group in one click, and remembers it (2026-09-22)',
    file: 'src/components/HottestSectors.tsx',
    // Ajay 2026-09-22: "Also give me toggle option to open them app on one
    // click in stead of clicking on the carets". One control, persisted under
    // the board's own key, and the row count is stated on the button because
    // one click can open the whole payload.
    checks: (src) => {
      const errs = [];
      if (!/HS_EXPAND_KEY\s*=\s*'hs\.expandAll'/.test(src)) {
        errs.push('the expand-all preference must persist under the board\u2019s own key');
      }
      if (!/EXPAND_ALL_TITLE/.test(src)) {
        errs.push('the control must say what it will open \u2014 one click can open the whole payload');
      }
      if (!/inheritsAll|allOpen/.test(src)) {
        errs.push('a group that appears after the toggle must inherit the all-state, not default closed');
      }
      if (!/id: 'hottest-expand-all-2026-09-22'/.test(read('src/lib/newFeatures.ts'))) {
        errs.push('the expand-all toggle needs its \u2728 entry');
      }
      return errs;
    },
  },
  {
    name: '\u{1F300} the AMD column sits where he can SEE it, and the ranked legs stay together (2026-09-22)',
    file: 'src/components/HottestSectors.tsx',
    // Ajay 2026-09-22, on a screenshot: "last column is hidded". It shipped as
    // the twelfth of twelve on a table that already scrolled sideways.
    //
    // The fix is a POSITION, so a contract has to pin the position — and the
    // trap that made the first attempt dangerous: `visibleCols()` drives only
    // the <thead>. Every <tbody> cell is hard-coded JSX in source order, so
    // moving the header alone silently prints every name's AMD value under the
    // "Next ER" heading and shifts all nine ranked legs one header left.
    checks: (src) => {
      const errs = [];
      const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

      // 1. the header order: AMD first, then Pre-mkt leading the ranked legs
      const vc = (code.match(/export function visibleCols[\s\S]*?\n\}/) || [''])[0];
      if (!vc) errs.push('visibleCols() not found \u2014 the column order is unpinnable');
      else {
        const iAmd = vc.indexOf('AMD_COL');
        const iPre = vc.indexOf('PRE_COL');
        const iCols = vc.indexOf('...HS_COLS');
        if (iAmd < 0 || iPre < 0 || iCols < 0) {
          errs.push('visibleCols() no longer names all three of AMD_COL / PRE_COL / HS_COLS');
        } else if (!(iAmd < iPre && iPre < iCols)) {
          errs.push('the \u{1F300} AMD column must come FIRST, then Pre-mkt, then HS_COLS '
            + '\u2014 he reported it hidden when it was last');
        }
      }

      // 2. THE TRAP: the tbody cell order must match, or the board is misaligned
      const bodyOrder = (name, cellRe) => {
        const fn = (code.match(new RegExp(`function ${name}\\(([\\s\\S]*?)\\n\\}`)) || [''])[0];
        if (!fn) return null;
        const iAmd = fn.search(cellRe);
        const iLeg = fn.indexOf('<LegCells');
        return iAmd < 0 || iLeg < 0 ? null : iAmd < iLeg;
      };
      const nameRow = bodyOrder('NameRow', /hs-amd|amdCell\(/);
      if (nameRow === false) {
        errs.push('NameRow renders the AMD cell AFTER the ranked legs while the header '
          + 'puts it first \u2014 every value would print under the wrong heading');
      }
      // group rows: the em-dash cell must precede LegCells everywhere it is drawn
      const groupCells = [...code.matchAll(/<AmdGroupCell[\s\S]{0,400}?<LegCells/g)].length;
      const groupCellsAfter = [...code.matchAll(/<LegCells[\s\S]{0,400}?<AmdGroupCell/g)].length;
      if (groupCellsAfter > 0) {
        errs.push(`${groupCellsAfter} group row(s) render <AmdGroupCell> AFTER <LegCells> `
          + '\u2014 a group row stays cell-COUNT correct while being column-WRONG, '
          + 'because GroupFundCells ends in a spacer <td>');
      }
      if (!groupCells) {
        errs.push('no group row renders <AmdGroupCell> before <LegCells>');
      }

      // 3. the colSpan rows must be derived, never a hard-coded count
      if (/colSpan=\{\s*\d+\s*\}/.test(code)) {
        errs.push('a hard-coded colSpan survives \u2014 a new column leaves that row one cell short');
      }

      // 4. nothing was hidden to make room
      const media = (read('src/styles.css').match(
        /@media \(max-width: 720px\)\s*\{([\s\S]*?)\n\}/) || ['', ''])[1];
      if (/display:\s*none/.test(media)) {
        errs.push('the 720px block hides something \u2014 which column a phone loses is HIS call');
      }

      if (!/id: 'hottest-amd-column-visible-2026-09-22'/.test(read('src/lib/newFeatures.ts'))) {
        errs.push('the move needs its \u2728 entry');
      }
      // the question he ANSWERED must not still be asked on the card
      if (/whether it belongs before the price columns/.test(read('src/lib/newFeatures.ts'))) {
        errs.push('the \u2728 card still asks him where the column belongs \u2014 he answered that');
      }
      return errs;
    },
  },
  {
    name: '\u{1F300} the AMD cell prints a SERVED short form, never the page trimming a sentence (2026-09-22)',
    file: 'src/lib/hottestAmd.ts',
    // ~1,900 cells each began with the literal "AMD " while the header already
    // said 🌀 AMD. The short form is derived from the SAME backend wording
    // table as the long one — never by the page slicing a prefix off a served
    // sentence, which is how two surfaces start disagreeing.
    checks: (src) => {
      const errs = [];
      const py = read('../backend/supply_demand/turning_bullish.py');
      if (!/def verdict_short/.test(py)) {
        errs.push('the short form must be SERVED from turning_bullish, beside verdict_text');
      }
      if (!/AMD_TEXT/.test(py)) errs.push('one wording table, or the surfaces drift');
      // the page must not do string surgery on a served sentence
      for (const re of [/\.replace\(\s*['"/]AMD/, /\.slice\(\s*4\s*\)/, /startsWith\(\s*['"]AMD/]) {
        if (re.test(src)) {
          errs.push('hottestAmd.ts trims a served sentence \u2014 the short form is SERVED, not derived here');
        }
      }
      if (!/\bshort\b/.test(src)) errs.push('the cell must read the served `short` field');
      // a fallback must land on the served long text, never on a composed string
      if (!/short[\s\S]{0,120}\btext\b/.test(src)) {
        errs.push('no visible fallback from `short` to the served `text`');
      }
      if (/built_at_utc\?:\s*string/.test(src)) {
        errs.push('built_at_utc is a boolean MARKER, not a stamp \u2014 typing it as a string '
          + 'invites it to be printed as a date');
      }
      return errs;
    },
  },
  {
    name: '\u{1F48E} capital quality: not ONE invented number, and no attribution it cannot prove (2026-09-22)',
    file: 'src/lib/capitalQuality.ts',
    // Ajay 2026-09-22: "quality like very less capital and hi ROI", plus
    // "Rakesh Junjunwala used to call them Ghee companies. Look in to this."
    //
    // TWO things this contract exists to hold, both of which have burned this
    // app before:
    //   1. RULE #1. Four researchers and three adversarial refuters could not
    //      find ONE sourced link between Jhunjhunwala and "ghee companies" —
    //      no interview, no press, no book, just two social posts, one of them
    //      unreadable. The Bonde board already shipped FABRICATED quotes
    //      attributed to a named investor once. His name stays off this one.
    //   2. NO FITTED THRESHOLD. Every cut is definitional or sector-relative.
    //      The moment a "ROCE > 20" appears, the board is claiming a number
    //      nobody measured.
    checks: () => {
      const errs = [];
      const cr = read('../backend/sepa/capital_returns.py');
      const cq = read('../backend/growth/capital_quality.py');
      const files = {
        'capital_returns.py': cr,
        'capital_quality.py': cq,
        'capitalQuality.ts': read('src/lib/capitalQuality.ts'),
        'CapitalQualityChips.tsx': read('src/components/CapitalQualityChips.tsx'),
        'newFeatures.ts': read('src/lib/newFeatures.ts'),
      };

      // 1 — the attribution must not reach any surface. newFeatures.ts is
      // exempt ONLY because its card is where the negative finding is
      // reported to him; it must say it could NOT be verified.
      for (const [name, src] of Object.entries(files)) {
        if (name === 'newFeatures.ts') continue;
        if (/ghee|jhunjhunwala|junjunwala|big bull/i.test(src)) {
          errs.push(`${name} carries an attribution that could NOT be sourced`);
        }
      }
      const nf = files['newFeatures.ts'];
      if (/jhunjhunwala/i.test(nf) && !/could not verify|not verify/i.test(nf)) {
        errs.push('the \u2728 card names him without saying the attribution is UNVERIFIED');
      }

      // 2 — the sanity bound ships OFF, so the package invents no number
      if (!/MIN_DENOMINATOR_ASSET_SHARE\s*=\s*0\.0\b/.test(cr)) {
        errs.push('MIN_DENOMINATOR_ASSET_SHARE must ship at 0.0 \u2014 it is the one '
          + 'non-definitional number in the package and nobody measured a value for it');
      }
      // 3 — the peer floor is the app's OWN floor, not a new one
      if (!/MIN_PEERS\s*=\s*20\b/.test(cq) || !/MIN_SECTOR_N/.test(cq)) {
        errs.push('MIN_PEERS must be 20 AND cite longterm.MIN_SECTOR_N, not a fresh number');
      }
      // 4 — no fitted cut anywhere in the read
      for (const m of cq.matchAll(/^(?!\s*#).*?(roce|roic|roe|capex|fcf)[a-z_]*\s*[<>]=?\s*(-?\d+(\.\d+)?)/gim)) {
        if (!/[<>]=?\s*0(\.0*)?\s*$/.test(m[0])) {
          errs.push(`a FITTED cut survives in capital_quality.py: "${m[0].trim()}" `
            + '\u2014 only definitional (vs 0) or sector-relative cuts are allowed');
        }
      }
      // 5 — it must never claim an edge
      if (!/\bMEASURED\s*=\s*False\b/.test(cq) || !/\bMEASURED\s*=\s*False\b/.test(cr)) {
        errs.push('both modules must ship MEASURED = False \u2014 no study exists');
      }
      // 6 — it gates and sorts nothing (Rule #10)
      if (/SORT_KEYS[^\n]*capital_quality|capital_quality[^\n]*SORT_KEYS/.test(cq + files['capitalQuality.ts'])) {
        errs.push('capital quality entered a sort key \u2014 it is a screen, not a ranking');
      }
      // 7 — UNKNOWN is not a failure
      if (!/unknown/i.test(files['capitalQuality.ts'])) {
        errs.push('the FE must distinguish UNKNOWN from a failed component');
      }
      if (!/id: 'growth-capital-quality-2026-09-22'/.test(nf)) {
        errs.push('capital quality needs its \u2728 entry');
      }
      return errs;
    },
  },
  {
    name: '\u{1F48E} the quality chips hide nothing silently, and ship OFF (2026-09-22)',
    file: 'src/components/ExplosiveGrowth.tsx',
    // Measured on the live board 2026-09-22: stacking every definitional cut
    // leaves 2 of 21 (NVDA, TER); "no dilution" alone takes 11 -> 2. The same
    // shape as the `debt === 0` filter that returned ZERO of 29 rows and is
    // why `debtTier` defaults to "net cash". A chip that empties the board
    // without saying so reads as a broken board.
    checks: (src) => {
      const errs = [];
      const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
      const chips = read('src/components/CapitalQualityChips.tsx');

      // every chip OFF on first paint
      if (!/useState<ReadonlySet<string>>\(\(\)\s*=>\s*new Set<string>\(\)\)/.test(code)) {
        errs.push('the quality chips must ship with an EMPTY set \u2014 any default ON '
          + 'hides rows on first paint on a 21-name board');
      }
      // the hidden count and its reasons must be rendered
      if (!/CapitalQualityHidden/.test(code)) errs.push('no hidden-count line is rendered');
      if (!/CapitalQualityNote/.test(code)) errs.push('the not-measured note is not rendered');
      // the count must be over the DRAWN rows, not the whole served board
      if (!/visibleComponentCounts|visibleCounts/.test(code)) {
        errs.push('the chip counts must be measured over the rows actually on screen \u2014 '
          + 'a count over the whole board promises hides the other filters already made');
      }
      // un-hide PER REASON (a per-key button that toggles that one question
      // back off), plus a clear-all. Not a single all-or-nothing reset.
      if (!/hiddenByKey\[c\.key\]/.test(chips) || !/onClick=\{\(\)\s*=>\s*onToggle\(c\.key\)\}/.test(chips)) {
        errs.push('each hidden reason must be individually un-hideable \u2014 a per-key '
          + 'control that names its own row count, not one all-or-nothing reset');
      }
      if (!/onClear/.test(chips)) errs.push('no clear-all alongside the per-reason un-hide');
      return errs;
    },
  },

  /* ── 🔥 Hottest: a live group row states its cohort and never blends ──────
   *
   * Ajay 2026-09-23: "I think the sector rotation is wrong.. Its actualy
   * rotating this morning I wanna see live rotattion." The group rows now go
   * live with the names. Two ways that can quietly go wrong, and both are
   * exactly the reason the rows sat on the close for a week:
   *
   *   1. BLENDING. A median over the live members PLUS the last-close members
   *      describes no session at all. The row must filter on `d1_live_n` and
   *      the screen must mark a row that has no live member.
   *   2. DIFFERENCING TWO COHORTS. `rel_1d_close` is a median over a DIFFERENT
   *      set of names (for a sector, the rotation grid's 40-name sample) than
   *      `rel_1d`. `d1_live_close` is the same-cohort close and is the ONLY
   *      close the tooltip may quote.
   */
  {
    name: 'hottest live group rows: cohort stated, never blended, never differenced',
    file: 'src/components/HottestSectors.tsx',
    checks: (src) => {
      const errs = [];
      const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

      // the tooltip quotes the SAME-COHORT close, never the row's other one
      const cell = code.slice(code.indexOf('export function dayCell'),
                              code.indexOf('export function asOfLine'));
      if (!cell) { errs.push('dayCell not found'); return errs; }
      if (!/was = r\.d1_live_close/.test(cell)) {
        errs.push('the live group tooltip must read `d1_live_close` \u2014 the close over the '
          + 'SAME members. `rel_1d_close` is a median over a different cohort.');
      }
      if (/groupLive[\s\S]{0,400}rel_1d_close/.test(cell)) {
        errs.push('`rel_1d_close` must not reach the live group sentence \u2014 for a sector '
          + 'it is the rotation grid\u2019s 40-name sample, not these names');
      }
      // the two close numbers are never subtracted from anything on this screen
      if (/(rel_1d\s*[-+]\s*rel_1d_close|rel_1d_close\s*[-+]\s*rel_1d|d1_live_close\s*[-+]\s*r?\.?rel_1d)/.test(code)) {
        errs.push('two group medians over different cohorts are being differenced \u2014 '
          + 'a delta between them is a number no set of names produced');
      }
      // the denominator is printed only when the cohort is partial
      if (!/n\s*<\s*of/.test(cell)) {
        errs.push('`partial` must be `n < of` \u2014 a live median over FEWER members than '
          + 'the row has must print its denominator');
      }
      if (!/d1_live_n\}\/\{r\.d1_live_of/.test(code)) {
        errs.push('the partial denominator (n/of) never reaches the cell');
      }
      // a row with no live member is still MARKED, exactly as before
      if (!/const marked = boardLive && !rowLive/.test(cell)) {
        errs.push('a group row with no live member must still be marked \u201clast close\u201d '
          + '\u2014 a live header over a close number is the bug this replaced');
      }
      // and nothing here decides the basis by reading prose
      if (/group_basis\s*(===|!==)\s*['\`"](?!live|close)/.test(code)) {
        errs.push('`group_basis` is a token (live|close); never string-match a sentence');
      }
      return errs;
    },
  },
  {
    name: '⌘-click opens a Chart Maps tab in a new browser tab — every tab is a LINK (2026-09-24)',
    file: 'src/pages/ChartMaps.tsx',
    // Ajay 2026-09-24: "add Command clicks to the Tabs in chart maps so I can
    // open new tabs.. Of that specific Section". The tabs were <button>s, and a
    // button has no address: ⌘-click, middle-click and "Open in new tab" all
    // did nothing. A refactor back to a button — or an onClick that swallows
    // every click — would silently take this away and every render test would
    // still pass, because jsdom does not open tabs.
    checks: (src) => {
      const errs = [];
      const strip = src.slice(src.indexOf('<div className="cm-tabs" role="tablist">'));
      const head = strip.slice(0, 900);
      if (!head) return ['the cm-tabs strip could not be found'];
      if (!/<a key=\{t\} role="tab"/.test(head)) {
        errs.push('each Chart Maps tab must be an <a role="tab"> — a <button> has no address to open in a new tab');
      }
      if (!/href=\{`\?\$\{tabSearch\(params, t\)\}`\}/.test(head)) {
        errs.push('the tab href must come from tabSearch(params, t) — the SAME address setTab switches to, so a click and a ⌘-click cannot land on two boards');
      }
      if (!/if \(!isPlainLeftClick\(e\)\) return;/.test(head)) {
        errs.push('the tab onClick must hand every modified / non-primary click back to the browser (isPlainLeftClick) — intercepting them is how a link becomes a button again');
      }
      if (!/e\.preventDefault\(\);\s*setTab\(t\);/.test(head)) {
        errs.push('a PLAIN click must still preventDefault and switch in place — otherwise every tab click is a full page reload');
      }
      const lib = read('src/lib/chartMaps.ts');
      if (!/const setTab = \(t: CmTab\) => \{\s*setParams\(new URLSearchParams\(tabSearch\(params, t\)\)/.test(src)) {
        errs.push('setTab must build its query with tabSearch — one owner for a tab address');
      }
      if (!/return e\.button === 0 && !e\.metaKey && !e\.ctrlKey && !e\.shiftKey && !e\.altKey;/.test(lib)) {
        errs.push('isPlainLeftClick must treat ⌘, Ctrl, ⇧, ⌥ and any non-primary button as the browser’s click');
      }
      return errs;
    },
  },
  {
    name: '🗺️ StockTitan heatmap: every sector maps to StockTitan’s own name, and nothing is guessed (2026-09-24)',
    file: 'src/lib/rotation.ts',
    // StockTitan matches a sector EXACTLY and a miss quietly draws the whole
    // S&P 500 map — a link that looks like it worked. The eleven GICS names
    // were read off its own payload (window.__TREEMAP_API_DATA__) on
    // 2026-09-24. A new sector, a typo, or a "helpful" fuzzy fallback would all
    // ship a wrong link that no render test notices.
    checks: (src) => {
      const errs = [];
      const THEIRS = ['Health Care', 'Information Technology', 'Consumer Discretionary',
        'Financials', 'Consumer Staples', 'Utilities', 'Materials', 'Industrials',
        'Real Estate', 'Energy', 'Communication Services'];
      const table = src.slice(src.indexOf('export const STOCKTITAN_SECTOR'),
                              src.indexOf('export function stockTitanHeatmapUrl'));
      if (!table) return ['STOCKTITAN_SECTOR could not be found'];
      const pairs = [...table.matchAll(/'([^']+)':\s*'([^']+)'/g)].map((m) => m[2]);
      if (pairs.length !== 11) errs.push(`STOCKTITAN_SECTOR must map exactly 11 sectors, found ${pairs.length}`);
      for (const t of THEIRS) {
        if (!pairs.includes(t)) errs.push(`STOCKTITAN_SECTOR never maps to StockTitan’s "${t}"`);
      }
      for (const v of pairs) {
        if (!THEIRS.includes(v)) errs.push(`"${v}" is not a StockTitan sector name — the link would open the whole map`);
      }
      if (!/Object\.freeze\(/.test(table)) errs.push('STOCKTITAN_SECTOR must be frozen');
      const fn = src.slice(src.indexOf('export function stockTitanHeatmapUrl'));
      if (!/if \(!theirs\) return null;/.test(fn)) {
        errs.push('an unmapped sector must get NO link (return null) — never a guessed one');
      }
      if (!/encodeURIComponent\(ind\)/.test(fn)) {
        errs.push('the industry must be encodeURIComponent-ed — "Oil & Gas E&P" carries a literal & that splits the hash');
      }
      const page = read('src/pages/Rotation.tsx');
      if (!/target="_blank" rel="noopener noreferrer"/.test(page)) {
        errs.push('the heatmap links must open in a new tab without handing StockTitan window.opener');
      }
      if (!/<Table title="Sectors" rows=\{data\.sectors\} showEtf heatmap/.test(page)) {
        errs.push('the Sectors table must ask for heatmap links');
      }
      if (/<Table title="(Your themes|Safe havens)"[^>]*\bheatmap\b/.test(page)) {
        errs.push('themes and havens have no StockTitan sector — they must not ask for heatmap links');
      }
      return errs;
    },
  },
  {
    name: '📰 Chart Maps carries the News tab — the market word is the GAUGE’s, mapped once, and the sector words say what they measure (2026-09-24)',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-24: "build me a news tab in chartmaps to give me a bullish
    // market or bearsish market and also pull Macro calendar that has T1 and T2
    // tier events in to this tab consider in to news. If bullish or beaish I
    // need to whcih sectors are bullish or which hotsectors are bearish. In a
    // table." What must not drift silently: (1) the market word is the Market
    // Gauge's own state, mapped to bullish/mixed/bearish in exactly ONE place on
    // the server — never a second score, never re-derived in the browser;
    // (2) the tab carries its own measurements WITH their intervals and names
    // the 5-session heat UNMEASURED; (3) nothing on it is a forecast.
    checks: (src) => {
      const errs = [];
      const tabs = /export const CM_TABS: CmTab\[\] = \[([\s\S]*?)\];/.exec(src);
      if (!tabs || !/'news'/.test(tabs[1])) errs.push("CM_TABS no longer lists 'news'");
      if (!/t !== 'news'/.test(src)) errs.push('isBoardTab must exclude news — it has its own endpoint and renderer');
      const at = src.indexOf('\n  news: {');
      const meta = at < 0 ? '' : src.slice(at, src.indexOf('\n  },', at));
      if (!meta) {
        errs.push('TAB_META has no news entry');
      } else {
        for (const must of ['−0.57pp', '−2.55pp', 'UNMEASURED', 'not a forecast', 'last close']) {
          if (!meta.includes(must)) errs.push(`the News blurb must carry "${must}" — a measured claim ships with its interval, and the heat word it prints is unmeasured`);
        }
        if (/\bbounce\b/i.test(meta)) errs.push('the News blurb says "bounce" — reversal, never bounce, on any surface he reads');
        if (/2026-09-24: daily/.test(meta)) errs.push('the News blurb types a live gauge reading — the numbers are SERVED, never written into the copy');
      }
      const page = read('src/pages/ChartMaps.tsx');
      // a comment may sit between the branch and the board; a `) :` would mean
      // the next branch started, so the match is bounded by it
      if (!/tab === 'news' \? \((?:(?!\) :)[\s\S]){0,1200}<NewsTabBoard \/>/.test(page)) {
        errs.push('ChartMaps must mount <NewsTabBoard /> on tab === news');
      }
      // ONE place maps gauge state → word, and it is the server.
      const be = read('../backend/chart_maps/news_tab.py');
      if (!be.includes('MARKET_WORD = {"constructive": "bullish", "caution": "mixed", "risk_off": "bearish"}')) {
        errs.push('news_tab.py must carry the one MARKET_WORD map, verbatim — the market word is the gauge’s state, mapped once');
      }
      if (!/LEG_BUDGET_SEC/.test(be) || /MACRO_BUDGET_SEC/.test(be)) {
        errs.push('news_tab.py must budget all four legs with the ONE LEG_BUDGET_SEC');
      }
      for (const rel of ['src/lib/newsTab.ts', 'src/components/NewsTabBoard.tsx']) {
        const f = read(rel);
        if (/['"](constructive|risk_off)['"]/.test(f)) {
          errs.push(`${rel} names a gauge state in a quoted literal — the browser must not re-derive the market word`);
        }
      }
      const cmDir = join(FRONTEND_ROOT, '..', 'backend', 'chart_maps');
      for (const f of readdirSync(cmDir)) {
        if (!f.endsWith('.py') || f === 'news_tab.py') continue;
        if (/"risk_off"/.test(readFileSync(join(cmDir, f), 'utf8'))) {
          errs.push(`backend/chart_maps/${f} names "risk_off" — the gauge-state word map lives in news_tab.py only`);
        }
      }
      const api = read('../backend/chart_maps/api.py');
      if (!/async def chart_maps_news\(\):/.test(api)) {
        errs.push('GET /chart-maps/news must take NO parameters — the tab is one fixed read (14 days, close basis)');
      }
      const board = read('src/components/NewsTabBoard.tsx');
      if (!/stockTitanHeatmapUrl/.test(board)) errs.push('NewsTabBoard must link each sector to its StockTitan heatmap via stockTitanHeatmapUrl');
      if (!/dayTagChipLabel/.test(board)) errs.push('NewsTabBoard must reuse the 🔥 Hottest day-tag chip (dayTagChipLabel) — one bull/bear-case renderer');
      if (!read('src/lib/newFeatures.ts').includes("'chart-maps-news-tab-2026-09-24'")) {
        errs.push('the News tab has no ✨ NEW entry');
      }
      // 🧠 Model read (2026-09-24, "You can use the abliterated model we have via
      // hermes. For this tab"): the LOCAL model only, no Hermes agent turn (a turn
      // carries a shell; headlines are untrusted text), prose refused when it
      // writes a number it was not handed, never run on the request.
      const mr = read('../backend/chart_maps/news_model_read.py');
      const mrCode = mr.split('"""').slice(2).join('"""');
      if (!/^PROVIDER = "local"$/m.test(mr)) errs.push('news_model_read.py must pin PROVIDER = "local" — he named the abliterated model');
      if (/["'](anthropic|auto)["']/.test(mrCode)) errs.push('news_model_read.py names a hosted provider — the model read is local only');
      if (/ollama_chat|hermes/i.test(mrCode)) errs.push('news_model_read.py must not open a Hermes agent turn — same model, no tools');
      if (!/stray_numbers\(bull \+ " " \+ bear, f\)/.test(mr)) errs.push('clean() must refuse a read that writes a number not in its facts');
      if (!/threading\.Thread\(target=_run/.test(mr) || !/_LOCK\.acquire\(blocking=False\)/.test(mr)) {
        errs.push('the model must run only in the single-flight background thread, never on the request');
      }
      if (!/news_model_read\.served, body\), LEG_BUDGET_SEC/.test(be)) {
        errs.push('news_tab.build must read the stored model read under the ONE LEG_BUDGET_SEC');
      }
      if (!/<ModelReadBlock b=\{payload\.model_read\} \/>/.test(board)) errs.push('NewsTabBoard must render the 🧠 model read');
      if (board.indexOf('nt-section-model') < board.indexOf('nt-section-verdict')) {
        errs.push('the 🧠 model read must sit UNDER the gauge’s market read, never above it');
      }
      if (!read('src/lib/newFeatures.ts').includes("'chart-maps-news-model-read-2026-09-24'")) {
        errs.push('the 🧠 model read has no ✨ NEW entry');
      }
      return errs;
    },
  },
  {
    name: '🌀 AMD raids on the Support tile — closed bars + provisional today, display only (2026-09-24)',
    file: 'src/components/PatternChart.tsx',
    // Ajay 2026-09-24: "Show all the possible raids, past ones too and todays
    // too." FRONTEND FILES ONLY — the backend strings (the one raid test,
    // the closed-bar split, the route wiring) are pinned by the backend tests
    // in tests/test_amd_all_raids_2026_09_24.py, so this goes green on its own.
    // Display only: one muted chip after the verdict, the list in a drill-in,
    // numbered circles read from the SAME served array as the list.
    checks: (src) => {
      const errs = [];
      if (!/<AmdRaidsChip\b/.test(src)) errs.push('PatternChart must mount <AmdRaidsChip — the one chip that lists every raid');
      if (!/amdRaidMarks\(/.test(src)) errs.push('PatternChart must place the circles with amdRaidMarks( — list and circles from one array');
      if (!/occupiedFromMarkers\(/.test(src)) errs.push('PatternChart must pass occupiedFromMarkers( so a circle never prints on an A / ▲ glyph');
      const badges = src.indexOf('(tile.badges || []).map(');
      const chipAt = src.indexOf('<AmdRaidsChip');
      const watchAt = src.indexOf('<SignalWatchButton');
      if (!(badges >= 0 && chipAt > badges && chipAt < watchAt)) {
        errs.push('the raids chip must sit right after the verdict badges and before + Signals (Rule #5 placement)');
      }
      const chip = read('src/components/AmdRaidsChip.tsx');
      if (!/\{chip\.text\}/.test(chip)) errs.push('AmdRaidsChip must print the SERVED chip.text');
      if (/raids\.length/.test(chip)) errs.push('AmdRaidsChip must not count raids itself — the served chip counts chains');
      if (!/cm-badge-muted/.test(chip) || /cm-badge-(good|warn)/.test(chip)) {
        errs.push('AmdRaidsChip must be muted only — the read is MEASURED INVERTED');
      }
      if (!/stopPropagation\(\)/.test(chip) || !/preventDefault\(\)/.test(chip)) {
        errs.push('AmdRaidsChip must preventDefault + stopPropagation — the whole tile is a <Link>');
      }
      const lib = read('src/lib/amdRaids.ts');
      if (!/draw_dirs/.test(lib)) errs.push('amdRaids.ts must filter the circles on the served draw_dirs');
      for (const [rel, f] of [['src/lib/amdRaids.ts', lib], ['src/components/AmdRaidsChip.tsx', chip]]) {
        if (/bounce/i.test(f)) errs.push(`${rel} says "bounce" — surfaces he reads say reversal`);
      }
      const ov = read('src/lib/chartOverlays.ts');
      if (!/amd_raids:\s*hidden\.has\('amd'\)/.test(ov)) {
        errs.push("filterTile must drop amd_raids beside hidden.has('amd') — the AMD box governs the raids too");
      }
      const nf = read('src/lib/newFeatures.ts');
      const at = nf.indexOf("'amd-all-raids-2026-09-24'");
      if (at < 0) {
        errs.push('the AMD raids feature has no ✨ NEW entry');
      } else {
        const entry = nf.slice(at, nf.indexOf('addedAt', at));
        if (!entry.includes('Show all the possible raids, past ones too and todays too.')) errs.push('the ✨ entry must quote his words verbatim');
        if (!/display only/i.test(entry)) errs.push('the ✨ entry must say display only');
        if (!entry.includes('INVERTED') || !entry.includes('−4.2pp')) errs.push('the ✨ entry must name the measured INVERTED result (−4.2pp)');
      }
      return errs;
    },
  },
  // ── ⚡ Momentum burst (Ajay 2026-09-24: "Can you add this as a check box in
  //    our filters please.." → "Pin + badge, hide nothing") ──────────────────
  {
    name: '⚡ momentum-burst pin (2026-09-24): prop-fed badge, client-side stable pin, hides nothing, every non-board tab exempt in writing',
    file: 'src/lib/momentumBurst.ts',
    // The read is SERVED (backend/supply_demand/momentum_burst.py). The teeth:
    //   * every non-board Chart Maps tab is exempt IN WRITING — an absent pin and
    //     a dropped one look identical from here;
    //   * no threshold, no rounding and no numeric comparison in the lib or the
    //     chip — a TSX copy of the rule is a second engine that drifts;
    //   * the ticker page's weekly figure is IMPORTED into the disambiguation
    //     line, never typed;
    //   * the state is `?burst=1` and nothing else: not in boardQuery (toggling
    //     never refetches), never in localStorage;
    //   * "reversal", never "bounce", on the three files he reads.
    checks: (src) => {
      const errs = [];
      const cm = read('src/lib/chartMaps.ts');
      const tabs = parseCmTabs(cm);
      if (!tabs) return ['CM_TABS declaration not found'];

      /* 1. BURST_EXEMPT keys == the non-board tabs, every reason written. */
      const m = /export const BURST_EXEMPT[^=]*=\s*\{([\s\S]*?)\n\};/.exec(src);
      if (!m) {
        errs.push('BURST_EXEMPT declaration not found in lib/momentumBurst.ts');
      } else {
        const body = m[1].replace(/\/\/[^\n]*/g, '');
        const keys = [...body.matchAll(/^\s*([a-z_]+)\s*:/gm)].map((x) => x[1]).sort();
        // WIDENED 2026-10-16 — 🕯️ doji_sweep is a board tab after 🚩
        const nonBoard = tabs.filter((t) => !/^(zones|deep_demand|quick_bounce|breaking|gabbar|vcp|topping|ict|undervalue|zero_dte|earnings|winners|keltner|amd|ipo|key_levels|dual_momentum|ath|resiliency|fallen|drop10|high_beta|doji_sweep)$/.test(t)).sort();
        if (keys.join(',') !== nonBoard.join(',')) {
          errs.push(`BURST_EXEMPT keys [${keys.join(', ')}] != the non-board CM_TABS [${nonBoard.join(', ')}] — a board tab must get the pin, a non-board tab must say why not`);
        }
        for (const line of body.split('\n')) {
          const kv = /^\s*([a-z_]+)\s*:\s*(.*?),?\s*$/.exec(line);
          if (!kv) continue;
          if (/^''$|^""$/.test(kv[2]) || !kv[2]) errs.push(`BURST_EXEMPT.${kv[1]} has an empty reason`);
        }
        if (!/const ROW_BOARD\s*=\s*\n?\s*"[^"]+"/.test(src)) {
          errs.push('the row-board exemption reason (ROW_BOARD) must be a non-empty string');
        }
      }

      /* 2. No maths in the lib or the chip. */
      const chip = read('src/components/MomentumBurstChip.tsx');
      for (const [rel, f] of [['src/lib/momentumBurst.ts', src], ['src/components/MomentumBurstChip.tsx', chip]]) {
        if (f.includes('1.5')) errs.push(`${rel} types 1.5 — the thresholds live in momentum_burst.py`);
        if (/\b8(\.0)?\s*%/.test(f)) errs.push(`${rel} types the ticker page's weekly figure — import BONDE_MOM_BURST_1W_PCT`);
        if (/toFixed/.test(f)) errs.push(`${rel} rounds a number — the served badge already carries the digits`);
        if (/\d+(\.\d+)?\s*(?:<=|>=|<|>)|(?:<=|>=|<|>)\s*\d/.test(f)) {
          errs.push(`${rel} compares a number — the verdict is served by momentum_burst.py`);
        }
      }
      if (!/import\s*\{[^}]*\bBONDE_MOM_BURST_1W_PCT\b[^}]*\}\s*from\s*'\.\/cheetahVerdict'/.test(src)) {
        errs.push("lib/momentumBurst.ts must import BONDE_MOM_BURST_1W_PCT from './cheetahVerdict'");
      }
      if (/\bfetch\s*\(/.test(chip) || /useEffect|useState/.test(chip)) {
        errs.push('MomentumBurstChip must be PROP-FED — no fetch, no effect, no state');
      }

      /* 3. The one tile renderer mounts it off the page's prop. */
      const tile = read('src/components/PatternChart.tsx');
      if (!/<MomentumBurstChip\s+read=\{burst\}/.test(tile)) {
        errs.push('PatternChart must render <MomentumBurstChip read={burst}> — the page hands the read down only while the box is ticked');
      }

      /* 4. The page: toggle, pin, note, URL key — and nothing on the wire. */
      const page = read('src/pages/ChartMaps.tsx');
      for (const [re, msg] of [
        [/<MomentumBurstToggle\s/, 'ChartMaps must mount <MomentumBurstToggle>'],
        [/pinBurst\(/, 'ChartMaps must order the grid through pinBurst() — the stable partition'],
        [/\{burstPin\.rows\.map\(/, 'ChartMaps must RENDER burstPin.rows — computing the pin and drawing tilePart.rows would pin nothing'],
        [/burst=\{burstOn \? \(t\.burst \?\? null\) : null\}/, 'the ⚡ badge must reach a tile only while the box is ticked — burst={burstOn ? (t.burst ?? null) : null}'],
        [/burst_note/, 'ChartMaps must print the SERVED burst_note'],
        [/BURST_PARAM/, 'ChartMaps must read the state from BURST_PARAM (?burst=1)'],
      ]) {
        if (!re.test(page)) errs.push(msg);
      }
      const bq = /export function boardQuery\([\s\S]*?\n\}/.exec(cm);
      if (!bq) errs.push('boardQuery not found in lib/chartMaps.ts');
      else if (/burst/i.test(bq[0])) errs.push('boardQuery must not carry burst — the pin is client-side and toggling never refetches');
      for (const line of page.split('\n')) {
        if (/localStorage/.test(line) && /burst/i.test(line)) {
          errs.push('the ⚡ state must live in the URL only — no localStorage');
          break;
        }
      }

      /* 5. The ✨ entry quotes the runway line and says UNMEASURED. */
      const nf = read('src/lib/newFeatures.ts');
      const at = nf.indexOf("'momentum-burst-2026-09-24'");
      if (at < 0) {
        errs.push('the ⚡ momentum burst has no ✨ NEW entry');
      } else {
        const entry = nf.slice(at, nf.indexOf('addedAt', at));
        if (!entry.includes('UNMEASURED')) errs.push('the ⚡ ✨ entry must say UNMEASURED');
        if (!entry.includes('not enough runway')) errs.push('the ⚡ ✨ entry must quote "not enough runway"');
      }

      /* 6. Every class ships a rule. */
      const css = read('src/styles.css');
      for (const c of ['cm-badge-burst', 'mb-toggle', 'mb-count', 'mb-unknown', 'mb-behind']) {
        if (!new RegExp('\\.' + c + '(?![\\w-])').test(css)) {
          errs.push(`.${c} has no CSS rule — the ⚡ control would ship unstyled`);
        }
      }

      /* 7. Reversal, never bounce, on the three files he reads. */
      for (const rel of ['src/lib/momentumBurst.ts', 'src/components/MomentumBurstChip.tsx',
                         'src/components/MomentumBurstToggle.tsx']) {
        if (/bounce/i.test(read(rel))) errs.push(`${rel} says "bounce" — surfaces he reads say reversal`);
      }
      return errs;
    },
  },
  // ── 📋 The Chart Maps card as an ENTRY LADDER (Ajay 2026-09-24: "I want
  //    them to categorized in a good way so I have enough info for entry of a
  //    stock." → 2026-09-25 "Yes, build the ladder") ─────────────────────────
  {
    name: '📋 the Chart Maps card reads as an entry ladder — organised, then folded, nothing removed (2026-09-25)',
    file: 'src/components/PatternChart.tsx',
    // The teeth:
    //   * the rungs render in the entry order, the chart between PRICE and PLAN;
    //   * the study run (verdicts + raids chip) sits in TIMING, never the fold;
    //   * the fold is HIDDEN, never unmounted, and its button cannot follow the
    //     tile <Link>;
    //   * the classifier is strings only — no number is parsed, rounded or
    //     scaled, and nothing says "bounce";
    //   * every new class ships a rule, and no chip rule cuts text mid-word;
    //   * the Trade-lines box decides what is DRAWN, never what PLAN prints;
    //   * ⊞ follows the 🔥 Hottest persistence convention; the wrappers skip the
    //     chips they already print.
    checks: (src) => {
      const errs = [];
      if (!/import\s*\{[^}]*\bcardLadder\b[^}]*\}\s*from\s*'\.\.\/lib\/cardLadder'/.test(src)) {
        errs.push('PatternChart must import cardLadder from ../lib/cardLadder — one classifier for every card');
      }
      const ret = src.indexOf('<Link');
      const body = ret >= 0 ? src.slice(ret) : '';
      const at = (needle) => body.indexOf(needle);
      const seq = ['cm-rung-entry', 'cm-rung-price', '<svg', 'cm-rung-plan', 'cm-rung-timing', 'className="cm-more"'];
      const pos = seq.map(at);
      if (pos.some((p) => p < 0)) {
        errs.push(`the ladder is missing a rung: ${seq.filter((_, i) => pos[i] < 0).join(', ')}`);
      } else if (!pos.every((p, i) => i === 0 || p > pos[i - 1])) {
        errs.push('the rungs must render ENTRY < PRICE < chart < PLAN < TIMING < ▸ more, in that source order');
      }
      const run = at('{studyRun}');
      if (!(run > at('cm-rung-timing') && run < at('className="cm-more"'))) {
        errs.push('{studyRun} must render inside TIMING, before the fold — the raids chip never lands in ▸ more');
      }
      if (!/className="cm-more"\s+hidden=\{/.test(body)) errs.push('the fold must use hidden={…} so every folded read stays in the DOM');
      if (/\{more\s*&&/.test(src)) errs.push('the fold must never be a conditional render ({more && …}) — getByText pins would lose folded reads');
      const btn = /<button[^>]*cm-badge-more[\s\S]*?<\/button>/.exec(body);
      if (!btn) {
        errs.push('the ▸ more button (cm-badge-more) is missing');
      } else {
        for (const [re, msg] of [[/aria-expanded=/, 'aria-expanded'], [/preventDefault\(\)/, 'preventDefault()'],
                                 [/stopPropagation\(\)/, 'stopPropagation()']]) {
          if (!re.test(btn[0])) errs.push(`the ▸ more button needs ${msg} — the whole tile is a <Link>`);
        }
      }

      const lib = read('src/lib/cardLadder.ts');
      for (const [re, msg] of [[/toFixed/, 'toFixed'], [/\*\s*100\b/, '*100'], [/\/\s*100\b/, '/100'],
                               [/parseFloat/, 'parseFloat'], [/Number\(/, 'Number(']]) {
        if (re.test(lib)) errs.push(`lib/cardLadder.ts uses ${msg} — the classifier is strings only`);
      }
      if (/bounce/i.test(lib)) errs.push('lib/cardLadder.ts says "bounce" — surfaces he reads say reversal');

      const css = read('src/styles.css');
      for (const c of ['cm-rungs', 'cm-rung', 'cm-rung-tag', 'cm-rung-items', 'cm-rung-note', 'cm-approach',
                       'cm-approach-good', 'cm-approach-warn', 'cm-approach-muted', 'cm-more', 'cm-more-group',
                       'cm-badge-more', 'cm-badge-more-warn', 'cm-tile-ident', 'cm-tile-actions', 'cm-kv',
                       'cm-stat-wide']) {
        if (!new RegExp('\\.' + c + '(?![\\w-])').test(css)) errs.push(`.${c} has no CSS rule — jsdom loads no stylesheet, so only this catches it`);
      }
      const cssNc = css.replace(/\/\*[\s\S]*?\*\//g, '');
      for (const m of cssNc.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
        if (/\.cm-(badge|rung|more)/.test(m[1]) && /text-overflow\s*:\s*ellipsis/.test(m[2])) {
          errs.push(`${m[1].trim()} cuts text with an ellipsis — chips wrap at spaces, never mid-word`);
        }
      }

      const ov = read('src/lib/chartOverlays.ts');
      if (!/plan_lines:/.test(ov) || !/isPlanLine\(/.test(ov)) {
        errs.push('filterTile must copy the plan lines into plan_lines — the Trade-lines box decides what is DRAWN, not what PLAN prints');
      }
      if (!/export function pxText\(/.test(read('src/lib/chartMaps.ts'))) {
        errs.push('lib/chartMaps.ts must export pxText — one price format for the plan row and the now-line');
      }

      const page = read('src/pages/ChartMaps.tsx');
      if (!/CM_MORE_EXPAND_KEY\s*=\s*'cm\.expandMore'/.test(lib)) {
        errs.push('⊞ must persist under the board’s own key (the 🔥 Hottest convention)');
      }
      if (!/readMoreExpandPref\(\)/.test(page) || !/writeMoreExpandPref\(/.test(page) || !/expandAll=\{moreAll\}/.test(page)) {
        errs.push('ChartMaps must read / write the ⊞ preference and hand it to every grid card (expandAll={moreAll})');
      }
      for (const [rel, konst] of [['src/components/SupportLevels.tsx', 'SUPPORT_OUTER_CHIPS'],
                                  ['src/components/PotusBoard.tsx', 'POTUS_OUTER_CHIPS'],
                                  ['src/components/EmaFramesBoard.tsx', 'EMA_OUTER_CHIPS']]) {
        /* 🎯 / 🧨 differ by source (the head reads the room endpoint, the tile
         * its own served read), so the list goes through outerChipsFor, which
         * skips them only on identical chip text (repair 2026-09-25). */
        if (!new RegExp('outerChips=\\{outerChipsFor\\(' + konst + ',').test(read(rel))) {
          errs.push(`${rel} prints chips beside the tile — it must pass outerChips={outerChipsFor(${konst}, …)} so each prints once and 🎯/🧨 skip only on equal text`);
        }
      }

      const nf = read('src/lib/newFeatures.ts');
      const idAt = nf.indexOf("'card-entry-ladder-2026-09-25'");
      if (idAt < 0) {
        errs.push('the entry ladder has no ✨ NEW entry (card-entry-ladder-2026-09-25)');
      } else {
        const entry = nf.slice(idAt, nf.indexOf('addedAt', idAt));
        if (!entry.includes('nothing removed')) errs.push('the ✨ entry must say "nothing removed"');
        if (!entry.includes('I want them to categorized in a good way so I have enough info for entry of a stock.')) {
          errs.push('the ✨ entry must quote his words verbatim');
        }
        if (/bounce/i.test(entry)) errs.push('the ✨ entry says "bounce"');
      }
      return errs;
    },
  },
  {
    name: '🔑 key levels (2026-09-25): the ✨ entry stays, and toneColor paints the key tones (never the grid grey)',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-25: "With check box give it a brigh color in the chart." The
    // 2026-09-12 study overlays shipped with no toneColor case and every line
    // fell through to the grid grey ("Non of these are showing up"). The key
    // tones must never repeat that, and the ✨ entry must not be lost in a rebase.
    checks: (src) => {
      const errs = [];
      const fn = /export function toneColor\([\s\S]*?\n\}/.exec(src);
      if (!fn) {
        errs.push('lib/chartMaps.ts must export toneColor');
      } else {
        if (!/tone === 'key'(?![\w])/.test(fn[0])) errs.push("toneColor has no 'key' case — key levels would draw grid grey");
        if (!/tone === 'key_broken'/.test(fn[0])) errs.push("toneColor has no 'key_broken' case — a broken key level would draw grid grey");
        if (!/var\(--cm-key,/.test(fn[0])) errs.push('the key tones must paint var(--cm-key, …), the swatch the 🔑 checkbox shows');
      }
      const nf = read('src/lib/newFeatures.ts');
      const idAt = nf.indexOf("id: 'key-levels-2026-09-25'");
      if (idAt < 0) {
        errs.push("newFeatures.ts lost the ✨ entry id: 'key-levels-2026-09-25'");
      } else {
        const entry = nf.slice(idAt, nf.indexOf('addedAt', idAt));
        if (!entry.includes('UNMEASURED')) errs.push('the 🔑 ✨ entry must say UNMEASURED');
        if (/bounce/i.test(entry)) errs.push('the 🔑 ✨ entry says "bounce" — surfaces he reads say reversal');
      }
      return errs;
    },
  },
  {
    name: '🧭 Catalysts (2026-09-25): every ticker opens its Supply & Demand tab, the drawer stays behind 🔎',
    file: 'src/pages/Catalysts.tsx',
    // Ajay 2026-09-25: "Can you help make all the catalyst pages to be going to
    // Ticker supply and demand please?" Every sub-tab used to open the deep-dive
    // drawer on a ticker click. A revert to setDrillTicker on a list click, or a
    // ticker <button> without the tab, silently undoes it.
    checks: (src) => {
      const errs = [];
      if (!/export const CATALYST_TICKER_TAB = 'supply';/.test(src)) {
        errs.push("CATALYST_TICKER_TAB must stay 'supply'");
      }
      if (/onClickTicker/.test(src)) {
        errs.push('onClickTicker is back — list clicks must go through openSupply / CatTicker, not the drawer');
      }
      if (/onClick=\{\(\) => setDrillTicker\(/.test(src) || /onClick=\{\(t\) => setDrillTicker\(t\)\}/.test(src)) {
        errs.push('a list click opens the drawer again — only 🔎 and the deep-dive box may call setDrillTicker');
      }
      if (/className="cat-(pred-card__ticker|tl-event__ticker|tl-chip)"[^>]*onClick/.test(src)) {
        errs.push('a ticker is a <button> again — it must be a CatTicker <a> so ⌘-click keeps the tab');
      }
      const cat = /function CatTicker\([\s\S]*?\n\}\n/.exec(src);
      if (!cat || !/tab=\{CATALYST_TICKER_TAB\}/.test(cat[0])) {
        errs.push('CatTicker must pass tab={CATALYST_TICKER_TAB} to TickerLink');
      }
      if (!/openTickerWithModifier\(e, navigate, location, t, 'Catalysts', CATALYST_TICKER_TAB\)/.test(src)) {
        errs.push('openSupply must hand CATALYST_TICKER_TAB to openTickerWithModifier');
      }
      if ((src.match(/if \(!isInnerControl\(e\)\)/g) || []).length < 5) {
        errs.push('the card / row clicks (Now, Pre-market, accumulator, stale, volume strip) must skip inner controls');
      }
      const nf = read('src/lib/newFeatures.ts');
      if (!nf.includes("id: 'catalyst-links-supply-2026-09-25'")) {
        errs.push("newFeatures.ts lost the ✨ entry id: 'catalyst-links-supply-2026-09-25'");
      }
      return errs;
    },
  },
  {
    name: 'Tape rows carry a date stamp and auctions never read BUY/SELL (2026-09-27)',
    file: 'src/components/TapePanel.tsx',
    // Ajay 2026-09-27, on the ORCL Tape tab: "Can you add date stamps please to
    // the tape?" then "this is for oracle hoping this info is accurate". ORCL
    // 09-25's closing cross was listed five times as a BUY (cross + four
    // Official Close re-sends). The backend now labels auctions by condition
    // (orderflow/tape.py:print_kind); the panel must stamp every big-print,
    // burst and dark-block row with its date, render the auction label from
    // printSideView (never the raw side), and show the served excluded note.
    checks: (src) => {
      const errs = [];
      if (!/data-testid="tape-print-stamp">\{printStamp\(p, d\.et_date\)\}/.test(src)) errs.push('big-print rows must render printStamp(p, d.et_date)');
      if (!/data-testid="tape-burst-stamp">\{printStamp\(b, d\.et_date\)\}/.test(src)) errs.push('burst lines must render printStamp(b, d.et_date)');
      if (!/data-testid="tape-block-stamp"[\s\S]{0,80}\{printStamp\(\{ date_et: b\.date_et, time_et: b\.time/.test(src)) errs.push('dark-block rows must render printStamp with b.date_et');
      if (!/const sc = printSideView\(p\.side, p\.kind\);/.test(src)) errs.push('big-print side must come from printSideView(p.side, p.kind)');
      if (/SIDE_CHIP\[p\.side\]/.test(src)) errs.push('the raw SIDE_CHIP[p.side] lookup is back — an auction row would read BUY/SELL');
      if ((src.match(/data-testid="tape-excluded-note"/g) || []).length < 2) errs.push('the excluded note must render in both the prints and no-prints branches');
      if (!/const excludedNote = d\.tape\?\.excluded\?\.note;/.test(src)) errs.push('the excluded note must be the served d.tape.excluded.note, not FE-written');
      const lib = read('src/lib/orderflow.ts');
      for (const [k, v] of [['auction_open', 'OPEN AUCTION'], ['auction_close', 'CLOSE AUCTION'], ['auction_reopen', 'REOPEN AUCTION']]) {
        if (!lib.includes(`${k}: '${v}'`)) errs.push(`orderflow.ts must label ${k} as '${v}'`);
      }
      if (!/export function fmtTapeStamp\(/.test(lib)) errs.push('fmtTapeStamp is gone from lib/orderflow.ts');
      const py = read('../backend/orderflow/tape.py');
      if (!/^def print_kind\(/m.test(py)) errs.push('backend tape.py lost print_kind');
      if (!/"side": None,/.test(py)) errs.push('backend auction rows must be served with side None');
      return errs;
    },
  },
  {
    name: '🔑 Key Levels tab (2026-09-28): closest-first off the served block, UNMEASURED, never bounce',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-28: "Also create me tab for keylevel main. Sort them by
    // stocks that are near lower keylevels". The board is ranked on the server
    // (chart_maps/key_levels_tab.py) and the page prints its served header;
    // losing any of these links silently drops the tab or the UNMEASURED word.
    checks: (src) => {
      const errs = [];
      const tabs = parseCmTabs(src);
      if (!tabs || !tabs.includes('key_levels')) errs.push("CM_TABS must carry 'key_levels'");
      const meta = /\n  key_levels: \{\n    label: '([^']*)',\n    blurb: '((?:[^'\\]|\\.)*)',/.exec(src);
      if (!meta) {
        errs.push('TAB_META.key_levels (label + blurb) is missing');
      } else {
        if (!meta[2].includes('UNMEASURED')) errs.push('the TAB_META.key_levels blurb must say UNMEASURED');
        if (/bounce/i.test(meta[2])) errs.push('the TAB_META.key_levels blurb says "bounce" — surfaces he reads say reversal');
      }
      const page = read('src/pages/ChartMaps.tsx');
      if (!/tab === 'key_levels' && <KeyLevelsBoardNote/.test(page)) errs.push("ChartMaps.tsx must render <KeyLevelsBoardNote … /> on tab === 'key_levels'");
      if (!/data\?\.warming && tab !== 'key_levels' \?/.test(page)) errs.push('the generic (demand) warming branch must skip the key_levels tab');
      const board = read('../backend/chart_maps/board.py');
      if (!/elif t == "key_levels":/.test(board)) errs.push('board.py lost the elif t == "key_levels": dispatch');
      const tabsPy = /^TABS = \(([^)]*)\)/m.exec(board);
      if (!tabsPy || !/"key_levels"/.test(tabsPy[1])) errs.push('board.py TABS must carry "key_levels"');
      if (!/attach_key_levels\([^\n]*now=_ctx\.get\("now"\)/.test(board)) errs.push('board.py attach_key_levels must take now=_ctx.get("now") — one clock for the badge and the line');
      let klt = '';
      try { klt = read('../backend/chart_maps/key_levels_tab.py'); } catch { errs.push('backend/chart_maps/key_levels_tab.py is missing'); }
      if (klt) {
        if (!klt.includes('UNMEASURED')) errs.push('key_levels_tab.py must say UNMEASURED');
        if (!klt.includes('avg_dollar_vol')) errs.push('key_levels_tab.py must take turnover from quick_bounce.avg_dollar_vol (the house 50-bar mean)');
        // `quick_bounce` is a MODULE NAME (internal identifiers keep `bounce`,
        // cheetah-ops) — the tab imports its avg_dollar_vol. Any other
        // "bounc" is served wording and fails.
        if (/bounc/i.test(klt.replace(/quick_bounce/g, ''))) errs.push('key_levels_tab.py says "bounce"');
      }
      const ladder = read('src/lib/cardLadder.ts');
      const pp = /const PRICE_PREFIX = \[([^\]]*)\]/.exec(ladder);
      if (!pp || !/'\\u\{1F511\} '|'🔑 '/.test(pp[1])) errs.push('cardLadder PRICE_PREFIX must route the served 🔑 position pill to PRICE');
      const nf = read('src/lib/newFeatures.ts');
      const idAt = nf.indexOf("id: 'key-levels-tab-2026-09-28'");
      if (idAt < 0) {
        errs.push("newFeatures.ts lost the ✨ entry id: 'key-levels-tab-2026-09-28'");
      } else {
        const entry = nf.slice(idAt, nf.indexOf('\n    addedAt', idAt) + 80);
        if (!entry.includes('UNMEASURED')) errs.push('the 🔑 Key Levels ✨ entry must say UNMEASURED');
        if (/bounce/i.test(entry)) errs.push('the 🔑 Key Levels ✨ entry says "bounce"');
        if (!entry.includes("route: '/chart-maps?tab=key_levels'")) errs.push("the 🔑 Key Levels ✨ entry must route to '/chart-maps?tab=key_levels'");
      }
      return errs;
    },
  },
  {
    name: '🏎️ Dual Momentum tab (2026-09-29): the page engine + the ONE demand engine, toggle served, UNMEASURED, never bounce',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-29: "Can you pull these in to chart maps and add the demand
    // zones logic to these?" + "I want a toggle and also the check boxes we
    // have like AMD and supple and demand zones computing and also key levels".
    // The leaders come from sepa/dual_momentum (the /dual-momentum page's own
    // engine); the zones and the 🎯 gate read from the ONE demand engine. Any
    // of these links lost silently drops the tab, its gate read, its UNMEASURED
    // word or its 🏎️ rank chip.
    checks: (src) => {
      const errs = [];
      const tabs = parseCmTabs(src);
      if (!tabs || !tabs.includes('dual_momentum')) {
        errs.push("CM_TABS must carry 'dual_momentum'");
      } else if (tabs.indexOf('dual_momentum') !== tabs.indexOf('key_levels') + 1) {
        errs.push("CM_TABS: 'dual_momentum' must sit right after 'key_levels' (spec §7 #1)");
      }
      const meta = /\n  dual_momentum: \{\n    label: '([^']*)',\n    blurb: '((?:[^'\\]|\\.)*)',/.exec(src);
      if (!meta) {
        errs.push('TAB_META.dual_momentum (label + blurb) is missing');
      } else {
        if (!meta[2].includes('UNMEASURED')) errs.push('the TAB_META.dual_momentum blurb must say UNMEASURED');
        if (/bounce/i.test(meta[2])) errs.push('the TAB_META.dual_momentum blurb says "bounce" — surfaces he reads say reversal');
      }
      if (!/\n  dual_momentum: 'demand',/.test(src)) errs.push("ENTERABLE_KIND must carry dual_momentum: 'demand' (the mirror of KIND_BY_TAB)");
      const page = read('src/pages/ChartMaps.tsx');
      if (!/tab === 'dual_momentum' && <DualMomentumBoardNote/.test(page)) errs.push("ChartMaps.tsx must render <DualMomentumBoardNote … /> on tab === 'dual_momentum'");
      if (!/data\?\.warming && tab === 'dual_momentum' \? null/.test(page)) errs.push('the generic (demand) warming branch must skip the dual_momentum tab — its warming line is served');
      const board = read('../backend/chart_maps/board.py');
      if (!/elif t == "dual_momentum":/.test(board)) errs.push('board.py lost the elif t == "dual_momentum": dispatch');
      const tabsPy = /^TABS = \(([^)]*)\)/m.exec(board);
      if (!tabsPy || !/"dual_momentum"/.test(tabsPy[1])) errs.push('board.py TABS must carry "dual_momentum"');
      let dmt = '';
      try { dmt = read('../backend/chart_maps/dual_momentum_tab.py'); } catch { errs.push('backend/chart_maps/dual_momentum_tab.py is missing'); }
      if (dmt) {
        if (!dmt.includes('UNMEASURED')) errs.push('dual_momentum_tab.py must say UNMEASURED');
        // `bounce_room` is a MODULE NAME (internal identifiers keep `bounce`,
        // cheetah-ops) — the tab imports its demand_read. Any other "bounc" is
        // served wording and fails.
        if (/bounc/i.test(dmt.replace(/bounce_room/g, ''))) errs.push('dual_momentum_tab.py says "bounce"');
        if (!/sepa\.dual_momentum|from sepa import dual_momentum/.test(dmt)) errs.push('dual_momentum_tab.py must reuse sepa.dual_momentum (the page engine), not re-rank');
        if (/def room_gate\b|def demand_proximity_gate\b/.test(dmt)) errs.push('dual_momentum_tab.py must not re-implement the alert gate (reuse alert_gates)');
        if (/ALERT_MIN_ROOM_PCT\s*=/.test(dmt)) errs.push('dual_momentum_tab.py must not retype ALERT_MIN_ROOM_PCT');
      }
      let en = '';
      try { en = read('../backend/supply_demand/enterable.py'); } catch { errs.push('backend/supply_demand/enterable.py is missing'); }
      if (en && !/"dual_momentum":\s*KIND_DEMAND/.test(en)) errs.push('enterable.py KIND_BY_TAB must carry "dual_momentum": KIND_DEMAND');
      const ladder = read('src/lib/cardLadder.ts');
      const ip = /const IDENT_PREFIX = \[([^\]]*)\]/.exec(ladder);
      if (!ip || !/'\\u\{1F3CE\}\\u\{FE0F\} #'|'🏎️ #'/.test(ip[1])) errs.push('cardLadder IDENT_PREFIX must route the served 🏎️ rank chip (VS16 included) to IDENT');
      const nf = read('src/lib/newFeatures.ts');
      const idAt = nf.indexOf("id: 'chart-maps-dual-momentum-2026-09-29'");
      if (idAt < 0) {
        errs.push("newFeatures.ts lost the ✨ entry id: 'chart-maps-dual-momentum-2026-09-29'");
      } else {
        const entry = nf.slice(idAt, nf.indexOf('\n    addedAt', idAt) + 80);
        if (!entry.includes('UNMEASURED')) errs.push('the 🏎️ Dual Momentum ✨ entry must say UNMEASURED');
        if (/bounce/i.test(entry)) errs.push('the 🏎️ Dual Momentum ✨ entry says "bounce"');
        if (!entry.includes("route: '/chart-maps?tab=dual_momentum'")) errs.push("the 🏎️ Dual Momentum ✨ entry must route to '/chart-maps?tab=dual_momentum'");
      }
      return errs;
    },
  },
  {
    name: '🏎️ Dual Momentum filters + 💰 order (2026-09-29): 🌀/📍/🔑 over the pool pre-cut, served counts, never silent, cap order tab-scoped, never bounce',
    file: 'src/lib/dmFilters.ts',
    // Ajay 2026-09-29: "Can you add AMD raided and near demand zone and near
    // lower Key level filters to dual momentum please" and, the same day,
    // "Also a sort by market cap please". The boxes are VIEWS over existing
    // reads (the AMD Raided tab's stored grade, the 🎯 gate's own proximity
    // read, the Key Levels tab's build/rank) applied over the WHOLE pool
    // BEFORE the cut; the 💰 order is two tab-scoped sort keys over the same
    // pool. Losing any link here silently changes WHICH leaders he sees.
    checks: (src) => {
      const errs = [];
      const ts = /export const DM_FILTER_KEYS = \[([^\]]*)\] as const/.exec(src);
      let dmt = '';
      try { dmt = read('../backend/chart_maps/dual_momentum_tab.py'); } catch { errs.push('backend/chart_maps/dual_momentum_tab.py is missing'); }
      const py = /^FILTER_KEYS = \(([^)]*)\)/m.exec(dmt);
      const keysOf = (m) => (m ? m[1].split(',').map((x) => x.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean) : null);
      if (!ts || !py) errs.push('DM_FILTER_KEYS (dmFilters.ts) or FILTER_KEYS (dual_momentum_tab.py) is missing');
      else if (JSON.stringify(keysOf(ts)) !== JSON.stringify(keysOf(py)) || JSON.stringify(keysOf(py)) !== '["amd","zone","level"]') {
        errs.push(`DM_FILTER_KEYS ${JSON.stringify(keysOf(ts))} must equal FILTER_KEYS ${JSON.stringify(keysOf(py))} == ["amd","zone","level"]`);
      }
      if (dmt) {
        for (const need of ['TB.AMD_TURNING', 'AMD_MEASURED', 'demand_proximity_gate', 'def near_demand_pct', 'KLT.rank', 'KLT.MEMO_TTL_SEC', 'market_caps_for', 'cap=0']) {
          if (!dmt.includes(need)) errs.push(`dual_momentum_tab.py must use ${need} (reuse the engine / constant by name)`);
        }
        if ((dmt.match(/^KEY_LEVEL_NEAR_PCT\s*=\s*1\.0\s*$/gm) || []).length !== 1 || (dmt.match(/KEY_LEVEL_NEAR_PCT\s*=/g) || []).length !== 1) {
          errs.push('dual_momentum_tab.py must define KEY_LEVEL_NEAR_PCT = 1.0 exactly once');
        }
        if (!/HIS CALL[^\n]*\n[^\n]*\nKEY_LEVEL_NEAR_PCT|HIS CALL[^\n]*\nKEY_LEVEL_NEAR_PCT/.test(dmt)) errs.push('KEY_LEVEL_NEAR_PCT must sit under its HIS CALL comment');
        // The 📍 bound is read off demand_proximity_gate's own default — the tab
        // test_06 source guard bans the alert constant's NAME in this module.
        if (/ALERT_MAX_ABOVE_DEMAND_PCT/.test(dmt)) errs.push('dual_momentum_tab.py must not spell ALERT_MAX_ABOVE_DEMAND_PCT (read it off demand_proximity_gate)');
        if (/51\.9/.test(dmt)) errs.push('dual_momentum_tab.py retypes the AMD measurement (use HA.AMD_MEASURED)');
        if (/amd_verdict|find_cycle|find_raids/.test(dmt)) errs.push('dual_momentum_tab.py must not read a per-name AMD frame (the sweep document is the AMD tab state)');
        if (!/^SORT_MARKET_CAP = "market_cap"$/m.test(dmt) || !/^SORT_MARKET_CAP_ASC = "market_cap_asc"$/m.test(dmt)) errs.push('dual_momentum_tab.py lost SORT_MARKET_CAP / SORT_MARKET_CAP_ASC');
        if (!/^TAB_SORTS = \(SORT_NEAREST_DEMAND,\) \+ CAP_SORTS/m.test(dmt)) errs.push('dual_momentum_tab.py TAB_SORTS must carry 📍 + both 💰 keys');
        if (/bounc/i.test(dmt.replace(/bounce_room/g, ''))) errs.push('dual_momentum_tab.py says "bounce"');
      }
      const board = read('../backend/chart_maps/board.py');
      const a = board.indexOf('def dual_momentum_tiles');
      const body = a >= 0 ? board.slice(a, board.indexOf('\ndef ', a + 10)) : '';
      const pPass = body.indexOf('DMT.passes(');
      const pCap = body.indexOf('DMT.market_caps(');
      const pFin = body.indexOf('_finish(tiles');
      if (!(pPass > 0 && pFin > pPass)) errs.push('board.py dual_momentum_tiles: the filter (DMT.passes) must run BEFORE _finish(tiles …) — pre-cut');
      if (!(pCap > pPass && pFin > pCap)) errs.push('board.py dual_momentum_tiles: the 💰 order must read caps AFTER the filter and BEFORE _finish(tiles …)');
      if ((body.match(/DMT\.market_caps\(/g) || []).length !== 1) errs.push('board.py dual_momentum_tiles: exactly ONE cap read');
      if ((board.match(/dm_filters=/g) || []).length !== 1 || !/elif t == "dual_momentum":\n\s*out = dual_momentum_tiles\([^)]*dm_filters=/.test(board)) {
        errs.push('board.py: dm_filters= must appear once, on the dual_momentum dispatch only');
      }
      if (!/t == "dual_momentum"\s*\n?\s*and sort in _DMT\.TAB_SORTS/.test(board)) errs.push('board.py: the tab-scoped sort coercion must use _DMT.TAB_SORTS (📍 + 💰 on this tab only)');
      const note = read('src/components/DualMomentumBoardNote.tsx');
      // 2026-09-30: the boxes are shared with 🛡️ Resiliency through a
      // `testIdPrefix` prop that DEFAULTS to 'cm-dm' — the DM ids are then
      // `${testIdPrefix}-filter-…` with that default, byte-identical output.
      const dmPrefixed = /testIdPrefix = 'cm-dm'/.test(note);
      const hasId = (id) => note.includes(`data-testid="${id}"`)
        || (dmPrefixed && id.startsWith('cm-dm-filter') && note.includes('data-testid={`${testIdPrefix}' + id.slice('cm-dm'.length) + '`}'));
      for (const id of ['cm-dm-filter-line', 'cm-dm-cap-line', 'cm-dm-sort-market_cap']) {
        if (!hasId(id)) errs.push(`DualMomentumBoardNote.tsx must render data-testid="${id}" (never silent)`);
      }
      if (!note.includes('dmCapSortNext(served)')) errs.push('the 💰 button must ask for dmCapSortNext(served) — the direction flips off the SERVED sort');
      if (/bounce/i.test(note)) errs.push('DualMomentumBoardNote.tsx says "bounce"');
      const page = read('src/pages/ChartMaps.tsx');
      if (!/tab === 'dual_momentum' && <DualMomentumBoardNote[^\n]*onToggleFilter=/.test(page)) errs.push("ChartMaps.tsx must pass onToggleFilter= on the tab === 'dual_momentum' && <DualMomentumBoardNote line");
      const cm = read('src/lib/chartMaps.ts');
      if (!/if \(p\.tab === 'dual_momentum' && p\.dmFilters\) q\.set\(DM_FILTER_PARAM, p\.dmFilters\);/.test(cm)) errs.push("chartMaps.ts boardQuery must set the dm param only under p.tab === 'dual_momentum'");
      if (!/export const DM_SORT_MARKET_CAP = 'market_cap';/.test(cm) || !/export const DM_SORT_MARKET_CAP_ASC = 'market_cap_asc';/.test(cm)) errs.push('chartMaps.ts DM_SORT_MARKET_CAP / _ASC must equal the served keys');
      // ANY by default + the "must match all" switch + served badges (Ajay
      // 2026-09-29: "How can I see all of these? at the same time? is there a
      // check box selection?"). The server decides ANY / ALL and serves one
      // badge per ticked box passed; the TSX never re-derives either.
      if (dmt) {
        if (!/^FILTER_MODE_DEFAULT = MODE_ANY$/m.test(dmt) || !/^MODE_ALL = "all"$/m.test(dmt) || !/^FILTER_MODE_PARAM = "dm_mode"$/m.test(dmt)) {
          errs.push('dual_momentum_tab.py: FILTER_MODE_DEFAULT must be MODE_ANY, MODE_ALL = "all", FILTER_MODE_PARAM = "dm_mode"');
        }
        if (!/def filter_badges\(tf, active\)[\s\S]*?if k in act and tf\.get\(k\) is True/.test(dmt)) errs.push('dual_momentum_tab.filter_badges must badge ONLY ticked boxes that are True');
        const labs = /^FILTER_LABELS = \{([^}]*)\}/m.exec(dmt);
        const pyLabels = labs ? [...labs[1].matchAll(/"([^"]+)"\s*[,}]?\s*$/gm)].map((m) => m[1]) : [];
        const unesc = (x) => x.replace(/\\U([0-9A-Fa-f]{8})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
          .replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)));
        const ladderSrc = read('src/lib/cardLadder.ts');
        const ie = /const IDENT_EXACT = new Set\(\[([^\]]*)\]\)/.exec(ladderSrc);
        // 2026-09-30: IDENT_EXACT also carries the 🛡️ Resiliency box labels
        // (pinned by the Resiliency block); this check compares the DM three.
        const dmRe = /AMD raided|Near demand zone|Near a lower key level/;
        const tsLabels = ie ? [...ie[1].matchAll(/'([^']+)'/g)].map((m) => unesc(m[1])).filter((x) => dmRe.test(x)) : [];
        const py = pyLabels.map(unesc).filter((x) => dmRe.test(x));
        if (py.length !== 3 || JSON.stringify(py) !== JSON.stringify(tsLabels)) {
          errs.push(`cardLadder IDENT_EXACT ${JSON.stringify(tsLabels)} must equal dual_momentum_tab.FILTER_LABELS ${JSON.stringify(py)} (the served filter badges sit on the identity line)`);
        }
      }
      {
        const pPass2 = body.indexOf('DMT.passes(t["dm_filter"], active, mode)');
        const pBadge = body.indexOf('DMT.filter_badges(t["dm_filter"], active)');
        if (!(pPass2 > 0 && pBadge > pPass2 && pFin > pBadge)) errs.push('board.py dual_momentum_tiles: DMT.passes(..., active, mode) then DMT.filter_badges(t["dm_filter"], active), both BEFORE _finish(tiles …)');
        if ((board.match(/dm_mode=/g) || []).length !== 1 || !/elif t == "dual_momentum":\n\s*out = dual_momentum_tiles\([\s\S]{0,300}?dm_mode=/.test(board)) {
          errs.push('board.py: dm_mode= must appear once, on the dual_momentum dispatch only');
        }
        if (!/if \(p\.tab === 'dual_momentum' && p\.dmMode === DM_MODE_ALL\) q\.set\(DM_MODE_PARAM, DM_MODE_ALL\);/.test(cm)) errs.push("chartMaps.ts boardQuery must set dm_mode=all only under p.tab === 'dual_momentum'");
        if (!/export const DM_MODE_PARAM = 'dm_mode';/.test(src) || !/export function parseDmMode/.test(src)) errs.push('dmFilters.ts must export DM_MODE_PARAM = \'dm_mode\' and parseDmMode');
        if (!/tab === 'dual_momentum' && <DualMomentumBoardNote[^\n]*onToggleMode=\{toggleDmMode\}/.test(page)) errs.push('ChartMaps.tsx must pass onToggleMode={toggleDmMode} on the DualMomentumBoardNote line (the mode lives in ?dm_mode=)');
        if (!/next\.set\(DM_MODE_PARAM, DM_MODE_ALL\)/.test(page) || !/next\.delete\(DM_MODE_PARAM\)/.test(page)) errs.push('ChartMaps.tsx: the switch must write / drop ?dm_mode=all in the URL');
        const modeId = note.includes('data-testid="cm-dm-filter-mode"')
          || (/testIdPrefix = 'cm-dm'/.test(note) && note.includes('data-testid={`${testIdPrefix}-filter-mode`}'));
        if (!modeId || !/checked=\{f\.mode === 'all'\}/.test(note)) errs.push('DualMomentumBoardNote.tsx: the "must match all" switch must render with checked = the SERVED mode');
        for (const [f, txt] of [['DualMomentumBoardNote.tsx', note], ['ChartMaps.tsx', page]]) {
          if (/dm_filter\s*[?.]|\.some\(\([^)]*\)\s*=>[^\n]*dm_filter|passed_any\s*[-+]/.test(txt)) errs.push(`${f} reads tile.dm_filter / re-derives a pass — the server decides ANY / ALL and serves the badges`);
        }
      }
      const nf = read('src/lib/newFeatures.ts');
      const at = nf.indexOf("id: 'chart-maps-dm-filters-2026-09-29'");
      if (at < 0) {
        errs.push("newFeatures.ts lost the ✨ entry id: 'chart-maps-dm-filters-2026-09-29'");
      } else {
        const entry = nf.slice(at, nf.indexOf("' },", at) + 4);
        for (const need of ['Can you add AMD raided and near demand zone and near lower Key level filters to dual momentum please',
                            'Also a sort by market cap please', 'MEASURED INVERTED', 'UNMEASURED', '💰',
                            'How can I see all of these? at the same time? is there a check box selection?',
                            'must match all']) {
          if (!entry.includes(need)) errs.push(`the 🏎️ filters ✨ entry must carry: ${need}`);
        }
        if (/bounce/i.test(entry)) errs.push('the 🏎️ filters ✨ entry says "bounce"');
      }
      return errs;
    },
  },
  {
    name: '🏷️ Under Value vs peers (2026-09-29): same tab, 💎 default unchanged, UNMEASURED served, no maths in TSX, toggle persisted, never bounce',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-29: "create me another tab where valuations are wrong based
    // on analytics …" then "Use the same tab actually". Any of these links lost
    // silently turns the toggle into a new tab, changes the 💎 default, drops
    // the UNMEASURED word, or lets the TSX compose a number the server did not
    // serve.
    checks: (src) => {
      const errs = [];
      const tabs = parseCmTabs(src);
      if (!tabs) {
        errs.push('CM_TABS could not be parsed');
      } else {
        if (tabs.some((t) => /peer|mispric/.test(t))) errs.push('CM_TABS gained a peers/mispriced tab — he said "Use the same tab actually"');
        if (tabs.filter((t) => t === 'undervalue').length !== 1) errs.push("CM_TABS must carry 'undervalue' exactly once");
      }
      if (/'(?:undervalue_peers|peers|mispriced)'/.test((/export type CmTab = ([^;]*);/.exec(src) || ['', ''])[1])) errs.push('CmTab gained a peers tab — same tab only');
      if (!src.includes("p.tab === 'undervalue' && p.uvView === UV_VIEW_PEERS) q.set(UV_VIEW_PARAM, UV_VIEW_PEERS)")) {
        errs.push("boardQuery must send uv=peers on the undervalue tab only: p.tab === 'undervalue' && p.uvView === UV_VIEW_PEERS) q.set(UV_VIEW_PARAM, UV_VIEW_PEERS)");
      }
      if (!/undervalue_view\?: CmUndervalueView \| null;/.test(src)) errs.push('CmBoard must type undervalue_view?: CmUndervalueView | null');
      const uv = read('src/lib/undervalueView.ts');
      const want = { UV_VIEW_PARAM: 'uv', UV_VIEW_PEERS: 'peers', UV_VIEW_PSG: 'psg' };
      for (const [k, v] of Object.entries(want)) {
        if (!new RegExp(`export const ${k} = '${v}';`).test(uv)) errs.push(`undervalueView.ts must export ${k} = '${v}'`);
      }
      const page = read('src/pages/ChartMaps.tsx');
      if (!page.includes("tab === 'undervalue' && <UndervalueViewNote block={data?.undervalue_view ?? null} onView={setUvView} />")) {
        errs.push("ChartMaps.tsx must render <UndervalueViewNote block={data?.undervalue_view ?? null} onView={setUvView} /> on tab === 'undervalue'");
      }
      if (!page.includes('parseUvView(params.get(UV_VIEW_PARAM))')) errs.push('ChartMaps.tsx must read the view from the URL: parseUvView(params.get(UV_VIEW_PARAM))');
      const note = read('src/components/UndervalueViewNote.tsx');
      const code = note.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
      if (/UNMEASURED|peer|median|toFixed|Math\.|%/.test(code)) errs.push('UndervalueViewNote.tsx composes wording or maths — print the served header/note only');
      if (!/block as \{ header\?: unknown \}\)\.header/.test(note)) errs.push('UndervalueViewNote.tsx must print the served header');
      let py = '';
      try { py = read('../backend/chart_maps/undervalue_peers.py'); } catch { errs.push('backend/chart_maps/undervalue_peers.py is missing'); }
      if (py) {
        if (!py.includes('UNMEASURED')) errs.push('undervalue_peers.py must say UNMEASURED');
        if (!/^MEASURED = False/m.test(py)) errs.push('undervalue_peers.py must carry MEASURED = False');
        const consts = [['PEER_PS_MAX_FRACTION', '0\\.50'], ['MIN_PEERS', '5'], ['MIN_SALES_YOY_Q_PCT', '20\\.0'],
                        ['MIN_SALES_TTM_GROWTH_PCT', '20\\.0'], ['MIN_TTM_REVENUE_USD', '100_000_000\\.0']];
        for (const [k, v] of consts) {
          if (!new RegExp(`^${k} = ${v}\\b`, 'm').test(py)) errs.push(`undervalue_peers.py: ${k} must be ${v.replace(/\\/g, '')} (HIS CALL — change the ✨ label with it)`);
        }
        const pyWant = { VIEW_PARAM: 'uv', VIEW_PEERS: 'peers', VIEW_PSG: 'psg' };
        for (const [k, v] of Object.entries(pyWant)) {
          if (!new RegExp(`^${k} = "${v}"`, 'm').test(py)) errs.push(`undervalue_peers.py must carry ${k} = "${v}" (equal to undervalueView.ts)`);
        }
        if (!/from growth\.capital_quality import _median/.test(py)) errs.push('undervalue_peers.py must import _median from growth.capital_quality (one median)');
        if (!/market_caps_for/.test(py)) errs.push('undervalue_peers.py must read caps via promo_circuit.market_caps_for');
        if (!/decision_snapshot/.test(py)) errs.push('undervalue_peers.py must read fundamentals via research.decision_snapshot');
        if (!py.includes('never compared across companies')) errs.push('undervalue_peers.py NOTE must say the share price is never compared across companies');
        if (/bounc|fake/i.test(py)) errs.push('undervalue_peers.py says "bounce"/"fake"');
      }
      const board = read('../backend/chart_maps/board.py');
      if (!board.includes('            out = undervalue_tiles(limit, days, themes_first, srt, tier,')) errs.push('board.py: the 💎 default branch must still call undervalue_tiles(limit, days, themes_first, srt, tier, …)');
      if (!board.includes('def undervalue_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,')) errs.push('board.py: def undervalue_tiles(limit: int = LIMIT_DEFAULT … signature changed');
      const api = read('../backend/chart_maps/api.py');
      if (!/uv: str = Query\(/.test(api)) errs.push('api.py must declare uv: str = Query(');
      if (!api.includes('uv=(uv if isinstance(uv, str) and uv.strip() else None),')) errs.push('api.py must pass uv through, coerced');
      const nf = read('src/lib/newFeatures.ts');
      const idAt = nf.indexOf("id: 'chart-maps-undervalue-peers-2026-09-29'");
      if (idAt < 0) {
        errs.push("newFeatures.ts lost the ✨ entry id: 'chart-maps-undervalue-peers-2026-09-29'");
      } else {
        const end = nf.indexOf('\n  {', idAt);
        const entry = nf.slice(idAt, end < 0 ? undefined : end);
        if (!entry.includes('UNMEASURED')) errs.push('the 🏷️ vs peers ✨ entry must say UNMEASURED');
        if (!entry.includes("route: '/chart-maps?tab=undervalue&uv=peers'")) errs.push("the 🏷️ vs peers ✨ entry must route to '/chart-maps?tab=undervalue&uv=peers'");
        if (/bounce|fake/i.test(entry)) errs.push('the 🏷️ vs peers ✨ entry says "bounce"/"fake"');
      }
      return errs;
    },
  },
  {
    name: '🏔️ ATH tab (2026-09-29): mounted after 🏎️, UNMEASURED served, proven vs high-since served, toggle persisted, never bounce',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-29: "Can you give me a new tab - for all the stocks that
    // are reaching all time highs? call it ATH. Once some of them are going
    // below their ATH or 52 Week Highs..". Any of these links lost silently
    // drops the tab, its UNMEASURED word, its proven-vs-"high since" honesty
    // (served by the backend, never composed in the TSX) or the URL-persisted
    // 🏔️ / ↘️ toggle.
    checks: (src) => {
      const errs = [];
      const tabs = parseCmTabs(src);
      if (!tabs || !tabs.includes('ath')) {
        errs.push("CM_TABS must carry 'ath'");
      } else if (tabs.indexOf('ath') !== tabs.indexOf('dual_momentum') + 1) {
        errs.push("CM_TABS: 'ath' must sit right after 'dual_momentum' (ATH spec HIS CALL #10)");
      }
      const meta = /\n  ath: \{\n    label: '([^']*)',\n    blurb: '((?:[^'\\]|\\.)*)',/.exec(src);
      if (!meta) {
        errs.push('TAB_META.ath (label + blurb) is missing');
      } else {
        if (!meta[2].includes('UNMEASURED')) errs.push('the TAB_META.ath blurb must say UNMEASURED');
        if (/bounce|fake/i.test(meta[2])) errs.push('the TAB_META.ath blurb says "bounce"/"fake"');
        if (/never count/i.test(meta[2])) errs.push('the TAB_META.ath blurb claims earlier-listing bars "never count" — they are cut only where a curated cut or a gap proves them');
      }
      if (/\n  ath: '/.test(src)) errs.push('ENTERABLE_KIND must NOT carry ath (🎯 n/a, the Key Levels precedent)');
      if (!/export const ATH_SORT_SLIPPING = 'slipping';/.test(src)) errs.push("chartMaps.ts must export ATH_SORT_SLIPPING = 'slipping'");
      const page = read('src/pages/ChartMaps.tsx');
      if (!/tab === 'ath' && <AthBoardNote board=\{data\?\.ath_board \?\? null\} sorts=\{data\?\.sorts\} sort=\{data\?\.sort\} onSort=\{setSortParam\} \/>/.test(page)) {
        errs.push("ChartMaps.tsx must render <AthBoardNote board={data?.ath_board ?? null} sorts={data?.sorts} sort={data?.sort} onSort={setSortParam} /> on tab === 'ath' (the toggle persists through ?sort=)");
      }
      if (!/data\?\.warming && tab === 'ath' \? null/.test(page)) errs.push('the generic (demand) warming branch must skip the ath tab — its warming line is served');
      const note = read('src/components/AthBoardNote.tsx');
      // The component prints the SERVED header/note; it must never compose the
      // proven / "high since" / all-time wording itself.
      const code = note.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
      if (/all-time|high since|proven|UNMEASURED/i.test(code)) errs.push('AthBoardNote.tsx composes ATH wording — the header and note must be printed as served');
      if (!/board as \{ header\?: unknown \}\)\.header/.test(note)) errs.push('AthBoardNote.tsx must print the served header');
      const board = read('../backend/chart_maps/board.py');
      if (!/elif t == "ath":/.test(board)) errs.push('board.py lost the elif t == "ath": dispatch');
      const tabsPy = /^TABS = \(([^)]*)\)/m.exec(board);
      if (!tabsPy || !/"ath"/.test(tabsPy[1])) errs.push('board.py TABS must carry "ath"');
      if (!/\(t == "ath" and sort == _ATH\.SORT_SLIPPING\)/.test(board)) errs.push('board.py must honour the tab-scoped ↘️ slipping sort on ath only');
      let at = '';
      try { at = read('../backend/chart_maps/ath_tab.py'); } catch { errs.push('backend/chart_maps/ath_tab.py is missing'); }
      if (at) {
        if (!at.includes('UNMEASURED')) errs.push('ath_tab.py must say UNMEASURED');
        if (/bounc|fake/i.test(at.replace(/quick_bounce/g, ''))) errs.push('ath_tab.py says "bounce"/"fake"');
        if (!/from supply_demand\.zone_edge import NEW_HIGH_TOL/.test(at)) errs.push('ath_tab.py must import NEW_HIGH_TOL from zone_edge (the one "at the high" band)');
        if (/0\.98/.test(at)) errs.push('ath_tab.py retypes 0.98 — import NEW_HIGH_TOL');
        if (!/KL\.anchor_read/.test(at) || !/KL\.verify_last/.test(at)) errs.push('ath_tab.py must use key_levels anchor_read / verify_last (the one live print + verify)');
        if (!/bulk_cached_frames/.test(at)) errs.push('ath_tab.py must read the cached frames via prices.bulk_cached_frames');
        if (!/"slip_from_high_since"/.test(at)) errs.push('ath_tab.py must count slips from a "high since" apart from a proven all-time high');
        if (!/proven all-time high/.test(at) || !/not proven all-time/.test(at)) errs.push('ath_tab.py headers must word proven all-time and "high since" apart');
        if (!/def monthly_reaches_listing\(/.test(at)) errs.push('ath_tab.py must prove all-time from the monthly history (monthly_reaches_listing), never the 2-year frame alone');
      }
      let ah = '';
      try { ah = read('../backend/chart_maps/ath_history.py'); } catch { errs.push('backend/chart_maps/ath_history.py is missing'); }
      if (ah) {
        if (!ah.includes('_cut_foreign_head(')) errs.push('ath_history.py must apply prices._cut_foreign_head');
        if (!ah.includes('_fetch_massive')) errs.push('ath_history.py must fetch through the ONE Massive fetcher prices._fetch_massive');
        if (/_mongo_put|price_cache|load_prices\(/.test(ah)) errs.push('ath_history.py must never touch the shared price cache or loader (_mongo_put / price_cache / load_prices)');
      }
      const nf = read('src/lib/newFeatures.ts');
      const idAt = nf.indexOf("id: 'chart-maps-ath-2026-09-29'");
      if (idAt < 0) {
        errs.push("newFeatures.ts lost the ✨ entry id: 'chart-maps-ath-2026-09-29'");
      } else {
        const entry = nf.slice(idAt, nf.indexOf("route: '", idAt) + 60);
        if (!entry.includes('UNMEASURED')) errs.push('the 🏔️ ATH ✨ entry must say UNMEASURED');
        if (/bounce|fake/i.test(entry)) errs.push('the 🏔️ ATH ✨ entry says "bounce"/"fake"');
        if (!entry.includes("route: '/chart-maps?tab=ath'")) errs.push("the 🏔️ ATH ✨ entry must route to '/chart-maps?tab=ath'");
      }
      return errs;
    },
  },
  {
    name: '🛡️ Resiliency tab (2026-09-30): mounted after 🏔️, UNMEASURED served, boxes = the backend keys, note composes nothing, never bounce',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-09-30: "Can you build me a new tab- Resileincy. This is to
    // help me with #1 - Stocks that are not going to by more than 0.5% during
    // a T1 event like FOMC or any others like todays Inflation and GDP track
    // T2s as well. #3 - Tape is positive and bullish EOD or Pre market. but
    // volume has to be accounted for. We have all of this data already."
    // Any of these links lost silently drops the tab, its UNMEASURED word, the
    // served boxes (FE keys must equal the backend's), the one-engine reuse
    // (anchor_read / verify_last / past_events / BURST_RVOL_MIN) or the rule
    // that the note prints served sentences and composes none.
    checks: (src) => {
      const errs = [];
      const tabs = parseCmTabs(src);
      if (!tabs || !tabs.includes('resiliency')) {
        errs.push("CM_TABS must carry 'resiliency'");
      } else if (tabs.indexOf('resiliency') !== tabs.indexOf('ath') + 1) {
        errs.push("CM_TABS: 'resiliency' must sit right after 'ath' (resiliency spec HIS CALL #16)");
      }
      const HIS = 'Can you build me a new tab- Resileincy. This is to help me with #1 - Stocks that are not going to by more than 0.5% during a T1 event like FOMC or any others like todays Inflation and GDP track T2s as well. #3 - Tape is positive and bullish EOD or Pre market. but volume has to be accounted for. We have all of this data already.';
      const meta = /\n  resiliency: \{\n    label: '([^']*)',\n    blurb: '((?:[^'\\]|\\.)*)',/.exec(src);
      if (!meta) {
        errs.push('TAB_META.resiliency (label + blurb) is missing');
      } else {
        if (!meta[2].includes('UNMEASURED')) errs.push('the TAB_META.resiliency blurb must say UNMEASURED');
        if (!meta[2].includes(HIS)) errs.push('the TAB_META.resiliency blurb must quote his ask verbatim');
        if (/bounce|fake|won't drop|won\\'t drop/i.test(meta[2])) errs.push('the TAB_META.resiliency blurb says "bounce"/"fake"/"won\'t drop"');
      }
      if (/\n  resiliency: '/.test(src)) errs.push('ENTERABLE_KIND must NOT carry resiliency (🎯 n/a, the ATH precedent)');
      for (const [k, v] of [['RES_SORT_T1', 'res_t1'], ['RES_SORT_T2', 'res_t2'], ['RES_SORT_DOWN', 'res_down'], ['RES_SORT_TODAY', 'res_today'], ['RES_SORT_GROWTH', 'res_growth']]) {
        if (!src.includes(`export const ${k} = '${v}';`)) errs.push(`chartMaps.ts must export ${k} = '${v}'`);
      }
      if (!/if \(p\.tab === 'resiliency' && p\.resFilters\) q\.set\(RES_FILTER_PARAM, p\.resFilters\);/.test(src)) errs.push("boardQuery must send res only under p.tab === 'resiliency'");
      if (!/if \(p\.tab === 'resiliency' && p\.resMode === DM_MODE_ALL\) q\.set\(RES_MODE_PARAM, DM_MODE_ALL\);/.test(src)) errs.push("boardQuery must send res_mode=all only under p.tab === 'resiliency'");

      const page = read('src/pages/ChartMaps.tsx');
      if (!/tab === 'resiliency' && <ResiliencyBoardNote board=\{data\?\.resiliency_board \?\? null\} sorts=\{data\?\.sorts\} sort=\{data\?\.sort\} onSort=\{setSortParam\} onToggleFilter=\{toggleResFilter\} onToggleMode=\{toggleResMode\} \/>/.test(page)) {
        errs.push("ChartMaps.tsx must render <ResiliencyBoardNote board={data?.resiliency_board ?? null} sorts={data?.sorts} sort={data?.sort} onSort={setSortParam} onToggleFilter={toggleResFilter} onToggleMode={toggleResMode} /> on tab === 'resiliency'");
      }
      if (!/data\?\.warming && tab === 'resiliency' \? null/.test(page)) errs.push('the generic (demand) warming branch must skip the resiliency tab — its warming line is served');
      // 2026-10-14: 🎢 high_beta is APPENDED after this one (BUILD_SPEC §3.8 WP3) — the pin allows exactly that tail.
      // WIDENED 2026-10-16 — 🕯️ doji_sweep is a board tab after 🚩 (the tail may also carry && tab !== 'doji_sweep').
      if (!/tab !== 'resiliency'(?:\s*&& tab !== '(?:high_beta|doji_sweep)')*\);/.test(page)) errs.push('the demand-scan progress poll must skip the resiliency tab');
      if (/res_filter\s*[?.]/.test(page)) errs.push('ChartMaps.tsx reads tile.res_filter — the server decides every box and serves the badges');

      const lib = read('src/lib/resiliencyFilters.ts');
      const ts = /export const RES_FILTER_KEYS = \[([^\]]*)\] as const/.exec(lib);
      if (!/import \{[^}]*parseDmMode[^}]*\} from '\.\/dmFilters'/.test(lib)) errs.push('resiliencyFilters.ts must import parseDmMode (one mode parser)');
      const note = read('src/components/ResiliencyBoardNote.tsx');
      const code = note.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
      if (/UNMEASURED|hold rate|%|toFixed|Math\./.test(code)) errs.push('ResiliencyBoardNote.tsx composes wording or maths — every sentence and number must be printed as served');
      if (/bounce|fake/i.test(note)) errs.push('ResiliencyBoardNote.tsx says "bounce"/"fake"');
      if (!/<DualMomentumFilters[^>]*knownKeys=\{RES_FILTER_KEYS\}[^>]*testIdPrefix="cm-res"/.test(note)) errs.push('ResiliencyBoardNote.tsx must reuse DualMomentumFilters with knownKeys={RES_FILTER_KEYS} testIdPrefix="cm-res"');

      const board = read('../backend/chart_maps/board.py');
      const tabsPy = /^TABS = \(([^)]*)\)/m.exec(board);
      if (!tabsPy || !/"resiliency"/.test(tabsPy[1])) errs.push('board.py TABS must carry "resiliency"');
      if (!/elif t == "resiliency":/.test(board)) errs.push('board.py lost the elif t == "resiliency": dispatch');
      if (!/\(t == "resiliency" and sort in _RES\.TAB_SORTS\)/.test(board)) errs.push('board.py must honour the tab-scoped resiliency sorts on this tab only');

      let rt = '';
      try { rt = read('../backend/chart_maps/resiliency_tab.py'); } catch { errs.push('backend/chart_maps/resiliency_tab.py is missing'); }
      if (rt) {
        const py = /^FILTER_KEYS = \(([^)]*)\)/m.exec(rt);
        const keysOf = (m) => (m ? m[1].split(',').map((x) => x.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean) : null);
        if (!ts || !py) errs.push('RES_FILTER_KEYS (resiliencyFilters.ts) or FILTER_KEYS (resiliency_tab.py) is missing');
        else if (JSON.stringify(keysOf(ts)) !== JSON.stringify(keysOf(py)) || JSON.stringify(keysOf(py)) !== '["t1","t2","eod","pre"]') {
          errs.push(`RES_FILTER_KEYS ${JSON.stringify(keysOf(ts))} must equal FILTER_KEYS ${JSON.stringify(keysOf(py))} == ["t1","t2","eod","pre"]`);
        }
        if (!rt.includes('UNMEASURED')) errs.push('resiliency_tab.py must say UNMEASURED');
        if (/bounc|fake|won't drop/i.test(rt.replace(/quick_bounce/g, ''))) errs.push('resiliency_tab.py says "bounce"/"fake"/"won\'t drop"');
        if (!/BURST_RVOL_MIN/.test(rt)) errs.push('resiliency_tab.py must import the 1.5× bar as momentum_burst.BURST_RVOL_MIN');
        const rtCode = rt.replace(/#[^\n]*/g, '');
        if (/=\s*1\.5\b/.test(rtCode)) errs.push('resiliency_tab.py retypes 1.5 — import BURST_RVOL_MIN');
        for (const need of ['KL.anchor_read', 'KL.verify_last', 'bulk_cached_frames', 'past_events']) {
          if (!rt.includes(need)) errs.push(`resiliency_tab.py must use ${need} (the one engine)`);
        }
        // The served box labels sit on the card's identity line (cardLadder IDENT_EXACT).
        const consts = {};
        for (const m of rt.matchAll(/^([A-Z_]*MARK) = "([^"]*)"/gm)) consts[m[1]] = m[2];
        const unesc = (x) => x.replace(/\\U([0-9A-Fa-f]{8})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
          .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
          .replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)));
        const labs = /^FILTER_LABELS = \{([\s\S]*?)\}/m.exec(rt);
        const pyLabels = labs ? [...labs[1].matchAll(/"(t1|t2|eod|pre)":\s*([A-Z_]+)\s*\+\s*"([^"]*)"/g)]
          .map((m) => (consts[m[2]] !== undefined ? unesc(consts[m[2]]) + unesc(m[3]) : `?${m[2]}`)) : [];
        const ladderSrc = read('src/lib/cardLadder.ts');
        const ie = /const IDENT_EXACT = new Set\(\[([^\]]*)\]\)/.exec(ladderSrc);
        const tsLabels = ie ? [...ie[1].matchAll(/'([^']+)'/g)].map((m) => unesc(m[1])).filter((x) => /Held on T[12]|Bullish tape/.test(x)) : [];
        if (pyLabels.length !== 4 || JSON.stringify(pyLabels) !== JSON.stringify(tsLabels)) {
          errs.push(`cardLadder IDENT_EXACT ${JSON.stringify(tsLabels)} must equal resiliency_tab.FILTER_LABELS ${JSON.stringify(pyLabels)}`);
        }
      }
      // 📅 every session + 🚀 growth (Ajay 2026-10-07: "I want the highest growth
      // stocks on top like Vistra for example"). The served sort keys, the
      // removed not-a-data-day sentence, the chip / pill prefixes the card
      // ladder routes on, the one-engine reuse and the shared scan parse.
      if (rt) {
        if (!rt.includes('"res_t1"') || !rt.includes('"res_growth"')) errs.push('resiliency_tab.py must serve "res_t1" and "res_growth"');
        if (rt.includes('TODAY_SORT_UNAVAILABLE') || rt.includes('not a T1 or T2 data day')) errs.push('resiliency_tab.py must never serve "not a T1 or T2 data day" again (2026-10-07)');
        for (const need of ['qoq.score_board', 'qoq._seq_pct', '_rev_base', 'decision_snapshot', 'mode_for', 'day_from_snapshot']) {
          if (!rt.includes(need)) errs.push(`resiliency_tab.py must use ${need} (the one engine)`);
        }
        const lad = read('src/lib/cardLadder.ts');
        const identPre = /const IDENT_PREFIX = \[([\s\S]*?)\];/.exec(lad);
        const pricePre = /const PRICE_PREFIX = \[([\s\S]*?)\];/.exec(lad);
        if (!/^GROWTH_CHIP_PREFIX = "Sales "/m.test(rt)) errs.push('resiliency_tab.py must define GROWTH_CHIP_PREFIX = "Sales "');
        if (!identPre || !identPre[1].includes("'Sales '")) errs.push("cardLadder IDENT_PREFIX must carry 'Sales ' (resiliency_tab.GROWTH_CHIP_PREFIX)");
        // 🚀 coverage line (2026-10-07 b): served iff the note prints it — a served
        // line nobody reads, or a reader for a line nobody serves, is a silent gap.
        {
          const note = read('src/components/ResiliencyBoardNote.tsx');
          const serves = rt.includes('"growth_line"');
          const reads = /\bb\.growth_line\b/.test(note);
          if (serves !== reads) errs.push(`resiliency_tab.py serves "growth_line" (${serves}) iff ResiliencyBoardNote.tsx reads b.growth_line (${reads})`);
          if (serves && !/\bb\.growth_gaps\b/.test(note)) errs.push('ResiliencyBoardNote.tsx must print the served growth_gaps fold');
        }
        if (!/^TODAY_PLAIN_FMT = TODAY_MARK \+ " today · /m.test(rt)) errs.push('resiliency_tab.py TODAY_PLAIN_FMT must start TODAY_MARK + " today · "');
        if (!/^TODAY_LAST_FMT = TODAY_MARK \+ " last session /m.test(rt)) errs.push('resiliency_tab.py TODAY_LAST_FMT must start TODAY_MARK + " last session "');
        if (!pricePre || !pricePre[1].includes("'\\u{1F4C5} today · '") || !pricePre[1].includes("'\\u{1F4C5} last session '")) {
          errs.push("cardLadder PRICE_PREFIX must carry '\\u{1F4C5} today · ' and '\\u{1F4C5} last session '");
        }
        const tilesFn = board.slice(board.indexOf('def resiliency_tiles('), board.indexOf('def fallen_tiles('));
        if (!tilesFn.includes('load_latest_shared()') || tilesFn.includes('scanner.load_latest()')) errs.push('board.py resiliency_tiles must read scanner.load_latest_shared() (READ-ONLY), never load_latest()');
      }
      {
        const nf2 = read('src/lib/newFeatures.ts');
        const at2 = nf2.indexOf("id: 'chart-maps-resiliency-today-growth-2026-10-07'");
        const ASK1 = 'Can you do a scan for me on the reseliency tab.. Is it working? Today is a very red day.. I wanna see which stocks were reselient cuz Vista was very reselient';
        const ASK2 = 'I want the highest growth stocks on top like Vistra for example';
        if (at2 < 0) {
          errs.push("newFeatures.ts lost the ✨ entry id: 'chart-maps-resiliency-today-growth-2026-10-07'");
        } else {
          const e2 = nf2.slice(at2, nf2.indexOf("' },", at2) + 4);
          if (!e2.includes(ASK1) || !e2.includes(ASK2)) errs.push('the 📅 🚀 Resiliency ✨ entry must quote BOTH asks verbatim');
          if (!e2.includes('UNMEASURED')) errs.push('the 📅 🚀 Resiliency ✨ entry must say UNMEASURED');
          if (/bounce|fake/i.test(e2)) errs.push('the 📅 🚀 Resiliency ✨ entry says "bounce"/"fake"');
          if (!e2.includes("route: '/chart-maps?tab=resiliency'")) errs.push("the 📅 🚀 Resiliency ✨ entry must route to '/chart-maps?tab=resiliency'");
        }
      }
      const nf = read('src/lib/newFeatures.ts');
      const idAt = nf.indexOf("id: 'chart-maps-resiliency-2026-09-30'");
      if (idAt < 0) {
        errs.push("newFeatures.ts lost the ✨ entry id: 'chart-maps-resiliency-2026-09-30'");
      } else {
        const entry = nf.slice(idAt, nf.indexOf("' },", idAt) + 4);
        if (!entry.includes('UNMEASURED')) errs.push('the 🛡️ Resiliency ✨ entry must say UNMEASURED');
        if (!entry.includes(HIS)) errs.push('the 🛡️ Resiliency ✨ entry must quote his ask verbatim');
        if (/bounce|fake|won't drop/i.test(entry)) errs.push('the 🛡️ Resiliency ✨ entry says "bounce"/"fake"/"won\'t drop"');
        if (!entry.includes("route: '/chart-maps?tab=resiliency'")) errs.push("the 🛡️ Resiliency ✨ entry must route to '/chart-maps?tab=resiliency'");
      }
      // Follow-up 2026-09-30: while resiliency_tab.PM_VOLUME_VERIFIED is False
      // the 🌅 volume leg is OFF — neither the ✨ entry nor the tab blurb may
      // promise the pre-market volume bar, and both must say it is off.
      const pmv = /^PM_VOLUME_VERIFIED = (True|False)\b/m.exec(rt || '');
      if (!pmv) {
        errs.push('resiliency_tab.py lost PM_VOLUME_VERIFIED = True|False');
      } else if (pmv[1] === 'False') {
        const promise = /1\.5×|by the same minute|pre-market volume against its own usual volume|pre-market tape is bullish/;
        const nfEntry = idAt < 0 ? '' : nf.slice(idAt, nf.indexOf("' },", idAt) + 4);
        for (const [what, txt] of [['the 🛡️ Resiliency ✨ entry', nfEntry], ['the TAB_META.resiliency blurb', meta ? meta[2] : '']]) {
          if (promise.test(txt)) errs.push(`${what} promises the pre-market volume bar while PM_VOLUME_VERIFIED = False`);
          if (!txt.includes('volume check is OFF')) errs.push(`${what} must say the pre-market "volume check is OFF" while PM_VOLUME_VERIFIED = False`);
        }
        if (!/it\.update\(off=True, off_reason=PRE_OFF_REASON\)/.test(rt)) errs.push('resiliency_tab.filters_block must serve the 🌅 box off + off_reason while PM_VOLUME_VERIFIED = False');
      }
      const dmf = read('src/components/DualMomentumBoardNote.tsx');
      if (!/filter-off-\$\{i\.key\}/.test(dmf) || !/disabled=\{!!offReason && i\.on !== true\}/.test(dmf)) {
        errs.push('DualMomentumFilters must grey a served off box (disabled unless ticked) and print its served off_reason');
      }
      return errs;
    },
  },
  {
    name: '📉 Down 40%+ tab (2026-10-02): mounted after 🛡️, label = THRESHOLD_PCT, UNMEASURED served, Bonde legend once, the FE composes and counts nothing, never bounce',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-10-02: "Can you build me a tab in chart maps about stocks that
    // dropped more than 40% lowers from like app loving company as an example
    // whcih si 60% low. But I also need you to capture informations about
    // sales like Bondes and other indicators based on Bondes formula please."
    // then "Scan the universe and bring me these stocks" and "also add things
    // like possible catalyst that made is drop like that."
    // Any of these links lost silently drops the tab, its UNMEASURED word, the
    // one-place threshold (the label and the ✨ numbers are read off the
    // backend constants, never typed twice), the once-per-tab Bonde legend,
    // or the rule that the FE prints served sentences and counts no legs.
    checks: (src) => {
      const errs = [];
      const tabs = parseCmTabs(src);
      if (!tabs || !tabs.includes('fallen')) {
        errs.push("CM_TABS must carry 'fallen'");
      } else {
        if (tabs.indexOf('fallen') !== tabs.indexOf('resiliency') + 1) errs.push("CM_TABS: 'fallen' must sit right after 'resiliency' (fallen spec HIS CALL #17)");
        if (tabs.filter((t) => t === 'fallen').length !== 1) errs.push("CM_TABS lists 'fallen' more than once");
        if (tabs.slice(0, 3).join(',') !== 'zones,deep_demand,quick_bounce') errs.push('CM_TABS lead three changed with the 📉 insertion');
      }
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\U([0-9A-Fa-f]{8})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)));
      let ft = '';
      try { ft = read('../backend/chart_maps/fallen_tab.py'); } catch { errs.push('backend/chart_maps/fallen_tab.py is missing'); }
      const thrM = /^THRESHOLD_PCT = ([0-9.]+)/m.exec(ft);
      const T = thrM ? String(Number(thrM[1])) : null;
      if (ft && !T) errs.push('fallen_tab.py lost THRESHOLD_PCT = <number>');
      const depM = /^DEPTH_STEPS = \(([^)]*)\)/m.exec(ft);
      const D = depM ? depM[1].split(',').map((x) => x.trim()).filter(Boolean) : null;
      if (ft && !D) errs.push('fallen_tab.py lost DEPTH_STEPS = (…)');
      if (T && D && String(Number(D[0])) !== T) errs.push(`fallen_tab.DEPTH_STEPS[0] (${D[0]}) must equal THRESHOLD_PCT (${T})`);
      let kl = '';
      try { kl = read('../backend/supply_demand/key_levels.py'); } catch { errs.push('backend/supply_demand/key_levels.py is missing'); }
      const yM = /^YEAR_BARS = (\d+)/m.exec(kl);
      const Y = yM ? yM[1] : null;
      if (kl && !Y) errs.push('key_levels.py lost YEAR_BARS = <int>');
      if (ft && !/^YEAR_BARS = KL\.YEAR_BARS\b/m.test(ft)) errs.push('fallen_tab.py must import YEAR_BARS = KL.YEAR_BARS (never type 252)');

      const HIS = [
        'Can you build me a tab in chart maps about stocks that dropped more than 40% lowers from like app loving company as an example whcih si 60% low. But I also need you to capture informations about sales like Bondes and other indicators based on Bondes formula please.',
        'Scan the universe and bring me these stocks',
        'also add things like possible catalyst that made is drop like that.',
      ];
      const meta = /\n  fallen: \{\n    label: '([^']*)',\n    blurb: '((?:[^'\\]|\\.)*)',/.exec(src);
      if (!meta) {
        errs.push('TAB_META.fallen (label + blurb) is missing');
      } else {
        if (T && unesc(meta[1]) !== `\u{1F4C9} Down ${T}%+`) errs.push(`TAB_META.fallen.label "${unesc(meta[1])}" must be "📉 Down ${T}%+" (fallen_tab.THRESHOLD_PCT)`);
        const blurb = meta[2].replace(/\\'/g, "'");
        if (!blurb.includes('UNMEASURED')) errs.push('the TAB_META.fallen blurb must say UNMEASURED');
        for (const h of HIS) if (!blurb.includes(h)) errs.push(`the TAB_META.fallen blurb must quote his ask verbatim: "${h.slice(0, 40)}…"`);
        if (/bounce|fake/i.test(blurb)) errs.push('the TAB_META.fallen blurb says "bounce"/"fake"');
        if (/\b39\b/.test(blurb)) errs.push('the TAB_META.fallen blurb carries the token 39');
      }
      if (/\n  fallen: '/.test(src)) errs.push('ENTERABLE_KIND must NOT carry fallen (🎯 n/a, the ATH / Resiliency precedent — fallen spec §7 #18)');
      for (const [k, v] of [['FALLEN_SORT_DEPTH', 'fallen_depth'], ['FALLEN_SORT_SALES', 'fallen_sales'], ['FALLEN_DEPTH_PARAM', 'depth']]) {
        if (!src.includes(`export const ${k} = '${v}';`)) errs.push(`chartMaps.ts must export ${k} = '${v}'`);
      }
      if (ft) {
        for (const [py, v] of [['SORT_DEPTH', 'fallen_depth'], ['SORT_SALES', 'fallen_sales'], ['DEPTH_PARAM', 'depth']]) {
          if (!new RegExp(`^${py} = "${v}"`, 'm').test(ft)) errs.push(`fallen_tab.${py} must be "${v}" (the FE constant)`);
        }
      }
      if (!/if \(p\.tab === 'fallen' && p\.fallenDepth\) q\.set\(FALLEN_DEPTH_PARAM, p\.fallenDepth\);/.test(src)) errs.push("boardQuery must send depth only under p.tab === 'fallen'");
      if ((src.match(/q\.set\(FALLEN_DEPTH_PARAM/g) || []).length !== 1) errs.push('boardQuery must set the depth param in exactly one place');

      const page = read('src/pages/ChartMaps.tsx');
      if (!/tab === 'fallen' && <FallenBoardNote board=\{data\?\.fallen_board \?\? null\} sorts=\{data\?\.sorts\} sort=\{data\?\.sort\} onSort=\{setSortParam\} onDepth=\{setFallenDepth\} \/>/.test(page)) {
        errs.push("ChartMaps.tsx must render <FallenBoardNote board={data?.fallen_board ?? null} sorts={data?.sorts} sort={data?.sort} onSort={setSortParam} onDepth={setFallenDepth} /> on tab === 'fallen'");
      }
      if (!/data\?\.warming && tab === 'fallen' \? null/.test(page)) errs.push('the generic (demand) warming branch must skip the fallen tab — its warming line is served');
      // 2026-10-14: 🎢 high_beta is APPENDED after 'resiliency' (BUILD_SPEC §3.8 WP3) — the pin allows exactly that tail.
      // WIDENED 2026-10-16 — 🕯️ doji_sweep is a board tab after 🚩 (the tail may also carry && tab !== 'doji_sweep').
      if (!/tab !== 'fallen' && tab !== 'resiliency'(?:\s*&& tab !== '(?:high_beta|doji_sweep)')*\);/.test(page)) errs.push('the demand-scan progress poll must skip the fallen tab');
      if (!/\|\| tab === 'fallen' \|\| tab === 'quick_bounce'\) && \(\s*<div className="cm-rules"/.test(page)) errs.push('the ℹ️ Rules mount must include the fallen tab (section "fallen")');
      if (!/<FallenCardExtras tile=\{t\} legend=\{data\?\.fallen_board\?\.pick_legend \?\? null\} \/>/.test(page)) errs.push('the grid must wrap each fallen card with <FallenCardExtras tile={t} legend={data?.fallen_board?.pick_legend ?? null} />');
      if (!/const fallenDepth = tab === 'fallen' \?/.test(page)) errs.push("ChartMaps.tsx must read ?depth= on the fallen tab only");

      const note = read('src/components/FallenBoardNote.tsx');
      const extras = read('src/components/FallenCardExtras.tsx');
      const lib = read('src/lib/fallen.ts');
      const legendUses = (note.match(/<BondeCriteriaLegend\b/g) || []).length;
      if (legendUses !== 1) errs.push(`FallenBoardNote.tsx must render <BondeCriteriaLegend> exactly once — found ${legendUses}`);
      if (/<BondeCriteriaLegend\b/.test(extras) || /<BondeCriteriaLegend\b/.test(page)) errs.push('the Bonde legend renders once for the tab (FallenBoardNote), never per card or again on the page');
      if (!/<BondePickChips\b/.test(extras)) errs.push('FallenCardExtras.tsx must render <BondePickChips> (the 📈 Bonde tab\'s own chips)');
      for (const [f, t] of [['FallenBoardNote.tsx', note], ['FallenCardExtras.tsx', extras], ['lib/fallen.ts', lib]]) {
        if (/5¢|\b25M\b|\b39\b|\b100%|\$10B|10y|157/.test(t)) errs.push(`${f} carries a digit-bearing Bonde threshold — every Bonde number is served`);
        if (/bounce|fake|caused|because/i.test(t)) errs.push(`${f} says bounce / fake / caused / because`);
        if (/n_pass\s*[+\-]|\.filter\([^)]*ok/.test(t)) errs.push(`${f} computes a count over the legs — the count line is served`);
        const code = t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
        if (/toFixed|Math\.|UNMEASURED/.test(code)) errs.push(`${f} composes wording or maths — every sentence and number is printed as served`);
      }
      const ladder = read('src/lib/cardLadder.ts');
      if (!/const PRICE_SUFFIX = \[[^\]]*' below the 52-week high'/.test(ladder)) errs.push("cardLadder PRICE_SUFFIX must carry ' below the 52-week high' (the 📉 pill is a PRICE fact)");

      const nf = read('src/lib/newFeatures.ts');
      const idAt = nf.indexOf("id: 'chart-maps-fallen-2026-10-02'");
      if (idAt < 0) {
        errs.push("newFeatures.ts lost the ✨ entry id: 'chart-maps-fallen-2026-10-02'");
      } else {
        const entry = nf.slice(idAt, nf.indexOf("' },", idAt) + 4);
        if (!entry.includes("route: '/chart-maps?tab=fallen'")) errs.push("the 📉 ✨ entry must route to '/chart-maps?tab=fallen'");
        if (!entry.includes('UNMEASURED')) errs.push('the 📉 ✨ entry must say UNMEASURED');
        for (const h of HIS) if (!entry.includes(h)) errs.push(`the 📉 ✨ entry must quote his ask verbatim: "${h.slice(0, 40)}…"`);
        if (/bounce|fake/i.test(entry)) errs.push('the 📉 ✨ entry says "bounce"/"fake"');
        if (T && !entry.includes(`Every name ${T}% or more under its 52-week high`)) errs.push(`the 📉 ✨ entry's threshold must equal fallen_tab.THRESHOLD_PCT (${T})`);
        if (T && !entry.includes(`The ${T}%, the 52-week reference`)) errs.push(`the 📉 ✨ entry's his-call line must name THRESHOLD_PCT (${T})`);
        if (Y && !entry.includes(`the last ${Y} closed sessions`)) errs.push(`the 📉 ✨ entry's year must equal KL.YEAR_BARS (${Y})`);
        if (D && !entry.includes(`pick ${D.map((x) => String(Number(x))).join(' / ')}%`)) errs.push(`the 📉 ✨ entry's depth steps must equal fallen_tab.DEPTH_STEPS (${D.join(' / ')})`);
      }

      const board = read('../backend/chart_maps/board.py');
      const tabsPy = /^TABS = \(([^)]*)\)/m.exec(board);
      if (!tabsPy || !/"fallen"/.test(tabsPy[1])) errs.push('board.py TABS must carry "fallen"');
      if (!/elif t == "fallen":/.test(board)) errs.push('board.py lost the elif t == "fallen": dispatch');
      if (!/\(t == "fallen" and sort in _FAL\.TAB_SORTS\)/.test(board)) errs.push('board.py must honour the tab-scoped fallen sorts on this tab only');
      if (ft) {
        if (!ft.includes('UNMEASURED')) errs.push('fallen_tab.py must say UNMEASURED');
        if (/bounc|fake/i.test(ft.replace(/quick_bounce/g, ''))) errs.push('fallen_tab.py says "bounce"/"fake"');
        if (!/% below the 52-week high"/.test(ft)) errs.push('fallen_tab.py must serve the 📉 pill as "… below the 52-week high" (the cardLadder PRICE suffix)');
      }
      return errs;
    },
  },
  {
    name: '🔻 Down 10%+ today tab (2026-10-05): mounted after 📉, label = THRESHOLD_PCT, UNMEASURED served, live re-read on the served cadence, the FE composes and counts nothing, never bounce',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-10-03: "I would like to know about stocks that falled intraday
    // more than 10% new tab please."
    // Any of these links lost silently drops the tab, its UNMEASURED word, the
    // one-place threshold (the label and the ✨ number are read off the backend
    // constant, never typed twice), the live re-read, or the rule that the FE
    // prints served sentences and counts nothing.
    checks: (src) => {
      const errs = [];
      const tabs = parseCmTabs(src);
      if (!tabs || !tabs.includes('drop10')) {
        errs.push("CM_TABS must carry 'drop10'");
      } else {
        if (tabs.indexOf('drop10') !== tabs.indexOf('fallen') + 1) errs.push("CM_TABS: 'drop10' must sit right after 'fallen'");
        if (tabs.filter((t) => t === 'drop10').length !== 1) errs.push("CM_TABS lists 'drop10' more than once");
      }
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)));
      let dt = '';
      try { dt = read('../backend/chart_maps/drop10_tab.py'); } catch { errs.push('backend/chart_maps/drop10_tab.py is missing'); }
      const thrM = /^THRESHOLD_PCT = ([0-9.]+)/m.exec(dt);
      const T = thrM ? String(Number(thrM[1])) : null;
      if (dt && !T) errs.push('drop10_tab.py lost THRESHOLD_PCT = <number>');
      const HIS = ['I would like to know about stocks that falled intraday more than 10% new tab please.'];
      const meta = /\n  drop10: \{\n    label: '([^']*)',\n    blurb: '((?:[^'\\]|\\.)*)',/.exec(src);
      if (!meta) {
        errs.push('TAB_META.drop10 (label + blurb) is missing');
      } else {
        if (T && unesc(meta[1]) !== `\u{1F53B} Down ${T}%+ today`) errs.push(`TAB_META.drop10.label "${unesc(meta[1])}" must be "🔻 Down ${T}%+ today" (drop10_tab.THRESHOLD_PCT)`);
        const blurb = meta[2].replace(/\\'/g, "'");
        if (!blurb.includes('UNMEASURED')) errs.push('the TAB_META.drop10 blurb must say UNMEASURED');
        for (const h of HIS) if (!blurb.includes(h)) errs.push(`the TAB_META.drop10 blurb must quote his ask verbatim: "${h.slice(0, 40)}…"`);
        if (/bounce|fake/i.test(blurb)) errs.push('the TAB_META.drop10 blurb says "bounce"/"fake"');
      }
      if (dt && !new RegExp(`^TAB_LABEL = f"\\{MARK\\} Down \\{THRESHOLD_PCT:g\\}%\\+ today"`, 'm').test(dt)) errs.push('drop10_tab.TAB_LABEL must stay f"{MARK} Down {THRESHOLD_PCT:g}%+ today" (== TAB_META.drop10.label)');
      if (/\n  drop10: '/.test(src)) errs.push('ENTERABLE_KIND must NOT carry drop10 (🎯 n/a, the 📉 precedent)');
      for (const [k, v, py] of [['DROP10_SORT_NOW', 'drop10_now', 'SORT_NOW'], ['DROP10_SORT_RECLAIM', 'drop10_reclaim', 'SORT_RECLAIM'], ['DROP10_SORT_RVOL', 'drop10_rvol', 'SORT_RVOL']]) {
        if (!src.includes(`export const ${k} = '${v}';`)) errs.push(`chartMaps.ts must export ${k} = '${v}'`);
        if (dt && !new RegExp(`^${py} = "${v}"`, 'm').test(dt)) errs.push(`drop10_tab.${py} must be "${v}" (the FE constant)`);
      }

      const page = read('src/pages/ChartMaps.tsx');
      if (!/tab === 'drop10' && <Drop10BoardNote board=\{data\?\.drop10_board \?\? null\} sorts=\{data\?\.sorts\} sort=\{data\?\.sort\} onSort=\{setSortParam\} \/>/.test(page)) {
        errs.push("ChartMaps.tsx must render <Drop10BoardNote board={data?.drop10_board ?? null} sorts={data?.sorts} sort={data?.sort} onSort={setSortParam} /> on tab === 'drop10'");
      }
      if (!/data\?\.warming && tab === 'drop10' \? null/.test(page)) errs.push('the generic (demand) warming branch must skip the drop10 tab — its warming line is served');
      if (!/tab !== 'drop10' && tab !== 'fallen'/.test(page)) errs.push('the demand-scan progress poll must skip the drop10 tab');
      if (!/\|\| tab === 'drop10' \|\| tab === 'fallen' \|\| tab === 'quick_bounce'\) && \(\s*<div className="cm-rules"/.test(page)) errs.push('the ℹ️ Rules mount must include the drop10 tab (section "drop10")');
      if (!/<Drop10CardExtras tile=\{t\} \/>/.test(page)) errs.push('the grid must wrap each drop10 card with <Drop10CardExtras tile={t} />');
      if (!/const drop10Every = tab === 'drop10' \? drop10RefreshMs\(data\?\.drop10_board\) : null;/.test(page)) errs.push('ChartMaps.tsx must re-read the live drop10 board on the SERVED cadence (drop10RefreshMs)');

      const note = read('src/components/Drop10BoardNote.tsx');
      const extras = read('src/components/Drop10CardExtras.tsx');
      const lib = read('src/lib/drop10.ts');
      for (const [f, t] of [['Drop10BoardNote.tsx', note], ['Drop10CardExtras.tsx', extras], ['lib/drop10.ts', lib]]) {
        if (/bounce|fake|caused|because/i.test(t)) errs.push(`${f} says bounce / fake / caused / because`);
        const code = t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
        if (/toFixed|UNMEASURED|\b10%/.test(code)) errs.push(`${f} composes wording or types the threshold — every sentence and number is printed as served`);
        if (f !== 'lib/drop10.ts' && /Math\./.test(code)) errs.push(`${f} does maths — every number is printed as served`);
      }

      const nf = read('src/lib/newFeatures.ts');
      const idAt = nf.indexOf("id: 'chart-maps-drop10-2026-10-05'");
      if (idAt < 0) {
        errs.push("newFeatures.ts lost the ✨ entry id: 'chart-maps-drop10-2026-10-05'");
      } else {
        const entry = nf.slice(idAt, nf.indexOf("' },", idAt) + 4);
        if (!entry.includes("route: '/chart-maps?tab=drop10'")) errs.push("the 🔻 ✨ entry must route to '/chart-maps?tab=drop10'");
        if (!entry.includes('UNMEASURED')) errs.push('the 🔻 ✨ entry must say UNMEASURED');
        for (const h of HIS) if (!entry.includes(h)) errs.push(`the 🔻 ✨ entry must quote his ask verbatim: "${h.slice(0, 40)}…"`);
        if (/bounce|fake/i.test(entry)) errs.push('the 🔻 ✨ entry says "bounce"/"fake"');
        if (T && !entry.includes(`${T}% or more under the prior close`)) errs.push(`the 🔻 ✨ entry's threshold must equal drop10_tab.THRESHOLD_PCT (${T})`);
      }

      const board = read('../backend/chart_maps/board.py');
      const tabsPy = /^TABS = \(([^)]*)\)/m.exec(board);
      if (!tabsPy || !/"drop10"/.test(tabsPy[1])) errs.push('board.py TABS must carry "drop10"');
      if (!/elif t == "drop10":/.test(board)) errs.push('board.py lost the elif t == "drop10": dispatch');
      if (!/\(t == "drop10" and sort in _D10\.TAB_SORTS\)/.test(board)) errs.push('board.py must honour the tab-scoped drop10 sorts on this tab only');
      if (dt) {
        if (!dt.includes('UNMEASURED')) errs.push('drop10_tab.py must say UNMEASURED');
        if (/bounc|fake/i.test(dt.replace(/quick_bounce/g, ''))) errs.push('drop10_tab.py says "bounce"/"fake"');
      }
      return errs;
    },
  },
  {
    name: "🚩 Gajjala's tab (2026-10-13): mounted after 🎢, label = constants.TAB_LABEL, subs = constants.SUBS, scanner numbers = constants, four house chips, NO 🧨 toggle in writing, UNMEASURED, shadow pushes said, never bounce",
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-10-13: "Now can you build a new tab and build sub tabs for it
    // with multiple strategies. Name the Tab Gajjala's …" and "Implement his
    // full stategy do not assume anything." Any of these links lost silently
    // drops the tab, its label or sub strip drifting from the backend
    // constants, a scanner number typed twice and wrong, a house chip, the
    // written NO_TOGGLE reason, or the shadow-push truth on the surfaces he
    // reads (DECISIONS Round A: nothing rings until the study reads).
    checks: (src) => {
      const errs = [];
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\'/g, "'");
      const tabs = parseCmTabs(src);
      if (!tabs || !tabs.includes('gajjala')) {
        errs.push("CM_TABS must carry 'gajjala'");
      } else {
        if (tabs.filter((t) => t === 'gajjala').length !== 1) errs.push("CM_TABS lists 'gajjala' more than once");
        // 2026-10-14: 🎢 high_beta took the slot right after 🔻 (A13); 🚩 follows it.
        if (tabs.indexOf('gajjala') !== tabs.indexOf('high_beta') + 1) errs.push("CM_TABS: 'gajjala' must sit right after 'high_beta'");
        // WIDENED 2026-10-16 — 🕯️ doji_sweep is a board tab after 🚩 — 🕯️ took the slot between 🚩 and 〰️.
        if (tabs.indexOf('doji_sweep') !== tabs.indexOf('gajjala') + 1 || tabs.indexOf('ema_frames') !== tabs.indexOf('doji_sweep') + 1) errs.push("CM_TABS: 'doji_sweep' must follow 'gajjala' and 'ema_frames' must follow 'doji_sweep'");
      }
      if (!/&& t !== 'gajjala'/.test(src)) errs.push("isBoardTab must return false for 'gajjala' — it has its own endpoint");
      if (/\n  gajjala: '/.test(src)) errs.push('ENTERABLE_KIND must NOT carry gajjala (🎯 n/a, the 📉 / 🔻 precedent)');

      let gc = '';
      try { gc = read('../backend/chart_maps/gajjala/constants.py'); } catch { errs.push('backend/chart_maps/gajjala/constants.py is missing (WP1)'); }
      const num = (name) => { const m = new RegExp(`^${name} = ([0-9_.]+)`, 'm').exec(gc); return m ? Number(m[1].replace(/_/g, '')) : null; };
      const label = /^TAB_LABEL = "([^"]*)"/m.exec(gc);
      if (gc && !label) errs.push('constants.py lost TAB_LABEL = "<label>"');
      const lo = num('SCAN_MIN_PRICE'), hi = num('SCAN_MAX_PRICE'), vol = num('SCAN_MIN_VOLUME'), chg = num('SCAN_MIN_CHANGE_PCT');
      if (gc && [lo, hi, vol, chg].some((x) => x == null || !Number.isFinite(x))) errs.push('constants.py lost a SCAN_* number (MIN_PRICE / MAX_PRICE / MIN_VOLUME / MIN_CHANGE_PCT)');
      const money = (x) => (x < 1 ? x.toFixed(2) : String(x));
      const scanBits = gc && lo != null && hi != null && vol != null && chg != null
        ? [`$${money(lo)}–$${money(hi)}`, `${vol / 1e6}M+`, `up ${chg}%+`] : [];
      // The other numbers the blurb / ✨ entry print, read from constants.py too
      // (review 2026-10-13: they matched by luck, unpinned). STAY_LISTED_SESSIONS
      // is Ajay's number (CHEETAH_DEFAULTS; GG said "a couple of days", S9
      // 1:17:32), so the sentence carrying it must say so — never read as his.
      const stay = num('STAY_LISTED_SESSIONS'), first = num('NO_TRADE_AFTER_OPEN_MIN'), cad = num('PASS_CADENCE_SEC');
      const openEt = /^PASS_OPEN_ET = "([0-9:]+)"/m.exec(gc);
      const psyM = /^PSY_LEVELS = \(([^)]*)\)/m.exec(gc);
      const psy = psyM ? psyM[1].split(',').map((x) => x.trim()).filter(Boolean).map(Number) : [];
      if (gc && [stay, first, cad].some((x) => x == null || !Number.isFinite(x))) errs.push('constants.py lost STAY_LISTED_SESSIONS / NO_TRADE_AFTER_OPEN_MIN / PASS_CADENCE_SEC');
      if (gc && (!openEt || !psy.length || psy.some((x) => !Number.isFinite(x)))) errs.push('constants.py lost PASS_OPEN_ET = "HH:MM" / PSY_LEVELS = (…)');
      const stayCheetah = /^CHEETAH_DEFAULTS = \(([^)]*)\)/m.exec(gc);
      if (gc && !(stayCheetah && /"STAY_LISTED_SESSIONS"/.test(stayCheetah[1]))) errs.push('constants.CHEETAH_DEFAULTS must carry STAY_LISTED_SESSIONS (Ajay round A: his number, not GG\'s)');
      const psyText = psy.map((x) => `$${money(x)}`).join(' / ');
      const stayText = `stays listed ${stay} sessions (Cheetah default, not his)`;
      const cadText = cad != null ? `every ${cad / 60} minutes` : '';
      // Any of these numbers PRINTED in a sentence must be the constant's; the
      // blurb must print all of them (`need`), the ✨ entry only those it uses.
      const numberChecks = (where, text, need) => {
        const out = [];
        for (const m of text.matchAll(/(\d+) sessions?/g)) {
          if (Number(m[1]) !== stay) out.push(`${where} says "${m[0]}" — constants.STAY_LISTED_SESSIONS is ${stay}`);
        }
        if (/\d+ sessions?/.test(text) && !text.includes(stayText)) out.push(`${where} must say "${stayText}" — the stay is Ajay's number, not GG's`);
        for (const m of text.matchAll(/first[- ](\d+)[- ]minutes/g)) {
          if (Number(m[1]) !== first) out.push(`${where} says "${m[0]}" — constants.NO_TRADE_AFTER_OPEN_MIN is ${first}`);
        }
        for (const m of text.matchAll(/every (\d+) minutes/g)) {
          if (cad != null && Number(m[1]) !== cad / 60) out.push(`${where} says "${m[0]}" — constants.PASS_CADENCE_SEC is ${cad}`);
        }
        for (const m of text.matchAll(/from (\d\d:\d\d) to/g)) {
          if (openEt && m[1] !== openEt[1]) out.push(`${where} says "${m[0]}" — constants.PASS_OPEN_ET is ${openEt[1]}`);
        }
        for (const m of text.matchAll(/\$\d+(?:\.\d+)? \/ \$\d+(?:\.\d+)?(?: \/ \$\d+(?:\.\d+)?)*/g)) {
          if (m[0] !== psyText) out.push(`${where} says "${m[0]}" — constants.PSY_LEVELS is ${psyText}`);
        }
        if (need && gc) {
          for (const b of [stayText, psyText, `first-${first}-minutes`, cadText, `from ${openEt ? openEt[1] : '?'} to`]) {
            if (!text.includes(b)) out.push(`${where} must state "${b}" as constants.py has it`);
          }
        }
        return out;
      };
      let modeSrc = gc;
      if (!/^GAJJALA_PUSH_MODE = "/m.test(modeSrc)) { try { modeSrc = read('../backend/chart_maps/gajjala/alerts.py'); } catch { modeSrc = ''; } }
      const modeM = /^GAJJALA_PUSH_MODE = "([a-z]+)"/m.exec(modeSrc);
      const shadow = !modeM || modeM[1] === 'shadow';
      const HIS = [
        "Name the Tab Gajjala's he has multiple strategies..around this.",
        'Implement his full stategy do not assume anything.',
      ];

      const meta = /\n  gajjala: \{\n    label: "([^"]*)",\n    blurb: '((?:[^'\\]|\\.)*)',/.exec(src);
      if (!meta) {
        errs.push('TAB_META.gajjala (label + blurb) is missing');
      } else {
        if (label && meta[1] !== label[1]) errs.push(`TAB_META.gajjala.label "${meta[1]}" must equal constants.TAB_LABEL "${label[1]}"`);
        const blurb = unesc(meta[2]);
        if (!blurb.includes('UNMEASURED')) errs.push('the TAB_META.gajjala blurb must say UNMEASURED');
        for (const h of HIS) if (!blurb.includes(h)) errs.push(`the TAB_META.gajjala blurb must quote his ask verbatim: "${h.slice(0, 40)}…"`);
        if (/bounce|fake/i.test(blurb)) errs.push('the TAB_META.gajjala blurb says "bounce"/"fake"');
        for (const b of scanBits) if (!blurb.includes(b)) errs.push(`the TAB_META.gajjala blurb must state the scanner as constants.py has it: "${b}"`);
        errs.push(...numberChecks('the TAB_META.gajjala blurb', blurb, true));
        if (shadow && !/shadow/i.test(blurb)) errs.push('pushes are SHADOW (GAJJALA_PUSH_MODE) — the TAB_META.gajjala blurb must say so');
        if (shadow && /phone rings on every/i.test(blurb)) errs.push('the TAB_META.gajjala blurb promises a ring while pushes are shadow');
      }

      const page = read('src/pages/ChartMaps.tsx');
      const at = page.indexOf("tab === 'gajjala' ? (");
      const fb = page.indexOf('!isBoardTab(tab) ? (');
      if (at < 0 || !/<GajjalaBoard \/>/.test(page)) errs.push("ChartMaps.tsx must mount tab === 'gajjala' ? (<GajjalaBoard />)");
      else if (fb >= 0 && at > fb) errs.push('the gajjala mount must sit BEFORE the SupportLevels fallback (!isBoardTab)');

      const board = read('src/components/GajjalaBoard.tsx');
      for (const c of ['GrowthChip', 'ShortInterestChip', 'ExplosiveChip', 'EnterableChip', 'PatternChart']) {
        if (!new RegExp(`<${c}\\s`).test(board)) errs.push(`GajjalaBoard must render <${c}>`);
      }
      if (/<ExplosiveFirstToggle\s/.test(board)) errs.push('GajjalaBoard mounts <ExplosiveFirstToggle> — his setup state orders this board (NO_TOGGLE)');
      if (!/useBounceRoom\(/.test(board)) errs.push('GajjalaBoard must read the 🧨 / 🎯 chips from ONE page-level useBounceRoom map');
      if (!/<RulesInfo section=/.test(board)) errs.push('GajjalaBoard must mount the ℹ️ <RulesInfo section="gajjala" />');
      const lib = read('src/lib/gajjala.ts');
      let css = '';
      try { css = read('src/styles/gajjala.css'); } catch { errs.push('src/styles/gajjala.css is missing'); }
      for (const [f, t] of [['GajjalaBoard.tsx', board.replace(/useBounceRoom|BounceRoom|bounceRoom/g, '')], ['lib/gajjala.ts', lib], ['styles/gajjala.css', css]]) {
        if (/bounce|fake/i.test(t)) errs.push(`${f} says bounce / fake — surfaces he reads say reversal`);
      }

      // GG_SUBS == constants.SUBS, key / emoji / label, in order.
      const subsTs = /export const GG_SUBS[^=]*=\s*\[([\s\S]*?)\n\];/.exec(lib);
      const ts = subsTs ? [...subsTs[1].matchAll(/\{ key: '([a-z_]+)', emoji: '([^']+)', label: '([^']+)' \}/g)].map((m) => [m[1], unesc(m[2]), m[3]]) : [];
      const subsPy = /^SUBS = \(([\s\S]*?)\)\n/m.exec(gc);
      const py = subsPy ? [...subsPy[1].matchAll(/\(\s*"([a-z_]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)/g)].map((m) => [m[1], m[2], m[3]]) : [];
      if (!ts.length) errs.push('lib/gajjala.ts GG_SUBS not found');
      if (gc && !py.length) errs.push('constants.py lost SUBS = (("key", "emoji", "label"), …)');
      if (ts.length && py.length && JSON.stringify(ts) !== JSON.stringify(py)) {
        errs.push(`lib/gajjala.ts GG_SUBS ${JSON.stringify(ts)} != constants.SUBS ${JSON.stringify(py)}`);
      }

      const nf = read('src/lib/newFeatures.ts');
      const idAt = nf.indexOf("id: 'chart-maps-gajjala-2026-10-13'");
      if (idAt < 0) {
        errs.push("newFeatures.ts lacks the ✨ entry id: 'chart-maps-gajjala-2026-10-13'");
      } else {
        const entry = unesc(nf.slice(idAt, nf.indexOf('" },', idAt) + 4));
        if (!entry.includes("route: '/chart-maps?tab=gajjala'")) errs.push("the 🚩 ✨ entry must route to '/chart-maps?tab=gajjala'");
        if (!entry.includes('UNMEASURED')) errs.push('the 🚩 ✨ entry must say UNMEASURED');
        for (const h of HIS) if (!entry.includes(h)) errs.push(`the 🚩 ✨ entry must quote his ask verbatim: "${h.slice(0, 40)}…"`);
        if (/bounce|fake/i.test(entry)) errs.push('the 🚩 ✨ entry says "bounce"/"fake"');
        for (const b of scanBits.slice(0, 1).concat(scanBits.slice(1).map((x) => x.replace(/^up /, '')))) {
          if (!entry.includes(b.replace(/M\+$/, 'M+'))) errs.push(`the 🚩 ✨ entry must state the scanner as constants.py has it: "${b}"`);
        }
        errs.push(...numberChecks('the 🚩 ✨ entry', entry, false));
        if (shadow && !/shadow/i.test(entry)) errs.push('pushes are SHADOW (GAJJALA_PUSH_MODE) — the 🚩 ✨ entry must say so');
        if (shadow && /phone rings on every/i.test(entry)) errs.push('the 🚩 ✨ entry promises a ring while pushes are shadow');
      }
      return errs;
    },
  },
  {
    // WIDENED 2026-10-16 — Ajay flipped the A+ kind live ("you alert me when that happens", DECISIONS10 D1); default_prefs stays False (AMENDMENTS10 F1).
    name: '🚩 gajjala_setup push kind (2026-10-13; LIVE since 2026-10-16): declared in every registry, default off (AMENDMENTS10 F1) + owner keep-set coherent, MARKET kind, /alerts row, the mode said, never the b-word',
    file: 'src/lib/alertKinds.ts',
    // DECISIONS 2026-10-13: owner-only kind `gajjala_setup`, A+ only, pref in
    // push/subs.py, wrapper in push/hooks.py, keep-set + /alerts row — and
    // SHADOW first (GAJJALA_PUSH_MODE): recorded, nothing sent. A kind missing
    // from any registry sends to zero devices in silence (memory
    // cheetah_push_silent_drops) or renders a raw id on the bell. This block
    // passes once WP4 lands its half.
    checks: (src) => {
      const errs = [];
      if (!/\bgajjala_setup:/.test(src)) errs.push('alertKinds.ts must register gajjala_setup or the bell renders a raw id');
      if (!/gajjala_setup\?: boolean/.test(read('src/hooks/useNotificationPrefs.ts'))) errs.push('NotificationPrefs must carry gajjala_setup?: boolean');
      const notif = read('src/pages/Notifications.tsx');
      const nm = notif.match(/key: 'gajjala_setup'[\s\S]*?\},\n/);
      if (!nm) errs.push('gajjala_setup must be listed on the Notifications page — a kind the page cannot show cannot be muted');
      const d = nm ? nm[0] : '';
      if (nm && !/NOT MEASURED|UNMEASURED/.test(d)) errs.push('the gajjala_setup Notifications entry must say NOT MEASURED / UNMEASURED');
      if (nm && /bounce/i.test(d)) errs.push('the gajjala_setup Notifications entry says "bounce"');
      const subs = read('../backend/push/subs.py');
      const dm = subs.match(/["']gajjala_setup["']\s*:\s*(True|False)/);
      if (!dm) errs.push('push/subs.py default_prefs must list "gajjala_setup"');
      if (dm && dm[1] !== 'False') errs.push('gajjala_setup must be False in push/subs.py default_prefs — everyone else starts off');
      const gate = read('../backend/market_hours/gate.py');
      if (!(pyFrozenSet(gate, 'MARKET_ALERT_KINDS') || []).includes('gajjala_setup')) errs.push('market_hours/gate.py must treat gajjala_setup as a MARKET kind (silent on closed days)');
      if ((pyFrozenSet(gate, 'PERSONAL_KINDS') || []).includes('gajjala_setup')) errs.push('gajjala_setup must NOT be a PERSONAL kind');
      const ess = notif.slice(notif.indexOf("id: 'essentials'"), notif.indexOf("id: 'trading_only'"));
      if (keepSet(subs).includes('gajjala_setup')) {
        if (nm && !d.includes('ON FOR YOUR PHONE')) errs.push('gajjala_setup is in OWNER_KEEP_SET — the Notifications entry must say ON FOR YOUR PHONE');
        if (!/gajjala_setup:\s*true/.test(ess)) errs.push('gajjala_setup is in OWNER_KEEP_SET — Essentials must carry gajjala_setup: true');
      } else {
        if (nm && !d.includes('OFF BY DEFAULT')) errs.push('gajjala_setup is NOT in OWNER_KEEP_SET — the Notifications entry must say OFF BY DEFAULT');
        if (!/gajjala_setup:\s*false/.test(ess)) errs.push('gajjala_setup is NOT in OWNER_KEEP_SET — Essentials must carry gajjala_setup: false');
      }
      if (!/key: 'gajjala_setup'/.test(read('src/pages/Alerts.tsx'))) errs.push("Alerts.tsx PASSES must carry key: 'gajjala_setup'");
      let mode = '';
      for (const f of ['../backend/chart_maps/gajjala/constants.py', '../backend/chart_maps/gajjala/alerts.py']) {
        try { const m = /^GAJJALA_PUSH_MODE = "([a-z]+)"/m.exec(read(f)); if (m) { mode = m[1]; break; } } catch { /* WP1 / WP4 not landed */ }
      }
      if (!mode) errs.push('GAJJALA_PUSH_MODE = "shadow" | "live" not found in chart_maps/gajjala/constants.py or alerts.py');
      if (mode === 'shadow' && nm && !/shadow/i.test(d)) errs.push('GAJJALA_PUSH_MODE is "shadow" — the Notifications entry must say nothing is sent yet (shadow)');
      return errs;
    },
  },
  {
    name: '🔥 Hottest: every column reachable, multi-sort, ⓘ Quality (2026-09-28)',
    file: 'src/components/HottestSectors.tsx',
    // Ajay 2026-09-28: "Can you fix the horizontal columns hiding and also can
    // you help me with multi column sort also can you help with info icon on
    // the quality?" Three things must not silently revert:
    //   1. the ROOT CAUSE fix — the scroll wrapper is the direct flex child of
    //      `.hs` and stretches to it, so the box scrolls sideways inside
    //      itself instead of growing past the page and being cut by html's
    //      overflow-x: hidden; Sector / Name is sticky; full-width rows pin
    //      their text to the visible box;
    //   2. the multi-sort is a SERVER sort — one extra `then_by` param, every
    //      mark drawn from the served plan, no client sort;
    //   3. the ⓘ prints only the SERVED explainer — no number or citation is
    //      typed into the component.
    checks: (tsx) => {
      const errs = [];
      const css = read('src/styles.css');
      const rule = (sel) => {
        const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const m = new RegExp(`(?:^|\\n)${esc}\\s*\\{([^}]*)\\}`).exec(css);
        return m ? m[1] : null;
      };
      const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

      // 1 · layout
      const wrap = rule('.hs-scrollwrap');
      if (!wrap) errs.push('styles.css has no .hs-scrollwrap rule');
      else {
        for (const d of [/align-self:\s*stretch/, /min-width:\s*0/, /max-width:\s*100%/]) {
          if (!d.test(wrap)) errs.push(`.hs-scrollwrap lost ${d.source} — the box shrink-wraps the table again and the page cuts its right edge`);
        }
      }
      const scroll = rule('.hs-scroll');
      if (!scroll || !/min-width:\s*0/.test(scroll) || !/max-width:\s*100%/.test(scroll)) {
        errs.push('.hs-scroll must keep min-width: 0 and max-width: 100% — it may never grow past its wrapper');
      }
      const symRule = /\.hs-table[^{,]*td\.hs-sym[^{]*\{([^}]*)\}/.exec(css);
      if (!symRule || !/position:\s*sticky/.test(symRule[1]) || !/left:\s*0/.test(symRule[1])
          || !/background:/.test(symRule[1])) {
        errs.push('td.hs-sym under .hs-table must be `position: sticky; left: 0` with an opaque background — Sector / Name holds while the columns scroll');
      }
      const theadZ = /z-index:\s*(\d+)/.exec(rule('.hs-table thead th') || '');
      const cornerZ = /z-index:\s*(\d+)/.exec(rule('.hs-table thead th.hs-sym') || '');
      if (!theadZ || !cornerZ || !(Number(cornerZ[1]) > Number(theadZ[1]))) {
        errs.push('.hs-table thead th.hs-sym must sit ABOVE the other sticky headers (the corner of both sticky axes)');
      }
      if (!/\.hs-scrollwrap\.is-more-right::after\s*\{/.test(css)) errs.push('the "more columns" fade rule is gone');
      const pin = rule('.hs-rowpin');
      if (!pin || !/position:\s*sticky/.test(pin) || !/left:\s*0/.test(pin)
          || !/max-width:\s*calc\(var\(--hs-box-w/.test(pin)) {
        errs.push('.hs-rowpin must be sticky left:0 with max-width read from var(--hs-box-w — full-width rows ran across the whole table');
      }
      if (/--hs-box-w/.test(tsx)) {
        errs.push('HottestSectors.tsx must never type --hs-box-w — the hook owns it, and the hs-* sweep would demand a .hs-box-w rule');
      }
      for (const sel of ['.hs', '.hs-scrollwrap', '.hs-scroll', '.cm-page']) {
        const esc = sel.replace(/[.]/g, '\\.');
        for (const m of css.matchAll(new RegExp(`(?:^|\\n)${esc}\\s*\\{([^}]*)\\}`, 'g'))) {
          if (/overflow(-x)?:\s*(hidden|clip)/.test(m[1])) {
            errs.push(`${sel} clips its overflow — that is exactly how Next ER was cut`);
          }
        }
      }
      const iWrap = tsx.indexOf('className={`hs-scrollwrap');
      const iScroll = tsx.indexOf('<div className="hs-scroll"');
      if (iWrap < 0 || iScroll < 0 || iWrap > iScroll) {
        errs.push('the .hs-scrollwrap wrapper must enclose .hs-scroll — the stretch only works on the DIRECT flex child');
      }
      const cue = /useHScrollCue\([\s\S]*?\[([^\]]*)\]\)/.exec(tsx);
      if (!cue || !/\bopen\b/.test(cue[1]) || !/\bbyIndustry\b/.test(cue[1])) {
        errs.push('useHScrollCue must re-measure on `open` and `byIndustry` — opening a group widens the TABLE, not the box');
      }

      // 2 · multi-sort
      if (!/const thenKey = thenByParam\(thenBy\)/.test(tsx)
          || !/&dir=\$\{dir\}`\s*\n\s*\+ thenKey/.test(tsx)) {
        errs.push('thenByParam(thenBy) must be appended to the pinned sort/dir fetch');
      }
      if (!/sortBasis\(shownSort,/.test(tsx)) errs.push('the header must draw from sortBasis(shownSort, …)');
      if (!/sortMark\(c\.key, basisPlan\.sort, basisPlan\.dir, basisPlan\.thenBy\)/.test(tsx)) {
        errs.push('the header marks must be sortMark(…basisPlan…) — the SERVED plan, never a guessed client state');
      }
      if (!/const on = basisPlan\.sort === c\.key/.test(tsx)) {
        errs.push('is-sorted / aria-sort must sit on basisPlan.sort — the SERVED primary (critic 2026-09-28: a failed click left "Quality 1▲" over 5-day rows)');
      }
      if (/colLabel\(shownSort, data\)/.test(tsx)) {
        errs.push('"ranked on" must print basisPlan.sort — shownSort is the request after a failed read');
      }
      if (!/aria-sort=\{on \? \(basisPlan\.dir === 'desc'/.test(tsx)) {
        errs.push('aria-sort must read basisPlan.dir, and sit on the primary only');
      }
      const lib = read('src/lib/hottestSort.ts');
      const libCode = strip(lib);
      if (/\.sort\(/.test(libCode)) errs.push('hottestSort.ts must not sort anything — the server sorts before it truncates');
      if (/new Date\(|Date\.now\(/.test(libCode)) errs.push('hottestSort.ts must not read a clock');
      const fnBody = (name) => {
        const i = libCode.indexOf(`export function ${name}(`);
        if (i < 0) return null;
        const open = libCode.indexOf('{\n', libCode.indexOf(')', i));
        let depth = 0;
        for (let j = open; j < libCode.length; j++) {
          if (libCode[j] === '{') depth++;
          else if (libCode[j] === '}' && --depth === 0) return libCode.slice(open, j + 1);
        }
        return null;
      };
      for (const fn of ['shownThenBy', 'sortBasis']) {
        const b = fnBody(fn);
        if (!b) errs.push(`hottestSort.ts lost export function ${fn}`);
        else if (/\bset[A-Z]\w*\(/.test(b)) errs.push(`${fn} must be pure — a set* call there is a second fan-out`);
      }
      if (!/d\.sorted_by/.test(fnBody('sortBasis') || '')) {
        errs.push('sortBasis must take the settled PRIMARY from the served sorted_by, not the client state');
      }
      const py = read('../backend/rotation/hottest.py');
      const pyMax = /^MAX_SORT_KEYS\s*=\s*(\d+)/m.exec(py);
      const feMax = /export const HS_MAX_SORT_KEYS = (\d+);/.exec(lib);
      if (!pyMax || !feMax || pyMax[1] !== feMax[1]) {
        errs.push(`HS_MAX_SORT_KEYS (${feMax?.[1]}) must equal hottest.py MAX_SORT_KEYS (${pyMax?.[1]})`);
      }
      const pyDef = /^DEFAULT_SORT\s*=\s*"([a-z0-9_]+)"/m.exec(py);
      const feDef = /export const HS_DEFAULT_SORT = '([a-z0-9_]+)';/.exec(lib);
      if (!pyDef || !feDef || pyDef[1] !== feDef[1]) {
        errs.push(`HS_DEFAULT_SORT (${feDef?.[1]}) must equal hottest.py DEFAULT_SORT (${pyDef?.[1]})`);
      }
      if (!/then_by: str = Query\(/.test(read('../backend/rotation/api.py'))) {
        errs.push('GET /rotation/hottest must accept then_by: str = Query(…)');
      }

      // 3 · ⓘ Quality
      const qi = read('src/components/HottestQualityInfo.tsx');
      const qiCode = strip(qi);
      const bigNum = qiCode.match(/(?<![\w.#-])(?:[2-9]|\d{2,})(?:\.\d+)?(?![\w])/g);
      if (bigNum) errs.push(`HottestQualityInfo.tsx types a number (${bigNum.slice(0, 3).join(', ')}) — every number in the ⓘ is served`);
      if (/p\.\s?\d|Minervini|chapter|book|week/i.test(qiCode)) {
        errs.push('HottestQualityInfo.tsx carries a citation or a cadence — every word of the ⓘ is served');
      }
      if (!/<InfoButton inline sheet/.test(tsx)) errs.push('the Quality ⓘ must be an InfoButton `sheet` — an absolute pop is clipped by the scroll box');
      const pol = read('src/styles/polish.css');
      const sheet = /\.info-button__pop\.info-button__pop--sheet\s*\{([^}]*)\}/.exec(pol);
      if (!sheet || !/position:\s*fixed/.test(sheet[1])) errs.push('.info-button__pop--sheet must be position: fixed');
      const qiClasses = new Set();
      for (const m of qi.replace(/data-testid=\{?[`'"][^`'"]*[`'"]\}?/g, '').matchAll(/hs-[a-z0-9-]+/g)) qiClasses.add(m[0]);
      if (!qiClasses.size) errs.push('no hs-* classes in HottestQualityInfo.tsx — did it get renamed?');
      for (const c of qiClasses) {
        if (!new RegExp(`\\.${c}(?![\\w-])`).test(css)) errs.push(`styles.css has no rule for .${c} (HottestQualityInfo.tsx)`);
      }

      if (!/id: 'hottest-multisort-quality-2026-09-28'/.test(read('src/lib/newFeatures.ts'))) {
        errs.push('the change needs its ✨ entry');
      }
      if (!exists('scripts/hottest-layout-probe.mjs')) errs.push('scripts/hottest-layout-probe.mjs is gone — the only real-browser check of the fix');
      for (const f of ['src/lib/hottestSort.ts', 'src/hooks/useHScrollCue.ts',
                       'src/components/HottestQualityInfo.tsx', 'scripts/hottest-layout-probe.mjs']) {
        if (exists(f) && /\bbounce\b/i.test(read(f))) errs.push(`${f} says "bounce" — surfaces he reads say "reversal"`);
      }
      return errs;
    },
  },
  {
    name: '📌 Chart Maps tab strip stays pinned, keeps the active tab in view, and a return lands where he was (2026-09-28)',
    file: 'src/pages/ChartMaps.tsx',
    // Ajay 2026-09-28: "Pin the tab I am in, as I navigate back and fort lost
    // where I am". Three parts: a sticky wrapper around the strip, the active
    // tab scrolled into view inside the strip only (never the page), and a
    // one-shot sessionStorage record — armed by leaving for a ticker page —
    // that restores the same tab and place after the board renders.
    // docs/chart_maps/pinned_tab_strip_2026_09_28.md.
    checks: (src) => {
      const errs = [];
      const at = src.indexOf('<div className="cm-tabs" role="tablist">');
      if (at < 0) return ['the cm-tabs strip could not be found'];
      if (!src.slice(Math.max(0, at - 400), at).includes('className={`cm-tabs-bar')) {
        errs.push('the strip must sit inside the sticky .cm-tabs-bar wrapper (within 400 chars above it)');
      }
      if (src.includes('.scrollIntoView(')) {
        errs.push('ChartMaps.tsx must not call scrollIntoView — it scrolls the WINDOW vertically when the strip is off-screen');
      }
      for (const n of ['revealActiveTab', 'takeCmScroll', 'saveCmScroll', 'snapshotCmScroll', 'restoreCmScroll', 'leaveAction(window.location.pathname']) {
        if (!src.includes(n)) errs.push(`ChartMaps.tsx must use ${n}`);
      }
      if (!src.includes('if (isBoardTab(tab) && (loading || !tiles.length)) return;')) {
        errs.push('the restore must wait for the board to render: `if (isBoardTab(tab) && (loading || !tiles.length)) return;`');
      }
      const reveals = (src.match(/syncStrip\(true\)/g) || []).length;
      if (reveals !== 1) errs.push(`exactly one syncStrip(true) (the mount / tab-change layout effect), found ${reveals}`);
      if (!src.includes('new RO(() => syncStrip(false))')) {
        errs.push('the strip ResizeObserver must call syncStrip(false) — a resize never snaps the strip back');
      }
      if (!/const setTab = \(t: CmTab\) => \{\s*setParams\(new URLSearchParams\(tabSearch\(params, t\)\), \{ replace: true \}\);/.test(src)) {
        errs.push('setTab must keep `replace` history (HIS CALL #2 default)');
      }
      // Comments stripped: the rule's own comment names the cycle it forbids.
      const css = read('src/styles.css').replace(/\/\*[\s\S]*?\*\//g, '');
      const bar = /\.cm-tabs-bar \{([^}]*)\}/.exec(css);
      if (!bar) errs.push('styles.css lost the .cm-tabs-bar rule');
      else {
        for (const d of ['position: sticky', 'top: var(--sticky-top, 0px)', 'background: var(--bg)', 'z-index: 30']) {
          if (!bar[1].includes(d)) errs.push(`.cm-tabs-bar must have \`${d}\``);
        }
      }
      if (!/\.cm-tabs-bar ~ \* \{[^}]*--sticky-top: calc\(var\(--cm-nav-top/.test(css)) {
        errs.push('boards under the strip must read --sticky-top from --cm-nav-top + --cm-tabs-h');
      }
      if (css.includes('--sticky-top: calc(var(--sticky-top')) {
        errs.push('`--sticky-top: calc(var(--sticky-top …` is a custom-property cycle — every inner sticky header falls back to 0');
      }
      const th = /\.cm-tabs-bar ~ \* :is\(([^)]*)\) > thead \{ top: var\(--sticky-top, 0px\); \}/.exec(css);
      if (!th || !/\.pb-table/.test(th[1]) || !/\.cat-tl-table/.test(th[1])) {
        errs.push('the POTUS .pb-table and Catalysts .cat-tl-table theads must stick below the strip');
      } else {
        for (const bad of ['nt-table', 'og__table', 'sl-table', 'gnt-table', 'hs-table', 'eg-table']) {
          if (th[1].includes(bad)) errs.push(`.${bad} sits in its own overflow box — an offset pushes its header over its own rows`);
        }
      }
      if (/\.cm-(?:tabs-bar ~ \*|page)\s+thead\s*\{/.test(css)) {
        errs.push('no blanket Chart Maps thead offset — tables in their own scroll box would get their header pushed over their rows');
      }
      const fade = /\.cm-tabs-fade \{([^}]*)\}/.exec(css);
      if (!fade || !fade[1].includes('var(--cm-tabs-sb')) errs.push('.cm-tabs-fade must stop above a classic scrollbar (var(--cm-tabs-sb))');
      if (!/\.cm-head \{[^}]*z-index: 31/.test(css)) errs.push('.cm-head needs z-index: 31 so the ℹ️ panel paints above the strip');
      const lib = read('src/lib/cmPinnedTab.ts');
      if (!lib.includes('export const CM_SCROLL_MAX_AGE_MS = 30 * 60 * 1000;')) errs.push('CM_SCROLL_MAX_AGE_MS must stay 30 min');
      if (!lib.includes('export const CM_TICKER_PATH_RE = /^\\/sepa\\/[^/?#]+/;')) errs.push('CM_TICKER_PATH_RE must be the /sepa/:symbol route');
      const take = /export function takeCmScroll\([\s\S]*?\n\}/.exec(lib);
      if (!take || !take[0].includes('removeItem(CM_SCROLL_KEY)')) errs.push('takeCmScroll must remove the record (one-shot)');
      const cm = read('src/lib/chartMaps.ts');
      const order = parseCmTabs(cm);
      if (!order || order[0] !== 'zones') errs.push('CM_TABS[0] must stay zones (Back in Demand)');
      if (!cm.includes('export const DEFAULT_TAB: CmTab = CM_TABS[0];')) errs.push('DEFAULT_TAB must stay CM_TABS[0]');
      return errs;
    },
  },
  {
    name: 'the 📈 Bonde table is dense and contained — every cell holds its own content (2026-09-28)',
    file: 'src/components/BondeBoard.tsx',
    // Ajay 2026-09-28: "Once done can you fix this table too? so much empty
    // space". jsdom loads no stylesheet, so the CSS half of the fix is pinned
    // here and measured by scripts/bonde-layout-probe.mjs in headless Chrome.
    // docs/sepa/bonde_table_density_2026_09_28.md
    checks: (src) => {
      const errs = [];
      // ── TSX ───────────────────────────────────────────────────────────────
      if (!/className="bd-scroll"[\s\S]{0,200}className=\{`bd-rows/.test(src)) {
        errs.push('each section must wrap .bd-rows in a .bd-scroll box — html overflow-x:hidden cuts a wide table');
      }
      if (!src.includes('className="bd-sym-l1"')) errs.push('the ticker cell lost line 1 (.bd-sym-l1)');
      const l2 = src.indexOf('className="bd-sym-l2"');
      if (l2 < 0) errs.push('the ticker cell lost line 2 (.bd-sym-l2)');
      if (l2 >= 0 && src.indexOf('<BondePickChips', l2) < 0) errs.push('<BondePickChips must come after .bd-sym-l2 (line 3)');
      if (!/pivotColumnEmpty\(all\)/.test(src)) errs.push('the EP collapse must be computed as pivotColumnEmpty(all)');
      // (the declaration `pivotColumnEmpty(rows: …)` is a parameter, not a call)
      if (/pivotColumnEmpty\((s\.)?rows\b(?!\s*:)|pivotColumnEmpty\(part/.test(src)) {
        errs.push('the collapse must read the SERVED rows — a filter must never narrow the column');
      }
      if (!src.includes('aria-label={HEADS.pivot.text}')) errs.push('the EP head must keep aria-label={HEADS.pivot.text}');
      const hs = src.indexOf('className="bd-row bd-hdr"');
      const he = src.indexOf('{s.rows.map', hs);
      const hdr = hs >= 0 && he > hs ? src.slice(hs, he) : '';
      const nHead = (hdr.match(/className=\{?["'`]bd-(sym|today|since|sales|chips|pivot|metrics)\b/g) || []).length;
      if (nHead !== 7) errs.push(`the head row must carry exactly 7 cells (found ${nHead})`);

      // ── CSS ───────────────────────────────────────────────────────────────
      const css = read('src/styles.css').replace(/\/\*[\s\S]*?\*\//g, '');
      const rules = [];
      {
        const stack = [];
        let i = 0;
        for (;;) {
          const o = css.indexOf('{', i);
          const c = css.indexOf('}', i);
          if (c < 0 && o < 0) break;
          if (o < 0 || (c >= 0 && c < o)) { stack.pop(); i = c + 1; continue; }
          const pre = css.slice(i, o).split(';').pop().trim();
          if (pre.startsWith('@')) { stack.push(pre); i = o + 1; continue; }
          const q = css.indexOf('}', o);
          rules.push({ sels: pre.split(',').map((x) => x.replace(/\s+/g, ' ').trim()),
                       body: css.slice(o + 1, q), media: stack[stack.length - 1] || null });
          i = q + 1;
        }
      }
      const exact = (sel) => rules.filter((r) => r.sels.length === 1 && r.sels[0] === sel);
      const listed = (sel) => rules.filter((r) => r.sels.includes(sel));
      const has = (rs, re) => rs.some((r) => re.test(r.body));
      // (a) ONE track template
      const tracks = exact('.bd-row').filter((r) => /grid-template-columns/.test(r.body));
      if (tracks.length !== 1) {
        errs.push(`exactly ONE .bd-row rule may set grid-template-columns (found ${tracks.length}) — a stale track layer is back`);
      } else {
        const v = /grid-template-columns:\s*([^;]*)/.exec(tracks[0].body)[1].trim();
        const parts = []; let depth = 0; let cur = '';
        for (const ch of v) {
          if (ch === '(') depth++;
          if (ch === ')') depth--;
          if (/\s/.test(ch) && depth === 0) { if (cur) parts.push(cur); cur = ''; } else cur += ch;
        }
        if (cur) parts.push(cur);
        if (parts.length !== 7) errs.push(`the .bd-row track list must have 7 entries (found ${parts.length})`);
      }
      // (b) heads never hidden
      if (has(listed('.bd-row.bd-hdr'), /display:\s*none/)) errs.push('no rule may hide .bd-row.bd-hdr — unlabelled numbers are the bug');
      // (c) the scroll box
      const sc = exact('.bd-scroll');
      if (!has(sc, /overflow-x:\s*auto/) || !has(sc, /min-width:\s*0/)) errs.push('.bd-scroll must have overflow-x: auto and min-width: 0');
      // (d) the min-width sum lives on .bd-rows
      const rw = exact('.bd-rows').find((r) => /min-width:\s*calc\(/.test(r.body));
      if (!rw) errs.push('.bd-rows must carry min-width: calc(…) over the track widths');
      else {
        for (const v of ['sym', 'today', 'since', 'sales', 'char', 'pivot', 'metrics']) {
          if (!rw.body.includes(`--bd-w-${v}`)) errs.push(`.bd-rows min-width must name --bd-w-${v}`);
        }
      }
      // (e) the EP collapse
      if (!has(exact('.bd-rows.bd-rows--pivot-empty'), /--bd-w-pivot\s*:/)) errs.push('.bd-rows.bd-rows--pivot-empty must set --bd-w-pivot');
      // (f) the scoped wrap
      const wrap = listed('.bd-sym .cm-badge');
      if (!has(wrap, /white-space:\s*normal/) || !has(wrap, /overflow-wrap:\s*anywhere/)) {
        errs.push('.bd-sym .cm-badge must wrap (white-space: normal; overflow-wrap: anywhere) — the 🪜 sentence painted over Today');
      }
      // (g)
      if (!has(exact('.bd-row > *'), /min-width:\s*0/)) errs.push('.bd-row > * must have min-width: 0');
      // (h) sticky + opaque
      const pin = exact('.bd-row > .bd-sym');
      for (const [re, what] of [[/position:\s*sticky/, 'position: sticky'], [/left:\s*0/, 'left: 0'],
                                [/z-index:\s*1\b/, 'z-index: 1'], [/background:\s*var\(--bg/, 'background: var(--bg)']]) {
        if (!has(pin, re)) errs.push(`.bd-row > .bd-sym must have ${what}`);
      }
      // (i) the overlapping-head rule is gone
      if (rules.some((r) => r.sels.some((x) => /\.bd-m\b/.test(x)) && /min-width:\s*52px/.test(r.body))) {
        errs.push('a .bd-m rule has min-width: 52px again — that is what made the metric heads overlap');
      }
      if (!has(exact('.bd-row.bd-hdr .bd-m'), /white-space:\s*normal/)) errs.push('.bd-row.bd-hdr .bd-m must have white-space: normal (heads wrap, never overlap)');
      // (j)
      const mt = exact('.bd-metrics');
      if (!has(mt, /display:\s*grid/) || !has(mt, /repeat\(4,/)) errs.push('.bd-metrics must be a 4-column grid (display: grid; repeat(4, …))');
      // (k) NEGATIVE: the base pill is untouched
      if (!has(exact('.cm-badge').filter((r) => !r.media), /white-space:\s*nowrap/)) {
        errs.push('the base .cm-badge rule must keep white-space: nowrap — the wrap fix is scoped to .bd-sym');
      }
      // (l)
      if (!has(exact('.bd-sym-l2:empty'), /display:\s*none/)) errs.push('.bd-sym-l2:empty must be display: none');
      // (m)
      const base = exact('.bd-row').filter((r) => !r.media && /display:\s*grid/.test(r.body));
      if (!has(base, /align-items:\s*start/)) errs.push('the base .bd-row block must be align-items: start (each row reads across on its first line)');
      if (has(exact('.bd-row'), /align-items:\s*center/)) errs.push('a .bd-row rule is align-items: center again');
      // (n) "▸ all N" in the Ticker cell: two tracks at EVERY width, entries
      //     3+ (value / source / link) pinned to the second track. Five tracks
      //     in the cell broke the fold letter by letter (critic 2026-09-28).
      const pr = exact('.bd-sym .bd-pick-row').filter((r) => !r.media);
      if (!has(pr, /grid-template-columns:\s*14px\s+minmax\(0,\s*1fr\)\s*(;|$)/)) {
        errs.push('.bd-sym .bd-pick-row must be grid-template-columns: 14px minmax(0, 1fr) at every width');
      }
      if (!has(exact('.bd-sym .bd-pick-row > :nth-child(n+3)'), /grid-column:\s*2\b/)) {
        errs.push('.bd-sym .bd-pick-row > :nth-child(n+3) must be grid-column: 2 — auto-placement drops every other entry into the 14px glyph track');
      }
      // NEGATIVE: no .bd-sym .bd-pick-row rule, in any media block, brings back a 3+ track template
      for (const r of listed('.bd-sym .bd-pick-row')) {
        const m = /grid-template-columns:\s*([^;]*)/.exec(r.body);
        if (!m) continue;
        const n = m[1].trim().replace(/\([^)]*\)/g, '()').split(/\s+/).filter(Boolean).length;
        if (n > 2) errs.push(`.bd-sym .bd-pick-row has a ${n}-track template${r.media ? ` in ${r.media}` : ''} — the fold breaks letter by letter`);
      }

      // ── ✨ entry + probe ───────────────────────────────────────────────────
      const nf = read('src/lib/newFeatures.ts');
      const at = nf.indexOf("id: 'bonde-table-density-2026-09-28'");
      if (at < 0) errs.push("newFeatures.ts lost the ✨ entry id: 'bonde-table-density-2026-09-28'");
      else {
        const entry = nf.slice(at, nf.indexOf('addedAt', at) + 80);
        if (!entry.includes("route: '/chart-maps?tab=bonde'")) errs.push("the ✨ entry must route to '/chart-maps?tab=bonde'");
        if (!entry.includes('so much empty space')) errs.push('the ✨ entry must quote his ask ("so much empty space")');
        if (/bounce/i.test(entry)) errs.push('the ✨ entry says "bounce"');
      }
      let probe = '';
      try { probe = read('scripts/bonde-layout-probe.mjs'); } catch { errs.push('scripts/bonde-layout-probe.mjs is missing'); }
      if (probe) {
        if (!probe.includes('[1440, 1280, 1024, 768, 390]')) errs.push('the probe must measure [1440, 1280, 1024, 768, 390]');
        if (!probe.includes('C10') || !probe.includes('C11')) errs.push('the probe must run C10 (painted) and C11 (no mid-word break)');
        if (probe.includes('elementFromPoint')) errs.push('the probe must not use elementFromPoint — hit-testing cannot prove paint');
      }
      return errs;
    },
  },
  {
    name: '🧬 medical catalysts (2026-09-29): sub-tab mounted, UNMEASURED served, the kind declares itself everywhere, never bounce',
    file: 'src/pages/Catalysts.tsx',
    // Ajay 2026-09-29: "can you add a new routine to scan for … amd trails or
    // other medi cal nws and sector them separatively like new fdaapprovals or
    // break throughs like mrnaresearch how to catch thsse sectorsand
    // companiesand add right setup and alerts". The setup is PENDING STUDY:
    // every surface prints the served UNMEASURED note, none names a price to
    // act at, and the med_catalyst kind must exist in every registry or it
    // sends to zero devices in silence.
    checks: (src) => {
      const errs = [];
      // 1. the sub-tab
      const tt = /type TopTab = ([^;]*);/.exec(src);
      if (!tt || !/'medical'/.test(tt[1])) errs.push("TopTab must carry 'medical'");
      const tops = /const TOP_TABS: TopTab\[\] = \[([^\]]*)\]/.exec(src);
      if (!tops || !/'medical'/.test(tops[1])) errs.push("TOP_TABS must carry 'medical' — ?sub=medical would fall back to Predictions");
      if (!src.includes("{tab === 'medical' && <MedicalCatalysts />}")) errs.push("Catalysts.tsx must render {tab === 'medical' && <MedicalCatalysts />}");
      // 2. the served note + setup, on both surfaces
      const board = read('src/components/MedicalCatalysts.tsx');
      const panel = read('src/components/MedicalEventsPanel.tsx');
      const row = read('src/components/MedicalEventRow.tsx');
      if (!/data-testid="mc-unmeasured">\{data\.labels\.note\}/.test(board)) errs.push('MedicalCatalysts must render the SERVED data.labels.note in data-testid="mc-unmeasured"');
      if (!/data-testid="mc-setup">Setup: \{data\.labels\.setup\}/.test(board)) errs.push('MedicalCatalysts must render the SERVED labels.setup in data-testid="mc-setup"');
      if (!/data-testid="mc-panel-unmeasured">\{data\.labels\.note\}/.test(panel)) errs.push('MedicalEventsPanel must render the SERVED data.labels.note in data-testid="mc-panel-unmeasured"');
      if (!/data-testid="mc-panel-setup">Setup: \{data\.labels\.setup\}/.test(panel)) errs.push('MedicalEventsPanel must render the SERVED labels.setup in data-testid="mc-panel-setup"');
      // 3. never bounce, never a price to act at
      for (const [rel, txt] of [['MedicalCatalysts.tsx', board], ['MedicalEventRow.tsx', row], ['MedicalEventsPanel.tsx', panel]]) {
        if (/bounce/i.test(txt)) errs.push(`${rel} says "bounce" — surfaces he reads say reversal`);
        if (/\b(Stop|Target|Entry)\b/.test(txt)) errs.push(`${rel} carries Stop / Target / Entry — the setup is pending study`);
      }
      // 4. the ticker page mounts the panel inside the catalyst branch
      const sepa = read('src/pages/SepaCandidate.tsx');
      const catAt = sepa.indexOf("{tab === 'catalyst' && (");
      const catBranch = catAt < 0 ? '' : sepa.slice(catAt, sepa.indexOf("{tab === '", catAt + 10));
      if (!/<MedicalEventsPanel symbol=\{symbol\}/.test(catBranch)) errs.push("SepaCandidate.tsx's catalyst branch must mount <MedicalEventsPanel symbol={symbol} />");
      // 5. five registries
      if (!/\bmed_catalyst:/.test(read('src/lib/alertKinds.ts'))) errs.push('alertKinds.ts must register med_catalyst or the bell renders a raw id');
      if (!/med_catalyst\?: boolean/.test(read('src/hooks/useNotificationPrefs.ts'))) errs.push('NotificationPrefs must carry med_catalyst?: boolean');
      const notif = read('src/pages/Notifications.tsx');
      const nm = notif.match(/key: 'med_catalyst'[\s\S]*?\},\n/);
      if (!nm) errs.push('med_catalyst must be listed on the Notifications page — a kind the page cannot show cannot be muted');
      const d = nm ? nm[0] : '';
      for (const need of ['NOT MEASURED', 'Not a recommendation', 'add right setup and alerts']) {
        if (nm && !d.includes(need)) errs.push(`the med_catalyst Notifications entry must say ${need}`);
      }
      const subs = read('../backend/push/subs.py');
      const dm = subs.match(/["']med_catalyst["']\s*:\s*(True|False)/);
      if (!dm) errs.push('push/subs.py default_prefs must list "med_catalyst"');
      const gate = read('../backend/market_hours/gate.py');
      if (!(pyFrozenSet(gate, 'MARKET_ALERT_KINDS') || []).includes('med_catalyst')) errs.push('market_hours/gate.py must treat med_catalyst as a MARKET kind');
      if ((pyFrozenSet(gate, 'PERSONAL_KINDS') || []).includes('med_catalyst')) errs.push('med_catalyst must NOT be a PERSONAL kind — a closed day has no session to trade the news');
      // 6. default-state coherence (HIS CALL #1 flips the keep-set)
      if (dm && dm[1] !== 'False') errs.push('med_catalyst must be False in push/subs.py default_prefs — everyone else starts off');
      const ess = notif.slice(notif.indexOf("id: 'essentials'"), notif.indexOf("id: 'trading_only'"));
      if (keepSet(subs).includes('med_catalyst')) {
        if (nm && !d.includes('ON FOR YOUR PHONE')) errs.push('med_catalyst is in OWNER_KEEP_SET — the Notifications entry must say ON FOR YOUR PHONE');
        if (!/med_catalyst:\s*true/.test(ess)) errs.push('med_catalyst is in OWNER_KEEP_SET — Essentials must carry med_catalyst: true');
      } else {
        if (nm && !d.includes('OFF BY DEFAULT')) errs.push('med_catalyst is NOT in OWNER_KEEP_SET — the Notifications entry must say OFF BY DEFAULT');
        if (!/med_catalyst:\s*false/.test(ess)) errs.push('med_catalyst is NOT in OWNER_KEEP_SET — Essentials must carry med_catalyst: false');
      }
      // 7. the /alerts pass row
      if (!/key: 'med_catalyst'/.test(read('src/pages/Alerts.tsx'))) errs.push("Alerts.tsx PASSES must carry key: 'med_catalyst'");
      // 8. it rides promo_live — NO crontab line of its own (NEGATIVE)
      const cron = cronCommands(read('../backend/crontab'));
      if (cron.some((l) => /catalysts\.medical/.test(l))) errs.push('backend/crontab runs catalysts.medical — it must ride promo_live (the crontab is host-mounted; a deploy does not ship it)');
      const promoLines = cron.filter((l) => /catalysts\.promo_live/.test(l));
      if (promoLines.length !== 1) errs.push(`backend/crontab must run catalysts.promo_live exactly once — found ${promoLines.length}`);
      const promo = read('../backend/catalysts/promo_live.py');
      const mainAt = promo.indexOf('if __name__ == "__main__"');
      const main = mainAt < 0 ? '' : promo.slice(mainAt);
      const wz = main.indexOf('warm_zones()');
      const hk = main.indexOf('_run_medical_hook()');
      if (hk < 0 || wz < 0 || hk < wz) errs.push('promo_live.py __main__ must call _run_medical_hook() after warm_zones()');
      // 9. ✨ + nav
      if (!read('src/lib/newFeatures.ts').includes("id: 'medical-catalysts-2026-09-29'")) errs.push("newFeatures.ts lost the ✨ entry id: 'medical-catalysts-2026-09-29'");
      if (!/sub=medical/.test(read('src/lib/navSearch.ts'))) errs.push('navSearch.ts must deep-link sub=medical');
      // 10. the owner's address never reaches the bundle
      const scanEmail = (dir) => {
        for (const ent of readdirSync(join(FRONTEND_ROOT, dir), { withFileTypes: true })) {
          const rel = `${dir}/${ent.name}`;
          if (ent.isDirectory()) scanEmail(rel);
          else if (/\.(ts|tsx|js|jsx)$/.test(ent.name) && /ajaykandakatla@/.test(read(rel))) {
            errs.push(`${rel} carries the owner's email — it must never reach the JS bundle`);
          }
        }
      };
      scanEmail('src');
      // 11. every mc-* class the three components use has a rule (the hsm lesson)
      const css = read('src/styles.css').replace(/\/\*[\s\S]*?\*\//g, '');
      const used = new Set();
      for (const txt of [board, row, panel]) {
        for (const m of txt.matchAll(/className=(?:"([^"]*)"|\{`([^`]*)`\}|\{([^}]*)\})/g)) {
          for (const cls of (m[1] || m[2] || m[3] || '').split(/[\s${}?:'"+()]+/)) {
            if (/^mc-[\w-]*[\w]$/.test(cls)) used.add(cls);
          }
        }
      }
      for (const fn of ['mc-dir--pos', 'mc-dir--neg', 'mc-dir--mixed', 'mc-dir--unknown', 'mc-push--on', 'mc-push--off', 'mc-push--held']) used.add(fn);
      for (const c of [...used].sort()) {
        if (!new RegExp(`\\.${c}(?![\\w-])`).test(css)) errs.push(`styles.css has no rule for .${c} — the 🧬 board would ship unstyled`);
      }
      return errs;
    },
  },
  {
    name: 'a consolidated push lists EVERY item on /alerts; the phone payload stays short (2026-09-29)',
    file: 'src/pages/Alerts.tsx',
    // Ajay 2026-09-29, on "⚡ Tape burst at a zone — CRWV +7 more": "I am
    // unable to see the other that are hiddedn her … Can you show them all and
    // make all the tickers clicable individually?"
    //
    // Every composer LOGS each entry as `items`; push/sender strips them
    // before the device (Web Push caps a payload at ~4 KB and a 44-burst push
    // would fail the whole notification silently); push_history stores them;
    // push/recent serves them; /alerts links each ticker on its own.
    // docs/alerts/every_item_2026_09_29.md
    checks: (src) => {
      const errs = [];
      if (!/<AlertItems/.test(src) || !/row\.items/.test(src)) {
        errs.push('Alerts.tsx must render the served row.items through <AlertItems> — the raw body hides every name past the 4th line');
      }
      const items = read('src/components/AlertItems.tsx');
      if (!/TickerLink/.test(items)) errs.push('AlertItems.tsx must link each ticker through TickerLink (a real href, ⌘-click works)');
      if (!/not stored in this push/.test(items)) errs.push('AlertItems.tsx must say "+N more not stored in this push" for an old row — never a silent short list');
      if (!/ITEMS_FOLD_AT/.test(items)) errs.push('AlertItems.tsx must fold on ITEMS_FOLD_AT (measured p90 16, max 44 per push)');
      const sender = read('../backend/push/sender.py');
      if (!/LOG_ONLY_KEYS/.test(sender)) errs.push('push/sender.py must strip LOG_ONLY_KEYS before a device sees the payload');
      // 2026-10-21: both paths send through the ONE chokepoint _fan_out (it stamps the delivery-receipt push_id on
      // the stripped device dict); the pin is now "the chokepoint strips, both paths use it".
      const sends = (sender.match(/_send_one\(sub, device\)/g) || []).length;
      const fans = (sender.match(/_fan_out\(targets, payload\)/g) || []).length;
      if (sends !== 1 || fans !== 2) errs.push(`push/sender.py must send through _fan_out (one _send_one(sub, device), found ${sends}) from BOTH send_to_all and send_to_user (found ${fans}) — the unstripped payload would reach the phone`);
      const fan = sender.slice(sender.indexOf('def _fan_out('), sender.indexOf('def send_to_all('));
      if (!/device_payload\(payload\)/.test(fan)) errs.push('_fan_out must build the device dict from device_payload(payload)');
      const hist = read('../backend/push/history.py');
      if (!/"items":/.test(hist) || !/MAX_ITEMS/.test(hist)) errs.push('push/history.py::record must store the sanitized items, capped at MAX_ITEMS');
      const recent = read('../backend/push/recent.py');
      if (!/def served_items\(/.test(recent) || !/ITEM_URL_BY_KIND/.test(recent)) {
        errs.push('push/recent.py must serve items through served_items and ONE ITEM_URL_BY_KIND map');
      }
      for (const rel of [
        '../backend/orderflow/trade_flash.py',
        '../backend/supply_demand/demand_alerts.py',
        '../backend/supply_demand/zone_bounce_alerts.py',
        '../backend/supply_demand/zone_edge.py',
        '../backend/supply_demand/key_level_alerts.py',
        '../backend/supply_demand/accumulation_changes.py',
        '../backend/catalysts/medical/alerts.py',
        '../backend/push/hooks.py',
      ]) {
        if (!read(rel).includes('"items"')) errs.push(`${rel} must log every entry as "items" — its digest body stops at 4-8 lines`);
      }
      return errs;
    },
  },
  {
    name: '🧱 the 1% pad under demand floors is SERVED, drawn, never computed on the FE (2026-09-30)',
    file: 'src/lib/zonePad.ts',
    // Ajay 2026-09-30: "Also increase our Demand zone and key levels sizes by
    // 1%. … if the demand zone or key level is 133, it holding at 132." The
    // one number lives in backend/supply_demand/level_pad.py
    // (DEMAND_PAD_PCT = sd_liquidity.STOP_SHELF_PCT); the FE reads the served
    // pad_lo / pad_price and only compares. A typed 0.99 here would be a
    // second pad that silently disagrees with the engine when he flips it.
    checks: (src) => {
      const errs = [];
      const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
      for (const [re, what] of [[/0\.99/, '0.99'], [/\*\s*\(\s*1\s*-/, '* (1 -'], [/\/\s*100\b/, '/ 100']]) {
        if (re.test(code)) errs.push(`zonePad.ts must not type the pad (${what}) — it reads the served pad_lo / pad_price`);
      }
      if (!/export function padStrip\(/.test(code)) errs.push('zonePad.ts lost padStrip');
      if (!/export function keyPadStrip\(/.test(code)) errs.push('zonePad.ts lost keyPadStrip');
      for (const rel of ['src/components/PatternChart.tsx', 'src/components/zoneBandsPrimitive.ts']) {
        const f = read(rel).replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
        if (!/pad_lo/.test(f)) errs.push(`${rel} must read the served pad_lo`);
        if (!/from '\.\.\/lib\/zonePad'/.test(f)) errs.push(`${rel} must draw the pad through lib/zonePad`);
        if (/0\.99\b/.test(f) || /pad_lo\s*=(?!=)/.test(f) || /pad_lo\s*:\s*[^,}]*\*/.test(f)) {
          errs.push(`${rel} must never compute a pad — it reads pad_lo`);
        }
      }
      const lp = read('../backend/supply_demand/level_pad.py');
      if (!/^DEMAND_PAD_PCT = SL\.STOP_SHELF_PCT\b/m.test(lp)) {
        errs.push('backend level_pad.py must keep DEMAND_PAD_PCT = SL.STOP_SHELF_PCT (the one number, reused by name)');
      }
      const ri = read('../backend/supply_demand/rules_info.py');
      const keys = /SECTION_KEYS\s*=\s*\(([\s\S]*?)\)\s*\n\s*\n_DISCLAIMER/.exec(ri);
      if (!keys || !/"zone_pad"/.test(keys[1])) errs.push('backend rules_info.py SECTION_KEYS must contain "zone_pad"');
      if (!/<RulesInfo section="zone_pad"/.test(read('src/pages/ChartMaps.tsx'))) {
        errs.push('ChartMaps.tsx must mount <RulesInfo section="zone_pad" …> — his HIS CALL switches live there');
      }
      const nf = read('src/lib/newFeatures.ts');
      const at = nf.indexOf("id: 'sd-level-pad-2026-09-30'");
      if (at < 0) {
        errs.push("newFeatures.ts lacks the 'sd-level-pad-2026-09-30' ✨ entry");
      } else {
        const lq = nf.indexOf("label: '", at);
        const end = nf.indexOf("' },", lq);
        const label = lq > at && end > lq ? nf.slice(lq, end) : '';
        if (!label) errs.push('the sd-level-pad ✨ entry has no label');
        if (/bounce/i.test(label)) errs.push('the sd-level-pad ✨ label must say "reversal", never "bounce"');
      }
      return errs;
    },
  },

  {
    name: 'the \u{1FA73} short interest reaches EVERY Chart Maps tab and the ticker page (2026-10-03)',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-10-03: "I would like to see a new field for sotcks about short
    // interest ... can you add this field to all our chart maps scan. also the
    // individual tickers please". ONE chip (served text, FINRA date), mounted
    // beside every <PromoOriginChip/> — the growth-chip precedent above. A new
    // non-board tab whose renderer forgets it fails here.
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
        ema_frames: 'src/components/EmaFramesBoard.tsx',
        news: 'src/components/NewsTabBoard.tsx',
        growth: 'src/components/ExplosiveGrowth.tsx',
        gajjala: 'src/components/GajjalaBoard.tsx',
      };
      // Exempt only in writing (the growth-chip NO_CHIP rule): news has no
      // ticker rows, and its file says so.
      const NO_CHIP = { news: /no ticker rows on this tab/ };
      // WIDENED 2026-10-16 — 🕯️ doji_sweep is a board tab after 🚩
      const nonBoard = tabs.filter((t) => !/^(zones|deep_demand|quick_bounce|breaking|gabbar|vcp|topping|ict|undervalue|zero_dte|earnings|winners|keltner|amd|ipo|key_levels|dual_momentum|ath|resiliency|fallen|drop10|high_beta|doji_sweep)$/.test(t));
      for (const t of nonBoard) {
        const file = RENDERER[t];
        if (!file) {
          errs.push(`tab '${t}' has no renderer listed in this contract — add it and give it a <ShortInterestChip>`);
          continue;
        }
        const tsx = read(file);
        if (NO_CHIP[t]) {
          if (/<ShortInterestChip\s/.test(tsx)) {
            errs.push(`${file} (tab '${t}') renders <ShortInterestChip> but is listed as having no ticker rows — drop it from NO_CHIP`);
          } else if (!NO_CHIP[t].test(tsx)) {
            errs.push(`${file} (tab '${t}') has no <ShortInterestChip> and no longer states why`);
          }
          continue;
        }
        if (!/<ShortInterestChip\s/.test(tsx)) {
          errs.push(`${file} (tab '${t}') does not render <ShortInterestChip> — "add this field to all our chart maps scan"`);
        }
      }
      const tile = read('src/components/PatternChart.tsx');
      if (!/<ShortInterestChip\s+symbol=\{tile\.symbol\}/.test(tile)) {
        errs.push('PatternChart must render <ShortInterestChip symbol={tile.symbol}> — it is the one renderer behind every board tab');
      }
      const page = read('src/pages/SepaCandidate.tsx');
      if (!/<ShortInterestChip\s/.test(page)) errs.push('the ticker page header must render <ShortInterestChip> — "also the individual tickers please"');
      if (!/<ShortInterestPanel\s/.test(page)) errs.push('the ticker page must render <ShortInterestPanel> (Smart Money tab)');
      if (!/<RulesInfo section="short_interest"/.test(read('src/pages/ChartMaps.tsx'))) {
        errs.push('ChartMaps.tsx must mount <RulesInfo section="short_interest" /> once per tab, beside the 🧨 pill');
      }

      // One request per board: the FE chunk equals the backend cap.
      const hook = read('src/hooks/useShortInterest.ts');
      const fe = /SI_CHUNK\s*=\s*(\d+)/.exec(hook);
      if (!exists('../backend/short_interest/read.py')) {
        errs.push('backend short_interest/read.py is missing — the chip has no served read');
      } else {
        const be = /MAP_MAX_SYMBOLS\s*=\s*(\d+)/.exec(read('../backend/short_interest/read.py'));
        if (!fe || !be || fe[1] !== be[1]) {
          errs.push(`useShortInterest SI_CHUNK (${fe ? fe[1] : '?'}) must equal backend read.MAP_MAX_SYMBOLS (${be ? be[1] : '?'})`);
        }
      }
      const ri = exists('../backend/supply_demand/rules_info.py') ? read('../backend/supply_demand/rules_info.py') : '';
      const keys = /SECTION_KEYS\s*=\s*\(([\s\S]*?)\)\s*\n\s*\n_DISCLAIMER/.exec(ri);
      if (!keys || !/"short_interest"/.test(keys[1])) errs.push('backend rules_info.py SECTION_KEYS must contain "short_interest"');

      // Display only: the FE prints served strings. No arithmetic, no
      // toFixed, no forecast words.
      for (const rel of ['src/components/ShortInterestChip.tsx', 'src/components/ShortInterestPanel.tsx', 'src/lib/shortInterest.ts']) {
        const t = read(rel);
        if (/(pct_of_float|pct_of_shares_out|days_to_cover|si_shares)[^;\n]*(toFixed|[*\/+-]\s*\d)/.test(t)) {
          errs.push(`${rel} computes on a short-interest field — every number is served by short_interest/read.py`);
        }
        if (/\b(bounce|fake|predict)/i.test(t)) errs.push(`${rel} says bounce / fake / predict`);
      }

      // Nothing on the board side: no attach, no sort.
      const board = read('../backend/chart_maps/board.py');
      if (/short_interest\.read|from short_interest import read/.test(board)) {
        errs.push('chart_maps/board.py must not import short_interest.read — the chip is delivered by its own endpoint, nothing attaches to tiles');
      }
      const sorts = /^SORTS[^=]*=\s*\{([\s\S]*?)\n\}/m.exec(board);
      if (!sorts) {
        errs.push('chart_maps/board.py SORTS block not found');
      } else {
        for (const m of sorts[1].replace(/#[^\n]*/g, '').matchAll(/^\s*"([^"]+)"\s*:/gm)) {
          if (/short|\bsi\b/.test(m[1])) errs.push(`chart_maps/board.py SORTS has '${m[1]}' — nothing sorts by short interest`);
        }
      }
      if (!/id: 'short-interest-2026-10-03'/.test(read('src/lib/newFeatures.ts'))) {
        errs.push("newFeatures.ts lacks the 'short-interest-2026-10-03' ✨ entry");
      }
      return errs;
    },
  },
  {
    name: 'ops_alert is wired end to end (2026-10-06)',
    file: 'src/pages/Notifications.tsx',
    // 🩺 Ajay approved the Docker watchdog push on 2026-10-06 (ops/docker_watchdog.py
    // → POST /admin/ops/alert → push.hooks.notify_ops). A kind missing from
    // default_prefs targets ZERO devices; outside OWNER_KEEP_SET a re-registered
    // phone mutes it; outside PERSONAL_KINDS a Saturday Docker crash is dropped.
    checks: (src) => {
      const errs = [];
      const subs = read('../backend/push/subs.py');
      const dm = subs.match(/["']ops_alert["']\s*:\s*(True|False)/);
      if (!dm) errs.push('push/subs.py default_prefs must list ops_alert');
      else if (dm[1] !== 'True') errs.push('ops_alert must ship ON (True) in push/subs.py default_prefs');
      if (!keepSet(subs).includes('ops_alert')) {
        errs.push('ops_alert must sit in push/subs.OWNER_KEEP_SET — prefs_for() would mute it on re-registration');
      }
      const personal = pyFrozenSet(read('../backend/market_hours/gate.py'), 'PERSONAL_KINDS');
      if (!personal || !personal.includes('ops_alert')) {
        errs.push('ops_alert must be in market_hours/gate.PERSONAL_KINDS — host health rings on closed days');
      }
      const row = src.match(/\{\s*key:\s*'ops_alert'[^}]*\}/);
      if (!row) errs.push("Notifications.tsx CATEGORIES lacks key: 'ops_alert'");
      else if (!/group:\s*'admin'/.test(row[0])) errs.push("the ops_alert row must sit in group 'admin'");
      if (!/^\s*ops_alert:/m.test(read('src/lib/alertKinds.ts'))) errs.push('alertKinds.ts must register ops_alert');
      if (!/ops_alert\?: boolean/.test(read('src/hooks/useNotificationPrefs.ts'))) {
        errs.push('NotificationPrefs must carry ops_alert or the toggle cannot be stored');
      }
      if (!/id: 'ops-docker-watch-2026-10-06'/.test(read('src/lib/newFeatures.ts'))) {
        errs.push("newFeatures.ts lacks the 'ops-docker-watch-2026-10-06' ✨ entry");
      }
      return errs;
    },
  },
  {
    name: '✨ growth arrivals his-calls (2026-10-13): strip off on ?tab=growth, show=all on every chip, focus exemption, ✨ new only, per-tab links, membership hook',
    file: 'src/components/GrowthArrivalsStrip.tsx',
    // Ajay 2026-10-12 answered "yes" to the eight his-call questions after the
    // ✨ arrivals strip shipped (97b48ff4). Each pin below is one of them; the
    // 30-day window (#4) is KEPT and pinned on the backend (NEW_GROWTH_DAYS).
    checks: (src) => {
      const errs = [];
      // #5 every chip href carries the growth tab's own show=all override.
      if (!/withShowAll\(arrivalHref\(/.test(src)) errs.push('every strip chip href must go through withShowAll(arrivalHref(…)) — a BLOCKED arrival is drawn on landing');
      const fresh = read('src/lib/growthArrivalsFresh.ts');
      if (!/export function withShowAll/.test(fresh) || !/q\.set\('show', 'all'\)/.test(fresh)) {
        errs.push("growthArrivalsFresh.withShowAll must set show=all — the real param ChartMaps.tsx reads for the 🎯 cut");
      }
      // #3 the strip is gone on the growth tab (the rows carry the pills there).
      const page = read('src/pages/ChartMaps.tsx');
      if (!/tab !== GROWTH_TAB && <GrowthArrivalsStrip \/>/.test(page)) {
        errs.push('ChartMaps.tsx must mount <GrowthArrivalsStrip /> only when tab !== GROWTH_TAB');
      }
      // #7 open-on-fresh-batch rides on StudyNote's own store, not a parallel one.
      if (!/freshKey=\{newestFirstSeen\(arrivals\)\}/.test(src)) errs.push('the strip must pass freshKey={newestFirstSeen(arrivals)} to StudyNote');
      const note = read('src/components/StudyNote.tsx');
      if (!/freshKey\?: string \| null/.test(note) || !/cm\.study\.fresh\./.test(note)) {
        errs.push('StudyNote must take freshKey and keep the folded-at batch under cm.study.fresh.<id>');
      }
      // #8 per-tab links render off SERVED also_on only; nothing is computed here.
      if (!/alsoOnLinks\(a, params\)/.test(src) || !/cm-arrival-also/.test(src)) errs.push('the strip must render alsoOnLinks(a, params) under each chip (class cm-arrival-also)');
      const board = read('src/components/ExplosiveGrowth.tsx');
      // #2 ✨ new only is a filter with its own hidden-count line …
      if (!/data-testid="growth-new-only"/.test(board) || !/data-testid="growth-new-only-hidden"/.test(board)) {
        errs.push('ExplosiveGrowth must carry the ✨ new only checkbox AND its hidden-count line');
      }
      // … and #6 the focused row is drawn with a marker, never by flipping a filter.
      if (!/data-testid="growth-focus-exempt"/.test(board) || !/cm-row-exempt/.test(board)) {
        errs.push('ExplosiveGrowth must draw the focused-but-hidden row with cm-row-exempt and the growth-focus-exempt marker');
      }
      if (!/freshKey=\{newestFirstSeen\(/.test(board)) errs.push("the board's own arrivals line must follow the same open rule (freshKey)");
      const css = read('src/styles.css');
      for (const cls of ['.cm-row-exempt', '.cm-arrival-also']) {
        if (!css.includes(cls)) errs.push(`styles.css lacks ${cls}`);
      }
      // #8 backend: the membership hook sits AFTER out["tab"] and calls attach_also_on in both growth bodies.
      const bp = read('../backend/chart_maps/board.py');
      if (!/out\["tab"\] = t\n[\s\S]{0,600}?_MB\.record_board\(t, out, request=\{/.test(bp)) {
        errs.push('chart_maps/board.py must call membership.record_board(t, out, request={…}) right after out["tab"] = t');
      }
      const api = read('../backend/growth/api.py');
      if ((api.match(/_mem\.attach_also_on\(arr\)/g) || []).length !== 2) errs.push('growth/api.py must call _mem.attach_also_on(arr) in BOTH sync bodies (board + tags)');
      // #4 kept.
      if (!/NEW_GROWTH_DAYS = 30\b/.test(read('../backend/growth/tracker.py'))) errs.push('tracker.NEW_GROWTH_DAYS must stay 30 (his "yes" = keep)');
      if (!/id: 'chart-maps-growth-arrivals-his-calls-2026-10-13'/.test(read('src/lib/newFeatures.ts'))) {
        errs.push("newFeatures.ts lacks the 'chart-maps-growth-arrivals-his-calls-2026-10-13' ✨ entry");
      }
      return errs;
    },
  },
  {
    name: '🎢 High Beta tab (2026-10-14): mounted right after 🔻, label = high_beta_tab.TAB_LABEL, filter keys / box labels / sorts = the backend constants, the four numbers in the blurb + ✨ = the constants, UNMEASURED, the FE composes nothing, never bounce',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-10-14: "Can you create a new tab for High Beta stocks" (after
    // "I think Resielient and high beta will not go hand in hand"), and the
    // cut "give me all 3 categories" — β ≥ 1.5, β ≥ 2.0, top 20% — plus the
    // down 5%+ box. Any of these links lost silently drops the tab, lets a
    // label or a box key drift from the backend constant, retypes one of HIS
    // four numbers wrong in a sentence he reads, or lets the FE compose a
    // number or a verdict the server owns (BUILD_SPEC §3.8, WP4 (a)).
    checks: (src) => {
      const errs = [];
      const unesc = (x) => x.replace(/\\U([0-9A-Fa-f]{8})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\'/g, "'").replace(/\\"/g, '"');
      const tabs = parseCmTabs(src);
      if (!tabs || !tabs.includes('high_beta')) {
        errs.push("CM_TABS must carry 'high_beta'");
      } else {
        if (tabs.filter((t) => t === 'high_beta').length !== 1) errs.push("CM_TABS lists 'high_beta' more than once");
        if (tabs.indexOf('high_beta') !== tabs.indexOf('drop10') + 1) errs.push("CM_TABS: 'high_beta' must sit right after 'drop10'");
      }
      if (/\n  high_beta: '/.test(src)) errs.push('ENTERABLE_KIND must NOT carry high_beta (🎯 n/a, the 🔻 precedent)');

      let hb = '';
      try { hb = read('../backend/chart_maps/high_beta_tab.py'); } catch { errs.push('backend/chart_maps/high_beta_tab.py is missing (WP1)'); }
      const num = (name) => { const m = new RegExp(`^${name} = ([0-9_.]+)`, 'm').exec(hb); return m ? Number(m[1].replace(/_/g, '')) : null; };
      const B15 = num('B15_MIN'), B20 = num('B20_MIN'), TOP = num('TOP_PCT'), DOWN = num('DOWN_CHIP_PCT');
      if (hb && [B15, B20, TOP, DOWN].some((x) => x == null || !Number.isFinite(x))) errs.push('high_beta_tab.py lost B15_MIN / B20_MIN / TOP_PCT / DOWN_CHIP_PCT = <number>');
      if (hb && !/^MARK = "([^"]*)"/m.test(hb)) errs.push('high_beta_tab.py lost MARK = "<emoji>"');
      // Every top-level string / number constant of the module, so a label built from MARK, DROP_MARK, … renders.
      const consts = {};
      for (const m of hb.matchAll(/^([A-Z][A-Z_0-9]*) = "([^"]*)"/gm)) consts[m[1]] = unesc(m[2]);
      for (const m of hb.matchAll(/^([A-Z][A-Z_0-9]*) = ([0-9][0-9_]*(?:\.[0-9]+)?)\b/gm)) consts[m[1]] = Number(m[2].replace(/_/g, ''));
      // A python f-string body rendered with the module's own constants:
      // {NAME}, {NAME:.1f}, {NAME:g}. An unknown name renders as "?NAME" and fails the compare.
      const pyF = (body) => unesc(body).replace(/\{([A-Z_0-9]+)(?::([^}]*))?\}/g, (_m, n, spec) => {
        const v = consts[n];
        if (v == null) return `?${n}`;
        if (spec && /^\.\d+f$/.test(spec) && typeof v === 'number') return v.toFixed(Number(spec.slice(1, -1)));
        return typeof v === 'number' ? String(v) : v;
      });
      const pyStr = (q) => (q.f ? pyF(q.body) : unesc(q.body));
      const labelM = /^TAB_LABEL = (f?)"([^"]*)"/m.exec(hb);
      const pyLabel = labelM ? pyStr({ f: !!labelM[1], body: labelM[2] }) : null;
      if (hb && !labelM) errs.push('high_beta_tab.py lost TAB_LABEL = f"{MARK} High Beta"');
      if (pyLabel && pyLabel !== '\u{1F3A2} High Beta') errs.push(`high_beta_tab.TAB_LABEL renders "${pyLabel}" — the tab is "🎢 High Beta" (A13, his call to change)`);

      // The four numbers in a sentence he reads must be the constants' — present, and never another value.
      const numberChecks = (where, text) => {
        const out = [];
        if (B15 == null || B20 == null || TOP == null || DOWN == null) return out;
        for (const need of [B15.toFixed(1), B20.toFixed(1), `${TOP}%`, `${DOWN}%`]) {
          if (!text.includes(need)) out.push(`${where} must state ${need} as high_beta_tab.py has it`);
        }
        for (const m of text.matchAll(/β\s*(?:≥|>=)\s*(\d+(?:\.\d+)?)/g)) {
          if (![B15, B20].includes(Number(m[1]))) out.push(`${where} says "${m[0]}" — B15_MIN is ${B15}, B20_MIN is ${B20}`);
        }
        for (const m of text.matchAll(/\b[Tt]op (\d+(?:\.\d+)?)\s?%/g)) {
          if (Number(m[1]) !== TOP) out.push(`${where} says "${m[0]}" — TOP_PCT is ${TOP}`);
        }
        return out;
      };
      const HIS = ['Can you create a new tab for High Beta stocks'];

      const meta = /\n  high_beta: \{\n    label: (['"])((?:(?!\1)[^\\]|\\.)*)\1,\n    blurb: (['"])((?:(?!\3)[^\\]|\\.)*)\3,/.exec(src);
      if (!meta) {
        errs.push('TAB_META.high_beta (label + blurb) is missing');
      } else {
        if (unesc(meta[2]) !== '\u{1F3A2} High Beta') errs.push(`TAB_META.high_beta.label "${unesc(meta[2])}" must be "🎢 High Beta"`);
        if (pyLabel && unesc(meta[2]) !== pyLabel) errs.push(`TAB_META.high_beta.label "${unesc(meta[2])}" must equal high_beta_tab.TAB_LABEL "${pyLabel}"`);
        const blurb = unesc(meta[4]);
        if (!blurb.includes('UNMEASURED')) errs.push('the TAB_META.high_beta blurb must say UNMEASURED');
        for (const h of HIS) if (!blurb.includes(h)) errs.push(`the TAB_META.high_beta blurb must quote his ask verbatim: "${h}"`);
        if (/bounce|fake/i.test(blurb)) errs.push('the TAB_META.high_beta blurb says "bounce"/"fake"');
        errs.push(...numberChecks('the TAB_META.high_beta blurb', blurb));
      }

      // Box keys, box labels, sort keys: the FE copies are pinned to the module's.
      let lib = '';
      try { lib = read('src/lib/highBeta.ts'); } catch { errs.push('src/lib/highBeta.ts is missing (WP3)'); }
      const pyKeysM = /^FILTER_KEYS = \(([^)]*)\)/m.exec(hb);
      const pyKeys = pyKeysM ? [...pyKeysM[1].matchAll(/"([a-z0-9_]+)"/g)].map((m) => m[1]) : [];
      if (hb && !pyKeys.length) errs.push('high_beta_tab.py lost FILTER_KEYS = ("b15", …)');
      const tsKeysM = /export const HB_FILTER_KEYS\s*=\s*\[([^\]]*)\]\s*as const/.exec(lib);
      const tsKeys = tsKeysM ? [...tsKeysM[1].matchAll(/'([a-z0-9_]+)'/g)].map((m) => m[1]) : [];
      if (lib && !tsKeys.length) errs.push("lib/highBeta.ts lost export const HB_FILTER_KEYS = [...] as const");
      if (pyKeys.length && tsKeys.length && pyKeys.join(',') !== tsKeys.join(',')) {
        errs.push(`lib/highBeta.ts HB_FILTER_KEYS [${tsKeys.join(', ')}] != high_beta_tab.FILTER_KEYS [${pyKeys.join(', ')}]`);
      }
      const labsAt = hb.search(/^FILTER_LABELS = \{/m);
      const labsSrc = labsAt >= 0 ? hb.slice(labsAt, labsAt + 1200) : '';
      const pyLabels = {};
      for (const m of labsSrc.matchAll(/"([a-z0-9_]+)":\s*(f?)"((?:[^"\\]|\\.)*)"/g)) {
        if (pyKeys.includes(m[1]) && !(m[1] in pyLabels)) pyLabels[m[1]] = pyStr({ f: !!m[2], body: m[3] });
      }
      if (hb && pyKeys.length && Object.keys(pyLabels).length !== pyKeys.length) errs.push(`high_beta_tab.FILTER_LABELS must carry one label per FILTER_KEYS key (found ${Object.keys(pyLabels).join(', ') || 'none'})`);
      const ladder = read('src/lib/cardLadder.ts');
      const ie = /const IDENT_EXACT = new Set\(\[([^\]]*)\]\)/.exec(ladder);
      const ident = new Set(ie ? [...ie[1].matchAll(/'((?:[^'\\]|\\.)+)'/g)].map((m) => unesc(m[1])) : []);
      for (const [k, v] of Object.entries(pyLabels)) {
        if (v.includes('?')) errs.push(`high_beta_tab.FILTER_LABELS["${k}"] names a constant this contract cannot render: "${v}"`);
        else if (!ident.has(v)) errs.push(`cardLadder IDENT_EXACT must carry the served box badge "${v}" (high_beta_tab.FILTER_LABELS["${k}"]) — it sits on the identity line`);
      }
      // Sort keys: HB_SORT_DROP is the FE's (BUILD_SPEC §3.8); every HB_SORT_* the FE exports must be the module's SORT_*.
      const pySorts = Object.fromEntries([...hb.matchAll(/^(SORT_[A-Z_]+) = "([a-z_]+)"/gm)].map((m) => [m[1], m[2]]));
      if (hb && !pySorts.SORT_DROP) errs.push('high_beta_tab.py lost SORT_DROP = "hb_drop"');
      if (lib && !/export const HB_SORT_DROP = '[a-z_]+';/.test(lib)) errs.push("lib/highBeta.ts must export HB_SORT_DROP = '<high_beta_tab.SORT_DROP>'");
      for (const m of lib.matchAll(/export const HB_(SORT_[A-Z_]+) = '([a-z_]+)';/g)) {
        if (hb && pySorts[m[1]] !== m[2]) errs.push(`lib/highBeta.ts HB_${m[1]} = '${m[2]}' != high_beta_tab.${m[1]} = ${pySorts[m[1]] ? `"${pySorts[m[1]]}"` : '(absent)'}`);
      }

      const page = read('src/pages/ChartMaps.tsx');
      if (!/tab === 'high_beta' && <HighBetaBoardNote board=\{data\?\.high_beta_board \?\? null\}/.test(page)) {
        errs.push("ChartMaps.tsx must render <HighBetaBoardNote board={data?.high_beta_board ?? null} …/> on tab === 'high_beta'");
      }
      if (!/data\?\.warming && tab === 'high_beta' \? null/.test(page)) errs.push('the generic (demand) warming branch must skip the high_beta tab — its warming line is served');
      if (!/&& tab !== 'high_beta'/.test(page)) errs.push('the demand-scan progress poll must skip the high_beta tab');
      if (!/\|\| tab === 'high_beta' \|\|[^\n]*\) && \(/.test(page)) errs.push('the ℹ️ Rules mount must include the high_beta tab (section "high_beta")');
      if (!/const hbEvery = tab === 'high_beta' \? drop10RefreshMs\(data\?\.high_beta_board\) : null;/.test(page)) errs.push('ChartMaps.tsx must re-read the live high_beta board on the SERVED cadence (drop10RefreshMs)');

      let note = '';
      try { note = read('src/components/HighBetaBoardNote.tsx'); } catch { errs.push('src/components/HighBetaBoardNote.tsx is missing (WP3)'); }
      for (const [f, t] of [['HighBetaBoardNote.tsx', note], ['lib/highBeta.ts', lib]]) {
        if (!t) continue;
        if (/bounce|fake/i.test(t)) errs.push(`${f} says bounce / fake — surfaces he reads say reversal`);
        const code = t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
        if (/toFixed|UNMEASURED|Math\./.test(code)) errs.push(`${f} composes wording or does maths — every sentence and number is printed as served`);
      }

      const board = read('../backend/chart_maps/board.py');
      const tabsPy = /^TABS = \(([^)]*)\)/m.exec(board);
      if (!tabsPy || !/"high_beta"/.test(tabsPy[1])) errs.push('board.py TABS must carry "high_beta"');
      if (!/elif t == "high_beta":/.test(board)) errs.push('board.py lacks the elif t == "high_beta": dispatch');
      if (!/\(t == "high_beta" and sort in _HB\.TAB_SORTS\)/.test(board)) errs.push('board.py must honour the tab-scoped high_beta sorts on this tab only');
      if (hb) {
        if (!hb.includes('UNMEASURED')) errs.push('high_beta_tab.py must say UNMEASURED');
        // The guard list itself names the banned words; comments are never served.
        const served = hb.replace(/^FORBIDDEN_WORDS = \([\s\S]*?\)\s*(#[^\n]*)?$/m, '').replace(/#[^\n]*/g, '').replace(/quick_bounce/g, '');
        if (/bounc|fake/i.test(served)) errs.push('high_beta_tab.py says "bounce"/"fake"');
      }

      const nf = read('src/lib/newFeatures.ts');
      const idAt = nf.indexOf("id: 'chart-maps-high-beta-2026-10-14'");
      if (idAt < 0) {
        errs.push("newFeatures.ts lacks the ✨ entry id: 'chart-maps-high-beta-2026-10-14' (WP5)");
      } else {
        const next = nf.indexOf('{ id: ', idAt + 4);
        const entry = unesc(nf.slice(idAt, next < 0 ? undefined : next));
        if (!entry.includes("route: '/chart-maps?tab=high_beta'")) errs.push("the 🎢 ✨ entry must route to '/chart-maps?tab=high_beta'");
        if (!entry.includes('UNMEASURED')) errs.push('the 🎢 ✨ entry must say UNMEASURED');
        for (const h of HIS) if (!entry.includes(h)) errs.push(`the 🎢 ✨ entry must quote his ask verbatim: "${h}"`);
        if (/bounce|fake/i.test(entry)) errs.push('the 🎢 ✨ entry says "bounce"/"fake"');
        errs.push(...numberChecks('the 🎢 ✨ entry', entry));
      }
      return errs;
    },
  },
  {
    name: '🎢 header sorts + Sales view (2026-10-14 b): Sales heads / titles = 🔥 HS_COLS byte for byte, HS_FUND_KEYS = the Sales fund keys = FUND_SORTS ∪ {sales_tier, next_earnings}, HsFundCell reads only FUND_ROW_KEYS, every served column key is drawable (?raw mirror), the Hottest table recipe + CSS rules, no client sort, no Sort select on 🎢, the ✨ entry = the constants',
    file: 'src/components/HighBetaBoardNote.tsx',
    // 2026-10-14 b — Ajay 2026-10-14: "Can you add sort function on the headers
    // and also 5 day and 21 days columns to show how they were reacting in price
    // like hot sectors and also add sales tab make it like hot sector with some
    // important metrics like EPS, QUAlity and other colums that show the strength
    // of the stock". K1: the Sales view = the 🔥 Hottest columns through Hottest's
    // own functions, never a second formula — so a head, a title or a cell that
    // drifts from 🔥 is a second engine in disguise. B2 (AMENDMENTS2): a served
    // column key the FE does not know is silently not drawn; this mirrors the
    // HighBetaBoardNote.sales.test.tsx ?raw pin so the pre-commit hook catches it
    // too. The ✨ numbers are the tracker's windows (BUILD_SPEC2 §4 M2).
    // Each pure checker below is ALSO run on mutated inputs (NEGATIVE): a
    // checker that stops catching its own drift fails this contract.
    checks: (note) => {
      const errs = [];
      const unesc = (x) => x.replace(/\\U([0-9A-Fa-f]{8})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\'/g, "'").replace(/\\"/g, '"');
      const strip = (t) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
      const tryRead = (rel) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable`); return ''; } };
      const hb = tryRead('../backend/chart_maps/high_beta_tab.py');
      const hot = tryRead('../backend/rotation/hottest.py');
      const tracker = tryRead('../backend/rotation/tracker.py');
      const d10 = tryRead('../backend/chart_maps/drop10_tab.py');
      const boardPy = tryRead('../backend/chart_maps/board.py');
      const hs = tryRead('src/components/HottestSectors.tsx');
      const page = tryRead('src/pages/ChartMaps.tsx');
      const css = tryRead('src/styles.css');
      const nf = tryRead('src/lib/newFeatures.ts');

      // A top-level python assignment that may span lines: from "NAME = " to the
      // first following line that does not start with whitespace.
      const pyBlock = (src, name) => {
        const m = new RegExp(`^${name} = `, 'm').exec(src);
        if (!m) return null;
        const rest = src.slice(m.index).split('\n');
        const out = [rest[0]];
        for (const l of rest.slice(1)) { if (/^\s/.test(l)) out.push(l); else break; }
        return out.join('\n');
      };
      const pyStrs = (block) => (block ? [...block.matchAll(/"([^"]*)"/g)].map((m) => unesc(m[1])) : []);
      const pyPairs = (name) => {
        const b = pyBlock(hb, name);
        if (!b) { errs.push(`high_beta_tab.py lost ${name} = (("key", label), …)`); return []; }
        const keys = [...b.matchAll(/\("([a-z0-9_]+)",\s*/g)].map((m) => m[1]);
        if (!keys.length) errs.push(`high_beta_tab.${name}: no ("key", label) pair parsed — this pin cannot read it`);
        const lits = Object.fromEntries([...b.matchAll(/\("([a-z0-9_]+)",\s*"((?:[^"\\]|\\.)*)"\)/g)].map((m) => [m[1], unesc(m[2])]));
        return keys.map((k) => ({ key: k, label: k in lits ? lits[k] : null }));
      };
      const tableCols = pyPairs('TABLE_COLUMNS');
      const salesCols = pyPairs('SALES_COLUMNS');
      const fundRowKeys = pyStrs(pyBlock(hb, 'FUND_ROW_KEYS'));
      if (hb && fundRowKeys.length !== 14) errs.push(`high_beta_tab.FUND_ROW_KEYS must carry the 14 HOT._fundamentals_row keys (parsed ${fundRowKeys.length})`);
      const fundSorts = pyStrs(pyBlock(hot, 'FUND_SORTS'));
      if (hot && !fundSorts.length) errs.push('rotation/hottest.py lost FUND_SORTS = (…)');
      const titlesBlock = pyBlock(hb, 'COLUMN_TITLES') || '';
      const pyTitle = (k) => { const m = new RegExp(`"${k}":\\s*"((?:[^"\\\\]|\\\\.)*)"`).exec(titlesBlock); return m ? unesc(m[1]) : null; };

      // 🔥 HS_COLS (key, label, title) and HS_FUND_KEYS, read from HottestSectors.tsx.
      const hsAt = hs.indexOf('export const HS_COLS: HsCol[] = [');
      const hsBody = hsAt >= 0 ? hs.slice(hsAt, hs.indexOf('\n];', hsAt)) : '';
      if (hs && !hsBody) errs.push('HottestSectors.tsx lost export const HS_COLS: HsCol[] = [ … ];');
      const hsCols = [...hsBody.matchAll(/\{[^{}]*\}/g)].map((m) => {
        const g = (f) => { const x = new RegExp(`${f}: '((?:[^'\\\\]|\\\\.)*)'`).exec(m[0]); return x ? unesc(x[1]) : null; };
        return { key: g('key'), label: g('label'), title: g('title') };
      }).filter((c) => c.key);
      const hsFundM = /export const HS_FUND_KEYS = \[([^\]]*)\] as const;/.exec(hs);
      const hsFund = hsFundM ? [...hsFundM[1].matchAll(/'([a-z0-9_]+)'/g)].map((m) => m[1]) : [];
      if (hs && hsFund.length !== 6) errs.push(`HottestSectors.tsx must export const HS_FUND_KEYS = [the six fund keys] as const (parsed ${hsFund.length})`);

      // (1) Sales heads + the three titles = HS_COLS byte for byte.
      const FUND_SET = new Set(hsFund);
      const salesFund = salesCols.filter((c) => FUND_SET.has(c.key));
      for (const c of salesFund) {
        const h = hsCols.find((x) => x.key === c.key);
        if (!h) { errs.push(`HS_COLS has no '${c.key}' column`); continue; }
        if (c.label == null) errs.push(`high_beta_tab.SALES_COLUMNS "${c.key}" label is not a string literal — this pin cannot read it`);
        else if (c.label !== h.label) errs.push(`high_beta_tab.SALES_COLUMNS "${c.key}" head "${c.label}" != 🔥 HS_COLS "${h.label}"`);
        if (h.title != null && pyTitle(c.key) !== h.title) errs.push(`high_beta_tab.COLUMN_TITLES["${c.key}"] "${pyTitle(c.key)}" != 🔥 HS_COLS title "${h.title}"`);
      }
      for (const k of ['sales_tier', 'eq_score', 'next_earnings']) {
        if (hsCols.length && !hsCols.find((x) => x.key === k && x.title)) errs.push(`🔥 HS_COLS '${k}' lost its title — the 🎢 copy has nothing to equal`);
      }

      // (2) HS_FUND_KEYS = the Sales fund keys in order (contiguous) = HS_COLS minus the legs = FUND_SORTS ∪ {tier, ER}.
      const salesKeys = salesCols.map((c) => c.key);
      const at = salesKeys.indexOf(hsFund[0]);
      if (hsFund.length && salesKeys.slice(at, at + hsFund.length).join(',') !== hsFund.join(',')) {
        errs.push(`high_beta_tab.SALES_COLUMNS must carry HS_FUND_KEYS [${hsFund.join(', ')}] contiguous and in order (got [${salesKeys.join(', ')}])`);
      }
      const hsMinusLegs = hsCols.map((c) => c.key).filter((k) => !/^rel_\d+d$/.test(k));
      if (hsCols.length && hsMinusLegs.join(',') !== hsFund.join(',')) errs.push(`HS_FUND_KEYS [${hsFund.join(', ')}] != HS_COLS minus rel_* [${hsMinusLegs.join(', ')}]`);
      const want = new Set([...fundSorts, 'sales_tier', 'next_earnings']);
      if (fundSorts.length && (want.size !== FUND_SET.size || [...want].some((k) => !FUND_SET.has(k)))) {
        errs.push(`HS_FUND_KEYS {${hsFund.join(', ')}} != hottest.FUND_SORTS ∪ {sales_tier, next_earnings} {${[...want].join(', ')}}`);
      }

      // (3) HsFundCell reads only FUND_ROW_KEYS; HsFundRow picks exactly them.
      const cellAt = hs.indexOf('export function HsFundCell(');
      const cellEnd = cellAt >= 0 ? hs.indexOf('\n}\n', cellAt) : -1;
      const cellBody = cellAt >= 0 && cellEnd > cellAt ? strip(hs.slice(cellAt, cellEnd)) : '';
      if (hs && !cellBody) errs.push('HottestSectors.tsx lost export function HsFundCell(…) { … }');
      const reads = [...new Set([...cellBody.matchAll(/(?<![\w.])r\.([a-z0-9_]+)/g)].map((m) => m[1]))];
      if (cellBody && !reads.length) errs.push('HsFundCell reads no r.<key> — this pin cannot see its fields');
      const fundRowErrors = (rd, keys) => rd.filter((k) => !keys.includes(k)).map((k) => `HsFundCell reads r.${k} — not in high_beta_tab.FUND_ROW_KEYS (the 🎢 row would print it blank)`);
      if (fundRowKeys.length) errs.push(...fundRowErrors(reads, fundRowKeys));
      const pickM = /export type HsFundRow = Pick<HsName,([^>]*)>/.exec(hs);
      const pick = pickM ? [...pickM[1].matchAll(/'([a-z0-9_]+)'/g)].map((m) => m[1]) : [];
      if (hs && !pick.length) errs.push("HottestSectors.tsx lost export type HsFundRow = Pick<HsName, '…'>");
      if (pick.length && fundRowKeys.length && (pick.length !== fundRowKeys.length || pick.some((k) => !fundRowKeys.includes(k)))) {
        errs.push(`HsFundRow picks {${pick.join(', ')}} != high_beta_tab.FUND_ROW_KEYS {${fundRowKeys.join(', ')}}`);
      }

      // (4) B2 mirror: every served TABLE_COLUMNS / SALES_COLUMNS key ∈ HighBetaBoardNote COLUMN_KEYS.
      const code = strip(note);
      const setLits = (name, depth = 0) => {
        if (name === 'HS_FUND_KEYS') return /import \{[^}]*\bHS_FUND_KEYS\b[^}]*\} from '\.\/HottestSectors'/.test(note) ? hsFund : null;
        if (depth > 3) return null;
        const m = new RegExp(`(?:export )?const ${name}\\b[^=]*= new Set(?:<[^>]*>)?\\(([\\s\\S]*?)\\);`).exec(code);
        if (!m) return null;
        const body = m[1];
        const out = [...body.matchAll(/'([a-z0-9_]+)'/g)].map((x) => x[1]);
        for (const s of body.matchAll(/(?:\.\.\.)?\b([A-Z][A-Z0-9_]+)\b/g)) {
          const sub = setLits(s[1], depth + 1);
          if (sub == null) return null;
          out.push(...sub);
        }
        return out;
      };
      const colKeys = setLits('COLUMN_KEYS');
      if (colKeys == null) errs.push('HighBetaBoardNote.tsx: export const COLUMN_KEYS = new Set([…]) could not be resolved (a spread of an unknown set) — this pin cannot read it');
      const colKeyErrors = (served, known) => served.filter((k) => !known.includes(k)).map((k) => `high_beta_tab serves column "${k}" — not in HighBetaBoardNote COLUMN_KEYS, so the table silently drops it`);
      const servedKeys = [...new Set([...tableCols, ...salesCols].map((c) => c.key))];
      if (colKeys) errs.push(...colKeyErrors(servedKeys, colKeys));

      // (5) The 🔥 table recipe, and the table never sorts rows itself.
      if (!/import \{[^}]*\bHsFundCell\b[^}]*\} from '\.\/HottestSectors'/.test(note)) errs.push("HighBetaBoardNote.tsx must import { HsFundCell } from './HottestSectors' — one cell renderer");
      if (!/import \{[^}]*\buseHScrollCue\b[^}]*\} from '\.\.\/hooks\/useHScrollCue'/.test(note)) errs.push("HighBetaBoardNote.tsx must import { useHScrollCue } from '../hooks/useHScrollCue'");
      for (const cls of ['hs-scrollwrap', 'hs-scroll', 'hs-table', 'hs-sym', 'hs-sort', 'is-sorted', 'cm-hb-scroll']) {
        if (!new RegExp(`(?<![\\w-])${cls}(?![\\w-])`).test(code)) errs.push(`HighBetaBoardNote.tsx must use the ${cls} class (the 🔥 Hottest header recipe)`);
      }
      if (/\.(?:sort|toSorted)\(/.test(code)) errs.push('HighBetaBoardNote.tsx calls .sort( / .toSorted( — the server owns the order (the cards follow it)');
      const used = [...new Set([...code.matchAll(/(?<![\w-])(hs-[a-z][a-z0-9-]*|cm-hb-scroll)(?![\w-])/g)].map((m) => m[1]))];
      const cssErrors = (classes, sheet) => classes.filter((c) => !new RegExp(`\\.${c}(?![\\w-])`).test(sheet)).map((c) => `HighBetaBoardNote.tsx uses .${c} but styles.css has no rule for it`);
      errs.push(...cssErrors(used, css));

      // (6) The generic Sort select is not on 🎢 (BUILD_SPEC2 §7 his call: buttons + headers own the order).
      if (!/tab !== 'high_beta' && \(data\?\.sorts \|\| \[\]\)\.length > 0 && \(\s*<label className="cm-ctl">\s*Sort\s*<select\s*aria-label="Sort the board"/.test(page)) {
        errs.push("ChartMaps.tsx: the \"Sort the board\" select must be gated by tab !== 'high_beta' && (data?.sorts || []).length > 0");
      }

      // (7) The ✨ entry: present, dated, routed, his ask verbatim, UNMEASURED, no bounce / fake / forecast word,
      // and every number it types is the engine's.
      const ID = 'chart-maps-high-beta-table-2026-10-15';
      const ASK = 'Can you add sort function on the headers and also 5 day and 21 days columns to show how they were reacting in price like hot sectors and also add sales tab make it like hot sector with some important metrics like EPS, QUAlity and other colums that show the strength of the stock';
      const tnum = (name) => { const m = new RegExp(`^${name} = (\\d+)\\b`, 'm').exec(tracker); return m ? Number(m[1]) : null; };
      const tstr = (name) => { const m = new RegExp(`^${name} = "([A-Z]+)"`, 'm').exec(tracker); return m ? m[1] : null; };
      const lim = /^LIMIT_MAX = (\d+)\b/m.exec(boardPy);
      const dp = /^LEG_TEXT_DP = (\d+)\b/m.exec(hb);
      const ttlM = /^BASE_TTL_SEC = (\d+)(?: \* (\d+))?\s/m.exec(d10);
      const T = { fast: tnum('WINDOW_FAST'), short: tnum('WINDOW_SHORT'), med: tnum('WINDOW_MED'),
                  rsp: tstr('BENCHMARK'), spy: tstr('BENCHMARK_FALLBACK'), limit: lim ? Number(lim[1]) : null,
                  dp: dp ? Number(dp[1]) : null, ttl: ttlM ? Number(ttlM[1]) * Number(ttlM[2] || 1) : null,
                  forbidden: pyStrs(pyBlock(hb, 'FORBIDDEN_WORDS')) };
      for (const [k, v] of Object.entries(T)) if (v == null || (Array.isArray(v) && !v.length)) errs.push(`✨ pin: could not read ${k} from the engines (tracker WINDOW_* / BENCHMARK*, board.LIMIT_MAX, high_beta_tab.LEG_TEXT_DP / FORBIDDEN_WORDS, drop10_tab.BASE_TTL_SEC)`);
      // The tab's legs ARE the tracker's windows, and its Sales memo IS the base TTL.
      for (const [name, src] of [['LEG_FAST', 'WINDOW_FAST'], ['LEG_SHORT', 'WINDOW_SHORT'], ['RS_WINDOW', 'WINDOW_MED']]) {
        if (hb && !new RegExp(`^${name} = RT\\.${src}\\b`, 'm').test(hb)) errs.push(`high_beta_tab.${name} must be RT.${src} (the 🔥 tracker's own window)`);
      }
      if (hb && !/^FUND_TTL_SEC = BASE_TTL_SEC\b/m.test(hb)) errs.push('high_beta_tab.FUND_TTL_SEC must be BASE_TTL_SEC (the ✨ says "at most once an hour")');
      if (hb && !/^BASE_TTL_SEC(?:, \w+)* = D10\.BASE_TTL_SEC\b/m.test(hb)) errs.push('high_beta_tab.BASE_TTL_SEC must be drop10_tab.BASE_TTL_SEC');
      if (!/^REL_FALLBACK = RT\.BENCHMARK_FALLBACK\b/m.test(hb)) errs.push('high_beta_tab.REL_FALLBACK must be RT.BENCHMARK_FALLBACK');

      // Position is NOT pinned (2026-10-15): the ✨ list is newest-first, so a later feature sits above this one.
      const idAt = nf.indexOf(`{ id: '${ID}'`);
      let entry;
      if (idAt >= 0) {
        const nextAt = nf.indexOf('{ id: ', idAt + 4);
        const raw = nf.slice(idAt, nextAt < 0 ? nf.indexOf('\n];', idAt) : nextAt);
        const g = (f) => { const m = new RegExp(`${f}: (['"])((?:(?!\\1)[^\\\\]|\\\\.)*)\\1`).exec(raw); return m ? unesc(m[2]) : null; };
        entry = { id: ID, addedAt: g('addedAt'), route: g('route'), label: g('label') || '' };
      }
      const entryErrors = (e, t) => {
        if (!e) return [`newFeatures.ts lacks the ✨ entry id: '${ID}'`];
        const out = [];
        if (e.addedAt !== '2026-10-15') out.push(`the ✨ entry addedAt '${e.addedAt}' must be '2026-10-15' (the ET ship date)`);
        if (e.route !== '/chart-maps?tab=high_beta') out.push(`the ✨ entry must route to '/chart-maps?tab=high_beta' (got '${e.route}')`);
        const d = e.label;
        if (!d.includes(`“${ASK}”`)) out.push('the ✨ entry must quote his ask verbatim, in “ ”');
        if (!d.includes('UNMEASURED')) out.push('the ✨ entry must say UNMEASURED');
        if (!/not advice/i.test(d)) out.push('the ✨ entry must say not advice');
        if (/bounc|fake/i.test(d)) out.push('the ✨ entry says "bounce"/"fake" — surfaces he reads say reversal');
        for (const w of t.forbidden) if (d.toLowerCase().includes(w.toLowerCase())) out.push(`the ✨ entry says "${w}" (high_beta_tab.FORBIDDEN_WORDS)`);
        const mine = d.split('You said:')[0];
        const wins = [t.fast, t.short, t.med];
        for (const need of [`${t.fast} days`, `${t.short} days`, `${t.med} sessions`, `${t.limit} charts`, `against ${t.rsp}`, `RS vs ${t.spy}`]) {
          if (!mine.includes(need)) out.push(`the ✨ entry must state "${need}" before "You said:" (the engines' value)`);
        }
        for (const m of d.matchAll(/\b(\d+)[ -](?:days?|sessions?)\b|\b(\d+)d\b/g)) {
          if (!wins.includes(Number(m[1] || m[2]))) out.push(`the ✨ entry says "${m[0]}" — the windows are tracker WINDOW_FAST/SHORT/MED ${wins.join(' / ')}`);
        }
        for (const m of d.matchAll(/\b(\d+) charts\b/g)) if (Number(m[1]) !== t.limit) out.push(`the ✨ entry says "${m[0]}" — board.LIMIT_MAX is ${t.limit}`);
        for (const m of d.matchAll(/\b(\d+) decimals?\b/g)) if (Number(m[1]) !== t.dp) out.push(`the ✨ entry says "${m[0]}" — high_beta_tab.LEG_TEXT_DP is ${t.dp}`);
        if (/once an hour/.test(d) && t.ttl !== 3600) out.push(`the ✨ entry says "once an hour" — drop10_tab.BASE_TTL_SEC is ${t.ttl} s`);
        for (const m of d.matchAll(/\b(\d+) minutes\b/g)) if (Number(m[1]) * 60 !== t.ttl) out.push(`the ✨ entry says "${m[0]}" — FUND_TTL_SEC is ${t.ttl} s`);
        return out;
      };
      errs.push(...entryErrors(entry, T));

      // NEGATIVE self-tests: each checker must catch its own drift.
      if (entry && !errs.length) {
        const swap = (from, to) => ({ ...entry, label: entry.label.replace(from, to) });
        const muts = [
          ['21 days → 20 days', swap(`${T.short} days`, '20 days')],
          ['63 sessions → 60 sessions', swap(`${T.med} sessions`, '60 sessions')],
          ['80 charts → 50 charts', swap(`${T.limit} charts`, '50 charts')],
          ['1 decimal → 2 decimals', swap(`${T.dp} decimal`, '2 decimals')],
          ['once an hour → 15 minutes', swap('once an hour', 'once every 15 minutes')],
          ['UNMEASURED dropped', { ...entry, label: entry.label.replace('UNMEASURED', 'measured') }],
          ['ask edited', { ...entry, label: entry.label.replace('QUAlity', 'Quality') }],
          ['a bounce', { ...entry, label: `${entry.label} A bounce.` }],
          ['a forecast word', { ...entry, label: `${entry.label} Names likely to run.` }],
          ['route', { ...entry, route: '/chart-maps' }],
          ['addedAt', { ...entry, addedAt: '2026-10-14' }],
        ];
        for (const [what, bad] of muts) {
          if (bad.label === entry.label && bad.route === entry.route && bad.addedAt === entry.addedAt) errs.push(`self-test: the "${what}" mutation did not apply — the ✨ label moved`);
          else if (!entryErrors(bad, T).length) errs.push(`self-test: the ✨ checker missed "${what}"`);
        }
        if (entryErrors(undefined, T).length !== 1) errs.push('self-test: a missing ✨ entry is not reported');
        if (colKeys && !colKeyErrors([...servedKeys, 'zz_new_col'], colKeys).length) errs.push('self-test: a served column key outside COLUMN_KEYS was not caught');
        if (!fundRowErrors([...reads, 'zz_new_field'], fundRowKeys).length) errs.push('self-test: an HsFundCell read outside FUND_ROW_KEYS was not caught');
        if (!cssErrors(['hs-zz-norule'], css).length) errs.push('self-test: a class with no styles.css rule was not caught');
      }
      return errs;
    },
  },
  {
    name: '🎢 🗺️ tape-burst kinds (2026-10-14): in every registry, owner keep-set ON + default_prefs False, MARKET kinds, LIVE (never shadow), the burst numbers = tape.py, caps = tape_burst_kinds.py, window = trade_flash, own /alerts strip + chips, per-ticker tape links, never bounce',
    file: 'src/lib/alertKinds.ts',
    // Ajay 2026-10-14: "I need a tape burst notification specific for High
    // Beta stocks from the reselinet separately and also other tape bursts
    // from the Chart Maps page"; asked which names: "High-Beta tab names + all
    // Chart Maps names". A kind missing from any registry sends to zero devices
    // in silence (memory cheetah_push_silent_drops) or renders a raw id; a
    // number typed on the Notifications page drifts from the engine the way the
    // cap floor did (review 2026-09-14 F5). ⚡ trade_flash stays OUT of the
    // keep-set — his 2026-09-08 "Also kill the tape burst" (BUILD_SPEC §7 #7).
    checks: (src) => {
      const errs = [];
      const KINDS = ['tape_burst_highbeta', 'tape_burst_chartmaps'];
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16))).replace(/\\'/g, "'");
      const prefsTs = read('src/hooks/useNotificationPrefs.ts');
      const subs = read('../backend/push/subs.py');
      const keep = keepSet(subs);
      const gate = read('../backend/market_hours/gate.py');
      const market = pyFrozenSet(gate, 'MARKET_ALERT_KINDS') || [];
      const personal = pyFrozenSet(gate, 'PERSONAL_KINDS') || [];
      const recent = read('../backend/push/recent.py');
      const itemBlock = (/^ITEM_URL_BY_KIND = \{([\s\S]*?)\n\}/m.exec(recent) || [])[1] || '';
      let status = '';
      try { status = read('../backend/supply_demand/alert_status.py'); } catch { errs.push('backend/supply_demand/alert_status.py is unreadable'); }
      const notif = read('src/pages/Notifications.tsx');
      const ess = notif.slice(notif.indexOf("id: 'essentials'"), notif.indexOf("id: 'trading_only'"));
      const alerts = read('src/pages/Alerts.tsx');
      const passesBlock = (/const PASSES:[^=]*=\s*\[([\s\S]*?)\n\];/.exec(alerts) || [])[1] || '';
      const tapeBlock = (/export const TAPE_PASSES:[^=]*=\s*\[([\s\S]*?)\n\];/.exec(alerts) || [])[1] || '';
      const chipsLine = (/KIND_CHIPS: string\[\] = \[([^\]]*)\]/.exec(alerts) || [])[1] || '';
      if (!tapeBlock) errs.push('Alerts.tsx lost export const TAPE_PASSES = [...] — the tape passes get their own strip');

      // The numbers the rows type, read from the engines.
      const tape = read('../backend/orderflow/tape.py');
      const tnum = (name) => { const m = new RegExp(`^${name} = ([0-9_.]+)`, 'm').exec(tape); return m ? Number(m[1].replace(/_/g, '')) : null; };
      const win = tnum('BURST_WINDOW_SEC'), dollars = tnum('BURST_MIN_DOLLARS'), oneSided = tnum('BURST_ONE_SIDED'), trades = tnum('BURST_MIN_TRADES');
      if ([win, dollars, oneSided, trades].some((x) => x == null || !Number.isFinite(x))) errs.push('orderflow/tape.py lost a BURST_* constant (WINDOW_SEC / MIN_DOLLARS / ONE_SIDED / MIN_TRADES)');
      let tbk = '';
      try { tbk = read('../backend/orderflow/tape_burst_kinds.py'); } catch { errs.push('backend/orderflow/tape_burst_kinds.py is missing (WP2)'); }
      const cap = (name) => { const m = new RegExp(`^${name} = ([0-9_]+)`, 'm').exec(tbk); return m ? Number(m[1].replace(/_/g, '')) : null; };
      const CAPS = { tape_burst_highbeta: cap('HIGHBETA_MAX_SYMBOLS'), tape_burst_chartmaps: cap('CHARTMAPS_MAX_SYMBOLS') };
      if (tbk && Object.values(CAPS).some((x) => x == null)) errs.push('tape_burst_kinds.py lost HIGHBETA_MAX_SYMBOLS / CHARTMAPS_MAX_SYMBOLS = <int>');
      if (tbk && /bounc|fake/i.test(tbk.replace(/#[^\n]*/g, ''))) errs.push('tape_burst_kinds.py says "bounce"/"fake"');
      const tf = read('../backend/orderflow/trade_flash.py');
      const dt = (name) => { const m = new RegExp(`^${name} = dtime\\((\\d+),\\s*(\\d+)\\)`, 'm').exec(tf); return m ? `${m[1].padStart(2, '0')}:${m[2].padStart(2, '0')}` : null; };
      const open = dt('WATCH_OPEN_ET'), close = dt('WATCH_CLOSE_ET');
      if (!open || !close) errs.push('trade_flash.py must name the window WATCH_OPEN_ET = dtime(9, 32) / WATCH_CLOSE_ET = dtime(16, 0) (WP2)');
      // The house share-price floor the 🎢 watch list (board.high_beta_watch) and
      // scan_kind's `under_floor` apply — typed as "$2" on both rows (2026-10-14 fix).
      let floor = null;
      try {
        const m = /^MIN_SHARE_PRICE = ([0-9.]+)/m.exec(read('../backend/trading/safety_floor.py'));
        floor = m ? Number(m[1]) : null;
      } catch { /* reported below */ }
      if (floor == null || !Number.isFinite(floor)) errs.push('trading/safety_floor.py lost MIN_SHARE_PRICE = <number>');
      const floorText = floor == null ? null : `$${Number.isInteger(floor) ? floor : floor.toFixed(2)}`;
      const cronLines = cronCommands(read('../backend/crontab')).filter((l) => /sepa\.cli trade-flash-watch/.test(l));
      if (cronLines.length !== 1) errs.push(`the crontab must carry exactly one sepa.cli trade-flash-watch line (found ${cronLines.length}) — the two kinds ride it`);
      const stepM = cronLines.length === 1 ? /^\S*\/(\d+)\s/.exec(cronLines[0].trim()) : null;
      const step = stepM ? Number(stepM[1]) : null;

      for (const k of KINDS) {
        if (!new RegExp(`^\\s*${k}:\\s*\\{[^}]*group: 'tape'`, 'm').test(src)) errs.push(`alertKinds.ts must register ${k} in the 'tape' group — else the bell renders a raw id`);
        const def = (new RegExp(`^\\s*${k}:\\s*\\{[^}]*\\}`, 'm').exec(src) || [''])[0];
        if (/bounce|shadow/i.test(def.replace(k, ''))) errs.push(`the ${k} label says bounce / shadow`);
        if (!new RegExp(`\\b${k}\\?: boolean`).test(prefsTs)) errs.push(`NotificationPrefs (hooks/useNotificationPrefs.ts) must carry ${k}?: boolean`);
        const dm = new RegExp(`["']${k}["']\\s*:\\s*(True|False)`).exec(subs);
        if (!dm) errs.push(`push/subs.py default_prefs must list "${k}"`);
        else if (dm[1] !== 'False') errs.push(`${k} must be False in push/subs.py default_prefs — owner-only, everyone else starts off`);
        if (!keep.includes(k)) errs.push(`${k} must be in push/subs.OWNER_KEEP_SET — ON for him (his K4 answer, A12)`);
        if (!market.includes(k)) errs.push(`market_hours/gate.py must treat ${k} as a MARKET kind (silent on closed days)`);
        if (personal.includes(k)) errs.push(`${k} must NOT be a PERSONAL kind`);
        const iu = new RegExp(`["']${k}["']\\s*:\\s*([^,\\n]+)`).exec(itemBlock);
        if (!iu) errs.push(`push/recent.ITEM_URL_BY_KIND must carry ${k} — every ticker of a push is its own link on /alerts`);
        else if (/^["']/.test(iu[1].trim()) && !/^["']\/sepa\/\{sym\}\?tab=tape/.test(iu[1].trim())) errs.push(`push/recent.ITEM_URL_BY_KIND["${k}"] must open the ticker's tape (/sepa/{sym}?tab=tape…), got ${iu[1].trim()}`);
        if (status && !new RegExp(`["']${k}["']`).test(status)) errs.push(`supply_demand/alert_status.py must record the ${k} pass (PASS_KINDS / CADENCE_SEC)`);
        if (!new RegExp(`key: '${k}'`).test(tapeBlock)) errs.push(`Alerts.tsx TAPE_PASSES must carry key: '${k}'`);
        if (new RegExp(`'${k}'`).test(passesBlock)) errs.push(`Alerts.tsx PASSES must NOT carry ${k} — it would join "all N passes" and read stale outside its window`);
        if (!new RegExp(`'${k}'`).test(chipsLine)) errs.push(`Alerts.tsx KIND_CHIPS must carry '${k}'`);
        if (!new RegExp(`${k}:\\s*true`).test(ess)) errs.push(`Essentials must carry ${k}: true — it is in OWNER_KEEP_SET`);

        const nm = notif.match(new RegExp(`key: '${k}'[\\s\\S]*?' \\},\\n`));
        if (!nm) { errs.push(`${k} must be listed on the Notifications page — a kind the page cannot show cannot be muted`); continue; }
        const d = unesc(nm[0]);
        for (const need of ['ON FOR YOUR PHONE', 'rings live', 'UNMEASURED', 'every burst listed on /alerts']) {
          if (!d.includes(need)) errs.push(`the ${k} Notifications entry must say "${need}"`);
        }
        if (/shadow/i.test(d)) errs.push(`the ${k} Notifications entry says "shadow" — the kind rings live`);
        if (/every burst is sent|nothing is held back/i.test(d)) errs.push(`the ${k} Notifications entry says every burst is sent — the house floor, the poll budget and the cold first poll hold some back`);
        if (!d.includes('NOT READ:')) errs.push(`the ${k} Notifications entry must carry its NOT READ: sentence (what never reaches the push)`);
        if (floorText) {
          if (!d.includes(`house share-price floor (${floorText})`)) errs.push(`the ${k} entry must state "house share-price floor (${floorText})" as trading/safety_floor.MIN_SHARE_PRICE has it`);
          for (const m of d.matchAll(/share-price floor \(\$([0-9.]+)\)/g)) if (Number(m[1]) !== floor) errs.push(`the ${k} entry says "${m[0]}" — safety_floor.MIN_SHARE_PRICE is ${floor}`);
        }
        if (/OFF BY DEFAULT/.test(d)) errs.push(`the ${k} Notifications entry says OFF BY DEFAULT while the keep-set carries it`);
        if (/boun|fake/i.test(d)) errs.push(`the ${k} Notifications entry says "bounce"/"fake"`);
        if (win != null && dollars != null && oneSided != null && trades != null) {
          for (const need of [`${win}-second window`, `$${dollars / 1000}K or more`, `${Math.round(oneSided * 100)}% or more of it on one side`, `${trades}+ regular prints`]) {
            if (!d.includes(need)) errs.push(`the ${k} Notifications entry must state "${need}" as orderflow/tape.py has it`);
          }
          for (const m of d.matchAll(/(\d+)-second/g)) if (Number(m[1]) !== win) errs.push(`the ${k} entry says "${m[0]}" — tape.BURST_WINDOW_SEC is ${win}`);
          for (const m of d.matchAll(/\$(\d+)K/g)) if (Number(m[1]) * 1000 !== dollars) errs.push(`the ${k} entry says "${m[0]}" — tape.BURST_MIN_DOLLARS is ${dollars}`);
          for (const m of d.matchAll(/(\d+)\+ regular prints/g)) if (Number(m[1]) !== trades) errs.push(`the ${k} entry says "${m[0]}" — tape.BURST_MIN_TRADES is ${trades}`);
        }
        if (CAPS[k] != null) {
          if (!d.includes(`up to ${CAPS[k]} names`)) errs.push(`the ${k} entry must state "up to ${CAPS[k]} names" as tape_burst_kinds.py has it`);
          for (const m of d.matchAll(/up to (\d+) names/g)) if (Number(m[1]) !== CAPS[k]) errs.push(`the ${k} entry says "${m[0]}" — tape_burst_kinds caps it at ${CAPS[k]}`);
        }
        if (open && close && !d.includes(`${open}–${close} ET`)) errs.push(`the ${k} entry must state "${open}–${close} ET" (trade_flash.WATCH_OPEN_ET / WATCH_CLOSE_ET)`);
        if (step != null && !d.includes(`Every ${step} minutes`)) errs.push(`the ${k} entry must say "Every ${step} minutes" — the trade-flash-watch line's minute step`);
      }
      if (keep.includes('trade_flash')) errs.push('⚡ trade_flash must stay OUT of OWNER_KEEP_SET — his 2026-09-08 "Also kill the tape burst"');
      if (/shadow/i.test(tapeBlock)) errs.push('the TAPE_PASSES labels say shadow — both kinds ring live');
      const chipFn = (/export function tapeBurstChipText[\s\S]*?\n\}/.exec(alerts) || [''])[0];
      if (!chipFn) errs.push('Alerts.tsx lost tapeBurstChipText — the tape counters would render as raw keys');
      if (/shadow|bounce/i.test(chipFn)) errs.push('tapeBurstChipText says shadow / bounce');
      if (/sent as ⚡/.test(chipFn)) errs.push('tapeBurstChipText says "sent as ⚡" — ⚡ trade flash is muted on his phone; it is "recorded" (A4)');
      // The chip keys must be the counters tape_burst_kinds._served emits:
      // `claimed_zone` is never served (a dead chip with the A5-contradicting
      // words), `at_zone` / `under_floor` are; the re-sightings stay off the row.
      if (/case 'claimed_zone'/.test(chipFn)) errs.push('tapeBurstChipText words claimed_zone — tape_burst_kinds never serves it (the served key is at_zone, A5)');
      for (const key of ['at_zone', 'under_floor']) {
        if (!new RegExp(`case '${key}'`).test(chipFn)) errs.push(`tapeBurstChipText must word ${key} — tape_burst_kinds serves it`);
        if (tbk && !new RegExp(`"${key}"`).test(tbk)) errs.push(`tape_burst_kinds.py no longer serves "${key}" — the /alerts chip would be dead`);
      }
      if (!/const TAPE_HIDDEN_KEYS = \[[^\]]*'dup_same'[^\]]*'dup_earlier'/.test(alerts)) errs.push("Alerts.tsx must keep TAPE_HIDDEN_KEYS = ['dup_same', 'dup_earlier'] — re-sightings are not fresh (A3)");
      return errs;
    },
  },
  {
    name: '🎚️ tape_control (2026-10-16): WATCH / KIND / RULE_WORD in tape_control.py, in every registry, owner keep-set ON + default_prefs False, MARKET kind, own /alerts row after the tape strip, chip after 🧠, Notifications + ✨ numbers = tape.LATE_WINDOW_MIN + trade_flash window + the crontab step + WATCH, the FE composes no pin sentence, never the b-word',
    file: 'src/lib/alertKinds.ts',
    // Ajay 2026-10-16: "Can you add a watcher tape for IREN please." then "I
    // wwant you to alert me when the Buyers are winning in tape for IREN
    // today." He ACTS on this push (real money): a kind missing from a
    // registry sends to zero devices in silence (memory
    // cheetah_push_silent_drops); a number or a pinned name typed on a surface
    // drifts from the constant that drives the pass; a sentence the FE composes
    // can contradict the read the backend served. The tape-burst block above is
    // the template (a LIVE owner-only kind). UNMEASURED.
    checks: (src) => {
      const errs = [];
      const K = 'tape_control';
      const ASK1 = 'Can you add a watcher tape for IREN please.';
      const ASK2 = 'I wwant you to alert me when the Buyers are winning in tape for IREN today.';
      const BANNED = /boun|fak[e]/i;
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16))).replace(/\\'/g, "'");
      const pyNoComments = (x) => x.replace(/#[^\n]*/g, '');
      const tsNoComments = (x) => x.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '');

      // 1. the module and its frozen names.
      let tc = '';
      try { tc = read('../backend/orderflow/tape_control.py'); } catch { errs.push('backend/orderflow/tape_control.py is unreadable (WP-A)'); return errs; }
      const watchLine = (/^WATCH = \{[^\n]*$/m.exec(tc) || [''])[0];
      const watchBody = (/^WATCH = \{([^}\n]*)\}/m.exec(tc) || [])[1];
      const pins = [];
      if (watchBody == null) errs.push('tape_control.py must define WATCH = {"SYM": "YYYY-MM-DD" | None} on one line');
      else {
        for (const m of watchBody.matchAll(/"([A-Z][A-Z.]{0,5})"\s*:\s*(?:"(\d{4}-\d{2}-\d{2})"|(None))/g)) pins.push({ sym: m[1], until: m[2] || null });
        const rest = watchBody.replace(/"([A-Z][A-Z.]{0,5})"\s*:\s*(?:"(\d{4}-\d{2}-\d{2})"|(None))/g, '').replace(/[\s,]/g, '');
        if (!pins.length) errs.push('tape_control.WATCH must hold at least one "SYM": "YYYY-MM-DD" | None pair');
        if (rest) errs.push(`tape_control.WATCH carries an entry the contracts cannot read: ${rest}`);
      }
      if (!/# Ajay 2026-10-16/.test(watchLine)) errs.push('the WATCH = line must carry "# Ajay 2026-10-16" — the pin is his number');
      if (!/^KIND = "tape_control"/m.test(tc)) errs.push('tape_control.py must define KIND = "tape_control"');
      if (!/^RULE_WORD = "tick rule"/m.test(tc)) errs.push('tape_control.py must define RULE_WORD = "tick rule" — the surfaces say "tick rule"');
      if (BANNED.test(pyNoComments(tc))) errs.push('tape_control.py says the b-word or the sham word');
      const titleLine = (/^TITLE_FMT = [^\n]*/m.exec(tc) || [''])[0];
      const headlineFn = (/^def headline\([\s\S]*?(?=\n(?:def |[A-Z_]+ = |@)|$(?![\s\S]))/m.exec(tc) || [''])[0];
      if (!titleLine) errs.push('tape_control.py lost TITLE_FMT');
      if (!headlineFn) errs.push('tape_control.py lost def headline(ev)');
      if (/\bbuy\b|\benter/i.test(pyNoComments(titleLine + '\n' + headlineFn))) errs.push('TITLE_FMT / headline say "buy" or "enter" — "buyers" only, it is a read of the tape, not an entry');

      // 2. the numbers the surfaces type, read from the engines.
      const late = (() => { const m = /^LATE_WINDOW_MIN = (\d+)/m.exec(read('../backend/orderflow/tape.py')); return m ? Number(m[1]) : null; })();
      if (late == null) errs.push('orderflow/tape.py lost LATE_WINDOW_MIN = <int>');
      const tf = read('../backend/orderflow/trade_flash.py');
      const dt = (name) => { const m = new RegExp(`^${name} = dtime\\((\\d+),\\s*(\\d+)\\)`, 'm').exec(tf); return m ? `${m[1].padStart(2, '0')}:${m[2].padStart(2, '0')}` : null; };
      const open = dt('WATCH_OPEN_ET'), close = dt('WATCH_CLOSE_ET');
      if (!open || !close) errs.push('trade_flash.py must name the window WATCH_OPEN_ET / WATCH_CLOSE_ET = dtime(H, M)');
      const cronLines = cronCommands(read('../backend/crontab')).filter((l) => /sepa\.cli trade-flash-watch/.test(l));
      const stepM = cronLines.length === 1 ? /^\S*\/(\d+)\s/.exec(cronLines[0].trim()) : null;
      const step = stepM ? Number(stepM[1]) : null;
      if (step == null) errs.push('the crontab must carry exactly one sepa.cli trade-flash-watch line with a minute step — 🎚️ rides it');
      // the surface copy must name every pin and its last session (or "standing").
      const pinErrs = (where, text) => {
        const out = [];
        for (const p of pins) {
          if (!text.includes(p.sym)) out.push(`${where} must name the pinned ${p.sym} (tape_control.WATCH)`);
          if (p.until ? !text.includes(p.until) : !/standing/.test(text)) out.push(`${where} must state ${p.sym}'s pin as ${p.until || '"standing"'} (tape_control.WATCH)`);
        }
        return out;
      };
      const numErrs = (where, text) => {
        const out = [];
        if (late != null) {
          if (!text.includes(`last ${late} minutes`)) out.push(`${where} must say "last ${late} minutes" (tape.LATE_WINDOW_MIN)`);
          for (const m of text.matchAll(/(\d+) minutes’ delta/g)) if (Number(m[1]) !== late) out.push(`${where} says "${m[0]}" — tape.LATE_WINDOW_MIN is ${late}`);
          for (const m of text.matchAll(/last (\d+) minutes/g)) if (Number(m[1]) !== late) out.push(`${where} says "${m[0]}" — tape.LATE_WINDOW_MIN is ${late}`);
        }
        if (open && close && !text.includes(`${open}–${close} ET`)) out.push(`${where} must state "${open}–${close} ET" (trade_flash.WATCH_OPEN_ET / WATCH_CLOSE_ET)`);
        if (step != null && !text.includes(`Every ${step} minutes`)) out.push(`${where} must say "Every ${step} minutes" — the trade-flash-watch line's minute step`);
        return out;
      };

      // 3. every registry.
      if (!new RegExp(`^\\s*${K}:\\s*\\{[^\\n]*group: 'tape'`, 'm').test(src)) errs.push(`alertKinds.ts must register ${K} in the 'tape' group — else the bell renders a raw id`);
      const def = (new RegExp(`^\\s*${K}:\\s*\\{[^\\n]*`, 'm').exec(src) || [''])[0];
      if (/shadow/i.test(def) || BANNED.test(def)) errs.push(`the ${K} label says shadow / a banned word`);
      if (!new RegExp(`\\b${K}\\?: boolean`).test(read('src/hooks/useNotificationPrefs.ts'))) errs.push(`NotificationPrefs (hooks/useNotificationPrefs.ts) must carry ${K}?: boolean`);
      const subs = read('../backend/push/subs.py');
      const dm = new RegExp(`["']${K}["']\\s*:\\s*(True|False)`).exec(subs);
      if (!dm) errs.push(`push/subs.py default_prefs must list "${K}"`);
      else if (dm[1] !== 'False') errs.push(`${K} must be False in push/subs.py default_prefs — owner-only, everyone else starts off`);
      if (!keepSet(subs).includes(K)) errs.push(`${K} must be in push/subs.OWNER_KEEP_SET — "alert me" (DECISIONS7 D6)`);
      const gate = read('../backend/market_hours/gate.py');
      if (!(pyFrozenSet(gate, 'MARKET_ALERT_KINDS') || []).includes(K)) errs.push(`market_hours/gate.py must treat ${K} as a MARKET kind (silent on closed days)`);
      if ((pyFrozenSet(gate, 'PERSONAL_KINDS') || []).includes(K)) errs.push(`${K} must NOT be a PERSONAL kind`);
      const itemBlock = (/^ITEM_URL_BY_KIND = \{([\s\S]*?)\n\}/m.exec(read('../backend/push/recent.py')) || [])[1] || '';
      const iu = new RegExp(`["']${K}["']\\s*:\\s*([^,\\n]+)`).exec(pyNoComments(itemBlock));
      if (!iu) errs.push(`push/recent.ITEM_URL_BY_KIND must carry ${K} — the ticker of a ring is its own link on /alerts`);
      else if (!/^["']\/sepa\/\{sym\}\?tab=tape/.test(iu[1].trim())) errs.push(`push/recent.ITEM_URL_BY_KIND["${K}"] must open the ticker's tape (/sepa/{sym}?tab=tape…), got ${iu[1].trim()}`);
      let status = '';
      try { status = read('../backend/supply_demand/alert_status.py'); } catch { errs.push('backend/supply_demand/alert_status.py is unreadable'); }
      if (status && !new RegExp(`["']${K}["']`).test(pyNoComments(status))) errs.push(`supply_demand/alert_status.py must record the ${K} pass`);
      const alerts = read('src/pages/Alerts.tsx');
      const passesBlock = (/const PASSES:[^=]*=\s*\[([\s\S]*?)\n\];/.exec(alerts) || [])[1] || '';
      const tapeBlock = (/export const TAPE_PASSES:[^=]*=\s*\[([\s\S]*?)\n\];/.exec(alerts) || [])[1] || '';
      if (!/export const TAPE_CONTROL_PASS = \{\s*key: 'tape_control'/.test(alerts)) errs.push("Alerts.tsx must export TAPE_CONTROL_PASS = { key: 'tape_control', … } — its own row");
      if (new RegExp(`'${K}'`).test(passesBlock)) errs.push(`Alerts.tsx PASSES must NOT carry ${K} — it would join "all N passes" and read stale outside its window`);
      if (new RegExp(`'${K}'`).test(tapeBlock)) errs.push(`Alerts.tsx TAPE_PASSES must NOT carry ${K} — it has its own row`);
      const chips = [...((/KIND_CHIPS: string\[\] = \[([^\]]*)\]/.exec(alerts) || [])[1] || '').matchAll(/'([a-z0-9_]+)'/g)].map((m) => m[1]);
      if (!chips.includes(K)) errs.push(`Alerts.tsx KIND_CHIPS must carry '${K}'`);
      else if (chips.indexOf(K) < chips.indexOf('gajjala_potential')) errs.push(`Alerts.tsx KIND_CHIPS lists '${K}' before 'gajjala_potential' — it sits right after it`);
      const notif = read('src/pages/Notifications.tsx');
      const ess = notif.slice(notif.indexOf("id: 'essentials'"), notif.indexOf("id: 'trading_only'"));
      if (!new RegExp(`${K}:\\s*true`).test(ess)) errs.push(`Essentials must carry ${K}: true — it is in OWNER_KEEP_SET`);

      // 4. the Notifications entry.
      const nm = notif.match(new RegExp(`key: '${K}'[\\s\\S]*?' \\},\\n`));
      if (!nm) errs.push(`${K} must be listed on the Notifications page — a kind the page cannot show cannot be muted`);
      else {
        const d = unesc(nm[0]);
        const W = `the ${K} Notifications entry`;
        for (const need of ['ON FOR YOUR PHONE', 'rings live', 'UNMEASURED', 'tick rule', 'NOT READ:', ASK2]) {
          if (!d.includes(need)) errs.push(`${W} must say "${need}"`);
        }
        if (/shadow/i.test(d)) errs.push(`${W} says "shadow" — the kind rings live`);
        if (/OFF BY DEFAULT/.test(d)) errs.push(`${W} says OFF BY DEFAULT while the keep-set carries it`);
        if (BANNED.test(d)) errs.push(`${W} says the b-word or the sham word`);
        if (/buy signal/i.test(d)) errs.push(`${W} says "buy signal" — a read of the tape, not an entry`);
        errs.push(...pinErrs(W, d), ...numErrs(W, d));
      }

      // 5. the ✨ entry — FIRST, both verbatim quotes, the same numbers.
      const nf = read('src/lib/newFeatures.ts');
      const arr = nf.slice(nf.indexOf('export const NEW_FEATURES'));
      const firstAt = arr.indexOf("{ id: '");
      const firstId = (/^\{ id: '([^']+)'/.exec(arr.slice(firstAt)) || [])[1];
      const ID = 'alerts-tape-control-2026-10-16';
      // WIDENED 2026-10-16 — 🔴 live card overlay took the first ✨ slot the same day; this entry must be PRESENT (the newest feature is first).
      if (!nf.includes("id: 'alerts-tape-control-2026-10-16'")) errs.push("the ✨ entry 'alerts-tape-control-2026-10-16' is missing from NEW_FEATURES");
      const at = arr.indexOf(`{ id: '${ID}'`);
      if (at < 0) errs.push(`newFeatures.ts lacks the '${ID}' highlight`);
      else {
        const nextAt = arr.indexOf("{ id: '", at + 1);
        const e = unesc(arr.slice(at, nextAt < 0 ? undefined : nextAt));
        const W = 'the 🎚️ ✨ entry';
        if (!/route: '\/alerts'/.test(e)) errs.push(`${W} must route to '/alerts'`);
        for (const need of [ASK1, ASK2, 'tick rule', 'UNMEASURED']) if (!e.includes(need)) errs.push(`${W} must carry "${need}"`);
        if (BANNED.test(e)) errs.push(`${W} says the b-word or the sham word`);
        if (/buy signal/i.test(e)) errs.push(`${W} says "buy signal"`);
        errs.push(...pinErrs(W, e), ...numErrs(W, e));
      }

      // 6. the FE composes no pin sentence: TapeControlPins prints the served
      // `text` and `note`, and no string literal or JSX text in it names the read.
      const COMPOSED = /buyers|sellers|in control|delta|rang|tick rule/i;
      const composedIn = (fnSrc) => {
        const body = tsNoComments(fnSrc);
        const lits = [...body.matchAll(/(['"`])((?:\\.|(?!\1)[^\\])*?)\1/g)].map((m) => m[2]);
        const jsx = [...body.matchAll(/>([^<>{}]*[A-Za-z][^<>{}]*)</g)].map((m) => m[1]);
        return [...lits, ...jsx].filter((t) => COMPOSED.test(t));
      };
      const fn = (/export function TapeControlPins[\s\S]*?\n\}(?=\n)/.exec(alerts) || [''])[0];
      if (!fn) errs.push('Alerts.tsx lost export function TapeControlPins — the pinned names would not render');
      else {
        for (const t of composedIn(fn)) errs.push(`TapeControlPins types "${t}" — every pin word is served by tape_control.pin_text`);
        if (!/\{p\.text\}/.test(fn)) errs.push('TapeControlPins must render {p.text} — the served pin sentence');
        if (!/\{note\}/.test(fn)) errs.push('TapeControlPins must render {note} — the served pass note');
        // self-test: the checker must catch a typed sentence.
        if (!composedIn(fn.replace('{p.text}', "{'buyers in control'}")).length) errs.push('self-test: a typed "buyers in control" in TapeControlPins was not caught');
        if (!composedIn(fn.replace('{p.text}', '<b>sellers lead</b>')).length) errs.push('self-test: JSX text naming sellers in TapeControlPins was not caught');
      }
      return errs;
    },
  },
  {
    name: '🧠 gajjala_potential (2026-10-15): in every registry, owner keep-set ON + default_prefs False, MARKET kind, LIVE (never shadow), /alerts row after 🚩, times = data.py + NO_TRADE_AFTER_OPEN_MIN + the gajjala.run step, Cheetah defaults said iff True, the A+ shadow copy narrowed to A+, ✨ entry quotes all three asks, never the b-word',
    file: 'src/lib/alertKinds.ts',
    // Ajay 2026-10-15, three messages: "In Gajjalas setup I wanna find
    // potential stocks this shows me what has happened I am trying to setup for
    // this tab to act like Gajjalas brain. So create a potential category in
    // this section.", "In all the sub tab and add a track and alert to show me
    // new potential is added everyday." and "Give me an alert all continous
    // tracker on these specifically when I get alert I will jump on to ride the
    // wave". He ACTS on this push (real money): a kind missing from a registry
    // sends to zero devices in silence (memory cheetah_push_silent_drops); a
    // time typed on a surface drifts from the clock that gates it; and once 🧠
    // rings live, any A+ sentence that says "nothing rings / reaches / is sent"
    // tells him the opposite of what his phone does (BUILD_SPEC4 Revision 1,
    // finding 1). The tape-burst block above is the template (a LIVE owner-only
    // kind). UNMEASURED — a potential, not an entry.
    checks: (src) => {
      const errs = [];
      const K = 'gajjala_potential';
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16))).replace(/\\'/g, "'");
      const NOTHING = /nothing (rings|reaches|is sent)/i;
      const B_WORD = /boun|fake/i;
      const HIS = [
        'In Gajjalas setup I wanna find potential stocks this shows me what has happened I am trying to setup for this tab to act like Gajjalas brain. So create a potential category in this section.',
        'In all the sub tab and add a track and alert to show me new potential is added everyday.',
        'Give me an alert all continous tracker on these specifically when I get alert I will jump on to ride the wave',
      ];
      const pyBody = (pySrc, def) => {
        const at = pySrc.indexOf(`\ndef ${def}(`);
        if (at < 0) return null;
        const end = pySrc.indexOf('\ndef ', at + 5);
        return pySrc.slice(at, end < 0 ? undefined : end).replace(/#[^\n]*/g, '');
      };
      const tsNoComments = (t) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '');

      // ── the clock the copy prints, read from the engines ──
      const prefsTs = read('src/hooks/useNotificationPrefs.ts');
      const subs = read('../backend/push/subs.py');
      const keep = keepSet(subs);
      const gate = read('../backend/market_hours/gate.py');
      let gc = '';
      try { gc = read('../backend/chart_maps/gajjala/constants.py'); } catch { errs.push('backend/chart_maps/gajjala/constants.py is unreadable'); }
      const data = read('../backend/daytrading/data.py');
      const hm = (name) => { const m = new RegExp(`^${name} = dtime\\((\\d+),\\s*(\\d+)\\)`, 'm').exec(data); return m ? [Number(m[1]), Number(m[2])] : null; };
      const fmt = ([h, m]) => `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
      const pre = hm('ET_PREMARKET_OPEN'), rthT = hm('ET_RTH_OPEN'), ah = hm('ET_AFTERHOURS_CLOSE');
      if (!pre || !rthT || !ah) errs.push('daytrading/data.py lost ET_PREMARKET_OPEN / ET_RTH_OPEN / ET_AFTERHOURS_CLOSE = dtime(h, m)');
      const nm = /^NO_TRADE_AFTER_OPEN_MIN = (\d+)/m.exec(gc);
      const N = nm ? Number(nm[1]) : null;
      if (gc && N == null) errs.push('constants.py lost NO_TRADE_AFTER_OPEN_MIN = <int>');
      const open = pre ? fmt(pre) : null, close = ah ? fmt(ah) : null, rth = rthT ? fmt(rthT) : null;
      const mute = rthT && N != null ? fmt([Math.floor((rthT[0] * 60 + rthT[1] + N) / 60), (rthT[0] * 60 + rthT[1] + N) % 60]) : null;
      const runLines = cronCommands(read('../backend/crontab')).filter((l) => /chart_maps\.gajjala\.run\b/.test(l));
      if (runLines.length !== 1) errs.push(`the crontab must carry exactly one chart_maps.gajjala.run line (found ${runLines.length}) — the 🧠 pushes ride it`);
      const stepM = runLines.length === 1 ? /^\S*\/(\d+)\s/.exec(runLines[0].trim()) : null;
      const step = stepM ? Number(stepM[1]) : null;
      if (runLines.length === 1 && step == null) errs.push('the chart_maps.gajjala.run crontab line has no minute step (*/N or a-b/N)');
      if (cronCommands(read('../backend/crontab')).some((l) => /potential/i.test(l))) errs.push('the crontab names a potential job — 🧠 rides the gajjala.run pass, NO new crontab line (a deploy does not ship the crontab)');
      const TIMES = [open, close, rth, mute].filter(Boolean);
      const timeChecks = (where, text) => {
        const out = [];
        if (open && close && !text.includes(`${open}–${close} ET`)) out.push(`${where} must print "${open}–${close} ET" (data.py ET_PREMARKET_OPEN / ET_AFTERHOURS_CLOSE)`);
        if (rth && mute && !text.includes(`${rth}–${mute}`)) out.push(`${where} must print "${rth}–${mute}" (data.py ET_RTH_OPEN + constants.NO_TRADE_AFTER_OPEN_MIN)`);
        if (N != null && !text.includes(`his first ${N} minutes`)) out.push(`${where} must say "his first ${N} minutes" (constants.NO_TRADE_AFTER_OPEN_MIN)`);
        if (step != null && !new RegExp(`[Ee]very ${step} minutes`).test(text)) out.push(`${where} must say "every ${step} minutes" — the gajjala.run crontab step`);
        for (const m of text.matchAll(/\b(\d\d:\d\d)\b/g)) if (TIMES.length === 4 && !TIMES.includes(m[1])) out.push(`${where} prints "${m[1]}" — not one of ${TIMES.join(' / ')} (data.py + NO_TRADE_AFTER_OPEN_MIN)`);
        for (const m of text.matchAll(/[Ee]very (\d+) minutes/g)) if (step != null && Number(m[1]) !== step) out.push(`${where} says "${m[0]}" — the gajjala.run crontab step is ${step}`);
        for (const m of text.matchAll(/first (\d+) minutes/g)) if (N != null && Number(m[1]) !== N) out.push(`${where} says "${m[0]}" — constants.NO_TRADE_AFTER_OPEN_MIN is ${N}`);
        return out;
      };
      let forbidden = [];
      try {
        const fw = /^FORBIDDEN_WORDS = \(([\s\S]*?)\)/m.exec(read('../backend/chart_maps/high_beta_tab.py'));
        forbidden = fw ? [...fw[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]) : [];
      } catch { /* reported below */ }
      if (!forbidden.length) errs.push('chart_maps/high_beta_tab.py lost FORBIDDEN_WORDS = (…) — the house forecast list (AMENDMENTS4 D6)');
      const forecastChecks = (where, text) => forbidden.filter((w) => text.toLowerCase().includes(w.toLowerCase())).map((w) => `${where} says "${w}" (high_beta_tab.FORBIDDEN_WORDS — no forecast words)`);

      // ── constants.py ──
      if (gc && !/^POTENTIAL_PUSH_KIND = "gajjala_potential"/m.test(gc)) errs.push('constants.py must name POTENTIAL_PUSH_KIND = "gajjala_potential"');
      const subsPy = /^SUBS = \(([\s\S]*?)\)\n/m.exec(gc);
      const py = subsPy ? [...subsPy[1].matchAll(/\(\s*"([a-z_]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)/g)].map((m) => [m[1], m[2], m[3]]) : [];
      // WIDENED 2026-10-16 — 🏁 Track record (Ajay 2026-10-16: "keep a new tab to show wins vs losses") is appended
      // AFTER 🧠 (BUILD_SPEC9 D7 / AMENDMENTS9 E5, HIS CALL Q7): SUBS ends with the track_record tuple read from
      // constants.py, 🧠 Potential second to last; nothing else on the tab moves (HIS CALL P8).
      const trTupM = /\(\s*"(track_record)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)\s*\)\n/.exec(subsPy ? subsPy[0] : '');
      const trTup = trTupM ? [trTupM[1], trTupM[2], trTupM[3]] : null;
      if (gc && (!trTup || JSON.stringify(py[py.length - 1] || null) !== JSON.stringify(trTup))) errs.push('constants.SUBS must END with the ("track_record", …) tuple — 🏁 is appended last (2026-10-16, HIS CALL Q7)');
      if (gc && JSON.stringify(py[py.length - 2] || null) !== JSON.stringify(['potential', '🧠', 'Potential'])) errs.push('constants.SUBS must carry ("potential", "🧠", "Potential") second to last, right before 🏁 — nothing else on the tab moves (HIS CALL P8)');
      const cd = /^CHEETAH_DEFAULTS = \(([^)]*)\)/m.exec(gc);
      const DEFAULTS = ['POTENTIAL_NEEDS_BASE', 'POTENTIAL_FRESH_TAPE', 'POTENTIAL_DEFER_REFUSED'];
      for (const d of DEFAULTS) if (gc && !(cd && new RegExp(`"${d}"`).test(cd[1]))) errs.push(`constants.CHEETAH_DEFAULTS must carry "${d}" — a Cheetah default, not his (Revision 1, finding 2)`);
      const flag = (name) => { const m = new RegExp(`^${name} = (True|False)\\b`, 'm').exec(gc); return m ? m[1] === 'True' : null; };
      const FLAGS = Object.fromEntries(DEFAULTS.map((d) => [d, flag(d)]));
      for (const d of DEFAULTS) if (gc && FLAGS[d] == null) errs.push(`constants.py lost ${d} = True | False`);

      // ── registries ──
      const def = (new RegExp(`^\\s*${K}:\\s*\\{[^}]*\\}`, 'm').exec(src) || [''])[0];
      if (!def) errs.push(`alertKinds.ts must register ${K} — else the bell renders a raw id`);
      else {
        if (!/group: 'trading'/.test(def)) errs.push(`alertKinds.ts must put ${K} in the 'trading' group`);
        if (/shadow|boun/i.test(def.replace(K, ''))) errs.push(`the ${K} label says shadow / the b-word`);
      }
      if (!new RegExp(`\\b${K}\\?: boolean`).test(prefsTs)) errs.push(`NotificationPrefs (hooks/useNotificationPrefs.ts) must carry ${K}?: boolean`);
      const dm = new RegExp(`["']${K}["']\\s*:\\s*(True|False)`).exec(subs);
      if (!dm) errs.push(`push/subs.py default_prefs must list "${K}"`);
      else if (dm[1] !== 'False') errs.push(`${K} must be False in push/subs.py default_prefs — owner-only, everyone else starts off`);
      if (!keep.includes(K)) errs.push(`${K} must be in push/subs.OWNER_KEEP_SET — ON for his devices (DECISIONS4)`);
      if (!(pyFrozenSet(gate, 'MARKET_ALERT_KINDS') || []).includes(K)) errs.push(`market_hours/gate.py must treat ${K} as a MARKET kind (silent on closed days)`);
      if ((pyFrozenSet(gate, 'PERSONAL_KINDS') || []).includes(K)) errs.push(`${K} must NOT be a PERSONAL kind`);
      const hooks = read('../backend/push/hooks.py');
      if (!/def notify_gajjala_potential\(/.test(hooks) || !new RegExp(`kind="${K}"`).test(hooks)) errs.push(`push/hooks.py must carry notify_gajjala_potential → send_to_user(…, kind="${K}")`);
      const itemBlock = (/^ITEM_URL_BY_KIND = \{([\s\S]*?)\n\}/m.exec(read('../backend/push/recent.py')) || [])[1] || '';
      const iu = new RegExp(`["']${K}["']\\s*:\\s*["']([^"']+)["']`).exec(itemBlock);
      if (!iu) errs.push(`push/recent.ITEM_URL_BY_KIND must carry ${K} — every ticker of a push is its own link on /alerts`);
      else if (iu[1] !== '/chart-maps?tab=gajjala&focus={sym}') errs.push(`push/recent.ITEM_URL_BY_KIND["${K}"] must be /chart-maps?tab=gajjala&focus={sym} (App.tsx has only /chart-maps), got ${iu[1]}`);
      let status = '';
      try { status = read('../backend/supply_demand/alert_status.py'); } catch { errs.push('backend/supply_demand/alert_status.py is unreadable'); }
      if (status && !new RegExp(`["']${K}["']`).test(status)) errs.push(`supply_demand/alert_status.py must name ${K} (its own /alerts pass row)`);

      // ── /alerts ──
      const alerts = read('src/pages/Alerts.tsx');
      const passesBlock = (/const PASSES:[^=]*=\s*\[([\s\S]*?)\n\];/.exec(alerts) || [])[1] || '';
      const passKeys = [...passesBlock.matchAll(/key: '([a-z_]+)'/g)].map((m) => m[1]);
      if (!passKeys.includes(K)) errs.push(`Alerts.tsx PASSES must carry key: '${K}'`);
      else if (passKeys.indexOf(K) !== passKeys.indexOf('gajjala_setup') + 1) errs.push(`Alerts.tsx PASSES must list '${K}' right after 'gajjala_setup'`);
      const chips = ((/KIND_CHIPS: string\[\] = \[([^\]]*)\]/.exec(alerts) || [])[1] || '').match(/'[a-z_]+'/g) || [];
      const ci = chips.indexOf(`'${K}'`);
      if (ci < 0) errs.push(`Alerts.tsx KIND_CHIPS must carry '${K}'`);
      else if (ci < chips.indexOf("'tape_burst_highbeta'") || ci < chips.indexOf("'tape_burst_chartmaps'")) errs.push(`Alerts.tsx KIND_CHIPS must list '${K}' AFTER the two tape kinds (AMENDMENTS4 D4)`);
      const potChip = (/export function ggPotentialChipText[\s\S]*?\n\}/.exec(alerts) || [''])[0];
      if (!potChip) errs.push('Alerts.tsx lost ggPotentialChipText — the 🧠 counters would render as raw keys');
      if (/shadow|boun/i.test(tsNoComments(potChip))) errs.push('ggPotentialChipText says shadow / the b-word — the kind rings live');
      let pt = '';
      try { pt = read('../backend/chart_maps/gajjala/potential.py'); } catch { errs.push('backend/chart_maps/gajjala/potential.py is unreadable'); }
      const hwAt = pt.search(/^HELD_WORDS = \{/m);
      const hwEnd = hwAt < 0 ? -1 : pt.search(/^RULE_HELD = /m);
      const heldKeys = hwAt < 0 || hwEnd < hwAt ? [] : [...pt.slice(hwAt, hwEnd).matchAll(/"([a-z_]+)"\s*:/g)].map((m) => m[1]);
      if (pt && !heldKeys.length) errs.push('potential.py lost HELD_WORDS = {…} (followed by RULE_HELD)');
      const rowMap = (/export const GG_POTENTIAL_HELD_ROW[^=]*=\s*\{([\s\S]*?)\n\};/.exec(alerts) || [])[1] || '';
      const rowKeys = [...rowMap.matchAll(/^\s*([a-z_]+):\s*'/gm)].map((m) => m[1]);
      for (const k of heldKeys) if (!rowKeys.includes(k)) errs.push(`Alerts.tsx GG_POTENTIAL_HELD_ROW must word potential.HELD_WORDS["${k}"] — a held 🧠 row would print a raw reason`);

      // ── Notifications ──
      const notif = read('src/pages/Notifications.tsx');
      const ess = notif.slice(notif.indexOf("id: 'essentials'"), notif.indexOf("id: 'trading_only'"));
      if (!new RegExp(`${K}:\\s*true`).test(ess)) errs.push(`Essentials must carry ${K}: true — it is in OWNER_KEEP_SET`);
      const nmE = notif.match(new RegExp(`key: '${K}'[\\s\\S]*?' \\},\\n`));
      if (!nmE) errs.push(`${K} must be listed on the Notifications page — a kind the page cannot show cannot be muted`);
      else {
        const d = unesc(nmE[0]);
        const where = `the ${K} Notifications entry`;
        for (const need of ['ON FOR YOUR PHONE', 'rings live', 'UNMEASURED', HIS[2]]) if (!d.includes(need)) errs.push(`${where} must say "${need.slice(0, 60)}"`);
        if (/shadow/i.test(d)) errs.push(`${where} says "shadow" — the kind rings live (A+ are "recorded under 🚩, never sent")`);
        if (/OFF BY DEFAULT/.test(d)) errs.push(`${where} says OFF BY DEFAULT while the keep-set carries it`);
        if (B_WORD.test(d)) errs.push(`${where} says the b-word / "fake"`);
        if (/potential to\b/i.test(d)) errs.push(`${where} says "potential to" — the copy says "a potential"`);
        errs.push(...timeChecks(where, d), ...forecastChecks(where, d));
        const SENT = {
          POTENTIAL_NEEDS_BASE: /needing at least one sideways bar[^.]*/,
          POTENTIAL_DEFER_REFUSED: /rings on the next pass if it is still a potential[^.;]*/,
          POTENTIAL_FRESH_TAPE: /waits for its next print[^.]*/,
        };
        for (const [c, re] of Object.entries(SENT)) {
          const m = re.exec(d);
          if (FLAGS[c] === true && !m) errs.push(`${c} is True — ${where} must carry its sentence (${re.source.slice(0, 40)}…)`);
          if (FLAGS[c] === false && m) errs.push(`${c} is False — ${where} still carries its sentence "${m[0].slice(0, 50)}…"`);
          if (m && !m[0].includes('Cheetah default, not his')) errs.push(`${where}: the ${c} sentence must carry "Cheetah default, not his"`);
        }
      }

      // ── the tab ──
      const board = read('src/components/GajjalaBoard.tsx');
      for (const id of ['gg-potential', 'gg-track']) if (!new RegExp(`data-testid="${id}"`).test(board)) errs.push(`GajjalaBoard must mount data-testid="${id}"`);

      // ── ✨ entry ──
      const nf = read('src/lib/newFeatures.ts');
      const idAt = nf.indexOf("id: 'chart-maps-gajjala-potential-2026-10-15'");
      if (idAt < 0) errs.push("newFeatures.ts lacks the ✨ entry id: 'chart-maps-gajjala-potential-2026-10-15'");
      else {
        const entry = unesc(nf.slice(idAt, nf.indexOf("' },", idAt) + 4));
        const where = 'the 🧠 ✨ entry';
        if (!entry.includes("route: '/chart-maps?tab=gajjala&sub=potential'")) errs.push(`${where} must route to '/chart-maps?tab=gajjala&sub=potential'`);
        for (const h of HIS) if (!entry.includes(h)) errs.push(`${where} must quote his ask verbatim: "${h.slice(0, 40)}…"`);
        if (!entry.includes('UNMEASURED')) errs.push(`${where} must say UNMEASURED`);
        // WIDENED 2026-10-16 — Ajay flipped the A+ kind live ("you alert me when that happens", DECISIONS10 D1)
        if (!entry.includes('A+ entries went live 2026-10-16')) errs.push(`${where} must say the A+ entries went live 2026-10-16`);
        if (/A\+ alerts stay[^.]*shadow/.test(entry)) errs.push(`${where} still says the A+ alerts stay in shadow`);
        if (Object.values(FLAGS).some((v) => v === true) && !entry.includes('Cheetah defaults, not his')) errs.push(`${where} must say the POTENTIAL_* conditions are Cheetah defaults, not his`);
        if (B_WORD.test(entry)) errs.push(`${where} says the b-word / "fake"`);
        if (NOTHING.test(entry)) errs.push(`${where} says nothing rings / reaches / is sent — 🧠 rings live`);
        errs.push(...timeChecks(where, entry), ...forecastChecks(where, entry));
      }

      // ── Revision 1: no A+ sentence may say NOTHING rings while 🧠 rings live ──
      if (keep.includes(K)) {
        const cm = read('src/lib/chartMaps.ts');
        const meta = /\n  gajjala: \{\n    label: "([^"]*)",\n    blurb: '((?:[^'\\]|\\.)*)',/.exec(cm);
        if (!meta) errs.push('TAB_META.gajjala (label + blurb) is missing');
        else {
          const blurb = unesc(meta[2]);
          const where = 'the TAB_META.gajjala blurb';
          if (NOTHING.test(blurb)) errs.push(`${where} says "${NOTHING.exec(blurb)[0]}" — 🧠 potentials ring his phone live (W21: "no A+ rings a phone")`);
          if (!blurb.includes('🧠 Potential sub-tab')) errs.push(`${where} must name the 🧠 Potential sub-tab`);
          if (!/rings your phone live/.test(blurb)) errs.push(`${where} must say a potential rings your phone live`);
          if (open && close && !blurb.includes(`${open}–${close} ET`)) errs.push(`${where} must print "${open}–${close} ET" (data.py ET_PREMARKET_OPEN / ET_AFTERHOURS_CLOSE)`);
          if (B_WORD.test(blurb)) errs.push(`${where} says the b-word / "fake"`);
          errs.push(...forecastChecks(where, blurb));
        }
        const tabPy = read('../backend/chart_maps/gajjala/tab.py');
        const pb = pyBody(tabPy, 'push_block');
        if (pb == null) errs.push('chart_maps/gajjala/tab.py lost def push_block(');
        else if (NOTHING.test(pb)) errs.push(`tab.push_block says "${NOTHING.exec(pb)[0]}" — narrow it to A+ (W20)`);
        const ri = pyBody(read('../backend/supply_demand/rules_info.py'), '_gajjala_section');
        if (ri == null) errs.push('supply_demand/rules_info.py lost def _gajjala_section(');
        else if (NOTHING.test(ri)) errs.push(`rules_info._gajjala_section says "${NOTHING.exec(ri)[0]}" — narrow it to A+ (W20)`);
        const gcf = (/function gajjalaChipText[\s\S]*?\n\}/.exec(alerts) || [''])[0];
        if (!gcf) errs.push('Alerts.tsx lost gajjalaChipText');
        else if (NOTHING.test(tsNoComments(gcf))) errs.push(`Alerts.tsx gajjalaChipText says "${NOTHING.exec(tsNoComments(gcf))[0]}" — narrow it to A+ (W20)`);
        const setupE = notif.match(/key: 'gajjala_setup'[\s\S]*?' \},\n/);
        if (!setupE) errs.push('the 🚩 gajjala_setup Notifications entry is missing');
        else if (NOTHING.test(unesc(setupE[0]))) errs.push(`the 🚩 gajjala_setup Notifications entry says "${NOTHING.exec(unesc(setupE[0]))[0]}" — narrow it to A+ (W20)`);
        const oldAt = nf.indexOf("id: 'chart-maps-gajjala-2026-10-13'");
        if (oldAt >= 0) {
          const old = unesc(nf.slice(oldAt, nf.indexOf('" },', oldAt) + 4));
          if (NOTHING.test(old)) errs.push(`the 🚩 2026-10-13 ✨ entry says "${NOTHING.exec(old)[0]}" — narrow it to A+ (AMENDMENTS4 D7)`);
        }
      }
      return errs;
    },
  },
  {
    name: '🔄 Gajjala scan on open + 🎯 A+ banner (2026-10-15): owner-only POST on mount, gates dry, the cron never refused by an open, closed bars said, A+ only, ✨ entry quotes his ask',
    file: 'src/components/GajjalaBoard.tsx',
    // Ajay 2026-10-15: "When ever I open Gajjala's intiate a new scan of stocks.
    // In that moment and if there are any enterable stocks on the top which I
    // see in potential i guess" (two spaces after "stocks." in every verbatim
    // quote). He ACTS on the 🎯 line (real money). DECISIONS5 K1 (A+ only), K2
    // (an open rings no device — both push gates dry), K3 (the line on every
    // sub, first in 🧠 Potential), K4 (a pass under ON_DEMAND_REUSE_SEC old is
    // reused), C1 (the cron cadence is sacred), C4 (the trigger is its own
    // owner-only POST; the GET stays Mongo-only; no SSE), C8 (the banner never
    // borrows S&D's enterable machinery). AMENDMENTS5 A1: the on-open pass runs
    // in a SUBPROCESS, never a thread in the api; A13: "this pass rings no
    // device" (the NOTHING pattern below stays banned). BUILD_SPEC5 §4 WP-M, checks
    // 1–11. UNMEASURED — not a recommendation.
    checks: (src) => {
      const errs = [];
      const HIS = "When ever I open Gajjala's intiate a new scan of stocks.  In that moment and if there are any enterable stocks on the top which I see in potential i guess";
      const NOTHING = /nothing (rings|reaches|is sent)/i;
      const B_WORD = /boun|fake/i;
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16))).replace(/\\'/g, "'").replace(/\\"/g, '"');
      const pyBody = (pySrc, def) => {
        const at = pySrc.indexOf(`\ndef ${def}(`);
        if (at < 0) return null;
        const end = pySrc.indexOf('\ndef ', at + 5);
        return pySrc.slice(at, end < 0 ? undefined : end).replace(/#[^\n]*/g, '');
      };
      const tryRead = (rel) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable`); return ''; } };

      // 1. one path, one POST
      const lib = tryRead('src/lib/gajjala.ts');
      if (lib && !/^export const GG_SCAN_PATH = '\/chart-maps\/gajjala\/scan';/m.test(lib)) errs.push("lib/gajjala.ts must export GG_SCAN_PATH = '/chart-maps/gajjala/scan'");
      if (!/\$\{GG_SCAN_PATH\}`\s*,\s*\{[^}]*method: 'POST'/.test(src)) errs.push("GajjalaBoard must fetch `${API}${GG_SCAN_PATH}` with method: 'POST' (C4 — the trigger is its own POST)");
      // 2. owner-only (Q1 default: the /auth/me is_admin flag, every house owner)
      const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '');
      const ownerM = /const (\w+) = user\?\.is_admin === true;/.exec(code);
      if (!ownerM) errs.push('GajjalaBoard must derive the owner flag from user?.is_admin === true in code (owner-only, DECISIONS5 C4)');
      else if (!new RegExp(`if \\(!${ownerM[1]}\\b[^)]*\\) return;[\\s\\S]{0,120}startScan\\(\\)`).test(code)) errs.push(`GajjalaBoard's mount POST must return early unless ${ownerM[1]} (owner-only, DECISIONS5 C4)`);
      if (/is_primary_admin/.test(src)) errs.push('GajjalaBoard names is_primary_admin — the owner check is is_admin (Q1 default; his call to narrow)');
      // 3. no SSE (the GZip trap)
      if (/EventSource/.test(src)) errs.push('GajjalaBoard opens an EventSource — the board polls the existing GET (C4; GZip buffers streams)');
      // 4. the mounts, and the 🎯 line leads the 🧠 Track
      for (const id of ['gg-aplus', 'gg-scanning', 'gg-rescan']) if (!src.includes(`data-testid="${id}"`)) errs.push(`GajjalaBoard must mount data-testid="${id}"`);
      const tabsAt = src.indexOf('aria-label="Gajjala setups"');
      const bannerAt = src.indexOf('<AplusBanner');
      const trackAt = src.indexOf('<TrackPanel');
      if (tabsAt < 0 || bannerAt < 0 || trackAt < 0) errs.push('GajjalaBoard lost the sub tablist (aria-label="Gajjala setups"), <AplusBanner or <TrackPanel');
      else if (!(tabsAt < bannerAt && bannerAt < trackAt)) errs.push('<AplusBanner must sit AFTER the sub tablist and BEFORE <TrackPanel — the 🎯 line leads 🧠 Potential (K3)');
      // 5. the banner reads only its block (C8)
      const bAt = src.indexOf('function AplusBanner(');
      const banner = bAt < 0 ? '' : src.slice(bAt, src.indexOf('\n}\n', bAt) + 2);
      if (!banner) errs.push('GajjalaBoard lost function AplusBanner(');
      else {
        const hit = /room|EnterableChip|enterable:|ENTERABLE_KIND/i.exec(banner);
        if (hit) errs.push(`function AplusBanner names "${hit[0]}" — it reads ONLY its served block, never S&D's enterable machinery (C8)`);
      }
      // 6. the route: owner-only POST; the GET never scans
      const api = tryRead('../backend/chart_maps/api.py');
      const postAt = api.indexOf('@router.post("/chart-maps/gajjala/scan")');
      if (api && postAt < 0) errs.push('chart_maps/api.py lost @router.post("/chart-maps/gajjala/scan")');
      else if (api) {
        const nxt = api.indexOf('\n@router.', postAt + 5);
        const post = api.slice(postAt, nxt < 0 ? undefined : nxt);
        if (!post.includes('is_admin_email(')) errs.push('the POST /chart-maps/gajjala/scan handler must check is_admin_email( (owner-only)');
        if (!/status_code\s*=\s*404\b/.test(post)) errs.push('the POST /chart-maps/gajjala/scan handler must answer a non-owner 404 (stealth)');
      }
      const getAt = api.indexOf('async def chart_maps_gajjala(');
      if (api && getAt < 0) errs.push('chart_maps/api.py lost async def chart_maps_gajjala(');
      else if (api) {
        const nxt = api.indexOf('\n@router.', getAt);
        const get = api.slice(getAt, nxt < 0 ? undefined : nxt);
        if (/on_demand/.test(get)) errs.push('GET /chart-maps/gajjala names on_demand — the GET stays Mongo-only (C4); the scan is the POST');
      }
      // 7. the numbers: his 60 s, the short budget, the cron's wait limit
      const gc = tryRead('../backend/chart_maps/gajjala/constants.py');
      const line = (name) => (new RegExp(`^${name} = ([^#\\n]+?)\\s*(#[^\\n]*)?$`, 'm').exec(gc) || null);
      const num = (name, seen = []) => {
        const m = line(name);
        if (!m || seen.includes(name)) return null;
        const v = m[1].trim();
        if (/^\d+$/.test(v)) return Number(v);
        if (/^[A-Z_]+$/.test(v)) return num(v, [...seen, name]);
        return null;
      };
      if (gc) {
        const reuseL = line('ON_DEMAND_REUSE_SEC');
        if (!reuseL || reuseL[1].trim() !== '60') errs.push('constants.py must carry ON_DEMAND_REUSE_SEC = 60 (Ajay K4)');
        else if (!/^# Ajay 2026-10-15/.test(reuseL[2] || '')) errs.push('ON_DEMAND_REUSE_SEC must carry a comment starting "# Ajay 2026-10-15" — his number');
        const waitL = line('CRON_WAIT_ON_DEMAND_SEC');
        if (!waitL || waitL[1].trim() !== 'ON_DEMAND_BUDGET_SEC') errs.push('constants.py must derive CRON_WAIT_ON_DEMAND_SEC = ON_DEMAND_BUDGET_SEC (C1: the cron waits at most the on-open budget)');
        const budget = num('ON_DEMAND_BUDGET_SEC'), passB = num('PASS_BUDGET_SEC'), gap = num('LEASE_MIN_GAP_SEC'), cad = num('PASS_CADENCE_SEC'), wait = num('CRON_WAIT_ON_DEMAND_SEC');
        if ([budget, passB, gap, cad, wait].some((x) => x == null)) errs.push('constants.py lost ON_DEMAND_BUDGET_SEC / PASS_BUDGET_SEC / LEASE_MIN_GAP_SEC / PASS_CADENCE_SEC / CRON_WAIT_ON_DEMAND_SEC as ints or names');
        else {
          if (!(budget < passB)) errs.push(`ON_DEMAND_BUDGET_SEC (${budget}) must be under PASS_BUDGET_SEC (${passB}) — C2: the on-open budget is the short one`);
          if (!(wait + gap < cad)) errs.push(`CRON_WAIT_ON_DEMAND_SEC + LEASE_MIN_GAP_SEC (${wait} + ${gap}) must be under PASS_CADENCE_SEC (${cad}) — C1: a waiting cron never costs the next tick`);
        }
      }
      // 8. no new crontab line — the open is not a job
      const cron = cronCommands(tryRead('../backend/crontab'));
      const runLines = cron.filter((l) => /chart_maps\.gajjala\.run\b/.test(l));
      if (runLines.length !== 1) errs.push(`the crontab must carry exactly one chart_maps.gajjala.run line (found ${runLines.length})`);
      const stepM = runLines.length === 1 ? /^\S*\/(\d+)\s/.exec(runLines[0].trim()) : null;
      const step = stepM ? Number(stepM[1]) : null;
      if (runLines.length === 1 && step == null) errs.push('the chart_maps.gajjala.run crontab line has no minute step (*/N or a-b/N)');
      const odCron = cron.find((l) => /on_demand|on.open|gajjala\.scan/.test(l));
      if (odCron) errs.push(`a crontab line names the on-open scan ("${odCron.trim().slice(0, 60)}") — an open is never a cron job`);
      // 9. the api spawns a subprocess and runs no pass, sends nothing (A1, K2)
      const od = tryRead('../backend/chart_maps/gajjala/on_demand.py');
      if (od) {
        if (!/subprocess\.Popen\(/.test(od)) errs.push('gajjala/on_demand.py must start the pass with subprocess.Popen( (AMENDMENTS5 A1 — never a thread in the api)');
        if (!/start_new_session=True/.test(od)) errs.push('gajjala/on_demand.py must spawn with start_new_session=True (A1)');
        const bad = /threading\.Thread\(|notify_|send_to_user|alert_status|record_status|import pandas|from \. import (bars|detectors|scanner|alerts|potential)/.exec(od);
        if (bad) errs.push(`gajjala/on_demand.py names "${bad[0]}" — the api process runs no pass and sends nothing (A1, K2)`);
      }
      // 10. the served words: never "enterable" / "fresh bar" / the NOTHING pattern (C3, C8, A13)
      const tab = tryRead('../backend/chart_maps/gajjala/tab.py');
      for (const def of ['aplus_block', 'scan_block']) {
        const body = tab ? pyBody(tab, def) : null;
        if (tab && body == null) errs.push(`chart_maps/gajjala/tab.py lost def ${def}(`);
        else if (body) {
          const w = /enterable|fresh bar/i.exec(body);
          if (w) errs.push(`tab.${def} says "${w[0]}" — the served word is A+ / closed bars (C3, C8)`);
          if (NOTHING.test(body)) errs.push(`tab.${def} says "${NOTHING.exec(body)[0]}" — the words are "rings no device" (A13)`);
        }
      }
      // 11. the ✨ entry
      const nf = tryRead('src/lib/newFeatures.ts');
      const idAt = nf.indexOf("id: 'chart-maps-gajjala-on-open-2026-10-15'");
      if (nf && idAt < 0) errs.push("newFeatures.ts lacks the ✨ entry id: 'chart-maps-gajjala-on-open-2026-10-15'");
      else if (nf) {
        const end = nf.indexOf('" },', idAt);
        const entry = unesc(nf.slice(idAt, end < 0 ? undefined : end + 4));
        const where = 'the 🔄 ✨ entry';
        const reuse = num('ON_DEMAND_REUSE_SEC');
        if (!entry.includes("route: '/chart-maps?tab=gajjala&sub=potential'")) errs.push(`${where} must route to '/chart-maps?tab=gajjala&sub=potential'`);
        if (!entry.includes(HIS)) errs.push(`${where} must quote his ask verbatim (two spaces after "stocks.")`);
        if (!entry.includes('UNMEASURED')) errs.push(`${where} must say UNMEASURED`);
        if (!entry.includes('never rings your phone')) errs.push(`${where} must say an open never rings your phone (K2)`);
        const secs = [...entry.matchAll(/(\d+) seconds/g)].map((m) => Number(m[1]));
        if (!secs.length) errs.push(`${where} must say the reuse in seconds (constants.ON_DEMAND_REUSE_SEC)`);
        for (const s of secs) if (s !== reuse) errs.push(`${where} says "${s} seconds" — constants.ON_DEMAND_REUSE_SEC is ${reuse}`);
        const mins = [...entry.matchAll(/(\d+)-minute/g), ...entry.matchAll(/every (\d+) minutes/g)].map((m) => Number(m[1]));
        if (!mins.length) errs.push(`${where} must name the ${step}-minute pass (the gajjala.run crontab step)`);
        for (const n of mins) if (n !== step) errs.push(`${where} says "${n}-minute" — the gajjala.run crontab step is ${step}`);
        const own = entry.split(HIS).join('');
        if (/enterable/i.test(own)) errs.push(`${where} says "enterable" outside his quote — the word is A+ (C8)`);
        if (B_WORD.test(entry)) errs.push(`${where} says the b-word / "fake"`);
        let forbidden = [];
        try {
          const fw = /^FORBIDDEN_WORDS = \(([\s\S]*?)\)/m.exec(read('../backend/chart_maps/high_beta_tab.py'));
          forbidden = fw ? [...fw[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]) : [];
        } catch { /* reported below */ }
        if (!forbidden.length) errs.push('chart_maps/high_beta_tab.py lost FORBIDDEN_WORDS = (…) — the house forecast list');
        for (const w of forbidden) if (entry.toLowerCase().includes(w.toLowerCase())) errs.push(`${where} says "${w}" (high_beta_tab.FORBIDDEN_WORDS — no forecast words)`);
        if (NOTHING.test(entry)) errs.push(`${where} says "${NOTHING.exec(entry)[0]}" — say what does not ring (A13)`);
      }
      return errs;
    },
  },
  {
    name: '🕯️ Doji Sweep tab (2026-10-16): mounted right after 🚩, label = doji_sweep_tab.TAB_LABEL, chip keys / sorts / params = the backend constants, every number in the blurb + ✨ = the constants, the MEASURED line served (WP-R 2026-10-16), the ledger kind registered in its own bucket, the FE composes nothing, never the b-word',
    file: 'src/lib/chartMaps.ts',
    // Ajay 2026-10-16: "create me a new tab for Doji candle after a sweep. For
    // any stocks after a down trend. May be from all chart maps especially on
    // the 60% 70% down stocks", and K4 "Within 5% either side counts as a
    // test". Any of these links lost silently drops the tab, lets a chip key
    // or a sort drift from the backend constant, retypes one of the numbers
    // (HIS 5% test, the house 5% doji, Turtle Soup's 20 / 4) wrong in a
    // sentence he reads, files the ledger kind under the 📐 candles, or lets
    // the FE compose a number or a verdict the server owns (BUILD_SPEC6 §4
    // WP-M). AMENDMENTS6 B14: the TAB_META blurb never says "until the
    // backtest lands" — the MEASURED / UNMEASURED line lives on the board.
    checks: (src) => {
      const errs = [];
      // Helpers copied from the 🎢 block (BUILD_SPEC6 §4 WP-M: reuse by copy).
      const unesc = (x) => x.replace(/\\U([0-9A-Fa-f]{8})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\'/g, "'").replace(/\\"/g, '"');
      const LABEL = '\u{1F56F}\u{FE0F} Doji Sweep';
      const HIS = ['create me a new tab for Doji candle after a sweep. For any stocks after a down trend. May be from all chart maps especially on the 60% 70% down stocks'];
      const HIS_TEST = 'Within 5% either side counts as a test';

      // 1. The slot: once, right after 🚩, with 〰️ right after it; no 🎯 kind.
      const tabs = parseCmTabs(src);
      if (!tabs || !tabs.includes('doji_sweep')) {
        errs.push("CM_TABS must carry 'doji_sweep'");
      } else {
        if (tabs.filter((t) => t === 'doji_sweep').length !== 1) errs.push("CM_TABS lists 'doji_sweep' more than once");
        if (tabs.indexOf('doji_sweep') !== tabs.indexOf('gajjala') + 1) errs.push("CM_TABS: 'doji_sweep' must sit right after 'gajjala'");
        if (tabs.indexOf('ema_frames') !== tabs.indexOf('doji_sweep') + 1) errs.push("CM_TABS: 'ema_frames' must sit right after 'doji_sweep'");
      }
      if (/\n  doji_sweep: '/.test(src)) errs.push('ENTERABLE_KIND must NOT carry doji_sweep (🎯 n/a)');

      // 2. The backend constants: HIS 5% test, Turtle Soup's 20 / 4, the house doji.
      let dj = '';
      try { dj = read('../backend/chart_maps/doji_sweep_tab.py'); } catch { errs.push('backend/chart_maps/doji_sweep_tab.py is missing (WP-A)'); }
      const consts = {};
      for (const m of dj.matchAll(/^([A-Z][A-Z_0-9]*) = "([^"]*)"/gm)) consts[m[1]] = unesc(m[2]);
      for (const m of dj.matchAll(/^([A-Z][A-Z_0-9]*) = ([0-9][0-9_]*(?:\.[0-9]+)?)\b/gm)) consts[m[1]] = Number(m[2].replace(/_/g, ''));
      const pyF = (body) => unesc(body).replace(/\{([A-Z_0-9]+)(?::([^}]*))?\}/g, (_m, n, spec) => {
        const v = consts[n];
        if (v == null) return `?${n}`;
        if (spec && /^\.\d+f$/.test(spec) && typeof v === 'number') return v.toFixed(Number(spec.slice(1, -1)));
        return typeof v === 'number' ? String(v) : v;
      });
      const tagged = (name, tag) => {
        const m = new RegExp(`^${name} = [^\\n#]*#\\s*([^\\n]*)$`, 'm').exec(dj);
        return !!m && m[1].startsWith(tag);
      };
      if (dj) {
        if (!/^SWEEP_TEST_PCT = 5\.0\s+# Ajay 2026-10-16/m.test(dj)) errs.push('doji_sweep_tab.py must keep SWEEP_TEST_PCT = 5.0  # Ajay 2026-10-16 (his "Within 5% either side counts as a test")');
        for (const n of ['SWEEP_REF_SESSIONS', 'SWEEP_REF_MIN_AGE']) {
          if (!tagged(n, 'Cheetah default (')) errs.push(`doji_sweep_tab.${n} must be tagged "# Cheetah default (…)" — Turtle Soup's, not his`);
        }
        if (!/^DOJI_BODY_PCT = CANDLES\.DOJI_BODY_PCT\b/m.test(dj)) errs.push('doji_sweep_tab.DOJI_BODY_PCT must be imported (CANDLES.DOJI_BODY_PCT), never retyped');
        if (!/^DEPTH_CHIPS = \(FAL\.DEPTH_STEPS\[\d\], FAL\.DEPTH_STEPS\[\d\], FAL\.DEPTH_STEPS\[\d\]\)/m.test(dj)) errs.push('doji_sweep_tab.DEPTH_CHIPS must pick the 📉 tab\'s own FAL.DEPTH_STEPS');
      }
      let cand = '';
      try { cand = read('../backend/scalping/candles.py'); } catch { errs.push('backend/scalping/candles.py is missing'); }
      const bodyM = /^DOJI_BODY_PCT = ([0-9.]+)/m.exec(cand);
      const B5 = bodyM ? Math.round(Number(bodyM[1]) * 100) : null;
      if (cand && B5 !== 5) errs.push(`scalping/candles.DOJI_BODY_PCT reads ${bodyM ? bodyM[1] : '(absent)'} — the house doji is 0.05`);
      let fal = '';
      try { fal = read('../backend/chart_maps/fallen_tab.py'); } catch { errs.push('backend/chart_maps/fallen_tab.py is missing'); }
      const stepsM = /^DEPTH_STEPS = \(([^)]*)\)/m.exec(fal);
      const steps = stepsM ? stepsM[1].split(',').map((x) => Number(x.trim())).filter(Number.isFinite) : [];
      const chipIdx = /^DEPTH_CHIPS = \(FAL\.DEPTH_STEPS\[(\d)\], FAL\.DEPTH_STEPS\[(\d)\], FAL\.DEPTH_STEPS\[(\d)\]\)/m.exec(dj);
      const CHIPS = chipIdx ? [1, 2, 3].map((i) => steps[Number(chipIdx[i])]) : [];
      let kl = '';
      try { kl = read('../backend/supply_demand/key_levels.py'); } catch { errs.push('backend/supply_demand/key_levels.py is missing'); }
      const rollM = /^ROLL_AT = dtime\((\d+), (\d+)\)/m.exec(kl);
      const ROLL = rollM ? `${rollM[1].padStart(2, '0')}:${rollM[2].padStart(2, '0')} ET` : null;
      if (kl && !ROLL) errs.push('key_levels.py lost ROLL_AT = dtime(HH, MM)');
      const N = consts.SWEEP_REF_SESSIONS, AGE = consts.SWEEP_REF_MIN_AGE, T = consts.SWEEP_TEST_PCT;
      const DOWN = consts.DOWN_PCT, FAST = consts.SMA_FAST, SLOW = consts.SMA_SLOW, WIDE = consts.DOJI_BODY_WIDE_PCT;
      const nums = [N, AGE, T, DOWN, FAST, SLOW, WIDE];
      if (dj && nums.some((x) => typeof x !== 'number' || !Number.isFinite(x))) errs.push('doji_sweep_tab.py lost SWEEP_REF_SESSIONS / SWEEP_REF_MIN_AGE / SWEEP_TEST_PCT / DOWN_PCT / SMA_FAST / SMA_SLOW / DOJI_BODY_WIDE_PCT = <number>');
      if (dj && CHIPS.length !== 3) errs.push('the 40 / 60 / 70 chips could not be read off fallen_tab.DEPTH_STEPS via doji_sweep_tab.DEPTH_CHIPS');
      const g = (x) => String(Number(x));   // python's :g for these values (5.0 → 5, 60.0 → 60)

      // 3. TAB_LABEL renders the FE label.
      const labelM = /^TAB_LABEL = (f?)"([^"]*)"/m.exec(dj);
      const pyLabel = labelM ? (labelM[1] ? pyF(labelM[2]) : unesc(labelM[2])) : null;
      if (dj && !labelM) errs.push('doji_sweep_tab.py lost TAB_LABEL = f"{MARK} Doji Sweep"');
      if (pyLabel && pyLabel !== LABEL) errs.push(`doji_sweep_tab.TAB_LABEL renders "${pyLabel}" — the tab is "${LABEL}" (Q1, his call to change)`);

      // 4 / 13. Every number in a sentence he reads = the constants — present, and never another value.
      const numberChecks = (where, text, needs) => {
        const out = [];
        if (nums.some((x) => typeof x !== 'number') || B5 == null || CHIPS.length !== 3) return out;
        for (const need of needs) if (!text.includes(need)) out.push(`${where} must state "${need}" as the backend constants have it`);
        for (const m of text.matchAll(/(\d+(?:\.\d+)?)% either side/g)) if (Number(m[1]) !== T) out.push(`${where} says "${m[0]}" — SWEEP_TEST_PCT is ${T}`);
        for (const m of text.matchAll(/(\d+) sessions/g)) if (![N, AGE].includes(Number(m[1]))) out.push(`${where} says "${m[0]}" — SWEEP_REF_SESSIONS is ${N}, SWEEP_REF_MIN_AGE ${AGE}`);
        for (const m of text.matchAll(/(\d+)% or more/g)) if (Number(m[1]) !== DOWN) out.push(`${where} says "${m[0]}" — DOWN_PCT is ${DOWN}`);
        for (const m of text.matchAll(/(\d+)%\+/g)) if (Number(m[1]) !== DOWN) out.push(`${where} says "${m[0]}" — DOWN_PCT is ${DOWN}`);
        for (const m of text.matchAll(/(\d+)- and (\d+)-day/g)) if (Number(m[1]) !== FAST || Number(m[2]) !== SLOW) out.push(`${where} says "${m[0]}" — SMA_FAST / SMA_SLOW are ${FAST} / ${SLOW}`);
        for (const m of text.matchAll(/body under (\d+)%/g)) if (Number(m[1]) !== B5) out.push(`${where} says "${m[0]}" — DOJI_BODY_PCT is ${B5}%`);
        return out;
      };
      const strip = (text, quotes) => quotes.reduce((t, q) => t.split(q).join(''), text);
      const forbidden = (() => {
        let hb = '';
        try { hb = read('../backend/chart_maps/high_beta_tab.py'); } catch { return null; }
        const m = /^FORBIDDEN_WORDS = \(([\s\S]*?)\)/m.exec(hb);
        return m ? [...m[1].matchAll(/"([^"]+)"/g)].map((x) => x[1]) : null;
      })();
      if (!forbidden || !forbidden.length) errs.push('high_beta_tab.FORBIDDEN_WORDS could not be read');
      const words = (where, text) => {
        const out = [];
        if (/bounc|fake/i.test(text)) out.push(`${where} says "bounce"/"fake" — surfaces he reads say reversal`);
        for (const w of forbidden || []) if (text.toLowerCase().includes(w.toLowerCase())) out.push(`${where} says "${w}" (high_beta_tab.FORBIDDEN_WORDS)`);
        return out;
      };
      const meta = /\n  doji_sweep: \{\n    label: (['"])((?:(?!\1)[^\\]|\\.)*)\1,\n    blurb: (['"])((?:(?!\3)[^\\]|\\.)*)\3,/.exec(src);
      if (!meta) {
        errs.push('TAB_META.doji_sweep (label + blurb) is missing');
      } else {
        if (unesc(meta[2]) !== LABEL) errs.push(`TAB_META.doji_sweep.label "${unesc(meta[2])}" must be "${LABEL}"`);
        if (pyLabel && unesc(meta[2]) !== pyLabel) errs.push(`TAB_META.doji_sweep.label "${unesc(meta[2])}" must equal doji_sweep_tab.TAB_LABEL "${pyLabel}"`);
        const blurb = unesc(meta[4]);
        for (const h of [...HIS, HIS_TEST]) if (!blurb.includes(h)) errs.push(`the TAB_META.doji_sweep blurb must quote him verbatim: "${h}"`);
        // AMENDMENTS6 B14 (overrides §4 WP-M check 4's "UNMEASURED"): the blurb opens on the board's read and never says
        // "until the backtest lands"; the MEASURED / UNMEASURED word lives in the board header only.
        if (!blurb.includes('the measured read is on the board; a scanner, not an entry')) errs.push('the TAB_META.doji_sweep blurb must say "the measured read is on the board; a scanner, not an entry" (AMENDMENTS6 B14)');
        if (/until the backtest lands|UNMEASURED/.test(blurb)) errs.push('the TAB_META.doji_sweep blurb says "until the backtest lands" / UNMEASURED — the measured line lives in the board header only (AMENDMENTS6 B14)');
        errs.push(...words('the TAB_META.doji_sweep blurb', strip(blurb, HIS)));
        if (CHIPS.length === 3 && WIDE != null) {
          errs.push(...numberChecks('the TAB_META.doji_sweep blurb', strip(blurb, [...HIS, HIS_TEST]), [
            `body under ${B5}%`, `${Math.round(WIDE * 100)}%`, `within ${g(T)}% either side`, `${N} sessions`, `${AGE} sessions old`,
            `${g(DOWN)}% or more`, `${FAST}- and ${SLOW}-day`, CHIPS.join(' / ') + '%', ROLL || '?ROLL_AT']));
        }
      }

      // 5. The FE copies of the chip keys, sorts and params = the module's.
      let lib = '';
      try { lib = read('src/lib/dojiSweep.ts'); } catch { errs.push('src/lib/dojiSweep.ts is missing (WP-C)'); }
      const pyKeysM = /^FILTER_KEYS = \(([^)]*)\)/m.exec(dj);
      const pyKeys = pyKeysM ? [...pyKeysM[1].matchAll(/"([a-z0-9_]+)"/g)].map((m) => m[1]) : [];
      if (dj && !pyKeys.length) errs.push('doji_sweep_tab.py lost FILTER_KEYS = ("w52_40", …)');
      const tsKeysM = /export const DJ_FILTER_KEYS\s*=\s*\[([^\]]*)\]\s*as const/.exec(lib);
      const tsKeys = tsKeysM ? [...tsKeysM[1].matchAll(/'([a-z0-9_]+)'/g)].map((m) => m[1]) : [];
      if (lib && !tsKeys.length) errs.push('lib/dojiSweep.ts lost export const DJ_FILTER_KEYS = [...] as const');
      if (pyKeys.length && tsKeys.length && pyKeys.join(',') !== tsKeys.join(',')) errs.push(`lib/dojiSweep.ts DJ_FILTER_KEYS [${tsKeys.join(', ')}] != doji_sweep_tab.FILTER_KEYS [${pyKeys.join(', ')}]`);
      for (const [ts, py] of [['DJ_SORT_TEST', 'SORT_TEST'], ['DJ_SORT_ATH', 'SORT_ATH'], ['DJ_FILTER_PARAM', 'FILTER_PARAM'], ['DJ_BODY_PARAM', 'BODY_PARAM']]) {
        const m = new RegExp(`export const ${ts} = '([a-z_]+)';`).exec(lib);
        if (!m) errs.push(`lib/dojiSweep.ts must export ${ts} = '<doji_sweep_tab.${py}>'`);
        else if (dj && consts[py] !== m[1]) errs.push(`lib/dojiSweep.ts ${ts} = '${m[1]}' != doji_sweep_tab.${py} = ${consts[py] ? `"${consts[py]}"` : '(absent)'}`);
      }

      // 6. The page mounts the note, skips the generic warming + the demand poll, mounts ℹ️ Rules.
      const page = read('src/pages/ChartMaps.tsx');
      if (!/tab === 'doji_sweep' && <DojiSweepBoardNote board=\{data\?\.doji_sweep_board \?\? null\}/.test(page)) errs.push("ChartMaps.tsx must render <DojiSweepBoardNote board={data?.doji_sweep_board ?? null} …/> on tab === 'doji_sweep'");
      if (!/data\?\.warming && tab === 'doji_sweep' \? null/.test(page)) errs.push('the generic (demand) warming branch must skip the doji_sweep tab — its warming line is served');
      if (!/&& tab !== 'doji_sweep'\);/.test(page)) errs.push('the demand-scan progress poll must skip the doji_sweep tab');
      if (!/\|\| tab === 'doji_sweep' \|\|[^\n]*\) && \(/.test(page)) errs.push('the ℹ️ Rules mount must include the doji_sweep tab (section "doji_sweep")');

      // 7. The note and its lib print what is served — no maths, no b-word.
      let note = '';
      try { note = read('src/components/DojiSweepBoardNote.tsx'); } catch { errs.push('src/components/DojiSweepBoardNote.tsx is missing (WP-C)'); }
      for (const [f, t] of [['DojiSweepBoardNote.tsx', note], ['lib/dojiSweep.ts', lib]]) {
        if (!t) continue;
        if (/bounce|fake/i.test(t)) errs.push(`${f} says bounce / fake — surfaces he reads say reversal`);
        const code = t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
        if (/toFixed|UNMEASURED|Math\./.test(code)) errs.push(`${f} composes wording or does maths — every sentence and number is printed as served`);
      }

      // 8 / 9. Board registration + the memo block key.
      const board = read('../backend/chart_maps/board.py');
      const tabsPy = /^TABS = \(([^)]*)\)/m.exec(board);
      const pyTabs = tabsPy ? [...tabsPy[1].matchAll(/"([a-z0-9_]+)"/g)].map((m) => m[1]) : [];
      if (pyTabs[pyTabs.length - 1] !== 'doji_sweep') errs.push('board.py TABS must end with "doji_sweep" (appended)');
      if (!/elif t == "doji_sweep":/.test(board)) errs.push('board.py lacks the elif t == "doji_sweep": dispatch');
      if (!/\(t == "doji_sweep" and sort in _DJ\.TAB_SORTS\)/.test(board)) errs.push('board.py must honour the tab-scoped doji sorts on this tab only');
      if (!/"dj": dj\b/.test(board) || !/"dj_body": dj_body\b/.test(board)) errs.push('board.py\'s membership hook dict must carry "dj": dj and "dj_body": dj_body — a missing board() param stops EVERY tab\'s membership write');
      const memb = read('../backend/chart_maps/membership.py');
      if (!/"doji_sweep": "doji_sweep_board"/.test(memb)) errs.push('membership.MEMO_BLOCK_KEY must map "doji_sweep": "doji_sweep_board"');

      // 10. The ledger kind, in its own bucket, graded as the up-direction read.
      const hist = read('../backend/patterns/history.py');
      if (!/^DOJI_SWEEP_KIND = "doji_sweep"/m.test(hist)) errs.push('patterns/history.py must define DOJI_SWEEP_KIND = "doji_sweep"');
      if (!/^DOJI_SWEEP_READ = "bullish_reversal_setup"/m.test(hist)) errs.push('patterns/history.py DOJI_SWEEP_READ must be exactly "bullish_reversal_setup" — any other read is graded BEARISH (_grade_candle)');
      const gk = /^GRADABLE_KINDS = \(([^)]*)\)/m.exec(hist);
      if (!gk || !/\bDOJI_SWEEP_KIND\b/.test(gk[1])) errs.push('patterns/history.GRADABLE_KINDS must hold DOJI_SWEEP_KIND');

      // 11. The ℹ️ Rules section sits immediately before 🎢 (no order pin moves).
      const ri = read('../backend/supply_demand/rules_info.py');
      // Comments are stripped BEFORE the tuple is cut — they carry their own "(…)".
      const skAt = ri.search(/^SECTION_KEYS = \(/m);
      const sk = skAt >= 0 ? /^SECTION_KEYS = \(([^)]*)\)/.exec(ri.slice(skAt).replace(/#[^\n]*/g, '')) : null;
      const keys = sk ? [...sk[1].matchAll(/"([a-z0-9_]+)"/g)].map((m) => m[1]) : [];
      if (!keys.includes('doji_sweep') || keys.indexOf('high_beta') !== keys.indexOf('doji_sweep') + 1) errs.push('rules_info.SECTION_KEYS must carry "doji_sweep" immediately before "high_beta"');

      // 12. The engine and the literal: UNMEASURED said, the b-word never.
      let dsm = '';
      try { dsm = read('../backend/chart_maps/doji_sweep_measured.py'); } catch { errs.push('backend/chart_maps/doji_sweep_measured.py is missing (WP-A)'); }
      if (dj && !dj.includes('UNMEASURED')) errs.push('doji_sweep_tab.py must say UNMEASURED');
      for (const [f, t] of [['doji_sweep_tab.py', dj], ['doji_sweep_measured.py', dsm]]) {
        if (t && /bounc/i.test(t.replace(/quick_bounce/g, ''))) errs.push(`${f} says the b-word (comments included) — reversal`);
      }

      // 13. The ✨ entry.
      const nf = read('src/lib/newFeatures.ts');
      const idAt = nf.indexOf("id: 'chart-maps-doji-sweep-2026-10-16'");
      if (idAt < 0) {
        errs.push("newFeatures.ts lacks the ✨ entry id: 'chart-maps-doji-sweep-2026-10-16' (WP-M)");
      } else {
        const end = nf.indexOf("' },", idAt);
        const entry = unesc(nf.slice(idAt, end < 0 ? undefined : end + 4));
        if (!entry.includes("route: '/chart-maps?tab=doji_sweep'")) errs.push("the 🕯️ ✨ entry must route to '/chart-maps?tab=doji_sweep'");
        for (const h of HIS) if (!entry.includes(h)) errs.push(`the 🕯️ ✨ entry must quote his ask verbatim: "${h}"`);
        if (!entry.includes('MEASURED — no edge this study can separate from zero')) errs.push('the 🕯️ ✨ entry must say "MEASURED — no edge this study can separate from zero" (WP-R 2026-10-16: the study ran)');
        if (entry.includes('UNMEASURED') || entry.includes('until it lands')) errs.push('the 🕯️ ✨ entry still says UNMEASURED / "until it lands" — the study ran 2026-10-16 (WP-R)');
        if (!entry.includes('Pushes nothing')) errs.push('the 🕯️ ✨ entry must say "Pushes nothing" (AMENDMENTS6 B3 — the tab is out of the 🗺️ watch)');
        errs.push(...words('the 🕯️ ✨ entry', strip(entry, HIS)));
        if (CHIPS.length === 3 && WIDE != null) {
          errs.push(...numberChecks('the 🕯️ ✨ entry', strip(entry, HIS), [
            `body under ${B5}%`, `${Math.round(WIDE * 100)}%`, `within ${g(T)}% either side`, `${N} sessions`, `${AGE} sessions old`,
            `${g(DOWN)}%+`, `${FAST}- and ${SLOW}-day`, CHIPS.join(' / ') + '%']));
        }
      }

      // 14. SPECS.md carries the section.
      const specs = read('../SPECS.md');
      if (!specs.includes('### Chart Maps — 🕯️ Doji Sweep tab — `chart_maps/doji_sweep_tab.py` (2026-10-16)')) errs.push('SPECS.md lacks "### Chart Maps — 🕯️ Doji Sweep tab — `chart_maps/doji_sweep_tab.py` (2026-10-16)"');
      return errs;
    },
  },
  {
    name: '🔴 live card overlay (2026-10-16): POST /chart-maps/live + useCardLive — the 30 s / 30 min cadences are the pinned constants, the cap is prices._SNAP_CHUNK by name, the route string is shared, the FE composes no word, the ✨ entry is first and every number in it is a constant, never the b-word',
    file: 'src/lib/cardLive.ts',
    // Ajay 2026-10-16: "Can you make this chart more live please like when its
    // 24 hour or todays entry" and "actual price is this  above but it stale
    // value" (his XLAB pair: the card's "now 2.64" vs the ticker page's "$2.77
    // … Today · Live"). Any of these links lost silently brings the stale card
    // back or makes a sentence he reads lie: a cadence retyped away from the
    // ticker page's 30 s, a cap typed as a number that drifts from the
    // snapshot chunk, the route renamed on one side only, a footer word
    // composed in the client, or the ✨ entry stating a number no constant
    // holds (BUILD_SPEC8 §4 WP-M, AMENDMENTS8 C7).
    checks: (src) => {
      const errs = [];
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\'/g, "'").replace(/\\"/g, '"');
      const noComments = (t) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
      // TS type declarations carry the served field VALUES as types (session: 'premarket' | …) — never rendered.
      const noTypes = (t) => t.replace(/export type \w+ = \{[\s\S]*?\};/g, '');
      const num = (x) => Number(String(x).replace(/_/g, ''));
      const HIS = [
        'Can you make this chart more live please like when its 24 hour or todays entry',
        'actual price is this  above but it stale value',
      ];
      const HIS_SHOT = ['now 2.64', '$2.77 … Today · Live'];

      // (a) the cadences: lib/cardLive.ts owns both (the hook imports them), tagged; = the ticker page / the closed TTL.
      const fastM = /^export const CARD_LIVE_MS = ([0-9_]+);\s*\/\/ MINE\b/m.exec(src);
      const slowM = /^export const CARD_LIVE_CLOSED_MS = ([0-9_]+) \* 60_000;\s*\/\/ Cheetah default\b/m.exec(src);
      const FAST = fastM ? num(fastM[1]) : null;
      const SLOW = slowM ? num(slowM[1]) * 60_000 : null;
      if (FAST !== 30_000) errs.push(`lib/cardLive.ts must declare CARD_LIVE_MS = 30_000  // MINE (reads ${fastM ? fastM[1] : '(absent)'}) — HIS CALL Q1`);
      if (SLOW !== 30 * 60_000) errs.push(`lib/cardLive.ts must declare CARD_LIVE_CLOSED_MS = 30 * 60_000  // Cheetah default (reads ${slowM ? slowM[0] : '(absent)'}) — HIS CALL Q5`);
      let hook = '';
      try { hook = read('src/hooks/useCardLive.ts'); } catch { errs.push('src/hooks/useCardLive.ts is missing (WP-C)'); }
      if (hook) {
        if (!/import \{[^}]*\bnextCadence\b[^}]*\} from '\.\.\/lib\/cardLive';/.test(hook)) errs.push('useCardLive.ts must take its cadence from lib/cardLive (nextCadence), never its own number');
        if (/\b\d[\d_]*_000\b|\b\d{4,}\b/.test(noComments(hook))) errs.push('useCardLive.ts holds a millisecond literal — the cadences live in lib/cardLive.ts only');
      }
      const sp = read('src/components/SessionPrice.tsx');
      const spM = /setInterval\(load, ([0-9_]+)\)/.exec(sp);
      if (!spM || num(spM[1]) !== FAST) errs.push(`CARD_LIVE_MS (${FAST}) must equal SessionPrice's poll (${spM ? spM[1] : 'setInterval(load, …) absent'}) — the card follows the ticker page`);
      const d10 = read('../backend/chart_maps/drop10_tab.py');
      const ttlM = /^CLOSED_TTL_SEC = (\d+) \* 60\b/m.exec(d10);
      if (!ttlM || Number(ttlM[1]) * 60 * 1000 !== SLOW) errs.push(`CARD_LIVE_CLOSED_MS (${SLOW}) must equal drop10_tab.CLOSED_TTL_SEC (${ttlM ? `${ttlM[1]} * 60` : 'absent'}) — the closed-hours house value`);

      // (b) the cap: the snapshot chunk, by name, everywhere.
      const pr = read('../backend/sepa/prices.py');
      const chunkM = /^_SNAP_CHUNK = (\d+)/m.exec(pr);
      const CHUNK = chunkM ? Number(chunkM[1]) : null;
      if (CHUNK == null) errs.push('sepa/prices.py lost _SNAP_CHUNK = <n>');
      let lc = '';
      try { lc = read('../backend/chart_maps/live_card.py'); } catch { errs.push('backend/chart_maps/live_card.py is missing (WP-A)'); }
      if (lc) {
        if (!/def cap\(\) -> int:[\s\S]{0,200}?return int\(prices\._SNAP_CHUNK\)/.test(lc)) errs.push('live_card.cap() must return int(prices._SNAP_CHUNK) — the cap is the snapshot chunk by name');
        if (CHUNK != null && new RegExp(`\\b${CHUNK}\\b`).test(lc)) errs.push(`live_card.py types the cap ${CHUNK} — read prices._SNAP_CHUNK instead`);
        if (/^[A-Z_]*(CAP|CHUNK|MAX)[A-Z_]* = \d/m.test(lc)) errs.push('live_card.py defines its own numeric cap constant — it must be prices._SNAP_CHUNK');
      }
      const bd = read('../backend/chart_maps/board.py');
      const limM = /^LIMIT_MAX = (\d+)/m.exec(bd);
      if (!limM || CHUNK == null || Number(limM[1]) > CHUNK) errs.push(`board.LIMIT_MAX (${limM ? limM[1] : 'absent'}) must be ≤ prices._SNAP_CHUNK (${CHUNK}) — one live read per board, the FE never splits`);
      if (CHUNK != null && new RegExp(`\\b${CHUNK}\\b`).test(noComments(src))) errs.push(`lib/cardLive.ts types the cap ${CHUNK} — the server owns it`);

      // (c) the route string, the same on both sides; the POST route refuses whole above the cap.
      const api = read('../backend/chart_maps/api.py');
      if (!api.includes('@router.post("/chart-maps/live")')) errs.push('chart_maps/api.py lacks @router.post("/chart-maps/live")');
      const hAt = api.indexOf('@router.post("/chart-maps/live")');
      const hEnd = hAt < 0 ? -1 : api.indexOf('\n@router.', hAt + 1);
      const handler = hAt < 0 ? '' : api.slice(hAt, hEnd < 0 ? undefined : hEnd);
      if (handler && (!handler.includes('status_code=413') || !handler.includes('live_card'))) errs.push('the /chart-maps/live handler must call live_card and refuse above the cap with status_code=413');
      if (!/^export const CARD_LIVE_PATH = '\/chart-maps\/live';/m.test(src)) errs.push("lib/cardLive.ts must export CARD_LIVE_PATH = '/chart-maps/live' (the api.py route string)");
      const page = read('src/pages/ChartMaps.tsx');
      if (page.includes("'/chart-maps/live'")) errs.push('ChartMaps.tsx types the live route — it goes through CARD_LIVE_PATH in the hook');
      if (hook && !/fetch\(`\$\{API\}\$\{CARD_LIVE_PATH\}`/.test(hook)) errs.push('useCardLive.ts must POST to `${API}${CARD_LIVE_PATH}`');
      if (/fetch\(/.test(noComments(src))) errs.push('lib/cardLive.ts fetches — it is the pure half; the hook owns the POST');

      // (d) the FE composes nothing: no footer / label word in the lib, the hook or the page's live slice.
      const WORDS = /live ·|last refresh|now ·|premarket|afterhours| ET'|' ET/;
      const sAt = page.indexOf('const liveSyms');
      const sEnd = page.indexOf('[data?.tiles, cardLive.answer]);', sAt);
      if (sAt < 0 || sEnd < 0) errs.push('ChartMaps.tsx lost the live slice (const liveSyms … the liveTiles memo)');
      const slice = sAt < 0 || sEnd < 0 ? '' : page.slice(sAt, sEnd);
      for (const [f, t] of [['lib/cardLive.ts', src], ['hooks/useCardLive.ts', hook], ['the ChartMaps.tsx live slice', slice]]) {
        if (!t) continue;
        const code = unesc(noTypes(noComments(t)));
        const m = WORDS.exec(code);
        if (m) errs.push(`${f} composes "${m[0]}" — every footer and label word is served (chart_maps/live_card.py)`);
      }
      if ((page.match(/\buseCardLive\(/g) || []).length !== 1) errs.push('ChartMaps.tsx must call useCardLive( exactly once (one live read per board)');
      const fAt = page.indexOf('const freshness =');
      const fEnd = fAt < 0 ? -1 : page.indexOf(': null;', fAt);
      const fresh = fAt < 0 || fEnd < 0 ? '' : page.slice(fAt, fEnd);
      const inFresh = (fresh.match(/cardLive\.footer/g) || []).length;
      if (!fresh.includes("[stampPart, throughPart, cardLive.footer].filter(Boolean).join(' \\u00b7 ')")) errs.push('cardLive.footer must join the existing freshness line ([stampPart, throughPart, cardLive.footer]) — no new chrome');
      if (inFresh !== (page.match(/cardLive\.footer/g) || []).length) errs.push('cardLive.footer is rendered outside the freshness join');
      if ((page.match(/className="cm-scanstamp"/g) || []).length !== 1) errs.push('ChartMaps.tsx must keep exactly one className="cm-scanstamp"');
      if (/className="[^"]*live[^"]*"/.test(slice)) errs.push('the live slice adds a class — the footer rides the existing line');

      // (e) K4: the 5-minute board refetch is untouched.
      const brM = /^const BOARD_REFRESH_MS = (\d+) \* 60_000;/m.exec(page);
      const BOARD_MIN = brM ? Number(brM[1]) : null;
      if (BOARD_MIN !== 5) errs.push(`BOARD_REFRESH_MS must stay 5 * 60_000 (reads ${brM ? brM[0] : 'absent'}) — K4, HIS CALL Q4`);

      // (f) the session clock for "04:00–20:00 ET".
      const ze = read('../backend/supply_demand/zone_edge.py');
      const hm = (re) => { const m = re.exec(ze); return m ? `${m[1].padStart(2, '0')}:${m[2].padStart(2, '0')}` : null; };
      const OPEN = hm(/^SESSION_OPEN = dtime\((\d+), (\d+)\)/m);
      const CLOSE = hm(/^SESSION_CLOSE = dtime\((\d+), (\d+)\)/m);
      if (!OPEN || !CLOSE) errs.push('zone_edge.py lost SESSION_OPEN / SESSION_CLOSE = dtime(h, m)');

      // (g) the b-word, comments included.
      for (const [f, t] of [['live_card.py', lc], ['lib/cardLive.ts', src], ['hooks/useCardLive.ts', hook]]) {
        if (t && /bounc/i.test(t)) errs.push(`${f} says the b-word — reversal`);
      }

      // (h) the ✨ entry: FIRST, routed, his words verbatim, every number a constant.
      const nf = read('src/lib/newFeatures.ts');
      const head = nf.indexOf('export const NEW_FEATURES: NewFeature[] = [');
      const firstAt = head < 0 ? -1 : nf.indexOf("{ id: '", head);
      const ID = "{ id: 'chart-maps-live-card-2026-10-16'";
      // WIDENED 2026-10-16 — 🏁 Gajjala track record took the first ✨ slot the same day; this entry must be PRESENT (the newest feature is first).
      if (!nf.includes("id: 'chart-maps-live-card-2026-10-16'")) errs.push("the ✨ entry 'chart-maps-live-card-2026-10-16' is missing from NEW_FEATURES");
      const idAt = nf.indexOf(ID);
      if (idAt < 0) {
        errs.push("newFeatures.ts lacks the ✨ entry id: 'chart-maps-live-card-2026-10-16' (WP-M)");
      } else {
        const end = nf.indexOf("' },", idAt);
        const entry = unesc(nf.slice(idAt, end < 0 ? undefined : end + 4));
        const lm = /label: '((?:[^'\\]|\\.)*)'/.exec(nf.slice(idAt, end < 0 ? undefined : end + 4));
        const label = lm ? unesc(lm[1]) : '';
        if (!/route: '\/chart-maps',/.test(entry)) errs.push("the 🔴 ✨ entry must route to '/chart-maps' (every card, every board tab)");
        for (const h of [...HIS, ...HIS_SHOT]) if (!label.includes(h)) errs.push(`the 🔴 ✨ entry must quote him verbatim: "${h}"`);
        let rest = [...HIS, ...HIS_SHOT].reduce((t, q) => t.split(q).join(''), label);
        if (/bounc|fake/i.test(rest)) errs.push('the 🔴 ✨ entry says the b-word / "fake" — reversal');
        const hb = read('../backend/chart_maps/high_beta_tab.py');
        const fw = /^FORBIDDEN_WORDS = \(([\s\S]*?)\)/m.exec(hb);
        for (const w of fw ? [...fw[1].matchAll(/"([^"]+)"/g)].map((x) => x[1]) : []) {
          if (rest.toLowerCase().includes(w.toLowerCase())) errs.push(`the 🔴 ✨ entry says "${w}" (high_beta_tab.FORBIDDEN_WORDS)`);
        }
        const closes = /^CLOSE_FOLLOWS_PRINT_RTH = (True|False)\b/m.exec(lc);
        if (!closes) errs.push('live_card.py lost CLOSE_FOLLOWS_PRINT_RTH = True|False');
        else if ((closes[1] === 'True') !== rest.includes('closes at the last trade')) errs.push(`the 🔴 ✨ entry must say "closes at the last trade" iff live_card.CLOSE_FOLLOWS_PRINT_RTH (= ${closes[1]})`);
        if (FAST != null && SLOW != null && BOARD_MIN != null && OPEN && CLOSE) {
          const needs = [`every ${FAST / 1000} seconds`, `every ${SLOW / 60_000} minutes`, `${OPEN}–${CLOSE} ET`, `${BOARD_MIN}-minute`];
          for (const n of needs) if (!rest.includes(n)) errs.push(`the 🔴 ✨ entry must state "${n}" as the constants have it`);
          // Every digit left after his words must sit in one of the four constant phrases, with the constant's value.
          const checks = [
            [/every (\d+) seconds/g, (m) => Number(m[1]) === FAST / 1000, `CARD_LIVE_MS is ${FAST / 1000} s`],
            [/every (\d+) minutes/g, (m) => Number(m[1]) === SLOW / 60_000, `CARD_LIVE_CLOSED_MS is ${SLOW / 60_000} min`],
            [/(\d+)-minute/g, (m) => Number(m[1]) === BOARD_MIN, `BOARD_REFRESH_MS is ${BOARD_MIN} min`],
            [/(\d{2}:\d{2})–(\d{2}:\d{2}) ET/g, (m) => m[1] === OPEN && m[2] === CLOSE, `zone_edge is ${OPEN}–${CLOSE} ET`],
          ];
          for (const [re, ok, why] of checks) {
            for (const m of rest.matchAll(re)) if (!ok(m)) errs.push(`the 🔴 ✨ entry says "${m[0]}" — ${why}`);
            rest = rest.replace(re, '');
          }
          const stray = /\d[\d:.,]*/.exec(rest);
          if (stray) errs.push(`the 🔴 ✨ entry types "${stray[0]}" — no constant holds it`);
        }
        if (/\b(forecast|predict|will rise|edge)\b/i.test(rest)) errs.push('the 🔴 ✨ entry claims a forecast / an edge — this build claims none');
      }

      // (i) SPECS.md carries the section.
      const specs = read('../SPECS.md');
      const SEC = '### Chart Maps — 🔴 live today candle + now line on every card — chart_maps/live_card.py (2026-10-16)';
      if (!specs.includes(SEC)) errs.push(`SPECS.md lacks "${SEC}"`);
      return errs;
    },
  },
  {
    name: '🏁 Gajjala track record (2026-10-16): the sub LAST, his numbers pinned (+1R, both columns, fills from 09:30 + NO_TRADE_AFTER_OPEN_MIN), the R floor + default span tagged MINE, the grade rides the existing 20:15 nightly line, the GET reads bars on 🏁 only, the FE composes nothing, ✨ first + quotes both paragraphs, never the b-word',
    file: 'src/components/GajjalaBoard.tsx',
    // Ajay 2026-10-16: "also can you track all Gajjals stocks and keep a new
    // tab to show wins vs losses. To see a percentage and the ticker." and "We
    // are not looking for winners just in time but when they got in to our
    // alerts if they made it or not. Like XLAB today was a winner I made good
    // money on it". His knob answers: "GG's trade math", "Both columns", "Keep
    // GG's math", "From 09:45 ET only" (DECISIONS9 + AMENDMENTS9 E1). He made
    // real money on the alert this grades: a +1R typed apart from the grader, a
    // 09:45 retyped instead of built from GG's 15 minutes, a second crontab line
    // a deploy never ships, a bar read on another sub's GET, or a win / loss
    // word composed in the browser would each tell him a different record than
    // the one his phone rang for. UNMEASURED — a ledger, never a study.
    checks: (board) => {
      const errs = [];
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16))).replace(/\\'/g, "'");
      const B_WORD = /boun|fake/i;
      const HIS = [
        'also can you track all Gajjals stocks and keep a new tab to show wins vs losses. To see a percentage and the ticker.',
        'We are not looking for winners just in time but when they got in to our alerts if they made it or not. Like XLAB today was a winner I made good money on it',
      ];
      const tryRead = (rel) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable`); return ''; } };
      const pyCode = (s) => s.replace(/"""[\s\S]*?"""/g, '').replace(/#[^\n]*/g, '');

      // 1. constants.py — his numbers tagged his, mine tagged MINE, the 09:45 BUILT from GG's 15 minutes.
      const gc = tryRead('../backend/chart_maps/gajjala/constants.py');
      const data = tryRead('../backend/daytrading/data.py');
      const cline = (name) => new RegExp(`^${name} = ([^\\n]*?)\\s*#\\s*([^\\n]*)$`, 'm').exec(gc);
      const val = (name) => { const m = cline(name); return m ? m[1].trim() : null; };
      const tag = (name) => { const m = cline(name); return m ? m[2].trim() : ''; };
      const AJAY = /^Ajay 2026-10-16\b/;
      const MINE = /^(?:MINE\b|Cheetah default \(MINE\b)/;
      if (gc) {
        if (val('LEDGER_SUB') !== '"track_record"' || !AJAY.test(tag('LEDGER_SUB'))) errs.push('constants.py must carry LEDGER_SUB = "track_record"  # Ajay 2026-10-16 …');
        if (val('LEDGER_R_MULT') !== '1.0' || !AJAY.test(tag('LEDGER_R_MULT'))) errs.push('constants.py must carry LEDGER_R_MULT = 1.0  # Ajay 2026-10-16 ("GG\'s trade math": +1R before the stop)');
        if (val('LEDGER_HORIZONS') !== '("same", "next")' || !AJAY.test(tag('LEDGER_HORIZONS'))) errs.push('constants.py must carry LEDGER_HORIZONS = ("same", "next")  # Ajay 2026-10-16 ("Both columns")');
        const from = val('LEDGER_FILL_FROM_ET');
        if (from == null || !AJAY.test(tag('LEDGER_FILL_FROM_ET'))) errs.push('constants.py must carry LEDGER_FILL_FROM_ET = …  # Ajay 2026-10-16 ("From 09:45 ET only")');
        else {
          if (!/timedelta\(\s*minutes\s*=\s*NO_TRADE_AFTER_OPEN_MIN\s*\)/.test(from)) errs.push('LEDGER_FILL_FROM_ET must be BUILT as 09:30 + timedelta(minutes=NO_TRADE_AFTER_OPEN_MIN) — never a typed 15 or 09:45 (AMENDMENTS9 E1)');
          if (/time\(\s*9\s*,\s*45\b|minutes\s*=\s*\d/.test(from)) errs.push('LEDGER_FILL_FROM_ET types 09:45 / a minute count — build it from NO_TRADE_AFTER_OPEN_MIN');
          const base = /datetime\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/.exec(from);
          const rth = /^ET_RTH_OPEN = dtime\((\d+),\s*(\d+)\)/m.exec(data);
          if (!base || !rth || Number(base[1]) !== Number(rth[1]) || Number(base[2]) !== Number(rth[2])) errs.push('LEDGER_FILL_FROM_ET\'s base must equal daytrading/data.py ET_RTH_OPEN (09:30)');
        }
        const to = /^LEDGER_FILL_TO_ET = _dt\.time\((\d+),\s*(\d+)\)/m.exec(gc);
        const rthC = /^ET_RTH_CLOSE = dtime\((\d+),\s*(\d+)\)/m.exec(data);
        if (!to || !rthC || to[1] !== rthC[1] || to[2] !== rthC[2] || !/^Cheetah default\b/.test(tag('LEDGER_FILL_TO_ET'))) errs.push('LEDGER_FILL_TO_ET must be _dt.time(h, m) = data.py ET_RTH_CLOSE, tagged # Cheetah default');
        const rPct = Number(val('LEDGER_MIN_R_PCT'));
        if (!Number.isFinite(rPct) || rPct <= 0 || !MINE.test(tag('LEDGER_MIN_R_PCT'))) errs.push('constants.py must carry LEDGER_MIN_R_PCT = <number>  # MINE / Cheetah default (MINE … — the thin-R floor is my number, HIS CALL Q16');
        const sess = Number(val('LEDGER_SPAN_SESSIONS'));
        const spans = (/^LEDGER_SPANS = \(([^)]*)\)/m.exec(gc) || ['', ''])[1].split(',').map((x) => x.trim().replace(/^"|"$/g, '')).filter(Boolean);
        const def = (val('LEDGER_SPAN_DEFAULT') || '').replace(/^"|"$/g, '');
        if (!Number.isInteger(sess) || sess <= 0 || !MINE.test(tag('LEDGER_SPAN_SESSIONS'))) errs.push('constants.py must carry LEDGER_SPAN_SESSIONS = <int>  # Cheetah default (MINE …');
        if (!spans.includes(def) || def !== `${sess}d` || !MINE.test(tag('LEDGER_SPAN_DEFAULT'))) errs.push(`LEDGER_SPAN_DEFAULT must be "${sess}d" (the last LEDGER_SPAN_SESSIONS sessions, AMENDMENTS9 E2), one of LEDGER_SPANS, tagged # Cheetah default (MINE …`);
        if (!/^LEDGER_GRADE_AT_ET = "\d\d:\d\d"/m.test(gc)) errs.push('constants.py must carry LEDGER_GRADE_AT_ET = "HH:MM"');
        // SUBS' last triple is 🏁 and its key is LEDGER_SUB (GG_SUBS == SUBS is the 🚩 block's check — not repeated here).
        const subsPy = /^SUBS = \(([\s\S]*?)\)\n/m.exec(gc);
        const py = subsPy ? [...subsPy[1].matchAll(/\(\s*"([a-z_]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)/g)].map((m) => [m[1], m[2], m[3]]) : [];
        if (JSON.stringify(py[py.length - 1] || null) !== JSON.stringify(['track_record', '🏁', 'Track record'])) errs.push('constants.SUBS must END with ("track_record", "🏁", "Track record")');
      }
      const at = (/^LEDGER_GRADE_AT_ET = "(\d\d:\d\d)"/m.exec(gc) || [])[1] || null;
      const N = Number((/^NO_TRADE_AFTER_OPEN_MIN = (\d+)/m.exec(gc) || [])[1]);
      const R = Number(val('LEDGER_R_MULT'));
      const SESS = Number(val('LEDGER_SPAN_SESSIONS'));

      // 2. ledger.py — no script import, never the b-word, no 09:45 / 15 typed in its code, the window read by name.
      const lg = tryRead('../backend/chart_maps/gajjala/ledger.py');
      if (lg) {
        if (/^\s*(?:from|import)\s+scripts\b/m.test(lg)) errs.push('ledger.py imports scripts/ — the runtime never imports the study script');
        if (/bounc|fake/i.test(lg)) errs.push('ledger.py says bounce / fake');
        const code = pyCode(lg);
        if (/\b15\b|09:45|\b9\s*,\s*45\b/.test(code)) errs.push('ledger.py code types 15 / 09:45 — read GC.LEDGER_FILL_FROM_ET (built from NO_TRADE_AFTER_OPEN_MIN)');
        if (!/GC\.LEDGER_FILL_FROM_ET\b/.test(code)) errs.push('ledger.py must read GC.LEDGER_FILL_FROM_ET for the fill window');
        if (!/GC\.LEDGER_R_MULT\b/.test(code)) errs.push('ledger.py must read GC.LEDGER_R_MULT for the +1R target');
      }

      // 3. the grade rides the EXISTING 20:15 nightly line (a deploy never ships the crontab).
      const cron = cronCommands(tryRead('../backend/crontab'));
      const nl = cron.filter((l) => /chart_maps\.gajjala\.nightly\b/.test(l));
      if (nl.length !== 1) errs.push(`the crontab must carry exactly one chart_maps.gajjala.nightly line (found ${nl.length})`);
      else {
        if (/--steps/.test(nl[0])) errs.push('the chart_maps.gajjala.nightly line passes --steps — the grade step runs only by default (STEPS)');
        const mh = /^(\d+)\s+(\d+)\s/.exec(nl[0].trim());
        if (!mh || !at || `${mh[2].padStart(2, '0')}:${mh[1].padStart(2, '0')}` !== at) errs.push(`the chart_maps.gajjala.nightly line runs at ${mh ? `${mh[2]}:${mh[1]}` : '?'} — constants.LEDGER_GRADE_AT_ET is ${at}`);
      }
      if (cron.some((l) => /ledger|track_record|grade_step/.test(l))) errs.push('the crontab names a ledger / track_record / grade job — 🏁 rides the existing nightly line, NO new crontab line');
      const nightly = tryRead('../backend/chart_maps/gajjala/nightly.py');
      const steps = /^STEPS = \(([^)]*)\)/m.exec(nightly);
      const stepList = steps ? [...steps[1].matchAll(/"([a-z_]+)"/g)].map((m) => m[1]) : [];
      if (stepList[stepList.length - 1] !== 'grade') errs.push(`nightly.STEPS must end with "grade" (its failure never stops a step) — found ${JSON.stringify(stepList)}`);

      // 4. the GET reads bars on 🏁 only (ledger.today_read behind the LEDGER_SUB test); never on_demand.
      const api = tryRead('../backend/chart_maps/api.py');
      const getAt = api.indexOf('async def chart_maps_gajjala(');
      if (api && getAt < 0) errs.push('chart_maps/api.py lost async def chart_maps_gajjala(');
      else if (api) {
        const nxt = api.indexOf('\n@router.', getAt);
        const get = pyCode(api.slice(getAt, nxt < 0 ? undefined : nxt));
        if (!/==\s*GC\.LEDGER_SUB\s*:[\s\S]*?today_read\(/.test(get)) errs.push('GET /chart-maps/gajjala must call ledger.today_read( only under `== GC.LEDGER_SUB:` (🏁 only — every other sub stays Mongo-only)');
        if ((get.match(/today_read\(/g) || []).length !== 1) errs.push('GET /chart-maps/gajjala must call today_read( exactly once');
        if (/on_demand/.test(get)) errs.push('GET /chart-maps/gajjala names on_demand — the GET never scans');
        if (!/\bspan\b/.test(get)) errs.push('GET /chart-maps/gajjala lost the span param');
      }

      // 5. the FE composes nothing: the panel prints served strings only.
      for (const id of ['gg-track-record', 'gg-tr-counts-same', 'gg-tr-counts-next']) if (!board.includes(`data-testid="${id}"`)) errs.push(`GajjalaBoard must mount data-testid="${id}"`);
      if (!/<TrackRecordPanel\s/.test(board)) errs.push('GajjalaBoard must mount <TrackRecordPanel …/> on the track_record sub');
      const fnBody = (name) => {
        const fa = board.indexOf(`\nfunction ${name}(`);
        const ca = board.indexOf(`\nconst ${name} = `);
        if (fa < 0 && ca < 0) return null;
        const a = fa >= 0 ? fa : ca;
        const e = board.indexOf(fa >= 0 ? '\n}\n' : ';\n', a + 1);
        return board.slice(a, e < 0 ? undefined : e);
      };
      const panel = ['TrCell', 'trChip', 'TrRowCells', 'TrackRecordPanel'].map((n) => {
        const b = fnBody(n);
        if (b == null) errs.push(`GajjalaBoard lost ${n} (the 🏁 panel)`);
        return b || '';
      }).join('\n').replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '');
      if (/toFixed|changeText\(|riskText\(|pxText\(|Math\.|%/.test(panel)) errs.push('the 🏁 panel computes or formats a number (toFixed / Math. / a % / a *Text( helper) — every number is served');
      const literals = [
        ...[...panel.matchAll(/'([^'\n]*)'|"([^"\n]*)"|`([^`]*)`/g)].map((m) => m[1] ?? m[2] ?? m[3]),
        ...[...panel.matchAll(/>([^<>{}\n]+)</g)].map((m) => m[1]),
      ].map((s) => s.replace(/\$\{[^}]*\}/g, ' ').replace(/\b(?:gg|cm)-[\w-]*/g, ' ').replace(/\b\w+_text\b/g, ' '));
      const WORDS = /win|loss|no entry|no plan|rang|thin|through|graded/i;
      for (const s of literals) if (WORDS.test(s)) errs.push(`the 🏁 panel types "${s.trim()}" — every win / loss / state word is served by ledger.py`);

      // 6. ✨ — FIRST, routes to the sub, both paragraphs verbatim, UNMEASURED + shadow, every number = a pinned constant.
      const nf = tryRead('src/lib/newFeatures.ts');
      // WIDENED 2026-10-16 — 🎯 Gajjala entry live took the first ✨ slot the same day; this entry must be PRESENT (the newest feature is first).
      const ID = 'chart-maps-gajjala-track-record-2026-10-16';
      if (!nf.includes(`id: '${ID}'`)) errs.push(`the ✨ entry '${ID}' is missing from NEW_FEATURES`);
      const idAt = nf.indexOf(`id: '${ID}'`);
      if (idAt < 0) errs.push(`newFeatures.ts lacks the ✨ entry id: '${ID}'`);
      else {
        const end = nf.indexOf("' },", idAt);
        const entry = unesc(nf.slice(idAt, end < 0 ? undefined : end + 1));
        if (!entry.includes("route: '/chart-maps?tab=gajjala&sub=track_record'")) errs.push("the 🏁 ✨ entry must route to '/chart-maps?tab=gajjala&sub=track_record'");
        for (const h of HIS) if (!entry.includes(h)) errs.push(`the 🏁 ✨ entry must quote his ask verbatim: "${h.slice(0, 40)}…"`);
        if (!entry.includes('UNMEASURED')) errs.push('the 🏁 ✨ entry must say UNMEASURED');
        if (!/shadow/.test(entry)) errs.push('the 🏁 ✨ entry must say the A+ line is shadow (never sent)');
        // WIDENED 2026-10-16 — Ajay flipped the A+ kind live ("you alert me when that happens", DECISIONS10 D1) — the shadow-period rows stay; the live entries are said too.
        if (!entry.includes('A+ entries went live 2026-10-16')) errs.push('the 🏁 ✨ entry must say the A+ entries went live 2026-10-16');
        if (B_WORD.test(entry)) errs.push('the 🏁 ✨ entry says bounce / fake');
        let forbidden = [];
        try {
          const fw = /^FORBIDDEN_WORDS = \(([\s\S]*?)\)/m.exec(read('../backend/chart_maps/high_beta_tab.py'));
          forbidden = fw ? [...fw[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]) : [];
        } catch { /* reported below */ }
        if (!forbidden.length) errs.push('chart_maps/high_beta_tab.py lost FORBIDDEN_WORDS = (…)');
        for (const w of forbidden) if (entry.toLowerCase().includes(w.toLowerCase())) errs.push(`the 🏁 ✨ entry says "${w}" (high_beta_tab.FORBIDDEN_WORDS)`);
        let label = entry.slice(Math.max(0, entry.indexOf("label: '")));
        for (const h of HIS) label = label.split(h).join(' ');
        const seen = { r: 0, t: 0, m: 0, s: 0 };
        for (const m of label.matchAll(/\+(\d+(?:\.\d+)?)R\b/g)) { seen.r++; if (Number(m[1]) !== R) errs.push(`the 🏁 ✨ entry says "${m[0]}" — constants.LEDGER_R_MULT is ${R}`); }
        for (const m of label.matchAll(/\b(\d\d:\d\d)\b/g)) { seen.t++; if (m[1] !== at) errs.push(`the 🏁 ✨ entry prints "${m[1]}" — constants.LEDGER_GRADE_AT_ET is ${at}`); }
        for (const m of label.matchAll(/(\d+) minutes/g)) { seen.m++; if (Number(m[1]) !== N) errs.push(`the 🏁 ✨ entry says "${m[0]}" — constants.NO_TRADE_AFTER_OPEN_MIN is ${N}`); }
        for (const m of label.matchAll(/(\d+) sessions/g)) { seen.s++; if (Number(m[1]) !== SESS) errs.push(`the 🏁 ✨ entry says "${m[0]}" — constants.LEDGER_SPAN_SESSIONS is ${SESS}`); }
        for (const [k, w] of [['r', `+${R}R`], ['t', `${at} ET`], ['m', `${N} minutes`], ['s', `${SESS} sessions`]]) if (!seen[k]) errs.push(`the 🏁 ✨ entry must state "${w}" as constants.py has it`);
        const left = label.replace(/\+\d+(?:\.\d+)?R\b|\b\d\d:\d\d\b|\d+ minutes|\d+ sessions|\b\d{4}-\d\d-\d\d\b/g, ' ');
        const stray = /[^\s]*\d[^\s]*/.exec(left);
        if (stray) errs.push(`the 🏁 ✨ entry prints "${stray[0]}" — no constant pins it (numbers only from constants.py)`);
      }

      // 7. SPECS.md + the doc.
      const specs = tryRead('../SPECS.md');
      if (specs && !specs.includes("### Chart Maps — 🏁 Gajjala's Track record — `chart_maps/gajjala/ledger.py` (2026-10-16)")) errs.push("SPECS.md lacks \"### Chart Maps — 🏁 Gajjala's Track record — `chart_maps/gajjala/ledger.py` (2026-10-16)\"");
      if (!exists('../docs/gajjala/track_record_2026_10_16.md')) errs.push('docs/gajjala/track_record_2026_10_16.md is missing');
      return errs;
    },
  },
  {
    name: '🎯 Gajjala entry live (2026-10-16): GAJJALA_PUSH_MODE "live" by his call, default_prefs False (AMENDMENTS10 F1, owner keep-set ON), ENTRY_WORDS = SETUPS each citing a verified_rules id of its topic, the 🧠 clause read after the dry gate, every surface says live + UNMEASURED, the FE composes no entry word, ✨ first + his words verbatim',
    file: 'src/lib/newFeatures.ts',
    // Ajay 2026-10-16: "can you add liver tracker for Gajjala's entry." and "Dont understand the question I amlooking for
    // Entry of his stocks from all 5 tabs. When every they satisfy all his criteria.. LIke for some he says we need to
    // make sure EMA is kissed you alert me when that happens 5 mins track of it when there are potentials and also look
    // for new potentials". DECISIONS10 D1–D11 + AMENDMENTS10 F1–F11. He ACTS on this push (real money). UNMEASURED — the
    // 2026-10-14 study read NULL; the flip is his call, not a measurement. A flip back to "shadow" reverts this block and
    // the WIDENED pins together. F1: default_prefs stays False (everyone else starts off; his devices ride OWNER_KEEP_SET).
    // F3: the live A+ entries are counted on their own 🎯 line, never pooled with the 🧠 %. F5: the entry clause is in the
    // words of his rules, and the 🎾 "2+ sources" label is verified_rules.json's own status label. F9: numbers first.
    checks: (nf) => {
      const errs = [];
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16))).replace(/\\'/g, "'");
      const tryRead = (rel) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable`); return ''; } };
      const B_WORD = /boun|fake/i;
      const HIS = [
        "can you add liver tracker for Gajjala's entry.",
        'Dont understand the question I amlooking for Entry of his stocks from all 5 tabs. When every they satisfy all his criteria.. LIke for some he says we need to make sure EMA is kissed you alert me when that happens 5 mins track of it when there are potentials and also look for new potentials',
      ];
      const gc = tryRead('../backend/chart_maps/gajjala/constants.py');
      const al = tryRead('../backend/chart_maps/gajjala/alerts.py');
      const subs = tryRead('../backend/push/subs.py');
      const data = tryRead('../backend/daytrading/data.py');
      const sig = tryRead('../backend/orderflow/signals.py');
      let vr = {};
      try { vr = JSON.parse(tryRead('../backend/chart_maps/gajjala/verified_rules.json') || '{}'); } catch { errs.push('verified_rules.json does not parse'); }
      // F5: the 🎾 clause's "(🎾: 2+ sources, no first-hand entry rule on file)" — the label is verified_rules.json's own.
      const MULTI = ((vr.status_labels || {}).confirmed_multi_source) || '';
      if (!MULTI) errs.push('verified_rules.json lost status_labels.confirmed_multi_source (the "2+ sources" label)');
      const RS_NOTE = MULTI ? `(🎾: ${MULTI}, no first-hand entry rule on file)` : null;
      let forbidden = [];
      try { const fw = /^FORBIDDEN_WORDS = \(([\s\S]*?)\)/m.exec(read('../backend/chart_maps/high_beta_tab.py')); forbidden = fw ? [...fw[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]) : []; } catch { /* below */ }
      if (!forbidden.length) errs.push('chart_maps/high_beta_tab.py lost FORBIDDEN_WORDS = (…)');
      const words = (where, t) => [...(B_WORD.test(t) ? [`${where} says the b-word / "fake"`] : []),
        ...forbidden.filter((w) => t.toLowerCase().includes(w.toLowerCase())).map((w) => `${where} says "${w}" (high_beta_tab.FORBIDDEN_WORDS)`)];
      const hm = (name) => { const m = new RegExp(`^${name} = dtime\\((\\d+),\\s*(\\d+)\\)`, 'm').exec(data); return m ? Number(m[1]) * 60 + Number(m[2]) : null; };
      const fmt = (x) => `${String(Math.floor(x / 60)).padStart(2, '0')}:${String(x % 60).padStart(2, '0')}`;
      const N = Number((/^NO_TRADE_AFTER_OPEN_MIN = (\d+)/m.exec(gc) || [])[1]);
      const rthO = hm('ET_RTH_OPEN'), rthC = hm('ET_RTH_CLOSE'), ahC = hm('ET_AFTERHOURS_CLOSE');
      const ok = rthO != null && rthC != null && ahC != null && Number.isFinite(N);
      if (!ok) errs.push('daytrading/data.py ET_RTH_OPEN / ET_RTH_CLOSE / ET_AFTERHOURS_CLOSE or constants.NO_TRADE_AFTER_OPEN_MIN unreadable');
      const WINDOW = ok ? `${fmt(rthO + N)}–${fmt(rthC)} and ${fmt(rthC)}–${fmt(ahC)} ET` : null;
      const TIMES = ok ? [fmt(rthO + N), fmt(rthC), fmt(ahC)] : [];
      const FAST = Number((/^EMA_FAST = (\d+)/m.exec(sig) || [])[1]);
      const CAD = Number((/^PASS_CADENCE_SEC = (\d+)/m.exec(gc) || [])[1]) / 60;
      const pyBody = (src, def) => { const a = src.indexOf(`\ndef ${def}(`); if (a < 0) return null; const e = src.indexOf('\ndef ', a + 5); return src.slice(a, e < 0 ? undefined : e); };

      // 1. the mode — his call, his words tagged on the line
      if (!/^GAJJALA_PUSH_MODE = "live"\s+# Ajay 2026-10-16\b/m.test(gc)) errs.push('constants.py must carry GAJJALA_PUSH_MODE = "live"  # Ajay 2026-10-16 (…) — DECISIONS10 D1');
      // 2. prefs: in the keep-set (his devices ON), default_prefs False for everyone else (AMENDMENTS10 F1)
      if (!keepSet(subs).includes('gajjala_setup')) errs.push('gajjala_setup must stay in push/subs.OWNER_KEEP_SET');
      const dm = subs.match(/["']gajjala_setup["']\s*:\s*(True|False)/);
      if (!dm || dm[1] !== 'False') errs.push('gajjala_setup must stay False in push/subs.py default_prefs — everyone else starts off (F1); his devices ride OWNER_KEEP_SET');
      // 3. ENTRY_WORDS: keys == SETUPS, no digit, each line cites ≥1 verified_rules id of its own topic; the words' assumptions hold
      const setups = [...((/^SETUPS = \(([^)]*)\)/m.exec(gc) || ['', ''])[1]).matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
      const ew = /^ENTRY_WORDS = \{\n([\s\S]*?)\n\}/m.exec(al);
      if (!ew) errs.push('alerts.py lost ENTRY_WORDS = {…} (one clause per setup, GG\'s words)');
      else {
        const lines = ew[1].split('\n').filter((l) => /^\s+"[a-z_]+":/.test(l));
        const keys = lines.map((l) => /^\s+"([a-z_]+)":/.exec(l)[1]);
        if (JSON.stringify(keys) !== JSON.stringify(setups)) errs.push(`ENTRY_WORDS keys ${JSON.stringify(keys)} != constants.SETUPS ${JSON.stringify(setups)}`);
        const topicOf = new Map((vr.topics || []).flatMap((t) => (t.verified || []).map((r) => [r.id, t.key])));
        for (const l of lines) {
          const k = /^\s+"([a-z_]+)":/.exec(l)[1];
          const val = (/:\s*"((?:[^"\\]|\\.)*)"/.exec(l) || [])[1] || '';
          const cmt = l.slice(l.indexOf(val) + val.length);
          if (!val.trim()) errs.push(`ENTRY_WORDS["${k}"] is empty`);
          if (/\d/.test(val)) errs.push(`ENTRY_WORDS["${k}"] types a number — use {fast} / {slow} (orderflow.signals EMA_FAST / EMA_SLOW)`);
          errs.push(...words(`ENTRY_WORDS["${k}"]`, val));
          const cited = [...cmt.matchAll(/\b((?:BF|KF|HF|VCP|RS)\d+)\b/g)].map((m) => m[1]);
          if (!cited.length) errs.push(`ENTRY_WORDS["${k}"] cites no verified_rules.json id on its line`);
          for (const id of cited) if (topicOf.get(id) !== k) errs.push(`ENTRY_WORDS["${k}"] cites ${id} — not a rule of the ${k} topic in verified_rules.json`);
        }
      }
      if (!/^KF_HONOR_ALL_PULLBACK_CLOSES = True\b/m.test(gc)) errs.push('ENTRY_WORDS["kiss_fly"] says "honored" — it assumes KF_HONOR_ALL_PULLBACK_CLOSES = True; revisit the words');
      if (!/^HF_TRIGGER = "base_high"/m.test(gc)) errs.push('ENTRY_WORDS["horizontal_fade"] says "the new highs" — it assumes HF_TRIGGER = "base_high"; revisit the words');
      // 4. compose / run_pass (F9: numbers first — compose CONTAINS entry_words(, it does not lead with it)
      const cp = pyBody(al, 'compose'), rp = pyBody(al, 'run_pass');
      // WIDENED 2026-10-17 (AMENDMENTS12 A1 / F6) — a name on his 🚫 list gets " · " + tab.BROKER_FLAG_ICON appended AFTER
      // the "… A+ entry" title, so a flagged title may end with ` · 🚫`; compose still builds the "… A+ entry" title first.
      if (!cp || !/A\+ entry"/.test(cp)) errs.push('alerts.compose: the title must end "A+ entry" — or "A+ entry · 🚫" when the name is on his 🚫 list (DECISIONS10 D2, AMENDMENTS12 A1)');
      if (!cp || !/entry_words\(/.test(cp) || !/UNMEASURED_TAIL/.test(cp)) errs.push('alerts.compose must contain entry_words( and end with UNMEASURED_TAIL (AMENDMENTS10 F9)');
      if (!rp) errs.push('alerts.py lost def run_pass(');
      else {
        const dryAt = rp.indexOf('if dry:'), potAt = rp.indexOf('potential_rang_at(');
        if (potAt < 0) errs.push('alerts.run_pass must read the 🧠 potential through potential_rang_at( (DECISIONS10 D2)');
        else if (dryAt < 0 || potAt < dryAt) errs.push('alerts.run_pass reads the 🧠 potential before the dry gate — an open / dry pass must read nothing');
      }
      // 5. Notifications
      const notif = tryRead('src/pages/Notifications.tsx');
      if (/SHADOW FIRST/.test(notif)) errs.push('Notifications.tsx still says "SHADOW FIRST" — the A+ kind is live since 2026-10-16');
      const ne = notif.match(/key: 'gajjala_setup'[\s\S]*?' \},\n/);
      if (!ne) errs.push('the 🚩 gajjala_setup Notifications entry is missing');
      else {
        const d = unesc(ne[0]);
        for (const need of ['ON FOR YOUR PHONE', 'everyone else starts off', 'LIVE SINCE 2026-10-16', 'every A+ entry in the window is its own push', 'you alert me when that happens', 'NOT MEASURED', 'the 2026-10-14 study']) if (!d.includes(need)) errs.push(`the 🚩 Notifications entry must say "${need}"`);
        if (d.includes('only your phone is ever sent one')) errs.push('the 🚩 Notifications entry says "only your phone is ever sent one" — F1 keeps "everyone else starts off"');
        if (/entry in his words/.test(d)) errs.push('the 🚩 Notifications entry says "in his words" — F5: "in the words of his rules"');
        if (RS_NOTE && !d.includes(RS_NOTE)) errs.push(`the 🚩 Notifications entry must say "${RS_NOTE}" (F5, verified_rules.json status_labels)`);
        for (const m of d.matchAll(/\b(\d+) EMA\b/g)) if (Number(m[1]) !== FAST) errs.push(`the 🚩 Notifications entry says "${m[0]}" — orderflow.signals.EMA_FAST is ${FAST}`);
        if (WINDOW && !d.includes(WINDOW)) errs.push(`the 🚩 Notifications entry must print "${WINDOW}"`);
        errs.push(...words('the 🚩 Notifications entry', d));
      }
      const pe = notif.match(/key: 'gajjala_potential'[\s\S]*?' \},\n/);
      if (pe && /A\+[^.]*never sent/.test(unesc(pe[0]))) errs.push('the 🧠 Notifications entry still says the A+ are never sent');
      // 6. the tab blurb
      const cm = tryRead('src/lib/chartMaps.ts');
      const meta = /\n  gajjala: \{\n    label: "([^"]*)",\n    blurb: '((?:[^'\\]|\\.)*)',/.exec(cm);
      if (!meta) errs.push('TAB_META.gajjala blurb is missing');
      else {
        const b = unesc(meta[2]);
        if (/no A\+ rings a phone/.test(b)) errs.push('the TAB_META.gajjala blurb still says no A+ rings a phone');
        if (!b.includes('A+ entry rings your phone live since 2026-10-16')) errs.push('the TAB_META.gajjala blurb must say "A+ entry rings your phone live since 2026-10-16"');
        if (WINDOW && !b.includes(WINDOW)) errs.push(`the TAB_META.gajjala blurb must print "${WINDOW}"`);
      }
      // 7. ✨ — FIRST, routed, both messages verbatim, every number a constant; the older 🚩 / 🧠 / 🏁 entries say it went live
      const arr = nf.indexOf('export const NEW_FEATURES');
      // WIDENED 2026-10-16 (night) — 🕰️ Gajjala entry timeline took the first ✨ slot the same day; this entry must be PRESENT (the newest feature is first).
      const ID = 'chart-maps-gajjala-entry-live-2026-10-16';
      if (!nf.includes(`id: '${ID}'`)) errs.push(`the ✨ entry '${ID}' is missing from NEW_FEATURES`);
      const at = nf.indexOf(`{ id: '${ID}'`);
      if (at < 0) errs.push(`newFeatures.ts lacks the ✨ entry id: '${ID}'`);
      else {
        // the entry ends at its own `" },` (a double-quoted label — the 🚩 2026-10-13 house pattern), never the next entry's comment
        const end = nf.indexOf('" },', at);
        const e = unesc(nf.slice(at, end < 0 ? undefined : end + 4));
        if (!e.includes("route: '/chart-maps?tab=gajjala'")) errs.push("the 🎯 ✨ entry must route to '/chart-maps?tab=gajjala'");
        for (const h of HIS) if (!e.includes(h)) errs.push(`the 🎯 ✨ entry must quote him verbatim: "${h.slice(0, 40)}…"`);
        for (const need of ['UNMEASURED', 'the 2026-10-14 study read no edge', 'your call', 'never pre-market', 'on their own 🎯 line', "counted on that pass's /alerts row, never rung"]) if (!e.includes(need)) errs.push(`the 🎯 ✨ entry must say "${need}"`);
        if (RS_NOTE && !e.includes(RS_NOTE)) errs.push(`the 🎯 ✨ entry must say "${RS_NOTE}" (F5, verified_rules.json status_labels)`);
        errs.push(...words('the 🎯 ✨ entry', e));
        let label = e.slice(Math.max(0, e.indexOf('label: ')));
        for (const h of HIS) label = label.split(h).join(' ');
        if (RS_NOTE) label = label.split(RS_NOTE).join(' ');
        if (WINDOW && !label.includes(WINDOW)) errs.push(`the 🎯 ✨ entry must print "${WINDOW}"`);
        for (const m of label.matchAll(/\b(\d\d:\d\d)\b/g)) if (!TIMES.includes(m[1])) errs.push(`the 🎯 ✨ entry prints "${m[1]}" — not one of ${TIMES.join(' / ')}`);
        for (const m of label.matchAll(/first (\d+) minutes/g)) if (Number(m[1]) !== N) errs.push(`the 🎯 ✨ entry says "${m[0]}" — NO_TRADE_AFTER_OPEN_MIN is ${N}`);
        for (const m of label.matchAll(/every (\d+) minutes/g)) if (Number(m[1]) !== CAD) errs.push(`the 🎯 ✨ entry says "${m[0]}" — PASS_CADENCE_SEC is ${CAD * 60}`);
        for (const m of label.matchAll(/\b(\d+) EMA\b/g)) if (Number(m[1]) !== FAST) errs.push(`the 🎯 ✨ entry says "${m[0]}" — orderflow.signals.EMA_FAST is ${FAST}`);
        const left = label.replace(/\b\d\d:\d\d\b|first \d+ minutes|every \d+ minutes|\b\d+ EMA\b|\b\d{4}-\d\d-\d\d\b/g, ' ');
        const stray = /[^\s]*\d[^\s]*/.exec(left);
        if (stray) errs.push(`the 🎯 ✨ entry prints "${stray[0]}" — no constant pins it`);
      }
      for (const [id, close] of [['chart-maps-gajjala-2026-10-13', '" },'], ['chart-maps-gajjala-potential-2026-10-15', "' },"], ['chart-maps-gajjala-track-record-2026-10-16', "' },"]]) {
        const a = nf.indexOf(`id: '${id}'`);
        if (a < 0) { errs.push(`newFeatures.ts lost '${id}'`); continue; }
        const old = unesc(nf.slice(a, nf.indexOf(close, a) + close.length));
        if (!old.includes('A+ entries went live 2026-10-16')) errs.push(`the older ✨ entry '${id}' must say "A+ entries went live 2026-10-16" — an old entry must not lie`);
      }
      // 8. the FE composes no entry word
      const board = tryRead('src/components/GajjalaBoard.tsx');
      if (!board.includes('data-testid={`gg-track-entry-${id}`}') || !/r\.entry_text/.test(board)) errs.push('GajjalaBoard TrackRows must render the served r.entry_text (data-testid gg-track-entry-{id})');
      if (/entry sent/.test(board.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, ''))) errs.push('GajjalaBoard types "entry sent" — tab.py serves those words');
      if (!board.includes('data-testid="gg-tr-entries"') || !/tr\.entries_text/.test(board)) errs.push('GajjalaBoard TrackRecordPanel must render the served tr.entries_text (data-testid gg-tr-entries) — F3');
      // 9. the backend's served words
      const tab = tryRead('../backend/chart_maps/gajjala/tab.py');
      if (!tab.includes('ENTRY_SENT_TEXT = "🎯 entry sent {at} ET"')) errs.push('tab.py must carry ENTRY_SENT_TEXT = "🎯 entry sent {at} ET" (DECISIONS10 D4)');
      const tr = pyBody(tab, '_track_row');
      if (!tr || !tr.includes('"entry_text"')) errs.push('tab._track_row must serve "entry_text"');
      const lg = tryRead('../backend/chart_maps/gajjala/ledger.py');
      if (/The A\+ line was never sent/.test(lg)) errs.push('ledger.HONESTY still says the A+ line was never sent');
      if (!lg.includes('("aplus", "live"): "🎯 A+ entry"')) errs.push('ledger.KIND_TEXT[("aplus", "live")] must be "🎯 A+ entry"');
      if (!lg.includes('"entry"')) errs.push('ledger.served_block must count live A+ entries under counts["entry"] (F3)');
      // sharpened 2026-10-16 (fix round 1): "entry" alone is vacuous — ledger.py already carries it elsewhere; pin what only F3 adds
      // WIDENED 2026-10-16 (night): DECISIONS11 D5 — the ⏪ replayed line has its own count bucket (AMENDMENTS11 F3)
      if (!lg.includes('COUNT_LINES = ("live", "shadow", "entry", "replayed")')) errs.push('ledger.COUNT_LINES must be ("live", "shadow", "entry", "replayed") — live A+ entries are their own count line, never pooled into the 🧠 % (F3); the ⏪ replayed rows their own (DECISIONS11 D5)');
      const sb = pyBody(lg, 'served_block');
      if (!sb || !sb.includes('counts["entry"]') || !sb.includes('"entries_text"')) errs.push('ledger.served_block must read counts["entry"] and serve "entries_text" (F3)');
      // 10. SPECS + the doc
      const specs = tryRead('../SPECS.md');
      if (!specs.includes('- **🎯 A+ entry LIVE** (2026-10-16')) errs.push('SPECS.md lacks the "- **🎯 A+ entry LIVE** (2026-10-16" bullet');
      if (specs.includes('**nothing is sent**')) errs.push('SPECS.md still says "**nothing is sent**" for gajjala_setup');
      const doc = exists('../docs/gajjala/entry_live_2026_10_16.md') ? read('../docs/gajjala/entry_live_2026_10_16.md') : '';
      if (!doc) errs.push('docs/gajjala/entry_live_2026_10_16.md is missing');
      else for (const need of ['READ THIS FIRST', 'HIS CALL', 'Q1', 'UNMEASURED', 'study_2026_10_13.md']) if (!doc.includes(need)) errs.push(`docs/gajjala/entry_live_2026_10_16.md must carry "${need}"`);
      // 11. ☀️ / 🌙 movers clickable (commit 2) — "Also in the after market movers under Gajjala's can you make sure I can click on them." / "Same place as other Gajjala rows"
      const MOVERS = "Also in the after market movers under Gajjala's can you make sure I can click on them.";
      if (at >= 0) {
        const end11 = nf.indexOf('" },', at);
        if (!unesc(nf.slice(at, end11 < 0 ? undefined : end11 + 4)).includes(MOVERS)) errs.push('the 🎯 ✨ entry must quote the movers line verbatim');
      }
      // AMENDMENTS10 F10(b): comments are stripped first — a comment that names an anchor is not a rendered one
      const boardCode = board.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '');
      for (const m of boardCode.matchAll(/<a\s[^>]*>/g)) if (!/target="_blank"/.test(m[0])) errs.push(`GajjalaBoard renders an in-app <a> (${m[0].slice(0, 60)}…) — in-app links are router <Link> (no full-page reload)`);
      if (!board.includes('data-testid={`gg-tile-link-${t.symbol}`}') || !/withSource\(ggHref\(t\.href\)/.test(board)) errs.push('the bar-less ☀️ / 🌙 tile must be a router <Link> through withSource(ggHref(t.href) …) — the charted tile\'s target');
      if (!board.includes('data-testid={`gg-recap-row-${id}`}') || !/ggHref\(r\.href\)/.test(board)) errs.push('the 🌙 recap rows must link the SERVED href through ggHref');
      if (!/"href": PT\.deep_link\(sym, setup\)/.test(tab)) errs.push('tab.recap must serve each row\'s href = potential.deep_link(sym, setup)');
      return errs;
    },
  },
  {
    name: '🕰️ Gajjala entry tape + replay (2026-10-16): ONE tape primitive for both tabs, PromoTagTape byte-identical, every tape word served by tape.py, completed days never force-fetched, today through the ledger memo, the lite stride = promo_tape.LITE_STRIDE, the view toggle served, ✨ first + his words verbatim',
    file: 'src/components/GgEntryTape.tsx',
    // Ajay 2026-10-16: "We have a Promo Circuit tab in Catalyst tab. Can you use the graph component from  that to
    // show what happened to Entries alert of Gajjala with all the 100% criteria satisfier. One you alert it from the
    // alert system you built please" (DECISIONS11 D1–D10, BUILD_SPEC11 §3.10). He trades these entries with real
    // money: a second tape engine, a tape word or a percent composed in the browser, a forced re-fetch of a cached
    // day, a second today memo or a typed stride would each draw him a different picture than the record his phone
    // rang for. UNMEASURED — a picture of what each alert did, graded by the ledger's own math; never a study.
    checks: (gg) => {
      const errs = [];
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16))).replace(/\\'/g, "'");
      const tryRead = (rel) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable`); return ''; } };
      const pyCode = (s) => s.replace(/"""[\s\S]*?"""/g, '').replace(/#[^\n]*/g, '');
      const tsCode = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '').replace(/(^|\s)\/\/[^\n]*/g, '$1');
      const pyBody = (src, def) => { const a = src.indexOf(`\ndef ${def}(`); if (a < 0) return null; const e = src.indexOf('\ndef ', a + 5); return src.slice(a, e < 0 ? undefined : e); };
      const B_WORD = /boun|fake/i;
      const HIS = [
        'We have a Promo Circuit tab in Catalyst tab.',
        'Can you use the graph component from  that to show what happened to Entries alert of Gajjala with all the 100% criteria satisfier. One you alert it from the alert system you built please',
      ];

      // 1. ONE tape engine: TapeChart.tsx draws; PromoTagTape.tsx re-exports it and defines none of it.
      const tc = tsCode(tryRead('src/components/TapeChart.tsx'));
      for (const need of ['function layout(', 'function miniLayout(', 'function TapeChart(', 'function TapeSpark(', 'export const etStamp']) {
        if (tc && !tc.includes(need)) errs.push(`TapeChart.tsx must define ${need} — the one tape primitive (DECISIONS11 D1)`);
      }
      const ptt = tsCode(tryRead('src/components/PromoTagTape.tsx'));
      if (ptt) {
        if (!/from\s+'\.\/TapeChart'/.test(ptt)) errs.push("PromoTagTape.tsx must import './TapeChart' — the Promo tape draws on the primitive");
        for (const n of ['layout', 'miniLayout', 'etStamp']) {
          if (!new RegExp(`export\\s*\\{[^}]*\\b${n}\\b[^}]*\\}\\s*from\\s*'\\./TapeChart'`).test(ptt)) errs.push(`PromoTagTape.tsx must re-export ${n} from './TapeChart' (PromoTagTape.test.tsx imports it from './PromoTagTape')`);
        }
        for (const bad of ['function layout(', 'function miniLayout(', 'const etStamp =']) {
          if (ptt.includes(bad)) errs.push(`PromoTagTape.tsx defines ${bad} — a second tape engine; it lives in TapeChart.tsx only`);
        }
      }

      // 2. GgEntryTape.tsx types no word, number or percent: the tape is drawn from served strings only.
      const g = tsCode(gg);
      if (!/import\s*\{[^}]*\bTapeChart\b[^}]*\}\s*from\s*'\.\/TapeChart'/.test(g) || !/import\s*\{[^}]*\bTapeSpark\b[^}]*\}\s*from\s*'\.\/TapeChart'/.test(g)) errs.push("GgEntryTape.tsx must import TapeChart and TapeSpark from './TapeChart' — never a second SVG");
      if (!g.includes("GG_TAPE_PATH = '/chart-maps/gajjala/entry-tape'")) errs.push("GgEntryTape.tsx must carry GG_TAPE_PATH = '/chart-maps/gajjala/entry-tape'");
      const fmt = /toFixed|Math\.|%|etStamp\(|toLocale|Intl\./.exec(g);
      if (fmt) errs.push(`GgEntryTape.tsx composes a number / a percent / a date ("${fmt[0]}") — every tape string is served by tape.py`);
      for (const m of g.matchAll(/>([^<>{}\n]+)</g)) {
        const t = m[1].trim();
        if (t && t !== '…' && t !== '—') errs.push(`GgEntryTape.tsx types the JSX text "${t}" — only "…" / "—" glyphs; every word is served`);
      }

      // 3. tape.py — the only place a tape word is typed; the house loader without force; today through the ledger memo.
      const tpRaw = tryRead('../backend/chart_maps/gajjala/tape.py');
      if (tpRaw) {
        const tp = pyCode(tpRaw);
        if (!/^ENTRY_TAPE_WORDS = \{/m.test(tpRaw)) errs.push('tape.py must carry ENTRY_TAPE_WORDS = { … } — the only place a tape word is typed');
        if (/force\s*=\s*True/.test(tp)) errs.push('tape.py passes force=True — a cached completed day is never re-fetched (C1)');
        if (/_today_load\(/.test(tp)) errs.push('tape.py calls _today_load( — today goes through LG.today_bars (the ONE memo, _TODAY_MEMO)');
        // LG.today_bars( or (today_bars or LG.today_bars)( — BUILD_SPEC11 §3.3 step 4's own injectable call
        if (!/LG\.today_bars\)?\(/.test(tp)) errs.push('tape.py must read today through LG.today_bars( — the shared ledger memo');
        if (!/stride\s*=\s*PROMO\.LITE_STRIDE\b/.test(tp)) errs.push('tape.py must call the Promo lite engine with stride=PROMO.LITE_STRIDE (read at call time — never a typed 3)');
        if (/%\s*3\b|::3\b|"5min"|'5min'/.test(tp)) errs.push('tape.py types the stride or the frame ("% 3" / "::3" / "5min") — use PROMO.LITE_STRIDE / GC.LEDGER_TAPE_TF_MIN');
        if (/^\s*(?:from|import)\s+scripts\b/m.test(tp)) errs.push('tape.py imports scripts/ — the runtime never imports a study script');
        // /bounc/ (the 🏁 block's ledger.py rule): tape.py calls LG._bounds_of — an identifier, not the word
        if (/bounc|fake/i.test(tpRaw)) errs.push('tape.py says the b-word / "fake"');
      }

      // 4. the route: its own GET (404 on an unknown id), never inside the board GET's slice.
      const api = tryRead('../backend/chart_maps/api.py');
      if (api) {
        const ra = api.indexOf('@router.get("/chart-maps/gajjala/entry-tape")');
        if (ra < 0) errs.push('chart_maps/api.py lacks @router.get("/chart-maps/gajjala/entry-tape")');
        else {
          const rn = api.indexOf('\n@router.', ra + 1);
          const h = pyCode(api.slice(ra, rn < 0 ? undefined : rn));
          if (!/entry_tape\(/.test(h)) errs.push('the entry-tape handler must call entry_tape(');
          if (!/\b404\b/.test(h)) errs.push('the entry-tape handler must answer 404 for an unknown id');
        }
        const ga = api.indexOf('async def chart_maps_gajjala(');
        if (ga >= 0) {
          const gn = api.indexOf('\n@router.', ga);
          if (/entry_tape/.test(api.slice(ga, gn < 0 ? undefined : gn))) errs.push('GET /chart-maps/gajjala names entry_tape — the board GET never reads a tape (the lazy per-row GET does)');
        }
      }

      // 5. constants.py — the 10d span tagged mine; the four tape lines mine; the memo + cap built by name.
      const gc = tryRead('../backend/chart_maps/gajjala/constants.py');
      const cline = (name) => new RegExp(`^${name} = ([^\\n]*?)\\s*#\\s*([^\\n]*)$`, 'm').exec(gc);
      const val = (name) => { const m = cline(name); return m ? m[1].trim() : null; };
      const tag = (name) => { const m = cline(name); return m ? m[2].trim() : ''; };
      const LONG = Number(val('LEDGER_SPAN_SESSIONS_LONG'));
      const TF = Number(val('LEDGER_TAPE_TF_MIN'));
      if (gc) {
        if (!/^\d+$/.test(val('LEDGER_SPAN_SESSIONS_LONG') || '') || !/^Cheetah default \(MINE\b/.test(tag('LEDGER_SPAN_SESSIONS_LONG'))) errs.push('constants.py must carry LEDGER_SPAN_SESSIONS_LONG = <int>  # Cheetah default (MINE … (HIS CALL Q3)');
        const spans = (/^LEDGER_SPANS = \(([^)]*)\)/m.exec(gc) || ['', ''])[1].split(',').map((x) => x.trim().replace(/^"|"$/g, '')).filter(Boolean);
        if (!Number.isInteger(LONG) || !spans.includes(`${LONG}d`)) errs.push(`constants.LEDGER_SPANS must contain "${LONG}d" (LEDGER_SPAN_SESSIONS_LONG)`);
        if (val('LEDGER_TAPE_MEMO_SEC') !== 'PASS_CADENCE_SEC') errs.push('constants.py must carry LEDGER_TAPE_MEMO_SEC = PASS_CADENCE_SEC (memo 5 min per id, by name)');
        const cap = val('LEDGER_TAPE_BARS_MAX') || '';
        if (!/\bLEDGER_TAPE_SESSIONS\b/.test(cap) || !/\bLEDGER_TAPE_TF_MIN\b/.test(cap)) errs.push('constants.LEDGER_TAPE_BARS_MAX must be BUILT from LEDGER_TAPE_SESSIONS and LEDGER_TAPE_TF_MIN');
        if (!/^\d+$/.test(val('LEDGER_TAPE_TF_MIN') || '')) errs.push('constants.py must carry LEDGER_TAPE_TF_MIN = <int>');
        for (const [n, re, w] of [['LEDGER_TAPE_TF_MIN', /^TRANSPORT — MINE\b/, 'TRANSPORT — MINE'], ['LEDGER_TAPE_SESSIONS', /^TRANSPORT — MINE\b/, 'TRANSPORT — MINE'],
                                  ['LEDGER_TAPE_BARS_MAX', /^derived — MINE\b/, 'derived — MINE'], ['LEDGER_TAPE_MEMO_SEC', /^derived — MINE\b/, 'derived — MINE']]) {
          if (!re.test(tag(n))) errs.push(`constants.${n} must be tagged # ${w} (…`);
        }
      }

      // 6. ledger.py — today_bars reads/fills the ONE memo; the 🏁 block serves the views.
      const lg = tryRead('../backend/chart_maps/gajjala/ledger.py');
      if (lg) {
        const tb = pyBody(lg, 'today_bars');
        if (!tb) errs.push('ledger.py lacks def today_bars(');
        else if (!tb.includes('_TODAY_MEMO') || !tb.includes('GC.LEDGER_TODAY_MEMO_SEC')) errs.push('ledger.today_bars must read / fill _TODAY_MEMO under GC.LEDGER_TODAY_MEMO_SEC (ONE today memo)');
        const sb = pyBody(lg, 'served_block');
        if (!sb || !sb.includes('"views"')) errs.push('ledger.served_block must serve "views" (tape.views_block())');
      }

      // 7. GajjalaBoard — the view param FE-only, dropped by a sub click; the toggle + timeline outside the 🏁 bodies.
      const board = tryRead('src/components/GajjalaBoard.tsx');
      if (board) {
        if (!/import\s*\{[^}]*\bGG_VIEW_PARAM\b[^}]*\}\s*from\s*'\.\.\/lib\/gajjala'/.test(board)) errs.push("GajjalaBoard must import GG_VIEW_PARAM from '../lib/gajjala'");
        if (!/const pickSub = [^\n]*\[[^\]\n]*\bGG_VIEW_PARAM\b[^\]\n]*\]/.test(board)) errs.push('GajjalaBoard pickSub must drop GG_VIEW_PARAM (a sub click drops the 🕰️ view)');
        for (const m of ['<GgTrViews ', '<GgEntryTimeline ']) if (!board.includes(m)) errs.push(`GajjalaBoard must mount ${m}…/>`);
        const fnBody = (name) => {
          const fa = board.indexOf(`\nfunction ${name}(`);
          const ca = board.indexOf(`\nconst ${name} = `);
          if (fa < 0 && ca < 0) return null;
          const a = fa >= 0 ? fa : ca;
          const e = board.indexOf(fa >= 0 ? '\n}\n' : ';\n', a + 1);
          return board.slice(a, e < 0 ? undefined : e);
        };
        for (const n of ['TrCell', 'trChip', 'TrRowCells', 'TrackRecordPanel']) {
          const b = fnBody(n);
          if (b == null) errs.push(`GajjalaBoard lost ${n} (the 🏁 panel)`);
          else if (/GgEntryTape|GgEntryMiniTape/.test(tsCode(b))) errs.push(`the 🏁 body ${n} names GgEntryTape / GgEntryMiniTape — the tape mounts only inside GgEntryTimeline (outside the scanned bodies)`);
        }
      }
      const lib = tryRead('src/lib/gajjala.ts');
      if (lib) {
        const qa = lib.indexOf('export function ggQuery(');
        const qe = qa < 0 ? -1 : lib.indexOf('\n}\n', qa);
        if (qa < 0) errs.push('lib/gajjala.ts lost export function ggQuery(');
        else if (/GG_VIEW_PARAM|\bview\b/.test(lib.slice(qa, qe < 0 ? undefined : qe))) errs.push('lib/gajjala.ts ggQuery names the view — the 🕰️ view is FE-only, it never rides the GET');
        if (!/export const GG_VIEW_PARAM = 'view'/.test(lib) || !/export const GG_VIEW_TIMELINE = 'timeline'/.test(lib)) errs.push("lib/gajjala.ts must carry GG_VIEW_PARAM = 'view' and GG_VIEW_TIMELINE = 'timeline'");
      }

      // 8. ✨ — FIRST, routed to the timeline, his two lines verbatim, UNMEASURED, every number a pinned constant.
      const nf = tryRead('src/lib/newFeatures.ts');
      const ID = 'chart-maps-gajjala-entry-timeline-2026-10-16';
      // WIDENED 2026-10-17 — 🚫 Gajjala broker tag took the first ✨ slot; this entry must be PRESENT (the newest feature is first).
      if (!nf.includes(`{ id: '${ID}'`)) errs.push(`the ✨ entry id: '${ID}' is missing from NEW_FEATURES`);
      const at = nf.indexOf(`{ id: '${ID}'`);
      if (at < 0) errs.push(`newFeatures.ts lacks the ✨ entry id: '${ID}'`);
      else {
        const end = nf.indexOf('" },', at);
        const e = unesc(nf.slice(at, end < 0 ? undefined : end + 4));
        const W = 'the 🕰️ ✨ entry';
        if (!e.includes("route: '/chart-maps?tab=gajjala&sub=track_record&view=timeline'")) errs.push(`${W} must route to '/chart-maps?tab=gajjala&sub=track_record&view=timeline'`);
        for (const h of HIS) if (!e.includes(h)) errs.push(`${W} must quote him verbatim: "${h.slice(0, 40)}…"`);
        for (const need of ['UNMEASURED', 'the 2026-10-14 study read no edge']) if (!e.includes(need)) errs.push(`${W} must say "${need}"`);
        if (B_WORD.test(e)) errs.push(`${W} says the b-word / "fake"`);
        let forbidden = [];
        try { const fw = /^FORBIDDEN_WORDS = \(([\s\S]*?)\)/m.exec(read('../backend/chart_maps/high_beta_tab.py')); forbidden = fw ? [...fw[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]) : []; } catch { /* below */ }
        if (!forbidden.length) errs.push('chart_maps/high_beta_tab.py lost FORBIDDEN_WORDS = (…)');
        for (const w of forbidden) if (e.toLowerCase().includes(w.toLowerCase())) errs.push(`${W} says "${w}" (high_beta_tab.FORBIDDEN_WORDS)`);
        const R = Number(val('LEDGER_R_MULT'));
        const AT = (/^LEDGER_GRADE_AT_ET = "(\d\d:\d\d)"/m.exec(gc) || [])[1] || null;
        let label = e.slice(Math.max(0, e.indexOf('label: ')));
        for (const h of HIS) label = label.split(h).join(' ');
        const seen = { s: 0, m: 0, r: 0, t: 0 };
        for (const m of label.matchAll(/(\d+) sessions/g)) { seen.s++; if (Number(m[1]) !== LONG) errs.push(`${W} says "${m[0]}" — constants.LEDGER_SPAN_SESSIONS_LONG is ${LONG}`); }
        for (const m of label.matchAll(/(\d+)-minute/g)) { seen.m++; if (Number(m[1]) !== TF) errs.push(`${W} says "${m[0]}" — constants.LEDGER_TAPE_TF_MIN is ${TF}`); }
        for (const m of label.matchAll(/\+(\d+(?:\.\d+)?)R\b/g)) { seen.r++; if (Number(m[1]) !== R) errs.push(`${W} says "${m[0]}" — constants.LEDGER_R_MULT is ${R}`); }
        for (const m of label.matchAll(/\b(\d\d:\d\d)\b/g)) { seen.t++; if (m[1] !== AT) errs.push(`${W} prints "${m[1]}" — constants.LEDGER_GRADE_AT_ET is ${AT}`); }
        for (const [k, w] of [['s', `${LONG} sessions`], ['m', `${TF}-minute`], ['r', `+${R}R`], ['t', `${AT} ET`]]) if (!seen[k]) errs.push(`${W} must state "${w}" as constants.py has it`);
        const left = label.replace(/\d+ sessions|\d+-minute|\+\d+(?:\.\d+)?R\b|\b\d\d:\d\d\b|\b\d{4}-\d\d-\d\d\b/g, ' ');
        const stray = /[^\s]*\d[^\s]*/.exec(left);
        if (stray) errs.push(`${W} prints "${stray[0]}" — no constant pins it (numbers only from constants.py)`);
      }

      // 9. SPECS.md + the doc.
      const specs = tryRead('../SPECS.md');
      if (specs && !specs.includes('- **🕰️ Entries timeline + tape** (2026-10-16')) errs.push('SPECS.md lacks the "- **🕰️ Entries timeline + tape** (2026-10-16" bullet');
      const DOC = '../docs/gajjala/entry_timeline_2026_10_16.md';
      if (!exists(DOC)) errs.push('docs/gajjala/entry_timeline_2026_10_16.md is missing');
      else {
        const doc = read(DOC);
        for (const need of ['READ THIS FIRST', 'HIS CALL', 'Q1', 'UNMEASURED']) if (!doc.includes(need)) errs.push(`docs/gajjala/entry_timeline_2026_10_16.md must carry "${need}"`);
      }

      // ---- PHASE 2 (2026-10-16 night, BUILD_SPEC11 §3.10 checks 10–17, AMENDMENTS11 F3 / F7 / F13 / F16 / F17).
      // Ajay: "Would you be able to back test for the past week from his alerts any way to do so? build a pre historic
      // timeline or so?" and "I want winners and losers category in his track record and would like us to study the
      // losers". A replayed row pooled into a sent count, a chip that counts a %, a loss fact that says why, or a losers
      // study that grades the strategy would each tell him something the record does not say. UNMEASURED.
      const HIS2 = ['Would you be able to back test for the past week from his alerts any way to do so?', 'build a pre historic timeline or so?'];
      const HIS3 = 'I want winners and losers category in his track record and would like us to study the losers';
      const lit = (s) => [...s.matchAll(/'([^'\n]*)'|"([^"\n]*)"|`([^`]*)`/g)].map((m) => m[1] ?? m[2] ?? m[3]);
      const methodBody = (src, def) => {
        const a = src.indexOf(`def ${def}(`);
        if (a < 0) return null;
        const ends = ['\n    def ', '\ndef ', '\nclass ', '\n    @'].map((x) => src.indexOf(x, a + 4)).filter((i) => i > 0);
        return src.slice(a, ends.length ? Math.min(...ends) : undefined);
      };
      const nfEntry = (() => {
        const a = nf.indexOf(`{ id: '${ID}'`);
        if (a < 0) return '';
        const e2 = nf.indexOf('" },', a);
        return unesc(nf.slice(a, e2 < 0 ? undefined : e2 + 4));
      })();
      // 10. ledger.py — the ⏪ line: its own LINES entry, its own count bucket, its kind words; the nightly never reads it.
      if (lg) {
        for (const need of ['LINES = ("live", "shadow", "replayed")', 'COUNT_LINES = ("live", "shadow", "entry", "replayed")',
                            '("aplus", "replayed"): "⏪ A+ replayed"', 'REPLAY_ID_PREFIX = "REPLAY:"']) {
          if (!lg.includes(need)) errs.push(`ledger.py must carry ${need} — the ⏪ replayed line is its own line and count bucket (DECISIONS11 D5)`);
        }
        for (const def of ['grade_step', 'today_read']) {
          const b = pyBody(lg, def);
          if (!b) errs.push(`ledger.py lost def ${def}(`);
          else if (/\bwith_replay\b/.test(pyCode(b))) errs.push(`ledger.${def} names with_replay — the nightly grade and the today read never see a replay doc (D5)`);
        }
        const rt = pyBody(lg, '_replayed_text');
        if (!rt) errs.push('ledger.py lacks def _replayed_text( (the ⏪ line, DECISIONS11 D5)');
        else if (!/\bpct\s*=\s*False\b/.test(pyCode(rt))) errs.push('ledger._replayed_text must pass pct=False — the ⏪ replayed line never prints a % (D5 / D7)');
      }
      // 11. store.py — the NEW collection in ALL (so fake_store carries it), written only through upsert_replay's key gate.
      const st = tryRead('../backend/chart_maps/gajjala/store.py');
      if (st) {
        if (!/^REPLAY = "gajjala_replay"/m.test(st)) errs.push('store.py must carry REPLAY = "gajjala_replay" (DECISIONS11 D4)');
        const all = /^ALL = \(([^)]*)\)/m.exec(st);
        if (!all || !/\bREPLAY\b/.test(all[1])) errs.push('store.ALL = (…) must name REPLAY — a collection outside ALL reaches for a real Mongo in tests');
        const ur = methodBody(st, 'upsert_replay');
        if (!ur) errs.push('store.py lacks def upsert_replay(');
        else if (!/\bREPLAY_KEYS\b/.test(pyCode(ur))) errs.push('store.upsert_replay must gate the doc keys on REPLAY_KEYS');
      }
      // 12. the replay script — refuses RTH and sessions with records, writes only through upsert_replay, never force-fetches.
      const RP = '../backend/scripts/gajjala_replay.py';
      if (!exists(RP)) errs.push('backend/scripts/gajjala_replay.py is missing (DECISIONS11 D4)');
      else {
        const rp = read(RP);
        const rc = pyCode(rp);
        for (const need of ['refused_window(', 'records_on(', 'upsert_replay(']) if (!rc.includes(need)) errs.push(`scripts/gajjala_replay.py must call ${need} (DECISIONS11 D4 refusals / the one write)`);
        for (const flag of ['--write', '--sha']) if (!rp.includes(flag)) errs.push(`scripts/gajjala_replay.py must carry ${flag}`);
        if (/force\s*=\s*True/.test(rc)) errs.push('scripts/gajjala_replay.py passes force=True — the replay never force-fetches');
      }
      // 13. ✨ — his message 2 verbatim; the replay says it never rang, is not a backtest, and the 🎾 rows are ungated.
      if (nfEntry) {
        for (const h of HIS2) if (!nfEntry.includes(h)) errs.push(`the 🕰️ ✨ entry must quote him verbatim: "${h.slice(0, 40)}…"`);
        for (const need of ['never rang', 'not a backtest', '🎾 ungated']) if (!nfEntry.includes(need)) errs.push(`the 🕰️ ✨ entry must say "${need}" (DECISIONS11 D7 / D10)`);
      }
      // 14. SPECS + the doc carry the ⏪ section.
      if (specs && !specs.includes('- **⏪ Replayed line** (2026-10-16')) errs.push('SPECS.md lacks the "- **⏪ Replayed line** (2026-10-16" bullet');
      if (exists(DOC) && !read(DOC).includes('## ⏪ Replayed line')) errs.push('docs/gajjala/entry_timeline_2026_10_16.md lacks "## ⏪ Replayed line"');
      // 15. (D11) the ✅ / ❌ categories — served buckets and chips, ROW counts never a %; the FE types no category word.
      if (lg) {
        if (!lg.includes('BUCKETS = ("win", "loss", "open", "flat", "out")')) errs.push('ledger.py must carry BUCKETS = ("win", "loss", "open", "flat", "out") (DECISIONS11 D11)');
        if (!/\ndef bucket_of\(/.test(lg)) errs.push('ledger.py lacks def bucket_of( (the one bucket engine — the losers script imports it)');
        const sb = pyBody(lg, 'served_block');
        for (const k of ['"categories"', '"categories_timeline"']) if (!sb || !sb.includes(k)) errs.push(`ledger.served_block must serve ${k} (DECISIONS11 D11)`);
        const cl = /^CATEGORY_LABELS = \{([\s\S]*?)\}/m.exec(lg);
        // AMENDMENTS11 F7: "out" reads "— no fill / not graded" (pending rows read that until the nightly grades them)
        const LABELS = [['all', '📋 all'], ['win', '✅ winners'], ['loss', '❌ losers'], ['open', '⏳ open'], ['flat', '➖ flat'], ['out', '— no fill / not graded']];
        if (!cl) errs.push('ledger.py lacks CATEGORY_LABELS = { … }');
        else for (const [k, l] of LABELS) if (!new RegExp(`"${k}"\\s*:\\s*"${l.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&')}"`).test(cl[1])) errs.push(`ledger.CATEGORY_LABELS["${k}"] must be "${l}" (DECISIONS11 D11 / AMENDMENTS11 F7)`);
        const ct = pyBody(lg, '_category_text');
        if (!ct) errs.push('ledger.py lacks def _category_text( (the chip text, its ROW count inside)');
        else if (/%/.test(pyCode(ct))) errs.push('ledger._category_text types a % — the chips count ROWS, never a %');
        const hon = /^HONESTY = \(([\s\S]*?)\)\s*(?:#[^\n]*)?$/m.exec(lg);
        const honText = hon ? [...hon[1].matchAll(/"((?:[^"\\]|\\.)*)"/g)].map((m) => m[1]).join('') : '';
        if (!/[Tt]he winners \/ losers chips count ROWS/.test(honText)) errs.push('ledger.HONESTY must carry "the winners / losers chips count ROWS" (DECISIONS11 D11)');
      }
      if (board) {
        if (!/import\s*\{[^}]*\bGG_CAT_PARAM\b[^}]*\}\s*from\s*'\.\.\/lib\/gajjala'/.test(board)) errs.push("GajjalaBoard must import GG_CAT_PARAM from '../lib/gajjala'");
        if (!/const pickSub = [^\n]*\[[^\]\n]*\bGG_CAT_PARAM\b[^\]\n]*\]/.test(board)) errs.push('GajjalaBoard pickSub must drop GG_CAT_PARAM (a sub click drops the ✅ / ❌ category)');
        const fb = (name) => {
          const fa = board.indexOf(`\nfunction ${name}(`);
          const ca = board.indexOf(`\nconst ${name} = `);
          if (fa < 0 && ca < 0) return null;
          const a = fa >= 0 ? fa : ca;
          const e = board.indexOf(fa >= 0 ? '\n}\n' : ';\n', a + 1);
          return board.slice(a, e < 0 ? undefined : e);
        };
        for (const n of ['TrCell', 'trChip', 'TrRowCells', 'TrackRecordPanel', 'GgEntryTimeline', 'GgEntryTimelineRow', 'GgTrCats', 'GgTrLossLine']) {
          const b = fb(n);
          if (b == null) { errs.push(`GajjalaBoard lost ${n}`); continue; }
          const code = tsCode(b);
          // JSX text between tags OR after / before an expression (`{x} ❌ word<`), plus every string literal
          for (const s of [...lit(code), ...[...code.matchAll(/[>}]([^<>{}\n]+)[<{]/g)].map((m) => m[1])]) {
            if (/winner|loser/i.test(s)) errs.push(`GajjalaBoard ${n} types "${s.trim()}" — every category word is served by ledger.py (D11)`);
          }
        }
        if (!board.includes('data-testid="gg-tr-cats"') || !board.includes('data-testid={`gg-tr-cat-${c.key}`}')) errs.push('GajjalaBoard must mount the served chips (data-testid gg-tr-cats / gg-tr-cat-{key})');
        if (!board.includes('<GgTrCats ')) errs.push('GajjalaBoard TrackRecordPanel must mount <GgTrCats …/>');
        // AMENDMENTS11 F13 — no per-row ✅ / ❌ chip (the Same / Through-next cells already say WIN / LOSS)
        if (/bucket_text|gg-tr-bucket-/.test(tsCode(board))) errs.push('GajjalaBoard draws the per-row bucket chip — AMENDMENTS11 F13 drops it (Rule #5)');
      }
      // 16. (D12) loss facts — frozen words, facts from stored grade fields only, no causal word; the thresholds MINE.
      if (lg) {
        // AMENDMENTS11 F17: LOSS_FACT_BEST = "high +{x}R through the stop minute"
        for (const need of ['LOSS_FACT_THIN = "thin R (not in the %)"', 'LOSS_FACT_STOPPED = "stopped {n} min after the fill"',
                            'LOSS_FACT_BEST = "high +{x}R through the stop minute"', 'LOSS_FACT_FILLED = "filled {m} min after it rang"',
                            'LOSS_FACT_FILL_MINUTE = "stop in the fill minute"', 'LOSS_FACT_LATE_RTH = "last {n} min of RTH"',
                            'LOSS_FACT_NEXT_MORNING = "filled next morning (rang AH)"', 'LOSS_FACT_STALE = "filled ≥{n} min after the ring"']) {
          if (!lg.includes(need)) errs.push(`ledger.py must carry ${need} (DECISIONS11 D12 frozen words)`);
        }
        for (const def of ['loss_facts', 'loss_text']) {
          const b = pyBody(lg, def);
          if (!b) errs.push(`ledger.py lacks def ${def}(`);
          else if (/(?<![\w.])grade\(|\bLG\.grade\(|\._?grade\(/.test(pyCode(b).replace(/^def [^\n]*\n/, ''))) errs.push(`ledger.${def} calls grade( — the loss facts read the STORED grade fields only (never a regrade)`);
        }
        for (const m of lg.matchAll(/^(LOSS_FACT_\w+) = "([^"\n]*)"/gm)) {
          if (/because|due to|caused|\bwhy\b/i.test(m[2])) errs.push(`ledger.${m[1]} says a causal word ("${m[2]}") — facts only (D12)`);
        }
      }
      if (gc) {
        // AMENDMENTS11 F16 — the five thresholds by name (LEDGER_LOSS_CLASS_FLAG_N is his Rule #9 count, tagged Ajay)
        for (const n of ['LEDGER_LOSS_FAST_MIN', 'LEDGER_LOSS_LATE_RTH_MIN', 'LEDGER_LOSS_STALE_FILL_MIN', 'LEDGER_LOSS_NO_PROGRESS_R', 'LEDGER_LOSS_GAVE_BACK_R']) {
          if (val(n) == null) errs.push(`constants.py lacks ${n} = …  # … MINE (DECISIONS11 D12)`);
          else if (!/\bMINE\b/.test(tag(n)) || /^(Ajay|GG)\b/.test(tag(n))) errs.push(`constants.${n} must be tagged MINE (DECISIONS11 D12 — my threshold, HIS CALL Q13)`);
        }
      }
      // 17. (D13) the losers study — the ONE engine (LG.loss_facts / LG.bucket_of), never the study script, no verdict.
      const LS = '../backend/scripts/gajjala_losers.py';
      if (!exists(LS)) errs.push('backend/scripts/gajjala_losers.py is missing (DECISIONS11 D13)');
      else {
        const ls = read(LS);
        const lc = pyCode(ls);
        for (const need of ['LG.loss_facts', 'LG.bucket_of']) if (!lc.includes(need)) errs.push(`scripts/gajjala_losers.py must use ${need} — one engine (C9)`);
        if (/gajjala_study/.test(lc)) errs.push('scripts/gajjala_losers.py names gajjala_study — it imports the ledger only (D13)');
        const mdDefs = [...ls.matchAll(/^def (\w*md\w*)\(/gm)].map((m) => m[1]);
        const md = mdDefs.length ? mdDefs.map((d) => pyCode(pyBody(ls, d) || '')).join('\n') : lc;
        const verdict = /win rate|expectancy|verdict/i.exec(md);
        if (verdict) errs.push(`the losers md writer names "${verdict[0]}" — descriptive counts only (D13)`);
      }
      const LDOC = '../docs/gajjala/losers_study_2026_10_16.md';
      if (!exists(LDOC)) errs.push('docs/gajjala/losers_study_2026_10_16.md is missing (DECISIONS11 D13)');
      else {
        const ld = read(LDOC);
        for (const need of ['descriptive', 'HIS CALL']) if (!ld.includes(need)) errs.push(`docs/gajjala/losers_study_2026_10_16.md must carry "${need}"`);
      }
      if (nfEntry && !nfEntry.includes(HIS3)) errs.push(`the 🕰️ ✨ entry must quote him verbatim: "${HIS3.slice(0, 40)}…"`);
      return errs;
    },
  },
  {
    name: '🚫 Gajjala broker tag (2026-10-17): his own list, a TAG never a filter, the one served word in tab.py, the broker name only in constants.py, owner-only (the GET + three stealth-404 routes), the clause before UNMEASURED, the FE types no word, ✨ first + his words verbatim',
    file: 'src/components/GajjalaBoard.tsx',
    // Ajay 2026-10-17: "ok then avoid showing me names that are not eligible in Fidelity then." and "Or just add a tag
    // that not eligible on Fidelity" (DECISIONS12 D1–D9, BUILD_SPEC12 §3.10, AMENDMENTS12 A1 / F1 / F5 / F6 / F9). He
    // trades these names with real money: a hidden row, a gate on the list, a broker word typed in the browser, a second
    // copy of the served word, or the list served to anyone but him would each show him a board that is not the record.
    // Owner = the PRIMARY admin only (F1). A store read fault fails open to the seed and SAYS so (F5). Nothing is guessed.
    checks: (board) => {
      const errs = [];
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16))).replace(/\\'/g, "'");
      const tryRead = (rel) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable`); return ''; } };
      const pyCode = (s) => s.replace(/"""[\s\S]*?"""/g, '').replace(/#[^\n]*/g, '');
      const tsCode = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '').replace(/(^|\s)\/\/[^\n]*/g, '$1');
      const pyBody = (src, def) => { const a = src.indexOf(`\ndef ${def}(`); if (a < 0) return null; const e = src.indexOf('\ndef ', a + 5); return src.slice(a, e < 0 ? undefined : e); };
      const B_WORD = /boun|fake/i;
      const HIS = [
        'ok then avoid showing me names that are not eligible in Fidelity then.',
        'Or just add a tag that not eligible on Fidelity',
      ];
      const GG = '../backend/chart_maps/gajjala/';

      // 1. constants.py — the broker's name and the (empty) seed are HIS values; the symbol cap is mine.
      const gc = tryRead(`${GG}constants.py`);
      const cline = (name) => new RegExp(`^${name} = ([^\\n]*?)\\s*#\\s*([^\\n]*)$`, 'm').exec(gc);
      const val = (name) => { const m = cline(name); return m ? m[1].trim() : null; };
      const tag = (name) => { const m = cline(name); return m ? m[2].trim() : ''; };
      const BROKER_NAME = (/^"([^"\n]+)"$/.exec(val('BROKER_NAME') || '') || [])[1] || null;
      if (gc) {
        if (!BROKER_NAME || !/^Ajay 2026-10-17\b/.test(tag('BROKER_NAME'))) errs.push('constants.py must carry BROKER_NAME = "…"  # Ajay 2026-10-17 (DECISIONS12 D1 — his broker, his words)');
        if (!/^\([^)]*\)$/.test(val('BROKER_FLAG_SEED') || '') || !/^Ajay 2026-10-17\b/.test(tag('BROKER_FLAG_SEED'))) errs.push('constants.py must carry BROKER_FLAG_SEED = (…)  # Ajay 2026-10-17 (DECISIONS12 D1 — a name enters only on his word)');
        if (!/^\d+$/.test(val('BROKER_SYMBOL_MAX_LEN') || '') || !/^TRANSPORT — MINE\b/.test(tag('BROKER_SYMBOL_MAX_LEN'))) errs.push('constants.py must carry BROKER_SYMBOL_MAX_LEN = <int>  # TRANSPORT — MINE (…)');
      }

      // 2. the ONE served word: no broker-name literal in the served Python, "not eligible at" exactly once — tab.py's
      //    BROKER_FLAG_TEXT. CASE-SENSITIVE (AMENDMENTS12 F9): rules_info's capital "Not eligible at %s" is its own line.
      const PY = ['tab', 'alerts', 'potential', 'ledger', 'store', 'run'].map((n) => `${GG}${n}.py`)
        .concat(['../backend/chart_maps/api.py', '../backend/supply_demand/rules_info.py']);
      const src = Object.fromEntries(PY.map((p) => [p, tryRead(p)]));
      let once = 0;
      for (const p of PY) {
        const code = pyCode(src[p] || '');
        if (BROKER_NAME && code.includes(BROKER_NAME)) errs.push(`${p.replace('../backend/', '')} types "${BROKER_NAME}" in code — the broker's name lives in constants.BROKER_NAME only`);
        once += (code.match(/not eligible at/g) || []).length;
      }
      if (once !== 1) errs.push(`"not eligible at" must appear exactly ONCE in the served Python (case-sensitive) — tab.BROKER_FLAG_TEXT; found ${once}`);
      const tab = src[`${GG}tab.py`] || '';
      if (tab) {
        if (!/^BROKER_FLAG_TEXT = f"🚫 not eligible at \{GC\.BROKER_NAME\}"/m.test(tab)) errs.push('tab.py must carry BROKER_FLAG_TEXT = f"🚫 not eligible at {GC.BROKER_NAME}" — the ONE served word (DECISIONS12 D1)');
        for (const d of ['def broker_text_for(', 'def _broker_tag(']) if (!tab.includes(`\n${d}`)) errs.push(`tab.py must define ${d} (DECISIONS12 D2 — one helper, one annotator)`);
      }

      // 3. the pushes carry the tag and never gate on it: both run_pass bodies read the list and tag; no if …broker… line.
      const al = src[`${GG}alerts.py`] || '', pt = src[`${GG}potential.py`] || '';
      for (const [f, s] of [['alerts.py', al], ['potential.py', pt]]) {
        const rp = pyBody(s, 'run_pass');
        if (!rp) { errs.push(`${f} lost def run_pass(`); continue; }
        const code = pyCode(rp);
        for (const need of ['broker_flags(', 'broker_text_for(']) if (!code.includes(need)) errs.push(`${f} run_pass must name ${need} (DECISIONS12 D4 — the list read once per pass, the tag on the body)`);
        const gate = /^[ \t]*(?:if|elif|while)\b[^\n]*broker[^\n]*$/m.exec(code);
        if (gate) errs.push(`${f} run_pass gates on the broker list ("${gate[0].trim()}") — a TAG only, the push still rings (D4 / HIS CALL Q4)`);
        // 2026-10-17 (main session, F11): the set bound from broker_flags( may be USED only for the tag (broker_text_for) and
        // the count (broker_fold) — any other line that names it (a filter, a skip, a rebinding of reads) is a gate in disguise.
        const bind = /^[ \t]*(\w+)\s*=\s*[^\n]*\bbroker_flags\(/m.exec(code);
        if (!bind) errs.push(`${f} run_pass must bind the list ONCE (name = … broker_flags(…)) (D4)`);
        else {
          const id = bind[1];
          const uses = code.split('\n').filter((ln) => new RegExp(`\\b${id}\\b`).test(ln) && !ln.includes('broker_flags(')
            && !ln.includes('broker_text_for(') && !ln.includes('broker_fold('));
          for (const ln of uses) errs.push(`${f} run_pass uses the broker list beyond the tag and the count ("${ln.trim()}") — a TAG only, nothing filtered (D4)`);
        }
      }
      const ck = /^COUNT_KEYS = \(([\s\S]*?)\)/m.exec(al);
      if (al && (!ck || !/"broker_flagged"/.test(ck[1]))) errs.push('alerts.COUNT_KEYS must carry "broker_flagged" (DECISIONS12 D4 — informational)');

      // 4. store.py — one gajjala_state doc, the seed unioned; no new collection; the pass never filters on it.
      const st = src[`${GG}store.py`] || '';
      if (st) {
        if (!/^BROKER_STATE_ID = "broker_flags"/m.test(st)) errs.push('store.py must carry BROKER_STATE_ID = "broker_flags" (one gajjala_state doc, DECISIONS12 D1)');
        const bf = pyBody(st, 'broker_flags');
        if (!bf) errs.push('store.py lacks def broker_flags( (the ONE effective-set engine, R1)');
        else {
          const helpers = [...new Set([...pyCode(bf).matchAll(/\b(_broker\w*)\(/g)].map((m) => m[1]))].map((h) => pyBody(st, h) || '');
          const path = pyCode([bf, ...helpers].join('\n'));
          if (!/GC\.BROKER_FLAG_SEED\b/.test(pyCode(bf))) errs.push('store.broker_flags must union GC.BROKER_FLAG_SEED (fail-open to the seed, D1)');
          // AMENDMENTS12 F5 modifies D1: the read is fault-aware (_find_or_none), get_state the fallback
          if (!/_find_or_none\(|get_state\b/.test(path)) errs.push('store.broker_flags must read the doc through _find_or_none( / get_state (D1 / F5)');
        }
        const all = /^ALL = \(([^)]*)\)/m.exec(st);
        if (all && /broker/i.test(all[1])) errs.push('store.ALL names a broker collection — the list is a gajjala_state doc (no new collection)');
      }
      for (const f of ['run.py', 'scanner.py']) {
        const s = tryRead(`${GG}${f}`);
        if (/broker/i.test(s)) errs.push(`${f} names broker — nothing in the scan or the pass is filtered by his list (a TAG only)`);
      }

      // 5. api.py — the board GET serves the tag to the PRIMARY owner only (F1); three stealth-404 routes after entry-tape.
      const api = src['../backend/chart_maps/api.py'] || '';
      if (api) {
        const slice = (at) => { const n = api.indexOf('\n@router.', at + 1); return pyCode(api.slice(at, n < 0 ? undefined : n)); };
        const ga = api.indexOf('async def chart_maps_gajjala(');
        if (ga < 0) errs.push('chart_maps/api.py lost async def chart_maps_gajjala(');
        else {
          const get = slice(ga);
          if (!/is_primary_admin\(/.test(get) || !/\bowner=/.test(get)) errs.push('GET /chart-maps/gajjala must decide owner= through is_primary_admin( (AMENDMENTS12 F1 — his list, his eyes only)');
          for (const bad of ['on_demand', 'entry_tape', 'broker-flags']) if (get.includes(bad)) errs.push(`GET /chart-maps/gajjala names ${bad} — its slice stays clean (the broker routes sit after entry-tape)`);
        }
        const tapeAt = api.indexOf('@router.get("/chart-maps/gajjala/entry-tape")');
        for (const r of ['@router.get("/chart-maps/gajjala/broker-flags")', '@router.post("/chart-maps/gajjala/broker-flags")',
                         '@router.delete("/chart-maps/gajjala/broker-flags/{symbol}")']) {
          const at = api.indexOf(r);
          if (at < 0) { errs.push(`chart_maps/api.py lacks ${r} (DECISIONS12 D5)`); continue; }
          const h = slice(at);
          if (!/is_primary_admin\(/.test(h) || !/\b404\b/.test(h)) errs.push(`${r} must check is_primary_admin( and answer a non-owner 404 (stealth, AMENDMENTS12 F1)`);
          if (tapeAt < 0 || at < tapeAt) errs.push(`${r} must sit AFTER the entry-tape route (the GET / entry-tape slices stay clean)`);
        }
      }

      // 6. ledger.py — the 🏁 rows carry the tag from the tab's callable; rows_for (the history) is untouched.
      const lg = src[`${GG}ledger.py`] || '';
      if (lg) {
        const sb = pyBody(lg, 'served_block');
        if (!sb || !sb.includes('broker_text_of') || !sb.includes('"broker_text"')) errs.push('ledger.served_block must serve "broker_text" from broker_text_of (DECISIONS12 D2)');
        const rf = pyBody(lg, 'rows_for');
        if (!rf) errs.push('ledger.py lost def rows_for(');
        else if (/broker/i.test(rf)) errs.push('ledger.rows_for names broker — the history is never filtered (DECISIONS12 D2)');
      }

      // 7. the FE types no word: the broker's name never appears in GajjalaBoard.tsx (not even in a comment — house
      //    rule), never in lib/gajjala.ts code; the one path; the mounts; every chip testid; the broker JSX text is
      //    whitespace or ✕ only; ggQuery is unchanged.
      const lib = tryRead('src/lib/gajjala.ts');
      if (/Fidelity/i.test(board) || (BROKER_NAME && board.toLowerCase().includes(BROKER_NAME.toLowerCase()))) errs.push("GajjalaBoard.tsx spells the broker's name — every word is served by tab.py (DECISIONS12 D1)");
      if (/not eligible/i.test(tsCode(board))) errs.push('GajjalaBoard.tsx types "not eligible" — the served broker_text is printed verbatim');
      const libCode = tsCode(lib);
      if (/Fidelity/i.test(libCode) || /not eligible/i.test(libCode)) errs.push('lib/gajjala.ts types the broker word in code — every word is served by tab.py');
      if (lib && !/^export const GG_BROKER_PATH = '\/chart-maps\/gajjala\/broker-flags';/m.test(lib)) errs.push("lib/gajjala.ts must export GG_BROKER_PATH = '/chart-maps/gajjala/broker-flags' (== the api route)");
      for (const m of ['<BrokerFlagsStrip ', '<BrokerToggle ']) if (!board.includes(m)) errs.push(`GajjalaBoard must mount ${m}…/> (DECISIONS12 D5)`);
      for (const id of ['gg-broker-tile-', 'gg-broker-pot-', 'gg-broker-track-', 'gg-broker-watch-', 'gg-broker-aplus-',
                        'gg-broker-recap-', 'gg-graveyard-broker', 'gg-tr-broker-']) {
        if (!board.includes(id)) errs.push(`GajjalaBoard must carry the chip testid ${id}… (DECISIONS12 D2 — every surface that lists a name)`);
      }
      const fnBody = (name) => {
        const a = board.indexOf(`\nfunction ${name}(`);
        if (a < 0) return null;
        const e = board.indexOf('\n}\n', a + 1);
        return board.slice(a, e < 0 ? undefined : e);
      };
      for (const n of ['GgBrokerChip', 'BrokerFlagsStrip', 'BrokerToggle']) {
        const b = fnBody(n);
        if (b == null) { errs.push(`GajjalaBoard lacks function ${n}(`); continue; }
        // JSX text inline (`>text<`) or alone on its own line between a tag end and a tag start; `=>` folded so an arrow
        // is never a tag end
        const code = tsCode(b).replace(/=>/g, '=');
        for (const m of [...code.matchAll(/>([^<>{}\n]+)</g), ...code.matchAll(/>[ \t]*\n([^<>{}\n]+)\n[ \t]*</g)]) {
          const t = m[1].trim();
          if (t && t !== '✕') errs.push(`GajjalaBoard ${n} types the JSX text "${t}" — only "✕"; every word is served by tab.py`);
        }
      }
      if (/\bisOwner\b/.test(fnBody('BrokerFlagsStrip') || '') || /\bisOwner\b/.test(fnBody('BrokerToggle') || '')) errs.push('the 🚫 strip / toggle read isOwner — the gate is the SERVED broker_flags block');
      const qa = lib.indexOf('export function ggQuery(');
      const qe = qa < 0 ? -1 : lib.indexOf('\n}\n', qa);
      if (qa >= 0 && /broker/i.test(lib.slice(qa, qe < 0 ? undefined : qe))) errs.push('lib/gajjala.ts ggQuery names broker — the board GET is unchanged');

      // 8. ✨ — FIRST, routed to the tab, his two lines verbatim, the served word, nothing hidden, the title carries 🚫.
      const nf = tryRead('src/lib/newFeatures.ts');
      const ID = 'chart-maps-gajjala-broker-tag-2026-10-17';
      const arr = nf.indexOf('export const NEW_FEATURES');
      // WIDENED 2026-10-18 (DECISIONS13 D7 / BUILD_SPEC13 §2 B5a) — 🎾 float order + 🚩 K4 long flags took the first two ✨
      // slots; this entry must be PRESENT (the newest feature is first). `arr` stays for the slice below.
      if (arr < 0 || !nf.slice(arr).includes(`{ id: '${ID}'`)) errs.push(`the ✨ entry id: '${ID}' is missing from NEW_FEATURES`);
      const at = nf.indexOf(`{ id: '${ID}'`);
      if (at < 0) errs.push(`newFeatures.ts lacks the ✨ entry id: '${ID}'`);
      else {
        const end = nf.indexOf('" },', at);
        const e = unesc(nf.slice(at, end < 0 ? undefined : end + 4));
        const W = 'the 🚫 ✨ entry';
        if (!e.includes("route: '/chart-maps?tab=gajjala',")) errs.push(`${W} must route to '/chart-maps?tab=gajjala'`);
        for (const h of HIS) if (!e.includes(h)) errs.push(`${W} must quote him verbatim: "${h.slice(0, 40)}…"`);
        const needs = [`🚫 not eligible at ${BROKER_NAME}`, 'Nothing is hidden', 'the title carries 🚫'];   // the last = AMENDMENTS12 A1
        for (const need of needs) if (!e.includes(need)) errs.push(`${W} must say "${need}"`);
        if (B_WORD.test(e)) errs.push(`${W} says the b-word / "fake"`);
        let forbidden = [];
        try { const fw = /^FORBIDDEN_WORDS = \(([\s\S]*?)\)/m.exec(read('../backend/chart_maps/high_beta_tab.py')); forbidden = fw ? [...fw[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]) : []; } catch { /* below */ }
        if (!forbidden.length) errs.push('chart_maps/high_beta_tab.py lost FORBIDDEN_WORDS = (…)');
        for (const w of forbidden) if (e.toLowerCase().includes(w.toLowerCase())) errs.push(`${W} says "${w}" (high_beta_tab.FORBIDDEN_WORDS)`);
        let label = e.slice(Math.max(0, e.indexOf('label: ')));
        for (const h of HIS) label = label.split(h).join(' ');
        const stray = /[^\s]*\d[^\s]*/.exec(label.replace(/\b\d{4}-\d\d-\d\d\b/g, ' '));
        if (stray) errs.push(`${W} prints "${stray[0]}" — no number outside an ISO date (nothing is measured, D6)`);
      }

      // 9. SPECS.md + the doc.
      const specs = tryRead('../SPECS.md');
      if (specs && !specs.includes(`- **🚫 Not eligible at ${BROKER_NAME}** (2026-10-17`)) errs.push(`SPECS.md lacks the "- **🚫 Not eligible at ${BROKER_NAME}** (2026-10-17" bullet`);
      const DOC = '../docs/gajjala/broker_flags_2026_10_17.md';
      if (!exists(DOC)) errs.push('docs/gajjala/broker_flags_2026_10_17.md is missing');
      else {
        const doc = read(DOC);
        for (const need of ['READ THIS FIRST', 'HIS CALL', 'Q1', 'Nothing is hidden']) if (!doc.includes(need)) errs.push(`docs/gajjala/broker_flags_2026_10_17.md must carry "${need}"`);
      }
      return errs;
    },
  },
  {
    name: '🚩 K4 long flags + 🎾 float order (2026-10-18): 1–5 pullback bars = A+ (long-flag band empty), the float cap + 15 minutes unchanged on his word, the squeeze sub orders by float inside the state (MINE), the order word served by tab.py, no "a long flag" in WHAT NEVER FIRES, the FE types no word, ✨ first + second with his words verbatim',
    file: 'src/lib/newFeatures.ts',
    // Ajay 2026-10-18: "Keep the float reduce and also 15 mins filter." / "make the change for Long flags" / "for the float lower
    // the better is what I wanna follow so sort it by lowest on top" (DECISIONS13 D1–D8, BUILD_SPEC13 §2 B5b). He trades the A+
    // pushes with real money: a 4–5 bar flag must ring under the K4 numbers he set, the float cap and his first 15 minutes must
    // hold on his word, and the order word must be the served one — never a second copy typed in the browser.
    checks: (nf) => {
      const errs = [];
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16))).replace(/\\'/g, "'");
      const tryRead = (rel) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable`); return ''; } };
      const tsCode = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '').replace(/(^|\s)\/\/[^\n]*/g, '$1');
      const pyBody = (src, def) => { const a = src.indexOf(`\ndef ${def}(`); if (a < 0) return null; const e = src.indexOf('\ndef ', a + 5); return src.slice(a, e < 0 ? undefined : e); };
      const B_WORD = /boun|fake/i;
      const HIS_KEEP = 'Keep the float reduce and also 15 mins filter';
      const HIS_LONG = 'make the change for Long flags';
      const HIS_FLOAT = 'for the float lower the better is what I wanna follow so sort it by lowest on top';
      const GG = '../backend/chart_maps/gajjala/';

      // 1–3. constants.py — his K4 numbers (dated), his confirmation of K8 + the 15 minutes (values unchanged), my sort knob.
      const gc = tryRead(`${GG}constants.py`);
      const cline = (name) => new RegExp(`^${name} = ([^\\n]*?)\\s*#\\s*([^\\n]*)$`, 'm').exec(gc);
      const val = (name) => { const m = cline(name); return m ? m[1].trim() : null; };
      const tag = (name) => { const m = cline(name); return m ? m[2].trim() : ''; };
      if (gc) {
        if (val('K4_BF_PULL_MAX') !== '5' || !/^Ajay 2026-10-18\b/.test(tag('K4_BF_PULL_MAX'))) errs.push('constants.py must carry K4_BF_PULL_MAX = 5  # Ajay 2026-10-18 … (DECISIONS13 D1 — 1–5 pullback bars = A+)');
        if (val('K4_BF_LONG_FLAG_MAX') !== 'None' || !/^Ajay 2026-10-18\b/.test(tag('K4_BF_LONG_FLAG_MAX'))) errs.push('constants.py must carry K4_BF_LONG_FLAG_MAX = None  # Ajay 2026-10-18 … (DECISIONS13 D1 — the long-flag band is empty)');
        if (val('K8_MAX_FLOAT') !== '10_000_000') errs.push(`constants.py K8_MAX_FLOAT must stay 10_000_000 — Ajay 2026-10-18 "${HIS_KEEP}" (found ${val('K8_MAX_FLOAT')})`);
        if (val('NO_TRADE_AFTER_OPEN_MIN') !== '15') errs.push(`constants.py NO_TRADE_AFTER_OPEN_MIN must stay 15 — Ajay 2026-10-18 "${HIS_KEEP}" (found ${val('NO_TRADE_AFTER_OPEN_MIN')})`);
        if (!/^"(within_state|global)"$/.test(val('RS_FLOAT_SORT') || '') || !/^MINE\b/.test(tag('RS_FLOAT_SORT'))) errs.push('constants.py must carry RS_FLOAT_SORT = "within_state" | "global"  # MINE (DECISIONS13 D3 — HIS CALL Q1)');
      }

      // 4. tab.py — the ONE served order word, the float key on the squeeze sub only, served as order_note.
      const tab = tryRead(`${GG}tab.py`);
      if (tab) {
        if (!/^RS_ORDER_TEXT = "🎾 lowest float on top"/m.test(tab)) errs.push('tab.py must carry RS_ORDER_TEXT = "🎾 lowest float on top" — the ONE served order word (DECISIONS13 D3)');
        const ok = pyBody(tab, 'order_key');
        if (!ok) errs.push('tab.py lost def order_key(');
        else for (const need of ['_float_shares', 'reversal_squeeze']) if (!ok.includes(need)) errs.push(`tab.order_key must name ${need} (DECISIONS13 D3 — float order on the squeeze sub only)`);
        if (!tab.includes('"order_note"')) errs.push('tab.py must serve "order_note" (the key lib/gajjala.ts reads)');
      }

      // 5. Notifications.tsx — neither WHAT NEVER FIRES sentence (🚩 / 🧠) names "a long flag" any more (DECISIONS13 D4).
      const nt = tryRead('src/pages/Notifications.tsx');
      for (const k of ['gajjala_setup', 'gajjala_potential']) {
        const a = nt.indexOf(`key: '${k}'`);
        if (a < 0) { errs.push(`Notifications.tsx lost the ${k} entry`); continue; }
        const b = nt.indexOf("{ key: '", a + 5);
        const entry = nt.slice(a, b < 0 ? undefined : b);
        const w = entry.indexOf('WHAT NEVER FIRES');
        if (w < 0) { errs.push(`Notifications.tsx ${k} lost its WHAT NEVER FIRES sentence`); continue; }
        const q = /(?<!\\)'/.exec(entry.slice(w));
        const sentence = entry.slice(w, q ? w + q.index : undefined);
        if (/long flag/i.test(sentence)) errs.push(`Notifications.tsx ${k} WHAT NEVER FIRES still names "a long flag" — 1–5 bars are A+ since 2026-10-18 (DECISIONS13 D4)`);
      }

      // 6. the FE types no order word: GajjalaBoard.tsx + lib/gajjala.ts code never spell "lowest float"; the board prints
      //    the served order_note under its testid; the lib type carries the key.
      const board = tryRead('src/components/GajjalaBoard.tsx');
      const lib = tryRead('src/lib/gajjala.ts');
      if (/lowest float/i.test(tsCode(board))) errs.push('GajjalaBoard.tsx types "lowest float" — the served order_note is printed verbatim (DECISIONS13 D3)');
      if (/lowest float/i.test(tsCode(lib))) errs.push('lib/gajjala.ts types "lowest float" in code — the order word is served by tab.py');
      if (board && (!board.includes('data-testid="gg-order-note"') || !board.includes('board.order_note'))) errs.push('GajjalaBoard.tsx must print board.order_note under data-testid="gg-order-note" (BUILD_SPEC13 §2 B2)');
      if (lib && !/order_note\?: string \| null;/.test(lib)) errs.push('lib/gajjala.ts board type must carry order_note?: string | null (BUILD_SPEC13 §2 B1)');

      // 7. ✨ — the 🎾 float order, then the 🚩 long flags right after it; his lines verbatim; routes; UNMEASURED; never the b-word.
      // WIDENED 2026-10-18 (DECISIONS14 D8 / BUILD_SPEC14 B2) — the ⚡ Tape scan entry took the first ✨ slot; the two entries
      // must be PRESENT and ADJACENT in this order (the newest feature is first), no longer FIRST and SECOND.
      const arr = nf.indexOf('export const NEW_FEATURES');
      const allIds = arr < 0 ? [] : [...nf.slice(arr).matchAll(/\{ id: '([^']+)'/g)].map((m) => m[1]);
      const ID1 = 'chart-maps-gajjala-float-sort-2026-10-18', ID2 = 'chart-maps-gajjala-long-flags-2026-10-18';
      const i1 = allIds.indexOf(ID1);
      if (i1 < 0 || allIds[i1 + 1] !== ID2) errs.push(`the ✨ entries '${ID1}' then '${ID2}' must be present and adjacent in NEW_FEATURES (found ${allIds.slice(0, 3).join(', ')})`);
      let forbidden = [];
      try { const fw = /^FORBIDDEN_WORDS = \(([\s\S]*?)\)/m.exec(read('../backend/chart_maps/high_beta_tab.py')); forbidden = fw ? [...fw[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]) : []; } catch { /* below */ }
      if (!forbidden.length) errs.push('chart_maps/high_beta_tab.py lost FORBIDDEN_WORDS = (…)');
      const rows = [
        [ID1, '/chart-maps?tab=gajjala&sub=reversal_squeeze', [HIS_FLOAT], 'the 🎾 ✨ entry', '🎾 Gajjala’s Reversal Squeeze now lists the lowest float on top.'],
        [ID2, '/chart-maps?tab=gajjala&sub=bull_flag', [HIS_LONG, HIS_KEEP, 'UNMEASURED'], 'the 🚩 K4 ✨ entry', '🚩 Bull Flags with 4–5 pullback bars are A+ now (they ring).'],
      ];
      for (const [id, route, needs, W, lead] of rows) {
        const at = nf.indexOf(`{ id: '${id}'`);
        if (at < 0) { errs.push(`newFeatures.ts lacks the ✨ entry id: '${id}'`); continue; }
        const end = nf.indexOf('" },', at);
        const e = unesc(nf.slice(at, end < 0 ? undefined : end + 4));
        if (!e.includes(`route: '${route}',`)) errs.push(`${W} must route to '${route}'`);
        if (!e.includes(`label: "${lead}`)) errs.push(`${W} label must begin "${lead}"`);
        for (const h of needs) if (!e.includes(h)) errs.push(`${W} must say / quote him verbatim: "${h.slice(0, 40)}…"`);
        if (B_WORD.test(e)) errs.push(`${W} says the b-word / "fake"`);
        for (const w of forbidden) if (e.toLowerCase().includes(w.toLowerCase())) errs.push(`${W} says "${w}" (high_beta_tab.FORBIDDEN_WORDS)`);
      }

      // 8. the doc.
      const DOC = '../docs/gajjala/k4_long_flags_float_2026_10_18.md';
      if (!exists(DOC)) errs.push('docs/gajjala/k4_long_flags_float_2026_10_18.md is missing');
      else {
        const doc = read(DOC);
        for (const need of ['READ THIS FIRST', 'HIS CALL', 'Q1', 'UNMEASURED']) if (!doc.includes(need)) errs.push(`docs/gajjala/k4_long_flags_float_2026_10_18.md must carry "${need}"`);
      }

      // 9. SPECS.md names K4_BF_PULL_MAX with 1–5.
      const specs = tryRead('../SPECS.md');
      if (specs && !/`K4_BF_PULL_MAX`[^\n]{0,24}1–5/.test(specs)) errs.push('SPECS.md must name `K4_BF_PULL_MAX` 1–5 (BUILD_SPEC13 §3 M2)');
      return errs;
    },
  },
  {
    name: '⚡ Tape scan parallel windows (2026-10-18): MINE edges / workers / per-window caps pinned, the covered-window rule in quote_rule_sides and retail.identify, the FE copy promises no seconds and no "1.2M", ✨ first with his words + the AFTER line, coverage % = prints with a quote we hold (D10), per-page compaction (D11), caps 24 / 8 (D12), no "always read", the docs',
    file: 'src/lib/newFeatures.ts',
    // Ajay 2026-10-18: "I see a big lag in Tap reading its 30 secs this feature. Can we make it fast." (DECISIONS14 D1–D8,
    // BUILD_SPEC14 B3). The day is pulled in parallel ET windows with a per-window cap; the quote rule must classify only
    // prints whose quote is held, and the panel must never promise a number of seconds or a print count it no longer reads.
    checks: (nf) => {
      const errs = [];
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16))).replace(/\\'/g, "'");
      const tryRead = (rel) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable`); return ''; } };
      const pyBody = (src, def) => { const a = src.indexOf(`\ndef ${def}(`); if (a < 0) return null; const e = src.indexOf('\ndef ', a + 5); return src.slice(a, e < 0 ? undefined : e); };
      const HIS = 'I see a big lag in Tap reading its 30 secs this feature. Can we make it fast.';
      const OF = '../backend/orderflow/';
      const constLine = (src, name) => new RegExp(`^${name} = ([^\\n#]*?)\\s*#\\s*([^\\n]*)$`, 'm').exec(src);

      // 1. massive_pages.py — the MINE window edges (D2), the MINE worker count (D3), the two entry points (D1).
      const mp = tryRead(`${OF}massive_pages.py`);
      if (mp) {
        // the statement = its first line through the first line whose CODE (before #) closes the tuple, so a trailing
        // comment's own parentheses never end it
        const wa = mp.search(/^WINDOW_EDGES_ET = \(/m);
        let we = null;
        if (wa >= 0) {
          const span = [], code = [];
          for (const ln of mp.slice(wa).split('\n')) { span.push(ln); code.push(ln.split('#')[0]); if (code.length === 1 ? code[0].slice(code[0].indexOf('(') + 1).includes(')') : code[code.length - 1].includes(')')) break; }
          we = [span.join('\n'), code.join('\n')];
        }
        if (!we) errs.push('massive_pages.py must carry WINDOW_EDGES_ET = ( … ) (DECISIONS14 D2)');
        else {
          const edges = [...we[1].matchAll(/"([^"]*)"/g)].map((m) => m[1]);
          const hhmm = edges.every((x) => /^\d\d:\d\d$/.test(x));
          const asc = edges.every((x, i) => i === 0 || x > edges[i - 1]);
          if (edges.length !== 14 || !hhmm || !asc || edges[0] !== '04:00' || edges[13] !== '20:00') errs.push(`massive_pages.WINDOW_EDGES_ET must hold 14 ascending "HH:MM" edges from "04:00" to "20:00" (DECISIONS14 D2; found ${edges.length}: ${edges.join(', ')})`);
          if (!we[0].includes('# MINE (DECISIONS14 D2)')) errs.push('massive_pages.WINDOW_EDGES_ET must carry # MINE (DECISIONS14 D2)');
        }
        const fw = constLine(mp, 'FETCH_WORKERS');
        if (!fw || fw[1].trim() !== '8' || !fw[2].startsWith('MINE (DECISIONS14 D3)')) errs.push('massive_pages.py must carry FETCH_WORKERS = 8  # MINE (DECISIONS14 D3)');
        for (const d of ['windows_for', 'fetch_windowed']) if (!mp.includes(`def ${d}(`)) errs.push(`massive_pages.py must define def ${d}( (DECISIONS14 D1)`);
        // 10. every page is compacted as it arrives — fetch_windowed takes the compact callable (DECISIONS14 D11).
        const fwSig = /def fetch_windowed\(([\s\S]*?)\)\s*(->[^:\n]*)?:/.exec(mp);
        if (fwSig && !/\bcompact\b/.test(fwSig[1])) errs.push('massive_pages.fetch_windowed must take compact — each page compacted as it arrives (DECISIONS14 D11)');
      }

      // 2. tape.py — the per-window trade cap (D4); fetch_trades goes through the shared pager, no serial loop left (D1).
      const tp = tryRead(`${OF}tape.py`);
      if (tp) {
        const tc = constLine(tp, 'TRADE_PAGES_PER_WINDOW');
        // CHANGED 2026-10-18 (DECISIONS14 D12, critic HIGH): 2 → 24 = the old whole-day cap, so no window is capped on a day
        // the serial pager read in full.
        if (!tc || tc[1].trim() !== '24' || !tc[2].startsWith('MINE (DECISIONS14 D12)')) errs.push('tape.py must carry TRADE_PAGES_PER_WINDOW = 24  # MINE (DECISIONS14 D12)');
        const ft = pyBody(tp, 'fetch_trades');
        if (!ft) errs.push('tape.py lost def fetch_trades(');
        else {
          if (!ft.includes('fetch_windowed(')) errs.push('tape.fetch_trades must call fetch_windowed( (DECISIONS14 D1 — one shared pager)');
          if (/while\s+next_url/.test(ft)) errs.push('tape.fetch_trades still pages serially (while next_url) — DECISIONS14 D1');
        }
      }

      // 3. quotes.py — the per-window quote cap (D4), covered windows set by fetch_quotes and honoured by the quote rule (D5);
      //    retail.identify honours them too (D5).
      const qt = tryRead(`${OF}quotes.py`);
      if (qt) {
        const qc = constLine(qt, 'QUOTE_PAGES_PER_WINDOW');
        // CHANGED 2026-10-18 (DECISIONS14 D12): 4 → 8 (400k NBBO rows per window).
        if (!qc || qc[1].trim() !== '8' || !qc[2].startsWith('MINE (DECISIONS14 D12)')) errs.push('quotes.py must carry QUOTE_PAGES_PER_WINDOW = 8  # MINE (DECISIONS14 D12)');
        if (!qt.includes('\ndef covered_mask(')) errs.push('quotes.py must define def covered_mask( (DECISIONS14 D5)');
        const fq = pyBody(qt, 'fetch_quotes');
        if (!fq) errs.push('quotes.py lost def fetch_quotes(');
        else if (!/attrs\[\s*["']covered["']\s*\]\s*=/.test(fq)) errs.push('quotes.fetch_quotes must set attrs["covered"] (DECISIONS14 D5)');
        const qr = pyBody(qt, 'quote_rule_sides');
        if (!qr) errs.push('quotes.py lost def quote_rule_sides(');
        else if (!qr.includes('covered_mask(')) errs.push('quotes.quote_rule_sides must call covered_mask( — classify only inside covered windows (DECISIONS14 D5)');
      }
      const rt = tryRead(`${OF}retail.py`);
      if (rt) {
        const idf = pyBody(rt, 'identify');
        if (!idf) errs.push('retail.py lost def identify(');
        else if (!idf.includes('covered_mask(')) errs.push('retail.identify must call covered_mask( — sign only inside covered windows (DECISIONS14 D5)');
      }

      // 4. TapePanel.tsx — the copy promises no seconds and no print count (D8).
      const panel = tryRead('src/components/TapePanel.tsx');
      if (panel) {
        if (!panel.includes('megacaps take longer')) errs.push('TapePanel.tsx scanning copy must say "megacaps take longer" (DECISIONS14 D8)');
        if (panel.includes('~30s')) errs.push('TapePanel.tsx still promises "~30s" — no number of seconds (DECISIONS14 D8)');
        if (panel.includes('1.2M')) errs.push('TapePanel.tsx still says "1.2M" — the cap is per window now (DECISIONS14 D4/D8)');
      }

      // 5. ✨ — present, his line verbatim, "Not advice.". WIDENED 2026-10-18 (same day): FIRST → present, because the
      // 🧠 tiles-first entry (chart-maps-gajjala-potential-tiles-first-2026-10-18, his later ask that day) is newer.
      const ID = 'tape-scan-parallel-2026-10-18';
      const at = nf.indexOf(`{ id: '${ID}'`);
      if (at < 0) errs.push(`newFeatures.ts lacks the ✨ entry id: '${ID}' (DECISIONS14 D8)`);
      else {
        const end = nf.indexOf('" },', at);
        const e = unesc(nf.slice(at, end < 0 ? undefined : end + 4));
        if (!e.includes(HIS)) errs.push(`the ⚡ ✨ entry must quote him verbatim: "${HIS}" (DECISIONS14 D8)`);
        if (!e.includes('Not advice.')) errs.push('the ⚡ ✨ entry must end "Not advice." (DECISIONS14 D8)');
        // 8. the AFTER line is present (the __AFTER__ token or the filled counts), the old placeholder gone (DECISIONS14 Amendments).
        // CHANGED 2026-10-18 (DECISIONS14 Amendments after the critic): the counts are re-measured, so the token is accepted.
        if (!e.includes('After, same day:')) errs.push('the ⚡ ✨ entry must carry the "After, same day:" line (DECISIONS14 Amendments)');
        if (e.includes('measured after the build')) errs.push('the ⚡ ✨ entry still carries the "measured after the build" placeholder (DECISIONS14 Amendments)');
      }

      // 7. lib/orderflow.ts classificationView — coverage % = prints with a quote we hold, in BOTH tooltips; never the old
      //    wording that conflated coverage with the midpoint (DECISIONS14 D10).
      const ofl = tryRead('src/lib/orderflow.ts');
      if (ofl) {
        const ca = ofl.indexOf('export function classificationView(');
        const ce = ca < 0 ? -1 : ofl.indexOf('\n}\n', ca);
        const cv = ca < 0 ? '' : ofl.slice(ca, ce < 0 ? undefined : ce);
        if (!cv) errs.push('lib/orderflow.ts lost export function classificationView( (DECISIONS14 D10)');
        else {
          const qa = cv.indexOf("method === 'quote'"), ma = cv.indexOf("method === 'mixed'");
          const quoteBr = qa < 0 ? '' : cv.slice(qa, ma > qa ? ma : undefined);
          const mixedBr = ma < 0 ? '' : cv.slice(ma);
          if (!quoteBr.includes('had a quote we hold')) errs.push('classificationView quote tooltip must say "had a quote we hold" (DECISIONS14 D10)');
          if (!mixedBr.includes('had a quote we hold')) errs.push('classificationView mixed tooltip must say "had a quote we hold" (DECISIONS14 D10)');
          if (cv.includes('the rest sat exactly at the midpoint')) errs.push('classificationView still says "the rest sat exactly at the midpoint" — coverage and at-mid are two counts (DECISIONS14 D10)');
        }
      }

      // 11. no surface claims the tail of the day is "always read" — a capped window loses ITS tail (DECISIONS14 critic MED).
      if (nf.includes('always read')) errs.push('newFeatures.ts says "always read" — a capped window loses its own tail (DECISIONS14 critic MED)');
      const pdoc = exists('../docs/orderflow/parallel_fetch_2026_10_18.md') ? read('../docs/orderflow/parallel_fetch_2026_10_18.md') : '';
      if (pdoc.includes('always read')) errs.push('docs/orderflow/parallel_fetch_2026_10_18.md says "always read" — a capped window loses its own tail (DECISIONS14 critic MED)');

      // 9. the quote-rule doc says it in the same words (DECISIONS14 D10).
      const qdoc = tryRead('../docs/orderflow/quote_rule_and_darkpool.md');
      if (qdoc && !qdoc.includes('quote we hold')) errs.push('docs/orderflow/quote_rule_and_darkpool.md must say "quote we hold" (DECISIONS14 D10)');

      // 6. the doc.
      const DOC = '../docs/orderflow/parallel_fetch_2026_10_18.md';
      if (!exists(DOC)) errs.push('docs/orderflow/parallel_fetch_2026_10_18.md is missing (DECISIONS14 D8)');
      else {
        const doc = read(DOC);
        for (const need of ['READ THIS FIRST', 'Measured', 'HIS CALL']) if (!doc.includes(need)) errs.push(`docs/orderflow/parallel_fetch_2026_10_18.md must carry "${need}" (DECISIONS14 D8/D9)`);
      }
      return errs;
    },
  },
  {
    name: 'ℹ️ Gajjala counts legend (2026-10-18): ONE served legend (tab.count_legend + LEGEND_KEYS, MINE) served as counts_legend, its texts carry the definitions, the FE prints them and types none, lib/gajjala.ts declares the key, ✨ first with his lines verbatim + "Not advice.", the tab doc names counts_legend',
    file: 'src/lib/newFeatures.ts',
    // Ajay 2026-10-18: "Ok Forming is still Criteria not met.. Potential is all the gajjalas criteria met. may be add an info
    // tag for them explicitly.. To tell me what athey are" (DECISIONS15 D1–D4, BUILD_SPEC15 B5). He read two words the other
    // way round; the words that explain them must have ONE source (tab.py), never a second copy typed in the browser.
    checks: (nf) => {
      const errs = [];
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16))).replace(/\\'/g, "'");
      const tryRead = (rel) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable`); return ''; } };
      const pyBody = (src, def) => { const a = src.indexOf(`\ndef ${def}(`); if (a < 0) return null; const e = src.indexOf('\ndef ', a + 5); return src.slice(a, e < 0 ? undefined : e); };
      const DEFS = ['no rule has failed', 'a rule failed', 'every rule'];
      const HIS1 = 'Ok Forming is still Criteria not met.. Potential is all the gajjalas criteria met.';
      const HIS2 = 'may be add an info tag for them explicitly.. To tell me what athey are';

      // 1–2. tab.py — the legend function, its MINE keys, served on the payload; the definitions live in its body.
      const tab = tryRead('../backend/chart_maps/gajjala/tab.py');
      if (tab) {
        if (!/^LEGEND_KEYS = [^\n]*# MINE \(DECISIONS15 D1\)/m.test(tab)) errs.push('tab.py must carry LEGEND_KEYS = …  # MINE (DECISIONS15 D1)');
        const body = pyBody(tab, 'count_legend');
        if (!body) errs.push('tab.py must define def count_legend( (DECISIONS15 D1 — the ONE served legend)');
        else for (const need of DEFS) if (!body.includes(need)) errs.push(`tab.count_legend must say "${need}" (DECISIONS15 table)`);
        if (!tab.includes('"counts_legend"')) errs.push('tab.py must serve "counts_legend" (the key lib/gajjala.ts reads)');
      }

      // 3. GajjalaBoard.tsx prints the served legend and types no definition.
      const board = tryRead('src/components/GajjalaBoard.tsx');
      if (board) {
        if (!board.includes('gg-counts-legend')) errs.push('GajjalaBoard.tsx must render the folded legend (gg-counts-legend, DECISIONS15 D2)');
        if (!board.includes('counts_legend')) errs.push('GajjalaBoard.tsx must read board.counts_legend (DECISIONS15 D2)');
        for (const d of DEFS) if (board.toLowerCase().includes(d)) errs.push(`GajjalaBoard.tsx types "${d}" — the FE prints the served legend and defines no state (DECISIONS15 D2)`);
      }

      // 4. lib/gajjala.ts declares the served key.
      const lib = tryRead('src/lib/gajjala.ts');
      if (lib && !/counts_legend\?:/.test(lib)) errs.push('lib/gajjala.ts board type must declare counts_legend?: (BUILD_SPEC15 B1)');

      // 5. ✨ FIRST, his lines verbatim, "Not advice.", never the b-word / "fake".
      const ID = 'chart-maps-gajjala-counts-legend-2026-10-18';
      // WIDENED 2026-10-19 — 🌙 overnight session took the first ✨ slot (BUILD_SPEC16 §3.10 (7)); this entry must be PRESENT (the newest feature is first).
      const arr = nf.indexOf('export const NEW_FEATURES');
      if (arr < 0 || !nf.slice(arr).includes(`{ id: '${ID}'`)) errs.push(`the ✨ entry '${ID}' is missing from NEW_FEATURES`);
      const at = nf.indexOf(`{ id: '${ID}'`);
      if (at >= 0) {
        const end = nf.indexOf('" },', at);
        const e = unesc(nf.slice(at, end < 0 ? undefined : end + 4));
        if (!e.includes("route: '/chart-maps?tab=gajjala&sub=potential',")) errs.push("the ℹ️ ✨ entry must route to '/chart-maps?tab=gajjala&sub=potential'");
        for (const h of [HIS1, HIS2]) if (!e.includes(h)) errs.push(`the ℹ️ ✨ entry must quote him verbatim: "${h.slice(0, 40)}…"`);
        if (!e.includes('Not advice.')) errs.push('the ℹ️ ✨ entry must end "Not advice."');
        if (/boun|fake/i.test(e)) errs.push('the ℹ️ ✨ entry says the b-word / "fake"');
      }

      // 6. the tab doc names the served key.
      const doc = tryRead('../docs/gajjala/gajjala_tab_2026_10_13.md');
      if (doc && !doc.includes('counts_legend')) errs.push('docs/gajjala/gajjala_tab_2026_10_13.md must name "counts_legend" (BUILD_SPEC15 A3)');
      return errs;
    },
  },
  {
    name: '🌙 overnight session + overnight_movers (2026-10-19)',
    file: 'src/components/OvernightSessionBoard.tsx',
    // Ajay 2026-10-19: "Can you do an over night scan for all the stocks they are all growing over night", "Here are from
    // stocktwits", "These are over night check qqq for example", "Massive is what we use probably we don't have the
    // subscription" (BUILD_SPEC16 §3.10 + AMENDMENTS16 A1/A4). He ACTS on what this tab and its push say (real money): a
    // floor typed on a surface drifts from the constant that drives the pass, a kind missing from a registry sends to zero
    // devices in silence, a cron line wrapped in market_hours.gate skips Sunday night. The 🎚️ block is the template.
    // Every backend file is hard-read: the four packages land in ONE commit. UNMEASURED.
    checks: (board) => {
      const errs = [];
      const K = 'overnight_movers';
      const ID = 'chart-maps-overnight-session-2026-10-19';
      const HIS = [
        'Can you do an over night scan for all the stocks they are all growing over night',
        'Here are from stocktwits',
        'These are over night check qqq for example',
        "Massive is what we use probably we don't have the subscription",
      ];
      const BANNED = /boun|fak[e]/i;
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)))
        .replace(/\\u([0-9A-Fa-f]{4})/g, (_m, h) => String.fromCodePoint(parseInt(h, 16))).replace(/\\'/g, "'");
      const pyNoComments = (x) => x.replace(/#[^\n]*/g, '');
      const tryRead = (rel, who) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable (${who})`); return ''; } };
      const pyNum = (src, name) => { const m = new RegExp(`^${name} = ([0-9_.]+)\\b`, 'm').exec(src); return m ? Number(m[1].replace(/_/g, '')) : null; };
      const usd = (n) => (n >= 1e6 && n % 1e6 === 0 ? `$${n / 1e6}M` : n >= 1e3 && n % 1e3 === 0 ? `$${n / 1e3}K` : `$${Number(n.toFixed(2))}`);

      // 1. the engines and their frozen names (WP-A / WP-B).
      const scan = tryRead('../backend/overnight/scan.py', 'WP-A');
      const sess = tryRead('../backend/overnight/session.py', 'WP-A');
      const boardPy = tryRead('../backend/overnight/board.py', 'WP-A');
      const push = tryRead('../backend/overnight/push.py', 'WP-B');
      const floor = tryRead('../backend/trading/safety_floor.py', 'house floor');
      for (const [src, file, re, word] of [
        [scan, 'scan.py', /^FEED = "overnight"/m, 'FEED = "overnight"'],
        [scan, 'scan.py', /^ALPACA_BATCH = 200\b/m, 'ALPACA_BATCH = 200'],
        [scan, 'scan.py', /^UNIVERSE_MIN_DOLLAR_VOL = 1_000_000\b/m, 'UNIVERSE_MIN_DOLLAR_VOL = 1_000_000'],
        [scan, 'scan.py', /^BOARD_MIN_ON_DOLLAR = 25_000\b/m, 'BOARD_MIN_ON_DOLLAR = 25_000'],
        [scan, 'scan.py', /^REF_SYMBOLS = \("SPY", "QQQ", "IWM", "DIA"\)/m, 'REF_SYMBOLS = ("SPY", "QQQ", "IWM", "DIA")'],
        [scan, 'scan.py', /^UNIVERSE_MIN_PRICE = MIN_SHARE_PRICE\b/m, 'UNIVERSE_MIN_PRICE = MIN_SHARE_PRICE (the house $ floor, by name)'],
        [sess, 'session.py', /^SESSION_OPEN_ET = dtime\(20, 0\)/m, 'SESSION_OPEN_ET = dtime(20, 0)'],
        [sess, 'session.py', /^SESSION_CLOSE_ET = dtime\(4, 0\)/m, 'SESSION_CLOSE_ET = dtime(4, 0)'],
        [push, 'push.py', /^KIND = "overnight_movers"/m, 'KIND = "overnight_movers"'],
        [push, 'push.py', /^SLOT_ET = "\d\d:\d\d"/m, 'SLOT_ET = "HH:MM"'],
        [push, 'push.py', /^PUSH_TOP_N = \d+\b/m, 'PUSH_TOP_N = <int>'],
        [push, 'push.py', /^PUSH_MIN_ON_DOLLAR = [0-9_]+\b/m, 'PUSH_MIN_ON_DOLLAR = <int>'],
        [push, 'push.py', /^PUSH_MIN_PRICE = MIN_SHARE_PRICE\b/m, 'PUSH_MIN_PRICE = MIN_SHARE_PRICE (the house $ floor, by name)'],
      ]) if (src && !re.test(src)) errs.push(`overnight/${file} must define ${word} (BUILD_SPEC16 §3.10 (1))`);
      const minPx = pyNum(floor, 'MIN_SHARE_PRICE');
      if (floor && minPx == null) errs.push('trading/safety_floor.py lost MIN_SHARE_PRICE = <number>');
      const uniDv = pyNum(scan, 'UNIVERSE_MIN_DOLLAR_VOL'), boardDv = pyNum(scan, 'BOARD_MIN_ON_DOLLAR'), cadence = pyNum(scan, 'CADENCE_SEC');
      const topN = pyNum(push, 'PUSH_TOP_N'), pushDv = pyNum(push, 'PUSH_MIN_ON_DOLLAR');
      const slot = (/^SLOT_ET = "(\d\d:\d\d)"/m.exec(push) || [])[1] || null;
      const hm = (name) => { const m = new RegExp(`^${name} = dtime\\((\\d+),\\s*(\\d+)\\)`, 'm').exec(sess); return m ? `${m[1].padStart(2, '0')}:${m[2].padStart(2, '0')}` : null; };
      const open = hm('SESSION_OPEN_ET'), close = hm('SESSION_CLOSE_ET');

      // 2. the crontab: two self-gated scan lines, one gated push line at SLOT_ET.
      const cron = cronCommands(tryRead('../backend/crontab', 'WP-A'));
      const scanLines = cron.filter((l) => /-m overnight\.scan\b/.test(l));
      const wantScan = [['*/10', '20-23', '*', '*', '0-4'], ['*/10', '0-3', '*', '*', '1-5']];
      if (scanLines.length !== 2) errs.push(`the crontab must carry exactly two "-m overnight.scan" lines (found ${scanLines.length}, BUILD_SPEC16 §3.5)`);
      else for (let i = 0; i < 2; i++) {
        const f = scanLines[i].trim().split(/\s+/).slice(0, 5);
        if (f.join(' ') !== wantScan[i].join(' ')) errs.push(`overnight.scan line ${i + 1} must run "${wantScan[i].join(' ')}" (got "${f.join(' ')}")`);
      }
      for (const l of scanLines) if (/market_hours\.gate/.test(l)) errs.push('an overnight.scan line runs via market_hours.gate — the gate reads TODAY and Sunday 20:00 would skip (D6)');
      for (const l of cron.filter((x) => /overnight/.test(x))) if (/curl|api:8000/.test(l)) errs.push(`an overnight crontab line calls the api (${l.trim()}) — a python module, never a curl`);
      const step = scanLines.length ? Number((/^\*\/(\d+)\s/.exec(scanLines[0].trim()) || [])[1]) : null;
      if (step && cadence != null && step * 60 !== cadence) errs.push(`scan.CADENCE_SEC (${cadence}) != the crontab */${step} step`);
      const pushLines = cron.filter((l) => /market_hours\.gate overnight\.push\b/.test(l));
      if (pushLines.length !== 1) errs.push(`the crontab must carry exactly one "market_hours.gate overnight.push" line (found ${pushLines.length})`);
      else if (slot) {
        const [mm, hh] = pushLines[0].trim().split(/\s+/);
        if (`${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}` !== slot) errs.push(`the overnight.push line runs at ${hh}:${mm} — push.SLOT_ET is ${slot}`);
      }

      // 3. every registry — ships OFF, NOT in the keep-set.
      const subs = tryRead('../backend/push/subs.py', 'WP-B');
      const dm = new RegExp(`["']${K}["']\\s*:\\s*(True|False)`).exec(subs);
      if (subs && !dm) errs.push(`push/subs.py default_prefs must list "${K}" (a kind missing = zero devices)`);
      else if (dm && dm[1] !== 'False') errs.push(`${K} must be False in push/subs.py default_prefs — it ships OFF (HIS CALL #1)`);
      if (keepSet(subs).includes(K)) errs.push(`${K} must NOT be in push/subs.OWNER_KEEP_SET — he asked for a scan, not an alert (HIS CALL #1)`);
      const gate = tryRead('../backend/market_hours/gate.py', 'WP-B');
      if (gate && !(pyFrozenSet(gate, 'MARKET_ALERT_KINDS') || []).includes(K)) errs.push(`market_hours/gate.py must treat ${K} as a MARKET kind (silent on closed days)`);
      const recent = tryRead('../backend/push/recent.py', 'WP-B');
      const itemBlock = (/^ITEM_URL_BY_KIND = \{([\s\S]*?)\n\}/m.exec(recent) || [])[1] || '';
      const iu = new RegExp(`["']${K}["']\\s*:\\s*([^,\\n]+)`).exec(pyNoComments(itemBlock));
      if (recent && !iu) errs.push(`push/recent.ITEM_URL_BY_KIND must carry ${K} — every listed name is its own link on /alerts`);
      else if (iu && iu[1].trim() !== '"/chart-maps?tab=support&symbol={sym}"') errs.push(`push/recent.ITEM_URL_BY_KIND["${K}"] must be "/chart-maps?tab=support&symbol={sym}" (got ${iu[1].trim()})`);
      const status = tryRead('../backend/supply_demand/alert_status.py', 'WP-B');
      const dpk = (/^DAILY_PASS_KINDS = \(([\s\S]*?)\)/m.exec(pyNoComments(status)) || [])[1] || '';
      // A member is the literal or a module-level NAME bound to it (the TAPE_CONTROL_KIND precedent: `OVERNIGHT_KIND = "overnight_movers"`).
      const dpkHas = new RegExp(`["']${K}["']`).test(dpk) || [...dpk.matchAll(/\b([A-Z][A-Z0-9_]*)\b/g)]
        .some((m) => new RegExp(`^${m[1]} = ["']${K}["']`, 'm').test(status));
      if (status && !dpkHas) errs.push(`supply_demand/alert_status.DAILY_PASS_KINDS must carry "${K}"`);
      const kinds = tryRead('src/lib/alertKinds.ts', 'WP-B');
      if (kinds && !new RegExp(`^\\s*${K}:\\s*\\{[^\\n]*group: 'trading'`, 'm').test(kinds)) errs.push(`alertKinds.ts must register ${K} in the 'trading' group — else the bell renders a raw id`);
      const alerts = tryRead('src/pages/Alerts.tsx', 'WP-B');
      const daily = (/const DAILY_PASSES:[^=]*=\s*\[([\s\S]*?)\n\];/.exec(alerts) || [])[1] || '';
      if (alerts && !new RegExp(`key: '${K}'`).test(daily)) errs.push(`Alerts.tsx DAILY_PASSES must carry '${K}' — the 🌙 daily strip`);
      const chips = [...((/KIND_CHIPS: string\[\] = \[([^\]]*)\]/.exec(alerts) || [])[1] || '').matchAll(/'([a-z0-9_]+)'/g)].map((m) => m[1]);
      if (alerts && chips.indexOf(K) < 0) errs.push(`Alerts.tsx KIND_CHIPS must carry '${K}'`);
      else if (alerts && chips.indexOf(K) !== chips.indexOf('tape_control') + 1) errs.push(`Alerts.tsx KIND_CHIPS must list '${K}' right after 'tape_control'`);
      const prefs = tryRead('src/hooks/useNotificationPrefs.ts', 'WP-B');
      if (prefs && !new RegExp(`\\b${K}\\?: boolean`).test(prefs)) errs.push(`NotificationPrefs (hooks/useNotificationPrefs.ts) must carry ${K}?: boolean`);
      const notif = tryRead('src/pages/Notifications.tsx', 'WP-B');
      const ess = notif.slice(notif.indexOf("id: 'essentials'"), notif.indexOf("id: 'trading_only'"));
      if (new RegExp(`${K}:\\s*true`).test(ess)) errs.push(`Essentials must NOT turn ${K} on — it is not in OWNER_KEEP_SET`);

      // 4. the numbers on the two surfaces he reads == the constants.
      const numErrs = (where, text, dollarsAllowed, needs) => {
        const out = [];
        for (const n of needs) if (n && !text.toLowerCase().includes(n.toLowerCase())) out.push(`${where} must say "${n}"`);
        for (const m of text.matchAll(/\$(\d+(?:\.\d+)?)([KMB]?)(?!\d)/g)) {
          const tok = m[0];
          if (m[2] ? !dollarsAllowed.includes(tok) : (minPx == null || Number(m[1]) !== minPx)) out.push(`${where} says "${tok}" — no constant carries it`);
        }
        if (topN != null) for (const m of text.matchAll(/top (\d+)/gi)) if (Number(m[1]) !== topN) out.push(`${where} says "${m[0]}" — push.PUSH_TOP_N is ${topN}`);
        if (step) for (const m of text.matchAll(/every (\d+) minutes/gi)) if (Number(m[1]) !== step) out.push(`${where} says "${m[0]}" — the crontab step is ${step}`);
        if (slot) for (const m of text.matchAll(/(\d\d:\d\d) ET push/g)) if (m[1] !== slot) out.push(`${where} says "${m[0]}" — push.SLOT_ET is ${slot}`);
        return out;
      };
      const px = minPx != null ? usd(minPx) : null;
      const nm = notif.match(new RegExp(`key: '${K}'[\\s\\S]*?' \\},\\n`));
      if (notif && !nm) errs.push(`${K} must be listed on the Notifications page — a kind the page cannot show cannot be switched on`);
      else if (nm) {
        const d = unesc(nm[0]);
        const W = `the ${K} Notifications entry`;
        for (const need of ['OFF', 'ships off', 'UNMEASURED', 'Not advice.', HIS[0]]) if (!d.includes(need)) errs.push(`${W} must say "${need}"`);
        if (BANNED.test(d)) errs.push(`${W} says the b-word or the sham word`);
        errs.push(...numErrs(W, d, pushDv != null ? [usd(pushDv)] : [],
          [px, pushDv != null ? usd(pushDv) : null, slot, topN != null ? `top ${topN}` : null]));
      }

      // 6. the ✨ entry — FIRST, his four lines verbatim, UNMEASURED, ends "Not advice.", the same numbers.
      const nf = read('src/lib/newFeatures.ts');
      const arr = nf.slice(nf.indexOf('export const NEW_FEATURES'));
      // 2026-10-19, later the same day: the 📱 gajjala phone-layout ✨ (its own block below) sits above this one —
      // the FIRST pin widened to the top two, dated.
      // 2026-10-20: the 🏛️ shareholders'-equity ✨ (its own block) sits above both — widened to the top three, dated.
      // 2026-10-20, later: the 🔄 scan-now ✨ (its own block) sits above all three — widened to the top four, dated.
      // 2026-10-20, later still: the 🚩 Gajjala lane ✨ (its own block, FIRST) sits above all four — widened to the top five, dated.
      // 2026-10-20, later again: the 🌀 VCP two-contractions ✨ (its own block, FIRST) sits above all five — widened to the top six, dated.
      // 2026-10-21: the 🛡 adopt_held served-sentence ✨ (autopilot-adopt-held-sentence-2026-10-21, its own block, FIRST) ships above — widened by one, dated (merged below with the two 🔴/🎚 pins that landed after it: +3 over the base).
      // 2026-10-21: the 🔴 Gajjala cards live ✨ and the 🎚 Tape control line ✨ (their own blocks, FIRST and SECOND) ship above all six — widened to the top nine, dated.
      // 2026-10-21, later: the 🚩 lane GG's-rules ✨ (its own block, FIRST — BUILD_SPEC19 F7) lands above the three of this morning — widened by one more, dated.
      // 2026-10-21, later still (BUILD_SPEC22 A5 / B4): the 🚩 lane GG's-words ✨ (FIRST) and the 🚩 K11 volume-floor ✨ (SECOND), each pinned in its own block, land above — widened by two, dated.
      // 2026-10-21, later again: the 🔎 Gajjala's-in-⌘K ✨ (its own block, FIRST) lands above — widened by one, dated.
      // 2026-10-21, evening: the 📬 push delivery receipts ✨ (alerts-push-delivery-receipts-2026-10-21, its own block, FIRST) lands above the 🔎 one — widened by one more, dated.
      const firstTwelve = [...arr.matchAll(/\{ id: '([^']+)'/g)].slice(0, 14).map((m) => m[1]);
      if (!firstTwelve.includes(ID)) errs.push(`the ✨ entry '${ID}' must be one of the first fourteen (found ${firstTwelve.join(', ') || 'none'})`);
      const at = arr.indexOf(`{ id: '${ID}'`);
      if (at < 0) errs.push(`newFeatures.ts lacks the '${ID}' highlight`);
      else {
        const nextAt = arr.indexOf("{ id: '", at + 1);
        const e = unesc(arr.slice(at, nextAt < 0 ? undefined : nextAt));
        const label = (/label: "([^"]*)"/.exec(e) || [])[1] || '';
        const W = 'the 🌙 ✨ entry';
        if (!e.includes("route: '/chart-maps?tab=overnight&on_sub=session'")) errs.push(`${W} must route to '/chart-maps?tab=overnight&on_sub=session'`);
        for (const h of HIS) if (!label.includes(h)) errs.push(`${W} must quote him verbatim: "${h}"`);
        if (!label.includes('UNMEASURED')) errs.push(`${W} must say UNMEASURED`);
        if (!label.endsWith('Not advice.')) errs.push(`${W} must end "Not advice."`);
        if (BANNED.test(label)) errs.push(`${W} says the b-word or the sham word`);
        errs.push(...numErrs(W, label, [uniDv, boardDv].filter((n) => n != null).map(usd),
          [px, uniDv != null ? usd(uniDv) : null, boardDv != null ? usd(boardDv) : null, slot,
           topN != null ? `top ${topN}` : null, step ? `every ${step} minutes` : null, open && close ? `${open}–${close}` : null]));
      }
      // The spec's own engine `supply_demand.bounce_room` (SESSION_OPEN, push.window_reason §3.6) is an internal module
      // name — internal identifiers keep the word (cheetah-ops); only that identifier is exempt, every other use fails.
      for (const [src, file] of [[scan, 'scan.py'], [sess, 'session.py'], [boardPy, 'board.py'], [push, 'push.py']]) {
        if (src && BANNED.test(pyNoComments(src).replace(/\bbounce_room\b/g, ''))) errs.push(`overnight/${file} says the b-word or the sham word (comments stripped)`);
      }
      if (!BANNED.test(pyNoComments('x = "a reversal bounce"').replace(/\bbounce_room\b/g, ''))) errs.push('self-test: a typed b-word in a string was not caught');

      // 5. the board + lib type no floor, no clock, no dollar threshold; they print the served lines.
      const lib = tryRead('src/lib/overnightSession.ts', 'WP-C');
      const TYPED = ['$25', '$250', '$1M', '$2 ', '20:00', '04:00', '06:45', '15 min'];
      const typedIn = (text) => TYPED.filter((t) => text.includes(t));
      for (const [src, file] of [[board, 'OvernightSessionBoard.tsx'], [lib, 'lib/overnightSession.ts']]) {
        for (const t of typedIn(src)) errs.push(`${file} types "${t}" — every floor, clock and $ figure is served by overnight/board.py`);
      }
      if (!typedIn(board + '\n{"$25K"}').length) errs.push('self-test: a typed "$25K" in the board was not caught');
      for (const [re, word] of [[/session\??\.line/, 'session.line'], [/lines\??\.counts/, 'lines.counts'],
                                [/lines\??\.price_rule/, 'lines.price_rule'], [/lines\??\.unmeasured/, 'lines.unmeasured']]) {
        if (!re.test(board)) errs.push(`OvernightSessionBoard.tsx must print the served ${word}`);
      }
      // A1/A4: a trade-based price is "indicative" and "delayed", never "live" — the FE types no "live".
      const tsNoComments = (x) => x.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '');
      for (const [src, file] of [[board, 'OvernightSessionBoard.tsx'], [lib, 'lib/overnightSession.ts']]) {
        if (/\blive\b/i.test(tsNoComments(src))) errs.push(`${file} says "live" — an overnight trade is indicative and delayed (AMENDMENTS16 A1/A4)`);
      }
      if (lib && !(/indicative/.test(lib) && /delayed/.test(lib))) errs.push('lib/overnightSession.ts srcWords must call a trade price "indicative" and "delayed" (AMENDMENTS16 A4)');
      for (const f of ['src/lib/overnightSession.ts', 'src/hooks/useOvernightSession.ts', 'src/components/OvernightTab.tsx',
                       'src/components/OvernightSessionBoard.tsx', 'src/styles/overnight.css']) {
        const s = tryRead(f, 'WP-C');
        if (s && BANNED.test(s)) errs.push(`${f} says the b-word or the sham word`);
      }
      if (!/import '\.\.\/styles\/overnight\.css'/.test(board)) errs.push("OvernightSessionBoard.tsx must import '../styles/overnight.css' (the per-component CSS precedent)");

      // 8. the doc names the stored keys.
      const DOC = '../docs/overnight/overnight_2026_10_19.md';
      if (!exists(DOC)) errs.push('docs/overnight/overnight_2026_10_19.md is missing (WP-D)');
      else {
        const doc = read(DOC);
        for (const need of ['overnight_reads', 'on_dollar', 'prior_pct', 'leveraged']) if (!doc.includes(need)) errs.push(`docs/overnight/overnight_2026_10_19.md must name "${need}"`);
      }
      return errs;
    },
  },
  {
    name: '📱 gajjala phone layout (2026-10-19)',
    file: 'src/styles/gajjala.css',
    // Ajay 2026-10-19, an iPhone 14 Pro Max screenshot of a TCRT card: "On the phone Gajjalas looks wierd and cut off can
    // you fix the UX issues I use an Iphone 14 pro max". Measured in the browser at 430 px: the card is a .cm-grid item,
    // and a grid item's default `min-width: auto` let ONE unbreakable served chip (the 549 px `flag #1 today · Business
    // Insider: …` house badge, nowrap) widen the single 1fr column to 552 px inside a 386 px board — the chart, the K-rule
    // lines and the chip row ran off the screen. Two CSS rules fix it and nothing served changes; this pins them, the
    // guard test (incl. NEGATIVES), the ✨ line with his words, and the doc section.
    checks: (css) => {
      const errs = [];
      const card = /(^|\n)\s*\.gg-card\s*\{([^}]*)\}/.exec(css);
      if (!card) errs.push('gajjala.css must keep a .gg-card rule');
      else {
        if (!/min-width:\s*0\b/.test(card[2])) errs.push('.gg-card must carry min-width: 0 — a grid item never exceeds its column');
        if (!/max-width:\s*100%/.test(card[2])) errs.push('.gg-card must carry max-width: 100%');
      }
      const chip = /\n([^{}\n]*\.gg-chip-row \.cm-badge[^{}\n]*)\{([^}]*)\}/.exec(css);
      if (!chip) errs.push('gajjala.css must un-nowrap .gg-chip-row .cm-badge (the served chips wrap instead of widening the card)');
      else {
        for (const sel of ['.gg-pot-tells .cm-badge', '.cm-tile-chips .cm-badge']) if (!chip[1].includes(sel)) errs.push(`the chip-wrap rule must also list ${sel}`);
        if (!/white-space:\s*normal/.test(chip[2])) errs.push('the chip-wrap rule must set white-space: normal');
        if (!/overflow-wrap:\s*anywhere/.test(chip[2])) errs.push('the chip-wrap rule must set overflow-wrap: anywhere');
      }
      const lines = /\n([^{}\n]*\.gg-criteria li[^{}\n]*)\{([^}]*overflow-wrap:\s*anywhere[^}]*)\}/.exec(css);
      if (!lines) errs.push('the K-rule lines (.gg-criteria li) must carry overflow-wrap: anywhere');
      else for (const sel of ['.gg-pills .gg-state', '.gg-pills .gg-variant', '.gg-pot-tile .gg-pot-kind', '.gg-plan', '.gg-line']) if (!lines[1].includes(sel)) errs.push(`the wrap-anywhere rule must list ${sel}`);
      if (!exists('src/components/GajjalaBoard.phone.test.tsx')) errs.push('GajjalaBoard.phone.test.tsx (the guard incl. NEGATIVES) is missing');
      const nf = read('src/lib/newFeatures.ts');
      const ID = 'chart-maps-gajjala-phone-layout-2026-10-19';
      if (!nf.includes(`id: '${ID}'`)) errs.push(`newFeatures.ts must carry the ✨ ${ID}`);
      if (!nf.includes('On the phone Gajjalas looks wierd and cut off')) errs.push('the ✨ line must quote his words verbatim');
      const DOC = '../docs/gajjala/gajjala_tab_2026_10_13.md';
      if (!exists(DOC) || !read(DOC).includes('Phone layout (2026-10-19)')) errs.push('docs/gajjala/gajjala_tab_2026_10_13.md must carry the "Phone layout (2026-10-19)" section');
      return errs;
    },
  },
  {
    name: "🏛️ shareholders' equity = the FILED balance sheet first (2026-10-20)",
    file: 'src/components/CompanyHeadline.tsx',
    // Ajay 2026-10-20, the SXTC card: "Share holders queirty is werong". It showed $25.69B on a $1.2M company —
    // Yahoo's `bookValue` per share ($2,480.58, stale after serial reverse splits) × today's 10.36M shares; the 20-F
    // filed 2026-07-01 says $29,707,422. BRK-B got $735T the same way (the A-share book value per share × the B-share
    // count), CDT $4.59B, NIVF $2.39B, TWG $1.13B. He reads this figure (real money): the backend serves the newest
    // FILED balance sheet through the ONE financials helper, with its period end and a served sentence; Yahoo's
    // product only as a plausible fallback; the FE prints the served words and types no formula of its own.
    checks: (head) => {
      const errs = [];
      const ID = 'sepa-headline-equity-filed-2026-10-20';
      const tryRead = (rel, who) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable (${who})`); return ''; } };
      // 1. the backend: the two functions, the dotted spelling, the two statements, the served keys, the schema bump.
      const sa = tryRead('../backend/sepa/stock_analysis.py', 'backend');
      for (const need of ['def filed_equity(', 'def pick_equity(', 'def cache_ttl_for(', 'symbols.for_massive(',
                          'statements=(MF.INCOME, MF.BALANCE)', 'timeout=HELPER_TIMEOUT_SEC', 'equity_attributable_to_parent',
                          '{"status": "skipped"} if is_etf else filed_equity(symbol)', 'financial_currency=info.get("financialCurrency")',
                          '"equity_source": equity["source"]', '"equity_status": equity["status"]', '"equity_as_of": equity["as_of"]',
                          '"equity_filed": equity["filed"]', '"equity_period": equity["period"]', '"equity_note": equity["note"]',
                          'EQUITY_IMPLAUSIBLE_CAP_MULT = 20', 'UNAVAILABLE_TTL_SEC = 300', 'HELPER_TIMEOUT_SEC = 6.0',
                          '_cache_put(sym, payload, ttl_sec=cache_ttl_for(payload))',
                          'fundamental_panel(sym, is_etf=bool(etf and etf.get("is_etf")))']) {
        if (!sa.includes(need)) errs.push(`stock_analysis.py must carry ${need}`);
      }
      const sv = /^SCHEMA_VERSION = (\d+)/m.exec(sa);
      if (!sv || Number(sv[1]) < 5) errs.push('stock_analysis.SCHEMA_VERSION must be ≥ 5 so cached v4 products recompute');
      const ce = tryRead('../backend/sepa/card_enrichment.py', 'backend');
      for (const k of ['"equity_source"', '"equity_status"', '"equity_as_of"', '"equity_note"']) if (!ce.includes(k)) errs.push(`card_enrichment._extract_headline must pass ${k}`);
      for (const need of ['def _headline_current(', 'def _cacheable(', 'and _headline_current(doc)', 'coll is not None and _cacheable(headline)']) {
        if (!ce.includes(need)) errs.push(`card_enrichment.py must carry ${need} (the 24h chip cache: recompute pre-fix rows, never cache an outage build)`);
      }
      if (!exists('../backend/tests/test_fundamental_headline_equity_2026_10_20.py')) errs.push('the backend test (incl. NEGATIVES) is missing');
      // 2. the FE: the served words, the as-of under the figure, no formula of its own outside the served-note fallback.
      for (const need of ['equity_note', 'equity_source', 'equity_as_of', 'cm-headline__sub', 'cm-equity-note']) {
        if (!head.includes(need)) errs.push(`CompanyHeadline.tsx must reference ${need}`);
      }
      const formula = 'book value per share × shares outstanding';
      const nForm = head.split(formula).length - 1;
      if (nForm !== 1) errs.push(`CompanyHeadline.tsx must type the old formula exactly once, as the fallback when no equity_note is served (found ${nForm})`);
      if (head.indexOf('{h?.equity_note') < 0 || head.indexOf('{h?.equity_note') > head.indexOf(formula)) errs.push('CompanyHeadline.tsx: the served equity_note must be checked (in the JSX) before the formula fallback');
      const sap = tryRead('src/components/StockAnalysisPanel.tsx', 'FE');
      if (!sap.includes('h.equity_note')) errs.push('StockAnalysisPanel.tsx must print the served equity_note');
      if (sap.split(formula).length - 1 !== 1) errs.push('StockAnalysisPanel.tsx must type the old formula exactly once, as the fallback');
      const chips = tryRead('src/components/CardEnrichmentChips.tsx', 'FE');
      if (!chips.includes('equity_note')) errs.push('CardEnrichmentChips.tsx must put the served equity_note on the 🏛️ hover');
      const hook = tryRead('src/hooks/useCardEnrichment.ts', 'FE');
      for (const k of ['equity_source', 'equity_as_of', 'equity_note']) if (!hook.includes(k)) errs.push(`useCardEnrichment.ts headline type must carry ${k}`);
      if (!tryRead('src/styles.css', 'FE').includes('.cm-headline__sub')) errs.push('styles.css must style .cm-headline__sub');
      if (!exists('src/components/CompanyHeadline.equity.test.tsx')) errs.push('CompanyHeadline.equity.test.tsx (incl. NEGATIVES) is missing');
      // 3. the ✨ line with his words, and the doc.
      const nf = read('src/lib/newFeatures.ts');
      if (!nf.includes(`id: '${ID}'`)) errs.push(`newFeatures.ts must carry the ✨ ${ID}`);
      if (!nf.includes('Share holders queirty is werong')) errs.push('the ✨ line must quote his words verbatim');
      const DOC = '../docs/sepa/fundamentals_headline.md';
      if (!exists(DOC) || !read(DOC).includes('2026-10-20')) errs.push('docs/sepa/fundamentals_headline.md must carry the 2026-10-20 section');
      return errs;
    },
  },
  {
    name: '🔄 Gajjala scan-now answers every tap (2026-10-20)',
    file: 'src/components/GajjalaBoard.tsx',
    // Ajay 2026-10-20, a screenshot of the 🔄 button on Gajjala's: "This can button has been unresponsive for me". The api
    // answered every tap 200 (24 POSTs that morning) — the board printed nothing for `reused` when the pass was the one on
    // screen and for `closed`, nothing for a non-ok answer, and only dimmed (`disabled`) while a pass ran. Frontend only.
    // Pins: the served line for every plan-less answer, keyed on the GET sequence (a read already in flight never clears
    // it; no FE timer), aria-busy + disabled while the POST is out, the served `detail` on a non-ok answer (404 → nothing),
    // the pulse rule (still under reduced motion), the tests incl. NEGATIVES, the ✨ FIRST with his words, the doc section.
    checks: (src) => {
      const errs = [];
      for (const need of [
        'const [posting, setPosting] = useState(false);',
        'const [scanErr, setScanErr] = useState<string | null>(null);',
        'const noteSeq = useRef<number | null>(null);',
        'disabled={scanning || posting}',
        "aria-busy={posting ? 'true' : undefined}",
        'data-testid="gg-scan-err"',
        'if (resp.state !== \'refused\' && text) { noteSeq.current = seq.current; setReusedText(text); }',
        'if (noteSeq.current != null && boardSeq > noteSeq.current) { noteSeq.current = null; setReusedText(null); }',
        "detail = r.status !== 404 && typeof d === 'string' && d.trim() ? d : null;",
        'if (failed || !resp || typeof resp !== \'object\') { setScanResp(null); return; }',
      ]) if (!src.includes(need)) errs.push(`GajjalaBoard.tsx must carry: ${need}`);
      if (/setTimeout\([^;]*(setReusedText|setScanErr)/.test(src)) errs.push('the served answer line must not be cleared by an FE timer (no FE number) — it lives until the next board read or the next tap');
      const css = read('src/styles/gajjala.css');
      if (!/\.gg-rescan\[aria-busy="true"\]\s*\{\s*animation:\s*gg-rescan-pulse/.test(css)) errs.push('gajjala.css must pulse .gg-rescan[aria-busy="true"]');
      if (!/@keyframes gg-rescan-pulse/.test(css)) errs.push('gajjala.css must define @keyframes gg-rescan-pulse');
      if (!/prefers-reduced-motion: reduce\)\s*\{\s*\.gg-rescan\[aria-busy="true"\]\s*\{\s*animation: none/.test(css)) errs.push('the pulse must stop under prefers-reduced-motion');
      const t = read('src/components/GajjalaBoard.scan.test.tsx');
      for (const name of [
        'reused for the pass on screen → the served line shows at once, no extra GET, and goes on the first board read started after it',
        'closed → the served closed line, no poll, not the error class',
        'NEGATIVE: an answer without a served text prints no line, never "undefined"',
        'the button is disabled and aria-busy while the POST is out',
        'a non-ok answer with a served detail → the detail line (error class); NEGATIVE: a 404 or a non-string detail prints nothing',
        'a second tap replaces the line with the new answer; a later failed answer clears it',
        'the line stays (the in-flight read never clears it)',
        'nothing shown, no poll, the button idle again',
      ]) if (!t.includes(name)) errs.push(`GajjalaBoard.scan.test.tsx must keep the test "${name}"`);
      const nf = read('src/lib/newFeatures.ts');
      const ID = 'chart-maps-gajjala-scan-now-2026-10-20';
      const arr = nf.slice(nf.indexOf('export const NEW_FEATURES'));
      // 2026-10-20, later: the 🚩 Gajjala lane ✨ (its own block) ships above this one — the FIRST pin widened to the top two, dated.
      // 2026-10-20, later again: the 🌀 VCP two-contractions ✨ (its own block, FIRST) ships above both — widened to the top three, dated.
      // 2026-10-21: the 🛡 adopt_held served-sentence ✨ (autopilot-adopt-held-sentence-2026-10-21, its own block, FIRST) ships above — widened by one, dated (merged below with the two 🔴/🎚 pins that landed after it: +3 over the base).
      // 2026-10-21: the 🔴 Gajjala cards live ✨ and the 🎚 Tape control line ✨ (their own blocks, FIRST and SECOND) ship above all three — widened to the top six, dated.
      // 2026-10-21, later: the 🚩 lane GG's-rules ✨ (its own block, FIRST — BUILD_SPEC19 F7) lands above the three of this morning — widened by one more, dated.
      // 2026-10-21, later still (BUILD_SPEC22 A5 / B4): the 🚩 lane GG's-words ✨ (FIRST) and the 🚩 K11 volume-floor ✨ (SECOND), each pinned in its own block, land above — widened by two, dated.
      // 2026-10-21, later again: the 🔎 Gajjala's-in-⌘K ✨ (its own block, FIRST) lands above — widened by one, dated.
      // 2026-10-21, evening: the 📬 push delivery receipts ✨ (alerts-push-delivery-receipts-2026-10-21, its own block, FIRST) lands above the 🔎 one — widened by one more, dated.
      const firstNine = [...arr.matchAll(/\{ id: '([^']+)'/g)].slice(0, 11).map((m) => m[1]);
      if (!firstNine.includes(ID)) errs.push(`the ✨ ${ID} must be one of the first eleven (found ${firstNine.join(', ') || 'none'})`);
      const at = arr.indexOf(`{ id: '${ID}'`);
      const nextAt = at < 0 ? -1 : arr.indexOf("{ id: '", at + 1);
      const e = at < 0 ? '' : arr.slice(at, nextAt < 0 ? undefined : nextAt);
      const label = (/label: "([^"]*)"/.exec(e) || [])[1] || '';
      if (!label.includes('This can button has been unresponsive for me')) errs.push('the ✨ label must quote his words verbatim');
      if (!label.endsWith('Not advice.')) errs.push('the ✨ label must end "Not advice."');
      if (/\d/.test(label)) errs.push('the ✨ label types a number — nothing here is measured, nothing counted changed');
      if (/b[o]unce|enterable/i.test(label)) errs.push('the ✨ label says the b-word or the sham word');
      if (!/route: '\/chart-maps\?tab=gajjala/.test(e)) errs.push('the ✨ must route to the Gajjala tab');
      const DOC = '../docs/gajjala/gajjala_tab_2026_10_13.md';
      if (!exists(DOC) || !read(DOC).includes('## 🔄 Scan now answers every tap (2026-10-20)')) errs.push('docs/gajjala/gajjala_tab_2026_10_13.md must carry the "🔄 Scan now answers every tap (2026-10-20)" section');
      return errs;
    },
  },
  {
    name: '🚫 Gajjala no-risk A+ · one price grid (2026-10-20)',
    file: 'src/lib/gajjala.ts',
    // Measured in the live Mongo 2026-10-20: the pushed A+ GG:2026-10-20|MMA|kiss_fly carried trigger = stop (risk 0). Nothing
    // rounded it — a one-print name; the kiss bar was one trade with no range. Pinned: (1) the card's ggPx mirrors the broker grid
    // constants in backend/trading/broker_alpaca.py and GajjalaBoard prints trigger / stop through it, never pxText / toFixed;
    // (2) the backend refuses a no-risk break at the detector (ledger.plan_of) and at the push gate (COUNT_KEYS "no_risk", right
    // before "broker_flagged"); (3) /alerts words the refusal; (4) tab._px sits on round_price / price_decimals; (5) the ✨ label
    // types no digit; (6) the doc carries the dated section; (7) the tests exist.
    checks: (lib) => {
      const errs = [];
      const tryRead = (rel, who) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable (${who})`); return ''; } };
      const BWORD = /boun/i;

      // 1. the grid, mirrored once and pinned to the broker module's constants
      const py = tryRead('../backend/trading/broker_alpaca.py', 'the broker grid');
      const pyNum = (name) => {
        const m = new RegExp(`^${name}\\s*=\\s*(-?\\d+(?:\\.\\d+)?)\\b`, 'm').exec(py);
        if (py && !m) errs.push(`broker_alpaca.py must define ${name} = <number> at column 0`);
        return m ? Number(m[1]) : null;
      };
      const LINE = pyNum('SUB_DOLLAR_LINE'), UNDER = pyNum('SUB_DOLLAR_DECIMALS'), OVER = pyNum('DOLLAR_DECIMALS');
      const grid = /export const GG_PX_GRID = \{ line: ([0-9.]+), under: (\d+), atOrOver: (\d+) \} as const;/.exec(lib);
      if (!grid) errs.push('lib/gajjala.ts must export GG_PX_GRID = { line, under, atOrOver } as const');
      else {
        if (LINE !== null && Number(grid[1]) !== LINE) errs.push(`GG_PX_GRID.line ${grid[1]} ≠ broker_alpaca.SUB_DOLLAR_LINE ${LINE}`);
        if (UNDER !== null && Number(grid[2]) !== UNDER) errs.push(`GG_PX_GRID.under ${grid[2]} ≠ broker_alpaca.SUB_DOLLAR_DECIMALS ${UNDER}`);
        if (OVER !== null && Number(grid[3]) !== OVER) errs.push(`GG_PX_GRID.atOrOver ${grid[3]} ≠ broker_alpaca.DOLLAR_DECIMALS ${OVER}`);
      }
      if (!/export function ggPx\(p: unknown\): string \| null/.test(lib)) errs.push('lib/gajjala.ts must export ggPx(p: unknown): string | null');
      const board = tryRead('src/components/GajjalaBoard.tsx', 'the card');
      if (board && !board.includes('const trig = ggPx(read.trigger)')) errs.push('GajjalaBoard must print the trigger through ggPx');
      if (board && !board.includes('const stop = ggPx(read.stop)')) errs.push('GajjalaBoard must print the stop through ggPx');
      if (/pxText\(/.test(board)) errs.push('GajjalaBoard calls pxText( — the house 3-decimal print blurs a sub-dollar trigger and stop');
      if (/toFixed\(/.test(board)) errs.push('GajjalaBoard types a toFixed( — every number on the card is served or on the grid');

      // 2. the backend: the detector rule and the push gate
      const det = tryRead('../backend/chart_maps/gajjala/detectors.py', 'the detectors');
      for (const need of ['from chart_maps.gajjala.ledger import PLANS, plan_of', 'NO_RISK_REASON = "no risk', 'NO_PLAN_REASON = "no plan',
                          'plan = plan_of(trigger, stop)[0]', 'return _invalid(r, NO_RISK_REASON if plan == PLANS[2] else NO_PLAN_REASON)']) {
        if (det && !det.includes(need)) errs.push(`detectors.py must carry ${need}`);
      }
      const al = tryRead('../backend/chart_maps/gajjala/alerts.py', 'the push gate');
      const keys = (/^COUNT_KEYS = \(([\s\S]*?"broker_flagged")\)/m.exec(al) || [])[1] || '';
      const keyList = [...keys.replace(/#[^\n]*/g, '').matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
      if (al && (keyList.indexOf('no_risk') !== keyList.length - 2 || keyList[keyList.length - 1] !== 'broker_flagged')) {
        errs.push(`alerts.COUNT_KEYS must carry "no_risk" right before "broker_flagged" (found …${keyList.slice(-3).join(', ')})`);
      }
      if (al && !al.includes('state = "no_risk"')) errs.push('alerts.run_pass must refuse a no-risk A+ with state = "no_risk"');
      const tab = tryRead('../backend/chart_maps/gajjala/tab.py', 'the formatter');
      if (tab && !/def _px\(x\) -> str:[\s\S]*?v = round_price\(v\)\s*\n\s*n = price_decimals\(v\)/.test(tab)) errs.push('tab._px must sit on trading.broker.round_price / price_decimals');
      if (tab && !tab.includes('or the trigger would equal the stop (a reference bar with no ')) errs.push('tab.count_legend invalid text must name the no-risk cause');

      // 3. /alerts words the refusal
      const alerts = tryRead('src/pages/Alerts.tsx', 'the alerts page');
      const chip = /case 'no_risk':\s*return `\$\{n\} ([^`]*)`;/.exec(alerts);
      if (!chip) errs.push("Alerts.tsx gajjalaChipText must carry case 'no_risk'");
      else if (!/no risk/.test(chip[1]) || BWORD.test(chip[1])) errs.push(`Alerts.tsx no_risk chip must say "no risk" without the b-word (found "${chip[1]}")`);
      const gk = (/const GAJJALA_KEYS = \[([\s\S]*?)\];/.exec(alerts) || [])[1] || '';
      if (!/'no_risk'/.test(gk)) errs.push("Alerts.tsx GAJJALA_KEYS must list 'no_risk' (a key not listed never prints)");

      // 4. the ✨ line: present, routed to the kiss_fly sub, no digit typed
      const nf = tryRead('src/lib/newFeatures.ts', 'the ✨ line');
      const ent = /\{ id: 'chart-maps-gajjala-no-risk-price-grid-2026-10-20', addedAt: '2026-10-20', route: '\/chart-maps\?tab=gajjala&sub=kiss_fly',\s*label: "([^"]*)" \}/.exec(nf);
      if (!ent) errs.push("newFeatures.ts must carry chart-maps-gajjala-no-risk-price-grid-2026-10-20 routed to /chart-maps?tab=gajjala&sub=kiss_fly");
      else {
        if (/\d/.test(ent[1])) errs.push('the ✨ label types a digit — every number is a backend constant, none belongs in the label');
        for (const need of ['no risk', 'MMA', 'never pushed', 'Not advice.']) if (!ent[1].includes(need)) errs.push(`the ✨ label must carry "${need}"`);
        if (BWORD.test(ent[1])) errs.push('the ✨ label says the b-word');
      }

      // 5. the doc and the tests
      const doc = tryRead('../docs/gajjala/gajjala_tab_2026_10_13.md', 'the tab doc');
      if (doc && !doc.includes('## 🚫 A no-risk A+ never rings · one price grid (2026-10-20)')) errs.push('docs/gajjala/gajjala_tab_2026_10_13.md must carry the dated 2026-10-20 section');
      if (!exists('../backend/tests/test_gajjala_no_risk_2026_10_20.py')) errs.push('backend/tests/test_gajjala_no_risk_2026_10_20.py is missing');
      const lt = tryRead('src/lib/gajjala.test.ts', 'the lib test');
      if (lt && !/describe\('ggPx — the broker price grid'/.test(lt)) errs.push("lib/gajjala.test.ts must carry describe('ggPx — the broker price grid') incl. the $4.46 NEGATIVE");
      if (lt && !lt.includes("[4.46, '4.46']")) errs.push('lib/gajjala.test.ts must pin the NEGATIVE: a $4.46 level prints two decimals');
      if (!BWORD.test('a bounce') || !/\d/.test('a 4')) errs.push('self-test: the b-word / digit regexes do not catch');
      return errs;
    },
  },
  {
    name: '🚩 Auto-Pilot Gajjala lane (2026-10-20)',
    file: 'src/pages/Trading.tsx',
    // Ajay 2026-10-20: "in the autopilot can you stop rest of the strategies and only use the Gajjalas strategies please."
    // BUILD_SPEC17: a NEW paper lane (backend/trading/gajjala_entry.py) trades the 🚩 A+ ENTRY alerts that reached his
    // phone with GG's trade math; the 🚩 Gajjala tab on /trading prints only served strings. Pinned: the tab is wired,
    // its three writes, its silence on numbers / books / the b-word, the journal row, the backend anchor strings (⚓,
    // §3.1–3.5), the ✨ line (every number a backend constant) and the doc. UNMEASURED — the study read no edge.
    // UPDATED 2026-10-21 to v2's constants (BUILD_SPEC19 F6 / D3 / D4 / D7, Ajay "Follow full Gajjala … implement them
    // exactly"): GAJJALA_RISK_PCT is GG's 0.25 (pinned with its GG cite in the block "🚩 Gajjala lane: GG's rules
    // (2026-10-21)"), the day cap is off (None), the +0.5% chase limit / the +1R target / thin_r / stale / dead are
    // gone (their v2 counterparts: a market entry, no take-profit, the missed bound, the SKIP_KINDS below), the floors
    // default OFF. What still holds is pinned as before.
    checks: (tr) => {
      const errs = [];
      const HIS = 'in the autopilot can you stop rest of the strategies and only use the Gajjalas strategies please.';
      const tryRead = (rel, who) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable (${who})`); return ''; } };
      const unesc = (x) => x.replace(/\\u\{([0-9A-Fa-f]+)\}/g, (_m, h) => String.fromCodePoint(parseInt(h, 16)));

      // 1. Trading.tsx: import, View, VIEWS (right after Dashboard), parseView, the mount.
      if (!/import\s*\{\s*GajjalaLaneTab\s*\}\s*from\s*'\.\.\/components\/GajjalaLaneTab'/.test(tr)) errs.push("Trading.tsx must import { GajjalaLaneTab } from '../components/GajjalaLaneTab'");
      if (!/export\s+type\s+View\s*=[^;]*'gajjala'/.test(tr)) errs.push("Trading.tsx View type must carry 'gajjala'");
      const viewsBody = (/export const VIEWS:[^=]*=\s*\[([\s\S]*?)\n\];/.exec(tr) || [])[1] || '';
      const viewKeys = [...viewsBody.replace(/\/\/[^\n]*/g, '').matchAll(/key:\s*'([a-z_]+)'/g)].map((m) => m[1]);
      if (viewKeys[0] !== 'dashboard' || viewKeys[1] !== 'gajjala') errs.push(`VIEWS must list 'gajjala' right after 'dashboard' (found ${viewKeys.join(', ') || 'none'})`);
      if (!/\{\s*key:\s*'gajjala'\s*,\s*label:\s*'🚩 Gajjala'\s*\}/.test(viewsBody)) errs.push("VIEWS must carry { key: 'gajjala', label: '🚩 Gajjala' }");
      const pv = (/export function parseView[\s\S]*?\n\}/.exec(tr) || [''])[0];
      if (!/v\s*===\s*'gajjala'/.test(pv)) errs.push("parseView must accept 'gajjala' (the ✨ route /trading?view=gajjala)");
      if (!/view\s*===\s*'gajjala'\s*&&\s*<GajjalaLaneTab\s+onChanged=\{refresh\}\s*\/>/.test(tr)) errs.push("Trading.tsx must mount <GajjalaLaneTab onChanged={refresh} /> on view === 'gajjala'");

      // 2. the tab: one GET, the two switches' four bodies, the close URL, the confirm dialogs, the poll.
      const tab = tryRead('src/components/GajjalaLaneTab.tsx', 'WP-B');
      for (const need of ['`${API}/trading/gajjala`', "credentials: 'include'", 'export const POLL_MS = 60_000', 'clearInterval(t)',
                          "{ gajjala_entry: false }", "{ gajjala_entry: true }", "{ gajjala_floors: false }", "{ gajjala_floors: true }",
                          '`/trading/gajjala/close/${encodeURIComponent(row.symbol)}`', 'aria-label={`Close ${closing} Gajjala?`}',
                          's.floors_off_confirm_text', "row.floors === 'gg'", 'row.broker_text', 'row.closable === true',
                          'row.fate_text', 'row.pnl_text', 's.caps_text', 's.floors_text', 's.floors_flip', 's.skipped_floor_text',
                          's.unmeasured_text', 's.streak_text', 's.track_record_url', 's.empty_today_text', 's.live_text',
                          's.disabled_text', 'data.journal?.text', 'rules.map(']) {
        if (tab && !tab.includes(need)) errs.push(`GajjalaLaneTab.tsx must carry ${need}`);
      }
      if (tab && !/<Link to=\{s\.track_record_url\}/.test(tab)) errs.push('GajjalaLaneTab.tsx must link the 🏁 Track record with a router <Link> (no full-page reload)');
      if (tab && !/<Link to=\{row\.url\}>/.test(tab)) errs.push('GajjalaLaneTab.tsx must link each symbol to its served row.url with a router <Link>');
      if (!exists('src/components/GajjalaLaneTab.test.tsx')) errs.push('GajjalaLaneTab.test.tsx (incl. NEGATIVES) is missing');

      // 3. the tab types no book, no b-word, and none of the lane's numbers (they are served).
      const BOOK = /TLSW|TTLAC|Minervini p\./;
      const BWORD = /boun/i;
      // 2026-10-21: v2's GAJJALA_RISK_PCT (0.25%) joins the typed-number guard (BUILD_SPEC19 D14 — the FE types no number).
      const TYPED = /15:55|0\.5%|0\.25%|09:45/;
      if (BOOK.test(tab)) errs.push('GajjalaLaneTab.tsx names a book — the lane is owner rules, no book');
      if (BWORD.test(tab)) errs.push('GajjalaLaneTab.tsx says the b-word — "reversal", never the b-word');
      const typed = tab.match(TYPED);
      if (typed) errs.push(`GajjalaLaneTab.tsx types "${typed[0]}" — every number, time and percent is served by trading/gajjala_entry.py`);
      if (!TYPED.test(`${tab}\nflat by 15:55`) || !TYPED.test(`${tab}\nrisk 0.25% a trade`) || !BWORD.test('a bounce') || !BOOK.test('TLSW p.1')) errs.push('self-test: a typed 15:55 / 0.25% / b-word / book name was not caught');

      // 4. the journal row: 🚩 first, named, owner rules + UNMEASURED.
      const jbs = tryRead('src/components/JournalByStrategy.tsx', 'WP-B');
      const order = (/export const STRATEGY_ORDER:[^=]*=\s*\[([^\]]*)\]/.exec(jbs) || [])[1] || '';
      if (((/'([a-z_]+)'/.exec(order)) || [])[1] !== 'gajjala') errs.push("JournalByStrategy STRATEGY_ORDER must lead with 'gajjala'");
      if (!/gajjala:\s*\{\s*glyph:\s*'🚩',\s*label:\s*'Gajjala',\s*blurb:\s*'The 🚩 Gajjala lane — his A\+ ENTRY alerts on paper \(owner rules, UNMEASURED\)\.'/.test(jbs)) {
        errs.push("JournalByStrategy STRATEGY_META must carry gajjala: { glyph: '🚩', label: 'Gajjala', blurb: 'The 🚩 Gajjala lane — … (owner rules, UNMEASURED).' }");
      }
      const sk = jbs.indexOf('export type StrategyKey');
      if (sk < 0 || !/'gajjala'/.test(jbs.slice(sk, jbs.indexOf(';', sk)))) errs.push("StrategyKey must carry 'gajjala'");

      // 5. the backend anchor strings (⚓) the tab and the ✨ depend on.
      const gl = tryRead('../backend/trading/gajjala_entry.py', 'WP-A');
      const num = (name) => {
        const m = new RegExp(`^${name}\\s*=\\s*(-?\\d+(?:\\.\\d+)?)\\b`, 'm').exec(gl);
        if (gl && !m) errs.push(`gajjala_entry.py must define ${name} = <number> at column 0`);
        return m ? Number(m[1]) : null;
      };
      // 2026-10-21 (v2): RISK = GG's 0.25 (value + cite pinned in the GG's-rules block); NOTIONAL / MAX_OPEN / cut-off /
      // flatten / rounding still hold. GAJJALA_MAX_ENTRIES_PER_DAY is OFF (D3: None or gone — never a number again without
      // his call). The stale age (SIGNAL_MAX_AGE_MIN), the chase limit (CHASE_PCT) and the limit's fill wait are v1-only
      // (D7: market at the break) — no longer pinned; their counterpart is GAJJALA_MISSED_R (MINE — HIS CALL #9) and the
      // TE.enter( call below (no limit at E, no target).
      const RISK = num('GAJJALA_RISK_PCT');
      num('GAJJALA_MAX_NOTIONAL_PCT');
      if (gl && /^GAJJALA_MAX_ENTRIES_PER_DAY\s*=\s*-?\d/m.test(gl)) errs.push('gajjala_entry.py GAJJALA_MAX_ENTRIES_PER_DAY must be None (or gone) in v2 — GG has no day cap (BUILD_SPEC19 D3)');
      num('GAJJALA_MAX_OPEN');
      num('GAJJALA_MAX_ROUND_R_PCT');
      num('GAJJALA_MISSED_R');
      num('GAJJALA_ENTRY_CUTOFF_BEFORE_CLOSE_MIN');
      const FLAT_MIN = num('GAJJALA_FLATTEN_BEFORE_CLOSE_MIN');
      for (const need of ['from trading.broker import BrokerError, get_broker, round_price, MIN_STOP_GAP_USD',
                          'STRATEGY = "gajjala"', 'LANE_COLL = "gajjala_lane"']) {
        if (gl && !gl.includes(need)) errs.push(`gajjala_entry.py must carry ${need}`);
      }
      // 2026-10-21 (v2): the +1R target (R_MULT) and the thin-R skip (MIN_R_PCT) are gone from the lane (D7 / D8d) — the
      // 🏁 grader keeps GC.LEDGER_R_MULT; the window still opens at the ledger's 09:45.
      for (const line of ['WINDOW_OPEN_ET = GC.LEDGER_FILL_FROM_ET']) {
        if (gl && !new RegExp(`^${line.replace(/\./g, '\\.')}\\b`, 'm').test(gl)) errs.push(`gajjala_entry.py must take its number by name at column 0: ${line}`);
      }
      const skipKinds = (/^SKIP_KINDS = \(([\s\S]*?)\)/m.exec(gl) || [])[1];
      if (gl && skipKinds == null) errs.push('gajjala_entry.py must define SKIP_KINDS = (…) at column 0');
      else if (gl) {
        const kinds = [...skipKinds.matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
        // stale / thin_r / dead are no longer produced in v2 (D7); older rows may still carry them, so they are not pinned
        // absent here — the backend tests (test_gajjala_lane_gg_rules.py) own "never produced".
        for (const need of ['no_plan', 'no_risk', 'missed', 'rounding', 'broker_gap', 'size', 'held', 'cap_open', 'floor', 'disarmed', 'blocked', 'never_triggered', 'cooldown', 'halt']) {
          if (!kinds.includes(need)) errs.push(`gajjala_entry.py SKIP_KINDS must carry "${need}" (BUILD_SPEC19 D7)`);
        }
      }
      // FIXED 2026-10-21 (critic): the FIRST TE.enter( in gajjala_entry.py is now the breakeven ADD — the ENTRY call is
      // found by its own anchor (order_intent="gg-" + setup), never by indexOf('TE.enter(').
      const ENTRY_ANCHOR = 'order_intent="gg-" + setup';
      const teCalls = (src) => {
        const found = [];
        for (let at = src.indexOf('TE.enter('); at >= 0; at = src.indexOf('TE.enter(', at + 1)) {
          let depth = 0, end = at + 'TE.enter'.length;
          for (; end < src.length; end++) {
            if (src[end] === '(') depth++;
            else if (src[end] === ')') { depth--; if (depth === 0) break; }
          }
          found.push(src.slice(at, end + 1));
        }
        return found;
      };
      const entryCalls = teCalls(gl).filter((c) => c.includes(ENTRY_ANCHOR));
      if (teCalls('TE.enter(a, order_intent="gg-add-" + setup)\nTE.enter(b, order_intent="gg-" + setup)').filter((c) => c.includes(ENTRY_ANCHOR)).join() !== 'TE.enter(b, order_intent="gg-" + setup)') errs.push('self-test: the entry TE.enter( was not found by its anchor behind an add call');
      if (gl && teCalls(gl).length === 0) errs.push('gajjala_entry.py must enter through the ONE chokepoint TE.enter(…)');
      else if (gl && entryCalls.length !== 1) errs.push(`gajjala_entry.py must carry exactly ONE TE.enter( call with ${ENTRY_ANCHOR} (the lane's entry) — found ${entryCalls.length}`);
      else if (gl) {
        const call = entryCalls[0];
        // 2026-10-21 (v2): 'target_price=TP' is gone (no target — pinned in the GG's-rules block); the entry is a market
        // order (D7) — never the v1 limit at E.
        for (const need of ['strategy=STRATEGY', 'sizing=', 'floors=', 'tif="day"', 'order_intent="gg-" + setup']) {
          if (!call.includes(need)) errs.push(`the TE.enter( call must carry ${need}`);
        }
        if (/limit_price=(?!None\b)/.test(call)) errs.push('the TE.enter( call must not carry a limit price — v2 enters at market (BUILD_SPEC19 D7); limit_price=None only');
      }
      const ee = tryRead('../backend/trading/exit_engine.py', 'WP-A');
      // 2026-10-21 (v2, BUILD_SPEC19 D1): the floors switch defaults OFF for GG's lane (True = the house floors apply).
      for (const need of ['"gajjala_entry": bool(doc.get("gajjala_entry", True)),', '"gajjala_floors": bool(doc.get("gajjala_floors", False)),',
                          '"last_gajjala_disabled_day": doc.get("last_gajjala_disabled_day"),',
                          'out["gajjala_lane"] = gajjala_entry.status_block(cfg)']) {
        if (ee && !ee.includes(need)) errs.push(`exit_engine.py must carry ${need}`);
      }
      const RUN = 'summary["gajjala_lane"] = gajjala_entry.run(broker=broker, cfg=get_config())';
      const runAt = ee.indexOf(RUN);
      const hpAt = ee.indexOf('hot_pullback_entry.run(');
      if (ee && runAt < 0) errs.push(`exit_engine.py tick must carry ${RUN}`);
      else if (ee && !(hpAt >= 0 && hpAt < runAt)) errs.push('exit_engine.py: the 🚩 step (n) must run after hot_pullback_entry.run( (step m)');
      const api = tryRead('../backend/trading/api.py', 'WP-A');
      for (const need of ['for lane_key in ("gajjala_entry", "gajjala_floors", "hot_pullback_entry"):',
                          '@router.get("/gajjala")', '@router.post("/gajjala/close/{symbol}")']) {
        if (api && !api.includes(need)) errs.push(`api.py must carry ${need}`);
      }
      const en = tryRead('../backend/trading/entries.py', 'WP-A');
      for (const need of ['STRATEGIES = ("minervini", "demand_zone", "breakout", "catalyst", "gajjala", "manual")',
                          'FLOOR_WAIVER_STRATEGIES = ("gajjala",)']) {
        if (en && !en.includes(need)) errs.push(`entries.py must carry ${need}`);
      }
      const ba = tryRead('../backend/trading/broker_alpaca.py', 'WP-A');
      for (const [re, line] of [[/^SUB_DOLLAR_DECIMALS = 4\b/m, 'SUB_DOLLAR_DECIMALS = 4'], [/^MIN_STOP_GAP_USD = 0\.01\b/m, 'MIN_STOP_GAP_USD = 0.01']]) {
        if (ba && !re.test(ba)) errs.push(`broker_alpaca.py must carry ${line} at column 0`);
      }

      // 6. the v1 ✨ entry: present, routed to the tab, his words verbatim, UNMEASURED, ends "Not advice.".
      // UPDATED 2026-10-21 (BUILD_SPEC19 F6 / F7): the 🚩 lane GG's-rules ✨ (its own block, FIRST) ships above the 🌀 VCP
      // ✨ and this one — the pin widened to the top three, dated. The v1 label is the dated 2026-10-20 history entry: its
      // numbers were v1's constants (0.5% risk, the day cap, the +1R target), which v2 changed — so they are no longer
      // re-read against the constants here; the FIRST ✨ (v2) types no number outside his quote, pinned in its own block.
      const ID = 'autopilot-gajjala-lane-2026-10-20';
      const nf = read('src/lib/newFeatures.ts');
      const arr = nf.slice(nf.indexOf('export const NEW_FEATURES'));
      // 2026-10-21: the 🛡 adopt_held served-sentence ✨ (autopilot-adopt-held-sentence-2026-10-21, its own block, FIRST) ships above — widened by one, dated (merged below with the two 🔴/🎚 pins that landed after it: +3 over the base).
      // 2026-10-21: the 🔴 Gajjala cards live ✨ and the 🎚 Tape control line ✨ (their own blocks, FIRST and SECOND) ship above both — widened to the top five, dated.
      // 2026-10-21, later: the 🚩 lane GG's-rules ✨ (its own block, FIRST — BUILD_SPEC19 F7) lands above the three of this morning — widened to the top six, dated.
      // 2026-10-21, later still (BUILD_SPEC22 A5 / B4): the 🚩 lane GG's-words ✨ (FIRST) and the 🚩 K11 volume-floor ✨ (SECOND), each pinned in its own block, land above — widened by two, dated.
      // 2026-10-21, later again: the 🔎 Gajjala's-in-⌘K ✨ (its own block, FIRST) lands above — widened by one, dated.
      // 2026-10-21, evening: the 📬 push delivery receipts ✨ (alerts-push-delivery-receipts-2026-10-21, its own block, FIRST) lands above the 🔎 one — widened by one more, dated.
      const firstEight = [...arr.matchAll(/\{ id: '([^']+)'/g)].slice(0, 10).map((m) => m[1]);
      if (!firstEight.includes(ID)) errs.push(`the ✨ entry '${ID}' must be one of the first ten in NEW_FEATURES (found ${firstEight.join(', ') || 'none'})`);
      const at = arr.indexOf(`{ id: '${ID}'`);
      if (at < 0) errs.push(`newFeatures.ts lacks the '${ID}' highlight`);
      else {
        const nextAt = arr.indexOf("{ id: '", at + 1);
        const e = unesc(arr.slice(at, nextAt < 0 ? undefined : nextAt));
        const label = (/label: "([^"]*)"/.exec(e) || [])[1] || '';
        const W = 'the 🚩 ✨ entry';
        if (!e.includes("route: '/trading?view=gajjala'")) errs.push(`${W} must route to '/trading?view=gajjala'`);
        if (!label.includes(HIS)) errs.push(`${W} must quote him verbatim: "${HIS}"`);
        if (!label.includes('UNMEASURED')) errs.push(`${W} must say UNMEASURED`);
        if (!label.endsWith('Not advice.')) errs.push(`${W} must end "Not advice."`);
        if (BWORD.test(label) || BOOK.test(label)) errs.push(`${W} says the b-word or names a book`);
      }
      if (RISK == null && gl) errs.push('gajjala_entry.py GAJJALA_RISK_PCT is unreadable');
      if (FLAT_MIN == null && gl) errs.push('gajjala_entry.py GAJJALA_FLATTEN_BEFORE_CLOSE_MIN is unreadable');

      // 7. the doc: the ask verbatim, the floors his-call, UNMEASURED, the three-lane rule satisfied.
      const DOC = '../docs/trading_gajjala_lane.md';
      if (!exists(DOC)) errs.push('docs/trading_gajjala_lane.md is missing (WP-A)');
      else {
        const doc = read(DOC);
        for (const need of [HIS, 'HIS CALL #0', 'UNMEASURED', 'never add a lane without his call']) if (!doc.includes(need)) errs.push(`docs/trading_gajjala_lane.md must carry "${need}"`);
      }
      return errs;
    },
  },
  {
    name: "🚩 Gajjala lane: GG's rules (2026-10-21)",
    file: 'src/components/GajjalaLaneTab.tsx',
    // Ajay 2026-10-21, on a screenshot of the 🚩 lane's floor skips: "Is the 700 M floor by Gajjala?" / "Follow full Gajjala
    // and he doesnt care exactly about this.. Go through his rules from play book and implement them exactly". BUILD_SPEC19
    // (sources: chart_maps/gajjala/verified_rules.json + playbook.py): GG's numbers carry a "# GG" cite, the missing ones
    // are None placeholders "awaiting your number" (the rule is off while None), the house floors / earnings shield /
    // p.312 ceiling / SEPA distribution exit do not apply to his lane, no take-profit ever, management on CLOSED bars
    // only. The tab prints the served `rules` object verbatim and types no digit; the ✨ is FIRST and its only digits are
    // inside his quote. PAPER, UNMEASURED.
    // UPDATED 2026-10-21, later (BUILD_SPEC22 A5 — Ajay "keep what ever Gajjala says for these"): the four None
    // placeholders are GG's sentences now (VR 11.4 / 10.1 / 11.7) and `awaiting` is served EMPTY; this block pins the new
    // constants and their cites instead of the placeholders, and the ✨ sits in the top three (two newer ✨ above it).
    checks: (tab) => {
      const errs = [];
      const tryRead = (rel, who) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable (${who})`); return ''; } };
      const pyNoComments = (x) => x.replace(/#[^\n]*/g, '');
      // self-test: a surviving placeholder line must be caught by the NEGATIVE below.
      if (!/^(GG_[A-Z_]+)\s*=\s*None\b[^\n]*awaiting your number/m.test('X = 1\nGG_PARTIAL_R = None  # awaiting your number — R')) {
        errs.push('self-test: a `= None  # awaiting your number` placeholder line was not caught');
      }
      const HIS1 = 'Is the 700 M floor by Gajjala?';
      const HIS2 = 'Follow full Gajjala and he doesnt care exactly about this.. Go through his rules from play book and implement them exactly';
      const BWORD = /boun/i;
      const RULE_KEYS = ['entry_text', 'stop_text', 'size_text', 'manage_text', 'risk_text', 'exempt_text'];

      // 1. GG's numbers at column 0 with a GG cite on the line (VR 11.7 / 11.4 / 10.6) — never MINE.
      const gl = tryRead('../backend/trading/gajjala_entry.py', 'WP-A');
      const ggNum = (name, want) => {
        const m = new RegExp(`^${name}\\s*=\\s*(-?\\d+(?:\\.\\d+)?)\\b([^\\n]*)$`, 'm').exec(gl);
        if (!m) { if (gl) errs.push(`gajjala_entry.py must define ${name} = ${want} at column 0 (BUILD_SPEC19)`); return; }
        if (Number(m[1]) !== want) errs.push(`gajjala_entry.py ${name} is ${m[1]} — GG's number is ${want} (BUILD_SPEC19)`);
        if (!/#[^\n]*\bGG\b/.test(m[2])) errs.push(`gajjala_entry.py ${name} must carry its GG cite on the line ("# … GG …")`);
        if (/\bMINE\b/.test(m[2])) errs.push(`gajjala_entry.py ${name} is GG's number, not MINE`);
      };
      ggNum('GAJJALA_RISK_PCT', 0.25);          // VR 11.7 — he STARTS at 0.25% of the account per trade
      ggNum('GG_BE_AFTER_BARS', 3);             // VR 11.4 — "give it 15 minutes, three bars"
      ggNum('GG_REENTRY_WAIT_BARS', 2);         // VR 10.6 — "at least like couple of bars"
      ggNum('GG_DRAWDOWN_PCT', 10);             // VR 11.7 — a −10% drawdown …
      ggNum('GG_DRAWDOWN_TRADES', 5);           // … the next five trades …
      ggNum('GG_DRAWDOWN_RISK_SUM_PCT', 5);     // … ≤ −5% together
      // REWRITTEN 2026-10-21 (BUILD_SPEC22 A5 — Ajay "keep what ever Gajjala says for these"): the four `= None  # awaiting
      // your number` placeholders are gone; each is GG's sentence now. Pin the new constants with their VR cite and his
      // 2026-10-21 line, the three readings flagged HIS CALL #24 / #25 / #26, and an EMPTY awaiting list.
      const HIS_WORDS = 'keep what ever Gajjala says for these';
      ggNum('GG_PARTIAL_FRAC', 0.5);            // VR 11.4 — "peel off 1/3 or half" — half (HIS CALL #25)
      ggNum('GG_HALT_CALM_BARS', 1);            // VR 10.1 — one clean closed bar after the resume (HIS CALL #26)
      ggNum('GG_CUSHION_LOSERS', 2);            // VR 11.7 — "a cushion that survives 2 losers"
      ggNum('GG_DOUBLE_MULT', 2);               // VR 11.7 — "A+ up to double"
      const ggLine = (name, valRe, valWord, vr, hisCall) => {
        const m = new RegExp(`^${name}\\s*=\\s*${valRe}\\s+(#[^\\n]*)$`, 'm').exec(gl);
        if (!m) { if (gl) errs.push(`gajjala_entry.py must define ${name} = ${valWord} at column 0 (BUILD_SPEC22)`); return; }
        if (!/\bGG\b/.test(m[1]) || !m[1].includes(vr)) errs.push(`gajjala_entry.py ${name} must carry its GG cite "${vr}" on the line`);
        if (/\bMINE\b/.test(m[1])) errs.push(`gajjala_entry.py ${name} is GG's word, not MINE`);
        if (hisCall && !m[1].includes(hisCall)) errs.push(`gajjala_entry.py ${name} must flag ${hisCall} on the line (the lead's reading)`);
        return m[1];
      };
      for (const [name, valRe, valWord, vr, hisCall] of [
        ['GG_PARTIAL_AFTER', '"add"', '"add"', 'VR 11.4', null],
        ['GG_PARTIAL_STRENGTH', '"new_high"', '"new_high"', 'VR 11.4', 'HIS CALL #24'],
        ['GG_TRAIL_EMA_KF', 'GC\\.EMA_SLOW\\b', 'GC.EMA_SLOW (the pass\'s 21 EMA — imported, never retyped)', 'VR 11.4', null],
        ['GG_HALT_CALM_BARS', '1\\b', '1', 'VR 10.1', 'HIS CALL #26'],
        ['GG_CUSHION_LOSERS', '2\\b', '2', 'VR 11.7', null],
        ['GG_DOUBLE_MULT', '2(?:\\.0)?\\b', '2.0', 'VR 11.7', null],
        ['GG_CUSHION_PERIOD', '"month"', '"month"', 'VR 11.7', null],
      ]) {
        const c = ggLine(name, valRe, valWord, vr, hisCall);
        if (c != null && !c.includes(`Ajay 2026-10-21 "${HIS_WORDS}"`)) errs.push(`gajjala_entry.py ${name} must carry his line on the line: Ajay 2026-10-21 "${HIS_WORDS}"`);
      }
      if (gl && !/^GG_PARTIAL_FRAC\s*=[^\n]*HIS CALL #25/m.test(gl)) errs.push('gajjala_entry.py GG_PARTIAL_FRAC must flag HIS CALL #25 (1/3 vs half) on the line');
      if (gl && /^GG_TRAIL_EMA_KF\s*=\s*\d/m.test(gl)) errs.push('gajjala_entry.py GG_TRAIL_EMA_KF retypes a number — it is GC.EMA_SLOW by name');
      // NEGATIVE: the placeholders are gone — no `= None` line, no R / minutes / % stand-in under any of the old names.
      for (const name of ['GG_PARTIAL_R', 'GG_HALT_CALM_MIN', 'GG_CUSHION_DOUBLE_PCT']) {
        if (gl && new RegExp(`^${name}\\s*=`, 'm').test(gl)) errs.push(`gajjala_entry.py still defines ${name} — the placeholder is GG's sentence now (BUILD_SPEC22 A2 / A3 / A4)`);
      }
      if (gl && /^(GG_[A-Z_]+)\s*=\s*None\b[^\n]*awaiting your number/m.test(gl)) errs.push('gajjala_entry.py still carries a `= None  # awaiting your number` placeholder (BUILD_SPEC22 A5: nothing awaits)');
      // the served awaiting list is EMPTY: AWAITING is the empty tuple and the status serves it through AWAITING only.
      if (gl && !/^AWAITING: tuple = \(\)\s/m.test(gl)) errs.push('gajjala_entry.py must carry AWAITING: tuple = () — nothing awaits (BUILD_SPEC22 A5)');
      if (gl && !pyNoComments(gl).includes('"awaiting": [{"key": k, "question": q} for k, q in AWAITING')) errs.push('gajjala_entry.py rules."awaiting" must be built from AWAITING (served EMPTY)');

      // 2. the served `rules` object (D14) — every key the tab prints, and the awaiting rows' question.
      const glCode = pyNoComments(gl);
      if (gl && !/"rules":/.test(glCode)) errs.push('gajjala_entry.py status block must serve "rules"');
      for (const k of [...RULE_KEYS, 'not_built', 'awaiting', 'question']) {
        if (gl && !glCode.includes(`"${k}"`)) errs.push(`gajjala_entry.py must serve rules."${k}" (BUILD_SPEC19 D14)`);
      }

      // 3. the lane's entry: no earnings shield, the gg ceiling, no take-profit; management on closed bars only.
      // FIXED 2026-10-21 (critic): read the ENTRY call by its anchor (order_intent="gg-" + setup) — the first TE.enter( is
      // the breakeven add, so indexOf only ever checked the add. EVERY lane TE.enter( (entry and add) must carry both.
      const ENTRY_ANCHOR = 'order_intent="gg-" + setup';
      const teCalls = (src) => {
        const found = [];
        for (let at = src.indexOf('TE.enter('); at >= 0; at = src.indexOf('TE.enter(', at + 1)) {
          let depth = 0, end = at + 'TE.enter'.length;
          for (; end < src.length; end++) {
            if (src[end] === '(') depth++;
            else if (src[end] === ')') { depth--; if (depth === 0) break; }
          }
          found.push(src.slice(at, end + 1));
        }
        return found;
      };
      const allCalls = teCalls(gl);
      const entryCall = allCalls.find((c) => c.includes(ENTRY_ANCHOR));
      const callErrs = (who, call) => {
        const out = [];
        for (const need of ['allow_earnings=True', 'ceiling="gg"']) if (!call.includes(need)) out.push(`the lane's ${who} TE.enter( call must carry ${need} (BUILD_SPEC19 D2 / D3)`);
        if (/target_price=(?!None\b)/.test(call) || /take_profit/.test(call)) out.push(`the lane's ${who} TE.enter( call must carry no target — GG has no fixed target (VR 11.6, D8d); target_price=None only`);
        return out;
      };
      // self-test: a compliant add call FIRST, then an entry call that dropped allow_earnings → must be caught
      const stand = teCalls('TE.enter(a, order_intent="gg-add-" + setup, allow_earnings=True, ceiling="gg")\nTE.enter(b, order_intent="gg-" + setup, ceiling="gg")');
      const standEntry = stand.find((c) => c.includes(ENTRY_ANCHOR)) || '';
      if (!standEntry.startsWith('TE.enter(b') || callErrs('entry', standEntry).length !== 1) errs.push('self-test: an entry call without allow_earnings=True behind a compliant add call was not caught');
      if (gl && !allCalls.length) errs.push('gajjala_entry.py must enter through TE.enter(…)');
      else if (gl && entryCall == null) errs.push(`gajjala_entry.py: no TE.enter( call carries ${ENTRY_ANCHOR} (the lane's entry)`);
      else if (gl) {
        errs.push(...callErrs('entry', entryCall));
        for (const c of allCalls.filter((x) => x !== entryCall)) errs.push(...callErrs('add', c));
      }
      if (gl && !/\bclosed_only\(/.test(glCode)) errs.push("gajjala_entry.py management must read bars through chart_maps.gajjala.bars closed_only( — CLOSED bars only (D8, the live-bar trap)");
      const en = tryRead('../backend/trading/entries.py', 'WP-A');
      if (en && !en.includes('ceiling: str = "house"')) errs.push('entries.py must accept ceiling: str = "house" (the p.312 ceiling waiver, BUILD_SPEC19 D3)');
      const ee = tryRead('../backend/trading/exit_engine.py', 'WP-A');
      if (ee && !ee.includes('"gajjala_floors": bool(doc.get("gajjala_floors", False)),')) errs.push('exit_engine.get_config must default "gajjala_floors" to False (BUILD_SPEC19 D1)');
      if (ee && ee.includes('"gajjala_floors": bool(doc.get("gajjala_floors", True)),')) errs.push('exit_engine.get_config still defaults "gajjala_floors" to True');

      // 4. the tab: the v2 object typed, guarded (array = the older API), each served key printed verbatim, no digit typed.
      for (const need of ["rules?: string[] | GajjalaRules | null;", "!Array.isArray(v)", 'const ggRules = ggRulesOf(s?.rules);',
                          '{ggRules && <GgRulesBlock rules={ggRules} />}', 'rules.not_built', 'rules.awaiting', 'rules[k]',
                          '<code>{a.key}</code>', 'served(a.question)', 'data-testid="gg-lane-awaiting"', 'data-testid="gg-lane-not-built"']) {
        if (!tab.includes(need)) errs.push(`GajjalaLaneTab.tsx must carry ${need}`);
      }
      const keysLine = (/export const GG_RULE_KEYS = \[([^\]]*)\] as const;/.exec(tab) || [])[1];
      const tabKeys = keysLine ? [...keysLine.matchAll(/'([a-z_]+)'/g)].map((m) => m[1]) : [];
      if (tabKeys.join(',') !== RULE_KEYS.join(',')) errs.push(`GajjalaLaneTab.tsx GG_RULE_KEYS must be exactly ${RULE_KEYS.join(', ')} (found ${tabKeys.join(', ') || 'none'})`);
      const bAt = tab.indexOf('function GgRulesBlock(');
      const bEnd = bAt < 0 ? -1 : tab.indexOf('\nfunction Block(', bAt);
      if (bAt < 0 || bEnd < 0) errs.push('GajjalaLaneTab.tsx must carry function GgRulesBlock( right above function Block(');
      else {
        const block = tab.slice(bAt, bEnd);
        const d = block.match(/\d/);
        if (d) errs.push(`GajjalaLaneTab.tsx GgRulesBlock types a digit ("${d[0]}") — every number of GG's rules is served`);
        if (BWORD.test(block)) errs.push('GajjalaLaneTab.tsx GgRulesBlock says the b-word');
        if (!/\d/.test(`${block}\nafter 3 bars`)) errs.push('self-test: a typed digit in GgRulesBlock was not caught');
      }
      const t = tryRead('src/components/GajjalaLaneTab.test.tsx', 'WP-B');
      for (const name of ["GajjalaLaneTab — GG's rules (2026-10-21)", "NEGATIVE: no `rules` served → no GG\\'s rules block and no older list",
                          "NEGATIVE: the older API (rules: string[]) renders the old list exactly as before, no GG\\'s rules block",
                          'NEGATIVE: an empty awaiting list (every number given) → no awaiting list; an empty not_built → no not-built list']) {
        if (t && !t.includes(name)) errs.push(`GajjalaLaneTab.test.tsx must keep the test "${name}"`);
      }
      if (!exists('../backend/tests/test_gajjala_lane_gg_rules.py')) errs.push('backend/tests/test_gajjala_lane_gg_rules.py is missing (WP-A, BUILD_SPEC19 D17)');

      // 5. the ✨ entry: FIRST, routed to the tab, both his lines verbatim, the only digits inside his quote, UNMEASURED, "Not advice.".
      // WIDENED 2026-10-21, later (BUILD_SPEC22 A5 / B4): the 🚩 lane GG's-words ✨ (FIRST) and the 🚩 K11 volume-floor ✨
      // (SECOND), each pinned in its own block, ship above this one — the FIRST pin widened to the top three, dated.
      const ID = 'autopilot-gajjala-lane-gg-rules-2026-10-21';
      const nf = read('src/lib/newFeatures.ts');
      const arr = nf.slice(nf.indexOf('export const NEW_FEATURES'));
      // 2026-10-21, later again: the 🔎 Gajjala's-in-⌘K ✨ (its own block, FIRST) lands above — widened by one, dated.
      // 2026-10-21, evening: the 📬 push delivery receipts ✨ (alerts-push-delivery-receipts-2026-10-21, its own block, FIRST) lands above the 🔎 one — widened by one more, dated.
      const firstThreeIds = [...arr.matchAll(/\{ id: '([^']+)'/g)].slice(0, 5).map((m) => m[1]);
      if (!firstThreeIds.includes(ID)) errs.push(`the ✨ entry '${ID}' must be one of the first five in NEW_FEATURES (found ${firstThreeIds.join(', ') || 'none'})`);
      const at = arr.indexOf(`{ id: '${ID}'`);
      if (at < 0) errs.push(`newFeatures.ts lacks the '${ID}' highlight`);
      else {
        const nextAt = arr.indexOf("{ id: '", at + 1);
        const e = arr.slice(at, nextAt < 0 ? undefined : nextAt);
        const label = (/label: "([^"]*)"/.exec(e) || [])[1] || '';
        const W = "the 🚩 GG's-rules ✨ entry";
        if (!e.includes("route: '/trading?view=gajjala'")) errs.push(`${W} must route to '/trading?view=gajjala'`);
        for (const h of [HIS1, HIS2]) if (!label.includes(`“${h}”`)) errs.push(`${W} must quote him verbatim: "${h.slice(0, 40)}…"`);
        if (!label.includes('UNMEASURED')) errs.push(`${W} must say UNMEASURED`);
        if (!label.endsWith('Not advice.')) errs.push(`${W} must end "Not advice."`);
        if (BWORD.test(label)) errs.push(`${W} says the b-word`);
        const outside = label.split(`“${HIS1}”`).join('').split(`“${HIS2}”`).join('');
        const d = outside.match(/\d+/);
        if (d) errs.push(`${W} types "${d[0]}" outside his quote — every number is served on the tab`);
        if (!/\d/.test(`${outside} risk 0.25%`)) errs.push('self-test: a typed number outside his quote was not caught');
      }

      // 6. the doc: REWRITTEN 2026-10-21 (BUILD_SPEC22 A5) — the placeholders are resolved by his word; the phrase
      // "awaiting your number" survives only as history inside that section, never as a live list.
      const DOC = '../docs/trading_gajjala_lane.md';
      const docTxt = exists(DOC) ? read(DOC) : '';
      const SEC = '## The four placeholders, resolved by his word';
      if (!docTxt.includes(SEC)) errs.push(`docs/trading_gajjala_lane.md must carry the section "${SEC}" (BUILD_SPEC22 A5)`);
      for (const need of [HIS_WORDS, 'HIS CALL #24', 'HIS CALL #25', 'HIS CALL #26', 'served EMPTY']) {
        if (docTxt && !docTxt.includes(need)) errs.push(`docs/trading_gajjala_lane.md must carry "${need}" (BUILD_SPEC22 A5)`);
      }
      const nb = docTxt.indexOf('## Not built');
      const nbBody = nb < 0 ? '' : docTxt.slice(nb, docTxt.indexOf('\n## ', nb + 3) < 0 ? undefined : docTxt.indexOf('\n## ', nb + 3));
      if (docTxt && !/all-in/.test(nbBody)) errs.push('docs/trading_gajjala_lane.md "## Not built" must keep all-in on an obvious A+ (his word "obvious" has no rule)');
      return errs;
    },
  },
  {
    name: '🌀 Gajjala VCP cards from two contractions (2026-10-20)',
    file: 'src/components/GajjalaBoard.tsx',
    // Ajay 2026-10-20: "Hey, Can you actually show me stocks only that have 2 contractions. in Gajjallas I don't see a point
    // of seeing the ones with one contraction do you?" BUILD_SPEC18 D1–D8: ONE switch (GC.VCP_LIST_FROM_K4) — the 🌀 sub
    // cards only reads with at least GC.K4_VCP_MIN_CYCLES contractions (HIS number); fewer are counted, never carded, never
    // a 🧠 potential; the served `list_note` says how many. The FE prints the note verbatim and types no word and no number.
    // Pins: the FE span + type, the backend switch / count / listing / potential clause / ℹ️ clause, both test files, the ✨
    // FIRST with his words (its only digit = K4_VCP_MIN_CYCLES read from constants.py), the doc section.
    checks: (src) => {
      const errs = [];
      const tryRead = (rel, who) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable (${who})`); return ''; } };
      const HIS = "Hey, Can you actually show me stocks only that have 2 contractions. in Gajjallas I don't see a point of seeing the ones with one contraction do you?";
      const BWORD = /boun/i;

      // 1. the FE: the served line printed verbatim, guarded, typed.
      for (const need of ['data-testid="gg-list-note"', 'board.list_note']) if (!src.includes(need)) errs.push(`GajjalaBoard.tsx must carry: ${need}`);
      if (!/typeof board\?\.list_note === 'string' && board\.list_note\.trim\(\)/.test(src)) errs.push('GajjalaBoard.tsx must guard list_note (a string, not blank) before printing it');
      const lib = tryRead('src/lib/gajjala.ts', 'frontend');
      if (lib && !lib.includes('list_note?: string | null;')) errs.push('lib/gajjala.ts GgBoard must type list_note?: string | null;');

      // 2. the backend: the switch, HIS number (read, never retyped), the count on the read, the listing, the potential clause, ℹ️.
      const gc = tryRead('../backend/chart_maps/gajjala/constants.py', 'backend');
      if (gc && !/^VCP_LIST_FROM_K4 = True\b/m.test(gc)) errs.push('chart_maps/gajjala/constants.py must carry VCP_LIST_FROM_K4 = True at column 0');
      const k4 = Number(((/^K4_VCP_MIN_CYCLES = (\d+)\b/m.exec(gc)) || [])[1]);
      if (!Number.isInteger(k4)) errs.push('chart_maps/gajjala/constants.py K4_VCP_MIN_CYCLES is unreadable');
      const det = tryRead('../backend/chart_maps/gajjala/detectors.py', 'backend');
      if (det && !det.includes('r["cycles"] = n')) errs.push('chart_maps/gajjala/detectors.py _vcp_leg must store r["cycles"] = n');
      const tab = tryRead('../backend/chart_maps/gajjala/tab.py', 'backend');
      for (const need of ['def _vcp_listed(', '"list_note"']) if (tab && !tab.includes(need)) errs.push(`chart_maps/gajjala/tab.py must carry: ${need}`);
      const pot = tryRead('../backend/chart_maps/gajjala/potential.py', 'backend');
      if (pot) {
        const at = pot.indexOf('def potential_kind(');
        const next = at < 0 ? -1 : pot.slice(at + 1).search(/\ndef |\nclass /);
        const body = at < 0 ? '' : pot.slice(at, next < 0 ? undefined : at + 1 + next);
        if (at < 0) errs.push('chart_maps/gajjala/potential.py lost def potential_kind(');
        else if (!body.includes('vcp_list_min_cycles(')) errs.push('chart_maps/gajjala/potential.py potential_kind must call vcp_list_min_cycles(');
      }
      const ri = tryRead('../backend/supply_demand/rules_info.py', 'backend');
      if (ri && !ri.includes('carded from')) errs.push('supply_demand/rules_info.py 🌀 line must carry the "carded from" clause');

      // 3. the tests, both sides.
      if (!exists('../backend/tests/test_gajjala_vcp_listing.py')) errs.push('backend/tests/test_gajjala_vcp_listing.py is missing (WP-A)');
      if (!exists('src/components/GajjalaBoard.list_note.test.tsx')) errs.push('src/components/GajjalaBoard.list_note.test.tsx is missing');

      // 4. the ✨ entry: FIRST, routed to the 🌀 sub, his words verbatim, the only digit = K4_VCP_MIN_CYCLES, ends "Not advice.".
      const ID = 'chart-maps-gajjala-vcp-two-contractions-2026-10-20';
      const nf = read('src/lib/newFeatures.ts');
      const arr = nf.slice(nf.indexOf('export const NEW_FEATURES'));
      // 2026-10-21: the 🛡 adopt_held served-sentence ✨ (autopilot-adopt-held-sentence-2026-10-21, its own block, FIRST) ships above — widened by one, dated (merged below with the two 🔴/🎚 pins that landed after it: +3 over the base).
      // 2026-10-21: the 🔴 Gajjala cards live ✨ and the 🎚 Tape control line ✨ (their own blocks, FIRST and SECOND) ship above this one — the FIRST pin widened to the top four, dated.
      // 2026-10-21, later: the 🚩 lane GG's-rules ✨ (its own block, FIRST — BUILD_SPEC19 F7) lands above the three of this morning — widened by one more, dated.
      // 2026-10-21, later still (BUILD_SPEC22 A5 / B4): the 🚩 lane GG's-words ✨ (FIRST) and the 🚩 K11 volume-floor ✨ (SECOND), each pinned in its own block, land above — widened by two, dated.
      // 2026-10-21, later again: the 🔎 Gajjala's-in-⌘K ✨ (its own block, FIRST) lands above — widened by one, dated.
      // 2026-10-21, evening: the 📬 push delivery receipts ✨ (alerts-push-delivery-receipts-2026-10-21, its own block, FIRST) lands above the 🔎 one — widened by one more, dated.
      const firstSeven = [...arr.matchAll(/\{ id: '([^']+)'/g)].slice(0, 9).map((m) => m[1]);
      if (!firstSeven.includes(ID)) errs.push(`the ✨ entry '${ID}' must be one of the first nine in NEW_FEATURES (found ${firstSeven.join(', ') || 'none'})`);
      const at = arr.indexOf(`{ id: '${ID}'`);
      if (at < 0) errs.push(`newFeatures.ts lacks the '${ID}' highlight`);
      else {
        const nextAt = arr.indexOf("{ id: '", at + 1);
        const e = arr.slice(at, nextAt < 0 ? undefined : nextAt);
        const label = (/label: "([^"]*)"/.exec(e) || [])[1] || '';
        const W = 'the 🌀 ✨ entry';
        if (!e.includes("route: '/chart-maps?tab=gajjala&sub=intraday_vcp'")) errs.push(`${W} must route to '/chart-maps?tab=gajjala&sub=intraday_vcp'`);
        if (!label.startsWith("🌀 Gajjala's Intraday VCP sub lists only names with at least two contractions now.")) errs.push(`${W} must lead with what changed`);
        if (!label.includes(`“${HIS}”`)) errs.push(`${W} must quote him verbatim: "${HIS}"`);
        if (!label.includes('UNMEASURED')) errs.push(`${W} must say UNMEASURED`);
        if (!label.endsWith('Not advice.')) errs.push(`${W} must end "Not advice."`);
        if (BWORD.test(label)) errs.push(`${W} says the b-word`);
        const digits = label.match(/\d+/g) || [];
        if (digits.length !== 1) errs.push(`${W} must carry exactly one number — the one in his quote (found ${digits.join(', ') || 'none'})`);
        else if (Number.isInteger(k4) && Number(digits[0]) !== k4) errs.push(`${W} says "${digits[0]}" — K4_VCP_MIN_CYCLES is ${k4}`);
      }

      // 5. the doc section (WP-A).
      const DOC = '../docs/gajjala/gajjala_tab_2026_10_13.md';
      if (!exists(DOC) || !read(DOC).includes('## 🌀 Cards from two contractions (2026-10-20)')) errs.push('docs/gajjala/gajjala_tab_2026_10_13.md must carry the "🌀 Cards from two contractions (2026-10-20)" section (WP-A)');
      return errs;
    },
  },
  {
    name: '🔴 Gajjala cards live (2026-10-21)',
    file: 'src/components/GajjalaBoard.tsx',
    // Ajay 2026-10-21, on a StockTwits screenshot of SAIQ: "Are we not real time SAIQ already broke the EMA", "I see it on
    // Stock Twitz" and "If something is Potential add min on min for pricing and other updates to make them more realtime
    // and give us a better edge". BUILD_SPEC20 D1–D7: every Gajjala tile rides the Chart Maps card poll (useCardLive on
    // the tile symbols, only inside the SERVED window) → patchTiles into PatternChart → the served footer after "as of";
    // POST /chart-maps/live takes an OPTIONAL `levels` (the tile's own served trigger / stop / frame) and live_card adds
    // display-only `vs` words (VS_TEXT); the card prints `live_vs.text` verbatim. The read still moves at GG's closed bar.
    // Pins: the FE wiring, no typed vs word on the FE, the backend signature / route / words / kinds, the import guard
    // (nothing that reads, rings or trades imports live_card), CARD_LIVE_MS unchanged, the ✨ FIRST, the tests, the docs.
    checks: (src) => {
      const errs = [];
      const tryRead = (rel, who) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable (${who})`); return ''; } };
      const noComments = (t) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
      const HIS = [
        'Are we not real time SAIQ already broke the EMA',
        'I see it on Stock Twitz',
        'If something is Potential add min on min for pricing and other updates to make them more realtime and give us a better edge',
      ];
      const LINE = "the card's price and its stop/trigger relation now refresh every 30 s; the read itself still moves at GG's bar close (5-minute; 15-minute for a fade read on 15-minute bars)";
      const VS_WORDS = /over the trigger|under the stop|between the stop|on the live bar|bar closes/i;

      // 1. the FE wiring (GajjalaBoard.tsx).
      const code = noComments(src);
      for (const need of [
        "import { useCardLive } from '../hooks/useCardLive';",
        'const liveSyms = useMemo(() => cardLiveSymbols(tiles), [tiles]);',
        'const inWindow = every != null && every > 0;',
        'useCardLive(liveSyms, inWindow && liveSyms.length > 0, {',
        'levels: liveLevels,',
        'patchTiles(tiles, cardLive.answer)',
        'liveTiles.map((t) => {',
        '<span className="gg-muted" data-testid="gg-live-footer">{cardLive.footer}</span>',
        'live={liveVsText(t)}',
        'data-testid={`gg-live-${sym}`}>{live}</div>',
        'const trigger = fin(t?.gajjala?.trigger);',
        'const stop = fin(t?.gajjala?.stop);',
        'if (!sym || (trigger == null && stop == null)) continue;',
      ]) if (!code.includes(need)) errs.push(`GajjalaBoard.tsx must carry: ${need}`);
      if (!/^\s*const every = ggRefreshMs\(board\);/m.test(code)) errs.push('GajjalaBoard.tsx: the window is the SERVED refresh_sec (const every = ggRefreshMs(board))');
      if ((code.match(/\buseCardLive\(/g) || []).length !== 1) errs.push('GajjalaBoard.tsx must call useCardLive( exactly once (one live read per board)');
      if ((code.match(/data-testid="gg-live-footer"/g) || []).length !== 1) errs.push('GajjalaBoard.tsx must print the live footer exactly once');
      const asOfAt = code.indexOf('data-testid="gg-as-of"');
      const footAt = code.indexOf('data-testid="gg-live-footer"');
      if (asOfAt < 0 || footAt < asOfAt) errs.push('the gg-live-footer must print AFTER the "as of" span');
      const cardLive = tryRead('src/lib/cardLive.ts', 'frontend');
      const hook = tryRead('src/hooks/useCardLive.ts', 'frontend');
      for (const [f, t] of [['GajjalaBoard.tsx', src], ['lib/cardLive.ts', cardLive], ['hooks/useCardLive.ts', hook]]) {
        const m = t ? VS_WORDS.exec(noComments(t)) : null;
        if (m) errs.push(`${f} types "${m[0]}" — every live-vs word is served (live_card.VS_TEXT)`);
        if (t && /[?&]levels=/.test(noComments(t))) errs.push(`${f} puts levels in a URL — the POST body only`);
      }
      // 2. lib/cardLive.ts: the quote type, the copy, the same tile when unchanged, the cadence untouched.
      if (cardLive) {
        for (const need of ['vs?: CardLiveVs | null;', 'export type CardLiveVs = { kind: string; text: string };',
          'const vs = validVs(q.vs) ? q.vs : undefined;', 'if (bars === bars0 && lines === lines0 && sameVs) return t;',
          'if (vs) out.live_vs = vs; else delete out.live_vs;', 'export function liveVsText(']) {
          if (!cardLive.includes(need)) errs.push(`lib/cardLive.ts must carry: ${need}`);
        }
        if (!/^export const CARD_LIVE_MS = 30_000;/m.test(cardLive)) errs.push('lib/cardLive.ts CARD_LIVE_MS must stay 30_000 (HIS CALL #1 — 10 s is his call)');
      }
      // 3. the hook: optional levels, the body unchanged without them.
      if (hook) {
        if (!hook.includes('levels?: CardLiveLevels | null')) errs.push('useCardLive.ts opts must take levels?: CardLiveLevels | null');
        if (!hook.includes('JSON.stringify(Object.keys(levels).length ? { symbols: asked, levels } : { symbols: asked })')) errs.push('useCardLive.ts must send {symbols, levels} only when a level is given, else exactly {symbols}');
      }
      // 4. the backend: the route takes levels, compose's signature, the words, the kinds.
      const api = tryRead('../backend/chart_maps/api.py', 'backend');
      const hAt = api.indexOf('@router.post("/chart-maps/live")');
      const hEnd = hAt < 0 ? -1 : api.indexOf('\n@router.', hAt + 1);
      const handler = hAt < 0 ? '' : api.slice(hAt, hEnd < 0 ? undefined : hEnd);
      if (!handler.includes('payload.get("levels")') || !handler.includes('levels=levels')) errs.push('the /chart-maps/live handler must read payload.get("levels") and pass levels=levels to live_card.compose (WP-A)');
      const lc = tryRead('../backend/chart_maps/live_card.py', 'backend');
      if (lc) {
        if (!/^def compose\(symbols, \*, levels=None, now: Optional\[datetime\] = None\) -> dict:/m.test(lc)) errs.push('live_card.compose must read def compose(symbols, *, levels=None, now: Optional[datetime] = None) -> dict: (WP-A)');
        if (!/^VS_KINDS = \("over_trigger", "under_stop", "between", "none"\)/m.test(lc)) errs.push('live_card.py must declare VS_KINDS = ("over_trigger", "under_stop", "between", "none") (WP-A)');
        const vAt = lc.search(/^VS_TEXT = \{/m);
        const vEnd = vAt < 0 ? -1 : lc.indexOf('\n}', vAt);
        const vt = vAt < 0 ? '' : lc.slice(vAt, vEnd < 0 ? undefined : vEnd).replace(/"\s*\n\s*"/g, '');
        if (!vt) errs.push('live_card.py must declare VS_TEXT = { … } (WP-A)');
        for (const need of [
          '"over_trigger": ("🔴 {px} over the trigger {trigger} on the live bar — the read moves when the {tf}-minute bar closes ({next_close} ET)"',
          '"under_stop": ("🔴 {px} under the stop {stop} on the live bar — the read moves when the {tf}-minute bar closes ({next_close} ET)"',
          '"between": "🔴 {px} · between the stop {stop} and the trigger {trigger}"',
        ]) if (vt && !vt.includes(need)) errs.push(`live_card.VS_TEXT must carry ${need.slice(0, 60)}… (BUILD_SPEC20 D2)`);
        if (/bounc/i.test(lc)) errs.push('live_card.py says the b-word — reversal');
      }
      // 5. the import guard: nothing that reads, stores, rings, grades or trades imports live_card.
      const walk = (rel) => {
        const out = [];
        let names = [];
        try { names = readdirSync(join(FRONTEND_ROOT, rel), { withFileTypes: true }); } catch { return out; }
        for (const d of names) {
          if (d.name === '__pycache__') continue;
          const p = `${rel}/${d.name}`;
          if (d.isDirectory()) out.push(...walk(p)); else if (d.name.endsWith('.py')) out.push(p);
        }
        return out;
      };
      const IMPORT = /^\s*(from\s+[\w.]*\blive_card\b\s+import|import\s+[\w.]*\blive_card\b|from\s+[\w.]+\s+import\s+[^\n]*\blive_card\b)/m;
      for (const f of [...walk('../backend/chart_maps/gajjala'), ...walk('../backend/trading')]) {
        if (IMPORT.test(read(f))) errs.push(`${f.replace('../', '')} imports live_card — the live words are display only (BUILD_SPEC20 D2)`);
      }
      // 6. the tests, both sides.
      if (!exists('../backend/tests/test_gajjala_live_vs_2026_10_21.py')) errs.push('backend/tests/test_gajjala_live_vs_2026_10_21.py is missing (WP-A)');
      if (!exists('src/components/GajjalaBoard.live.test.tsx')) errs.push('src/components/GajjalaBoard.live.test.tsx is missing');
      // 7. the ✨ entry: FIRST, routed to 🧠, his three lines verbatim, the line, the two digits = the constants.
      const ID = 'chart-maps-gajjala-live-2026-10-21';
      const nf = read('src/lib/newFeatures.ts');
      const arr = nf.slice(nf.indexOf('export const NEW_FEATURES'));
      // 2026-10-21, later: the 🚩 lane GG's-rules ✨ (its own block, FIRST — BUILD_SPEC19 F7) lands above this one — the FIRST pin widened to the top two, dated.
      // 2026-10-21, later still (BUILD_SPEC22 A5 / B4): the 🚩 lane GG's-words ✨ (FIRST) and the 🚩 K11 volume-floor ✨ (SECOND), each pinned in its own block, land above — widened by two, dated.
      // 2026-10-21, later again: the 🔎 Gajjala's-in-⌘K ✨ (its own block, FIRST) lands above — widened by one, dated.
      // 2026-10-21, evening: the 📬 push delivery receipts ✨ (alerts-push-delivery-receipts-2026-10-21, its own block, FIRST) lands above the 🔎 one — widened by one more, dated.
      const firstFour = [...arr.matchAll(/\{ id: '([^']+)'/g)].slice(0, 6).map((m) => m[1]);
      if (!firstFour.includes(ID)) errs.push(`the ✨ entry '${ID}' must be one of the first six in NEW_FEATURES (found ${firstFour.join(', ') || 'none'})`);
      const at = arr.indexOf(`{ id: '${ID}'`);
      if (at >= 0) {
        const nextAt = arr.indexOf("{ id: '", at + 1);
        const e = arr.slice(at, nextAt < 0 ? undefined : nextAt);
        const label = (/label: "([^"]*)"/.exec(e) || [])[1] || '';
        const W = 'the 🔴 ✨ entry';
        if (!e.includes("route: '/chart-maps?tab=gajjala&sub=potential'")) errs.push(`${W} must route to '/chart-maps?tab=gajjala&sub=potential'`);
        for (const h of HIS) if (!label.includes(`“${h}”`)) errs.push(`${W} must quote him verbatim: "${h}"`);
        if (!label.includes(LINE)) errs.push(`${W} must say: ${LINE}`);
        for (const need of ['UNMEASURED', 'freshness']) if (!label.includes(need)) errs.push(`${W} must say "${need}"`);
        if (!label.endsWith('Not advice.')) errs.push(`${W} must end "Not advice."`);
        if (/bounc/i.test(label)) errs.push(`${W} says the b-word`);
        const fastM = /^export const CARD_LIVE_MS = ([0-9_]+);/m.exec(cardLive);
        const sec = fastM ? Number(fastM[1].replace(/_/g, '')) / 1000 : null;
        const tab = tryRead('../backend/chart_maps/gajjala/tab.py', 'backend');
        // 2026-10-21 (verifier): the label names BOTH of GG's frames — a fade read can sit on 15-minute bars — so every
        // tab.TFS value is an allowed number, not only TFS[0].
        const tfM = /^TFS = \(([^)]*)\)/m.exec(tab);
        const frames = tfM ? [...tfM[1].matchAll(/"(\d+)m"/g)].map((m) => Number(m[1])) : [];
        const digits = [...new Set(label.match(/\d+/g) || [])].map(Number).sort((a, b) => a - b);
        const want = [...new Set([...frames, sec].filter((x) => x != null))].sort((a, b) => a - b);
        if (digits.join(',') !== want.join(',')) errs.push(`${W} numbers ${digits.join(', ')} must be exactly CARD_LIVE_MS/1000 (${sec}) and tab.TFS (${frames.join(', ')})`);
      } else errs.push(`newFeatures.ts lacks the '${ID}' highlight`);
      // 8. the docs (WP-A).
      const DOC = '../docs/gajjala/gajjala_tab_2026_10_13.md';
      if (!exists(DOC) || !read(DOC).includes('🔴 Live on the cards (2026-10-21)')) errs.push('docs/gajjala/gajjala_tab_2026_10_13.md must carry the "🔴 Live on the cards (2026-10-21)" section (WP-A)');
      const ri = tryRead('../backend/supply_demand/rules_info.py', 'backend');
      if (ri && !(ri.includes('the read moves at the %d-minute') || ri.includes('the read moves at the 5-minute'))) errs.push('supply_demand/rules_info.py 🚩 block must carry the "the read moves at the … bar close" line (WP-A)');
      return errs;
    },
  },
  {
    name: '🎚 Tape: one control line (2026-10-21)',
    file: 'src/components/TapePanel.tsx',
    // Ajay 2026-10-21, on a screenshot of the Tape panel's delta block ("MIXED 40.4%" beside "who's in control"): "Also
    // its not very clear in the TAPE if they are buyers or sellers". BUILD_SPEC21 D1–D7: ONE served control read
    // (orderflow/tape.py delta_summary `control`, CONTROL_TEXT — the SIGN rule the FE used, moved server-side, NO
    // threshold); the panel prints control.headline / control.detail verbatim and types no control word; deltaTone keeps
    // the colour only; the classification badge leaves the "who's in control" eyebrow for the footnote. UNMEASURED.
    checks: (src) => {
      const errs = [];
      const tryRead = (rel, who) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable (${who})`); return ''; } };
      const noComments = (t) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
      const HIS = 'Also its not very clear in the TAPE if they are buyers or sellers';
      const LINE = 'one served line says who is in control; the classification badge moved to the footnote';

      // 1. the backend: CONTROL_TEXT, the words, the sign rule, no threshold, the served key.
      const py = tryRead('../backend/orderflow/tape.py', 'backend');
      if (py) {
        if (!/^CONTROL_WORDS = \("buyers", "sellers", "balanced"\)/m.test(py)) errs.push('orderflow/tape.py must declare CONTROL_WORDS = ("buyers", "sellers", "balanced") (WP-A)');
        const cAt = py.search(/^CONTROL_TEXT = \{/m);
        const ct = cAt < 0 ? '' : py.slice(cAt, py.indexOf('\n}', cAt));
        if (!ct) errs.push('orderflow/tape.py must declare CONTROL_TEXT = { … } (WP-A)');
        for (const need of ['"{session_upper} IN CONTROL"', '— turning"', '"BALANCED"', '"balanced for the session · {late} now"', '"no prints yet"',
          '"session {delta} sh ({pct}% of volume) · last {late_window_min} min {late_delta} sh"']) {
          if (ct && !ct.includes(need)) errs.push(`orderflow/tape.py CONTROL_TEXT must carry ${need} (BUILD_SPEC21 D1)`);
        }
        if (!/return buyers if delta > 0 else \(sellers if delta < 0 else balanced\)/.test(py)) errs.push('orderflow/tape.py _control_word must be the SIGN rule (> 0 buyers, < 0 sellers, else balanced) — no threshold');
        if (/^CONTROL_[A-Z_]*(MIN|MAX|THRESH|PCT|SHARES|FLOOR)[A-Z_]* = /m.test(py)) errs.push('orderflow/tape.py defines a CONTROL_* threshold — the word is the sign rule only (a threshold is a conscious, cited change)');
        if (!/^def _signed_shares\(/m.test(py)) errs.push('orderflow/tape.py must carry def _signed_shares( (one helper, the FE minus)');
        if (!/"control": control_read\(/.test(py)) errs.push('orderflow/tape.py delta_summary must serve "control": control_read(…) (WP-A)');
        if (/bounc/i.test(py.slice(Math.max(0, cAt - 1200), cAt + 2000))) errs.push('the tape.py control block says the b-word');
      }
      // 2. the FE prints the served line only, types no control word, keeps the 30-minute caption.
      const code = noComments(src);
      for (const need of ['{control.headline}', '{control.detail}', 'data-testid="tape-control-headline"', 'data-testid="tape-control-detail"',
        "delta?.control && typeof delta.control.headline === 'string' && delta.control.headline.trim()",
        'sub={`${delta?.delta_pct_of_volume ?? 0}% of volume`}', `sub="who's in control now"`]) {
        if (!code.includes(need)) errs.push(`TapePanel.tsx must carry: ${need}`);
      }
      if (/\btone\.word\b|\.word\b/.test(code)) errs.push('TapePanel.tsx reads a .word — the control word is served (delta.control)');
      const bare = code.replace(/<InfoButton[\s\S]*?<\/InfoButton>/g, '');
      const typed = /\b(buyers|sellers|balanced)\b|IN CONTROL|BALANCED/.exec(bare);
      if (typed) errs.push(`TapePanel.tsx types "${typed[0]}" outside an ⓘ — the control words are served`);
      if (!src.includes('The headline is who is in control: the sign of the session delta, and the last 30 minutes next to it — when they disagree the tape is turning.')) errs.push('the ⓘ "What is delta?" must carry the headline sentence (BUILD_SPEC21 D4)');
      // 3. deltaTone keeps the colour only.
      const lib = tryRead('src/lib/orderflow.ts', 'frontend');
      const dAt = lib.indexOf('export function deltaTone(');
      const dBody = dAt < 0 ? '' : lib.slice(dAt, lib.indexOf('\n}', dAt));
      if (!dBody.startsWith('export function deltaTone(delta: number): { color: string } {')) errs.push('lib/orderflow.ts deltaTone must return { color: string } only');
      if (/word/.test(dBody)) errs.push('lib/orderflow.ts deltaTone still carries a word');
      if (!lib.includes('control?: TapeControl | null;')) errs.push('lib/orderflow.ts must type delta.control?: TapeControl | null;');
      // 4. the badge: out of the eyebrow, into the footnote.
      const eAt = code.indexOf('data-testid="tape-delta-eyebrow"');
      const eEnd = eAt < 0 ? -1 : code.indexOf('</InfoButton>\n        </div>', eAt);
      const eyebrow = eAt < 0 || eEnd < 0 ? '' : code.slice(eAt, eEnd);
      if (!eyebrow) errs.push('TapePanel.tsx lost the tape-delta-eyebrow block');
      if (/cls\.|tape-method-badge/.test(eyebrow.replace(/<InfoButton[\s\S]*?<\/InfoButton>/g, ''))) errs.push('the classification badge is back in the "who\'s in control" eyebrow');
      const fAt = code.indexOf('data-testid="tape-method-footnote"');
      const foot = fAt < 0 ? '' : code.slice(fAt, code.indexOf('</p>', fAt));
      if (!foot.includes('data-testid="tape-method-badge"') || !foot.includes('classified: {cls.label}') || !foot.includes('title={cls.title}')) errs.push('the footnote must carry the badge: data-testid="tape-method-badge", title={cls.title}, classified: {cls.label}');
      if ((code.match(/\{cls\.label\}/g) || []).length !== 1) errs.push('TapePanel.tsx must print cls.label exactly once (the footnote)');
      // 5. the tests, both sides.
      if (!exists('../backend/tests/test_tape_control_line_2026_10_21.py')) errs.push('backend/tests/test_tape_control_line_2026_10_21.py is missing (WP-A)');
      const t = tryRead('src/components/TapePanel.test.tsx', 'frontend');
      for (const name of ['prints the served control.headline and control.detail verbatim',
        'NEGATIVE: an older snapshot with no control → no headline row and no control word anywhere',
        'NEGATIVE: never in the eyebrow']) if (t && !t.includes(name)) errs.push(`TapePanel.test.tsx must keep the test "${name}"`);
      // 6. the ✨ entry: in the top two, routed, his line verbatim, the one digit = tape.LATE_WINDOW_MIN.
      const ID = 'chart-maps-tape-control-line-2026-10-21';
      const nf = read('src/lib/newFeatures.ts');
      const arr = nf.slice(nf.indexOf('export const NEW_FEATURES'));
      // 2026-10-21, later: the 🚩 lane GG's-rules ✨ (its own block, FIRST — BUILD_SPEC19 F7) lands above the three of this morning — widened to the top three, dated.
      // 2026-10-21, later still (BUILD_SPEC22 A5 / B4): the 🚩 lane GG's-words ✨ (FIRST) and the 🚩 K11 volume-floor ✨ (SECOND), each pinned in its own block, land above — widened by two, dated.
      // 2026-10-21, later again: the 🔎 Gajjala's-in-⌘K ✨ (its own block, FIRST) lands above — widened by one, dated.
      // 2026-10-21, evening: the 📬 push delivery receipts ✨ (alerts-push-delivery-receipts-2026-10-21, its own block, FIRST) lands above the 🔎 one — widened by one more, dated.
      const firstFive = [...arr.matchAll(/\{ id: '([^']+)'/g)].slice(0, 7).map((m) => m[1]);
      if (!firstFive.includes(ID)) errs.push(`the ✨ entry '${ID}' must be one of the first seven in NEW_FEATURES (found ${firstFive.join(', ') || 'none'})`);
      const at = arr.indexOf(`{ id: '${ID}'`);
      if (at >= 0) {
        const nextAt = arr.indexOf("{ id: '", at + 1);
        const e = arr.slice(at, nextAt < 0 ? undefined : nextAt);
        const label = (/label: "([^"]*)"/.exec(e) || [])[1] || '';
        const W = 'the 🎚 ✨ entry';
        if (!e.includes("route: '/alerts'")) errs.push(`${W} must route to '/alerts' (the symbol-less page whose 🎚 rows open a tape)`);
        if (!label.includes(`“${HIS}”`)) errs.push(`${W} must quote him verbatim: "${HIS}"`);
        if (!label.includes(LINE)) errs.push(`${W} must say: ${LINE}`);
        if (!label.includes('UNMEASURED')) errs.push(`${W} must say UNMEASURED`);
        if (!label.endsWith('Not advice.')) errs.push(`${W} must end "Not advice."`);
        if (/bounc/i.test(label)) errs.push(`${W} says the b-word`);
        const lwM = /^LATE_WINDOW_MIN = (\d+)/m.exec(py);
        const digits = [...new Set(label.match(/\d+/g) || [])];
        if (!lwM || digits.length !== 1 || digits[0] !== lwM[1]) errs.push(`${W} must carry exactly one number = tape.LATE_WINDOW_MIN (${lwM ? lwM[1] : 'absent'}; found ${digits.join(', ') || 'none'})`);
      } else errs.push(`newFeatures.ts lacks the '${ID}' highlight`);
      // 7. the doc (WP-A).
      const DOC = '../docs/sepa/orderflow_methodology.md';
      if (!exists(DOC) || !read(DOC).includes("Who's in control (2026-10-21)")) errs.push(`docs/sepa/orderflow_methodology.md must carry the "Who's in control (2026-10-21)" section (WP-A)`);
      return errs;
    },
  },
  {
    name: "🚩 Gajjala lane: GG's words (2026-10-21)",
    file: 'src/lib/newFeatures.ts',
    // Ajay 2026-10-21 ~13:10 ET: "keep what ever Gajjala says for these" — on the four lane placeholders (partial R,
    // 9 or 21 EMA on Kiss & Fly, halt calm-down minutes, cushion for double size). BUILD_SPEC22 Part A: each is GG's
    // sentence (VR 11.4 / 11.3 / 10.1 / 11.7) in backend/trading/gajjala_entry.py — its constants are pinned in the
    // block "🚩 Gajjala lane: GG's rules (2026-10-21)". This block pins the ✨ (FIRST, his line verbatim, the four rules
    // in words, NO digit outside his quote — the numbers are served on the tab) and the 🚩 lane rules_info line built
    // from the new constants by name. PAPER, UNMEASURED.
    checks: (nf) => {
      const errs = [];
      const tryRead = (rel, who) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable (${who})`); return ''; } };
      const HIS = 'keep what ever Gajjala says for these';
      const ID = 'autopilot-gajjala-lane-gg-words-2026-10-21';
      // 1. the ✨ entry: FIRST.
      // 2026-10-21, later again: the 🔎 Gajjala's-in-⌘K ✨ (its own block, FIRST) lands above this one — widened to the top two, dated.
      // 2026-10-21, evening: the 📬 push delivery receipts ✨ (alerts-push-delivery-receipts-2026-10-21, its own block, FIRST) lands above the 🔎 one — widened by one more, dated.
      const arr = nf.slice(nf.indexOf('export const NEW_FEATURES'));
      const firstTwoIds = [...arr.matchAll(/\{ id: '([^']+)'/g)].slice(0, 3).map((m) => m[1]);
      if (!firstTwoIds.includes(ID)) errs.push(`the ✨ entry '${ID}' must be one of the first three in NEW_FEATURES (found ${firstTwoIds.join(', ') || 'none'})`);
      const at = arr.indexOf(`{ id: '${ID}'`);
      if (at < 0) errs.push(`newFeatures.ts lacks the '${ID}' highlight`);
      else {
        const nextAt = arr.indexOf("{ id: '", at + 1);
        const e = arr.slice(at, nextAt < 0 ? undefined : nextAt);
        const label = (/label: "([^"]*)"/.exec(e) || [])[1] || '';
        const W = "the 🚩 GG's-words ✨ entry";
        if (!e.includes("route: '/trading?view=gajjala'")) errs.push(`${W} must route to '/trading?view=gajjala'`);
        if (!e.includes("addedAt: '2026-10-21'")) errs.push(`${W} must carry addedAt '2026-10-21'`);
        if (!label.includes(`“${HIS}”`)) errs.push(`${W} must quote him verbatim: “${HIS}”`);
        // the four rules, in words (A1 Kiss & Fly trail, A2 partial after the add, A3 halt wait, A4 cushion → double).
        for (const need of ['Kiss & Fly', 'slower EMA', 'added at breakeven', 'closes above every high since the entry sells half',
                            'never enters while a name is halting', 'one clean closed bar after the resume', 'risks up to double', // 2026-10-21 verifier: 'up to' — the size caps still apply
                            'covers two losers', 'no loss streak', 'drawdown mode off', 'all-in on an obvious A+ stays not built']) {
          if (!label.includes(need)) errs.push(`${W} must say "${need}" (BUILD_SPEC22 A1–A4)`);
        }
        for (const need of ['UNMEASURED', '(paper)']) if (!label.includes(need)) errs.push(`${W} must say "${need}"`);
        if (!label.endsWith('Not advice.')) errs.push(`${W} must end "Not advice."`);
        if (/boun/i.test(label)) errs.push(`${W} says the b-word`);
        const outside = label.split(`“${HIS}”`).join('');
        const d = outside.match(/\d+/);
        if (d) errs.push(`${W} types "${d[0]}" outside his quote — every number is served on the tab`);
        if (!/\d/.test(`${outside} the 21 EMA`)) errs.push('self-test: a typed number outside his quote was not caught');
      }
      // 2. the 🚩 lane rules_info line reads the new constants by name (WP-A) — never a retyped 21 / 1 / 2.
      const ri = tryRead('../backend/supply_demand/rules_info.py', 'WP-A');
      for (const name of ['GLN.GG_TRAIL_EMA_KF', 'GLN.GG_PARTIAL_FRAC', 'GLN.GG_HALT_CALM_BARS', 'GLN.GG_DOUBLE_MULT', 'GLN.GG_CUSHION_LOSERS']) {
        if (ri && !ri.includes(name)) errs.push(`rules_info.py 🚩 lane line must read ${name} by name (BUILD_SPEC22 A5)`);
      }
      if (ri && /GG_PARTIAL_R\b|GG_HALT_CALM_MIN|GG_CUSHION_DOUBLE_PCT/.test(ri)) errs.push('rules_info.py still names a removed placeholder (GG_PARTIAL_R / GG_HALT_CALM_MIN / GG_CUSHION_DOUBLE_PCT)');
      // 3. the tests, both sides.
      if (!exists('../backend/tests/test_gajjala_lane_gg_words_2026_10_21.py')) errs.push('backend/tests/test_gajjala_lane_gg_words_2026_10_21.py is missing (WP-A)');
      const t = tryRead('src/components/GajjalaLaneTab.test.tsx', 'frontend');
      if (t && !t.includes('NEGATIVE: an empty awaiting list (every number given) → no awaiting list')) errs.push('GajjalaLaneTab.test.tsx must keep the empty-awaiting NEGATIVE (rules.awaiting is served EMPTY)');
      return errs;
    },
  },
  {
    name: "🚩 Gajjala K11 today's volume floor (2026-10-21)",
    file: '../backend/chart_maps/gajjala/detectors.py',
    // Ajay 2026-10-21 ~13:10 ET: "keep what ever Gajjala says for these" — on "Whether an A+ should also require today’s
    // volume to clear GG’s 1M floor (NIXX rang on 288K shares)." BUILD_SPEC22 Part B: GG VR 0.4 "1M is a floor … it must
    // SUSTAIN (one 1M bar then a fade = not interested)". ONE number: K11_MIN_SESSION_VOLUME = SCAN_MIN_VOLUME. A broke
    // read under it (or with no figure — fail-closed) is "broke — not A+" before the push gate (detectors.k11_gate inside
    // read_all), so it is never claimed; forming 🧠 reads are untouched. The ✨ sits in the top two; its only digits are
    // inside his quoted line. UNMEASURED.
    checks: (det) => {
      const errs = [];
      const tryRead = (rel, who) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable (${who})`); return ''; } };
      const pyNoComments = (x) => x.replace(/#[^\n]*/g, '');
      const HIS = 'keep what ever Gajjala says for these';
      const ASKED = 'Whether an A+ should also require today’s volume to clear GG’s 1M floor (NIXX rang on 288K shares).';
      // 1. ONE number: the floor IS the scanner floor, by name, with GG's VR cite and his line on the line.
      const gc = tryRead('../backend/chart_maps/gajjala/constants.py', 'WP-B');
      const k = /^K11_MIN_SESSION_VOLUME\s*=\s*([^#\n]*?)\s*(#[^\n]*)?$/m.exec(gc);
      if (gc && !k) errs.push('constants.py must define K11_MIN_SESSION_VOLUME at column 0 (BUILD_SPEC22 B1)');
      else if (k) {
        if (k[1] !== 'SCAN_MIN_VOLUME') errs.push(`constants.py K11_MIN_SESSION_VOLUME must be SCAN_MIN_VOLUME by name — one number, never a second (found "${k[1]}")`);
        if (!/\bGG VR 0\.4\b/.test(k[2] || '')) errs.push('constants.py K11_MIN_SESSION_VOLUME must carry its cite "# GG VR 0.4 …" on the line');
        if (!(k[2] || '').includes(`Ajay 2026-10-21 "keep what ever Gajjala says`)) errs.push('constants.py K11_MIN_SESSION_VOLUME must carry his 2026-10-21 line on the line');
      }
      if (gc && !/^SCAN_MIN_VOLUME = 1_000_000\b/m.test(gc)) errs.push('constants.py SCAN_MIN_VOLUME must stay his 1_000_000 (GG S8 19:12)');
      const second = gc ? [...gc.matchAll(/^(K11_[A-Z_]+)\s*=\s*[-\d]/gm)].map((m) => m[1]) : [];
      if (second.length) errs.push(`constants.py types a second K11 number (${second.join(', ')}) — K11 has ONE number, the scanner floor`);
      if (!/^(K11_[A-Z_]+)\s*=\s*[-\d]/m.test('K11_MIN_SESSION_VOLUME = SCAN_MIN_VOLUME\nK11_FADE_BARS = 3')) errs.push('self-test: a second typed K11 number was not caught');
      // 2. the detector: the criteria key, the states judged (never forming), the fail-closed words, the claim gate.
      const code = pyNoComments(det);
      for (const [re, line] of [
        [/^K11_KEY = "k11_volume"$/m, 'K11_KEY = "k11_volume"'],
        [/^K11_CTX_KEY = "session_volume"$/m, 'K11_CTX_KEY = "session_volume"'],
        [/^K11_STATES = \("aplus", "triggered", "stopped"\)$/m, 'K11_STATES = ("aplus", "triggered", "stopped")'],
        [/^K11_UNKNOWN = "today's volume unknown"$/m, 'K11_UNKNOWN = "today\'s volume unknown"'],
        [/^K11_WHY = "GG: one 1M bar then a fade = not interested"/m, 'K11_WHY = "GG: one 1M bar then a fade = not interested"'],
        [/^NOT_APLUS_REASON = "broke — not A\+"/m, 'NOT_APLUS_REASON = "broke — not A+"'],
      ]) if (!re.test(det)) errs.push(`detectors.py must carry ${line} at column 0 (BUILD_SPEC22 B1)`);
      const st = (/^K11_STATES = \(([^)]*)\)/m.exec(det) || [])[1] || '';
      if (/"forming"|"potential"/.test(st)) errs.push('detectors.K11_STATES judges a forming read — 🧠 potentials are untouched (K11 is judged at the ring)');
      const crit = (/def k11_criterion\([\s\S]*?\n(?=\n\ndef )/.exec(code) || [''])[0];
      if (!crit) errs.push('detectors.py must define k11_criterion(');
      else {
        if (!crit.includes('floor = int(GC.K11_MIN_SESSION_VOLUME)')) errs.push('k11_criterion must read the floor from GC.K11_MIN_SESSION_VOLUME at call time');
        if (/\b\d{3,}\b|\d_\d{3}/.test(crit)) errs.push('k11_criterion types a number — the floor is the constant');
        if (!/if v is None:\s*\n\s*return criterion\(K11_KEY, f"K11 \{K11_UNKNOWN\} \(needs ≥ \{floor:,\}\)", False/.test(crit)) {
          errs.push('k11_criterion must FAIL CLOSED: no figure → criterion(K11_KEY, f"K11 {K11_UNKNOWN} (needs ≥ {floor:,})", False, …)');
        }
        if (!crit.includes('if v >= floor:')) errs.push('k11_criterion must pass at v >= floor (the floor itself clears)');
      }
      const gate = (/def k11_gate\([\s\S]*?\n(?=\n\n)/.exec(code) || [''])[0];
      if (!gate) errs.push('detectors.py must define k11_gate(');
      else {
        if (!gate.includes('r.get("state") not in K11_STATES')) errs.push('k11_gate must judge only K11_STATES reads (forming untouched)');
        if (!/r\["state"\], r\["reason"\], r\["ready"\] = "partial", NOT_APLUS_REASON, False/.test(gate)) errs.push('k11_gate must turn a miss into state "partial", NOT_APLUS_REASON, ready False (the K3 path) — never A+');
      }
      const ra = (/def read_all\([\s\S]*?\n    return out\n/.exec(code) || [''])[0];
      if (!ra) errs.push('detectors.read_all must end "return out"');
      else if (!/if K11_CTX_KEY in ctx:[\s\S]*k11_gate\(r, vol\)[\s\S]*return out\n$/.test(ra)) errs.push('detectors.read_all must apply k11_gate(r, vol) to every read when ctx carries K11_CTX_KEY — the claim gate runs before alerts.py sees the read');
      // the seam (critic 2026-10-21): the pass hands its own scanner session volume to BOTH read_all calls, or K11 never fires.
      const rp = pyNoComments(tryRead('../backend/chart_maps/gajjala/run.py', 'seam'));
      const rcalls = rp.match(/deps\.read_all\([^\n]*\n?[^\n]*/g) || [];
      if (rp && (rcalls.length !== 2 || !rcalls.every((c) => c.includes('D.K11_CTX_KEY: sv.get(s)')) || !/sv = \{s: \(q_rows\.get\(s\) or _row_from_snapshot\(s, rows\.get\(s\), session_iso\) or \{\}\)\.get\("volume"\) for s in frames\}/.test(rp))) errs.push('run.py must pass D.K11_CTX_KEY: sv.get(s) (the pass\'s own qualifier / snapshot row volume, never the stored row) to BOTH deps.read_all calls');
      // the push gate claims an "aplus" read only — so a K11 "partial" is never a candidate.
      const al = tryRead('../backend/chart_maps/gajjala/alerts.py', 'WP-B');
      if (al && !/K11/.test(al)) errs.push('alerts.py must say how K11 keeps a read off the claim (docstring)');
      if (al && !/state"\)\s*(?:!=|==)\s*"aplus"|state"\) == "aplus"|\.get\("state"\) != "aplus"/.test(pyNoComments(al))) errs.push('alerts.py must gate the claim on state "aplus" only');
      // 3. the panel line, the Playbook row, the tests, the doc, SPECS.md.
      const ri = tryRead('../backend/supply_demand/rules_info.py', 'WP-C');
      if (ri && !/_gg_n\("K11_MIN_SESSION_VOLUME"\), GD\.K11_WHY, GD\.K11_UNKNOWN, GD\.NOT_APLUS_REASON/.test(ri)) errs.push('rules_info.py 🚩 Gajjala section must build the K11 line from _gg_n("K11_MIN_SESSION_VOLUME"), GD.K11_WHY, GD.K11_UNKNOWN, GD.NOT_APLUS_REASON — never retyped');
      const pb = tryRead('../backend/chart_maps/gajjala/playbook.py', 'WP-B');
      if (pb && !/\("K11", "today's volume ≥ %s shares at the ring[^"]*"\s*\n\s*% _n\("K11_MIN_SESSION_VOLUME"\)/.test(pb)) errs.push('playbook.py must carry the ("K11", "today\'s volume ≥ %s shares at the ring …" % _n("K11_MIN_SESSION_VOLUME")) row');
      for (const f of ['../backend/tests/test_gajjala_k11_volume_2026_10_21.py', '../backend/tests/test_rules_info_gajjala_k11_2026_10_21.py']) {
        if (!exists(f)) errs.push(`${f.replace('../', '')} is missing (BUILD_SPEC22 B5)`);
      }
      const DOC = '../docs/gajjala/gajjala_tab_2026_10_13.md';
      const doc = exists(DOC) ? read(DOC) : '';
      const SEC = "## K11 today's volume floor on the A+ claim (2026-10-21)";
      if (!doc.includes(SEC)) errs.push(`${DOC.replace('../', '')} must carry the section "${SEC}"`);
      else {
        const body = doc.slice(doc.indexOf(SEC), doc.indexOf('\n## ', doc.indexOf(SEC) + 3) < 0 ? undefined : doc.indexOf('\n## ', doc.indexOf(SEC) + 3));
        for (const need of ['NIXX', '288', 'HIS CALL #27', 'UNMEASURED', 'K11_MIN_SESSION_VOLUME']) if (!body.includes(need)) errs.push(`the K11 doc section must carry "${need}"`);
        if (/boun/i.test(body)) errs.push('the K11 doc section says the b-word');
      }
      const specs = tryRead('../SPECS.md', 'WP-C');
      if (specs && !/`K11_MIN_SESSION_VOLUME` = `SCAN_MIN_VOLUME`/.test(specs)) errs.push('SPECS.md must carry the K11 line (`K11_MIN_SESSION_VOLUME` = `SCAN_MIN_VOLUME`)');
      // 4. the ✨ entry: in the top two, routed, his words + the line he answered verbatim, the only digits inside that quote.
      const nf = read('src/lib/newFeatures.ts');
      const arr = nf.slice(nf.indexOf('export const NEW_FEATURES'));
      const ID = 'chart-maps-gajjala-k11-volume-floor-2026-10-21';
      // 2026-10-21, later again: the 🔎 Gajjala's-in-⌘K ✨ (its own block, FIRST) lands above — widened by one, dated.
      // 2026-10-21, evening: the 📬 push delivery receipts ✨ (alerts-push-delivery-receipts-2026-10-21, its own block, FIRST) lands above the 🔎 one — widened by one more, dated.
      const firstTwo = [...arr.matchAll(/\{ id: '([^']+)'/g)].slice(0, 4).map((m) => m[1]);
      if (!firstTwo.includes(ID)) errs.push(`the ✨ entry '${ID}' must be one of the first four in NEW_FEATURES (found ${firstTwo.join(', ') || 'none'})`);
      const at = arr.indexOf(`{ id: '${ID}'`);
      if (at < 0) errs.push(`newFeatures.ts lacks the '${ID}' highlight`);
      else {
        const nextAt = arr.indexOf("{ id: '", at + 1);
        const e = arr.slice(at, nextAt < 0 ? undefined : nextAt);
        const label = (/label: "([^"]*)"/.exec(e) || [])[1] || '';
        const W = 'the 🚩 K11 ✨ entry';
        if (!e.includes("route: '/chart-maps?tab=gajjala&sub=kiss_fly'")) errs.push(`${W} must route to '/chart-maps?tab=gajjala&sub=kiss_fly'`);
        for (const h of [HIS, ASKED]) if (!label.includes(`“${h}”`)) errs.push(`${W} must quote verbatim: “${h.slice(0, 50)}…”`);
        for (const need of ['broke — not A+', 'no volume figure', 'never rings', 'potentials are not judged', 'not comparable', 'UNMEASURED']) {
          if (!label.includes(need)) errs.push(`${W} must say "${need}"`);
        }
        if (!label.endsWith('Not advice.')) errs.push(`${W} must end "Not advice."`);
        if (/boun/i.test(label)) errs.push(`${W} says the b-word`);
        const outside = label.split(`“${HIS}”`).join('').split(`“${ASKED}”`).join('');
        const d = outside.match(/\d+/);
        if (d) errs.push(`${W} types "${d[0]}" outside the quote — the floor is served (K11_MIN_SESSION_VOLUME)`);
        if (!/\d/.test(`${outside} under 1M`)) errs.push('self-test: a typed number outside the quote was not caught');
      }
      return errs;
    },
  },
  {
    name: "🔎 Gajjala's in ⌘K (2026-10-21)",
    file: 'src/lib/navSearch.ts',
    // Ajay 2026-10-21 ~14:20 ET: "Also I need this tab and its subtabs sercheable in global search". ONE palette row for
    // the tab + ONE deep link per sub, GENERATED from lib/gajjala.GG_SUBS (pinned to backend constants.SUBS) — never a
    // typed sub key; the 🚩 lane view on Trading rides along under its own parent. Search words only; "reversal", never
    // "bounce"; the tab label == chartMaps.TAB_META.gajjala.label. The ✨ is FIRST with his line verbatim. Frontend only.
    checks: (nav) => {
      const errs = [];
      const tryRead = (rel, who) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable (${who})`); return ''; } };
      if (!/^import \{ GG_SUBS, GG_SUB_PARAM \} from '\.\/gajjala';$/m.test(nav)) errs.push("navSearch.ts must import { GG_SUBS, GG_SUB_PARAM } from './gajjala' — the rows are generated from the sub strip");
      if (!/^export const GG_TAB_TO = '\/chart-maps\?tab=gajjala';$/m.test(nav)) errs.push("navSearch.ts must export GG_TAB_TO = '/chart-maps?tab=gajjala'");
      if (!/^export const GG_LANE_TO = '\/trading\?view=gajjala';$/m.test(nav)) errs.push("navSearch.ts must export GG_LANE_TO = '/trading?view=gajjala'");
      const block = (/export const GAJJALA_ENTRIES: ExtraEntry\[\] = \[[\s\S]*?\n\];/.exec(nav) || [''])[0];
      if (!block) errs.push('navSearch.ts must define export const GAJJALA_ENTRIES: ExtraEntry[] = [ … ];');
      else {
        if (!/\.\.\.GG_SUBS\.map\(\(s\) => \(\{/.test(block)) errs.push('GAJJALA_ENTRIES must spread ...GG_SUBS.map((s) => ({ … })) — one generated row per sub');
        if (!/to: `\$\{GG_TAB_TO\}&\$\{GG_SUB_PARAM\}=\$\{s\.key\}`/.test(block)) errs.push('each sub row must route `${GG_TAB_TO}&${GG_SUB_PARAM}=${s.key}`');
        if (/sub=[a-z_]+/.test(block)) errs.push('GAJJALA_ENTRIES types a sub key (sub=…) — the keys come from GG_SUBS only');
        if (/bounce/i.test(block)) errs.push('GAJJALA_ENTRIES says "bounce" — "reversal", never "bounce", on a surface he reads');
        if (!/parent: 'trading', to: GG_LANE_TO/.test(block)) errs.push('the 🚩 lane row must sit under parent trading with to: GG_LANE_TO');
        if (!/parent: 'chart-maps', to: GG_TAB_TO, label: GG_TAB_LABEL/.test(block)) errs.push('the tab row must be { parent: chart-maps, to: GG_TAB_TO, label: GG_TAB_LABEL }');
      }
      if (!/^\s*\.\.\.GAJJALA_ENTRIES,$/m.test(nav)) errs.push('EXTRA_ENTRIES must spread ...GAJJALA_ENTRIES');
      // the sub-word map names only real subs (a typo would silently add nothing)
      const words = (/const GG_SUB_WORDS: Record<string, string\[\]> = \{([\s\S]*?)\n\};/.exec(nav) || ['', ''])[1];
      if (!words) errs.push('navSearch.ts must define const GG_SUB_WORDS: Record<string, string[]> = { … };');
      const gg = tryRead('src/lib/gajjala.ts', 'the sub strip');
      const strip = (/export const GG_SUBS[\s\S]*?\n\];/.exec(gg) || [''])[0];
      const subKeys = [...strip.matchAll(/\{ key: '([a-z_]+)', emoji:/g)].map((m) => m[1]);
      if (gg && subKeys.length < 10) errs.push(`gajjala.ts GG_SUBS lists ${subKeys.length} subs — expected the ten (2026-10-13 DECISIONS order)`);
      for (const m of words.matchAll(/^\s*([a-z_]+):\s*\[/gm)) if (gg && !subKeys.includes(m[1])) errs.push(`GG_SUB_WORDS names '${m[1]}', which is not a GG_SUBS key`);
      if (/bounce/i.test(words)) errs.push('GG_SUB_WORDS says "bounce"');
      // the tab label is the Chart Maps tab label
      const cm = tryRead('src/lib/chartMaps.ts', 'TAB_META');
      const tabLabel = (/\n\s*gajjala: \{\s*\n\s*label: "([^"]+)"/.exec(cm) || [])[1];
      if (cm && !tabLabel) errs.push('chartMaps.ts TAB_META.gajjala.label not found');
      if (tabLabel && !nav.includes(`const GG_TAB_LABEL = "Chart Maps ▸ 🚩 ${tabLabel}";`)) errs.push(`navSearch.ts GG_TAB_LABEL must be "Chart Maps ▸ 🚩 ${tabLabel}" (== TAB_META.gajjala.label)`);
      // synonyms: 'chart-maps' answers to gajjala
      if (!/'chart-maps':\s*\[[^\]]*'gajjala'/.test(nav)) errs.push("NAV_SYNONYMS['chart-maps'] must carry 'gajjala'");
      // the tests read the same strip and keep the negatives
      const t = tryRead('src/lib/navSearch.test.ts', 'the tests');
      if (t && !/import \{ GG_SUBS, GG_SUB_PARAM, parseGgSub \} from '\.\/gajjala';/.test(t)) errs.push('navSearch.test.ts must read GG_SUBS + parseGgSub from ./gajjala (one row per sub, each URL resolving to its sub)');
      if (t && !/NEGATIVE: no row types "bounce"/.test(t)) errs.push('navSearch.test.ts lost the "bounce" negative');
      if (t && !/NEGATIVE: no lane row without Trading in the menu/.test(t)) errs.push('navSearch.test.ts lost the no-Trading negative');
      // the ✨: FIRST, routed to the tab, his line verbatim, no digit in the label.
      const nf = tryRead('src/lib/newFeatures.ts', 'the ✨');
      const arr = nf.slice(nf.indexOf('export const NEW_FEATURES'));
      const ID = 'chart-maps-gajjala-global-search-2026-10-21';
      // 2026-10-21, evening: the 📬 push delivery receipts ✨ (alerts-push-delivery-receipts-2026-10-21, its own block, FIRST) lands above this one — the FIRST pin widened to the top two, dated.
      const firstTwo = [...arr.matchAll(/\{ id: '([^']+)'/g)].slice(0, 2).map((m) => m[1]);
      if (nf && !firstTwo.includes(ID)) errs.push(`the ✨ '${ID}' must be one of the first two in NEW_FEATURES (found ${firstTwo.join(', ') || 'none'})`);
      const at = arr.indexOf(`{ id: '${ID}'`);
      if (at >= 0) {
        const entry = arr.slice(at, arr.indexOf('}', arr.indexOf('label:', at)) + 1);
        if (!entry.includes("route: '/chart-maps?tab=gajjala'")) errs.push('the ✨ must route to /chart-maps?tab=gajjala');
        if (!entry.includes('“Also I need this tab and its subtabs sercheable in global search”')) errs.push('the ✨ must quote his line verbatim');
        const label = (/label: "([^"]*)"/.exec(entry) || ['', ''])[1];
        if (/\d/.test(label)) errs.push('the ✨ label types a digit — nothing here is a number of his');
      }
      return errs;
    },
  },
  {
    name: '📬 Push delivery receipts (2026-10-21)',
    file: '../backend/push/receipts.py',
    // Ajay 2026-10-21 ~16:05 ET, on the 15:36:15 ET 🚩 gajjala_setup NIXX push that push_history recorded as sent 3 /
    // failed 0: "Oh man I did not get an A+ alert for it then today" — "Yes POLA reached and SAIQ too". `sent` is the push
    // SERVICE accepting the message; the receipt is the device's screen. The chain: sender stamps push_id → sw.js echoes it
    // after showNotification → POST /push/receipt (public path, the subscription endpoint is the credential) → one receipt
    // per device on the history row → push/recent serves `shown_on` → /alerts prints `text` verbatim. Never an endpoint or
    // a key stored or served; sent/failed/total never changed by a receipt.
    checks: (rc) => {
      const errs = [];
      const tryRead = (rel, who) => { try { return read(rel); } catch { errs.push(`${rel} is unreadable (${who})`); return ''; } };
      const pyNoComments = (x) => x.replace(/#[^\n]*/g, '');
      const HIS = ['Oh man I did not get an A+ alert for it then today', 'Yes POLA reached and SAIQ too'];
      // 1. receipts.py: the path, sha1 of the endpoint, no auth dependency, the served sentence builder.
      const rcc = pyNoComments(rc);
      if (!/^RECEIPT_PATH = "\/push\/receipt"/m.test(rc)) errs.push('receipts.RECEIPT_PATH must be "/push/receipt"');
      if (!/hashlib\.sha1\(/.test(rcc)) errs.push('receipts.endpoint_hash must be sha1 of the endpoint');
      if (/current_user_email/.test(rcc)) errs.push('the receipt route must take NO auth dependency — the SW may have no session cookie');
      if (!/"receipts\.sub": \{"\$ne": h\}/.test(rcc)) errs.push('record_receipt must refuse a second receipt from the same device (receipts.sub $ne)');
      if (/\$set[^\n]*(sent|failed|total)/.test(rcc)) errs.push('record_receipt must never write sent / failed / total');
      if (!/def shown_on\(/.test(rc)) errs.push('receipts.shown_on is gone');
      if (!/f"shown on \{shown\} of \{total\} device/.test(rc)) errs.push('shown_on.text must lead "shown on N of M device(s)"');
      if (!/; no receipt from /.test(rc)) errs.push('shown_on.text must name the silent devices ("; no receipt from …")');
      // 2. the sender stamp — both send paths hand the SAME id to the devices and to history.
      const sender = tryRead('../backend/push/sender.py', 'sender');
      if (sender) {
        const sc = pyNoComments(sender);
        if (!/device\["push_id"\] = push_id/.test(sc)) errs.push('sender._fan_out must stamp push_id on the DEVICE dict');
        if (!/device = dict\(device_payload\(payload\)\)/.test(sc)) errs.push('the device dict must be a COPY (the caller\'s payload is never mutated)');
        if ((sc.match(/push_id=push_id, targets=target_rows/g) || []).length !== 2) errs.push('both send_to_all and send_to_user must record push_id + targets');
        if (/payload\["push_id"\]/.test(sc)) errs.push('the caller\'s payload must never get push_id written into it');
      }
      // 3. history: the sparse index and the two optional fields; a legacy call stores neither.
      const hist = tryRead('../backend/push/history.py', 'history');
      if (hist) {
        if (!/create_index\("push_id", sparse=True\)/.test(hist)) errs.push('push_history needs the sparse push_id index');
        if (!/push_id: Optional\[str\] = None,\s*\n\s*targets: Optional\[list\] = None/.test(hist)) errs.push('history.record must take push_id / targets as optional kwargs');
        if (!/if push_id:\s*\n\s*doc\["push_id"\] = str\(push_id\)/.test(hist)) errs.push('history.record must store push_id only when given (a legacy row reads "before receipts")');
      }
      // 4. recent: shown_on on every push row; the hashes never leave the server.
      const recent = tryRead('../backend/push/recent.py', 'recent');
      if (recent) {
        if (!/p\["shown_on"\] = _shown_on\(p\)/.test(recent)) errs.push('push/recent must serve shown_on on every push row');
        for (const k of ['receipts', 'targets', 'push_id']) if (!recent.includes(`p.pop("${k}", None)`)) errs.push(`push/recent must strip "${k}" before serving`);
      }
      // 5. main.py: public path + the router.
      const main = tryRead('../backend/main.py', 'main');
      if (main) {
        const at = main.indexOf('_PUBLIC_API_PATHS = {');
        const block = at < 0 ? '' : main.slice(at, main.indexOf('}', at));
        if (!/"\/push\/receipt",/.test(block)) errs.push('main._PUBLIC_API_PATHS must list "/push/receipt" (the SW posts without a session)');
        if (!main.includes('app.include_router(push_receipts_router)')) errs.push('main.py must include push.receipts.router');
      }
      // 6. sw.js: the receipt FOLLOWS showNotification; three keys; never a key or content.
      const sw = tryRead('public/sw.js', 'sw');
      if (sw) {
        const show = sw.indexOf('self.registration.showNotification(title, options)');
        if (show < 0 || !sw.slice(show, show + 200).includes('.then(() => sendReceipt(payload)')) errs.push('sw.js must post the receipt AFTER showNotification resolves');
        if (!/fetch\(`\$\{cfg\.api\}\/push\/receipt`/.test(sw)) errs.push('sw.js must POST to <api>/push/receipt via the shared config');
        if (!/credentials: 'include'/.test(sw.slice(sw.indexOf('async function sendReceipt(')))) errs.push('the receipt fetch must send credentials');
        const rb = sw.slice(sw.indexOf('function receiptBody('), sw.indexOf('\n}\n', sw.indexOf('function receiptBody(')));
        if (!rb.includes('push_id: payload.push_id, endpoint: endpoint, shown_at: Date.now()')) errs.push('receiptBody must be exactly {push_id, endpoint, shown_at}');
        if (/keys|title|body:/.test(rb.replace(/payload\.push_id/g, ''))) errs.push('receiptBody must carry no key and no content');
      }
      // 7. the page prints the served words; the row type carries the block.
      const page = tryRead('src/pages/Alerts.tsx', 'page');
      if (page) {
        if (!page.includes('data-testid="alert-shown-on"') || !page.includes('{row.shown_on.text}')) errs.push('Alerts.tsx must print row.shown_on.text verbatim under data-testid="alert-shown-on"');
        if (/shown on \$\{|`shown on /.test(page)) errs.push('Alerts.tsx composes its own "shown on" sentence — the server owns the words');
      }
      const hook = tryRead('src/hooks/useAlertHistory.ts', 'hook');
      if (hook && !/shown_on\?: ShownOnBlock \| null;/.test(hook)) errs.push('AlertRow must carry shown_on?: ShownOnBlock | null');
      // 8. tests, both sides, with their NEGATIVEs.
      if (!exists('../backend/tests/test_push_receipts_2026_10_21.py')) errs.push('backend/tests/test_push_receipts_2026_10_21.py is missing');
      const bt = tryRead('../backend/tests/test_push_receipts_2026_10_21.py', 'backend tests');
      for (const name of ['test_NEGATIVE_a_receipt_never_changes_sent_failed_total', 'test_NEGATIVE_legacy_record_call_stores_neither_key',
        'test_unknown_endpoint_unknown_push_and_another_users_row_all_answer_404', 'test_recent_serves_shown_on_and_never_the_hashes']) {
        if (bt && !bt.includes(name)) errs.push(`test_push_receipts_2026_10_21.py must keep ${name}`);
      }
      const st = tryRead('src/lib/swReceipt.test.ts', 'sw test');
      for (const name of ['NEGATIVE: a payload without push_id', 'NEGATIVE: a receipt that fails never rejects the push event', 'NEGATIVE: a failed showNotification posts no receipt']) {
        if (st && !st.includes(name)) errs.push(`swReceipt.test.ts must keep the test "${name}"`);
      }
      const at2 = tryRead('src/pages/Alerts.receipts.test.tsx', 'page test');
      if (at2 && !at2.includes('NEGATIVE: a row from before receipts (shown_on null)')) errs.push('Alerts.receipts.test.tsx must keep the legacy-row NEGATIVE');
      // 9. docs + SPECS.
      if (!exists('../docs/notifications/push_delivery_receipts_2026_10_21.md')) errs.push('docs/notifications/push_delivery_receipts_2026_10_21.md is missing');
      const specs = tryRead('../SPECS.md', 'specs');
      if (specs && !specs.includes('`/push/receipt`')) errs.push('SPECS.md must carry the /push/receipt line');
      // 10. the ✨ entry: FIRST, routed to /alerts, both his lines verbatim, UNMEASURED, no digit outside his quotes.
      const nf = read('src/lib/newFeatures.ts');
      const ID = 'alerts-push-delivery-receipts-2026-10-21';
      const arr = nf.slice(nf.indexOf('export const NEW_FEATURES'));
      const firstId = ((/\{ id: '([^']+)'/.exec(arr)) || [])[1];
      if (firstId !== ID) errs.push(`the ✨ entry '${ID}' must be FIRST in NEW_FEATURES (found ${firstId || 'none'})`);
      const at3 = arr.indexOf(`{ id: '${ID}'`);
      if (at3 < 0) errs.push(`newFeatures.ts lacks the '${ID}' highlight`);
      else {
        const nextAt = arr.indexOf("{ id: '", at3 + 1);
        const e = arr.slice(at3, nextAt < 0 ? undefined : nextAt);
        const label = (/label: "([^"]*)"/.exec(e) || [])[1] || '';
        const W = 'the 📬 ✨ entry';
        if (!e.includes("route: '/alerts'")) errs.push(`${W} must route to '/alerts'`);
        for (const h of HIS) if (!label.includes(`“${h}”`)) errs.push(`${W} must quote verbatim: “${h.slice(0, 40)}…”`);
        for (const need of ['no receipt', 'never corrects', 'UNMEASURED']) if (!label.includes(need)) errs.push(`${W} must say "${need}"`);
        if (!label.endsWith('Not advice.')) errs.push(`${W} must end "Not advice."`);
        if (/boun/i.test(label)) errs.push(`${W} says the b-word`);
        let outside = label;
        for (const h of HIS) outside = outside.split(`“${h}”`).join('');
        const d = outside.match(/\d+/);
        if (d) errs.push(`${W} types "${d[0]}" outside his quotes — the counts are served`);
        if (!/\d/.test(`${outside} 3 devices`)) errs.push('self-test: a typed number outside the quote was not caught');
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
