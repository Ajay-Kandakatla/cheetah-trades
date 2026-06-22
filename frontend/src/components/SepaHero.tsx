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

// ── Universe multi-select (2026-05-30) ──────────────────────────────────
// Orthogonal building blocks the user can mix. `subsetOf` lists the broader
// sets that already CONTAIN this one, so we can flag/skip overlaps: e.g.
// S&P 500 ⊂ Russell 1000 ⊂ Russell 3000. Curated/micro/ETF are independent.
type UnivComp = { key: string; label: string; approx: string; subsetOf: string[] };
const UNIVERSE_COMPONENTS: UnivComp[] = [
  { key: 'curated',     label: 'Curated',      approx: '130',  subsetOf: [] },
  { key: 'sp500',       label: 'S&P 500',      approx: '500',  subsetOf: ['russell1000', 'russell3000'] },
  { key: 'sp400',       label: 'S&P 400',      approx: '400',  subsetOf: ['russell3000'] },
  { key: 'russell1000', label: 'Russell 1000', approx: '1k',   subsetOf: ['russell3000'] },
  { key: 'russell3000', label: 'Russell 3000', approx: '2.6k', subsetOf: [] },
  { key: 'micro',       label: 'Micro-caps',   approx: '1.3k', subsetOf: [] },
  { key: 'etf',         label: 'ETFs',         approx: '370',  subsetOf: [] },
];
const BROAD_SET = ['curated', 'sp500', 'sp400', 'russell3000', 'micro', 'etf'];
// Migrate the old single-mode preference (sepa_mode_v3) to component sets.
const LEGACY_MODE_MAP: Record<string, string[]> = {
  broad: BROAD_SET,
  expanded: ['curated', 'sp500'],
  all_us: ['russell3000', 'micro'],
  russell1000: ['russell1000'],
  russell3000: ['russell3000'],
  sp500: ['sp500'],
  curated: ['curated'],
};

/**
 * SepaHero — top strip with market state, scan freshness, key counts, actions.
 * Color-coded market gate makes "should I be long today?" instantly readable.
 */
export function SepaHero({ data, scanning, onScan }: Props) {
  const [includeCatalyst, setIncludeCatalyst] = useState(true);
  // Universe is now a MULTI-select of building blocks (user 2026-05-30:
  // "make the dropdown multiselect, remove overlaps"). Stored as a string[]
  // of component keys; default = the full broad set. Migrates from the old
  // single-mode preference. Key bumped v3 → v4 for the new shape.
  const [components, setComponents] = useState<string[]>(() => {
    if (typeof window === 'undefined') return BROAD_SET;
    const v4 = localStorage.getItem('sepa_universe_v4');
    if (v4) return v4.split(',').filter(Boolean);
    const v3 = localStorage.getItem('sepa_mode_v3');
    if (v3 && LEGACY_MODE_MAP[v3]) return LEGACY_MODE_MAP[v3];
    return BROAD_SET;
  });
  useEffect(() => {
    if (typeof window !== 'undefined') localStorage.setItem('sepa_universe_v4', components.join(','));
  }, [components]);

  const selectedSet = new Set(components);
  const toggleComp = (key: string) =>
    setComponents((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  // A selected component is "redundant" when a broader selected set already
  // contains it (e.g. S&P 500 when Russell 3000 is on). We DIM it as a hint,
  // but still send it: overlaps are removed by the backend's set-union dedup
  // (each ticker scanned once), and the few names a subset has that the
  // broader snapshot is missing — recent index adds — are still picked up.
  const isRedundant = (c: UnivComp) =>
    selectedSet.has(c.key) && c.subsetOf.some((s) => selectedSet.has(s));
  // Send all selected components in canonical order; backend unions + dedups.
  const effectiveMode =
    UNIVERSE_COMPONENTS.filter((c) => selectedSet.has(c.key))
      .map((c) => c.key)
      .join(',') || 'curated';

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
            ready to enter
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
        <button
          className="sepa-btn sepa-btn--primary"
          onClick={() => onScan(includeCatalyst, { mode: effectiveMode })}
          disabled={scanning}
          title="Re-runs every per-symbol analysis from scratch over the selected universe."
        >
          {scanning ? 'Scanning…' : 'Full Scan'}
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
        <div className="sepa-univ">
          <span className="eyebrow">Universe · mix &amp; match</span>
          <div className="sepa-univ__chips">
            {UNIVERSE_COMPONENTS.map((c) => {
              const on = selectedSet.has(c.key);
              const redundant = isRedundant(c);
              return (
                <button
                  key={c.key}
                  type="button"
                  className={`sepa-chip ${on ? 'is-active' : ''} ${redundant ? 'sepa-univ__chip--redundant' : ''}`}
                  onClick={() => toggleComp(c.key)}
                  disabled={scanning}
                  title={
                    redundant
                      ? `${c.label} is already inside a broader set you've selected — overlap removed, it won't be double-scanned.`
                      : `~${c.approx} names. Tap to ${on ? 'remove' : 'add'}.`
                  }
                >
                  {on ? '✓ ' : ''}{c.label}
                  <span className="sepa-univ__n">{c.approx}</span>
                  {redundant && <span className="sepa-univ__incl">⊂ incl</span>}
                </button>
              );
            })}
            <span className="sepa-univ__sep" />
            <button
              type="button"
              className="sepa-chip sepa-univ__preset"
              onClick={() => setComponents(BROAD_SET)}
              disabled={scanning}
              title="Select everything (the broad universe)"
            >★ All</button>
            <button
              type="button"
              className="sepa-chip sepa-univ__preset"
              onClick={() => setComponents(['russell1000'])}
              disabled={scanning}
              title="Russell 1000 only — fastest scans"
            >⚡ Fast</button>
          </div>
        </div>
      </div>

      {/* Research-cache banner removed — the heavy weekly batch auto-runs
          Sundays 8pm ET via cron, so the manual button was rarely needed
          and added clutter. Full Scan also refreshes research as a side
          effect when needed. */}

      <div className="sepa-hero__actions-help">
        <span><b>Full Scan</b> — re-runs everything from scratch over the selected universe. ~3-15 min depending on size. Refreshes research cache as a side-effect.</span>
        <span><b>Include catalyst</b> — Full-Scan-only. Fetches news, earnings calendar, and analyst revisions for each candidate.</span>
      </div>
    </header>
  );
}
