import { FormulaCard } from '../components/FormulaCard';
import { IndicatorsCard } from '../components/IndicatorsCard';
import { CheetahTable } from '../components/CheetahTable';
import { CompetitorScoutCard } from '../components/CompetitorScoutCard';
import { UnicornsCard } from '../components/UnicornsCard';
import { EtfsCard } from '../components/EtfsCard';
import { NewsPanel } from '../components/NewsPanel';
import { RefreshButton } from '../components/RefreshButton';
import { useCheetahStocks } from '../hooks/useCheetahStocks';

export function Dashboard() {
  const { stocks, computedAt, error, loading, refetch } = useCheetahStocks();

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Cheetah Stocks Dashboard</h1>
          <div className="page-sub">
            Short-term growth screener · Tier 1 cheetahs + Tier 2 public rivals + private unicorns + thematic ETFs · Real-time news
          </div>
        </div>
        <RefreshButton onClick={refetch} loading={loading} computedAt={computedAt} />
      </div>

      <div className="disclaimer">
        <strong>Not financial advice.</strong> Cheetah Scores are heuristic composites
        from public data and analyst reports. Short-term trading carries substantial
        risk of loss. Do your own due diligence and consider speaking with a licensed
        financial advisor.
      </div>

      <FormulaCard />
      <IndicatorsCard />

      <section className="card">
        <h2>Tier 1 Cheetahs &amp; competitors</h2>
        <p className="muted">
          Tier 2 = established rivals with meaningful share · Tier 3 = emerging / smaller / higher-risk challengers.
          Key Signals pills are color-coded: <span className="signal-pill growth">Growth</span>
          <span className="signal-pill momentum">Momentum</span>
          <span className="signal-pill quality">Quality</span>
          <span className="signal-pill value">Value</span>
          <span className="signal-pill stability">Stability</span>
        </p>
      </section>

      {error && (
        <div className="error-card">
          Failed to load Cheetah data: {error}. Make sure the backend is running at{' '}
          <code>localhost:8000</code>.
        </div>
      )}
      {!stocks && !error && <div className="loading">Loading…</div>}
      {stocks && <CheetahTable stocks={stocks} />}

      <CompetitorScoutCard />
      <UnicornsCard />
      <EtfsCard />
      <NewsPanel />
    </div>
  );
}
