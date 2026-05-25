import { useMemo } from 'react';
import { useSoirRuns } from '../hooks/useOptionsPulse';

/* ==========================================================================
   OptionsDateScrubber — date picker pinned above the Options Pulse list.
   Mirrors SepaDateScrubber. Lets you load a historical SOIR scan as if it
   were today's, so you can validate Schaeffer signals against subsequent
   price action.
   ========================================================================== */

type Props = {
  /** Currently-selected date_iso (YYYY-MM-DD), or null = live (today). */
  value: string | null;
  /** Called with the new date_iso, or null to return to live data. */
  onChange: (date: string | null) => void;
};

export function OptionsDateScrubber({ value, onChange }: Props) {
  const { runs, loading } = useSoirRuns(60);

  const dateOptions = useMemo(() => {
    const seen = new Set<string>();
    const out: { date: string; count: number }[] = [];
    for (const r of runs) {
      if (!r.date || seen.has(r.date)) continue;
      seen.add(r.date);
      out.push({ date: r.date, count: r.n_symbols ?? 0 });
    }
    return out;
  }, [runs]);

  if (loading) return null;
  if (dateOptions.length === 0) {
    // No history yet — first cron hasn't run. Show a subtle hint instead
    // of nothing so the user knows the feature exists once history accrues.
    return (
      <div className="sepa-datescrub">
        <span className="eyebrow">Viewing</span>
        <span className="sepa-datescrub__viewing mono" style={{ opacity: 0.65 }}>
          Live · history accumulates after first cron run
        </span>
      </div>
    );
  }

  return (
    <div className="sepa-datescrub">
      <span className="eyebrow">Viewing</span>
      <button
        className={`sepa-chip ${value === null ? 'is-active' : ''}`}
        onClick={() => onChange(null)}
        title="Show today's live SOIR scan"
      >
        Live
      </button>
      <select
        className="sepa-datescrub__select"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value || null)}
        title="Scrub the SOIR list back to a previous scan date"
      >
        <option value="">— pick a date —</option>
        {dateOptions.map((d) => (
          <option key={d.date} value={d.date}>
            {d.date} ({d.count} symbols)
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
