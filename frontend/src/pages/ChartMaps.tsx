/* /chart-maps — the charts-only study board.
 *
 * Ajay 2026-08-15: "I need just maps that you are pulling show… The goal for
 * me is to look at patterns and learn them day by day… Also with then that
 * page show me a previously winning stocks with similar patterns."
 *
 * Three tabs, one tile shape:
 *   📐 Strong VCP    — tight bases from the SEPA scan, base box + pivot + stop
 *   🟢 Back in Demand — pullbacks into a demand zone, band + buy/stop/target
 *   🏆 Past Winners   — setups from OUR ledger that hit target before stop
 *
 * Deliberately no tables. The scanners already have those; this page is the
 * visual index over them, and every tile clicks through to the SEPA detail.
 *
 * HONESTY: tab 3 shows a measured sample of what happened, with the stop-first
 * losses stated next to the wins. Win rates are never compared BETWEEN
 * patterns — their stop brackets differ ~2x, which is the exact comparison the
 * 2026-07-10 pattern audit found broken.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { PatternChart } from '../components/PatternChart';
import { PatternsBoard } from './PatternsPage';
import { InfoButton } from '../components/InfoButton';
import {
  CM_TABS, DEFAULT_MIN_TIER, DEFAULT_SORT, ENTERABLE_KIND, TAB_META, THEMES_FIRST_DEFAULT,
  quickBounceStudyText, quickBouncePersistenceText, tabUsageKey, breakingPassText, lidBreakStudyText, sessionNoteText,
  WINNER_SOURCES, boardQuery, isBoardTab, ROOM_TABS, DEFAULT_MIN_ROOM, parseMinRoom,
  parseGrades, gradesParam,
  DEEP_LEVELS, DEEP_LEVEL_LABEL, parseLevels, levelsParam, AMD_GRADE_LABEL,
  AMD_FLIGHT_LABEL, parseFlight, flightParam,
  UNHIDE_PARAM, parseUnhide, unhideParam,
  dataThrough, isThinSample, parseSort, parseSource, parseTab, parseTier,
  recordLine, scanStamp,
  DEFAULT_ICT_BIAS, DEFAULT_ICT_MICRO, ICT_BIASES, ICT_LEGEND, ICT_MICROS,
  ICT_SOURCE, ictParamRows, ictSource, parseBias, parseMicro,
  type CmBoard, type CmTab,
} from '../lib/chartMaps';
// The room floor's TWO states come from the one shared list (2026-09-17) — the
// same array the Back in Demand panel renders. See lib/bounceRoom.ts.
import { ROOM_FLOORS } from '../lib/bounceRoom';

/** This toolbar's label for a room floor. The FLOORS are shared (bounceRoom's
 *  ROOM_FLOORS, so the panel and the tiles can never offer different ones); the
 *  WORDING is local, because a dense tile toolbar labels tighter than a panel
 *  select and these buttons have read this way since 2026-09-05.
 *
 *  ONE function, used by the buttons AND by the hidden-count readout that tells
 *  him which button to press — naming a control with a string the control does
 *  not carry is how a readout starts pointing at nothing. */
export function cmRoomLabel(floor: number): string {
  return floor === 0 ? 'Any room' : `🧱 Room ≥ ${floor}%`;
}
const CM_ANY_ROOM_LABEL = cmRoomLabel(0);
import { SupportLevels } from '../components/SupportLevels';
import { SignalLabBoard } from '../components/SignalLabBoard';
import { HottestSectors } from '../components/HottestSectors';
import { ExplosiveGrowth } from '../components/ExplosiveGrowth';
import GntBoard from '../components/GntBoard';
import BondeBoard from '../components/BondeBoard';
import { OvernightGappers } from '../components/OvernightGappers';
import SessionBoard from '../components/SessionBoard';
import HoldingsBoard from '../components/HoldingsBoard';
import PotusBoard from '../components/PotusBoard';
import IpoUpcomingStrip from '../components/IpoUpcomingStrip';
import HotSectors from '../components/HotSectors';
import IndexZones from '../components/IndexZones';
import OverlayLegend from '../components/OverlayLegend';
import { filterForGrid, filterTile, hiddenForTab, loadHidden, presentGroups,
         saveHidden, studiesWanted, tabFamily } from '../lib/chartOverlays';

/** Stable empty set so `lockedOverlays` keeps identity on every non-🌀 tab. */
const EMPTY_LOCK: Set<string> = new Set();
import { normalizeSymbol, parseTf, parseWindow } from '../lib/supportLevels';
import { useSepaScanStream } from '../hooks/useSepaScanStream';
import { SepaScanProgress } from '../components/SepaScanProgress';
import { DemandScanProgress } from '../components/DemandScanProgress';
import { useDemandScanProgress } from '../hooks/useDemandScanProgress';
import { CatalystsBoard } from '../pages/Catalysts';
import { HotPullbackBoard } from '../components/HotPullbackBoard';
import { useMyFeatures } from '../hooks/useMyFeatures';
import { RulesInfo } from '../components/RulesInfo';
import { EnterableOnlyToggle } from '../components/EnterableOnlyToggle';
import { HiddenCount } from '../components/HiddenCount';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { partitionEnterable, type EnterableRead } from '../lib/enterable';
import { BAND_STRUCTURE_KIND_NA, BAND_STRUCTURE_NA_TEXT } from '../lib/bandStructure';
import { StudyNote } from '../components/StudyNote';
import { trackFeature } from '../lib/usageTracker';

/** Background refetch cadence for a left-open tab. Slower than the 10s
 *  warming poll on purpose — this is drift correction, not live data. */
const BOARD_REFRESH_MS = 5 * 60_000;

/* One universe (Ajay 2026-08-25: "Remove all these themes and just do
 * default universe scan"). The picker is gone with it — the server collapses
 * every legacy key to the SEPA `full` alias, so old bookmarked URLs still
 * resolve. */
const UNIVERSE = 'full';

const HowItWorks = (
  <>
    <p>A study board — the same scans you already run, shown as charts instead
      of rows, so the shape is what you remember.</p>
    <p><strong>Order.</strong> The tabs run most-used first (2026-09-06): the
      demand boards lead and a bare Chart Maps link opens on Back in Demand;
      the SEPA slices and the study boards follow. Every tab open is counted,
      so the order is re-cut from the numbers rather than from memory.</p>
    <ul>
      <li><strong>🟢 Back in Demand</strong> — price left a demand zone and has
        come back into it. Band is the zone; BUY / STOP / TARGET are the plan.</li>
      <li><strong>🚀 Breaking</strong> — the zone-edge pass as cards (2026-09-06):
        $1B+ names within 1% under the ceiling of their last supply band, or
        through it today by up to 3%, broke-today first. Red band is the
        ceiling, the dashed line its top, a second band the next proven lid.
        It was the text list on top of Deep Demand; Deep Demand is cards only now.</li>
      <li><strong>📐 Strong VCP</strong> — the SEPA scan named VCP as the entry
        setup <em>and</em> the base scored tight (≥70). The green box is the
        base, the solid line the pivot, the dashed line the suggested stop.</li>
      <li><strong>🧭 ICT</strong> — took the Into Supply slot on 2026-09-03.
        Two clocks: the daily chart sets the key levels (3-candle fractal
        swings and open fair value gaps) and the 60-minute loop wakes only
        when one is tapped. It then looks for the manipulation (a wick through
        the level that fails to close through it), the energetic push back
        that leaves a new gap, the market structure shift, and the inverted-FVG
        entry. Stop under the manipulation wick, target at the next daily
        swing. Every threshold the video does not give is an owner setting,
        listed under the board. No moving averages anywhere in it.</li>
      <li><strong>🗞️ Catalysts</strong> — moved here from its own page on
        2026-09-05. Microcaps moving on a catalyst or chatter, scored on chatter
        vs evidence; cards lead with room to the first supply band overhead
        (open sky first, then the biggest gap) and flag names reversing off a
        demand band. Room and the reversal read are a configured price-structure read
        shared with the Demand board — owner settings, not advice.</li>
      <li><strong>📏 Support Levels</strong> — the only tab that is not a board.
        Search any ticker and pick a zoom (opens on 1 year since 2026-09-06). The
        same clustering rule runs over a 1-month to 5-year frame, and the answers differ on
        purpose: a short read finds the level this week's trade is standing on,
        a long one finds the structural floor. A ● marks a level price has
        actually tested inside the last month — untested year-old structure and
        last week's floor are both support and are not the same claim.</li>
      <li><strong>🏆 Past Winners</strong> — recorded setups that touched their
        measure-rule target <em>before</em> their stop, within 21 bars. The
        dotted vertical is the confirmation bar: study the base to the LEFT of
        it, because that is all you could see at the time.</li>
    </ul>
    <p><strong>Themes.</strong> The S&P indices require positive earnings and US
      domicile, so no quantum name, and none of OKLO / SMR / NNE / ARM, can be
      in them. Those arrive from a hand-kept theme list and are tagged. They
      pass the same trend, knife and liquidity filters as everything else.</p>
    <p><strong>What the win rates are not.</strong> Each pattern's record is read
      against its own target and stop distance. A cup's handle stop is tight and
      a double bottom's stop is far below entry, so a higher win rate does not
      mean a better pattern. Small samples stay labelled as small.</p>
  </>
);

export function ChartMaps() {
  const [params, setParams] = useSearchParams();
  // The Catalysts tab (2026-09-05) mounts a board that is its own access
  // feature (`catalysts`, backend/access/store.py) — being allowed on Chart
  // Maps does not grant it. Offer the tab, and honour ?tab=catalysts, only
  // when the user has it; otherwise the deep link lands on the first tab like
  // any unknown value. Permissive while the features fetch is in flight (the
  // FeatureRoute around this page has already waited for it in practice).
  const feats = useMyFeatures();
  const canCatalysts = !feats.loaded || feats.features.has('catalysts');
  const tabs = canCatalysts ? CM_TABS : CM_TABS.filter((t) => t !== 'catalysts');
  const rawTab = parseTab(params.get('tab'));
  const tab = rawTab === 'catalysts' && !canCatalysts ? parseTab(null) : rawTab;
  // Count every tab open (landing or click) — Ajay 2026-09-06: "Move most
  // used tabs to the beginning of the list"; nothing had recorded which tab
  // was open, so the strip's order is re-cut from these counts (Mongo
  // usage_stats `feature:chart-maps:tab:<tab>`). Best-effort, never blocks.
  useEffect(() => { trackFeature(tabUsageKey(tab)); }, [tab]);
  const pattern = params.get('pattern');
  const source = parseSource(params.get('source'));
  // Chart window. Per-tab defaults live on the backend; this only widens the
  // VCP/zones view when Ajay wants more context. Measured legibility ceiling is
  // 255 bars on a Retina display and 127 on a non-Retina one, so 252 is the top
  // option — see docs/sepa/chart_timeframes.md.
  const days = Number(params.get('days')) || undefined;
  const minerviniOnly = params.get('minervini') === 'true';
  const sort = parseSort(params.get('sort'));
  const minTier = parseTier(params.get('min_tier'));
  /* Support tab. Both live in the URL so a level read is shareable and a
   * refresh does not drop you back on an empty search box. */
  const supportSymbol = normalizeSymbol(params.get('symbol'));
  const supportWindow = parseWindow(params.get('window'));
  const supportTf = parseTf(params.get('tf'));
  const universe = UNIVERSE;
  /* Reaching vs already reached (Ajay 2026-08-31: "give me toggle reaching vs
   * already reached"). URL-backed so a refresh or a shared link keeps the
   * moment being looked at; only the non-default value is written. */
  const LENS_TABS = tab === 'undervalue' || tab === 'gabbar';
  const rawPhase = params.get('phase');
  // Demand boards have two moments (default reached); the lens tabs have
  // three (default All — their population is a screen the lens narrows).
  const phase = rawPhase === 'approaching' ? 'approaching'
    : rawPhase === 'reached' ? 'reached'
    : LENS_TABS ? 'all' : 'reached';
  const target = params.get('target') === 'order_block' ? 'order_block' : 'zone';
  const setPhase = (v: string) => {
    const next = new URLSearchParams(params);
    if (v === 'approaching') next.set('phase', 'approaching');
    else if (v === 'reached' && LENS_TABS) next.set('phase', 'reached');
    else next.delete('phase');
    setParams(next, { replace: true });
  };
  const setTarget = (v: string) => {
    const next = new URLSearchParams(params);
    if (v === 'order_block') next.set('target', 'order_block');
    else next.delete('target');
    setParams(next, { replace: true });
  };
  /* Room floor (Ajay 2026-09-05: "I need the same logic in Demand and deep
   * demand zone. So that there are stocks that have more room atleast >5%").
   * URL-backed like phase; only the OFF value is written (`room=any`) so the
   * plain tab URL keeps the floor. The floor itself is applied on the server
   * against the LIVE print — the page only asks for it and reports the count. */
  /* 🎯 ENTERABLE (Ajay 2026-09-15: "I only wanna see the stocks that are
   * enterable ... I do not want to see not enterable alerts or stocks in any of
   * the chart maps"). ON by default, which is the ask — so the state that has
   * to be visible is the OFF one, and it lives in the URL as `?show=all` and
   * nowhere else. No localStorage: a filter he cannot see the state of is a
   * filter that quietly eats a board tomorrow.
   *
   * The KIND is SERVED (`enterable_kind`) with the local map as the fallback
   * before the first payload lands, so moving a tab between `demand` and `n/a`
   * (his call, spec §7.16) is a backend change, not a deploy. */
  const enterableOnly = params.get('show') !== 'all';
  const setEnterableOnly = useCallback((v: boolean) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (v) next.delete('show'); else next.set('show', 'all');
      return next;
    }, { replace: true });
  }, [setParams]);

  /* 🎯 UN-HIDE BY REASON (Ajay 2026-09-17: "Can you give me a toggle for the
   * room too? I am not seeing all stocks on the selected filter due to this
   * now"). Every reason the count line already prints becomes a button; the
   * set of un-hidden CODES lives in the URL as `?unhide=room,proximity` and
   * nowhere else — same rule as `?show=all`, and for the same reason.
   *
   * It changes WHAT IS DRAWN and nothing else. An un-hidden row is the served
   * BLOCKED: it keeps its ⛔ chip, the phone still will not page it, and no
   * lane will enter it. Nothing here reaches the server — the reason list is
   * already on every row.
   *
   * ONE stable reference for the page (memoised on `params`), handed to the
   * provider and to the grid's own partition, so a chip can never light up
   * while the rows sit still. */
  const unhide = useMemo(() => parseUnhide(params.get(UNHIDE_PARAM)), [params]);
  const toggleReason = useCallback((code: string) => {
    setParams((prev) => {
      // Read the CURRENT param, never a captured copy: clicking `room` and then
      // `not at band` must write both, not replace the first.
      const sel = parseUnhide(prev.get(UNHIDE_PARAM));
      if (sel.has(code)) sel.delete(code); else sel.add(code);
      const spec = unhideParam(sel);
      const next = new URLSearchParams(prev);
      if (spec) next.set(UNHIDE_PARAM, spec); else next.delete(UNHIDE_PARAM);
      return next;
    }, { replace: true });
  }, [setParams]);

  const ROOM_TAB = ROOM_TABS.includes(tab);
  const minRoom = parseMinRoom(params.get('room'));
  const setRoom = (v: 'floor' | 'any') => {
    const next = new URLSearchParams(params);
    if (v === 'any') next.set('room', 'any'); else next.delete('room');
    setParams(next, { replace: true });
  };
  /* 🩹 Deep Demand arrival level (Ajay 2026-09-16: "can you do level 4 and give
   * me filters for that"). Multi-select, all three ON by default — which is the
   * same board as no filter at all, so only a NARROWING selection is written to
   * the URL (`?levels=3,4`), exactly like phase and room. Turning every chip off
   * is meaningless and normalises back to all: the page can never ask for an
   * empty board, and neither can a hand-typed URL (the parser fails open, as
   * does the server's). NOT `?level=` — that one is the gabbar tab's band-type
   * lens and is untouched. */
  /* 🌀 AMD grade filter (Ajay 2026-09-17: "I wanna see all AMD and also
   * filterable AMD ... I wanna know any new stocks are are are getting
   * manipulated and about to be Distrubuted too ... Feel free to bring stocks
   * that are getting distributed too but I need to see it as a filter").
   *
   * The nightly sweep stores every name at every grade; this tab served only
   * the turning one and dropped 86% of its own document. Multi-select, and
   * NOTHING selected normalises back to the server default (the turning grade)
   * rather than asking for an empty board — same rule as the level chips. */
  /** The server's own ceiling (chart_maps.board.LIMIT_MAX). Asking for less is
 *  how "Showing 24 of 587" happened. */
const BOARD_LIMIT = 80;

const GRADE_TAB = tab === 'amd' || tab === 'keltner';
  const gradeSel = useMemo(() => parseGrades(params.get('grades')), [params]);
  // No `grades_all` collapse here: this runs before `data` exists, and the
  // explicit list says the same thing to the server as "all" does.
  const gradesSpec = GRADE_TAB ? (gradesParam(gradeSel) ?? undefined) : undefined;
  const toggleGrade = (g: string) => {
    const sel = new Set(gradeSel);
    if (sel.has(g)) sel.delete(g); else sel.add(g);
    const spec = gradesParam(sel);
    const next = new URLSearchParams(params);
    if (spec) next.set('grades', spec); else next.delete('grades');
    setParams(next, { replace: true });
  };

  /* 🔻 The AMD cycle IN FLIGHT (Ajay 2026-09-17: "Today its not granular we do
   * not show potentially or in the flight mani pulation i wanna see those").
   * Live states, read against the base edge on today's own low — unconfirmed
   * until the close, and the control says so. AMD only. */
  const FLIGHT_TAB = tab === 'amd';
  const flightSel = useMemo(() => parseFlight(params.get('flight')), [params]);
  const flightSpec = FLIGHT_TAB ? (flightParam(flightSel) ?? undefined) : undefined;
  const toggleFlight = (k: string) => {
    const sel = new Set(flightSel);
    if (sel.has(k)) sel.delete(k); else sel.add(k);
    // Passing the universe here (a closure, so `data` exists by now) lets an
    // ALL-selected set collapse to no param — every state on is the same board
    // as no filter, and a URL that says so would send a pointless narrowing.
    const spec = flightParam(sel, data?.flight_states);
    const next = new URLSearchParams(params);
    if (spec) next.set('flight', spec); else next.delete('flight');
    setParams(next, { replace: true });
  };

  const DEEP_TAB = tab === 'deep_demand';
  const levelSel = useMemo(() => parseLevels(params.get('levels')), [params]);
  const levelsSpec = levelsParam(levelSel) ?? 'all';
  const toggleLevel = (n: number) => {
    const sel = new Set(levelSel);
    if (sel.has(n)) sel.delete(n); else sel.add(n);
    const spec = levelsParam(sel);
    const next = new URLSearchParams(params);
    if (spec) next.set('levels', spec); else next.delete('levels');
    setParams(next, { replace: true });
  };
  const [gabbarLevel, setGabbarLevel] = useState('all');
  const [gabbarTouchingOnly, setGabbarTouchingOnly] = useState(false);
  /* ICT (Ajay 2026-09-03): which side of the sweep, and which trigger clock.
   * URL-backed like phase/target so a shared link keeps the read; only the
   * non-default value is written so the plain tab URL stays clean. */
  const bias = parseBias(params.get('bias'));
  const micro = parseMicro(params.get('micro'));
  const setIctParam = (key: 'bias' | 'micro', v: string, dflt: string) => {
    const next = new URLSearchParams(params);
    if (v && v !== dflt) next.set(key, v); else next.delete(key);
    setParams(next, { replace: true });
  };
  const [themesFirst, setThemesFirst] = useState(THEMES_FIRST_DEFAULT);
  const [data, setData] = useState<CmBoard | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  /* Live scan progress. Ajay 2026-08-17: "can you give realtime ticker scan
   * progress like other tabs in SEPA".
   *
   * This board never scans on its own — it reads `scanner.load_latest()` and
   * the demand cache. So the honest wiring is not a fake progress bar over a
   * board fetch: it is the SAME SEPA scan stream the other tabs watch, started
   * from here, with the board reloading when it lands. Same hook, same
   * component, same events — nothing re-implemented. */
  const stream = useSepaScanStream();
  const wasScanning = useRef(false);

  /* Whoever asked LAST owns the board. A cold board computes for seconds, a
   * warm one answers instantly - so flipping tab/phase/target while a slow
   * request is in flight let the STALE response land last and repaint the
   * old board under the new toggles (same race Ajay hit on the Support tab
   * zoom, 2026-08-31). */
  /* Declared ABOVE `load` on purpose: `load`'s dependency array reads it so a
   * study toggle refetches, and a const declared further down is in its
   * temporal dead zone at that point. */
  const [hiddenOverlays, setHiddenOverlays] = useState<Set<string>>(() => loadHidden());

  /* THE ONE BIT OF THE OVERLAY STATE THE FETCH ACTUALLY DEPENDS ON.
   *
   * `load` used to list `hiddenOverlays` itself, and `toggleOverlay` builds a
   * NEW Set on every click — so ticking ANY of the twelve families, including
   * the pure client-side filters (demand, now, trade), rebuilt `load`, flipped
   * the spinner on and refetched all 24 tiles. The 2026-09-12 note promised
   * "it refetches on the CROSSING only"; this is the line that makes that
   * true. Only the boolean crossing changes identity, so a client-side tick
   * stays client-side.
   *
   * `tabHidden` is the same set with the TAB'S OWN family forced visible: both
   * study families are off by default, so KC Coiled would otherwise open as a
   * grid of bare candles with its channel filtered out. */
  const wantStudies = studiesWanted(hiddenOverlays);
  const tabHidden = useMemo(
    () => hiddenForTab(hiddenOverlays, tab), [hiddenOverlays, tab]);
  const lockedOverlays = useMemo(() => {
    const fam = tabFamily(tab);
    return fam ? new Set([fam]) : EMPTY_LOCK;
  }, [tab]);

  const boardSeq = useRef(0);
  const load = useCallback(async () => {
    const my = ++boardSeq.current;
    setErr(null);
    // `/chart-maps` answers an unknown `tab` with the VCP board rather than a
    // 404, so fetching it for the Support tab would quietly draw the wrong
    // charts under the right heading.
    if (!isBoardTab(tab)) { setData(null); setLoading(false); return; }
    /* BOARD_LIMIT — Ajay 2026-09-18: "Only seeing 24 stocks", on an AMD board
     * whose own footer read "Showing 24 of 587 matches". The page had always
     * asked for 24 (gabbar alone asked for 80); the server's ceiling is
     * board.LIMIT_MAX = 80. So every tab now asks for the ceiling.
     *
     * This is NOT the whole fix and the footer still says so: 80 of 587 is
     * still a cut. Reaching all 587 needs paging, which needs LIMIT_MAX to move
     * and a "next" control — a separate build.
     *
     * Safe because the AMD board sorts BEFORE it cuts (turning_bullish.board:
     * `hits.sort(key=_key)` then `hits[:limit]`), so a bigger page is more of
     * the same ranking, not a different one. Where a sort runs AFTER the cut —
     * the 🪜 band-structure ordering — the board already says out loud that it
     * ranks the page, and that stays true at 80. */
    const q = boardQuery({ tab, limit: BOARD_LIMIT, days,
                           universe, themesFirst, pattern,
                           source, minerviniOnly, sort, minTier, gabbarLevel,
                           gabbarTouchingOnly, phase, target, bias, micro,
                           minRoom: ROOM_TAB ? minRoom : undefined,
                           grades: gradesSpec,
                           flight: flightSpec,
                           levels: levelsSpec });
    // The three study overlays are computed server-side and cost real time on
    // 60 tiles, so they are requested ONLY while one of their checkboxes is on
    // (Ajay 2026-09-12: default is supply/demand + order blocks alone).
    const qs = wantStudies ? `${q}&studies=true` : q;
    try {
      const r = await fetch(`${API}/chart-maps?${qs}`, {
        credentials: 'include', cache: 'no-store',
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const payload = await r.json();
      if (my !== boardSeq.current) return;
      setData(payload);
    } catch (e: any) {
      if (my !== boardSeq.current) return;
      setErr(String(e?.message ?? e));
    } finally {
      if (my === boardSeq.current) setLoading(false);
    }
  }, [tab, days, universe, themesFirst, pattern, source, minerviniOnly, sort, minTier, gabbarLevel, gabbarTouchingOnly, phase, target, bias, micro, ROOM_TAB, minRoom, levelsSpec, gradesSpec, flightSpec, wantStudies]);

  useEffect(() => { setLoading(true); void load(); }, [load]);

  // A finished scan rewrites the file this board reads, so pull it again. Edge-
  // triggered on the scanning->done transition, not on `phase === 'done'`,
  // which would refetch on every render once the scan ended.
  useEffect(() => {
    if (stream.scanning) { wasScanning.current = true; return; }
    if (wasScanning.current) {
      wasScanning.current = false;
      void load();
    }
  }, [stream.scanning, load]);

  // The demand board warms in a background thread on the server and answers
  // instantly with warming:true rather than holding the connection open (a
  // cold 1,500-name pass outlives Cloudflare's ~100s cut). Poll until it lands.
  useEffect(() => {
    if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null; }
    if (!data?.warming) return;
    pollRef.current = window.setInterval(() => { void load(); }, 10_000);
    return () => { if (pollRef.current) window.clearInterval(pollRef.current); };
  }, [data?.warming, load]);

  /* A left-open tab is how this board actually gets used — and until
   * 2026-08-25 it NEVER refetched on its own: the zones tab froze at its
   * 10:57 reload and disagreed with the server for an hour while fresh scans
   * landed ("UI is not updating with what you are saying"). Slow clock,
   * visible-tab only, no spinner. The re-render this forces is also what
   * keeps the freshness stamp's "Scanned Xm ago" ticking instead of frozen
   * at whatever it said when the tab was last touched. */
  useEffect(() => {
    const t = window.setInterval(() => {
      if (!document.hidden) void load();
    }, BOARD_REFRESH_MS);
    return () => window.clearInterval(t);
  }, [load]);

  /* The demand scan's live counter, polled faster than the board itself. The
   * board key is the universe the SERVER resolved (`universe_key`) — asking
   * for progress under a key the server didn't scan returns a permanent
   * idle. */
  // The ICT tab warms its OWN engine (ict_board cache), not the demand scan —
  // polling the demand counter for it would report a permanent idle.
  const demandProgress = useDemandScanProgress(
    data?.universe_key || universe, Boolean(data?.warming) && tab !== 'ict');

  /* Freshness line under the toolbar — see the render-site comment. Recomputed
   * per render; the board refetches on every scan/refresh so a live "now" is
   * at most one poll interval stale. */
  const stampPart = scanStamp(data?.generated_at ?? data?.scan_generated_at, Date.now());
  const throughPart = dataThrough(data?.tiles);
  const freshness = !data?.warming && (stampPart || throughPart)
    ? [stampPart, throughPart].filter(Boolean).join(' \u00b7 ')
    : null;

  const setTab = (t: CmTab) => {
    const next = new URLSearchParams(params);
    next.set('tab', t);
    next.delete('pattern');
    setParams(next, { replace: true });
  };

  const setPattern = (p: string | null) => {
    const next = new URLSearchParams(params);
    next.set('tab', 'winners');
    if (p) next.set('pattern', p); else next.delete('pattern');
    setParams(next, { replace: true });
  };

  /* Support tab. Written to the URL, not to component state, so the read is
   * shareable and survives a refresh — the same reason `pattern` lives there.
   * Not `replace: true` for the symbol: looking up four tickers in a row should
   * leave four back-button steps, which is how you compare them. */
  const setSupportSymbol = (sym: string) => {
    const next = new URLSearchParams(params);
    next.set('tab', 'support');
    const s = normalizeSymbol(sym);
    if (s) next.set('symbol', s); else next.delete('symbol');
    setParams(next);
  };

  const setSupportWindow = (w: string) => {
    const next = new URLSearchParams(params);
    next.set('tab', 'support');
    next.set('window', w);
    setParams(next, { replace: true });
  };

  /** BOTH halves of the chart view in ONE URL write.
   *
   *  Ajay 2026-08-29: "now the charts do not let me use yearly and monthly".
   *  Cause: the window and timeframe setters each built a fresh
   *  URLSearchParams from the SAME `params` snapshot, so calling them back to
   *  back in one handler meant the second silently discarded the first —
   *  picking "Daily · 1 year" set window=1y while the old tf=15m survived,
   *  and the chart stayed intraday. One setter, one write, no lost half.
   */
  const setSupportView = (w: string, t: string) => {
    const next = new URLSearchParams(params);
    next.set('tab', 'support');
    next.set('window', w);
    // Daily is the default, so it leaves the URL clean — a shared link of an
    // untouched tab looks exactly like it did before the dropdown existed.
    if (t && t !== 'daily') next.set('tf', t); else next.delete('tf');
    setParams(next, { replace: true });
  };

  /* The SERVED kind wins; the local map is only the fallback before the first
   * payload lands (and for the half second a previous tab's payload is still on
   * screen, which is why `data.tab` is checked). */
  const enterableKind = ((data?.tab ?? tab) === tab ? data?.enterable_kind : null)
    ?? ENTERABLE_KIND[tab] ?? 'demand';

  const rawTiles = data?.tiles || [];

  /* 🪜 WHICH KIND OF ROWS THIS TAB HAS, served (board.band_structure_kind →
   * band_structure.kind_for_tab → enterable.KIND_BY_TAB — one map, not a second
   * one). Same served-wins / local-fallback rule as the 🎯 kind above, for the
   * same reason: the banner must follow the tab the payload is FOR.
   *
   * The backend attaches `band_structure_study` on EVERY request, kind or no
   * kind, so without this check the "ordered by ceiling thickness" banner and
   * its three-group fallback note render over Strong VCP, Past Winners, S3
   * Topping, Earnings Flow, 0DTE and Under Value — boards whose rows are not
   * price bands, that carry no band read and are not ordered by one. */
  const bandKind = ((data?.tab ?? tab) === tab ? data?.band_structure_kind : null)
    ?? ENTERABLE_KIND[tab] ?? 'demand';
  const bandNa = String(bandKind) === BAND_STRUCTURE_KIND_NA;
  /* …and what those six tabs say INSTEAD — the 🎯 n/a precedent, which puts
   * that sentence on the page (HiddenCount's "no demand read for this tab")
   * rather than behind a sort dropdown they do not have.
   *
   * THE SENTENCE IS SERVED, in this order: the payload-level
   * `band_structure_na_text`, then the first tile that carries one
   * (band_structure.read → na_text). It used to be taken off the FIRST TILE
   * only — so an n/a tab that came back with ZERO tiles (0DTE outside the
   * session) rendered NEITHER the banner, suppressed on purpose, NOR this
   * line: the page went silent about a tab it has nothing to rank on, which is
   * the failure this surface has already been caught on twice.
   *
   * The KIND is served whether or not a tile is, so the kind decides the line
   * and `BAND_STRUCTURE_NA_TEXT` — the mirror of band_structure.NA_TEXT,
   * pinned to it character for character in bandStructure.test.ts — fills it
   * when no payload carried a sentence. The page still assembles none of its
   * own wording. */
  const bandNaText = useMemo(() => {
    const served = data?.band_structure_na_text;
    if (typeof served === 'string' && served.trim()) return served.trim();
    for (const t of rawTiles) {
      const s = t.band_structure?.na_text;
      if (typeof s === 'string' && s.trim()) return s.trim();
    }
    return BAND_STRUCTURE_NA_TEXT;
  }, [data?.band_structure_na_text, rawTiles]);
  /* The chart ledger (Ajay 2026-08-31: "Chart feel so clumsy can you give me
   * a ledger and some check boxes to toggle these off"). Hidden families are
   * a per-browser convenience (localStorage), filtered client-side — except
   * the three study families (AMD / fib / mean reversion), which are computed
   * server-side and so DO refetch when switched on. */
  const toggleOverlay = (key: string) => {
    setHiddenOverlays((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      saveHidden(next);
      return next;
    });
  };
  const overlayGroups = useMemo(() => presentGroups(rawTiles), [rawTiles]);
  // He chose "expanded chart only, not every grid tile" for fib. Applying that
  // HERE was a mistake: these tiles ARE the chart he reads on this page and
  // there is no separate expanded surface, so the rule silently meant "never
  // draw fib" — he reported it as "Non of these are showing up I selected AMD,
  // Fibonacci". Fib draws on the tiles; the checkbox is how he turns it off.
  const tiles = useMemo(
    () => rawTiles.map((t) => filterForGrid(filterTile(t, tabHidden), true)),
    [rawTiles, tabHidden]);
  /* 🎯 The enterable cut over the tiles this page already ordered. It is a
   * STABLE PARTITION, never a sort: shown tiles keep the board's own order and
   * the tiles with no read yet follow in theirs, so nothing is silently lost
   * and nothing is silently promoted.
   *
   * The read is attached per tile by chart_maps/board.attach_enterable on the
   * SAME live snapshot the now-line uses, AFTER the limit cut — so this counts
   * the tiles on screen, not the universe. The count line says so; raising
   * `limit` is how you see further (spec §7.15, his call).
   *
   * 📁 holdings is exempt and never reaches here: that tab renders its own
   * board, which never hides a position. */
  const tileReads = useMemo(() => {
    const m = new Map<string, EnterableRead | null | undefined>();
    for (const t of tiles) if (t.symbol) m.set(String(t.symbol).toUpperCase(), t.enterable ?? null);
    return m;
  }, [tiles]);
  const tilePart = useMemo(
    () => partitionEnterable(tiles, (t) => t.symbol, tileReads,
                             enterableOnly && enterableKind !== 'n/a' && tab !== 'holdings',
                             unhide),
    [tiles, tileReads, enterableOnly, enterableKind, tab, unhide]);

  /* The TWO controls both called "room" (spec §2.4). The `?room=` floor runs on
   * the SERVER against the live print and decides which tiles come back at all;
   * the `room` chip below runs in the browser over rows already served. They
   * compose in one direction only — the browser cannot un-hide a tile it never
   * received — so on a ROOM_TABS tab the chip says so, or he clicks it, sees
   * nothing, and reasonably concludes it is broken. The percentage is the
   * SERVED default, never a typed 5. */
  const roomChipTitle = useMemo(() => (ROOM_TAB ? {
    room: `This tab also has the server-side room floor above: names under ${data?.min_room_default ?? DEFAULT_MIN_ROOM}% room are never sent here. To see every one of them, set "any room" as well.`,
  } : null), [ROOM_TAB, data?.min_room_default]);

  const ictParams = useMemo(() => ictParamRows(data?.params), [data?.params]);
  // The backend flags which values the video actually states (3-candle
  // fractal, "two or more" consolidations); they get their own line so the
  // "not from the video" header is never printed over them.
  const ictVideoParams = useMemo(() => ictParams.filter((r) => r.fromVideo), [ictParams]);
  const ictOwnerParams = useMemo(() => ictParams.filter((r) => !r.fromVideo), [ictParams]);
  const ictSrc = useMemo(() => ictSource(data?.source), [data?.source]);

  return (
    <div className="cm-page">
      <div className="cm-head">
        <h1 className="cm-title">
          🗺️ Chart Maps
          <InfoButton title="Chart Maps — how to read this board">{HowItWorks}</InfoButton>
        </h1>
        <p className="cm-sub">Just the charts. One shape per tab — learn it by looking.</p>
      </div>

      {/* Where money flowed in the last month — above the tabs so every
        * board is read against the same rotation backdrop (Ajay 2026-08-31:
        * "make sure this scan you did today to be on top of the chart maps"). */}
      <HotSectors />

      <div className="cm-tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t}
                  className={`cm-tab${tab === t ? ' cm-tab-on' : ''}`}
                  onClick={() => setTab(t)}>
            {TAB_META[t].label}
          </button>
        ))}
      </div>

      {/* The ICT blurb names its source; the name is the link (Ajay: purely
        * price action from his spec + Jesse Rogers' walkthrough). Split on the
        * name so the copy stays one testable string in TAB_META. */}
      <p className="cm-blurb">
        {tab === 'ict'
          ? TAB_META.ict.blurb.split(ICT_SOURCE.label).flatMap((part, i, arr) =>
              i < arr.length - 1
                ? [part, <a key={`src-${i}`} href={ICT_SOURCE.url} target="_blank"
                            rel="noreferrer noopener">{ICT_SOURCE.label}</a>]
                : [part])
          : TAB_META[tab].blurb}
      </p>

      {/* 🧭 SPY · QQQ, PINNED to the Back in Demand tab (Ajay 2026-09-16:
        * "Can you create a SPY demand and supply zone please for me? and also
        * QQQ supply and demand zone and keep them always in the in demand zone
        * page. I need everything calculation overnight.")
        *
        * Mounted HERE, above every branch below it, on purpose: "keep them
        * always" means the strip renders while the scan is warming, while the
        * board is erroring, when nothing matched and when his filters have cut
        * the grid to zero. Everything under this line is the universe pass and
        * its controls — these two tickers are not in it and must never be
        * filtered, ordered or gated by it. An absent payload draws the strip's
        * own placeholder; it never renders nothing. */}
      {tab === 'zones' && <IndexZones data={data?.index_zones} />}
      {/* 🗓️ Coming up — the IPO tab's forward calendar (2026-09-20), pinned
        * above the grid the way the index strip is: it renders while the
        * board warms, when it errors and when the calendar came back empty,
        * and nothing in the controls below filters it. Rows are printed
        * verbatim from Finnhub — a price RANGE is never rounded into a price. */}
      {tab === 'ipo' && <IpoUpcomingStrip data={data?.upcoming ?? null} corroboration={data?.corroboration ?? null} />}

      {/* ℹ️ Rules — the board's own picks / stops / alerts from GET
        * /supply-demand/rules (Ajay 2026-09-06). The three boards that carry
        * a rule section; the zones tab is the "in demand" board. */}
      {(tab === 'zones' || tab === 'deep_demand' || tab === 'catalysts' || tab === 'breaking' || tab === 'quick_bounce') && (
        <div className="cm-rules" style={{ margin: '0.2rem 0 0.6rem' }}>
          <RulesInfo section={tab === 'zones' ? 'in_demand' : tab === 'breaking' ? 'alerts' : tab} />
        </div>
      )}

      {/* 🧨 The explosive read rides every tab, so its rules do too
        * (backend rules_info._explosive_section, built from the enforcing
        * constants). */}
      <div className="cm-rules" style={{ margin: '0.2rem 0 0.6rem' }}>
        <RulesInfo section="explosive" />
      </div>

      {/* 🎯 ENTERABLE — the filter he asked for, and the rules behind it.
        * Every word of the verdict is built on the backend from the enforcing
        * constants (the two standing push gates, the measured floor read, the
        * two measured drags), so the section is served like the others. The
        * checkbox is DISABLED rather than hidden on a tab whose rows are not
        * demand reversals at all; a control that vanishes reads as a bug. */}
      <div className="cm-rules cm-enterable-bar" style={{ margin: '0.2rem 0 0.6rem' }}>
        <EnterableOnlyToggle checked={enterableOnly} onChange={setEnterableOnly}
                             kind={enterableKind} unhideCount={unhide.size}
                             naText={data?.enterable_study?.fallback_note
                               || 'These rows are not demand reversals, so there is no enterable read to filter on.'} />
        <RulesInfo section="enterable" />
      </div>

      {/* Quick Bounce (Ajay 2026-09-06): the study's own numbers under the
        * blurb — the list is read against its base rate and its persistence,
        * never on its own. */}
      {tab === 'quick_bounce' && data?.study && (
        <p className="cm-note" data-testid="quick-bounce-study">
          Study{data.study.as_of ? ` (${data.study.as_of})` : ''}: {quickBounceStudyText(data.study)}.
          {' '}{quickBouncePersistenceText(data.study.persistence)}
        </p>
      )}

      {/* 🚀 Breaking (2026-09-06): the cards are the last zone-edge pass —
        * its stamp and whether it is live sit on the board, exactly as the
        * text list they replaced said them. */}
      {tab === 'breaking' && data && (
        <p className="cm-note" data-testid="breaking-pass">{breakingPassText(data)}</p>
      )}
      {/* Ajay 2026-09-08 (ORCL): "show real time premarket and extended hours
        * trading info as well in all the chart maps" — outside RTH every tile's
        * now line is the live print; one line says which tape. */}
      {data && sessionNoteText(data.tape_session) && (
        <p className="cm-note" data-testid="session-note">{sessionNoteText(data.tape_session)}</p>
      )}
      {/* Ajay 2026-09-07: "when the last resistance break will the price go to ATH" —
        * the weekly lid-break study (supply_demand/lid_break.py), pooled, placebo beside
        * every rate. The 2-year frame's high stands in for ATH and says so. */}
      {tab === 'breaking' && data?.lid_break && lidBreakStudyText(data.lid_break) && (
        <p className="cm-note" data-testid="lid-break-study">
          Last-lid breaks{data.lid_break.as_of ? ` (study ${data.lid_break.as_of})` : ''}: {lidBreakStudyText(data.lid_break)}.
          {' '}{quickBouncePersistenceText(data.lid_break.persistence)} Prior high = the 52-week high before the break; the 2-year frame’s high stands in for the all-time high. A study, not a rule.
        </p>
      )}

      {/* Reaching vs already reached — only the two demand boards have the two
        * moments. Segmented, not a checkbox: the two states are a choice of
        * WHICH list, not an on/off refinement of one list. */}
      {/* GRADE_TAB joins this row for the 🌀 AMD / Keltner grade chips
        * (2026-09-17). Every child below is gated on its own tab, so widening
        * the container shows nothing new on the tabs that were already here. */}
      {(tab === 'zones' || tab === 'deep_demand' || LENS_TABS || GRADE_TAB) && (
        <div className="cm-phase" role="tablist" aria-label="Zone phase">
          {LENS_TABS && (
            <button type="button" role="tab" aria-selected={phase === 'all'}
                    className={`cm-phase-btn${phase === 'all' ? ' cm-phase-on' : ''}`}
                    onClick={() => setPhase('all')}>
              All
            </button>
          )}
          <button type="button" role="tab" aria-selected={phase === 'reached'}
                  className={`cm-phase-btn${phase === 'reached' ? ' cm-phase-on' : ''}`}
                  onClick={() => setPhase('reached')}>
            ✅ Already reached
          </button>
          <button type="button" role="tab" aria-selected={phase === 'approaching'}
                  className={`cm-phase-btn${phase === 'approaching' ? ' cm-phase-on' : ''}`}
                  onClick={() => setPhase('approaching')}>
            🎯 Approaching
          </button>
          <span className="cm-phase-hint">
            {phase === 'approaching'
              ? 'Still above the level, close, and falling toward it — set the order before it arrives. Closest to the level first — money flow breaks ties.'
              : phase === 'all'
              ? 'The full screen; the other two narrow it to names at or nearing their level.'
              : tab === 'zones' && target === 'order_block'
              ? 'Inside a fresh order block on its first touch. Youngest block first — money flow breaks ties.'
              : 'Back inside a tested band and holding.'}
          </span>
          {/* Which LEVEL the moment is measured to (Ajay 2026-08-31). Zones
            * tab only, BOTH phases — reached+order block = in the block on
            * its first touch. Deep Demand's ARRIVAL band IS its level (2nd or
            * 3rd, per the crossed-level walk of 2026-09-16 — the tile draws
            * every level already crossed and says how many), and the lens tabs
            * measure to their own screens' bands. */}
          {/* Room floor (Ajay 2026-09-05), the room-gated boards only. Two
            * states, not a slider: the phone's gate (≥ 5% from the live print
            * to the first unbroken band overhead — ALERT_MIN_ROOM_PCT, owner
            * setting) or off. A tile at its lid is hidden by default and
            * counted under the board; "any room" shows it.
            *
            * The two entries come from lib/bounceRoom.ts ROOM_FLOORS — the SAME
            * array the Back in Demand panel renders (2026-09-17) — so the two
            * surfaces can never offer different floors. It is a VIEW filter and
            * gates nothing: no alert, no entry, no stop moves when he changes
            * it. Hidden entirely on a tab whose builder has no room read (the
            * amd / keltner turning-bullish tabs, ict, vcp, gabbar …) rather
            * than shown inert — ROOM_TABS mirrors board.board()'s routing. */}
          {ROOM_TAB && (
            <span className="cm-phase-sub" role="tablist" aria-label="Room floor"
                  title={`Room = % from the LIVE print to the first unbroken band overhead (supply not broken under yesterday's close, plus demand bands above). The phone only pages names with ≥ ${data?.min_room_default ?? DEFAULT_MIN_ROOM}%; this floor hides the rest here too. TRU 2026-09-05: 0.3% under a supply band — hidden. A view filter only — it changes nothing the alerts or the lanes do.`}>
              {/* The FLOORS come from the shared list so the two surfaces can
                * never offer different ones; the LABELS stay this toolbar's own.
                * Rendering bounceRoom's label strings here renamed buttons Ajay
                * has used since 2026-09-05 ("Any room" -> "any room (default)")
                * for no ask — the value of sharing is the numbers, not the
                * wording, and a dense tile toolbar labels tighter than a panel
                * select does. */}
              {ROOM_FLOORS.map((f) => {
                const floor = Number(f.key);
                const on = minRoom === floor;
                return (
                  <button key={f.key} type="button" role="tab" aria-selected={on}
                          className={`cm-phase-btn${on ? ' cm-phase-on' : ''}`}
                          onClick={() => setRoom(floor === 0 ? 'any' : 'floor')}>
                    {cmRoomLabel(floor)}
                  </button>
                );
              })}
            </span>
          )}
          {/* 🔻 In flight (Ajay 2026-09-17). WHERE PRICE IS AGAINST THE BASE
            * EDGE RIGHT NOW — the half the stored detector cannot show,
            * because it only fires once a raid has CLOSED back inside. Counts
            * are live and every one of them is unconfirmed until the close: a
            * "Reclaimed today" name is a raid FORMING, not a raid. */}
          {FLIGHT_TAB && !!(data?.flight_states || []).length && (
            <span className="cm-phase-sub" role="tablist" aria-label="In flight"
                  title="Where price is against its base edge RIGHT NOW, from today's own low and the live print — no threshold, just the facts. Sweeping = below the edge, unresolved. Reclaimed today = the low pierced the edge and price is back inside, which is a raid FORMING: the bar has not closed and nothing here is confirmed. Holding = today's low never reached the edge. Counts are live.">
              {(data?.flight_states || []).map((k) => {
                const c = data?.flight_counts ? Number(data.flight_counts[k] ?? 0) : null;
                const on = flightSel.has(k);
                const empty = c === 0;
                return (
                  <button key={k} type="button" role="tab" aria-selected={on}
                          aria-disabled={empty || undefined}
                          data-testid={`amd-flight-${k}`}
                          className={`cm-phase-btn${on ? ' cm-phase-on' : ''}`}
                          style={empty ? { opacity: 0.45 } : undefined}
                          onClick={() => toggleFlight(k)}>
                    {AMD_FLIGHT_LABEL[k] || k}{c == null ? '' : ` · ${c}`}
                  </button>
                );
              })}
            </span>
          )}
          {/* 🌀 AMD / Keltner grade (Ajay 2026-09-17). Multi-select over the
            * grades the SWEEP stores, rendered from the server's own
            * `grades_all` so the choices can never drift from what a row can
            * carry. Each chip shows how many names hold that grade across the
            * whole sweep — with the filter OFF, so a count never moves because
            * a chip is unselected. Nothing selected = the board this tab has
            * always opened on (the turning grade), never an empty page. */}
          {GRADE_TAB && !!(data?.grades_all || []).length && (
            <span className="cm-phase-sub" role="tablist" aria-label="AMD grade"
                  title="Which part of the cycle each name is in, from the nightly sweep. Counts are the whole sweep at that grade, not this page. Nothing selected shows the turning grade alone — the board this tab has always opened on. This read measured INVERTED against a placebo (see the note under the board): it describes the tape, it does not predict it, and it gates nothing.">
              {(data?.grades_all || []).map((g) => {
                const c = data?.grade_counts ? Number(data.grade_counts[g] ?? 0) : null;
                const on = gradeSel.has(g);
                const empty = c === 0;
                return (
                  <button key={g} type="button" role="tab" aria-selected={on}
                          aria-disabled={empty || undefined}
                          data-testid={`amd-grade-${g}`}
                          className={`cm-phase-btn${on ? ' cm-phase-on' : ''}`}
                          style={empty ? { opacity: 0.45 } : undefined}
                          onClick={() => toggleGrade(g)}>
                    {AMD_GRADE_LABEL[g] || g}{c == null ? '' : ` · ${c}`}
                  </button>
                );
              })}
            </span>
          )}
          {/* 🩹 Arrival level (Ajay 2026-09-16: "can you do level 4 and give me
            * filters for that"). Deep Demand only — it is the one board whose
            * rows HAVE an arrival level. Multi-select, not segmented: these
            * three are refinements of ONE list, unlike the phase tabs above
            * which are a choice of which list. Each chip carries the count that
            * level HOLDS with the filter OFF (served `level_counts`), so a
            * level with nothing in it reads as empty rather than missing —
            * dimmed, never hidden, and still clickable so a link that arrives
            * on an empty level is never a dead end. */}
          {DEEP_TAB && (
            <span className="cm-phase-sub" role="tablist" aria-label="Arrival level"
                  title="Arrival level = which demand band price is standing in after crossing the ones above it. 2nd = one band already crossed, 4th = three. Four is the deepest this window can express — the board is served the four bands nearest the price. Counts are how many names sit at each level on this board — same phase, room, sales and liquidity settings, with the level filter off. The page itself shows the first 24 of them.">
              {DEEP_LEVELS.map((n) => {
                const counts = data?.level_counts;
                const c = counts ? Number(counts[String(n)] ?? 0) : null;
                const on = levelSel.has(n);
                const empty = c === 0;
                return (
                  <button key={n} type="button" role="tab" aria-selected={on}
                          aria-disabled={empty || undefined}
                          data-testid={`deep-level-${n}`}
                          className={`cm-phase-btn${on ? ' cm-phase-on' : ''}`}
                          style={empty ? { opacity: 0.45 } : undefined}
                          onClick={() => toggleLevel(n)}>
                    {DEEP_LEVEL_LABEL[n]}{c == null ? '' : ` · ${c}`}
                  </button>
                );
              })}
            </span>
          )}
          {DEEP_TAB && (
            <span className="cm-phase-hint" data-testid="deep-levels-hint">
              Level = the demand band price arrived at after crossing the ones above
              it — 2nd means one band already crossed, 4th means three, and four is
              the deepest the served four-band window can express. Depth is NOT a
              measured edge: these chips narrow the board and order nothing, so a
              4th-level name never outranks a closer 2nd-level one.
            </span>
          )}
          {tab === 'zones' && (
            <span className="cm-phase-sub" role="tablist" aria-label="Approach target">
              <button type="button" role="tab" aria-selected={target === 'zone'}
                      className={`cm-phase-btn${target === 'zone' ? ' cm-phase-on' : ''}`}
                      onClick={() => setTarget('zone')}>
                Demand zone
              </button>
              <button type="button" role="tab" aria-selected={target === 'order_block'}
                      className={`cm-phase-btn${target === 'order_block' ? ' cm-phase-on' : ''}`}
                      onClick={() => setTarget('order_block')}>
                Order block
              </button>
            </span>
          )}
        </div>
      )}

      {/* 🎯 One filter state for the whole tab body: the twelve row boards
        * mounted below read it from here rather than each growing its own
        * checkbox and its own default. Standalone (/catalysts, /patterns,
        * /signal-lab) nothing wraps them, the default context is OFF and those
        * pages are unchanged — spec §7.8, his call. */}
      <EnterableFilterProvider enterableOnly={enterableOnly} kind={enterableKind}
                               setEnterableOnly={setEnterableOnly}
                               ignoreReasons={unhide} toggleReason={toggleReason}>
      {/* The one tab that is not a board. Everything below — the sort/tier
        * controls, the scan progress, the tile grid, the footer counts —
        * describes a universe pass that this tab does not run. */}
      {tab === 'session' ? (
        /* Reads the SAME two demand boards, asked a different question. Picking
         * a row hands the symbol to the Support tab, which is where the drill-in
         * (bands, SMC cards, chart) already lives — one place per job. */
        <SessionBoard onPick={(sym) => {
          const next = new URLSearchParams(params);
          next.set('tab', 'support');
          next.set('symbol', sym);
          setParams(next, { replace: true });
        }} />
      ) : tab === 'holdings' ? (
        /* 📁 My holdings (Ajay 2026-09-14: "about the new portfolio stocks I
         * want to run these against them"). One Support-tab tile per name he
         * owns, his cost and typed stop drawn on each — its own fetcher, no
         * universe pass, so the board controls and the grid are skipped. */
        <HoldingsBoard days={days ?? null} />
      ) : tab === 'hot_pullback' ? (
        /* 🔥 Hot Pullback (Ajay 2026-09-09: "a new tab for hot pull back like
         * 21 day moving average drops but have a reversal from demand zones …
         * like DYN today which bounced back quick"). Its own endpoint and its
         * own renderer, so the tile grid and the sort/tier controls are skipped
         * — the row's facts ARE the read, and the measured horizon rides on
         * every one of them. */
        <HotPullbackBoard />
      ) : tab === 'patterns' ? (
        /* 📐 Chart Patterns (Ajay 2026-09-09: "Can you move chart patterns in
         * to the Chartmaps page please and show the winning charts"). The same
         * component as the /patterns page — one implementation, one scan — with
         * its page title dropped because the tab header already says it. Every
         * card carries a 🏆 link into the Past Winners tab filtered to that
         * pattern, which is the tab immediately to the right. */
        <PatternsBoard />
      ) : tab === 'signals' ? (
        /* The Signal Lab's working surface, mounted as a tab (Ajay 2026-09-01:
         * "add the signals tab inside chart maps"). Same component as the
         * /signal-lab page — one implementation, one watchlist. */
        <SignalLabBoard />
      ) : tab === 'overnight' ? (
        /* The Day Trading page's overnight movers scan, mounted here because
         * this is where he starts the day (Ajay 2026-09-01: "I think we need a
         * page in Chart Maps to show over night volume or move this page
         * there"). Same component, same endpoint — one implementation. Picking
         * a row hands the symbol to the Support tab, same as Session. */
        <OvernightGappers profile="aggressive" onPick={(sym) => {
          const next = new URLSearchParams(params);
          next.set('tab', 'support');
          next.set('symbol', sym);
          setParams(next, { replace: true });
        }} />
      ) : tab === 'hot_sectors' ? (
        /* 🔥 Hottest (Ajay 2026-09-11: "find the hottest of the sectors like
         * the most growth and put them in to a new tab ... hottest from a
         * sector in to a table. Like the catalyst and keep sales and other
         * crucial metrics"). Its own endpoint and its own grouped table, so
         * the tile grid and the sort/tier controls are skipped. Sits with the
         * movers boards (Catalysts, Overnight) — it answers the same question
         * they do, one level up. */
        <HottestSectors />
      ) : tab === 'bonde' ? (
        /* 📈 Bonde (Ajay 2026-09-13: "create me a Bonde tab ... I wanna see
           his stocks"). His sales tiers are the universe, his Episodic Pivot
           is the entry, and the board is the intersection — either leg alone
           is unusable (the sales gate passes 50.6% of the scan; the Pivot
           alone carries declining-sales names). ✨ NEW marks arrivals. */
        <BondeBoard />
      ) : tab === 'gnt' ? (
        /* 📌 One public trader's posts + our own read (Ajay 2026-09-12:
           "I wanna track his stocks for investing"). Sentences, not a ticker
           list — he mixes live ideas with closed put trades. */
        <GntBoard />
      ) : tab === 'potus' ? (
        /* 🏛️ POTUS / federal (Ajay 2026-09-20: "I would like it to be in
           individual tickers but also in to the potus page in chart maps";
           earlier "Anytime POTUS does new investments show me those"). The
           📁 My holdings pattern: one Support tile per curated name in a fixed
           editorial order, then the watch's HEURISTIC candidates — its own
           fetcher, no universe pass, so the board controls and the grid are
           skipped. */
        <PotusBoard />
      ) : tab === 'growth' ? (
        /* 🚀 Explosive Growth (Ajay 2026-09-11: 100%+ sales AND 100%+ quarterly
         * EPS, "I wanna know when ever these are in demand, separately just
         * trackers", "remove the 700M rule for this page"). Its own endpoint,
         * its own board and its own alert kind — deliberately NO cap floor,
         * with the rows the trading engine will refuse marked ⛔ rather than
         * hidden. Sits beside Hottest: both are discovery surfaces. */
        <ExplosiveGrowth />
      ) : tab === 'catalysts' ? (
        /* The Catalysts page body, mounted as a tab (Ajay 2026-09-05: "move
         * catalyst tab in to Chart maps"). Same component as the old
         * /catalysts page — which now redirects here — one implementation.
         * `embedded` drops its own page header and gauge banner (this page
         * already has them) and moves its sub-tab URL param to `sub` so it
         * cannot fight Chart Maps' own `tab`. */
        <CatalystsBoard embedded />
      ) : !isBoardTab(tab) ? (
        <SupportLevels symbol={supportSymbol} window={supportWindow} tf={supportTf}
                       onSymbol={setSupportSymbol} onWindow={setSupportWindow}
                          onView={setSupportView} />
      ) : (
      <>
      {/* 0DTE only. Two facts a reader needs BEFORE the tiles, because either
        * one changes what the board means:
        *   - the session: after the close on expiry day the chain has settled,
        *     so a near-empty board is correct rather than broken;
        *   - the gap between names with a chain and names with anything
        *     tradeable, which is where the cost floors actually bite. */}
      {tab === 'zero_dte' && data?.session && (
        <div className={`cm-session cm-session-${data.session.state}`}
             role="status">
          <strong>{data.session.actionable ? 'Live' : 'Not live'}</strong>
          <span>{data.session.label}</span>
          {typeof data.with_chain === 'number' && (
            <span className="cm-session-counts">
              {data.with_contract ?? 0} of {data.with_chain} names have a
              contract clearing the spread, delta and volume floors
              {data.expiry ? ` · expiry ${data.expiry}` : ''}
            </span>
          )}
        </div>
      )}

      <div className="cm-controls">
        {/* ICT (2026-09-03): both sides are always scanned; Bias only narrows
          * what is shown. Micro picks the trigger clock the dormant loop runs
          * on once a daily level is tapped — 60m is the video's clock. */}
        {tab === 'ict' && (
          <label className="cm-ctl" title="Which side of the sweep. Bullish = the manipulation ran UNDER a key low or the accumulation lows and price pushed back up; bearish is the mirror over a key high. All shows both, ordered by state then grade.">
            Bias
            <select aria-label="ICT bias" value={bias}
                    onChange={(e) => setIctParam('bias', e.target.value, DEFAULT_ICT_BIAS)}>
              {ICT_BIASES.map((b) => (
                <option key={b.key} value={b.key}>{b.label}</option>
              ))}
            </select>
          </label>
        )}
        {tab === 'ict' && (
          <label className="cm-ctl" title="The trigger timeframe. The daily chart always sets the levels; this is the clock the manipulation, displacement, MSS and IFVG are read on once a level is tapped. 60m is the video's micro clock; 15m is a faster read of the same rules.">
            Micro
            <select aria-label="ICT micro timeframe" value={micro}
                    onChange={(e) => setIctParam('micro', e.target.value, DEFAULT_ICT_MICRO)}>
              {ICT_MICROS.map((m) => (
                <option key={m.key} value={m.key}>{m.label}</option>
              ))}
            </select>
          </label>
        )}
        {tab === 'gabbar' && (
          <label className="cm-ctl" title="Measure every covered name against one of Gabbar's band types. Aggressive is his shallowest buy zone; conservative 1 and 2 sit progressively deeper. Names he drew no such band for drop off the board under a lens.">
            Level
            <select value={gabbarLevel} onChange={(e) => setGabbarLevel(e.target.value)}>
              <option value="all">All bands</option>
              <option value="aggressive">🎯 Aggressive</option>
              <option value="conservative 1">🛡️ Conservative 1</option>
              <option value="conservative 2">🛡️ Conservative 2</option>
            </select>
          </label>
        )}
        {tab === 'gabbar' && (
          <label className="cm-ctl cm-ctl-check"
                 title="On (default): only names inside or within 3% of a measured band — the board answers 'is anything AT his levels'. Off: every covered name, ranked by distance, for shopping where the deeper entries sit.">
            <input type="checkbox" checked={gabbarTouchingOnly}
                   onChange={(e) => setGabbarTouchingOnly(e.target.checked)} />
            Touching only (≤3%)
          </label>
        )}
        {/* Not on Earnings: that board's order is "which group, then how much
            money traded", and a theme re-shuffle would misdescribe it. Same
            reason the backend returns empty sorts/tiers for the tab. */}
        {tab !== 'winners' && tab !== 'earnings' && (
          <label className="cm-ctl cm-ctl-check">
            <input type="checkbox" checked={themesFirst}
                   onChange={(e) => setThemesFirst(e.target.checked)} />
            Themes first (quantum · nuclear · robotics · AI semis)
          </label>
        )}
        {tab !== 'winners' && (
          <label className="cm-ctl">
            Window
            <select value={String(days || '')} onChange={(e) => setParams((p) => {
              const n = new URLSearchParams(p);
              if (e.target.value) n.set('days', e.target.value); else n.delete('days');
              return n;
            }, { replace: true })}>
              <option value="">Default</option>
              <option value="130">6 months</option>
              <option value="180">9 months</option>
              <option value="252">1 year</option>
              {/* Ajay 2026-09-06: "2 years ... 3 years and then keep 5 years
                * ... in all the chart map calculations and dropdown time
                * frames." Served from the deep 5y frame (board.DEEP_BARS_FROM). */}
              <option value="504">2 years</option>
              <option value="756">3 years</option>
              <option value="1260">5 years</option>
            </select>
          </label>
        )}
        {tab !== 'winners' && (data?.sorts || []).length > 0 && (
          <label className="cm-ctl">
            Sort
            <select
              aria-label="Sort the board"
              value={sort}
              onChange={(e) => setParams((p) => {
                const n = new URLSearchParams(p);
                if (e.target.value === DEFAULT_SORT) n.delete('sort');
                else n.set('sort', e.target.value);
                return n;
              }, { replace: true })}
            >
              {(data?.sorts || []).map((o) => (
                <option key={o.key} value={o.key}>{o.label}</option>
              ))}
            </select>
          </label>
        )}
        {tab !== 'winners' && (data?.tiers || []).length > 0 && (
          <label className="cm-ctl">
            Liquidity
            <select
              aria-label="Minimum average daily turnover"
              value={minTier}
              onChange={(e) => setParams((p) => {
                const n = new URLSearchParams(p);
                if (e.target.value === DEFAULT_MIN_TIER) n.delete('min_tier');
                else n.set('min_tier', e.target.value);
                return n;
              }, { replace: true })}
            >
              {(data?.tiers || []).map((o) => (
                <option key={o.key} value={o.key}>{o.label}</option>
              ))}
            </select>
          </label>
        )}
        {tab !== 'winners' && (
          <button type="button" className="cm-rescan"
                  disabled={stream.scanning}
                  onClick={() => stream.start({ fast: true })}>
            {stream.scanning ? 'Scanning…' : '↻ Re-scan'}
          </button>
        )}
        {tab === 'winners' && (
          <label className="cm-ctl">
            Source
            <select value={source} onChange={(e) => setParams((p) => {
              const n = new URLSearchParams(p);
              n.set('tab', 'winners');
              n.set('source', e.target.value);
              // A chart-pattern name means nothing for a demand zone.
              if (e.target.value === 'zone') { n.delete('pattern'); n.delete('minervini'); }
              return n;
            }, { replace: true })}>
              {WINNER_SOURCES.map((s) => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>
          </label>
        )}
        {tab === 'winners' && source === 'pattern' && (
          <label className="cm-ctl cm-ctl-check">
            <input type="checkbox" checked={minerviniOnly}
                   onChange={(e) => setParams((p) => {
                     const n = new URLSearchParams(p);
                     n.set('tab', 'winners');
                     if (e.target.checked) n.set('minervini', 'true'); else n.delete('minervini');
                     return n;
                   }, { replace: true })} />
            SEPA qualifiers only
          </label>
        )}
        {tab === 'winners' && source === 'pattern' && data?.patterns?.length ? (
          <label className="cm-ctl">
            Pattern
            <select value={pattern || ''} onChange={(e) => setPattern(e.target.value || null)}>
              <option value="">All patterns</option>
              {data.patterns.map((p) => (
                <option key={p} value={p}>{p.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </label>
        ) : null}
        <button className="cm-refresh" onClick={() => { setLoading(true); void load(); }}>
          ↻ Refresh
        </button>
      </div>

      {/* When this board was actually computed, and how new its bars are.
        * Ajay 2026-08-25: the same tiles two days running (a weekend plus one
        * flat session) read as "is this even updating?" — the board was fresh,
        * but carried no way to prove it. Wall-clock alone isn't enough: a scan
        * run five minutes ago over week-old bars is still stale, so the bar
        * date rides along. No timestamp from the server → no stamp; a made-up
        * "just now" would be the same false reassurance in the other
        * direction. */}
      {freshness ? <div className="cm-scanstamp">{freshness}</div> : null}

      {tab === 'winners' && data?.record ? (
        <div className="cm-record">
          <div className="cm-record-head">
            The record behind these charts —{' '}
            <b>{data.record.overall.wins} hit target</b>,{' '}
            <b>{data.record.overall.losses} stopped out</b>{' '}
            of {data.record.overall.n} resolved setups.
            {data.excluded_already_past_target
              ? ` ${data.excluded_already_past_target} more were already past target when recorded and are excluded.`
              : null}
          </div>
          <div className="cm-record-rows">
            {data.record.by_pattern.map((r) => (
              <button key={r.pattern}
                      className={`cm-record-row${pattern === r.pattern ? ' cm-record-on' : ''}`}
                      onClick={() => setPattern(pattern === r.pattern ? null : r.pattern)}>
                <span className="cm-record-name">{r.label}</span>
                <span className="cm-record-val">{recordLine(r)}</span>
                {isThinSample(r.n) ? <span className="cm-badge cm-badge-warn">small n</span> : null}
              </button>
            ))}
          </div>
          <div className="cm-record-caveat">{data.record.caveat}</div>
        </div>
      ) : null}

      {err ? <div className="cm-note cm-note-err">Couldn't load the board — {err}</div> : null}

      {/* Until 2026-09-06 Deep Demand opened with the zone-edge 🚀 list as
        * ~200 text rows above its cards. Ajay: "change the deep demand to be
        * like In Demand with charts and cards" — that read is the Breaking
        * tab now (board.py breaking_tiles); this tab is cards only. */}

      {/* The demand tab's own scan. NOT the SEPA stream above it — that one
        * feeds the VCP tab. Both this and the Back in Demand tab on
        * /supply-demand read one demand_reentry cache, so they watch the same
        * job and now show the same counter (Ajay 2026-08-17: "Are you updating
        * both pages when supply demand is getting updated"). */}
      {data?.warming && tab === 'ict' ? (
        /* The ICT engine warms in its own background thread (ict/engine.py
         * cached_or_warm, same pattern as demand_reentry) and this answers
         * warming:true rather than holding the connection open. The demand
         * counter above does not describe it, so it gets its own line. */
        <>
          <p className="cm-note" role="status">
            Scanning the ICT universe — daily levels for every $1B+ name, then the
            {' '}{micro} loop only for the names that tapped one. Usually under two
            minutes.
          </p>
          <p className="cm-note">
            The charts appear here as soon as it lands; you don't need to refresh.
          </p>
        </>
      ) : data?.warming ? (
        <>
          <DemandScanProgress progress={demandProgress ?? data.progress}
                              universeLabel={data.universe_key || universe}
                              running />
          <p className="cm-note">
            The charts appear here as soon as it lands; you don't need to refresh.
          </p>
        </>
      ) : null}

      {data?.sort_unavailable && (
        <p className="cm-note cm-note-warn">⚠️ {data.sort_unavailable}</p>
      )}
      {/* 🧨 The study's verdict, SERVED (board.explosive_study). It leads
        * with what was measured — including "no signal separates", which is the
        * branch the prior expects — so the 🧨 ordering is never read as an
        * explosiveness ranking it has not earned. No figure is typed here. */}
      {data?.explosive_study?.headline && (
        <StudyNote id="explosive" className="cm-explosive-study"
                   testId="cm-explosive-study"
                   headline={data.explosive_study.headline}
                   body={data.explosive_study.body}
                   fallbackNote={data.explosive_study.fallback_note}
                   limits={data.explosive_study.limits} />
      )}
      {/* 🎯 The entry-trigger study's verdict, SERVED (board.enterable_study).
        * The filter is ON by default, so what it is built on has to be on the
        * page next to it — including "study running" / "no trigger separates",
        * which are the branches the prior expects. No figure is typed here. */}
      {data?.enterable_study?.headline && (
        <StudyNote id="enterable" className="cm-enterable-study"
                   testId="cm-enterable-study"
                   headline={data.enterable_study.headline}
                   body={data.enterable_study.body}
                   fallbackNote={data.enterable_study.fallback_note}
                   limits={data.enterable_study.limits} />
      )}
      {/* 🪜 The band-structure study's verdict, SERVED (board.band_structure_study).
        * Ajay asked for the thinnest ceiling first and a layered floor; the
        * study measured both and NOTHING separated, so the ordering that ships
        * is DESCRIPTIVE and the banner is where that is said, in his own words
        * — "thinnest ceiling first" is never read as a prediction it did not
        * earn. No figure is typed here; every one comes off the wire.
        *
        * GATED ON THE TAB'S KIND, the way the 🎯 read gates its own line: see
        * `bandNa` above. A tab with no band read shows the served n/a sentence
        * underneath instead, never this banner. */}
      {!bandNa && data?.band_structure_study?.headline && (
        <StudyNote id="band-structure" className="cm-band-study"
                   testId="cm-band-structure-study"
                   headline={data.band_structure_study.headline}
                   body={data.band_structure_study.body}
                   fallbackNote={data.band_structure_study.fallback_note}
                   limits={data.band_structure_study.limits}
                   /* What the ordering could actually reach — served only when
                    * the sort ran and worked, because it is applied after the
                    * board was cut to its page size. */
                   extra={data.band_structure_scope}
                   extraTestId="cm-band-structure-scope" />
      )}
      {/* …and what a tab with NO band read says instead: the served sentence,
        * on the page, where the 🎯 n/a line lives — not a banner about an
        * ordering this board does not have. */}
      {bandNa && bandNaText && (
        <p className="cm-note cm-dim" data-testid="cm-band-structure-na">🪜 {bandNaText}</p>
      )}
      {!!data?.dropped_thin && (
        <p className="cm-note">
          {data.dropped_thin} name{data.dropped_thin === 1 ? '' : 's'} hidden below the
          liquidity floor — thin tape, so the base is not tradeable at size.
        </p>
      )}
      {!!data?.dropped_bounced && (
        <p className="cm-note">
          {data.dropped_bounced} name{data.dropped_bounced === 1 ? '' : 's'} hidden — already
          bounced {data.bounce_done_pct ?? 7}%+ off the demand zone, so the arrival is over.
        </p>
      )}
      {/* Room floor count (2026-09-05). Rendered from the payload, so it says
        * what the SERVER hid on the print it actually read — and it shows even
        * when the floor hid every tile, which is when it matters most. */}
      {!!data?.hidden_low_room && (
        <p className="cm-note" data-testid="hidden-low-room"
           title={`Hidden by the room floor: fewer than ${data.min_room ?? data.min_room_default ?? DEFAULT_MIN_ROOM}% from the live print to the first unbroken band overhead. Pick "${CM_ANY_ROOM_LABEL}" to see them flagged ⛔. The floor is a view filter — nothing is gated on it.`}>
          {data.hidden_low_room} hidden: room &lt;{' '}
          {data.min_room ?? data.min_room_default ?? DEFAULT_MIN_ROOM}% to the
          first unbroken band overhead on the live print (the phone's own gate) — pick
          {' '}<em>{CM_ANY_ROOM_LABEL}</em> to see them.
        </p>
      )}
      {/* 🩹 Arrival-level filter count (2026-09-16). Served, like the room
        * floor's — it says what the SERVER dropped on this call, so a board
        * that shrank because of a chip is explained rather than just smaller. */}
      {DEEP_TAB && !!data?.hidden_by_level && (
        <p className="cm-note" data-testid="hidden-by-level">
          {data.hidden_by_level} hidden: arriving at a level you have switched off
          {data.levels && data.levels !== 'all' ? ` (showing ${data.levels})` : ''} — turn
          the chips back on to see them.
        </p>
      )}
      {tab === 'quick_bounce' && !!(data?.no_band || data?.no_print) && (
        <p className="cm-note" data-testid="quick-bounce-away">
          {data.qualifying ?? 0} names qualify historically; {data.no_band ?? 0} sit away from
          every proven demand band right now (or fell through one) and {data.no_print ?? 0} had no
          print — only names at or just above a band are listed.
        </p>
      )}
      {!!data?.tape_pool && (
        <p className="cm-note">
          Tape pulled for {data.tape_enriched} of the top {data.tape_pool} by
          the default ranking — off-exchange and retail need an intraday tape, so
          this ranks that pool, not the whole scan.
        </p>
      )}
      {(stream.scanning || stream.phase === 'done' || stream.error) && (
        <div className="cm-progress">
          <SepaScanProgress {...stream} />
          {stream.phase === 'done' && (
            <p className="cm-progress-note">
              Scan finished — the board below has been reloaded from it.
            </p>
          )}
        </div>
      )}

      {loading && !tiles.length ? <div className="cm-note">Loading charts…</div> : null}

      {!loading && !tiles.length && !data?.warming && !err ? (
        <div className="cm-note">
          {data?.note || 'Nothing matched on this tab right now.'}
        </div>
      ) : null}

      <OverlayLegend present={overlayGroups} hidden={tabHidden}
                           locked={lockedOverlays}
                     onToggle={toggleOverlay} />
      {/* What the 🎯 filter cost this grid — ALWAYS on the page while it is on,
        * even at "0 hidden", with the reasons in the backend's own words and a
        * one-click way back. A board that empties itself in silence is the one
        * failure mode a default-ON filter has. */}
      <HiddenCount hidden={tilePart.hidden} unread={tilePart.unread}
                   hiddenByReason={tilePart.hiddenByReason}
                   enabled={enterableOnly && enterableKind !== 'n/a'}
                   kind={enterableKind}
                   note={`Counted over the ${tiles.length} tile${tiles.length === 1 ? '' : 's'} on this page — raise the limit to read further down the scan.`}
                   reasons={tilePart.reasons} unhidden={tilePart.unhidden}
                   onToggleReason={toggleReason} unhideCount={unhide.size}
                   reasonTitle={roomChipTitle}
                   onShowAll={() => setEnterableOnly(false)}
                   onEnterableOnly={() => setEnterableOnly(true)} />
      <div className="cm-grid">
        {tilePart.rows.map((t) => (
          <PatternChart key={`${t.symbol}-${t.href}`} tile={t} study={data?.explosive_study}
                        bandStudy={data?.band_structure_study} />
        ))}
      </div>

      {tilePart.rows.length ? (
        <div className="cm-foot">
          Showing {tilePart.rows.length}
          {data?.matched ? ` of ${data.matched} matches` : ''}
          {data?.scanned ? ` · ${data.scanned} names scanned` : ''}
          {data?.disclaimer ? <div className="cm-disclaimer">{data.disclaimer}</div> : null}
        </div>
      ) : null}

      {/* ICT only, under the board (Ajay 2026-09-03): the tile legend, how far
        * the dormant loop got, every owner constant the backend actually ran
        * with, and the source line. The constants are rendered from the
        * payload, not from a frontend copy, so a changed threshold shows up
        * here on the next scan with no deploy — and nothing here can claim
        * a number the video did not give. */}
      {/* `data.tab` guard: the board keeps the previous tab's payload on
        * screen while the next one loads (same as the tile grid), and a VCP
        * payload must not feed this block for the half second it takes. */}
      {tab === 'ict' && data && !data.warming && (data.tab ?? 'ict') === 'ict' ? (
        <div className="cm-note cm-ict-foot" data-testid="ict-foot">
          <div><strong>Legend</strong></div>
          <ul className="cm-ict-legend">
            {ICT_LEGEND.map((l) => (
              <li key={l.label}>
                <span className="cm-ict-glyph" aria-hidden="true">{l.glyph}</span>{' '}
                <strong>{l.label}</strong> — {l.hint}
              </li>
            ))}
          </ul>
          {data.counts ? (
            <div className="cm-ict-counts">
              <strong>Dormant loop</strong> — {data.counts.macro_n ?? 0} names on the
              daily pass · {data.counts.tapped_n ?? 0} tapped a level ·{' '}
              {data.counts.micro_n ?? 0} ran the {micro} loop
              {data.as_of ? ` · scanned ${String(data.as_of)}` : ''}
            </div>
          ) : null}
          {ictVideoParams.length ? (
            <div className="cm-ict-params" data-testid="ict-video-params">
              <strong>From the video</strong>:{' '}
              {ictVideoParams.map((r) => (
                <span key={r.key} className="cm-badge cm-badge-muted" title={r.key}>
                  {r.label} = {r.value}
                </span>
              ))}
            </div>
          ) : null}
          {ictOwnerParams.length ? (
            <div className="cm-ict-params" data-testid="ict-owner-params">
              <strong>Owner settings</strong> (house values — not from the video):{' '}
              {ictOwnerParams.map((r) => (
                <span key={r.key} className="cm-badge cm-badge-muted" title={r.key}>
                  {r.label} = {r.value}
                </span>
              ))}
            </div>
          ) : null}
          <div className="cm-ict-source">
            <strong>Source</strong> — Ajay's spec +{' '}
            <a href={ictSrc.url} target="_blank"
               rel="noreferrer noopener">{ICT_SOURCE.label}</a>
            {` (${ictSrc.stamps})`}. Not advice.
          </div>
        </div>
      ) : null}
      </>
      )}
      </EnterableFilterProvider>
    </div>
  );
}

export default ChartMaps;
