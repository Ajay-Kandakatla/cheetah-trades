/* ReactionMap — "pre-decide the direction" cheat sheet for the regime check.
 *
 * Given a data SURPRISE (hot jobs, hot CPI/PCE, hawkish Fed, cool data), how do
 * Yields / US Dollar / Gold / S&P 500 react — in the CURRENT regime. The arrows
 * are regime-dependent (tightening vs easing), so a toggle flips the whole table.
 * Static reference (the ZONETRADER618 "Reaction Map" slide). Not advice.
 */
import { useState } from 'react';

const ASSETS = ['Yields', 'US Dollar', 'Gold', 'S&P 500'] as const;
type Reaction = { yields: string; usd: string; gold: string; spx: string };

// Tightening regime (now): hot data → yields/$ up, gold/stocks down.
const TIGHTENING: { label: string; r: Reaction }[] = [
  { label: 'Jobs hotter',           r: { yields: '▲',  usd: '▲', gold: '▼', spx: '▼'  } },
  { label: 'CPI / PCE hotter',      r: { yields: '▲▲', usd: '▲', gold: '▼', spx: '▼▼' } },
  { label: 'Hawkish Fed / dots up', r: { yields: '▲',  usd: '▲', gold: '▼', spx: '▼'  } },
  { label: 'Data cooler / misses',  r: { yields: '▼',  usd: '▼', gold: '▲', spx: '▲'  } },
];

// Swap ▲↔▼ (incl. doubles) to flip the table for an easing regime.
function flip(a: string): string {
  return a.replace(/▲/g, '★').replace(/▼/g, '▲').replace(/★/g, '▼');
}

function Arrow({ a }: { a: string }) {
  if (!a) return <span className="rxn__arr">—</span>;
  const up = a.includes('▲');
  return <span className={`rxn__arr ${up ? 'rxn__arr--up' : 'rxn__arr--dn'}`}>{a}</span>;
}

export function ReactionMap() {
  const [easing, setEasing] = useState(false);
  const rows = easing
    ? TIGHTENING.map((x) => ({
        label: x.label,
        r: { yields: flip(x.r.yields), usd: flip(x.r.usd), gold: flip(x.r.gold), spx: flip(x.r.spx) },
      }))
    : TIGHTENING;

  return (
    <section className="rxn">
      <div className="eyebrow">Reaction map · {easing ? 'easing' : 'tightening'} regime</div>
      <p className="rxn__lede">
        Pre-decide the direction of the move so a surprise never wrong-foots you on the sign.
      </p>

      <div className="rxn__toggle">
        <button type="button" className={`rxn__tg${!easing ? ' is-active' : ''}`} onClick={() => setEasing(false)}>
          Tightening (now)
        </button>
        <button type="button" className={`rxn__tg${easing ? ' is-active' : ''}`} onClick={() => setEasing(true)}>
          Easing
        </button>
      </div>

      <div className="rxn__wrap">
        <table className="rxn__table">
          <thead>
            <tr>
              <th>If… (surprise)</th>
              {ASSETS.map((a) => <th key={a} className="rxn__num">{a}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <td className="rxn__if">{row.label}</td>
                {(['yields', 'usd', 'gold', 'spx'] as const).map((k) => (
                  <td key={k} className="rxn__num"><Arrow a={row.r[k]} /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="rxn__note">
        <strong>Flip the whole table</strong> the day the regime flips{' '}
        {easing ? 'back to tightening' : 'back to easing'} — then{' '}
        {easing
          ? 'hot data becomes bad for stocks again and cool data good'
          : 'cooler data becomes bad for stocks and hot data becomes good'}.
        The arrows are regime-dependent, not laws of nature.
      </p>
    </section>
  );
}
