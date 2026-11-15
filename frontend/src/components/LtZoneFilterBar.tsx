/* LtZoneFilterBar — the 🎯 Enterable (zones) checkbox, its sheet / level chips and the count line on the 📅 Long Term
 * table (2026-11-14, ltenter spec §3.7). Ajay 2026-11-14: "Make a enterable check box in longterm stocks with zone and
 * filters please".
 *
 * Every word on a chip and every count is served (`rules.sources` / `rules.levels` / `rules.reasons` labels, the
 * partition's numbers); the FE types only the control words "🎯 Enterable (zones)", "hidden", "showing all", "show all"
 * and "enterable only". The sheet / level chips render only while the box is ticked (they change nothing while it is
 * off; the saved choice comes back pressed). The count line always names the state, so a filter is never invisible.
 * Display only: it hides rows from view and never reorders them. UNMEASURED. */
import type { LtZoneRules } from '../lib/longTerm';
import { ltLevelKey, type LtZoneFilter, type LtZonePartition, type LtZoneSource } from '../lib/ltZones';

type Props = { rules: LtZoneRules; zf: LtZoneFilter; onChange: (f: LtZoneFilter) => void; part: LtZonePartition };

const isSource = (k: string): k is LtZoneSource => k === 'both' || k === 'pankaj' || k === 'gabbar';

export function LtZoneFilterBar({ rules, zf, onChange, part }: Props) {
  const sources = Array.isArray(rules.sources) ? rules.sources : [];
  const levels = Array.isArray(rules.levels) ? rules.levels : [];
  const allLevels = levels.map((l) => ltLevelKey({ source: l.source, level: l.key }));
  const set = (patch: Partial<LtZoneFilter>) => onChange({ ...zf, ...patch });

  /* [] = every level (every chip drawn pressed). A click while all are pressed keeps ONLY that level; un-pressing the
   * last one — or pressing the last missing one — returns to all. */
  const toggleLevel = (k: string) => {
    if (!zf.levels.length) { set({ levels: [k] }); return; }
    const next = zf.levels.includes(k) ? zf.levels.filter((x) => x !== k) : [...zf.levels, k];
    set({ levels: allLevels.every((x) => next.includes(x)) ? [] : next });
  };
  const toggleReason = (code: string) => {
    set({ unhide: zf.unhide.includes(code) ? zf.unhide.filter((x) => x !== code) : [...zf.unhide, code] });
  };
  const shownReasons = part.reasons.filter((r) => Boolean(r.baseline) || r.ignored);

  return (
    <div className="lt-zf-bar" data-testid="lt-zf-bar">
      <label className="lt-zf-toggle" title={rules.text ?? undefined}>
        <input type="checkbox" data-testid="lt-zf-on" checked={zf.on} onChange={(e) => set({ on: e.target.checked })} />
        {'🎯 Enterable (zones)'}
      </label>
      {zf.on ? sources.map((s) => (
        <button key={s.key} type="button" className="lt-zf-chip" data-testid={`lt-zf-src-${s.key}`}
                aria-pressed={zf.source === s.key} onClick={() => { if (isSource(s.key)) set({ source: s.key }); }}>
          {s.label}
        </button>
      )) : null}
      {zf.on ? levels.map((l) => {
        const k = ltLevelKey({ source: l.source, level: l.key });
        const off = zf.source !== 'both' && zf.source !== l.source;
        return (
          <button key={k} type="button" className="lt-zf-chip" data-testid={`lt-zf-lvl-${k}`} disabled={off}
                  aria-pressed={!zf.levels.length || zf.levels.includes(k)} onClick={() => toggleLevel(k)}>
            {l.label}
          </button>
        );
      }) : null}
      <span className="lt-line lt-muted" data-testid="lt-zf-count">
        {zf.on ? (
          <>
            {part.hidden}{' hidden'}
            {shownReasons.map((r) => (
              <button key={r.code} type="button" className="lt-zf-reason" data-testid={`lt-zf-reason-${r.code}`}
                      aria-pressed={r.ignored} title={rules.words?.not_house_chip ?? undefined}
                      onClick={() => toggleReason(r.code)}>
                {r.baseline}{' '}{r.label}
              </button>
            ))}
            {' · '}
            <button type="button" className="lt-zf-reason" data-testid="lt-zf-show-all" onClick={() => set({ on: false })}>
              {'show all'}
            </button>
          </>
        ) : (
          <>
            {'showing all · '}
            <button type="button" className="lt-zf-reason" data-testid="lt-zf-show-only" onClick={() => set({ on: true })}>
              {'🎯 enterable only'}
            </button>
          </>
        )}
      </span>
    </div>
  );
}
