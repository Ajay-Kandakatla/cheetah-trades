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
 *
 * 2026-10-14 b — header sorts, 5 / 21 days, the Price | Sales view. Ajay
 * 2026-10-14, verbatim: "Can you add sort function on the headers and also 5
 * day and 21 days columns to show how they were reacting in price like hot
 * sectors and also add sales tab make it like hot sector with some important
 * metrics like EPS, QUAlity and other colums that show the strength of the
 * stock".
 *  - HEADERS (K4): every served column with a served `sort` and `first` is a
 *    `button.hs-sort` (the 🔥 Hottest header recipe: `is-sorted`, `aria-sort`,
 *    the sortMark arrow). A tap hands `hbHeaderNext`'s answer to the page —
 *    the SERVER orders the rows (high_beta_tab.order_rows) and the 80 charts
 *    follow; this table never re-orders a row. With no handler (or an old
 *    payload) the heads stay plain labels.
 *  - PRICE: the served 5 / 21-day cells (own move and vs the served bench)
 *    print their served `text` (1 dp, high_beta_tab.LEG_TEXT_DP); the number
 *    only picks the 🔥 tone class. The served `returns_line` sits under the
 *    market line.
 *  - SALES (K1, K3): the same rows; the six 🔥 Hottest fundamentals cells are
 *    Hottest's own HsFundCell (one renderer, so a 🎢 cell and a 🔥 cell for one
 *    name read the same), ⓘ Quality beside its sort button, RS vs SPY as
 *    served text. A row the research cache did not answer draws EMPTY cells —
 *    never a zero, never a dash typed here. The served fundamentals line and
 *    note print in this view only.
 *  - The view is the page's `?hb_view=` (FE-only state, no refetch); the
 *    toggle's labels are the served `table.views`.
 *  - The box scrolls sideways under a sticky Symbol column with the "more
 *    columns →" cue (useHScrollCue), like 🔥 Hottest.
 */
import { useRef } from 'react';
import type { ReactNode } from 'react';
import type { CmSort } from '../lib/chartMaps';
import { HB_FILTER_KEYS, HB_VIEW_PRICE, HB_VIEW_SALES, hbHeaderNext, parseHbDir } from '../lib/highBeta';
import type { CmHighBetaBoard, CmHighBetaRow, HbDir, HbView } from '../lib/highBeta';
import { sortMark } from '../lib/hottestSort';
import { useHScrollCue } from '../hooks/useHScrollCue';
import { DualMomentumFilters } from './DualMomentumBoardNote';
import { HS_FUND_KEYS, HsFundCell, colTitle, tone } from './HottestSectors';
import type { HsFundKey, HsFundRow } from './HottestSectors';
import { HottestQualityInfo, showQualityInfo } from './HottestQualityInfo';
import type { HsQualityInfo } from './HottestQualityInfo';
import { InfoButton } from './InfoButton';
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
 *  is skipped (a cell the component cannot fill is not drawn blank).
 *  2026-10-14 b: + the 5 / 21-day legs, RS vs SPY and the six 🔥 Hottest
 *  fundamentals keys. Exported so a ?raw test pins every served
 *  high_beta_tab.TABLE_COLUMNS / SALES_COLUMNS key into it (AMENDMENTS2 B2). */
const LEG_KEYS: ReadonlySet<string> = new Set(['ret_5d', 'rel_5d', 'ret_21d', 'rel_21d', 'rs_spy_63d']);
const FUND_KEYS: ReadonlySet<string> = new Set<string>(HS_FUND_KEYS);
export const COLUMN_KEYS: ReadonlySet<string> = new Set([
  'symbol', 'levered', 'beta', 'sigma', 'cats', 'qqq', 'today', 'swing',
  ...LEG_KEYS, ...HS_FUND_KEYS,
]);
/** Right-aligned (`hs-num`) heads and cells — the number columns; the 🔥
 *  Hottest Sales trend / Next ER and the badge columns stay left. */
const NUM_KEYS: ReadonlySet<string> = new Set([
  'today', 'beta', 'swing', 'sigma', ...LEG_KEYS, 'sales_yoy', 'q_eps_yoy', 'net_margin', 'eq_score',
]);
const isNum = (v: unknown): number | null => (typeof v === 'number' ? v : null);

/** 🔗 (2026-10-14, "Can you add a short tag on these stocks for their Leverage
 *  equivalents like IRE for IREN, VSTL for VST"): the SERVED chip parts
 *  (sepa/levered_etf.chip), printed in order — an `etf` part is a link to its
 *  own page (/sepa/{etf}, tape tab; the route serves ETFs), a text part is a
 *  span (its served `title` on the "+n" run). Composes nothing: no factor, no
 *  "+", no join. A missing / malformed chip, or one with no drawable part,
 *  renders nothing. */
function LeveredChip({ chip, symbol, legend }: { chip: unknown; symbol: string; legend: string | null }) {
  const c = obj(chip);
  if (!c || !Array.isArray(c.parts)) return null;
  const parts = (c.parts as unknown[]).map(obj)
    .filter((p): p is Record<string, unknown> => !!p && (!!text(p.etf) || typeof p.text === 'string'));
  if (!parts.some((p) => !!text(p.etf))) return null;
  return (
    <span className="cm-badge cm-badge-muted" title={legend ?? undefined} data-testid={`cm-hb-lev-${symbol}`}>
      {parts.map((p, i) => {
        const etf = text(p.etf);
        if (etf) {
          return (
            <TickerLink key={`e-${i}`} ticker={etf} tab="tape" fromLabel="High Beta" showWatchlist={false}
                        title={text(p.title) ?? undefined} />
          );
        }
        return <span key={`t-${i}`} title={text(p.title) ?? undefined}>{String(p.text)}</span>;
      })}
    </span>
  );
}

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
  /** 2026-10-14 b — the page's `?hb_view=` (default Price), its setter, and
   *  the one header-sort setter (`dir` null = the column's served first). */
  view?: HbView;
  onView?: (v: HbView) => void;
  onHeaderSort?: (sort: string, dir: HbDir | null) => void;
};

type Row = Record<string, unknown> & { symbol: string };

type Col = Record<string, unknown> & { key: string; label: string };

const columnsOf = (v: unknown): Col[] => (Array.isArray(v) ? v as unknown[] : [])
  .map(obj)
  .filter((c): c is Col => !!c && typeof c.key === 'string' && COLUMN_KEYS.has(c.key) && !!text(c.label));

/** The view the table draws: Sales only when asked AND served (an old payload
 *  with no `sales_columns` keeps the Price heads rather than no table). */
function drawnView(table: Record<string, unknown>, view: HbView | undefined): HbView {
  return view === HB_VIEW_SALES && columnsOf(table.sales_columns).some((c) => c.key === 'symbol')
    ? HB_VIEW_SALES : HB_VIEW_PRICE;
}

function HighBetaTable({ board, table, rows: raw, greenOn, legend, view, onHeaderSort }: {
  board: Record<string, unknown>; table: Record<string, unknown>; rows: unknown; greenOn: boolean;
  legend: string | null; view: HbView; onHeaderSort?: (sort: string, dir: HbDir | null) => void;
}) {
  const columns = columnsOf(view === HB_VIEW_SALES ? table.sales_columns : table.columns);
  const rows = (Array.isArray(raw) ? raw as unknown[] : [])
    .map(obj)
    .filter((r): r is Row => !!r && !!text(r.symbol))
    // Green names only while the SERVED switch is on (A1 default: red only).
    .filter((r) => greenOn || r.red !== false);
  /* Hooks before the early returns (a hook must run on every render). The cue
   * labels are the printed heads after the sticky first column, in order. */
  const scrollRef = useRef<HTMLDivElement>(null);
  const cue = useHScrollCue(scrollRef, columns.slice(1).map((c) => c.label),
                            [columns.length, rows.length, view]);
  if (!columns.some((c) => c.key === 'symbol')) return null;
  if (!rows.length) return null;
  const catLabels = obj(table.cat_labels) ?? {};
  const qqqLabel = text(table.qqq_label);
  const fundBlock = obj(board.fundamentals);
  const info = (fundBlock && obj(fundBlock.quality_info)
    ? fundBlock.quality_info : null) as HsQualityInfo | null;
  const showInfo = showQualityInfo({ quality_info: info });
  const active = typeof board.sort === 'string' ? board.sort : null;
  const sortDir = typeof board.sort_dir === 'string' ? board.sort_dir : null;
  const scrollRight = () => {
    const el = scrollRef.current;
    if (el && typeof el.scrollBy === 'function') {
      el.scrollBy({ left: el.clientWidth * 0.8, behavior: 'smooth' });
    }
  };
  return (
    <>
      {/* Columns off to the right are ANNOUNCED, never silently cut (the 🔥
          Hottest recipe). The label list is the served heads, not textContent. */}
      {cue.right ? (
        <button type="button" className="hs-morecols" data-testid="cm-hb-more-cols"
                title={`Off to the right: ${cue.offRight.join(', ')}`} onClick={scrollRight}>
          {cue.offRight.length} more column{cue.offRight.length === 1 ? '' : 's'} →
        </button>
      ) : null}
      <div className={`hs-scrollwrap${cue.right ? ' is-more-right' : ''}${cue.left ? ' is-more-left' : ''}`}
           data-testid="cm-hb-table-wrap">
        <div className="hs-scroll cm-hb-scroll" ref={scrollRef} onScroll={cue.onScroll}>
          <table className="hs-table cm-hb-table" data-testid="cm-hb-table">
            <thead>
              <tr>
                {columns.map((c, i) => {
                  const key = c.key;
                  const label = c.label;
                  const sortKey = typeof c.sort === 'string' && c.sort ? c.sort : null;
                  const first = parseHbDir(typeof c.first === 'string' ? c.first : null);
                  const col = { sort: sortKey, first };
                  // A head is a sort button only when the server served it a key AND
                  // a readable first direction — a dead button is worse than a label.
                  const sortable = !!onHeaderSort && !!hbHeaderNext(col, null);
                  const on = !!sortKey && active === sortKey;
                  const cls = [i === 0 ? 'hs-sym' : '', NUM_KEYS.has(key) ? 'hs-num' : '', on ? 'is-sorted' : '']
                    .filter(Boolean).join(' ');
                  const ownTitle = text(c.title);
                  const head: ReactNode = sortable ? (
                    <button type="button" className="hs-sort" data-testid={`cm-hb-sort-head-${key}`}
                            title={colTitle({ key, title: ownTitle ?? undefined }, null)}
                            onClick={() => {
                              const n = hbHeaderNext(col, { sort: active, sort_dir: sortDir });
                              if (n && onHeaderSort) onHeaderSort(n.sort, n.dir);
                            }}>
                      {label}{sortMark(sortKey as string, active ?? '', parseHbDir(sortDir) ?? (first as HbDir), [])}
                    </button>
                  ) : label;
                  return (
                    <th key={key} scope="col" className={cls || undefined}
                        title={sortable ? undefined : (ownTitle ?? undefined)}
                        data-testid={`cm-hb-col-${key}`}
                        aria-sort={on ? ((parseHbDir(sortDir) ?? first) === 'asc' ? 'ascending' : 'descending') : undefined}>
                      {/* ⓘ Quality: a SIBLING of the sort button, never inside it —
                          opening it orders nothing. A sheet: this box scrolls. */}
                      {key === 'eq_score' && showInfo ? (
                        <span className="hs-thwrap">
                          {head}
                          <InfoButton inline sheet align="right" title="Quality score">
                            <HottestQualityInfo info={info as HsQualityInfo} />
                          </InfoButton>
                        </span>
                      ) : head}
                    </th>
                  );
                })}
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
                const fund = obj(r.fund);
                return (
                  <tr key={r.symbol} data-testid={`cm-hb-row-${r.symbol}`}
                      data-red={r.red === true ? 'true' : r.red === false ? 'false' : undefined}>
                    {columns.map((c, i) => {
                      const key = c.key;
                      const tid = `cm-hb-cell-${key}-${r.symbol}`;
                      if (FUND_KEYS.has(key)) {
                        // 🔥 Hottest's own cell for a read row; EMPTY when the research
                        // cache did not answer for this name (never a zero).
                        return fund
                          ? <HsFundCell key={key} k={key as HsFundKey} r={fund as unknown as HsFundRow}
                                        symbol={r.symbol} info={info} testId={tid} />
                          : <td key={key} data-testid={tid} />;
                      }
                      let body: ReactNode = null;
                      let cls = [i === 0 ? 'hs-sym' : '', NUM_KEYS.has(key) ? 'hs-num' : ''];
                      if (key === 'symbol') {
                        body = <TickerLink ticker={r.symbol} fromLabel="High Beta" showWatchlist={false} />;
                      } else if (key === 'levered') {
                        body = <LeveredChip chip={r.levered_chip} symbol={r.symbol} legend={legend} />;
                      } else if (key === 'beta') body = cell(t.beta);
                      else if (key === 'sigma') body = cell(t.sigma);
                      else if (key === 'swing') body = cell(t.swing);
                      else if (LEG_KEYS.has(key)) {
                        // The served text (1 dp); the served number only picks the tone.
                        body = cell(t[key]);
                        cls = [...cls, tone(isNum(r[key]))];
                      } else if (key === 'today') {
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
                      const className = cls.filter(Boolean).join(' ');
                      return (
                        <td key={key} data-testid={tid} className={className || undefined}>
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
      </div>
    </>
  );
}

export default function HighBetaBoardNote({ board, rows, sorts, sort, onSort, onToggleFilter, onToggleMode,
                                            onToggleGreen, view: tableView, onView, onHeaderSort }: Props) {
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
  /* 2026-10-14 b: the PRESSED preset is the served `sort_preset` (the preset
   * key only when the active column sort IS that preset in its first
   * direction; null = a header sort, so no button is pressed). A board that
   * serves no `sort_preset` keeps the rule above. */
  const pressed = 'sort_preset' in b
    ? (typeof b.sort_preset === 'string' ? b.sort_preset : null)
    : served;
  type LineKey = 'market' | 'returns' | 'qqq' | 'order' | 'view';
  const lines = ready
    ? ([['market', b.market_line], ['returns', b.returns_line], ['qqq', b.qqq_line], ['order', b.order_line],
        ['view', b.view_line]] as const)
      .map(([k, v]) => [k, text(v)] as const)
      .filter((kv): kv is readonly [LineKey, string] => !!kv[1])
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
  const lev = ready ? obj(b.levered) : null;
  const levLine = lev ? text(lev.line) : null;
  const levLegend = lev && lev.state === 'ready' ? text(lev.legend) : null;
  const shown = table ? drawnView(table, tableView) : HB_VIEW_PRICE;
  const views = table && Array.isArray(table.views)
    ? (table.views as unknown[]).map(obj)
      .filter((v): v is Record<string, unknown> & { key: HbView } =>
        !!v && (v.key === HB_VIEW_PRICE || v.key === HB_VIEW_SALES) && !!text(v.label))
    : [];
  const fund = ready && shown === HB_VIEW_SALES ? obj(b.fundamentals) : null;
  const fundLine = fund ? text(fund.line) : null;
  const fundNote = fund ? text(fund.note) : null;
  return (
    <div data-testid="cm-hb-board" data-state={state}
         data-mode={typeof b.mode === 'string' ? b.mode : undefined}>
      {offered.length > 0 ? (
        <span className="cm-phase-sub" role="group" aria-label="Order the board"
              data-testid="cm-hb-sorts">
          {offered.map((o) => {
            const key = String(o.key);
            const on = pressed === key;
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
      {levLine ? <p className="cm-note cm-dim" data-testid="cm-hb-levered">{levLine}</p> : null}
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
      {onView && views.length > 0 ? (
        <span className="cm-phase-sub" role="group" aria-label="Table view" data-testid="cm-hb-views">
          {views.map((v) => (
            <button key={v.key} type="button" aria-pressed={shown === v.key}
                    data-testid={`cm-hb-view-${v.key}`}
                    className={`cm-phase-btn${shown === v.key ? ' cm-phase-on' : ''}`}
                    onClick={() => onView(v.key)}>
              {String(v.label)}
            </button>
          ))}
        </span>
      ) : null}
      {fundLine ? <p className="cm-note cm-dim" data-testid="cm-hb-fund">{fundLine}</p> : null}
      {fundNote ? <p className="cm-note cm-dim" data-testid="cm-hb-fund-note">{fundNote}</p> : null}
      {table ? (
        <HighBetaTable board={b} table={table} rows={rows} greenOn={greenOn} legend={levLegend}
                       view={shown} onHeaderSort={onHeaderSort} />
      ) : null}
    </div>
  );
}

export { HighBetaBoardNote };
