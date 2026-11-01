/* LukScreens — one of 🥇 Luk's three scans (☀️ Premarket / 🏆 Leader / ⚡ Potent; 2026-11-01, luk spec §3.6 / §3.10).
 *
 * A table in the SERVED order: the served title and sorted-by line, the served heads, one row per served row (its
 * served cells, then every criterion ✓ / ✗ / · with its served value and need — a "cap unknown — not filtered" row is
 * KEPT, its criterion unjudged), then the served "not screened yet" and "his considerations — not applied" lines and
 * the served honesty line. The FE sorts nothing, filters nothing and types no word or number. */
import { Link } from 'react-router-dom';
import { lukMark, lukScreenCols, lukText, type LukScreen } from '../lib/luk';

function cell(v: unknown): string {
  if (typeof v === 'string') return v;
  if (typeof v === 'number' && Number.isFinite(v)) return String(v);
  return '';
}

export function LukScreens({ screen }: { screen?: LukScreen | null }) {
  if (!screen) return null;
  const cols = lukScreenCols(screen);
  const rows = screen.rows ?? [];
  return (
    <div className="luk-screen" data-testid={`luk-screen-${screen.key}`}>
      {lukText(screen.title) ? <h3 className="luk-h" data-testid="luk-screen-title">{screen.title}</h3> : null}
      {lukText(screen.sorted_by_text) ? <p className="luk-line luk-muted" data-testid="luk-screen-sorted">{screen.sorted_by_text}</p> : null}
      {rows.length ? (
        <div className="luk-table-wrap">
          <table className="luk-table" data-testid="luk-screen-table">
            {cols.length ? (
              <thead>
                <tr>{cols.map((c) => <th key={c.key} scope="col">{c.label}</th>)}<th scope="col" aria-label="criteria" /></tr>
              </thead>
            ) : null}
            <tbody>
              {rows.map((r) => (
                <tr key={r.symbol} data-testid={`luk-screen-row-${r.symbol}`}>
                  {cols.map((c) => (
                    <td key={c.key} data-col={c.key}>
                      {c.key === 'symbol' && lukText(r.href)
                        ? <Link to={r.href!} data-testid={`luk-screen-link-${r.symbol}`}>{r.symbol}</Link>
                        : cell(r[c.key])}
                    </td>
                  ))}
                  <td className="luk-crit-cell">
                    {r.criteria?.length ? (
                      <ul className="luk-criteria luk-criteria-inline" data-testid={`luk-screen-crit-${r.symbol}`}>
                        {r.criteria.map((c) => (
                          <li key={c.key} className={c.ok === true ? 'luk-ok' : c.ok === false ? 'luk-miss' : 'luk-unjudged'}
                              data-testid={`luk-screen-crit-${r.symbol}-${c.key}`}>
                            {lukMark(c.ok)} {c.label}
                            {lukText(c.value) ? <> — {c.value}</> : null}
                            {lukText(c.need) ? <span className="luk-muted"> ({c.need})</span> : null}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {lukText(screen.not_screened_text) ? <p className="luk-line luk-muted" data-testid="luk-not-screened">{screen.not_screened_text}</p> : null}
      {lukText(screen.considerations_text) ? <p className="luk-line" data-testid="luk-considerations">{screen.considerations_text}</p> : null}
      {lukText(screen.honesty) ? <p className="luk-line luk-muted" data-testid="luk-screen-honesty">{screen.honesty}</p> : null}
    </div>
  );
}

export default LukScreens;
