/* /pullback-ma — Minervini Stage-2 "pullback to the 50-day MA" scanner.
 *
 * Surfaces leaders in a confirmed uptrend (price above a rising 50 > 150 > 200
 * MA stack) that have just made a brief, shallow pullback TOWARD the rising
 * 50-day line on contracting volume — Minervini's "natural reaction / tennis
 * ball" re-entry (Trade Like a Stock Market Wizard, pp.72, 79, 237-238).
 *
 * Pure read of the cron-prewarmed /sepa/pullback-ma list, which itself derives
 * from the latest SEPA scan + cached bars (no second universe). Table mirrors
 * the Dual Momentum page so the two scanners feel consistent.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { InfoButton } from '../components/InfoButton';
import { MarketContextStrip } from '../components/MarketContextStrip';
import { API } from '../lib/apiBase';

type Band = 'tight' | 'mid' | 'deep';

type PullbackRow = {
  symbol: string;
  name?: string | null;
  last_close: number | null;
  pullback_pct: number | null;
  pullback_band: Band | null;
  pct_from_ma50: number | null;
  pct_from_ma200: number | null;
  rs_3m: number | null;
  rs_rank: number | null;
  vol_ratio: number | null;
  vol_healthy: boolean;
  ma50: number | null;
  recent_high: number | null;
  stage: number | null;
  is_sepa_candidate: boolean;
  score?: number | null;
  rank?: number;
};

type PullbackPayload = {
  generated_at: number;
  generated_at_iso: string;
  duration_sec: number;
  config: {
    recent_high_lookback: number;
    vol_avg_lookback: number;
    pullback_zone_ceiling_pct: number;
    bands: { tight_max: number; mid_max: number };
    vol_healthy_max: number;
  };
  rows: PullbackRow[];
  picks: PullbackRow[];
  universe_size: number;
  candidate_count: number;
  scan_generated_at?: number;
  error?: string;
};

const PageInfo = (
  <>
    <p>
      <strong>Pullback to MA</strong> finds leaders in a confirmed Stage-2
      uptrend that have just made a <em>natural reaction</em> — a brief, shallow
      dip back toward the rising 50-day moving average — the constructive
      re-entry Minervini calls <em>tennis-ball action</em> (<em>Trade Like a
      Stock Market Wizard</em>, pp.&nbsp;237–238).
    </p>
    <p>
      Every name here is already in a defined uptrend: price above a rising
      50&nbsp;&gt;&nbsp;150&nbsp;&gt;&nbsp;200-day stack (Trend Template
      criteria&nbsp;#4–5, p.&nbsp;79). The scan then keeps only those that have
      pulled back <em>toward</em> the 50-day rather than running extended above
      it.
    </p>
    <ul>
      <li>
        <strong>Pullback %</strong> — how far price has retraced from its recent
        high. <strong>Tight&nbsp;&lt;5%</strong> = minimal selling, high trend
        integrity; <strong>mid 5–8%</strong> = still acceptable;
        <strong> deep&nbsp;&gt;8%</strong> = wants extra confirmation before an
        entry.
      </li>
      <li>
        <strong>% from MA50</strong> — distance above the 50-day line. The
        closer to <strong>0%</strong>, the more it is testing the 50-day as
        support — the most actionable zone.
      </li>
      <li>
        <strong>RS 3M</strong> — 3-month price return. A positive reading
        confirms the stock was advancing <em>before</em> the pullback began.
      </li>
      <li>
        <strong>Vol Ratio</strong> — today’s volume vs the 20-day average.
        <strong> Below&nbsp;1.0×</strong> is the healthy sign: the dip is
        happening on <em>contracting</em> volume, a controlled reaction rather
        than distribution (p.&nbsp;72).
      </li>
    </ul>
    <p>
      This scanner is not financial advice. It is educational/informational
      only; a pattern working in the past does not guarantee future results.
      Do your own analysis before any trade.
    </p>
  </>
);

function fmtPct(v: number | null | undefined, signed = true): string {
  if (v == null) return '—';
  return `${signed && v > 0 ? '+' : ''}${v.toFixed(1)}%`;
}
function fmtX(v: number | null | undefined): string {
  if (v == null) return '—';
  return `${v.toFixed(2)}×`;
}
function bandClass(b: Band | null | undefined): string {
  return b ? `pb-band pb-band--${b}` : 'pb-band';
}
// % from MA50: nearer to 0 = more actionable -> greener.
function ma50Class(v: number | null | undefined): string {
  if (v == null) return 'dm-pct dm-pct--na';
  if (v <= 2) return 'dm-pct dm-pct--strong';
  if (v <= 5) return 'dm-pct dm-pct--good';
  return 'dm-pct dm-pct--bad';
}
function rs3mClass(v: number | null | undefined): string {
  if (v == null) return 'dm-pct dm-pct--na';
  if (v > 0) return 'dm-pct dm-pct--good';
  return 'dm-pct dm-pct--bad';
}

export function PullbackMaPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<PullbackPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [topN, setTopN] = useState(20);
  const [showAll, setShowAll] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ top_n: String(topN) });
      const r = await fetch(`${API}/sepa/pullback-ma?${params.toString()}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j: PullbackPayload = await r.json();
      setData(j);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [topN]);

  useEffect(() => {
    load();
  }, [load]);

  const display = useMemo(() => {
    if (!data) return [];
    return showAll ? data.rows : data.picks;
  }, [data, showAll]);

  const noScan = data?.error === 'no_scan';

  return (
    <div className="sepa-page dm-page">
      <div className="sepa-page__title">
        <InfoButton title="Pullback to MA">{PageInfo}</InfoButton>
        <div>
          <div className="eyebrow">№ — Setup · Minervini</div>
          <h1 className="display sepa-page__h1">Pullback to MA</h1>
          <p className="lede">
            Stage-2 leaders making a brief, low-volume pullback toward the rising
            50-day moving average — the “tennis ball” re-entry. Reuses the SEPA
            scan universe.
          </p>
        </div>
      </div>

      {/* Whole-market context so it's clear when it's not just your names that
          are red (Ajay 2026-06-04 theme: defensive, market-aware). */}
      <MarketContextStrip />

      {/* Controls */}
      <section className="dm-controls">
        <label>
          <span className="eyebrow">Top N</span>
          <select value={topN} onChange={(e) => setTopN(Number(e.target.value))}>
            {[10, 20, 30, 50].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </label>
        <label className="dm-controls__toggle">
          <input
            type="checkbox"
            checked={showAll}
            onChange={(e) => setShowAll(e.target.checked)}
          />
          <span>Show all candidates</span>
        </label>
        <a
          className="heatmap-panel__finviz"
          href="https://finviz.com/screener.ashx?v=211&f=ta_sma50_pa,ta_sma200_pa50,ta_perf_4wdown&ft=4"
          target="_blank"
          rel="noreferrer"
          title="Open a comparable above-50/200-MA pullback screen on Finviz"
        >
          Finviz pullback screen ↗
        </a>
        <button type="button" className="dm-refresh" onClick={load} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </section>

      {error && (
        <div className="sepa-empty-card">
          <div className="eyebrow">Error</div>
          <p>{error}</p>
        </div>
      )}

      {noScan && (
        <div className="sepa-empty-card">
          <div className="eyebrow">No scan data</div>
          <p>
            Pullback to MA reuses the latest <code>/sepa/scan</code> for its
            universe and cached prices. Open the <strong>SEPA</strong> tab and
            click <strong>Scan</strong> first (or wait for the post-close cron).
          </p>
        </div>
      )}

      {!noScan && data && (
        <section className="dm-results">
          <div className="dm-results__head">
            <div className="eyebrow">
              {showAll
                ? `All candidates (${data.candidate_count})`
                : `Top ${data.picks.length} · most actionable`}
            </div>
            <div className="dm-results__sub mono">
              {data.candidate_count} of {data.universe_size} · {data.duration_sec}s
            </div>
          </div>

          <div className="dm-table-wrap">
            <table className="dm-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Symbol</th>
                  <th>Company</th>
                  <th className="num">Pullback %</th>
                  <th>Depth</th>
                  <th className="num">% from MA50</th>
                  <th className="num">RS 3M</th>
                  <th className="num">Vol Ratio</th>
                  <th>Flags</th>
                </tr>
              </thead>
              <tbody>
                {display.map((row, idx) => (
                  <tr
                    key={row.symbol}
                    className={`dm-row ${row.is_sepa_candidate ? 'dm-row--sepa' : ''}`}
                    onClick={(e) => {
                      const url = `/sepa/${encodeURIComponent(row.symbol)}`;
                      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) {
                        window.open(url, '_blank', 'noopener,noreferrer');
                        return;
                      }
                      navigate(url, { state: { from: '/pullback-ma', label: 'Pullback to MA' } });
                    }}
                    title="Cmd/Ctrl-click to open in new tab"
                  >
                    <td className="mono">{row.rank ?? idx + 1}</td>
                    <td className="mono dm-sym"><strong>{row.symbol}</strong></td>
                    <td className="dm-name" title={row.name ?? ''}>{row.name ?? '—'}</td>
                    <td className="num">{fmtPct(row.pullback_pct, false)}</td>
                    <td>
                      {row.pullback_band && (
                        <span className={bandClass(row.pullback_band)}>{row.pullback_band}</span>
                      )}
                    </td>
                    <td className={`num ${ma50Class(row.pct_from_ma50)}`}>{fmtPct(row.pct_from_ma50)}</td>
                    <td className={`num ${rs3mClass(row.rs_3m)}`}>{fmtPct(row.rs_3m)}</td>
                    <td className={`num ${row.vol_healthy ? 'dm-pct--good' : 'dm-pct--bad'}`}>
                      {fmtX(row.vol_ratio)}
                    </td>
                    <td className="dm-flags">
                      {row.vol_healthy && <span className="dm-flag dm-flag--good" title="Pullback on contracting volume (book p.72)">vol↓</span>}
                      {row.rs_rank != null && <span className="dm-flag dm-flag--neutral" title="RS rank (1–99)">RS {row.rs_rank}</span>}
                      {row.is_sepa_candidate && <span className="dm-flag dm-flag--sepa" title="Also a full SEPA candidate">SEPA</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {display.length === 0 && (
            <div className="sepa-empty-card">
              <div className="eyebrow">No pullbacks right now</div>
              <p>
                No Stage-2 leaders are sitting in a pullback toward their 50-day
                line in the latest scan. In a broad market sell-off that’s
                normal — fewer names hold a rising MA stack.
              </p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
