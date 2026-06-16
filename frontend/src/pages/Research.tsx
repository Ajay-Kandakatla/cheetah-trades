/* Research — bullish vs bearish pattern mining + the insider thesis.

   Ajay 2026-06-04: "validate my thesis (bullish stocks have insiders), find
   other indicators winners share vs losers, use ranking too, multiple agents,
   a page I can keep using." Live prevalence numbers come from /research/patterns;
   the plain-English interpretation + adversarial caveats come from a multi-agent
   pass baked into researchContent.ts. The page merges them by pattern key. */
import { useResearch, type PatternRow } from '../hooks/useResearch';
import { RESEARCH_CONTENT, type PatternNote } from '../lib/researchContent';
import { InfoButton } from '../components/InfoButton';

const PageInfo = (
  <div>
    <p><strong>What this is.</strong> A study of the latest scan: stocks are split
    into a <em>bullish</em> third and a <em>bearish</em> third by their trailing
    3-month return, then every signal the app tracks is checked for how often it
    shows up in each group.</p>
    <p><strong>Lift</strong> = bullish% − bearish%. A big positive lift is a
    winner's tell; a big negative lift is a loser's tell. Cohorts are defined by
    return alone, so the signals aren't graded against themselves.</p>
  </div>
);

function ago(sec?: number): string {
  if (sec == null) return '';
  if (sec < 3600) return `${Math.round(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`;
  return `${Math.round(sec / 86400)}d ago`;
}

const CONF_META: Record<PatternNote['confidence'], { dot: string; label: string }> = {
  high: { dot: '🟢', label: 'high confidence' },
  medium: { dot: '🟡', label: 'medium confidence' },
  low: { dot: '🔴', label: 'low confidence — read caveat' },
};

/** One pattern row: live bull/bear bars + the authored explanation. `live` may
 *  be null for proposed rank-trajectory patterns not yet measured. */
function PatternCard({ note, live }: { note: PatternNote; live?: PatternRow }) {
  const conf = CONF_META[note.confidence];
  const bull = live?.bull_pct ?? null;
  const bear = live?.bear_pct ?? null;
  const lift = live?.lift ?? null;
  const proposed = !live;
  return (
    <div className={`rsx-card rsx-card--${note.confidence}`}>
      <div className="rsx-card__head">
        <span className="rsx-card__label">{note.label}</span>
        {proposed
          ? <span className="rsx-card__lift rsx-card__lift--proposed" title="A pattern the agents proposed using rank history — not yet wired into the live numbers.">proposed</span>
          : lift != null && <span className={`rsx-card__lift ${lift >= 0 ? 'is-bull' : 'is-bear'}`}>{lift >= 0 ? '+' : ''}{lift} pts</span>}
      </div>

      {!proposed && (
        <div className="rsx-bars" title="How often this signal is true in each cohort.">
          <div className="rsx-bar">
            <span className="rsx-bar__tag">winners</span>
            <div className="rsx-bar__track"><div className="rsx-bar__fill is-bull" style={{ width: `${bull ?? 0}%` }} /></div>
            <span className="rsx-bar__pct mono">{bull ?? '—'}%</span>
          </div>
          <div className="rsx-bar">
            <span className="rsx-bar__tag">losers</span>
            <div className="rsx-bar__track"><div className="rsx-bar__fill is-bear" style={{ width: `${bear ?? 0}%` }} /></div>
            <span className="rsx-bar__pct mono">{bear ?? '—'}%</span>
          </div>
        </div>
      )}

      <p className="rsx-card__plain">{note.plain_english}</p>
      <div className="rsx-card__conf" title={conf.label}>{conf.dot} {conf.label}</div>
      {note.caveat && <p className="rsx-card__caveat">⚠️ {note.caveat}</p>}
    </div>
  );
}

export function ResearchPage() {
  const { data, loading, err } = useResearch();
  const liveByKey: Record<string, PatternRow> = {};
  for (const p of [...(data?.bullish_patterns ?? []), ...(data?.bearish_patterns ?? []), ...(data?.overlap_patterns ?? [])]) {
    liveByKey[p.key] = p;
  }
  const th = data?.insider_thesis;

  return (
    <div className="sepa-page rsx-page">
      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">Winners vs losers</div>
          <h1 className="display sepa-page__h1" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            Research
            <InfoButton inline title="Research">{PageInfo}</InfoButton>
          </h1>
          <p className="lede">
            What do the stocks that are <strong>going up</strong> have in common — and
            what do the <strong>fallers</strong> share? Built by splitting the latest
            scan into winners and losers by 3-month return, then measuring every signal.
          </p>
        </div>
      </div>

      {loading && <div className="rsx-loading">Crunching the latest scan…</div>}
      {err && <div className="sepa-err">Couldn't load research: {err}</div>}

      {data && !data.ok && (
        <div className="sepa-empty-card"><p>Not enough price history in the latest scan to run the study yet — run a scan and check back.</p></div>
      )}

      {data && data.ok && (
        <>
          {/* ── The thesis ─────────────────────────────────────────── */}
          <section className="rsx-thesis">
            <div className="rsx-thesis__head">
              <span className="rsx-thesis__eyebrow">Your thesis · “bullish stocks have insiders, falling ones don’t”</span>
              <span className="rsx-thesis__verdict">Partly true — and it inverts</span>
            </div>
            <p className="rsx-thesis__body">{RESEARCH_CONTENT.thesis_verdict}</p>
            {th && th.bull && th.bear && (
              <div className="rsx-thesis__metrics">
                <ThesisMetric label="Any insider filing (30d)" bull={th.bull.any_form4_pct} bear={th.bear.any_form4_pct} />
                <ThesisMetric label="Actual open-market BUY" bull={th.bull.open_market_buy_pct} bear={th.bear.open_market_buy_pct} />
                <ThesisMetric label="Cluster buy (≥2 insiders)" bull={th.bull.cluster_buy_pct} bear={th.bear.cluster_buy_pct} />
              </div>
            )}
            <div className="rsx-thesis__foot mono">
              {th && th.bull ? `EDGAR sample · ${th.bull.n}+${th.bear?.n} stocks · refreshed ${ago(th.age_sec)}${th.stale ? ' · stale' : ''}` : 'Insider thesis refreshing — nightly EDGAR pass.'}
            </div>
          </section>

          {/* ── Cohort context ─────────────────────────────────────── */}
          <div className="rsx-cohorts mono">
            <span><strong>{data.universe_n}</strong> stocks studied · <strong>{data.cohort_n}</strong> per cohort</span>
            {data.bull_return_band && <span className="rsx-cohorts__bull">winners: {data.bull_return_band.min}%…{data.bull_return_band.max}% (3-mo)</span>}
            {data.bear_return_band && <span className="rsx-cohorts__bear">losers: {data.bear_return_band.min}%…{data.bear_return_band.max}%</span>}
          </div>

          {/* ── Bullish patterns (emphasised) ──────────────────────── */}
          <section className="rsx-section">
            <h2 className="rsx-section__title rsx-section__title--bull">📈 What winners share <span className="rsx-section__sub">{RESEARCH_CONTENT.bullish.length} patterns</span></h2>
            <p className="rsx-section__lede">{RESEARCH_CONTENT.watch_summary}</p>
            <div className="rsx-grid">
              {RESEARCH_CONTENT.bullish.map((n) => <PatternCard key={n.key} note={n} live={liveByKey[n.key]} />)}
            </div>
          </section>

          {/* ── Bearish patterns ───────────────────────────────────── */}
          <section className="rsx-section">
            <h2 className="rsx-section__title rsx-section__title--bear">📉 What fallers share <span className="rsx-section__sub">{RESEARCH_CONTENT.bearish.length} patterns</span></h2>
            <div className="rsx-grid">
              {RESEARCH_CONTENT.bearish.map((n) => <PatternCard key={n.key} note={n} live={liveByKey[n.key]} />)}
            </div>
          </section>

          {/* ── Overlaps + caveats ─────────────────────────────────── */}
          <section className="rsx-section">
            <h2 className="rsx-section__title">🔁 No separation (don’t over-read these)</h2>
            <ul className="rsx-overlaps">
              {RESEARCH_CONTENT.overlaps.map((o, i) => <li key={i}>{o}</li>)}
            </ul>
          </section>

          <section className="rsx-caveats">
            <h2 className="rsx-section__title">🧪 How to read this · honest caveats</h2>
            <ul>
              {RESEARCH_CONTENT.key_caveats.map((c, i) => <li key={i}>{c}</li>)}
            </ul>
            <p className="rsx-caveats__foot">
              Not financial advice — this is a data read of the current scan, not a recommendation.
              Numbers recompute every time you open the page; the insider thesis refreshes nightly.
            </p>
          </section>
        </>
      )}
    </div>
  );
}

function ThesisMetric({ label, bull, bear }: { label: string; bull: number | null | undefined; bear: number | null | undefined }) {
  const b = bull ?? 0, r = bear ?? 0;
  const winnerHigher = b >= r;
  return (
    <div className="rsx-tmetric">
      <div className="rsx-tmetric__label">{label}</div>
      <div className="rsx-tmetric__row">
        <span className="rsx-tmetric__side">winners <strong className="is-bull">{bull ?? '—'}%</strong></span>
        <span className="rsx-tmetric__vs">vs</span>
        <span className="rsx-tmetric__side">losers <strong className="is-bear">{bear ?? '—'}%</strong></span>
      </div>
      <div className={`rsx-tmetric__verdict ${winnerHigher ? 'is-bull' : 'is-bear'}`}>
        {winnerHigher ? '↑ higher in winners' : '↓ higher in fallers'}
      </div>
    </div>
  );
}
