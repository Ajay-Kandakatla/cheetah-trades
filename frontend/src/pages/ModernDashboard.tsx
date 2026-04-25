import { useState, useEffect } from 'react';
import { FormulaCard } from '../components/FormulaCard';
import { IndicatorsCard } from '../components/IndicatorsCard';
import { CheetahTable } from '../components/CheetahTable';
import { CompetitorScoutCard } from '../components/CompetitorScoutCard';
import { UnicornsCard } from '../components/UnicornsCard';
import { EtfsCard } from '../components/EtfsCard';
import { NewsPanel } from '../components/NewsPanel';
import { RefreshButton } from '../components/RefreshButton';
import { useCheetahStocks } from '../hooks/useCheetahStocks';
import { SepaBriefBanner } from '../components/SepaBriefBanner';

export function ModernDashboard() {
  const { stocks, computedAt, error, loading, refetch } = useCheetahStocks();
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  return (
    <div className="cm-page">
      <SepaBriefBanner />
      {/* -------------------------------------------------------------- */}
      {/*  Editorial head                                                */}
      {/* -------------------------------------------------------------- */}
      <header className="cm-pagehead">
        <div className="cm-pagehead__col">
          <div className="eyebrow">№ 01 — Methodology</div>
          <h1 className="display cm-pagehead__title">The Cheetah Score</h1>
          <p className="lede">
            A 0–100 composite blending five factor groups, tuned for short
            horizons where growth and momentum lead and quality, stability, and
            value act as ballast.
          </p>
        </div>
        <div className="cm-pagehead__aside">
          <RefreshButton onClick={refetch} loading={loading} computedAt={computedAt} />
        </div>
      </header>

      <aside className="cm-disclaimer">
        <span className="cm-disclaimer__label">Disclosure</span>
        <p>
          Not financial advice. Cheetah Scores are heuristic composites drawn
          from public data and analyst reports. Short-term trading carries
          substantial risk of loss — do your own due diligence and consider
          speaking with a licensed advisor.
        </p>
      </aside>

      {/* -------------------------------------------------------------- */}
      {/*  Formula plate + factor specimen                               */}
      {/* -------------------------------------------------------------- */}
      <section className="cm-section">
        <div className="cm-section__head">
          <div className="eyebrow">§ Composition</div>
          <h2 className="cm-section__title">Factors &amp; weights</h2>
        </div>
        <FormulaCard />
      </section>

      {/* -------------------------------------------------------------- */}
      {/*  Indicators + experts                                          */}
      {/* -------------------------------------------------------------- */}
      <section className="cm-section">
        <div className="cm-section__head">
          <div className="eyebrow">§ Instruments</div>
          <h2 className="cm-section__title">Indicators, formulas, and the frameworks behind them</h2>
        </div>
        <IndicatorsCard />
      </section>

      {/* -------------------------------------------------------------- */}
      {/*  Tier 1 + competitors                                          */}
      {/* -------------------------------------------------------------- */}
      <section className="cm-section">
        <div className="cm-section__head">
          <div className="eyebrow">№ 02 — Holdings</div>
          <h2 className="cm-section__title">Tier 1 cheetahs and their competitors</h2>
          <p className="cm-section__note">
            Tier 2 — established rivals with meaningful share. Tier 3 — emerging,
            smaller, or higher-risk challengers.
          </p>
        </div>

        <div className="cm-legend">
          <span className="cm-legend__item"><span className="cm-swatch cm-swatch--growth" />Growth</span>
          <span className="cm-legend__item"><span className="cm-swatch cm-swatch--momentum" />Momentum</span>
          <span className="cm-legend__item"><span className="cm-swatch cm-swatch--quality" />Quality</span>
          <span className="cm-legend__item"><span className="cm-swatch cm-swatch--value" />Value</span>
          <span className="cm-legend__item"><span className="cm-swatch cm-swatch--stability" />Stability</span>
        </div>

        {error && (
          <div className="cm-alert">
            <span className="cm-alert__label">Error</span>
            <p>
              Failed to load Cheetah data: {error}. Make sure the backend is
              running at <code className="mono">localhost:8000</code>.
            </p>
          </div>
        )}

        {!stocks && !error && (
          <div className={`cm-loading ${isMounted ? 'is-visible' : ''}`}>
            <span className="eyebrow">Loading</span>
            <span className="cm-loading__dots">
              <span /><span /><span />
            </span>
          </div>
        )}

        {stocks && (
          <>
            <CheetahTable stocks={stocks} />
            <div className="cm-grid-3">
              <CompetitorScoutCard />
              <UnicornsCard />
              <EtfsCard />
            </div>
          </>
        )}
      </section>

      {/* -------------------------------------------------------------- */}
      {/*  News                                                          */}
      {/* -------------------------------------------------------------- */}
      <section className="cm-section">
        <div className="cm-section__head">
          <div className="eyebrow">№ 03 — Wires</div>
          <h2 className="cm-section__title">Market news</h2>
        </div>
        <NewsPanel />
      </section>
    </div>
  );
}
