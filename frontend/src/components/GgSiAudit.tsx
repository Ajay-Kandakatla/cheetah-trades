/* 🧮 GgSiAuditSection — the nightly float and share-count source audit, inside the 🩳 sub's panel (2026-11-26, spec
 * floatguard §3.9, WP fe).
 *
 * Ajay 2026-11-26 ~21:20 ET: "Also the Float share count issue and SI discrepancy happened too many times need to do
 * something about it".
 *
 * Drawn from the SERVED block only (high_si.block → si_audit, built by short_interest.source_audit.served_block). Mounted
 * INSIDE GgHighSiPanel right after the 🏁 section, on the SAME digit-free line, so on the 🚩 board it lives in the 🩳 sub's
 * closed ⓘ fold and nothing of it is on the landing. GgHighSiState does not draw it.
 *
 * Absent / not an object → nothing. A served `fault_text` → ONE error line, no fold, no table. No served `summary_text` →
 * nothing. Else ONE closed <details data-testid="gg-sa"> whose summary is the served summary; its body MOUNTS ONLY WHILE
 * OPEN: the title, the as-of, the empty line, the table (the served heads; the first column the row's symbol, a link only
 * through ggHref; every other column the served cell of that head key; `data-contested` on a row served contested,
 * `data-held` on a row served held), the shown line, then ONE nested closed <details> for the served rule label → the rule
 * text + the honesty paragraph.
 * This file types no word and formats no number: it never sorts, counts or fetches; `n` and the three counts are never
 * printed; every string passes the servedText guard (a NaN / undefined / null / number / empty string prints nothing); a row
 * with no served symbol is dropped. What two data providers say — never a gate, sort, push or lane input. UNMEASURED.
 * House classes only (gg-tr-* in gajjala.css, gg-st-* in ggSiTrack.css) — no CSS of its own. */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ggHref, type GgSiAuditBlock, type GgSiAuditRow, type GgSiTrackHead } from '../lib/gajjala';
import '../styles/gajjala.css';
import '../styles/ggSiTrack.css';

/** A served line prints only when it is a non-empty string — NaN / undefined / null / a number prints nothing. */
function servedText(v: unknown): v is string {
  return typeof v === 'string' && v.trim() !== '';
}

const isObj = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);

function Line({ v, testid, className = 'gg-dv-line gg-muted' }: { v: unknown; testid: string; className?: string }) {
  if (!servedText(v)) return null;
  return <p className={className} data-testid={testid}>{v}</p>;
}

/** The served-shape guard for the head list: `[key, label]` pairs of served strings, in the SERVED order. */
function headsOf(v: unknown): GgSiTrackHead[] {
  if (!Array.isArray(v)) return [];
  return v.filter((h): h is GgSiTrackHead => {
    if (!Array.isArray(h)) return false;
    const [k, label] = h;
    return servedText(k) && servedText(label);
  });
}

/** The served-shape guard for the rows: objects that carry a served symbol, in the SERVED order. */
function rowsOf(v: unknown): GgSiAuditRow[] {
  return Array.isArray(v) ? v.filter((r): r is GgSiAuditRow => isObj(r) && servedText(r.symbol)) : [];
}

function Table({ heads, rows }: { heads: GgSiTrackHead[]; rows: GgSiAuditRow[] }) {
  return (
    <div className="gg-tr-scroll gg-st-scroll" data-testid="gg-sa-box">
      <table className="gg-tr-table gg-st-table" data-testid="gg-sa-table">
        <thead>
          <tr>{heads.map(([k, label]) => <th key={k} data-testid={`gg-sa-head-${k}`}>{label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const sym = r.symbol as string;
            const href = ggHref(r.href);
            const cells = isObj(r.cells) ? r.cells : {};
            return (
              <tr key={`${sym}-${i}`} data-testid={`gg-sa-row-${sym}`}
                  data-contested={r.contested === true ? 'true' : undefined}
                  data-held={r.held === true ? 'true' : undefined}>
                {heads.map(([k], j) => {
                  if (j) {
                    const v = cells[k];
                    return <td key={k} className="gg-tr-cell">{servedText(v) ? v : null}</td>;
                  }
                  return <td key={k} className="gg-tr-cell gg-st-sym">{href ? <Link to={href}>{sym}</Link> : sym}</td>;
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Body({ b }: { b: GgSiAuditBlock }) {
  const heads = headsOf(b.heads);
  const rows = heads.length ? rowsOf(b.rows) : [];
  return (
    <div className="gg-st-body">
      <Line v={b.title} testid="gg-sa-title" className="gg-dv-line gg-st-title" />
      <Line v={b.asof_text} testid="gg-sa-asof" />
      <Line v={b.empty_text} testid="gg-sa-empty" className="gg-dv-line" />
      {rows.length ? <Table heads={heads} rows={rows} /> : null}
      <Line v={b.shown_text} testid="gg-sa-shown" />
      {servedText(b.rule_label) ? (
        <details className="gg-st-rule gg-tr-rule" data-testid="gg-sa-rule">
          <summary>{b.rule_label}</summary>
          <Line v={b.rule_text} testid="gg-sa-rule-text" className="gg-dv-line" />
          <Line v={b.honesty} testid="gg-sa-honesty" />
        </details>
      ) : null}
    </div>
  );
}

export function GgSiAuditSection({ block }: { block: GgSiAuditBlock | null | undefined }) {
  const [open, setOpen] = useState(false);
  if (!isObj(block)) return null;
  const b = block as GgSiAuditBlock;
  if (servedText(b.fault_text)) {
    return <p className="gg-dv-line cm-note cm-note-err" data-testid="gg-sa-fault">{b.fault_text}</p>;
  }
  if (!servedText(b.summary_text)) return null;
  return (
    <details className="gg-st" data-testid="gg-sa" open={open}
             onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary data-testid="gg-sa-summary">{b.summary_text}</summary>
      {open ? <Body b={b} /> : null}
    </details>
  );
}
