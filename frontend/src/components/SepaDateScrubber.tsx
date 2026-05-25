import { useMemo } from 'react';
import { useSepaRuns } from '../hooks/useSepaHistory';

/* ==========================================================================
   SepaDateScrubber — date picker pinned above the SEPA candidate list.
   Lets you load a historical scan as if it were today's. The list itself
   re-renders against the chosen date's candidate snapshot.
   ========================================================================== */

type Props = {
  /** Currently-selected date_et, or null = live (today). */
  value: string | null;
  /** Called with the new date_et, or null to return to live data. */
  onChange: (date: string | null) => void;
};

export function SepaDateScrubber({ value, onChange }: Props) {
  const { runs, loading } = useSepaRuns(60);

  // Most recent run per Eastern date → the historical scrub options
  const dateOptions = useMemo(() => {
    const seen = new Set<string>();
    const out: { date: string; count: number }[] = [];
    for (const r of runs) {
      if (!r.date_et || seen.has(r.date_et)) continue;
      seen.add(r.date_et);
      out.push({ date: r.date_et, count: r.candidate_count ?? 0 });
    }
    return out;
  }, [runs]);

  if (loading) return null;

  return (
    <div className="sepa-datescrub">
      <span className="eyebrow">Viewing</span>
      <button
        className={`sepa-chip ${value === null ? 'is-active' : ''}`}
        onClick={() => onChange(null)}
        title="Show today's live scan"
      >
        Live
      </button>
      <select
        className="sepa-datescrub__select"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value || null)}
        title="Scrub the candidate list back to a previous scan date"
      >
        <option value="">— pick a date —</option>
        {dateOptions.map((d) => (
          <option key={d.date} value={d.date}>
            {d.date} ({d.count} candidates)
          </option>
        ))}
      </select>
      {value && (
        <span className="sepa-datescrub__viewing mono">
          Historical · {value}
        </span>
      )}
    </div>
  );
}
