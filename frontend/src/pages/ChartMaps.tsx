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
import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { PatternChart } from '../components/PatternChart';
import { InfoButton } from '../components/InfoButton';
import {
  CM_TABS, DEFAULT_MIN_TIER, DEFAULT_SORT, TAB_META, THEMES_FIRST_DEFAULT,
  WINNER_SOURCES, boardQuery,
  isThinSample, parseSort, parseSource, parseTab, parseTier, recordLine,
  type CmBoard, type CmTab,
} from '../lib/chartMaps';
import { useSepaScanStream } from '../hooks/useSepaScanStream';
import { SepaScanProgress } from '../components/SepaScanProgress';
import { DemandScanProgress } from '../components/DemandScanProgress';
import { useDemandScanProgress } from '../hooks/useDemandScanProgress';

const UNIVERSES = [
  { key: 'sp1500_plus', label: 'S&P 1500 + themes' },
  { key: 'sp1500', label: 'S&P 1500' },
  { key: 'themes', label: 'Themes only' },
  { key: 'sp500', label: 'S&P 500' },
];

const HowItWorks = (
  <>
    <p>A study board — the same scans you already run, shown as charts instead
      of rows, so the shape is what you remember.</p>
    <ul>
      <li><strong>📐 Strong VCP</strong> — the SEPA scan named VCP as the entry
        setup <em>and</em> the base scored tight (≥70). The green box is the
        base, the solid line the pivot, the dashed line the suggested stop.</li>
      <li><strong>🟢 Back in Demand</strong> — price left a demand zone and has
        come back into it. Band is the zone; BUY / STOP / TARGET are the plan.</li>
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
  const tab = parseTab(params.get('tab'));
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
  const [universe, setUniverse] = useState('sp1500_plus');
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

  const load = useCallback(async () => {
    setErr(null);
    const q = boardQuery({ tab, limit: 24, days, universe, themesFirst, pattern,
                           source, minerviniOnly, sort, minTier });
    try {
      const r = await fetch(`${API}/chart-maps?${q}`, {
        credentials: 'include', cache: 'no-store',
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    } finally {
      setLoading(false);
    }
  }, [tab, days, universe, themesFirst, pattern, source, minerviniOnly, sort, minTier]);

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

  /* The demand scan's live counter, polled faster than the board itself. The
   * board key is the universe the SERVER resolved (`universe_key`), not the
   * dropdown value — the demand board maps sp1500_plus onto its own key and
   * asking for progress under the wrong one returns a permanent idle. */
  const demandProgress = useDemandScanProgress(
    data?.universe_key || universe, Boolean(data?.warming));

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

  const tiles = data?.tiles || [];

  return (
    <div className="cm-page">
      <div className="cm-head">
        <h1 className="cm-title">
          🗺️ Chart Maps
          <InfoButton title="Chart Maps — how to read this board">{HowItWorks}</InfoButton>
        </h1>
        <p className="cm-sub">Just the charts. One shape per tab — learn it by looking.</p>
      </div>

      <div className="cm-tabs" role="tablist">
        {CM_TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t}
                  className={`cm-tab${tab === t ? ' cm-tab-on' : ''}`}
                  onClick={() => setTab(t)}>
            {TAB_META[t].label}
          </button>
        ))}
      </div>

      <p className="cm-blurb">{TAB_META[tab].blurb}</p>

      <div className="cm-controls">
        {tab === 'zones' && (
          <label className="cm-ctl">
            Universe
            <select value={universe} onChange={(e) => setUniverse(e.target.value)}>
              {UNIVERSES.map((u) => <option key={u.key} value={u.key}>{u.label}</option>)}
            </select>
          </label>
        )}
        {tab !== 'winners' && (
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

      {/* The demand tab's own scan. NOT the SEPA stream above it — that one
        * feeds the VCP tab. Both this and the Back in Demand tab on
        * /supply-demand read one demand_reentry cache, so they watch the same
        * job and now show the same counter (Ajay 2026-08-17: "Are you updating
        * both pages when supply demand is getting updated"). */}
      {data?.warming ? (
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
    </div>
  );
}

export default ChartMaps;
