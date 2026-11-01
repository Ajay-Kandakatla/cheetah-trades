/* 🧪 GgAuditedStrip — "What is different here" on the 🧪 Gajjala · Audited tab.
 *
 * Ajay, the day the tab was asked for: "I would like you to create a new tab for Gajjals when you modifiy with audit of
 * End of day.." "Gajjals-Audited" "So we can keep track of improvements on this tab".
 *
 * Draws the SERVED `audited` block (backend chart_maps/gajjala/audited_tab.audited_block) and nothing else: a <details>
 * FOLDED by default (Rule #5 — a dense surface), its summary the served title and pass line; the body one row per served
 * registry entry (id · rule · source · since · verdict · status · note), then the served lane-only, UNMEASURED and
 * process lines, the stale line when the overlay missed the latest pass, the unaudited line when served. The FE types no
 * rule, number or sentence of the audit and decides nothing — an absent block renders nothing. UNMEASURED.
 */
import type { GgAuditedBlock, GgAuditedRegistryRow } from '../lib/gajjala';
import '../styles/ggAudited.css';

const said = (v: unknown): v is string => typeof v === 'string' && v.trim() !== '';

function RuleRow({ r }: { r: GgAuditedRegistryRow }) {
  return (
    <li className={`gg-audited-rule gg-audited-rule-${r.status || 'unknown'}`} data-testid={`gg-audited-rule-${r.id}`}>
      <span className="gg-audited-rule-id" data-testid={`gg-audited-rule-id-${r.id}`}>{r.id}</span>
      {said(r.name) ? <span className="gg-audited-rule-name">{r.name}</span> : null}
      {said(r.status_text) ? <span className="gg-audited-rule-status" data-testid={`gg-audited-rule-status-${r.id}`}>{r.status_text}</span> : null}
      {said(r.rule) ? <div className="gg-audited-rule-text" data-testid={`gg-audited-rule-rule-${r.id}`}>{r.rule}</div> : null}
      {said(r.params_text) ? <div className="gg-muted" data-testid={`gg-audited-rule-params-${r.id}`}>{r.params_text}</div> : null}
      {said(r.source_text) ? <div className="gg-muted" data-testid={`gg-audited-rule-source-${r.id}`}>{r.source_text}</div> : null}
      {said(r.since) ? <span className="gg-muted" data-testid={`gg-audited-rule-since-${r.id}`}>{r.since}</span> : null}
      {said(r.verdict_text) ? <span className="gg-audited-rule-verdict" data-testid={`gg-audited-rule-verdict-${r.id}`}>{r.verdict_text}</span> : null}
      {said(r.changes_text) ? <div className="gg-muted" data-testid={`gg-audited-rule-changes-${r.id}`}>{r.changes_text}</div> : null}
      {said(r.note) ? <div className="gg-muted gg-audited-rule-note" data-testid={`gg-audited-rule-note-${r.id}`}>{r.note}</div> : null}
    </li>
  );
}

export function GgAuditedStrip({ block }: { block?: GgAuditedBlock | null }) {
  if (!block || typeof block !== 'object') return null;
  const rows = (Array.isArray(block.registry) ? block.registry : [])
    .filter((r): r is GgAuditedRegistryRow => !!r && said(r.id));
  const passText = block.pass && said(block.pass.text) ? block.pass.text : null;
  return (
    <details className="gg-audited-strip" data-testid="gg-audited-strip">
      <summary className="gg-audited-summary">
        {said(block.title) ? <strong data-testid="gg-audited-title">{block.title}</strong> : null}
        {passText ? <span className="gg-muted" data-testid="gg-audited-pass">{passText}</span> : null}
      </summary>
      {rows.length ? (
        <ul className="gg-audited-rules" data-testid="gg-audited-rules">
          {rows.map((r) => <RuleRow key={r.id} r={r} />)}
        </ul>
      ) : null}
      {said(block.lane_only_text) ? <div className="gg-muted" data-testid="gg-audited-lane-only">{block.lane_only_text}</div> : null}
      {said(block.unmeasured_text) ? <div className="gg-audited-unmeasured" data-testid="gg-audited-unmeasured">{block.unmeasured_text}</div> : null}
      {said(block.process_text) ? <div className="gg-muted" data-testid="gg-audited-process">{block.process_text}</div> : null}
      {block.stale === true && said(block.stale_text) ? (
        <div className="gg-audited-warn" data-testid="gg-audited-stale">{block.stale_text}</div>
      ) : null}
      {block.unaudited && said(block.unaudited.text) ? (
        <div className="gg-audited-warn" data-testid="gg-audited-unaudited">{block.unaudited.text}</div>
      ) : null}
    </details>
  );
}

export default GgAuditedStrip;
