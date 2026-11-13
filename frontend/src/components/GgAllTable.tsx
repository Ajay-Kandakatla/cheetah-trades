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
 * Display order only — no gate, count or alert changes; UNMEASURED. */
import { Fragment, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { GgEntryMiniTape } from './GgEntryTape';
import { GgTraderChip, servedChip } from './GgTraderChip';
import { GgNewMark } from './GgEntryMarks';
import { ggHref, type GgTableBlock, type GgTableRow } from '../lib/gajjala';
import type { CardLiveAnswer } from '../lib/cardLive';
import { withSource } from '../lib/navSource';

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
function cellOf(key: string, row: GgTableRow, answer: CardLiveAnswer | null | undefined, search: string, back: string): ReactNode {
  const small = (x: unknown, tid?: string) => (str(x) ? <small data-testid={tid}>{x as string}</small> : null);
  switch (key) {
    case 'rank':
      return <td key={key} className="gg-all-rank">{typeof row.rank === 'number' ? row.rank : null}</td>;
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
    case 'volume':
      return <td key={key} className="gg-tr-cell">{str(row.volume_text)}{small(row.rvol_text)}</td>;
    case 'float':
      return <td key={key}>{str(row.float_text)}</td>;
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
  /* An older API / a faulted build: no block → the served empty_note only. */
  if (!block || typeof block !== 'object') {
    return str(emptyNote) ? <div className="cm-note" data-testid="gg-empty">{emptyNote}</div> : null;
  }
  const heads = (Array.isArray(block.heads) ? block.heads : [])
    .filter((h) => h && typeof h.key === 'string' && h.key && typeof h.label === 'string');
  const rows = (Array.isArray(block.rows) ? block.rows : [])
    .filter((r) => r && typeof r === 'object' && typeof r.symbol === 'string' && r.symbol && typeof r.setup === 'string');
  const tapeHead = str(block.tape_head);
  const watchText = str(block.watch?.text);
  /* The divider goes after the LAST served in_watch row, only when a later row exists. */
  let lastWatch = -1;
  rows.forEach((r, i) => { if (r.in_watch === true) lastWatch = i; });
  const divideAt = lastWatch >= 0 && lastWatch < rows.length - 1 ? lastWatch : -1;
  return (
    <section className="gg-all" data-testid="gg-all">
      {str(block.title) ? <h3 className="gg-all-title" data-testid="gg-all-title">{block.title}</h3> : null}
      {str(block.order_text) ? <div className="gg-muted gg-all-order" data-testid="gg-all-order">{block.order_text}</div> : null}
      {rows.length && heads.length ? (
        <div className="gg-tr-scroll">
          <table className="gg-tr-table gg-all-table" data-testid="gg-all-table">
            <thead>
              <tr>{heads.map((h) => <th key={h.key}>{h.key === 'spark' && tapeHead ? tapeHead : h.label}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <Fragment key={rid(r)}>
                  <tr data-testid={`gg-all-row-${rid(r)}`} className={rowClass(r)}>
                    {heads.map((h) => cellOf(h.key, r, answer, search, back))}
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
      {!rows.length && str(block.empty_text) ? <div className="cm-note" data-testid="gg-all-empty">{block.empty_text}</div> : null}
      {str(block.honesty) ? <div className="gg-muted" data-testid="gg-all-honesty">{block.honesty}</div> : null}
    </section>
  );
}

export default GgAllTable;
