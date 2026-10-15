/* HighBetaBoardNote — the lines and the dense table above the 🎢 High Beta
 * grid (2026-10-14).
 *
 * Ajay 2026-10-14, verbatim: "Can you build me a category or filter for High
 * Beta stocks in Resilient and make a scan there were all down today
 * especially a qqq series. Can you please make sure you do a full scan." —
 * then "Can you create a new tab for High Beta stocks" — then "in the High
 * Beta tab.I wanna able to sort my most volatile stocks".
 *
 * The board is rated, read and ordered on the server
 * (chart_maps/high_beta_tab.py). This component prints its SERVED sentences
 * verbatim — the header, the market line, the QQQ line, the order line, the
 * view line, the count line, the categories line, the note (the UNMEASURED /
 * MEASURED line) and the held-out names — plus the served sort buttons, the
 * five boxes, the "include green names" switch and the table. It composes no
 * sentence, reads no count and does no maths: a number typed here could
 * disagree with the board it describes.
 *
 * THE SORT BUTTONS are the served `sorts`, one each, labels served (🎢 β ×
 * today's drop · 📉 today's drop · 🌊 the σ order, A14); an entry with no
 * label renders no button. The PRESSED button is the board's SERVED `sort` —
 * the key the server RESOLVED (`default` → β × today's drop) — and only when
 * the board carries none, the page's served `sort`; never the URL. A click
 * hands the key to the page's one sort setter.
 *
 * THE BOXES are the Dual Momentum boxes, reused (DualMomentumFilters with this
 * tab's served keys and `cm-hb` test ids): CHECKED = the served `on`, the
 * "must match all" switch only while a box is ticked; a served OFF box (the
 * QQQ box when the Nasdaq-100 list could not be read) is greyed with its
 * served reason.
 *
 * THE SWITCH (AMENDMENTS A1: red only by default) is the served `view` —
 * label served, CHECKED = the served `on`; a click hands off to the page's one
 * `?hb_all=` setter.
 *
 * THE TABLE (A1, his K2 "every red name"): one row per served `rows` entry —
 * every listed name left after the view, the boxes and the floor — in the
 * SERVED order, above the charts (the charts are the first of them). The
 * column heads, the category words and the QQQ word are the served
 * `table` block (high_beta_tab.table_block); each number cell prints its
 * served `text` (the card's own stat values) or nothing — never a raw number.
 * With the served switch OFF a row the server marks `red: false` is never
 * drawn, whatever else arrives. No served `table` = no table (the lines and
 * the charts stay).
 *
 * Renders NOTHING for an absent or malformed block. While the memo warms the
 * header is the served warming line with role="status", and no box, switch,
 * table or held-out fold renders.
 */
import type { ReactNode } from 'react';
import type { CmSort } from '../lib/chartMaps';
import { HB_FILTER_KEYS } from '../lib/highBeta';
import type { CmHighBetaBoard, CmHighBetaRow } from '../lib/highBeta';
import { DualMomentumFilters } from './DualMomentumBoardNote';
import { TickerLink } from './TickerLink';

const text = (v: unknown): string | null =>
  typeof v === 'string' && v.trim().length > 0 ? v : null;
const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : null;
/** A number cell: the served display text (high_beta_tab.compact_row `text`
 *  = the card's own stat values), else EMPTY. Never the raw number — a bare
 *  move or β would read differently from the card's served text for the same
 *  name. */
const cell = (served: unknown): string => (typeof served === 'string' ? served : '');

/** The column keys the table knows how to draw; a served key outside this set
 *  is skipped (a cell the component cannot fill is not drawn blank). */
const COLUMN_KEYS: ReadonlySet<string> = new Set(['symbol', 'beta', 'sigma', 'cats', 'qqq', 'today', 'swing']);

type Props = {
  board: CmHighBetaBoard | null | undefined;
  /** The payload's top-level `rows` (high_beta_tab.compact_row). */
  rows?: CmHighBetaRow[] | null;
  sorts?: CmSort[] | null;
  sort?: string | null;
  onSort: (key: string) => void;
  onToggleFilter?: (key: string) => void;
  onToggleMode?: () => void;
  onToggleGreen?: () => void;
};

type Row = Record<string, unknown> & { symbol: string };

function HighBetaTable({ table, rows: raw, greenOn }: {
  table: Record<string, unknown>; rows: unknown; greenOn: boolean;
}) {
  const columns = (Array.isArray(table.columns) ? table.columns as unknown[] : [])
    .map(obj)
    .filter((c): c is Record<string, unknown> =>
      !!c && typeof c.key === 'string' && COLUMN_KEYS.has(c.key) && !!text(c.label));
  if (!columns.some((c) => c.key === 'symbol')) return null;
  const catLabels = obj(table.cat_labels) ?? {};
  const qqqLabel = text(table.qqq_label);
  const rows = (Array.isArray(raw) ? raw as unknown[] : [])
    .map(obj)
    .filter((r): r is Row => !!r && !!text(r.symbol))
    // Green names only while the SERVED switch is on (A1 default: red only).
    .filter((r) => greenOn || r.red !== false);
  if (!rows.length) return null;
  return (
    <div className="cm-hb-table-wrap" data-testid="cm-hb-table-wrap"
         style={{ overflow: 'auto', maxHeight: '28rem', margin: '0.2rem 0 0.6rem',
                  border: '1px solid var(--cm-border, #263041)', borderRadius: 6 }}>
      <table className="cm-hb-table" data-testid="cm-hb-table"
             style={{ borderCollapse: 'collapse', fontSize: '0.78rem', fontVariantNumeric: 'tabular-nums' }}>
        <thead>
          <tr>
            {columns.map((c, i) => (
              <th key={String(c.key)} scope="col" title={text(c.title) ?? undefined}
                  data-testid={`cm-hb-col-${String(c.key)}`}
                  style={{ position: 'sticky', top: 0, zIndex: i === 0 ? 2 : 1, left: i === 0 ? 0 : undefined,
                           background: 'var(--cm-card, #111827)', textAlign: i === 0 ? 'left' : 'right',
                           padding: '0.25rem 0.5rem', whiteSpace: 'nowrap', fontWeight: 600 }}>
                {String(c.label)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const t = obj(r.text) ?? {};
            const read = r.state === 'read';
            const todayColor = !read ? 'var(--cm-slate, #8595ad)'
              : r.red === true ? 'var(--cm-red, #f85149)'
              : r.red === false ? 'var(--cm-green, #10b981)' : undefined;
            const cats = (Array.isArray(r.cats) ? r.cats as unknown[] : [])
              .map((k) => (typeof k === 'string' ? text(catLabels[k]) : null))
              .filter((l): l is string => !!l);
            return (
              <tr key={r.symbol} data-testid={`cm-hb-row-${r.symbol}`}
                  data-red={r.red === true ? 'true' : r.red === false ? 'false' : undefined}
                  style={{ borderTop: '1px solid var(--cm-border, #263041)' }}>
                {columns.map((c, i) => {
                  const key = String(c.key);
                  let body: ReactNode = null;
                  if (key === 'symbol') {
                    body = <TickerLink ticker={r.symbol} fromLabel="High Beta" showWatchlist={false} />;
                  } else if (key === 'beta') body = cell(t.beta);
                  else if (key === 'sigma') body = cell(t.sigma);
                  else if (key === 'swing') body = cell(t.swing);
                  else if (key === 'today') {
                    body = <span style={{ color: todayColor }}>{cell(t.today)}</span>;
                  } else if (key === 'cats') {
                    body = cats.map((l) => (
                      <span key={l} className="cm-badge cm-badge-muted" style={{ marginLeft: '0.2rem' }}>{l}</span>
                    ));
                  } else if (key === 'qqq') {
                    body = r.qqq === true && qqqLabel
                      ? <span className="cm-badge cm-badge-theme" data-testid={`cm-hb-qqq-${r.symbol}`}>{qqqLabel}</span>
                      : null;
                  }
                  return (
                    <td key={key} data-testid={`cm-hb-cell-${key}-${r.symbol}`}
                        style={{ padding: '0.2rem 0.5rem', whiteSpace: 'nowrap', textAlign: i === 0 ? 'left' : 'right',
                                 ...(i === 0 ? { position: 'sticky', left: 0, zIndex: 1,
                                                 background: 'var(--cm-card, #111827)' } : {}) }}>
                      {body}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function HighBetaBoardNote({ board, rows, sorts, sort, onSort, onToggleFilter, onToggleMode, onToggleGreen }: Props) {
  const b = obj(board);
  if (!b) return null;
  const header = text(b.header);
  if (!header) return null;
  const raw = b.state;
  const state = raw === 'warming' || raw === 'error' ? raw : 'ready';
  const ready = state === 'ready';
  const offered = (Array.isArray(sorts) ? sorts : [])
    .map(obj)
    .filter((s): s is Record<string, unknown> => !!s && !!text(s.key) && !!text(s.label));
  const served = typeof b.sort === 'string' ? b.sort : (typeof sort === 'string' ? sort : null);
  const lines = ready
    ? ([['market', b.market_line], ['qqq', b.qqq_line], ['order', b.order_line], ['view', b.view_line]] as const)
      .map(([k, v]) => [k, text(v)] as const)
      .filter((kv): kv is readonly ['market' | 'qqq' | 'order' | 'view', string] => !!kv[1])
    : [];
  const counts = ready ? text(b.count_line) : null;
  const catsLine = ready ? text(b.categories_line) : null;
  const note = text(b.note);
  const study = obj(b.study);
  const studyText = study ? text(study.text) : null;
  // The study sentence is printed once: not again when the note already says it.
  const showStudy = ready && !!studyText && studyText !== header && !(note && note.includes(studyText));
  const sus = ready ? obj(b.suspects) : null;
  const susN = sus && typeof sus.n === 'number' && Number.isFinite(sus.n) ? sus.n : 0;
  const susHead = sus ? text(sus.head) : null;
  const susLines = sus && Array.isArray(sus.lines)
    ? (sus.lines as unknown[]).filter((l): l is string => !!text(l)) : [];
  const view = ready ? obj(b.view) : null;
  const viewLabel = view ? text(view.label) : null;
  const greenOn = view?.on === true;
  const table = ready ? obj(b.table) : null;
  return (
    <div data-testid="cm-hb-board" data-state={state}
         data-mode={typeof b.mode === 'string' ? b.mode : undefined}>
      {offered.length > 0 ? (
        <span className="cm-phase-sub" role="group" aria-label="Order the board"
              data-testid="cm-hb-sorts">
          {offered.map((o) => {
            const key = String(o.key);
            const on = served === key;
            return (
              <button key={key} type="button" aria-pressed={on}
                      data-testid={`cm-hb-sort-${key}`}
                      className={`cm-phase-btn${on ? ' cm-phase-on' : ''}`}
                      onClick={() => onSort(key)}>
                {String(o.label)}
              </button>
            );
          })}
        </span>
      ) : null}
      {onToggleFilter && ready
        ? <DualMomentumFilters filters={b.filters} onToggle={onToggleFilter} onToggleMode={onToggleMode}
                               knownKeys={HB_FILTER_KEYS} testIdPrefix="cm-hb" />
        : null}
      {onToggleGreen && viewLabel ? (
        <span className="cm-phase-sub" role="group" aria-label="Green names" data-testid="cm-hb-green-group">
          <label className="cm-ctl cm-ctl-check dm-filter">
            <input type="checkbox" data-testid="cm-hb-green" checked={greenOn}
                   onChange={() => onToggleGreen()} />
            {viewLabel}
          </label>
        </span>
      ) : null}
      <p className="cm-note" data-testid="cm-hb-header"
         role={state === 'warming' ? 'status' : undefined}>{header}</p>
      {lines.map(([k, l]) => (
        <p key={k} className="cm-note" data-testid={`cm-hb-${k}`}>{l}</p>
      ))}
      {counts ? <p className="cm-note cm-dim" data-testid="cm-hb-counts">{counts}</p> : null}
      {catsLine ? <p className="cm-note cm-dim" data-testid="cm-hb-categories">{catsLine}</p> : null}
      {note && note !== header ? <p className="cm-note cm-dim" data-testid="cm-hb-note">{note}</p> : null}
      {showStudy ? <p className="cm-note cm-dim" data-testid="cm-hb-study">{studyText}</p> : null}
      {susN > 0 && susHead ? (
        <details className="cm-note cm-dim" data-testid="cm-hb-suspects">
          <summary>{susHead}</summary>
          {susLines.map((l, i) => (
            <p key={`s-${i}`} className="cm-note cm-dim" data-testid="cm-hb-suspect">{l}</p>
          ))}
        </details>
      ) : null}
      {table ? <HighBetaTable table={table} rows={rows} greenOn={greenOn} /> : null}
    </div>
  );
}

export { HighBetaBoardNote };
