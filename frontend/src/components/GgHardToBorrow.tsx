/* 🔒 GgHardToBorrow — the served "Hard to borrow" tag on the 🚩 Gajjala surfaces (2026-11-22, spec htb §3.3 / §3.4).
 *
 * Ajay 2026-11-22: "Can you do something for me for reversal squeezes can you also tell me if something is under when
 * it's on our list.. i want to check if people are finding it hard to get stocks like AkAN now has that issue.. add a tag
 * to stocks tickers like short interest, name the tag " hard to borrow" threshold security"
 *
 * Three pieces, one hook (useRegSho — ONE GET /short-interest/reg-sho per page):
 * - Chip  — the served `chip` (cards) or the served `short` form (the 📋 cell, the 👀 tile head); hover = served title.
 * - Label — the served `label` under the 🩳 line on a 🎾 Reversal Squeeze card.
 * - Fault — the served `fault_text` (a Reg SHO stock list could not be read) as one line; nothing otherwise.
 * Every word is SERVED by backend/short_interest/reg_sho.py — this file types none. Renders NOTHING (no wrapper, no
 * space) when the name is not tagged, the payload is not valid, or the request failed with nothing held (a failed
 * REFETCH keeps the last good list and retries after RS_RETRY_MS — useRegSho.ts). The list measures persistent
 * fails to deliver, not a broker's borrow rate. Display only: never a gate, sort, filter, push or lane input.
 * UNMEASURED. */
import { useRegSho, useRegShoPayload } from '../hooks/useRegSho';
import '../styles/ggHardToBorrow.css';

export function GgHardToBorrowChip({ symbol, testid, className = 'cm-badge', lead, form = 'chip' }: {
  symbol: string; testid: string; className?: string; lead?: boolean; form?: 'chip' | 'short';
}) {
  const { tag } = useRegSho(symbol);
  if (!tag) return null;
  return (
    <>
      {lead ? ' ' : null}
      <span className={`${className} gg-htb${tag.stale ? ' gg-htb-stale' : ''}`} title={tag.title} data-testid={testid}
            data-htb-market={tag.market} data-htb-asof={tag.asOf}>
        {form === 'short' ? tag.short : tag.chip}
      </span>
    </>
  );
}

export function GgHardToBorrowLabel({ symbol, testid }: { symbol: string; testid: string }) {
  const { tag } = useRegSho(symbol);
  if (!tag) return null;
  return (
    <div className={`cm-note gg-line gg-htb-label${tag.stale ? ' gg-htb-stale' : ''}`} title={tag.title}
         data-testid={testid} data-htb-market={tag.market} data-htb-asof={tag.asOf}>
      {tag.label}
    </div>
  );
}

export function GgHardToBorrowFault({ testid, className = 'cm-note cm-note-err', inline }: {
  testid: string; className?: string; inline?: boolean;
}) {
  const { payload } = useRegShoPayload();
  const text = payload?.fault_text;
  if (typeof text !== 'string' || !text.trim()) return null;
  const cls = `${className} gg-htb-fault`;
  return inline
    ? <span className={cls} data-testid={testid}>{text}</span>
    : <div className={cls} data-testid={testid}>{text}</div>;
}
