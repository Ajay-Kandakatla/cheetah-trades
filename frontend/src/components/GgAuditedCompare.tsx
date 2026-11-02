/* 🧪 GgAuditedCompare — the 🏁 side by side on the 🧪 Gajjala · Audited tab: the audited A+ against 🚩 Gajjala's
 * original A+ on the same sessions, graded by the same trade math.
 *
 * Ajay, the day the tab was asked for: "I would like you to create a new tab for Gajjals when you modifiy with audit of
 * End of day.." "Gajjals-Audited" "So we can keep track of improvements on this tab".
 *
 * Draws the SERVED `audited_compare` block (backend chart_maps/gajjala/audited_tab.compare_block): the served title, a
 * table of the served `sides`, the served held line and its rows, the served reconciliation line, the 🧪 Rule by rule
 * table (served `per_rule_title` above, ONE row per served `per_rule` row printing `label`, `with.text`, `other.text`
 * and `delta_text` verbatim, the served `by_rule_note` below), the per-day rows, the served honesty and the served
 * UNMEASURED line.
 *
 * Ajay 2026-11-01: "Yes make the changes in audited please" and "But keep a track record too to see the winners and
 * loster" — the per-rule table REPLACES the held-only `by_rule` table (a legacy `by_rule` key renders nothing).
 * `fired_alone` / `tie_held` are already inside the served `other.text` and are never recomposed here. NO arithmetic — every number is printed as served; the column heads are structural words.
 * `floor_reached` is a COUNT flag and is NEVER printed as a verdict: the words are the served `unmeasured_text`.
 * An absent block renders nothing. Shadow only. UNMEASURED.
 */
import type {
  GgAuditedCompare as GgAuditedCompareBlock, GgAuditedPerRuleRow, GgAuditedPerRuleSide, GgAuditedSide, GgAuditedTally,
} from '../lib/gajjala';
import '../styles/ggAudited.css';

const said = (v: unknown): v is string => typeof v === 'string' && v.trim() !== '';
/** A served number as served — never rounded, summed or derived here. */
const num = (v: unknown): string => (typeof v === 'number' && Number.isFinite(v) ? String(v) : '—');
const tally = (t: GgAuditedTally | null | undefined): string =>
  t ? `${num(t.n)} · ${num(t.win)} W · ${num(t.loss)} L` : '—';
/** A per-rule side prints ONLY its served sentence (it opens with the served side label) — no number composed here. */
const sideText = (s: GgAuditedPerRuleSide | null | undefined): string | null =>
  s && typeof s === 'object' && said(s.text) ? s.text : null;

export function GgAuditedCompare({ block }: { block?: GgAuditedCompareBlock | null }) {
  if (!block || typeof block !== 'object') return null;
  const sides = (Array.isArray(block.sides) ? block.sides : []).filter((s): s is GgAuditedSide => !!s && said(s.key));
  const held = block.held && typeof block.held === 'object' ? block.held : null;
  const heldRows = (Array.isArray(held?.rows) ? held!.rows! : []).filter((r) => !!r && said(r.symbol));
  const perRule = (Array.isArray(block.per_rule) ? block.per_rule : [])
    .filter((r): r is GgAuditedPerRuleRow => !!r && typeof r === 'object' && said(r.key));
  const byDay = (Array.isArray(block.by_day) ? block.by_day : []).filter((r) => !!r && said(r.date));
  const sideLabel = (k: string): string => {
    const s = sides.find((x) => x.key === k);
    return s && said(s.label) ? s.label : k;
  };
  return (
    <section className="gg-audited-compare" data-testid="gg-audited-compare">
      {said(block.title) ? <div className="gg-audited-compare-title" data-testid="gg-audited-compare-title"><strong>{block.title}</strong></div> : null}
      {sides.length ? (
        <table className="gg-audited-table" data-testid="gg-audited-sides">
          <thead>
            <tr><th></th><th>n</th><th>filled</th><th>W</th><th>L</th><th>open / flat</th><th>unfilled</th><th>mean R</th><th>win %</th><th></th></tr>
          </thead>
          <tbody>
            {sides.map((s) => (
              <tr key={s.key} data-testid={`gg-audited-side-${s.key}`}>
                <th scope="row">{said(s.label) ? s.label : s.key}</th>
                <td>{num(s.n)}</td><td>{num(s.filled)}</td><td>{num(s.win)}</td><td>{num(s.loss)}</td>
                <td>{num(s.open_flat)}</td><td>{num(s.unfilled)}</td><td>{num(s.mean_r)}</td><td>{num(s.win_pct)}</td>
                <td className="gg-muted">{said(s.text) ? s.text : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {held ? (
        <div className="gg-audited-held-line" data-testid="gg-audited-compare-held">
          {said(held.text) ? <span>{held.text}</span> : null}
          {heldRows.length ? (
            <ul className="gg-held-rows">
              {heldRows.map((r) => (
                <li key={`${r.date}-${r.symbol}-${r.setup}`} data-testid={`gg-audited-compare-held-${r.symbol}-${r.setup}`}>
                  {said(r.text) ? r.text : said(r.outcome_text) ? r.outcome_text : r.symbol}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {block.recon && said(block.recon.text) ? (
        <div className="gg-muted" data-testid="gg-audited-recon">{block.recon.text}</div>
      ) : null}
      {perRule.length ? (
        <>
          {said(block.per_rule_title) ? (
            <div className="gg-audited-compare-title" data-testid="gg-audited-per-rule-title"><strong>{block.per_rule_title}</strong></div>
          ) : null}
          <table className="gg-audited-table gg-audited-per-rule" data-testid="gg-audited-per-rule">
            <thead><tr><th>rule</th><th>with the rule</th><th>held / GG's math</th><th>what changed</th></tr></thead>
            <tbody>
              {perRule.map((r) => (
                <tr key={r.key} data-testid={`gg-audited-per-rule-${r.key}`}>
                  <th scope="row">{said(r.label) ? r.label : r.key}</th>
                  <td>{sideText(r.with)}</td>
                  <td>{sideText(r.other)}</td>
                  <td className="gg-muted">{said(r.delta_text) ? r.delta_text : null}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
      {said(block.by_rule_note) ? <div className="gg-muted" data-testid="gg-audited-by-rule-note">{block.by_rule_note}</div> : null}
      {byDay.length ? (
        <table className="gg-audited-table" data-testid="gg-audited-by-day">
          <thead><tr><th>day</th><th>{sideLabel('original')}</th><th>{sideLabel('audited')}</th><th>held</th><th></th></tr></thead>
          <tbody>
            {byDay.map((d) => (
              <tr key={d.date} data-testid={`gg-audited-by-day-${d.date}`}>
                <th scope="row">{said(d.label) ? d.label : d.date}</th>
                <td>{tally(d.original)}</td><td>{tally(d.audited)}</td><td>{tally(d.held)}</td>
                <td className="gg-muted">{said(d.text) ? d.text : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {said(block.honesty) ? <div className="gg-muted" data-testid="gg-audited-compare-honesty">{block.honesty}</div> : null}
      {said(block.unmeasured_text) ? (
        <div className="gg-audited-unmeasured" data-testid="gg-audited-compare-unmeasured">{block.unmeasured_text}</div>
      ) : null}
    </section>
  );
}

export default GgAuditedCompare;
