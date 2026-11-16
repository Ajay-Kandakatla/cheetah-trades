/* 📋 All strategies — the ONE table of every card on GG's five setups (2026-11-13, spec §3.5).
 * Ajay 2026-11-13: "Hey can you build be a table like track record on Gajjals landing page.. Call all strategies. I want
 * this table to rank based how gajjals sees them.. He watches 18 stocks simultaneously I am unable to see that view with
 * car and tab lay out I will use this table format but I need tha track record like graph thoouhg"
 *
 * Everything on it is SERVED by backend chart_maps/gajjala/all_table.block: the title, the order line, the heads (in served
 * order), one row per served row in the SERVED rank order (the FE never sorts), each row's tier / category / plan / volume
 * / float words, the preset lite spark (GgEntryMiniTape with `data` — zero per-row fetches), the "GG's 18" divider words,
 * the more / fault / empty / honesty lines. The price cell prints a SERVED string only: the route's `live_price_text`, else
 * the pass's `price_text` — no formatter, no arithmetic (the live poll's `now.label` is the word "now" / "now · pre" /
 * "now · AH", never a price — board.now_label — so it never reaches the cell). This file types no head,
 * tier or tape word and imports nothing from GajjalaBoard (the `ptt__mini-cell` and list-table pins live there; the 🚫
 * chip is GgTraderChip's servedChip — the identical span to the board's GgBrokerChip, contracts 9300-9318).
 * Display order only — no gate, count or alert changes; UNMEASURED.
 *
 * 2026-11-16 — Ajay: "Can you sort the table of all strategies by nearest to A+ support and then nearest to the EMA.
 * please" + "Add those columns to the Table and a Add to watch button". The server serves TWO orders — `rank` (GG's) and
 * `near_rank` (nearest the trigger, then nearest the 9 EMA, 🚫 last) — and the sort words; the toggle only picks which
 * SERVED rank lays the rows out (remembered in this browser, `gg-all-sort`). "GG's 18" is GG's order's divider, so it
 * shows under GG's order only. The served "To 9 EMA" cell; ➕/➖ Watch (the ONE GgWatchButton, owner only) by the ticker.
 *
 * 2026-11-16 — Ajay (screenshot of this table): "Add a short interest colume fo this table when available". The served
 * `si` head (label "Short interest", hover = the served si_head_title) prints the row's served si_text (the house 🩳 chip
 * verbatim) with the served si_title on hover; no record → an EMPTY cell (never 0, never a dash). The stale hook is a
 * class only — the served text carries the word. The served si_fault_text prints under the fault line. DISPLAY ONLY. */
import { Fragment, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { GgEntryMiniTape } from './GgEntryTape';
import { GgTraderChip, servedChip } from './GgTraderChip';
import { GgNewMark } from './GgEntryMarks';
import { ggHref, type GgTableBlock, type GgTableRow } from '../lib/gajjala';
import type { CardLiveAnswer } from '../lib/cardLive';
import { withSource } from '../lib/navSource';
import { GgWatchButton } from './GgWatchButton';

export const GG_ALL_SORT_KEY = 'gg-all-sort';
function readSort(): string | null {
  try { return window.localStorage.getItem(GG_ALL_SORT_KEY); } catch { return null; }
}
function saveSort(k: string): void {
  try { window.localStorage.setItem(GG_ALL_SORT_KEY, k); } catch { /* private window: the pick lasts this visit */ }
}

/** A served string, or null — null / "" / a non-string prints nothing. */
const str = (x: unknown): string | null => (typeof x === 'string' && x.trim() ? x : null);

/** The price cell's ONE served string: the route's live text, else the pass's text. The live poll's `now.label` is the
 * word "now" / "now · pre" / "now · AH" (backend board.now_label), never a price, so the answer is NOT read here. */
export function ggAllPriceText(row: GgTableRow, _answer?: CardLiveAnswer | null): string | null {
  return str(row.live_price_text) ?? str(row.price_text);
}

/** The id stem every per-row test id carries — a name on two setups is two rows. */
const rid = (r: GgTableRow) => `${r.symbol}-${r.setup}`;

function SymCell({ row, search, back }: { row: GgTableRow; search: string; back: string }) {
  const href = ggHref(row.href);
  const tierLabel = str(row.tier_label);
  return (
    <td className="gg-all-sym">
      {href ? (
        <Link to={withSource(href, 'chart-maps', search)} state={{ from: back, label: 'Chart Maps' }}
              data-testid={`gg-all-link-${rid(row)}`}><strong>{row.symbol}</strong></Link>
      ) : <strong data-testid={`gg-all-sym-${rid(row)}`}>{row.symbol}</strong>}
      {row.entry_plan === true ? (
        <span className="gg-all-entry" data-testid={`gg-all-entry-${rid(row)}`} role="img"
              aria-label={tierLabel ?? undefined} title={tierLabel ?? undefined}>{'\u{1F7E2}'}</span>
      ) : null}
      {servedChip(row.broker_text, 'gg-broker', `gg-broker-all-${rid(row)}`)}
      <GgTraderChip text={row.trader_text} testid={`gg-trader-all-${rid(row)}`}
                    promoText={row.promo_text} promoTestid={`gg-promo-all-${rid(row)}`} />
      <GgNewMark mark={row.new_mark} sym={`all-${rid(row)}`} />
      <GgWatchButton symbol={row.symbol} />
    </td>
  );
}

function SparkCell({ row }: { row: GgTableRow }) {
  const spark = row.spark && typeof row.spark === 'object' ? row.spark : null;
  if (!spark) return <td className="ptt__mini-cell" />;
  const mini = <GgEntryMiniTape id={str(spark.id) ?? rid(row)} data={spark} width={100} />;
  const href = ggHref(row.card_href);
  return (
    <td className="ptt__mini-cell">
      {href ? <Link to={href} data-testid={`gg-all-card-${rid(row)}`}>{mini}</Link> : mini}
    </td>
  );
}

/** One cell per served head key (the 🏁 `default:` rule — an unknown key is an empty cell). */
function cellOf(key: string, row: GgTableRow, answer: CardLiveAnswer | null | undefined, search: string, back: string,
                near = false): ReactNode {
  const small = (x: unknown, tid?: string) => (str(x) ? <small data-testid={tid}>{x as string}</small> : null);
  switch (key) {
    case 'rank':
      return (
        <td key={key} className="gg-all-rank">
          {near ? (typeof row.near_rank === 'number' ? row.near_rank : null) : (typeof row.rank === 'number' ? row.rank : null)}
        </td>
      );
    case 'symbol':
      return <SymCell key={key} row={row} search={search} back={back} />;
    case 'spark':
      return <SparkCell key={key} row={row} />;
    case 'category':
      return (
        <td key={key} className="gg-all-cat gg-tr-cell">
          {str(row.category_text)}
          {small(row.tier_label, `gg-all-tier-${rid(row)}`)}
          {small(row.vol_dried, `gg-all-dried-${rid(row)}`)}
        </td>
      );
    case 'price':
      return (
        <td key={key} className="gg-tr-cell" data-testid={`gg-all-price-${rid(row)}`}>
          <span data-testid={`gg-all-px-${rid(row)}`}>{ggAllPriceText(row, answer)}</span>
          {small(row.change_text)}
        </td>
      );
    case 'plan':
      return <td key={key} className="gg-all-plan">{str(row.plan_text)}</td>;
    case 'dist':
      return <td key={key}>{str(row.dist_text)}</td>;
    case 'ema9':
      return (
        <td key={key} className="gg-tr-cell" title={str(row.ema9_title) ?? undefined} data-testid={`gg-all-ema9-${rid(row)}`}>
          {str(row.ema9_gap_text)}{small(row.ema9_text)}
        </td>
      );
    case 'volume':
      return <td key={key} className="gg-tr-cell">{str(row.volume_text)}{small(row.rvol_text)}</td>;
    case 'float':
      return <td key={key}>{str(row.float_text)}</td>;
    case 'si':
      return (
        <td key={key} className={`gg-all-si${row.si_stale === true ? ' gg-all-si-stale' : ''}`}
            title={str(row.si_title) ?? undefined} data-testid={`gg-all-si-${rid(row)}`}>
          {str(row.si_text)}
        </td>
      );
    default:
      return <td key={key} />;
  }
}

function rowClass(row: GgTableRow): string {
  const cls = [`gg-all-tier-${row.tier}`];
  if (str(row.broker_text)) cls.push('gg-all-broker');
  if (row.in_watch === true) cls.push('gg-all-watch');
  return cls.join(' ');
}

export function GgAllTable({ block, emptyNote, answer, search, back }: {
  block: GgTableBlock | null | undefined; emptyNote?: string | null; answer?: CardLiveAnswer | null;
  search: string; back: string;
}) {
  const [picked, setPicked] = useState<string | null>(readSort);   // before any early return (rules of hooks)
  /* An older API / a faulted build: no block → the served empty_note only. */
  if (!block || typeof block !== 'object') {
    return str(emptyNote) ? <div className="cm-note" data-testid="gg-empty">{emptyNote}</div> : null;
  }
  const heads = (Array.isArray(block.heads) ? block.heads : [])
    .filter((h) => h && typeof h.key === 'string' && h.key && typeof h.label === 'string');
  const rows = (Array.isArray(block.rows) ? block.rows : [])
    .filter((r) => r && typeof r === 'object' && typeof r.symbol === 'string' && r.symbol && typeof r.setup === 'string');
  const tapeHead = str(block.tape_head);
  /* The served sort options; a stored pick the server no longer serves → the served default. */
  const opts = (Array.isArray(block.sorts?.options) ? block.sorts!.options! : [])
    .filter((o) => o && typeof o.key === 'string' && typeof o.label === 'string');
  const def = str(block.sorts?.default) ?? 'gg';
  const sortKey = picked && opts.some((o) => o.key === picked) ? picked : def;
  const near = sortKey === 'near' && rows.every((r) => typeof r.near_rank === 'number');
  const shown = near ? [...rows].sort((a, b) => (a.near_rank as number) - (b.near_rank as number)) : rows;
  const orderText = near ? str(block.sorts?.near_text) : str(block.order_text);
  const pick = (k: string) => { setPicked(k); saveSort(k); };
  const watchText = str(block.watch?.text);
  /* The divider goes after the LAST served in_watch row, only when a later row exists. */
  let lastWatch = -1;
  rows.forEach((r, i) => { if (r.in_watch === true) lastWatch = i; });
  const divideAt = !near && lastWatch >= 0 && lastWatch < rows.length - 1 ? lastWatch : -1;
  return (
    <section className="gg-all" data-testid="gg-all">
      {str(block.title) ? <h3 className="gg-all-title" data-testid="gg-all-title">{block.title}</h3> : null}
      {opts.length > 1 && rows.length > 1 ? (
        <div className="gg-all-sorts" role="group" aria-label="Sort" data-testid="gg-all-sorts">
          {opts.map((o) => (
            <button key={o.key} type="button" className={`cm-tv gg-all-sort${o.key === sortKey ? ' is-on' : ''}`}
                    aria-pressed={o.key === sortKey} data-testid={`gg-all-sort-${o.key}`} onClick={() => pick(o.key)}>
              {o.label}
            </button>
          ))}
        </div>
      ) : null}
      {orderText ? <div className="gg-muted gg-all-order" data-testid="gg-all-order">{orderText}</div> : null}
      {rows.length && heads.length ? (
        <div className="gg-tr-scroll">
          <table className="gg-tr-table gg-all-table" data-testid="gg-all-table">
            <thead>
              <tr>{heads.map((h) => (
                <th key={h.key} title={h.key === 'si' ? (str(block.si_head_title) ?? undefined) : undefined}>
                  {h.key === 'spark' && tapeHead ? tapeHead : h.label}
                </th>
              ))}</tr>
            </thead>
            <tbody>
              {shown.map((r, i) => (
                <Fragment key={rid(r)}>
                  <tr data-testid={`gg-all-row-${rid(r)}`} className={rowClass(r)}>
                    {heads.map((h) => cellOf(h.key, r, answer, search, back, near))}
                  </tr>
                  {i === divideAt ? (
                    <tr className="gg-all-divider" data-testid="gg-all-divider">
                      <td colSpan={heads.length}>{watchText}</td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {str(block.more_text) ? <div className="gg-muted" data-testid="gg-all-more">{block.more_text}</div> : null}
      {str(block.fault_text) ? <div className="cm-note cm-note-err" data-testid="gg-all-fault">{block.fault_text}</div> : null}
      {str(block.si_fault_text) ? <div className="cm-note cm-note-err" data-testid="gg-all-si-fault">{block.si_fault_text}</div> : null}
      {!rows.length && str(block.empty_text) ? <div className="cm-note" data-testid="gg-all-empty">{block.empty_text}</div> : null}
      {str(block.honesty) ? <div className="gg-muted" data-testid="gg-all-honesty">{block.honesty}</div> : null}
    </section>
  );
}

export default GgAllTable;
