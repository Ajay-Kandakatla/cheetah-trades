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
import { InfoButton } from '../components/InfoButton';
import {
  CM_TABS, DEFAULT_MIN_TIER, DEFAULT_SORT, TAB_META, THEMES_FIRST_DEFAULT,
  quickBounceStudyText, quickBouncePersistenceText, tabUsageKey,
  WINNER_SOURCES, boardQuery, isBoardTab, ROOM_TABS, DEFAULT_MIN_ROOM, parseMinRoom,
  dataThrough, isThinSample, parseSort, parseSource, parseTab, parseTier,
  recordLine, scanStamp,
  DEFAULT_ICT_BIAS, DEFAULT_ICT_MICRO, ICT_BIASES, ICT_LEGEND, ICT_MICROS,
  ICT_SOURCE, ictParamRows, ictSource, parseBias, parseMicro,
  type CmBoard, type CmTab,
} from '../lib/chartMaps';
import { SupportLevels } from '../components/SupportLevels';
import { SignalLabBoard } from '../components/SignalLabBoard';
import { OvernightGappers } from '../components/OvernightGappers';
import SessionBoard from '../components/SessionBoard';
import HotSectors from '../components/HotSectors';
import OverlayLegend from '../components/OverlayLegend';
import { filterTile, loadHidden, presentGroups, saveHidden } from '../lib/chartOverlays';
import { normalizeSymbol, parseTf, parseWindow } from '../lib/supportLevels';
import { useSepaScanStream } from '../hooks/useSepaScanStream';
import { SepaScanProgress } from '../components/SepaScanProgress';
import { DemandScanProgress } from '../components/DemandScanProgress';
import { useDemandScanProgress } from '../hooks/useDemandScanProgress';
import { ZoneEdgeBoard } from '../components/ZoneEdgeBoard';
import { CatalystsBoard } from '../pages/Catalysts';
import { useMyFeatures } from '../hooks/useMyFeatures';
import { RulesInfo } from '../components/RulesInfo';
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
        (open sky first, then the biggest gap) and flag names bouncing off a
        demand band. Room and bounce are a configured price-structure read
        shared with the Demand board — owner settings, not advice.</li>
      <li><strong>📏 Support Levels</strong> — the only tab that is not a board.
        Search any ticker and pick a zoom. The same clustering rule runs over a
        1-month, 3-month, 6-month or 1-year frame, and the answers differ on
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
  const ROOM_TAB = ROOM_TABS.includes(tab);
  const minRoom = parseMinRoom(params.get('room'));
  const setRoom = (v: 'floor' | 'any') => {
    const next = new URLSearchParams(params);
    if (v === 'any') next.set('room', 'any'); else next.delete('room');
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
  const boardSeq = useRef(0);
  const load = useCallback(async () => {
    const my = ++boardSeq.current;
    setErr(null);
    // `/chart-maps` answers an unknown `tab` with the VCP board rather than a
    // 404, so fetching it for the Support tab would quietly draw the wrong
    // charts under the right heading.
    if (!isBoardTab(tab)) { setData(null); setLoading(false); return; }
    const q = boardQuery({ tab, limit: tab === 'gabbar' ? 80 : 24, days,
                           universe, themesFirst, pattern,
                           source, minerviniOnly, sort, minTier, gabbarLevel,
                           gabbarTouchingOnly, phase, target, bias, micro,
                           minRoom: ROOM_TAB ? minRoom : undefined });
    try {
      const r = await fetch(`${API}/chart-maps?${q}`, {
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
  }, [tab, days, universe, themesFirst, pattern, source, minerviniOnly, sort, minTier, gabbarLevel, gabbarTouchingOnly, phase, target, bias, micro, ROOM_TAB, minRoom]);

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

  const rawTiles = data?.tiles || [];
  /* The chart ledger (Ajay 2026-08-31: "Chart feel so clumsy can you give me
   * a ledger and some check boxes to toggle these off"). Hidden families are
   * a per-browser convenience (localStorage), filtered client-side so a
   * toggle never refetches a board. */
  const [hiddenOverlays, setHiddenOverlays] = useState<Set<string>>(() => loadHidden());
  const toggleOverlay = (key: string) => {
    setHiddenOverlays((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      saveHidden(next);
      return next;
    });
  };
  const overlayGroups = useMemo(() => presentGroups(rawTiles), [rawTiles]);
  const tiles = useMemo(
    () => rawTiles.map((t) => filterTile(t, hiddenOverlays)),
    [rawTiles, hiddenOverlays]);
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

      {/* ℹ️ Rules — the board's own picks / stops / alerts from GET
        * /supply-demand/rules (Ajay 2026-09-06). The three boards that carry
        * a rule section; the zones tab is the "in demand" board. */}
      {(tab === 'zones' || tab === 'deep_demand' || tab === 'catalysts' || tab === 'quick_bounce') && (
        <div className="cm-rules" style={{ margin: '0.2rem 0 0.6rem' }}>
          <RulesInfo section={tab === 'zones' ? 'in_demand' : tab} />
        </div>
      )}

      {/* Quick Bounce (Ajay 2026-09-06): the study's own numbers under the
        * blurb — the list is read against its base rate and its persistence,
        * never on its own. */}
      {tab === 'quick_bounce' && data?.study && (
        <p className="cm-note" data-testid="quick-bounce-study">
          Study{data.study.as_of ? ` (${data.study.as_of})` : ''}: {quickBounceStudyText(data.study)}.
          {' '}{quickBouncePersistenceText(data.study.persistence)}
        </p>
      )}

      {/* Reaching vs already reached — only the two demand boards have the two
        * moments. Segmented, not a checkbox: the two states are a choice of
        * WHICH list, not an on/off refinement of one list. */}
      {(tab === 'zones' || tab === 'deep_demand' || LENS_TABS) && (
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
            * its first touch. Deep Demand's second band IS its level, and the
            * lens tabs measure to their own screens' bands. */}
          {/* Room floor (Ajay 2026-09-05), the two demand boards only. Two
            * states, not a slider: the phone's gate (≥ 5% from the live print
            * to the first unbroken band overhead — ALERT_MIN_ROOM_PCT, owner
            * setting) or off. A tile at its lid is hidden by default and
            * counted under the board; Any room shows it. */}
          {ROOM_TAB && (
            <span className="cm-phase-sub" role="tablist" aria-label="Room floor"
                  title={`Room = % from the LIVE print to the first unbroken band overhead (supply not broken under yesterday's close, plus demand bands above). The phone only pages names with ≥ ${DEFAULT_MIN_ROOM}%; this floor hides the rest here too. TRU 2026-09-05: 0.3% under a supply band — hidden.`}>
              <button type="button" role="tab" aria-selected={minRoom !== 0}
                      className={`cm-phase-btn${minRoom !== 0 ? ' cm-phase-on' : ''}`}
                      onClick={() => setRoom('floor')}>
                🧱 Room ≥ {DEFAULT_MIN_ROOM}%
              </button>
              <button type="button" role="tab" aria-selected={minRoom === 0}
                      className={`cm-phase-btn${minRoom === 0 ? ' cm-phase-on' : ''}`}
                      onClick={() => setRoom('any')}>
                Any room
              </button>
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

      {/* Deep Demand opens with the minute-by-minute breaking-resistance
        * board (Ajay 2026-09-03: "and also in to deep demand zones"): names
        * within 1% of breaking their LAST supply band toward new highs. Its
        * own endpoint and clock; the tiles below are the closed-bar scan.
        * This tab only — the other boards do not grow a supply read. */}
      {tab === 'deep_demand' && (
        <ZoneEdgeBoard mode="breaking" compact fromKey="chart-maps" />
      )}

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
        <p className="cm-note" data-testid="hidden-low-room">
          {data.hidden_low_room} hidden: room &lt; {data.min_room ?? DEFAULT_MIN_ROOM}% to the
          first unbroken band overhead on the live print (the phone's own gate) — pick
          {' '}<em>Any room</em> to see them.
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

      <OverlayLegend present={overlayGroups} hidden={hiddenOverlays}
                     onToggle={toggleOverlay} />
      <div className="cm-grid">
        {tiles.map((t) => <PatternChart key={`${t.symbol}-${t.href}`} tile={t} />)}
      </div>

      {tiles.length ? (
        <div className="cm-foot">
          Showing {tiles.length}
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
    </div>
  );
}

export default ChartMaps;
