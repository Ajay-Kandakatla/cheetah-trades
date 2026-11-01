/* 🧪 GgAuditedHeld — the A+ reads 🚩 Gajjala's served that an ON audit rule held, on the 🧪 Gajjala · Audited tab.
 *
 * Ajay, the day the tab was asked for: "I would like you to create a new tab for Gajjals when you modifiy with audit of
 * End of day.." "Gajjals-Audited" "So we can keep track of improvements on this tab".
 *
 * A held A+ is LISTED, never hidden. Draws the SERVED `held` block (backend chart_maps/gajjala/audited_tab.held_block):
 * the served title, one row per served row — its served line (a link when the served href is an in-app path), its
 * served setup label, one chip per rule that held it (the served id; the served why as its title) and the served audit
 * line — else the served empty line; the served note folded. The FE filters no row by rule and composes no word or
 * number. An absent block renders nothing. Shadow only. UNMEASURED.
 */
import { Link } from 'react-router-dom';
import { ggHref, type GgHeldBlock, type GgHeldRow } from '../lib/gajjala';
import '../styles/ggAudited.css';

const said = (v: unknown): v is string => typeof v === 'string' && v.trim() !== '';

function HeldRow({ r }: { r: GgHeldRow }) {
  const id = `${r.symbol}-${r.setup}`;
  const href = ggHref(r.href);
  const by = (Array.isArray(r.held_by) ? r.held_by : []).filter((h) => !!h && said(h.id));
  return (
    <li className="gg-held-row" data-testid={`gg-held-row-${id}`}>
      {href
        ? <Link to={href} className="gg-held-line" data-testid={`gg-held-line-${id}`}>{r.text}</Link>
        : <span className="gg-held-line" data-testid={`gg-held-line-${id}`}>{r.text}</span>}
      {said(r.setup_label) ? <span className="gg-muted">{r.setup_label}</span> : null}
      {by.map((h) => (
        <span key={h.id} className="gg-held-rule" data-testid={`gg-held-rule-${id}-${h.id}`}
              title={said(h.why) ? h.why : undefined}>{h.id}</span>
      ))}
      {said(r.audit_text) ? <div className="gg-muted gg-held-audit" data-testid={`gg-held-audit-${id}`}>{r.audit_text}</div> : null}
    </li>
  );
}

export function GgAuditedHeld({ block }: { block?: GgHeldBlock | null }) {
  if (!block || typeof block !== 'object') return null;
  const rows = (Array.isArray(block.rows) ? block.rows : [])
    .filter((r): r is GgHeldRow => !!r && said(r.symbol) && said(r.text));
  return (
    <div className="gg-held" data-testid="gg-held" role="status">
      {said(block.title) ? <span className="gg-held-title" data-testid="gg-held-title">{block.title}</span> : null}
      {rows.length ? (
        <ul className="gg-held-rows">
          {rows.map((r) => <HeldRow key={`${r.symbol}-${r.setup}`} r={r} />)}
        </ul>
      ) : said(block.empty_text) ? <span className="gg-muted" data-testid="gg-held-empty">{block.empty_text}</span> : null}
      {said(block.note) ? (
        <details className="gg-aplus-note"><summary>ⓘ</summary><span data-testid="gg-held-note">{block.note}</span></details>
      ) : null}
    </div>
  );
}

export default GgAuditedHeld;
