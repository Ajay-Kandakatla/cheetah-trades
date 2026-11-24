/* ⛔ GgSsr — the served SEC Rule 201 read on the 🚩 / 🧪 Gajjala cards, the 🎾 card and the 👀 Watch tile head
 * (2026-11-23, spec ssr §3.10).
 *
 * Ajay 2026-11-23: "No shorting at the bid (SEC short-sale restriction)
 * Can we check or this for other stocks too?"
 *
 * Three pieces, one batched hook (useSsr — ONE GET /short-interest/ssr?symbols=… per commit):
 * - Chip  — the served `chip` (cards) or the served `short` form (the 👀 tile head); hover = the served title.
 * - Label — the served `label` right after the 💸 line on a 🎾 Reversal Squeeze card.
 * - Fault — the served `fault_text` (the newest valid payload's) as one line; nothing otherwise.
 * Every word is SERVED by backend/short_interest/ssr.py — this file types none, and prints whatever is served for ANY
 * state: a form the server serves as null draws NOTHING (no wrapper, no space). A name read as off or as a quiet unknown
 * arrives as no item and draws nothing. Nothing draws without a valid payload or after a failed GET with nothing held.
 * Display only: never a gate, sort, filter, push or lane input. UNMEASURED. */
import { useSsr, useSsrFault } from '../hooks/useSsr';
import '../styles/ggSsr.css';

const drawn = (x: string | null | undefined): x is string => typeof x === 'string' && x.trim() !== '';

export function GgSsrChip({ symbol, testid, className = 'cm-badge', lead, form = 'chip' }: {
  symbol: string; testid: string; className?: string; lead?: boolean; form?: 'chip' | 'short';
}) {
  const { read } = useSsr(symbol);
  const text = read ? (form === 'short' ? read.short : read.chip) : null;
  if (!read || !drawn(text)) return null;
  return (
    <>
      {lead ? ' ' : null}
      <span className={`${className} gg-ssr`} title={read.title} data-testid={testid} data-ssr-state={read.state}>
        {text}
      </span>
    </>
  );
}

export function GgSsrLabel({ symbol, testid }: { symbol: string; testid: string }) {
  const { read } = useSsr(symbol);
  if (!read || !drawn(read.label)) return null;
  return (
    <div className="cm-note gg-line gg-ssr-label" title={read.title} data-testid={testid} data-ssr-state={read.state}>
      {read.label}
    </div>
  );
}

export function GgSsrFault({ testid, className = 'cm-note cm-note-err' }: { testid: string; className?: string }) {
  const text = useSsrFault();
  if (!drawn(text)) return null;
  return <div className={`${className} gg-ssr-fault`} data-testid={testid}>{text}</div>;
}
