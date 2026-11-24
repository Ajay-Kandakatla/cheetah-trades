/* ⛔ GgSsrNewSection — the names newly under SEC Rule 201 in the session shown, inside the 🩳 High SI panel
 * (2026-11-24, spec ssrlist §3.4, WP W3).
 *
 * Ajay 2026-11-24: "What are the SSR stocks today" · "Can you add it to short interest tab" · "The new ones"
 *
 * Drawn from the SERVED block only (high_si.block → ssr_new, built by high_si.ssr_new_block over ssr.new_triggers).
 * ALWAYS VISIBLE, in this order, each only when served as a non-empty string: the title, the counts line, the tier note,
 * the window, the as-of, the status, the partial note, the SI note, the list note, the faults line, the fault line, the
 * empty line.
 * 2026-11-24: on the 🚩 board the whole panel sits inside the sub's closed ⓘ fold (GajjalaBoard); 'always visible'
 * here means outside this panel's own rule fold.
 * Then one <details> per served fold — its rows are MOUNTED ONLY WHILE THE FOLD IS OPEN (a closed fold of
 * several hundred names costs no DOM) — and last the ⓘ rule fold (drawn only under a served label).
 * A served fault line means NO fold and NO empty line, whatever else is served.
 * This file types no word and formats no number: it never sorts, filters (beyond the served-shape guard), counts or
 * fetches; `n` / `n_untiered` are never printed. Display only — never a gate, sort, push or lane input. UNMEASURED. */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ggHref, type GgSsrNewBlock, type GgSsrNewGroup, type GgSsrNewRow } from '../lib/gajjala';
import '../styles/ggSsr.css';

/** A served line prints only when it is a non-empty string — NaN / undefined / null / a number prints nothing. */
function servedText(v: unknown): v is string {
  return typeof v === 'string' && v.trim() !== '';
}

function Line({ v, testid, className = 'gg-ssrn-line gg-muted' }: { v: unknown; testid: string; className?: string }) {
  if (!servedText(v)) return null;
  return <p className={className} data-testid={testid}>{v}</p>;
}

const isObj = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);

/** The served-shape guard: the rows that carry a served symbol, in the SERVED order. */
function servedRows(g: GgSsrNewGroup): GgSsrNewRow[] {
  return Array.isArray(g.rows) ? g.rows.filter((r) => isObj(r) && servedText(r.symbol)) : [];
}

function Piece({ v, className }: { v: unknown; className: string }) {
  return servedText(v) ? <span className={className}>{v}</span> : null;
}

function Row({ row }: { row: GgSsrNewRow }) {
  const sym = row.symbol as string;
  const href = ggHref(row.href);
  return (
    <li className="gg-ssrn-row" data-testid={`gg-ssrn-row-${sym}`}>
      <span className="gg-ssrn-sym">{href ? <Link to={href}>{sym}</Link> : sym}</span>
      <Piece v={row.at_text} className="gg-ssrn-at" />
      <Piece v={row.drop_text} className="gg-ssrn-drop" />
      <Piece v={row.source_text} className="gg-ssrn-src" />
      <Piece v={row.mark_text} className="gg-ssrn-mark" />
      <Piece v={row.si_text} className="gg-ssrn-si" />
    </li>
  );
}

function Fold({ group, id, rows }: { group: GgSsrNewGroup; id: string; rows: GgSsrNewRow[] }) {
  const [open, setOpen] = useState(group.open === true);
  return (
    <details className="gg-ssrn-g" data-testid={`gg-ssrn-g-${id}`} open={open}
             onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary>{group.summary}</summary>
      {open ? (
        <ul className="gg-ssrn-rows">
          {rows.map((r, i) => <Row key={`${r.symbol}-${i}`} row={r} />)}
        </ul>
      ) : null}
    </details>
  );
}

export function GgSsrNewSection({ block }: { block: GgSsrNewBlock | null | undefined }) {
  if (!isObj(block)) return null;
  const b = block as GgSsrNewBlock;
  const faulted = servedText(b.fault_text);
  const groups = faulted || !Array.isArray(b.groups) ? [] : b.groups
    .filter((g): g is GgSsrNewGroup => isObj(g) && servedText(g.summary))
    .map((g, i) => ({ g, id: servedText(g.key) ? g.key : String(i), rows: servedRows(g) }))
    .filter((x) => x.rows.length);
  return (
    <section className="gg-ssrn" data-testid="gg-ssrn">
      {servedText(b.title) ? <h4 className="gg-ssrn-title" data-testid="gg-ssrn-title">{b.title}</h4> : null}
      <Line v={b.counts_text} testid="gg-ssrn-counts" className="gg-ssrn-line" />
      <Line v={b.tier_note} testid="gg-ssrn-tier-note" />
      <Line v={b.window_text} testid="gg-ssrn-window" />
      <Line v={b.asof_text} testid="gg-ssrn-asof" />
      <Line v={b.status_text} testid="gg-ssrn-status" className="gg-ssrn-line" />
      <Line v={b.partial_text} testid="gg-ssrn-partial" className="gg-ssrn-line cm-note" />
      <Line v={b.si_note} testid="gg-ssrn-si-note" />
      <Line v={b.list_note} testid="gg-ssrn-list-note" />
      <Line v={b.faults_text} testid="gg-ssrn-faults" className="gg-ssrn-line cm-note" />
      <Line v={b.fault_text} testid="gg-ssrn-fault" className="gg-ssrn-line cm-note cm-note-err" />
      {faulted ? null : <Line v={b.empty_text} testid="gg-ssrn-empty" className="gg-ssrn-line" />}
      {groups.map(({ g, id, rows }) => <Fold key={id} group={g} id={id} rows={rows} />)}
      {servedText(b.rule_label) ? (
        <details className="gg-ssrn-rule" data-testid="gg-ssrn-rule">
          <summary>{b.rule_label}</summary>
          <Line v={b.rule_text} testid="gg-ssrn-rule-text" />
          <Line v={b.note_text} testid="gg-ssrn-note" />
          <Line v={b.order_note} testid="gg-ssrn-order" />
          <Line v={b.withheld_text} testid="gg-ssrn-withheld" />
        </details>
      ) : null}
    </section>
  );
}
