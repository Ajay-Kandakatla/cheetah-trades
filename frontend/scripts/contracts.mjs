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
    name: 'Chart Maps Deep Demand opens with the breaking-resistance board (2026-09-03)',
    file: 'src/pages/ChartMaps.tsx',
    // "and also in to deep demand zones". Gated to the deep_demand tab only —
    // VCP / winners / zero-DTE must not grow a supply read — and above the
    // tile grid, which is what "opens with" means.
    checks: (src) => {
      const errs = [];
      if (!/import\s*\{[^}]*\bZoneEdgeBoard\b[^}]*\}\s*from\s*'\.\.\/components\/ZoneEdgeBoard'/.test(src)) {
        errs.push("ChartMaps.tsx no longer imports ZoneEdgeBoard from '../components/ZoneEdgeBoard'");
      }
      const i = src.indexOf('<ZoneEdgeBoard');
      if (i < 0) return [...errs, 'ZoneEdgeBoard mount missing from ChartMaps'];
      const tag = src.slice(i, src.indexOf('/>', i));
      if (!/\bmode="breaking"/.test(tag)) errs.push('ChartMaps must mount ZoneEdgeBoard with mode="breaking"');
      if (!/\bcompact\b/.test(tag)) errs.push('ChartMaps mount lacks `compact` — the tab already explains itself');
      const gate = src.slice(Math.max(0, i - 120), i);
      if (!/tab === 'deep_demand'\s*&&\s*\(\s*$/.test(gate)) {
        errs.push("ZoneEdgeBoard mount is not gated on tab === 'deep_demand'");
      }
      const grid = src.indexOf('<div className="cm-grid">');
      if (grid >= 0 && i > grid) errs.push('ZoneEdgeBoard must render ABOVE the tile grid');
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
      if (!/supply_break_alert:\s*true/.test(ess)) errs.push('Essentials preset drops supply_break_alert');
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
