/* 💸 GgBorrow — the served borrow read on the 🚩 / 🧪 Gajjala cards and the 📋 table (2026-11-22, spec borrow §3.3 / §3.4).
 *
 * Ajay 2026-11-22: "What is short borrow fee? Is that a real time value I saw AKAN has a high short borrow fee" — then:
 * "yes i need that please".
 *
 * Two pieces, one batched hook (useBorrow — ONE GET /short-interest/borrow?symbols=… per page):
 * - Chip  — the served `chip` (cards) or the served `short` form (the 📋 cell); hover = the served title.
 * - Label — the served `label` under the 🔒 / 🩳 line on a 🎾 Reversal Squeeze card.
 * Every word is SERVED by backend/short_interest/borrow.py — this file types none, and prints whatever is served for ANY
 * state (listed / absent / unread): a form the server serves as null draws NOTHING (no wrapper, no space). Nothing draws
 * without a valid payload or after a failed GET with nothing held. One broker's indicative rate. Display only: never a
 * gate, sort, filter, push or lane input. Not on the 👀 Watch (his call). UNMEASURED. */
import { useBorrow } from '../hooks/useBorrow';
import '../styles/ggBorrow.css';

const drawn = (x: string | null | undefined): x is string => typeof x === 'string' && x.trim() !== '';

export function GgBorrowChip({ symbol, testid, className = 'cm-badge', lead, form = 'chip' }: {
  symbol: string; testid: string; className?: string; lead?: boolean; form?: 'chip' | 'short';
}) {
  const { read } = useBorrow(symbol);
  const text = read ? (form === 'short' ? read.short : read.chip) : null;
  if (!read || !drawn(text)) return null;
  return (
    <>
      {lead ? ' ' : null}
      <span className={`${className} gg-brw${read.stale ? ' gg-brw-stale' : ''}`} title={read.title} data-testid={testid}
            data-brw-state={read.state}>
        {text}
      </span>
    </>
  );
}

export function GgBorrowLabel({ symbol, testid }: { symbol: string; testid: string }) {
  const { read } = useBorrow(symbol);
  if (!read || !drawn(read.label)) return null;
  return (
    <div className={`cm-note gg-line gg-brw-label${read.stale ? ' gg-brw-stale' : ''}`} title={read.title}
         data-testid={testid} data-brw-state={read.state}>
      {read.label}
    </div>
  );
}
