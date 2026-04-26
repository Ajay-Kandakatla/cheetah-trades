import { useEffect, useState } from 'react';
import type { SepaScan, ResearchStatus } from '../hooks/useSepa';
import { fetchResearchStatus, refreshResearch } from '../hooks/useSepa';
import { InfoButton } from './InfoButton';

const HeroInfo = (
  <>
    <p>
      <strong>Market regime</strong> tells you whether the broad market is in a state
      where buying breakouts has historically worked.
    </p>
    <p>
      It runs Mark Minervini's <strong>Trend Template</strong> on two indexes:
      the <strong>S&amp;P 500 ETF (SPY)</strong> and the <strong>Nasdaq-100 ETF (QQQ)</strong>.
      The template checks price vs. its 50-day, 150-day, and 200-day moving averages,
      plus the slope of the 200-day average.
    </p>
    <ul>
      <li><strong>Confirmed Uptrend</strong> — both indexes pass. Safe to long.</li>
      <li><strong>Mixed</strong> — only one passes. Reduce size, be picky.</li>
      <li><strong>Caution</strong> — neither passes. Stand aside.</li>
    </ul>
    <p>
      Counts on the right show how many stocks were scanned and how many passed each
      stage of the Specific Entry Point Analysis (SEPA) pipeline.
    </p>
  </>
);

type Props = {
  data: SepaScan | null;
  scanning: boolean;
  onScan: (withCatalyst: boolean, opts?: { fast?: boolean; mode?: string }) => void;
  onReload: () => void;
};

function ageHuman(seconds: number | null | undefined): string {
  if (seconds == null) return '—';
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86400)}d ago`;
}

const MARKET_COLOR: Record<string, string> = {
  confirmed_uptrend: 'sepa-mkt--ok',
  mixed:             'sepa-mkt--warn',
  caution:           'sepa-mkt--bad',
};

const MARKET_LABEL: Record<string, string> = {
  confirmed_uptrend: 'Confirmed Uptrend',
  mixed:             'Mixed',
  caution:           'Caution',
};

/**
 * SepaHero — top strip with market state, scan freshness, key counts, actions.
 * Color-coded market gate makes "should I be long today?" instantly readable.
 */
export function SepaHero({ data, scanning, onScan, onReload }: Props) {
  const [includeCatalyst, setIncludeCatalyst] = useState(true);
  const [universeMode, setUniverseMode] = useState<string>(
    (typeof window !== 'undefined' && localStorage.getItem('sepa_mode')) || 'curated'
  );
  const [researchStatus, setResearchStatus] = useState<ResearchStatus | null>(null);
  const [refreshingResearch, setRefreshingResearch] = useState(false);

  useEffect(() => {
    fetchResearchStatus().then(setResearchStatus).catch(() => setResearchStatus(null));
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') localStorage.setItem('sepa_mode', universeMode);
  }, [universeMode]);

  const handleResearchRefresh = async () => {
    if (!confirm('Run heavy research refresh? This takes 5-30 min depending on universe size. Run during market-closed hours.')) return;
    setRefreshingResearch(true);
    try {
      await refreshResearch(universeMode);
      const s = await fetchResearchStatus();
      setResearchStatus(s);
    } catch (e) {
      alert(`Research refresh failed: ${e}`);
    } finally {
      setRefreshingResearch(false);
    }
  };

  const mkt = data?.market_context;
  const mktKey = mkt?.label || 'mixed';
  const mktClass = MARKET_COLOR[mktKey] || 'sepa-mkt--warn';
  const mktLabel = MARKET_LABEL[mktKey] || mktKey;
  const ts = data ? new Date(data.generated_at * 1000) : null;
  const fresh = ts ? (Date.now() - ts.getTime()) / 36e5 : null; // hours

  return (
    <header className="sepa-hero">
      <InfoButton title="Market Regime &amp; Stats">{HeroInfo}</InfoButton>
      <div className={`sepa-hero__market ${mktClass}`}>
        <div className="eyebrow">Market regime</div>
        <div className="sepa-hero__market-label">{mktLabel}</div>
        <div className="sepa-hero__market-sub mono">
          {mkt?.safe_to_long ? '✓ safe to long' : '⚠ not safe to long'}
        </div>
      </div>

      <div className="sepa-hero__stats">
        <div className="sepa-stat">
          <div className="sepa-stat__num">{data?.candidate_count ?? 0}</div>
          <div className="sepa-stat__label">candidates</div>
        </div>
        <div className="sepa-stat">
          <div className="sepa-stat__num">{data?.analyzed ?? 0}</div>
          <div className="sepa-stat__label">analyzed</div>
        </div>
        <div className="sepa-stat">
          <div className="sepa-stat__num">{data?.universe_size ?? 0}</div>
          <div className="sepa-stat__label">universe</div>
        </div>
        <div className="sepa-stat sepa-stat--ts">
          <div className="sepa-stat__num mono">
            {fresh == null ? '—' : fresh < 1 ? `${Math.round(fresh * 60)}m` : `${Math.round(fresh)}h`}
          </div>
          <div className="sepa-stat__label">since last scan</div>
          {ts && (
            <div className="sepa-stat__sub mono" title={ts.toString()}>
              {ts.toLocaleString(undefined, {
                weekday: 'short', month: 'short', day: 'numeric',
                hour: 'numeric', minute: '2-digit',
                timeZoneName: 'short',
              })}
            </div>
          )}
        </div>
      </div>

      <div className="sepa-hero__actions">
        <button className="sepa-btn" onClick={onReload}>Reload</button>
        <button
          className="sepa-btn sepa-btn--primary"
          onClick={() => onScan(false, { fast: true, mode: universeMode })}
          disabled={scanning}
          title="Joins cached weekend research with today's prices — typical 20-30s"
        >
          {scanning ? 'Scanning…' : 'Fast Scan'}
        </button>
        <button
          className="sepa-btn"
          onClick={() => onScan(includeCatalyst, { mode: universeMode })}
          disabled={scanning}
          title="Re-runs every per-symbol analysis from scratch. Slow."
        >
          Full Scan
        </button>
        <label className={`sepa-toggle ${includeCatalyst ? 'is-on' : ''}`}>
          <input
            type="checkbox"
            checked={includeCatalyst}
            onChange={(e) => setIncludeCatalyst(e.target.checked)}
            disabled={scanning}
          />
          <span className="sepa-toggle__track"><span className="sepa-toggle__thumb" /></span>
          <span className="sepa-toggle__label">Include catalyst</span>
        </label>
        <label className="sepa-mode-select">
          <span className="eyebrow">Universe</span>
          <select
            value={universeMode}
            onChange={(e) => setUniverseMode(e.target.value)}
            disabled={scanning}
          >
            <option value="curated">Curated (~130)</option>
            <option value="sp500">S&P 500 (~500)</option>
            <option value="russell1000">Russell 1000 (~1000)</option>
            <option value="expanded">Curated ∪ S&P 500</option>
          </select>
        </label>
      </div>

      {researchStatus && (
        <div className="sepa-research-banner">
          <div className="sepa-research-banner__main">
            <span className="eyebrow">Research cache</span>
            {researchStatus.total ? (
              <span className="mono">
                {researchStatus.fresh}/{researchStatus.total} symbols fresh
                {researchStatus.newest_age_sec != null && (
                  <> · refreshed <strong>{ageHuman(researchStatus.newest_age_sec)}</strong></>
                )}
              </span>
            ) : (
              <span className="mono">empty — run research refresh to enable Fast Scan</span>
            )}
          </div>
          <button
            type="button"
            className="sepa-btn sepa-btn--ghost"
            onClick={handleResearchRefresh}
            disabled={refreshingResearch || scanning}
          >
            {refreshingResearch ? 'Refreshing research…' : 'Refresh research'}
          </button>
        </div>
      )}

      <div className="sepa-hero__actions-help">
        <span><b>Fast Scan</b> — joins Sunday's cached research with today's prices. Typical ~20-30s.</span>
        <span><b>Full Scan</b> — re-runs everything from scratch. ~3-15 min depending on universe size. Refreshes research cache as a side-effect.</span>
        <span><b>Refresh research</b> — only the heavy weekly batch (VCP / Power Play / CANSLIM / liquidity). Auto-runs Sundays 8pm ET via cron.</span>
        <span><b>Include catalyst</b> — Full-Scan-only. Fetches news, earnings calendar, and analyst revisions for each candidate.</span>
      </div>
    </header>
  );
}
