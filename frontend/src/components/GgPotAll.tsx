/* 🧠 from every tab — the 🧠 Potential sub's list of every Gajjala sub's forming names the 🧠 cards do not show, plus the
 * setups whose 🧭 stages show a 🎯 A+ this session ("✅ broke HH:MM") (2026-11-24, potall spec §3.3, WP fe-potall).
 *
 * Ajay 2026-11-24: "I need a common place to see all the potnetials from all tabs" · "I mean all Gajjala's tabs".
 *
 * Everything is SERVED by backend chart_maps/gajjala/pot_all.block: one row per served row in the SERVED order (the FE
 * never sorts), the row's `text` verbatim, its ✅ / "listed · no 🧠 alert" / read-at chips, the 📌 / 🎪 / 🚫 tags, the
 * more / fault lines. A row links to its source card only when the server sent an href (ggHref-guarded); null / unsafe →
 * plain text. GgPotAll is the visible list (under the 🧠 cards, above 📈 Track); GgPotAllNotes carries the title, the
 * order, the rule and the as-of words and is mounted ONLY inside the 🧠 sub's ⓘ fold (no visible stamp — the board's own
 * gg-stale / gg-warming lines stay the visible ones). This file types no word. Display only — no rule, gate, count or
 * push changes; UNMEASURED. */
import { Link } from 'react-router-dom';
import { GgTraderChip, servedChip } from './GgTraderChip';
import { ggHref, type GgPotAllBlock, type GgPotAllRow } from '../lib/gajjala';
import { withSource } from '../lib/navSource';

/** The house servedText guard (copied per file): a non-empty string, else nothing prints. */
function servedText(v: unknown): v is string {
  return typeof v === 'string' && v.trim() !== '';
}

/** The served rows that can print: an object with a symbol, a setup and a served text. */
export function ggPotAllRows(block: GgPotAllBlock | null | undefined): GgPotAllRow[] {
  const rows = block && Array.isArray(block.rows) ? block.rows : [];
  return rows.filter((r): r is GgPotAllRow =>
    !!r && typeof r === 'object' && servedText(r.symbol) && servedText(r.setup) && servedText(r.text));
}

const rid = (r: GgPotAllRow) => `${r.symbol}-${r.setup}`;

function PotAllRow({ row, search, back }: { row: GgPotAllRow; search: string; back: string }) {
  const id = rid(row);
  const href = ggHref(row.href);
  return (
    <li className="gg-potall-row" data-testid={`gg-potall-row-${id}`} data-tier={servedText(row.tier) ? row.tier : undefined}
        title={servedText(row.state_label) ? row.state_label : undefined}>
      {href ? (
        <Link to={withSource(href, 'chart-maps', search)} state={{ from: back, label: 'Chart Maps' }}
              className="gg-potall-text" data-testid={`gg-potall-link-${id}`}>{row.text}</Link>
      ) : <span className="gg-potall-text" data-testid={`gg-potall-plain-${id}`}>{row.text}</span>}
      {servedText(row.broke_text) ? (
        <span className="cm-badge gg-potall-broke" data-testid={`gg-potall-broke-${id}`}>{row.broke_text}</span>
      ) : null}
      {servedText(row.alert_text) ? (
        <span className="gg-muted gg-potall-alert" data-testid={`gg-potall-alert-${id}`}>{row.alert_text}</span>
      ) : null}
      {servedText(row.read_at_text) ? (
        <span className="gg-muted gg-potall-readat" data-testid={`gg-potall-readat-${id}`}>{row.read_at_text}</span>
      ) : null}
      <GgTraderChip text={row.trader_text} testid={`gg-trader-potall-${id}`}
                    promoText={row.promo_text} promoTestid={`gg-promo-potall-${id}`} />
      {servedChip(row.broker_text, 'gg-broker', `gg-broker-potall-${id}`)}
    </li>
  );
}

/** The visible list: the served rows, then the served more / fault lines. Nothing when there is no row and no fault. */
export function GgPotAll({ block, search = '', back = '/chart-maps' }: {
  block: GgPotAllBlock | null | undefined; search?: string; back?: string;
}) {
  if (!block || typeof block !== 'object') return null;
  const rows = ggPotAllRows(block);
  const more = servedText(block.more_text) ? block.more_text : null;
  const fault = servedText(block.fault_text) ? block.fault_text : null;
  if (!rows.length && !fault) return null;
  return (
    <div className="gg-potall" data-testid="gg-potall-block">
      {rows.length ? (
        <ul className="gg-potall-rows" data-testid="gg-potall">
          {rows.map((r) => <PotAllRow key={rid(r)} row={r} search={search} back={back} />)}
        </ul>
      ) : null}
      {rows.length && more ? <div className="gg-muted gg-potall-more" data-testid="gg-potall-more">{more}</div> : null}
      {fault ? <div className="cm-note gg-potall-fault" data-testid="gg-potall-fault">{fault}</div> : null}
    </div>
  );
}

/** The served title / order / rule / as-of words — mounted ONLY inside the 🧠 sub's ⓘ fold body. */
export function GgPotAllNotes({ block }: { block: GgPotAllBlock | null | undefined }) {
  if (!block || typeof block !== 'object') return null;
  const title = servedText(block.title) ? block.title : null;
  const order = servedText(block.order_text) ? block.order_text : null;
  const rule = servedText(block.rule_text) ? block.rule_text : null;
  const asOf = servedText(block.as_of_text) ? block.as_of_text : null;
  if (!title && !order && !rule && !asOf) return null;
  return (
    <div className="gg-potall-notes" data-testid="gg-potall-notes">
      {title ? <strong className="gg-potall-title" data-testid="gg-potall-title">{title}</strong> : null}
      {order ? <span className="gg-muted" data-testid="gg-potall-order">{order}</span> : null}
      {rule ? <span className="gg-muted" data-testid="gg-potall-rule">{rule}</span> : null}
      {asOf ? <span className="gg-muted" data-testid="gg-potall-asof">{asOf}</span> : null}
    </div>
  );
}
