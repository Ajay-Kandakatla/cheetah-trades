import { useState } from 'react';
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
  onScan: (withCatalyst: boolean) => void;
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
          onClick={() => onScan(includeCatalyst)}
          disabled={scanning}
        >
          {scanning ? 'Scanning…' : 'Scan'}
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
      </div>
      <div className="sepa-hero__actions-help">
        <span><b>Reload</b> — re-read the last cached scan, no network calls.</span>
        <span><b>Scan</b> — runs the full pipeline. Fast (~30s) with catalyst <b>off</b>; slow (~2-4 min) with it <b>on</b>.</span>
        <span><b>Include catalyst</b> — when on, the scan also fetches news, earnings calendar, and analyst revisions for each candidate. Required to populate the <b>Catalyst</b> and <b>Fundamentals</b> tabs.</span>
      </div>
    </header>
  );
}
