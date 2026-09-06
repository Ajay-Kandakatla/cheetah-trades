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
      if (tabs.indexOf('ict') !== tabs.indexOf('zones') + 1) {
        errs.push("'ict' must sit directly after 'zones' (the old Into Supply slot)");
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
      if (tabs.indexOf('catalysts') !== tabs.indexOf('overnight') + 1) {
        errs.push("'catalysts' must sit directly after 'overnight' (both are movers boards)");
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
      if (!/export const ROOM_TABS:\s*CmTab\[\]\s*=\s*\['zones',\s*'deep_demand',\s*'quick_bounce'\]/.test(cm)) {
        errs.push("chartMaps.ts ROOM_TABS is not exactly ['zones', 'deep_demand', 'quick_bounce'] (Quick Bounce joined the room-gated boards 2026-09-06)");
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
