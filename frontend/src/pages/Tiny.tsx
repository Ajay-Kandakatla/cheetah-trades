import { useState, useMemo } from 'react';
import { useTinyList, useTinyMethodology, type TinyCandidate, type TinyTier, type TinyComponent } from '../hooks/useTinyStocks';
import { TickerLink } from '../components/TickerLink';
import { WatchlistButton } from '../components/WatchlistButton';
import { InfoButton } from '../components/InfoButton';

/* ==========================================================================
   /tiny — Pounce Tiny Score (PTS) ranked candidates.
   Composite scorer based on widely-cited frameworks:
     CANSLIM (O'Neil) · Tiny Titans (O'Shaughnessy) · Pioneer themes ·
     Catalyst proximity · Frenzy radar · Insider clusters · Float mechanics
   Each tier emits a calibration observation, so accuracy auto-tracks at
   /track under tiny_tier_* sources.
   ========================================================================== */

const TIER_LABEL: Record<TinyTier, { label: string; tone: string }> = {
  TINY_STRONG: { label: '★ Strong', tone: 'good' },
  TINY_BUY:    { label: 'Buy',      tone: 'good' },
  TINY_WATCH:  { label: 'Watch',    tone: 'mid'  },
};

const COMPONENT_LABEL: Record<TinyComponent, string> = {
  canslim:     'CANSLIM',
  tiny_titans: 'Tiny Titans',
  pioneer:     'Pioneer theme',
  catalyst:    'Catalyst',
  frenzy:      'Frenzy',
  insider:     'Insider',
  float:       'Float',
};

const COMPONENT_MAX: Record<TinyComponent, number> = {
  canslim: 20, tiny_titans: 15, pioneer: 15, catalyst: 15,
  frenzy: 15, insider: 10, float: 10,
};

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—';
  const s = v >= 0 ? '+' : '';
  return `${s}${v.toFixed(2)}%`;
}

const InfoContent = ({ methodology }: { methodology: ReturnType<typeof useTinyMethodology> }) => {
  if (!methodology) return <p>Loading methodology…</p>;
  return (
    <>
      <p>
        <strong>{methodology.name}</strong> — composite 0-{methodology.max_score} score
        for small/micro-cap stocks. Designed differently than Minervini's SEPA
        because tiny stocks don't have institutional sponsorship — instead
        they're driven by themes, catalysts, and float mechanics.
      </p>
      <p><strong>Components (weighted):</strong></p>
      <ul>
        {methodology.components.map((c, i) => (
          <li key={i}>
            <strong>{c.name}</strong> ({c.weight} pts) — <em style={{ color: 'var(--ink-muted)' }}>{c.source}</em>
          </li>
        ))}
      </ul>
      <p><strong>Tiers:</strong></p>
      <ul>
        {methodology.tiers.map((t, i) => (
          <li key={i}>
            <strong>{t.label}</strong> (≥{t.min_score}) — {t.interpretation}
          </li>
        ))}
      </ul>
      <p><strong>Hard gates:</strong></p>
      <ul>
        {methodology.hard_gates.map((g, i) => <li key={i}>{g}</li>)}
      </ul>
      <p style={{ padding: '0.6rem 0.8rem', background: 'var(--gold-faint)', borderLeft: '3px solid var(--gold)', borderRadius: 3 }}>
        Every PTS-flagged ticker logs a calibration observation under
        <code> tiny_tier_*</code>. See <strong>/track</strong> Calibration tab
        for hit rate by tier — the system learns which tiers actually pay off
        over time.
      </p>
    </>
  );
};

export default function TinyPage() {
  const [minTier, setMinTier] = useState<TinyTier>('TINY_WATCH');
  const { rows, loading, generatedAt } = useTinyList(minTier, 80);
  const methodology = useTinyMethodology();

  const counts = useMemo(() => {
    const c = { TINY_STRONG: 0, TINY_BUY: 0, TINY_WATCH: 0 };
    for (const r of rows) c[r.tiny_tier as TinyTier]++;
    return c;
  }, [rows]);

  return (
    <div className="tiny-page">
      <div className="tiny-page__title">
        <InfoButton title="Pounce Tiny Score">
          <InfoContent methodology={methodology} />
        </InfoButton>
        <div>
          <div className="eyebrow">№ 16 — Small caps</div>
          <h1 className="display tiny-page__h1">Tiny Stocks</h1>
          <p className="lede">
            Pounce Tiny Score — composite ranking for small/micro caps using
            CANSLIM, Tiny Titans, your Pioneer themes, catalysts, and the
            Frenzy Radar. Click ⓘ for the full methodology + citations.
          </p>
        </div>
      </div>

      <div className="tiny-tabs">
        {([
          { k: 'TINY_STRONG' as TinyTier, label: `★ Strong${counts.TINY_STRONG ? ` · ${counts.TINY_STRONG}` : ''}` },
          { k: 'TINY_BUY'    as TinyTier, label: `Buy${counts.TINY_BUY ? ` · ${counts.TINY_BUY}` : ''}` },
          { k: 'TINY_WATCH'  as TinyTier, label: `All (Watch+)${rows.length ? ` · ${rows.length}` : ''}` },
        ]).map(({ k, label }) => (
          <button key={k}
                  className={`sepa-chip ${minTier === k ? 'is-active' : ''}`}
                  onClick={() => setMinTier(k)}>
            {label}
          </button>
        ))}
        {generatedAt && (
          <span className="tiny-tabs__generated mono">
            scan {new Date(generatedAt * 1000).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
          </span>
        )}
      </div>

      {loading ? (
        <div className="tiny-empty">Loading tiny candidates…</div>
      ) : rows.length === 0 ? (
        <div className="tiny-empty">
          <p><strong>No tiny candidates at this tier right now.</strong></p>
          <p>
            This is normal in caution markets — PTS is conservative. Try the
            <strong> All (Watch+)</strong> tab to see the full ranked list.
            Or wait for the next scan; the cron runs every weekday at 4:30 PM ET.
          </p>
        </div>
      ) : (
        <div className="tiny-grid">
          {rows.map((r) => <TinyCard key={r.symbol} c={r} />)}
        </div>
      )}
    </div>
  );
}

function TinyCard({ c }: { c: TinyCandidate }) {
  const tier = TIER_LABEL[c.tiny_tier];
  const themes = c.pioneer_themes || [];

  return (
    <article className={`tiny-card tiny-card--${tier.tone}`}>
      <header className="tiny-card__head">
        <div className="tiny-card__sym-row">
          <TickerLink ticker={c.symbol} fromLabel="tiny" className="tiny-card__sym" showWatchlist={false} />
          <WatchlistButton ticker={c.symbol} />
          {c.is_pioneer && (
            <span className="tiny-card__pioneer mono" title={themes.join(' · ')}>🚀 Pioneer</span>
          )}
        </div>
        <div className="tiny-card__score-row">
          <div className="tiny-card__score">
            <span className="tiny-card__score-num">{c.tiny_score.toFixed(0)}</span>
            <span className="tiny-card__score-suffix">PTS</span>
          </div>
          <span className={`tiny-card__tier tiny-card__tier--${tier.tone}`}>
            {tier.label}
          </span>
        </div>
      </header>

      {c.name && <div className="tiny-card__name">{c.name}</div>}

      <div className="tiny-card__priceline mono">
        {c.last_close != null && <span>${c.last_close.toFixed(2)}</span>}
        {c.day_change_pct != null && (
          <span className={(c.day_change_pct >= 0) ? 'is-up' : 'is-down'}>
            {fmtPct(c.day_change_pct)}
          </span>
        )}
        {c.rs_rank != null && <span className="mono">RS {c.rs_rank}</span>}
        {c.adr_pct != null && <span className="mono">ADR {c.adr_pct.toFixed(1)}%</span>}
      </div>

      {/* Component breakdown — small horizontal bars */}
      <div className="tiny-card__components">
        {(['canslim', 'tiny_titans', 'pioneer', 'catalyst', 'frenzy', 'insider', 'float'] as TinyComponent[]).map((k) => {
          const v = c.tiny_components[k] ?? 0;
          const max = COMPONENT_MAX[k];
          const pct = max > 0 ? (v / max) * 100 : 0;
          return (
            <div key={k} className={`tiny-comp ${v > 0 ? 'is-on' : ''}`}
                 title={`${COMPONENT_LABEL[k]}: ${v} / ${max}`}>
              <div className="tiny-comp__label">{COMPONENT_LABEL[k]}</div>
              <div className="tiny-comp__bar">
                <div className="tiny-comp__fill" style={{ width: `${pct}%` }} />
              </div>
              <div className="tiny-comp__num mono">{v}</div>
            </div>
          );
        })}
      </div>

      {/* Pioneer + catalyst chips */}
      {(themes.length > 0 || c.catalyst) && (
        <div className="tiny-card__chips">
          {themes.slice(0, 2).map((t, i) => (
            <span key={i} className="tiny-chip tiny-chip--theme">{t}</span>
          ))}
          {c.catalyst?.kind && (
            <span className="tiny-chip tiny-chip--catalyst">
              {c.catalyst.kind}
              {c.catalyst.days_to_event != null && ` · ${c.catalyst.days_to_event}d`}
            </span>
          )}
          {c.entry_setup?.type && (
            <span className="tiny-chip tiny-chip--setup">{c.entry_setup.type}</span>
          )}
        </div>
      )}

      {c.tiny_narrative && (
        <p className="tiny-card__narrative">{c.tiny_narrative}</p>
      )}
    </article>
  );
}
