/* SetupOverlayStrip — small pill row rendered ABOVE a SepaCandidateCard
 * when the user has filtered the SEPA list down by a specific setup
 * category (Cheat — Low, Bull Flag, PEG, etc.). Surfaces the precomputed
 * trigger / stop / target / R:R so the user doesn't have to click into
 * /setups for the actionable numbers.
 *
 * Colors mirror the /setups page row:
 *   trigger / target — green
 *   stop             — red
 *   R:R              — bold (no color; just emphasis)
 *
 * Style intent: a thin dark band that visually "attaches" to the top of
 * the card without overwhelming the existing card visuals. Same dark-on-
 * dark contrast as the Setups page rows.
 */
import type { Setup } from '../hooks/useSetupsByKind';

function fmtPrice(n: number): string {
  if (!Number.isFinite(n)) return '—';
  return n >= 100 ? n.toFixed(2) : n.toFixed(3);
}

type Props = { setup: Setup };

export function SetupOverlayStrip({ setup }: Props) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.55rem',
        flexWrap: 'wrap',
        padding: '0.4rem 0.7rem',
        background: 'rgba(0,0,0,0.55)',
        border: '1px solid rgba(212,175,55,0.32)',
        borderRadius: '8px 8px 0 0',
        borderBottom: 'none',
        fontFamily:
          'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        fontSize: '0.74rem',
        color: '#cfcfd4',
        lineHeight: 1.5,
      }}
      title="Pre-computed setup levels — same numbers shown on the /setups page"
    >
      <span aria-hidden="true">🎯</span>
      <span>
        BUY ≥{' '}
        <strong style={{ color: '#22c55e' }}>${fmtPrice(setup.trigger)}</strong>
      </span>
      <span style={{ color: '#6a6a72' }}>·</span>
      <span>
        STOP <strong style={{ color: '#ef4444' }}>${fmtPrice(setup.stop)}</strong>
      </span>
      <span style={{ color: '#6a6a72' }}>·</span>
      <span>
        TGT <strong style={{ color: '#22c55e' }}>${fmtPrice(setup.target)}</strong>
      </span>
      <span style={{ color: '#6a6a72' }}>·</span>
      <span>
        R:R <strong>{Number.isFinite(setup.rr) ? setup.rr.toFixed(2) : '—'}</strong>
      </span>
    </div>
  );
}
