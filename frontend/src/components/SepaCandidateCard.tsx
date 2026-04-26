import { useState } from 'react';
import type { SepaCandidate } from '../hooks/useSepa';
import { SepaScoreBar } from './SepaScoreBar';
import { SepaTrendDots } from './SepaTrendDots';
import { PriceAlertModal } from './PriceAlertModal';

type Props = { row: SepaCandidate; onSelect: () => void };

/**
 * SepaCandidateCard — replaces the dense table row with a glance-readable card.
 * Shows: rating + score, trend dots, RS, setup pill, pivot/stop with risk %,
 * stage badge, volume/late-base flags.
 */
export function SepaCandidateCard({ row, onSelect }: Props) {
  const [alertOpen, setAlertOpen] = useState(false);
  const setup = row.entry_setup;
  const riskPct = setup ? Math.abs((setup.pivot - setup.stop) / setup.pivot) * 100 : null;
  const stage = row.stage?.stage;
  const lateBase = row.base_count?.is_late_stage;
  const accumulation = row.volume?.accumulation;
  const breakout = row.volume?.high_vol_breakout;

  return (
    <article
      className={`sepa-card ${row.is_candidate ? 'is-candidate' : ''}`}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect()}
    >
      <header className="sepa-card__head">
        <div className="sepa-card__sym">
          <strong>{row.symbol}</strong>
          {stage != null && (
            <span className={`sepa-stage sepa-stage--${stage}`}>S{stage}</span>
          )}
          {lateBase && <span className="sepa-tag sepa-tag--warn" title="Late-stage base — exhaustion risk">late</span>}
        </div>
        <div className="sepa-card__head-right">
          <button
            type="button"
            className="sepa-card__bell"
            title="Set alert"
            onClick={(e) => { e.stopPropagation(); setAlertOpen(true); }}
          >
            🔔
          </button>
          <SepaScoreBar score={row.score} rating={row.rating} size="sm" />
        </div>
      </header>

      {alertOpen && (
        <div onClick={(e) => e.stopPropagation()}>
          <PriceAlertModal
            symbol={row.symbol}
            currentPrice={setup?.pivot ?? null}
            onClose={() => setAlertOpen(false)}
          />
        </div>
      )}

      <div className="sepa-card__body">
        <div className="sepa-card__row">
          <span className="sepa-card__label">Trend</span>
          <SepaTrendDots checks={row.trend.checks} passed={row.trend.passed} />
        </div>

        <div className="sepa-card__row">
          <span className="sepa-card__label">RS</span>
          <div className="sepa-rs-bar">
            <div
              className="sepa-rs-bar__fill"
              style={{ width: `${row.rs_rank ?? 0}%` }}
              data-strong={row.rs_rank != null && row.rs_rank >= 80 ? 'true' : 'false'}
            />
            <span className="sepa-rs-bar__num mono">{row.rs_rank ?? '—'}</span>
          </div>
        </div>

        {setup && riskPct != null && (
          <div className="sepa-card__row sepa-card__setup">
            <span className={`sepa-pill sepa-pill--${setup.type.toLowerCase()}`}>{setup.type}</span>
            <span className="mono">
              ${setup.pivot} → stop ${setup.stop}{' '}
              <span className={`sepa-risk ${riskPct > 10 ? 'sepa-risk--bad' : riskPct > 7 ? 'sepa-risk--warn' : 'sepa-risk--ok'}`}>
                ({riskPct.toFixed(1)}%)
              </span>
            </span>
          </div>
        )}

        <div className="sepa-card__flags">
          {accumulation && <span className="sepa-flag sepa-flag--good">↑ accumulation</span>}
          {breakout && <span className="sepa-flag sepa-flag--good">🚀 hi-vol breakout</span>}
          {row.adr_pct != null && (
            <span className={`sepa-flag ${row.adr_pct >= 4 ? 'sepa-flag--good' : 'sepa-flag--neutral'}`}>
              ADR {row.adr_pct}%
            </span>
          )}
          {row.vcp?.has_base && row.vcp?.pivot_quality_ok && (
            <span className="sepa-flag sepa-flag--good">✓ pivot quality</span>
          )}
          {row.fundamentals && row.fundamentals.passed > 0 && (
            <span className="sepa-flag sepa-flag--good">CANSLIM {row.fundamentals.passed}/3</span>
          )}
        </div>
      </div>
    </article>
  );
}
