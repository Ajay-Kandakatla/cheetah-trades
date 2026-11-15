/**
 * 🌫️ 2026-11-15 — the day read line (spec §3.7). Ajay 2026-11-15 said yes to an information-only day label on the
 * Gajjala tab. Prints the served block (backend chart_maps/gajjala/day_read.served_block) verbatim: the head and the
 * caption visible; the chips, the note and the read rule under the served `fold_text`, OPEN by default (Ajay
 * 2026-11-15 "Yes" to unfolding them; a tap still folds) (an older API without
 * `fold_text` gets them unfolded). The absent state = head + caption + the read rule. A null block renders nothing.
 * Every word is served — this file types none (source-guarded in DayReadLine.test.tsx). Never a gate, sort or filter.
 */
import type { DayRead, DayReadChip } from '../lib/dayRead';
import '../styles/dayRead.css';

const str = (v: unknown): v is string => typeof v === 'string' && v.length > 0;

function chipTitle(c: DayReadChip): string | undefined {
  return [c.asof_text, c.source].filter((s): s is string => str(s)).join(' · ') || undefined;
}

export function DayReadLine({ block }: { block?: DayRead | null }) {
  if (!block || typeof block.head !== 'string') return null;
  const chips = Array.isArray(block.chips) ? block.chips : [];
  const chipList = chips.length ? (
    <ul className="dr-chips" data-testid="day-read-chips">
      {chips.map((c) => (
        <li key={c.form} className={`dr-chip dr-${c.state}`} data-state={c.state}
            data-testid={`day-read-chip-${c.form}`} title={chipTitle(c)}>
          {c.text}{str(c.state_text) ? `: ${c.state_text}` : ''}{str(c.value_text) ? ` · ${c.value_text}` : ''}
          {str(c.why) ? ` — ${c.why}` : ''}
        </li>
      ))}
    </ul>
  ) : null;
  const note = typeof block.note === 'string'
    ? <p className="dr-muted" data-testid="day-read-note">{block.note}</p> : null;
  const date = typeof block.read_date_text === 'string'
    ? <p className="dr-muted" data-testid="day-read-date">{block.read_date_text}</p> : null;
  return (
    <section className="dr" data-testid="day-read">
      <div className="dr-head" data-testid="day-read-head">{block.head}</div>
      {typeof block.caption === 'string' ? (
        <p className="dr-caption" data-testid="day-read-caption">{block.caption}</p>
      ) : null}
      {chipList ? (
        typeof block.fold_text === 'string' ? (
          <details className="dr-fold" data-testid="day-read-fold" open>
            <summary data-testid="day-read-fold-summary">{block.fold_text}</summary>
            {chipList}{note}{date}
          </details>
        ) : (<>{chipList}{note}{date}</>)
      ) : date}
    </section>
  );
}

export default DayReadLine;
