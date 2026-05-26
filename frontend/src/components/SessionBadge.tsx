/**
 * SessionBadge — small StockTwits-style pill labelling the trading
 * session a quoted price is from. Four states: PRE-MARKET (blue),
 * LIVE (green), AFTER-HOURS (orange), CLOSED (grey).
 *
 * Always renders display-only. Drives no logic — purely visual.
 */
import type { MarketSession } from '../lib/marketSession';

const STYLES: Record<MarketSession, { bg: string; color: string; label: string }> = {
  pre:    { bg: 'rgba(59,130,246,0.18)',  color: '#60a5fa', label: 'PRE-MARKET' },
  live:   { bg: 'rgba(34,197,94,0.18)',   color: '#22c55e', label: 'LIVE'       },
  after:  { bg: 'rgba(249,115,22,0.18)',  color: '#fb923c', label: 'AFTER-HRS'  },
  closed: { bg: 'rgba(154,154,170,0.15)', color: '#9aa8c8', label: 'CLOSED'     },
};

export function SessionBadge({ session }: { session: MarketSession }) {
  const s = STYLES[session];
  return (
    <span
      style={{
        display:        'inline-block',
        padding:        '0.05rem 0.4rem',
        fontSize:       '0.62rem',
        letterSpacing:  '0.08em',
        fontWeight:     700,
        textTransform:  'uppercase',
        background:     s.bg,
        color:          s.color,
        borderRadius:   3,
        verticalAlign:  'middle',
      }}
      aria-label={`Market session: ${s.label}`}
    >
      ● {s.label}
    </span>
  );
}
