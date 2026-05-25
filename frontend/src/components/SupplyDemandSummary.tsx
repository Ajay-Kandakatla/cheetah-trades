import { useNavigate } from 'react-router-dom';
import { useSectors } from '../hooks/useSupplyDemand';

type Props = { compact?: boolean };

/**
 * SupplyDemandSummary — compact strip showing the most-constrained and
 * most-oversupplied sectors. Used on Morning + Overnight pages as a
 * "what's the gap right now" quick read.
 */
export function SupplyDemandSummary(_props: Props = {}) {
  const nav = useNavigate();
  const { data, loading } = useSectors();

  if (loading || !data) {
    return (
      <div className="sd-summary sd-summary--loading">
        Classifying global supply / demand…
      </div>
    );
  }

  const sectors = data.sectors;
  const constrained = sectors.filter((s) => s.classification.state === 'constrained').slice(0, 3);
  const oversupplied = sectors.filter((s) => s.classification.state === 'oversupplied').slice(0, 2);

  return (
    <div className="sd-summary">
      <header className="sd-summary__head">
        <h2 className="sd-summary__h">Global supply / demand snapshot</h2>
        <button type="button" className="sd-summary__more" onClick={() => nav('/supply-demand')}>
          full atlas →
        </button>
      </header>

      <div className="sd-summary__cols">
        {constrained.length > 0 && (
          <div className="sd-summary__col">
            <div className="sd-summary__col-label sd-summary__col-label--good">SUPPLY-CONSTRAINED</div>
            <ul className="sd-summary__list">
              {constrained.map((s) => (
                <li key={s.sector_id} onClick={() => nav('/supply-demand')}>
                  <strong>{s.label}</strong>
                  <span className="mono sd-summary__gap">{s.classification.gap_index}/100</span>
                  <span className="sd-summary__narrative">{s.classification.narrative.slice(0, 120)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {oversupplied.length > 0 && (
          <div className="sd-summary__col">
            <div className="sd-summary__col-label sd-summary__col-label--bad">OVERSUPPLIED</div>
            <ul className="sd-summary__list">
              {oversupplied.map((s) => (
                <li key={s.sector_id} onClick={() => nav('/supply-demand')}>
                  <strong>{s.label}</strong>
                  <span className="mono sd-summary__gap">{s.classification.gap_index}/100</span>
                  <span className="sd-summary__narrative">{s.classification.narrative.slice(0, 120)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
