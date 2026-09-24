/* AmdRaidsChip — ONE muted chip beside the AMD verdict, and the full list of
 * raids in a drill-in.
 *
 * Ajay 2026-09-24: "Show all the possible raids, past ones too and todays too."
 *
 * IT PRINTS SERVED SENTENCES AND NOTHING ELSE. The chip text, its hover title,
 * the summary, the basis, every row and the note are written on the backend
 * (supply_demand/amd.py wording, chart_maps/board.py::_attach_amd_raids). The
 * only characters this file composes are "#" + the served mark, and "—" for a
 * row with no mark. It counts nothing.
 *
 * Rule #5: the tile header is dense, so this is exactly one chip, muted (the
 * read is MEASURED INVERTED), placed right after the verdict sentence it
 * expands. The list lives in the panel. The AMD checkbox hides both, because
 * filterTile drops `amd_raids` with the family.
 *
 * The whole tile is a <Link>: every handler here calls preventDefault AND
 * stopPropagation, or opening the list would navigate to the ticker page.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { SyntheticEvent } from 'react';
import { panelAlign, type AmdRaid, type AmdRaidsBlock } from '../lib/amdRaids';

const stop = (e: SyntheticEvent) => {
  e.preventDefault();
  e.stopPropagation();
};

function rowClass(r: AmdRaid): string {
  let cls = 'cm-amd-raids-row';
  if (!r.in_view) cls += ' cm-amd-raids-row--off';
  if ((r.sweep_seq ?? 1) > 1 || r.resweep_of) cls += ' cm-amd-raids-row--resweep';
  return cls;
}

export function AmdRaidsChip({ block }: { block: AmdRaidsBlock | null }) {
  const [open, setOpen] = useState(false);
  const [align, setAlign] = useState<'right' | 'left' | 'fixed'>('right');
  const wrapRef = useRef<HTMLSpanElement>(null);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        setOpen(false);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  if (!block || !block.chip) return null;
  const chip = block.chip;

  const toggle = (e: SyntheticEvent) => {
    stop(e);
    if (!open) {
      const el = wrapRef.current;
      const rect = el ? el.getBoundingClientRect() : null;
      const vw = typeof window !== 'undefined' ? window.innerWidth : 0;
      setAlign(rect && vw ? panelAlign({ left: rect.left, right: rect.right }, vw) : 'right');
    }
    setOpen((o) => !o);
  };

  // Newest first. The served list is oldest first; a copy is sorted so the
  // block the chart reads is never mutated.
  const closedRows = [...block.raids].sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));

  return (
    <span className="cm-amd-raids" ref={wrapRef}>
      <button type="button" className="cm-badge cm-badge-muted cm-amd-raids-chip"
              aria-expanded={open} aria-haspopup="dialog" title={chip.title}
              onClick={toggle}>
        {chip.text}
      </button>
      {open ? (
        <span className={`cm-amd-raids-panel cm-amd-raids-panel--${align}`}
              role="dialog" aria-label="AMD raids" onClick={stop}>
          <button type="button" className="cm-amd-raids-close" aria-label="Close AMD raids"
                  onClick={(e) => { stop(e); close(); }}>
            ✕
          </button>
          {block.summary ? <span className="cm-amd-raids-summary">{block.summary}</span> : null}
          {block.basis ? <span className="cm-amd-raids-basis">{block.basis}</span> : null}
          <span className="cm-amd-raids-list" role="list">
            {block.today.map((e, k) => (
              <span key={`t-${e.direction}-${k}`} role="listitem"
                    className="cm-amd-raids-row cm-amd-raids-row--today">
                {e.n != null && e.mark
                  ? <><span className="cm-amd-raids-mark">{`#${e.mark}`}</span>{' '}</>
                  : null}
                <span className="cm-amd-raids-text">{e.text}</span>
              </span>
            ))}
            {closedRows.map((r, k) => (
              <span key={`r-${r.direction}-${r.date}-${k}`} role="listitem" className={rowClass(r)}>
                <span className="cm-amd-raids-mark">{r.mark ? `#${r.mark}` : '—'}</span>{' '}
                <span className="cm-amd-raids-text">{r.text}</span>
              </span>
            ))}
          </span>
          {block.verdict_basis_note
            ? <span className="cm-amd-raids-note">{block.verdict_basis_note}</span>
            : null}
          {block.note ? <span className="cm-amd-raids-note">{block.note}</span> : null}
        </span>
      ) : null}
    </span>
  );
}
