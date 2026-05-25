/* SepaSignalChips — shared row of clickable ranking-component chips.
 *
 *  Renders all the SEPA scoring signals as clickable chips. Tap any
 *  chip → opens SignalDrillModal with that component's drill view.
 *
 *  Built 2026-05-22 for the SEPA detail page (/sepa/{symbol}) — the
 *  user landed on RYOJ via search and wanted the same chip experience
 *  that exists on the list cards.
 *
 *  Used by:
 *    - frontend/src/pages/SepaCandidate.tsx — detail page, full strip
 *      right under the score bar
 *    - (future) frontend/src/components/SepaCandidateCard.tsx — list
 *      card, when refactored to use this instead of inline chips
 *
 *  Chips rendered (in display order, conditional on data availability):
 *    📊 Score breakdown · 📈 Trend (8/N) · ⚡ RS rank · 🪜 Stage
 *    🎯 VCP / 🚀 Power Play · ⚠ Late base · 〰 ADR
 *    💪/📈/📉 Accumulation · 🪙 Pocket pivot · 🚀 Hi-vol breakout
 *    💸 Money outflow · ⚠️ N dist days
 *
 *  All chips share one modal-state slot — only one open at a time.
 */
import { lazy, Suspense, useState } from 'react';
import type { SepaCandidate } from '../hooks/useSepa';
import type { SignalKind } from './SignalDrillModal';

const SignalDrillModal = lazy(() =>
  import('./SignalDrillModal').then((m) => ({ default: m.SignalDrillModal })),
);

/** Common chip button styles — base + tone variants. Inline rather
 *  than CSS-class-based so this component drops into any page without
 *  needing the host's stylesheet. */
const CHIP_BASE: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  padding: '0.3rem 0.6rem',
  borderRadius: 14,
  fontSize: '0.78rem',
  fontWeight: 600,
  fontFamily: 'inherit',
  cursor: 'pointer',
  whiteSpace: 'nowrap',
  border: '1px solid',
  background: 'transparent',
};
const TONE: Record<'good' | 'bad' | 'neutral' | 'gold', { bg: string; border: string; color: string }> = {
  good:    { bg: 'rgba(16,185,129,0.10)', border: 'rgba(16,185,129,0.35)', color: '#10b981' },
  bad:     { bg: 'rgba(239,68,68,0.10)',  border: 'rgba(239,68,68,0.35)',  color: '#ef4444' },
  neutral: { bg: 'rgba(255,255,255,0.04)', border: 'rgba(255,255,255,0.12)', color: '#cfcfd4' },
  gold:    { bg: 'rgba(212,175,55,0.10)', border: 'rgba(212,175,55,0.35)', color: '#d4af37' },
};

function Chip({ tone, onClick, title, children }: {
  tone: keyof typeof TONE;
  onClick: () => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      title={title}
      style={{
        ...CHIP_BASE,
        background:   TONE[tone].bg,
        borderColor:  TONE[tone].border,
        color:        TONE[tone].color,
      }}
    >
      {children}
      <span style={{ fontSize: '0.72em', opacity: 0.7, marginLeft: 2 }}>↗</span>
    </button>
  );
}


/** Which chips to render.
 *
 *  - "all"         — every chip (default — used by SepaCandidate detail page)
 *  - "volume_only" — just the volume-driven signals + dist-day warning.
 *                    Used by SepaCandidateCard, which already renders score /
 *                    trend / RS / stage / setup / late base / ADR in its own
 *                    dedicated UI elements (score bar, trend dots, RS bar,
 *                    setup pill, stage badge). Without this filter the card
 *                    would double-render those chips. */
export type SignalChipsSubset = 'all' | 'volume_only';

export function SepaSignalChips({ row, subset = 'all' }: { row: SepaCandidate; subset?: SignalChipsSubset }) {
  const [openSignal, setOpenSignal] = useState<SignalKind | null>(null);
  const showAll = subset === 'all';

  // Build the modal's data snapshot ONCE per render — same shape as
  // SepaCandidateCard uses. Cast 'as any' on a few fields where the
  // candidate type is missing the v2 volume keys (recent_21d_high,
  // pocket_pivot_detail, etc.); they're optional + the modal degrades
  // when null.
  const v = row.volume as any;
  const signalData = {
    symbol:                row.symbol,
    last_vol:              v?.last_vol ?? null,
    avg_vol_50:            v?.avg_vol_50 ?? null,
    up_down_vol_ratio:     row.volume?.up_down_vol_ratio ?? null,
    last_close:            row.last_close ?? null,
    recent_21d_high:       v?.recent_21d_high ?? null,
    accumulation_strength: row.volume?.accumulation_strength ?? null,
    pocket_pivot_detail:   v?.pocket_pivot_detail ?? null,
    cmf_20:                v?.cmf_20 ?? null,
    distribution_days_25:  row.volume?.distribution_days_25 ?? null,
    accumulation_days_25:  row.volume?.accumulation_days_25 ?? null,
    score:                 row.score ?? null,
    rating:                row.rating ?? null,
    trend_passed:          row.trend?.passed ?? null,
    trend_checks:          (row.trend as any)?.checks ?? null,
    rs_rank:               row.rs_rank ?? null,
    stage_num:             (row.stage as any)?.stage ?? null,
    stage_label:           (row.stage as any)?.label ?? null,
    fundamentals_passed:   (row.fundamentals as any)?.passed ?? null,
    adr_pct:               row.adr_pct ?? null,
    base_count_n:          (row.base_count as any)?.base_count ?? null,
    base_count_is_late:    row.base_count?.is_late_stage ?? null,
    setup_type:            row.entry_setup?.type ?? null,
    setup_pivot:           row.entry_setup?.pivot ?? null,
    setup_stop:            row.entry_setup?.stop ?? null,
    liquidity_liquid:      (row as any)?.liquidity?.liquid ?? null,
    high_vol_breakout:     row.volume?.high_vol_breakout ?? null,
    pocket_pivot:          row.volume?.pocket_pivot ?? null,
    cmf_signal:            row.volume?.cmf_signal ?? null,
  };

  const stage = (row.stage as any)?.stage;
  const lateBase = row.base_count?.is_late_stage;
  const setupType = row.entry_setup?.type;
  const accStrength = row.volume?.accumulation_strength;
  const distDays = row.volume?.distribution_days_25 ?? 0;

  return (
    <>
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 6,
        // When subset="volume_only" we're nested inside the card's
        // existing .sepa-card__flags row which already has the right
        // spacing — kill our own margin to avoid double-padding.
        margin: showAll ? '0.6rem 0 0.5rem' : 0,
        alignItems: 'center',
      }}>
        {/* Ranking-component chips — score, trend, RS, stage, setup, late
            base, ADR. Hidden when subset="volume_only" because the
            SepaCandidateCard list view already renders these via its
            dedicated score bar / trend dots / RS bar / setup pill / stage
            badge — including them here would duplicate the UI. */}
        {showAll && row.score != null && (
          <Chip
            tone="gold"
            title="Tap for score breakdown — which components contributed how much"
            onClick={() => setOpenSignal('score_breakdown')}
          >📊 Score {row.score.toFixed(0)}</Chip>
        )}

        {showAll && row.trend?.passed != null && (
          <Chip
            tone={row.trend.passed >= 7 ? 'good' : row.trend.passed >= 5 ? 'neutral' : 'bad'}
            title="Trend Template — Minervini's 8 price/MA gates. Tap for gate-by-gate breakdown."
            onClick={() => setOpenSignal('trend_template')}
          >📈 Trend {row.trend.passed}/8</Chip>
        )}

        {showAll && row.rs_rank != null && (
          <Chip
            tone={row.rs_rank >= 80 ? 'good' : row.rs_rank >= 70 ? 'neutral' : 'bad'}
            title="Relative Strength rank — IBD-style percentile. ≥70 is the Minervini gate."
            onClick={() => setOpenSignal('rs_rank')}
          >⚡ RS {row.rs_rank}</Chip>
        )}

        {showAll && stage != null && (
          <Chip
            tone={stage === 2 ? 'good' : stage > 2 ? 'bad' : 'neutral'}
            title="Weinstein stage. Tap for the 4-stage framework."
            onClick={() => setOpenSignal('stage')}
          >🪜 S{stage}</Chip>
        )}

        {showAll && setupType === 'VCP' && (
          <Chip tone="good" title="VCP base detected" onClick={() => setOpenSignal('setup_vcp')}>
            🎯 VCP
          </Chip>
        )}
        {showAll && (setupType === 'POWER_PLAY' || setupType === 'POWERPLAY') && (
          <Chip tone="good" title="Power Play setup" onClick={() => setOpenSignal('setup_power_play')}>
            🚀 Power Play
          </Chip>
        )}

        {showAll && lateBase && (
          <Chip tone="bad"
                title="Late-stage base — -8 score penalty"
                onClick={() => setOpenSignal('base_count_late')}>
            ⚠ Late base #{(row.base_count as any)?.base_count ?? '?'}
          </Chip>
        )}

        {showAll && !setupType && !lateBase && (
          <Chip tone="neutral"
                title="No VCP or Power Play base detected — 0 of 15 setup points"
                onClick={() => setOpenSignal('base_count_none')}>
            🚫 No base
          </Chip>
        )}

        {showAll && row.adr_pct != null && (
          <Chip
            tone={row.adr_pct >= 4 ? 'good' : 'neutral'}
            title="Average Daily Range — leader-grade threshold is ≥4%"
            onClick={() => setOpenSignal('adr')}
          >〰 ADR {row.adr_pct}%</Chip>
        )}

        {/* Accumulation strength (v2) */}
        {accStrength === 'strong' && (
          <Chip tone="good" title="Strong accumulation — all 3 confirmations align"
                onClick={() => setOpenSignal('accum_strong')}>💪 Strong accum</Chip>
        )}
        {accStrength === 'accumulating' && (
          <Chip tone="good" title="Accumulating — up/down ratio ≥ 1.3"
                onClick={() => setOpenSignal('accum_accumulating')}>📈 Accumulating</Chip>
        )}
        {accStrength === 'distributing' && (
          <Chip tone="bad" title="Distributing — institutional selling"
                onClick={() => setOpenSignal('accum_distributing')}>📉 Distributing</Chip>
        )}
        {/* Legacy fallback chip when v2 field is missing but the binary
            accumulation flag is true (older cached scans). */}
        {!accStrength && row.volume?.accumulation && (
          <Chip tone="good" title="Vol accumulation (legacy binary signal)"
                onClick={() => setOpenSignal('accum_accumulating')}>📈 Vol accumulation</Chip>
        )}

        {/* Pocket pivot */}
        {row.volume?.pocket_pivot && (
          <Chip tone="good" title="Pocket pivot — pre-breakout institutional footprint"
                onClick={() => setOpenSignal('pocket_pivot')}>🪙 Pocket pivot</Chip>
        )}

        {/* Hi-vol breakout */}
        {row.volume?.high_vol_breakout && (
          <Chip tone="good" title="Hi-volume breakout — Minervini pivot-buy signal"
                onClick={() => setOpenSignal('hi_vol_breakout')}>🚀 Hi-vol breakout</Chip>
        )}

        {/* CMF outflow */}
        {row.volume?.cmf_signal === 'outflow' && (
          <Chip tone="bad" title="Chaikin Money Flow ≤ -0.10 — money flowing OUT"
                onClick={() => setOpenSignal('cmf_outflow')}>💸 Money outflow</Chip>
        )}

        {/* Distribution day warning (only when ≥3 but not yet flagged as
            'distributing' by the strength classifier) */}
        {distDays >= 3 && accStrength !== 'distributing' && (
          <Chip tone="neutral" title={`${distDays} distribution days — watch closely`}
                onClick={() => setOpenSignal('dist_days_warning')}>⚠️ {distDays} dist days</Chip>
        )}
      </div>

      {openSignal && (
        <Suspense fallback={null}>
          <SignalDrillModal
            kind={openSignal}
            data={signalData}
            onClose={() => setOpenSignal(null)}
          />
        </Suspense>
      )}
    </>
  );
}
