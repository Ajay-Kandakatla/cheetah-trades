import { useEffect, useState } from 'react';
import type { SepaScan } from '../hooks/useSepa';
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
  // Default universe is now 'broad' — Russell 3000 + micro-caps (IWC) + the
  // broad ETF list (~3,600 names, ETFs included). User 2026-05-30 wanted the
  // full universe by default ("it did not give full stack"). Key bumped
  // v2 → v3 so the old sticky 'russell1000' preference doesn't override the
  // new default. Switch back to russell1000 in the dropdown for fast scans.
  const [universeMode, setUniverseMode] = useState<string>(
    (typeof window !== 'undefined' && localStorage.getItem('sepa_mode_v3')) || 'broad'
  );
  useEffect(() => {
    if (typeof window !== 'undefined') localStorage.setItem('sepa_mode_v3', universeMode);
  }, [universeMode]);

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
          <div className="sepa-stat__sub mono" title="Trend Template + Stage 2 + VCP/PowerPlay + early base + liquid">
            buyable now
          </div>
        </div>
        <div className="sepa-stat">
          <div className="sepa-stat__num">{data?.qualifier_count ?? 0}</div>
          <div className="sepa-stat__label">qualifiers</div>
          <div className="sepa-stat__sub mono" title="Minervini Trend Template (book p.79) — Ajay's watchlist">
            watchlist
          </div>
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
            <option value="russell3000">Russell 3000 (~2,600)</option>
            <option value="broad">Broad — R3000 + Micro + ETFs (~3,600)</option>
            <option value="expanded">Curated ∪ S&P 500</option>
          </select>
        </label>
      </div>

      {/* Research-cache banner removed — the heavy weekly batch auto-runs
          Sundays 8pm ET via cron, so the manual button was rarely needed
          and added clutter. Full Scan also refreshes research as a side
          effect when needed. */}

      <div className="sepa-hero__actions-help">
        <span><b>Fast Scan</b> — joins Sunday's cached research with today's prices. Typical ~20-30s.</span>
        <span><b>Full Scan</b> — re-runs everything from scratch. ~3-15 min depending on universe size. Refreshes research cache as a side-effect.</span>
        <span><b>Include catalyst</b> — Full-Scan-only. Fetches news, earnings calendar, and analyst revisions for each candidate.</span>
      </div>
    </header>
  );
}
