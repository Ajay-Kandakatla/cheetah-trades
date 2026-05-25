/**
 * Pioneers — breakthrough-news ranker, themed + auto-discovered.
 *
 * Themes are curated (AI infra, AI storage, SMR nuclear, quantum, GLP-1,
 * genomics, robotics, defense tech, cybersecurity, fusion). Discoveries are
 * tickers from the latest SEPA scan that aren't in any theme but have
 * unusually dense breakthrough news flow ("Seagate moments").
 *
 * Each card shows: ticker, company name, SEPA score, RS rank, Dual Momentum
 * status, breakthrough headlines that scored highest. Click → SEPA candidate
 * page for that ticker.
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { InfoButton } from '../components/InfoButton';
import { API } from '../lib/apiBase';


type Headline = { title: string; link: string; pub: string; score: number };

type PioneerRow = {
  symbol: string;
  name?: string | null;
  sepa_score?: number | null;
  rating?: string | null;
  rs_rank?: number | null;
  is_etf?: boolean;
  is_candidate?: boolean;
  in_universe?: boolean;
  dual_momentum?: {
    return_12m: number | null;
    abs_mom_pass: boolean;
    beats_spy: boolean | null;
  } | null;
  news_score: number;
  breakthrough_count: number;
  total_news?: number;
  top_headlines: Headline[];
  pioneer_score: number;
};

type Theme = {
  theme_id: string;
  label: string;
  summary: string;
  keywords: string[];
  total_pioneer_score: number;
  tickers: PioneerRow[];
};

type PioneersPayload = {
  generated_at: number;
  generated_at_iso: string;
  themes: Theme[];
  discoveries: PioneerRow[];
  ranked_count: number;
  error?: string;
  message?: string;
};

const PageInfo = (
  <>
    <p>
      <strong>Pioneers</strong> tracks breakthrough categories where genuine
      industry shifts are happening — and surfaces the tickers riding them.
    </p>
    <p>
      <strong>Pioneer score</strong> blends three signals so news alone with
      weak fundamentals can't dominate the ranking:
    </p>
    <ul>
      <li>
        <strong>Breakthrough news density</strong> over the last ~30 days.
        Headlines containing terms like "FDA approval", "first-in-class",
        "patent granted", "milestone", "$1 billion deal", or theme-specific
        keywords (e.g. "HAMR", "SMR", "GLP-1") score higher.
      </li>
      <li>
        <strong>Specific Entry Point Analysis (SEPA) composite score</strong>{' '}
        — the ticker's overall Minervini score divided by 100, used as a
        multiplier so quality stocks float to the top within each theme.
      </li>
      <li>
        <strong>Dual Momentum boost</strong> — a 1.5× multiplier when the
        ticker passes Antonacci's two-gate filter (12m return positive AND
        beats SPDR S&amp;P 500 ETF (SPY)).
      </li>
    </ul>
    <p>
      <strong>Discoveries</strong> are off-theme tickers with high pioneer
      score — e.g. a name like Seagate that isn't in a pre-baked theme but
      has dense breakthrough news (HAMR storage, AI-data-center tailwinds).
    </p>
    <p>
      <em>News fetching is bounded-concurrent (8 in flight) and cached 30
      min per ticker. First page load can take 30-60 seconds for ~100
      tickers; subsequent loads are instant.</em>
    </p>
  </>
);

function fmtScore(n: number | null | undefined): string {
  if (n == null) return '—';
  return Math.round(n).toString();
}

function timeAgo(iso: string): string {
  const t = Date.parse(iso);
  if (!t) return '';
  const diffMin = Math.floor((Date.now() - t) / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffMin < 60 * 24) return `${Math.floor(diffMin / 60)}h ago`;
  return `${Math.floor(diffMin / (60 * 24))}d ago`;
}

function PioneerRowCard({ row, onOpen }: { row: PioneerRow; onOpen: (sym: string, e?: React.MouseEvent) => void }) {
  const dmEligible = row.dual_momentum?.abs_mom_pass && row.dual_momentum?.beats_spy;
  return (
    <article className="pioneer-row" onClick={(e) => onOpen(row.symbol, e)} title="Cmd/Ctrl-click to open in new tab">
      <header className="pioneer-row__head">
        <div className="pioneer-row__sym">
          <strong className="mono">{row.symbol}</strong>
          {row.is_etf && <span className="sepa-tag sepa-tag--etf">ETF</span>}
          {row.is_candidate && <span className="sepa-tag sepa-tag--candidate">SEPA candidate</span>}
        </div>
        <div className="pioneer-row__scores mono">
          <span title="Pioneer score = news × SEPA × Dual Momentum boost">
            <strong>{Math.round(row.pioneer_score)}</strong> pioneer
          </span>
          <span className="pioneer-row__sep">·</span>
          <span title="SEPA composite score">SEPA {fmtScore(row.sepa_score)}</span>
          {row.rs_rank != null && (
            <>
              <span className="pioneer-row__sep">·</span>
              <span title="Relative Strength rank">RS {row.rs_rank}</span>
            </>
          )}
          {dmEligible && (
            <>
              <span className="pioneer-row__sep">·</span>
              <span className="pioneer-row__dm" title="Dual Momentum eligible">DM ✓</span>
            </>
          )}
        </div>
      </header>
      {row.name && <div className="pioneer-row__name">{row.name}</div>}
      {row.top_headlines.length > 0 && (
        <ul className="pioneer-row__headlines">
          {row.top_headlines.slice(0, 3).map((h, i) => (
            <li key={i}>
              <a href={h.link} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
                {h.title}
              </a>
              {h.pub && <span className="pioneer-row__pub mono"> · {h.pub.split(',').pop()?.trim()}</span>}
            </li>
          ))}
        </ul>
      )}
      <div className="pioneer-row__foot mono">
        {row.breakthrough_count > 0
          ? `${row.breakthrough_count} breakthrough headline${row.breakthrough_count === 1 ? '' : 's'} of ${row.total_news ?? '—'} relevant news`
          : 'no breakthrough-flavored headlines · ranking by SEPA + theme membership only'}
      </div>
    </article>
  );
}

export function PioneersPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<PioneersPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/sepa/pioneers`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j: PioneersPayload = await r.json();
      setData(j);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openSymbol = (sym: string, e?: React.MouseEvent) => {
    const url = `/sepa/${encodeURIComponent(sym)}`;
    if (e && (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1)) {
      window.open(url, '_blank', 'noopener,noreferrer');
      return;
    }
    navigate(url, { state: { from: '/pioneers', label: 'Pioneers' } });
  };

  return (
    <div className="sepa-page">
      <div className="sepa-page__title">
        <InfoButton title="Pioneers — Breakthrough Tracker">{PageInfo}</InfoButton>
        <div>
          <div className="eyebrow">№ 09 — Breakthrough Tracker</div>
          <h1 className="display sepa-page__h1">Pioneers</h1>
          <p className="lede">
            Curated breakthrough categories + auto-discoveries from today's
            news flow. Cross-references the latest SEPA scan + Dual Momentum
            so signal beats noise.
          </p>
        </div>
      </div>

      <section className="dm-controls">
        <button type="button" className="dm-refresh" onClick={load} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
        {data?.generated_at_iso && (
          <span className="mono" style={{ color: 'var(--ink-faint)', fontSize: '0.78rem' }}>
            Last refresh: {timeAgo(data.generated_at_iso)}
          </span>
        )}
      </section>

      {error && (
        <div className="sepa-empty-card">
          <div className="eyebrow">Error</div>
          <p>{error}</p>
        </div>
      )}

      {data?.error === 'no_scan' && (
        <div className="sepa-empty-card">
          <div className="eyebrow">No scan data</div>
          <p>
            Pioneers reuses the latest <code>/sepa/scan</code>. Open the SEPA
            tab and click <strong>Fast Scan</strong> first, then come back.
          </p>
        </div>
      )}

      {loading && !data && (
        <div className="sepa-drawer__loading">
          <div className="eyebrow">Loading pioneer data…</div>
          <p className="mono" style={{ color: 'var(--ink-faint)', fontSize: '0.8rem' }}>
            First load fetches breakthrough news for ~100 tickers. ~30-60 seconds.
          </p>
        </div>
      )}

      {data && !data.error && (
        <>
          {data.discoveries.length > 0 && (
            <section className="pioneer-section pioneer-section--discoveries">
              <div className="eyebrow">
                Discoveries · off-theme tickers with breakthrough news traction
              </div>
              <div className="pioneer-grid">
                {data.discoveries.map((row) => (
                  <PioneerRowCard key={row.symbol} row={row} onOpen={openSymbol} />
                ))}
              </div>
            </section>
          )}

          {data.themes.map((theme) => {
            const present = theme.tickers.filter((t) => t.in_universe);
            if (present.length === 0) return null;
            return (
              <section key={theme.theme_id} className="pioneer-section">
                <div className="pioneer-section__head">
                  <div>
                    <div className="eyebrow">{theme.label}</div>
                    <p className="pioneer-section__summary">{theme.summary}</p>
                  </div>
                  <div className="pioneer-section__total mono">
                    {Math.round(theme.total_pioneer_score)} total pioneer score
                  </div>
                </div>
                <div className="pioneer-grid">
                  {theme.tickers.map((row) => (
                    <PioneerRowCard key={row.symbol} row={row} onOpen={openSymbol} />
                  ))}
                </div>
              </section>
            );
          })}
        </>
      )}
    </div>
  );
}
