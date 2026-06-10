/* PatternChips — the compact pattern verdict for one symbol, rendered inside
 * Portfolio cards / Leaderboard rows / Top Picks. Green = confirmed (closed
 * above its line), amber = forming (a shape, not a signal), candle icon =
 * formation read only. Clicking goes to /patterns (the chips live inside
 * <Link> rows, so the click stops propagation). Renders nothing when the
 * symbol wasn't in the last verdict scan. */
import { useNavigate } from 'react-router-dom';
import type { PatternVerdict } from '../hooks/usePatternVerdicts';

const SHORT: Record<string, string> = {
  double_bottom: 'W', triple_bottom: '3B',
  inverse_head_shoulders: 'iH&S', cup_with_handle: 'Cup',
};
const CANDLE_ICON: Record<string, string> = {
  hammer: '🔨', shooting_star: '☄️', doji: '➖',
  bullish_engulfing: '🟢', bearish_engulfing: '🔴', morning_star: '🌅',
};
const READ_COLOR: Record<string, string> = {
  bullish_reversal_setup: '#10b981', bearish_warning: '#ef4444', indecision: '#94a3b8',
};

export function PatternChips({ v, max = 2 }: { v?: PatternVerdict | null; max?: number }) {
  const navigate = useNavigate();
  if (!v) return null;

  const go = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    navigate('/patterns');
  };

  const chips: React.ReactNode[] = [];
  for (const m of (v.matches || []).slice(0, max)) {
    const conf = m.status === 'confirmed';
    const col = conf ? '#10b981' : '#f59e0b';
    chips.push(
      <button key={`m-${m.pattern}`} onClick={go}
              title={`${m.pattern.replace(/_/g, ' ')} — ${conf
                ? `CONFIRMED ${m.confirmed_date || ''} · line ${m.neckline} · target ${m.target} (measure rule) · stop ${m.stop}`
                : `forming, ${m.to_confirm_pct}% to the line ${m.neckline} — a shape, not a signal until it closes above`}\nClick for the Patterns page`}
              style={{ fontSize: '0.64rem', fontWeight: 700, color: col, cursor: 'pointer',
                       border: `1px solid ${col}55`, background: `${col}14`,
                       borderRadius: 5, padding: '0 6px', lineHeight: '1.25rem' }}>
        📐 {SHORT[m.pattern] || m.pattern} {conf ? '✓' : '…'}
      </button>,
    );
  }
  if (!chips.length) {
    const f = v.candles?.formations?.[0];
    if (f) {
      const col = READ_COLOR[f.read] || '#94a3b8';
      chips.push(
        <button key={`c-${f.name}`} onClick={go}
                title={`${f.name.replace(/_/g, ' ')} (${f.date}) — ${f.note}\n${f.stat || ''}\nClick for the Patterns page`}
                style={{ fontSize: '0.64rem', color: col, cursor: 'pointer',
                         border: `1px solid ${col}44`, background: 'transparent',
                         borderRadius: 5, padding: '0 6px', lineHeight: '1.25rem' }}>
          {CANDLE_ICON[f.name] || '🕯'} {f.name.replace(/_/g, ' ')}
        </button>,
      );
    }
  }
  if (!chips.length) return null;
  return <span style={{ display: 'inline-flex', gap: 4, verticalAlign: 'middle' }}>{chips}</span>;
}
