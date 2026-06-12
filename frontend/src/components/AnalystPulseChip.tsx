/* AnalystPulseChip — compact "📊 Est …" chip built from one
 * /sepa/analyst-map entry. Surfaces estimate-revision direction (TLSW
 * pp.124-125), with mean-price-target context appended, and flips to an
 * amber p.89 trap warning when upgrades/target raises land on a name
 * that is NOT in a confirmed uptrend ("Brokerage House Opinions": such
 * upgrades are often valuation calls and "turn out to be good short
 * candidates").
 *
 * Verdicts (backend decides — FE only renders):
 *   revisions_up_big — current-FY estimates revised up ≥5% in 30d (p.124)
 *   trending_higher  — estimates trending higher from 30 days earlier (p.125)
 *   neutral          — data exists but no signal (renders dim; renders
 *                      NOTHING when there's no analyst data at all)
 *   red_flag         — large downward revisions (p.125 "definitely a red flag")
 *   p89_trap         — bullish analyst action on a broken / non-Stage-2 name
 *
 * Click opens the AnalystPulseModal via onOpenDrill. The chip sits inside
 * <Link>-wrapped cards on some surfaces, so the handler does BOTH
 * stopPropagation AND preventDefault (house lesson — one without the
 * other still navigates).
 *
 * Price targets are analyst DATA, not Minervini methodology — Ch.4
 * "Value Comes at a Price" (TLSW p.41/p.44) framing lives in the modal.
 * Nothing here feeds the composite SEPA score.
 */
import { REVISION_BIG_PCT, type AnalystMapEntry } from '../hooks/useAnalystMap';

const GREEN = '#10b981';
const RED   = '#ef4444';
const AMBER = '#f59e0b';
const MUTED = '#8a93a6';

function fmtRev(x: number): string {
  const v = Math.abs(x);
  return v >= 10 ? v.toFixed(0) : v.toFixed(1);
}

export function AnalystPulseChip({ symbol, entry, onOpenDrill }: {
  symbol: string;
  entry: AnalystMapEntry | undefined;
  /** Opens the AnalystPulseModal for this symbol. */
  onOpenDrill?: () => void;
}) {
  if (!entry) return null;

  const rev = entry.fy_rev_30d;
  let color = MUTED;
  let weight = 600;
  let label = '';
  let title = '';

  switch (entry.verdict) {
    case 'revisions_up_big':
      color = GREEN;
      weight = 700;
      label = `📊 Est ↑${rev != null ? `${fmtRev(rev)}%` : ''}`;
      title =
        `${symbol}: current-FY estimates revised up ≥${REVISION_BIG_PCT}% in the last 30 days — ` +
        `"when estimates are revised upward by 5 percent or more, stocks tend to show ` +
        `better-than-average performance" (TLSW p.124).\n\n` +
        `Note: the book doesn't specify the lookback window for the 5% study — we use 30d, ` +
        `with 90d shown as context in the drill. Click for targets, revisions, and analyst actions.`;
      break;
    case 'trending_higher': {
      color = GREEN;
      weight = 600;
      const both = entry.trending_higher === 'both';
      label = `📊 Est ↗${rev != null && rev > 0 ? ` +${fmtRev(rev)}%` : ''}`;
      title =
        `${symbol}: "I like to see the current fiscal year or the next year's estimates ` +
        `trending higher from 30 days earlier; if both are trending higher, that is even better" ` +
        `(TLSW p.125).\n\n` +
        (both
          ? `Both the current-FY AND next-FY estimates are trending higher — the "even better" case.`
          : `One fiscal-year estimate is trending higher from 30 days earlier.`) +
        `\n\nClick for targets, revisions, and analyst actions.`;
      break;
    }
    case 'red_flag':
      color = RED;
      weight = 700;
      label = `📊 Est ↓${rev != null ? `${fmtRev(rev)}%` : ''}`;
      title =
        `${symbol}: large downward estimate revisions in the last 30 days — ` +
        `"large downward estimate revisions are definitely a red flag" (TLSW p.125). ` +
        `Downward revisions of 5% or more sit in the lower-than-average performance cohort (p.124).\n\n` +
        `Click for detail.`;
      break;
    case 'p89_trap':
      color = AMBER;
      weight = 700;
      label = '⚠ PT↑ on broken stock';
      title =
        `${symbol}: recent upgrades / price-target raises on a name that is NOT in a confirmed ` +
        `uptrend (not a Stage 2 scan qualifier). Upgrades on broken stocks are often ` +
        `valuation-based calls after the break and frequently "turn out to be good short ` +
        `candidates" (TLSW p.89). Caution signal, NOT bullish.\n\nClick for detail.`;
      break;
    case 'neutral':
    default:
      // No-data rows render nothing; only show the dim chip when there's
      // something behind it (actions or revision/target data).
      if (!(entry.n_actions > 0 || rev != null || entry.mean_target != null)) return null;
      color = MUTED;
      weight = 600;
      label = '📊 Est —';
      title =
        `${symbol}: no actionable analyst signal — either no meaningful estimate revisions in ` +
        `the last 30 days, or the name lacks a confirmed uptrend so bullish reads are gated ` +
        `(TLSW p.86 "tune out the analyst"). ` +
        `Click for price targets, revision detail, and recent analyst actions (pp.124-125 framing).`;
      break;
  }

  // Mean-target context — implied upside is DATA + Ch.4 context (p.41/44),
  // not a book formula. Green/red by sign only.
  const up = entry.implied_upside_pct;
  const showPT = entry.mean_target != null && up != null && isFinite(up);

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    onOpenDrill?.();
  };
  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.stopPropagation();
      e.preventDefault();
      onOpenDrill?.();
    }
  };

  return (
    <span
      role="button"
      tabIndex={0}
      title={title}
      onClick={handleClick}
      onKeyDown={handleKey}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        fontSize: '0.7rem', fontWeight: weight, lineHeight: 1.4,
        padding: '2px 8px', borderRadius: 6, whiteSpace: 'nowrap',
        color, background: `${color}1a`, border: `1px solid ${color}66`,
        cursor: onOpenDrill ? 'pointer' : 'default',
      }}
    >
      {label}
      {showPT && (
        <span style={{ color: up! >= 0 ? GREEN : RED, fontWeight: 600 }}>
          · PT {up! >= 0 ? '+' : ''}{up!.toFixed(0)}%
        </span>
      )}
    </span>
  );
}
