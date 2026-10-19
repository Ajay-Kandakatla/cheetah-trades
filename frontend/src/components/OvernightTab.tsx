/* Chart Maps ▸ Overnight — two subs (BUILD_SPEC16 D1 / §3.7, 2026-10-19).
 *
 *   🌙 Overnight session (default, HIS CALL #8) — the Blue Ocean session read
 *      from Alpaca's overnight feed (OvernightSessionBoard).
 *   Gappers — the unchanged pre-market / after-hours movers board
 *      (OvernightGappers, the Day Trading page's component).
 *
 * The sub rides its OWN param `on_sub` (replace), so a reload or a shared link
 * opens the same sub; the Gappers sub never fetches /overnight/session. */
import { useSearchParams } from 'react-router-dom';
import { OvernightGappers } from './OvernightGappers';
import OvernightSessionBoard from './OvernightSessionBoard';
import { ON_SUBS, ON_SUB_LABELS, ON_SUB_PARAM, parseOnSub, type OnSub } from '../lib/overnightSession';
import '../styles/overnight.css';

export default function OvernightTab({ onPick }: { onPick: (symbol: string) => void }) {
  const [params, setParams] = useSearchParams();
  const sub = parseOnSub(params.get(ON_SUB_PARAM));

  const pick = (s: OnSub) => {
    const next = new URLSearchParams(params);
    next.set(ON_SUB_PARAM, s);
    setParams(next, { replace: true });
  };

  return (
    <div className="ons-tab">
      <div className="cat-tabs ons-subs" role="tablist" aria-label="Overnight boards">
        {ON_SUBS.map((s) => (
          <button key={s} type="button" role="tab" aria-selected={s === sub}
                  data-testid={`ons-sub-${s}`}
                  className={`cat-tab${s === sub ? ' is-active' : ''}`}
                  onClick={() => pick(s)}>
            {ON_SUB_LABELS[s]}
          </button>
        ))}
      </div>
      {sub === 'session'
        ? <OvernightSessionBoard onPick={onPick} />
        : <OvernightGappers profile="aggressive" onPick={onPick} />}
    </div>
  );
}

export { OvernightTab };
