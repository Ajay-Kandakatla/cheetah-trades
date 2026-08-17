/* DemandScanProgress — the live view of a Back in Demand scan.
 *
 * Ajay 2026-08-17: "I am looking at this and its hard to tell if its scanning
 * or now". Replaces a static sentence with a bar, a running ticker, a live hit
 * count and an ETA.
 *
 * Reuses the .sepa-progress CSS so this reads as the same instrument as the
 * SEPA scan panel — but it is a DIFFERENT scan (see lib/demandScanProgress.ts),
 * and it is deliberately the compact version: this one sits inside a tab, not
 * on a page of its own.
 *
 * All arithmetic lives in lib/demandScanProgress.ts. Nothing here computes.
 */
import { progressView } from '../lib/demandScanProgress';
import type { DemandScanProgress as Progress } from '../lib/demandScanProgress';

export function DemandScanProgress({ progress, universeLabel, running }: {
  progress: Progress | null | undefined;
  universeLabel?: string | null;
  /** The board's own `warming` flag. Keeps the panel on screen for the second
   *  or two before the first progress poll lands — and if that poll never
   *  lands, the page still says a scan is running instead of going silent. */
  running?: boolean;
}) {
  const v = progressView(progress, universeLabel, { running });
  if (!v.visible) return null;

  const cls = `sepa-progress${v.isDone ? ' sepa-progress--done' : ''}`
    + `${v.isError ? ' sepa-progress--error' : ''}`;

  return (
    <div className={cls} style={{ gap: '0.7rem', padding: '0.9rem 1rem' }}
         role="status" aria-live="polite">
      <div className="sepa-progress__head">
        <div className="sepa-progress__head-left">
          <span className={`sepa-progress__phase sepa-progress__phase--${v.phaseClass}`}>
            {v.phaseLabel}
          </span>
          <span className="sepa-progress__msg">{v.message}</span>
        </div>
        <div className="sepa-progress__head-right">
          {v.countLabel && <span className="mono">{v.countLabel}</span>}
          {v.etaLabel && <><span className="sepa-progress__sep">·</span><span>{v.etaLabel}</span></>}
          {!v.etaLabel && v.elapsedLabel && (
            <><span className="sepa-progress__sep">·</span><span>{v.elapsedLabel}</span></>
          )}
        </div>
      </div>

      <div className="sepa-progress__bar-wrap">
        {/* No total yet: an indeterminate shimmer rather than a confident 0%,
            which is the "stuck at zero" impression this panel exists to kill. */}
        <div className={`sepa-progress__bar${v.isDone ? ' is-done' : ''}${v.isError ? ' is-error' : ''}`}
             style={v.pct == null
               ? { width: '35%', opacity: 0.5 }
               : { width: `${v.pct}%` }} />
      </div>

      <div style={{ display: 'flex', gap: '1.2rem', alignItems: 'baseline',
                    flexWrap: 'wrap', fontSize: '0.75rem' }}>
        <span>
          <strong className="mono" style={{ fontSize: '0.95rem' }}>{v.hits}</strong>
          <span className="sepa-progress__sub"> in demand so far</span>
        </span>
        {v.symbol && (
          <span className="mono" style={{ opacity: 0.8 }}>
            now: <strong>{v.symbol}</strong>
          </span>
        )}
        {v.pct != null && (
          <span className="mono" style={{ opacity: 0.6 }}>{v.pct}%</span>
        )}
      </div>
    </div>
  );
}
