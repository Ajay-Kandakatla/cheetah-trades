/* 🏁 GgSiTrackSection — the 🩳 SI track record, inside the 🩳 High SI panel (2026-11-26, spec sitrack §3.7 B, WP fe-track,
 * [fixed: OC1]).
 *
 * Ajay 2026-11-26: "I want us to track these patters for future from SI like a track recprd with in SI stocks itself"
 *
 * Drawn from the SERVED block only (high_si.block → si_track, built by si_track.served_block). Mounted INSIDE GgHighSiPanel
 * right after the ⛔ new-SSR section, so on the 🚩 board it lives in the 🩳 sub's closed ⓘ fold (gg-sub-body) and nothing of
 * it is on the landing (his standing "no explanations on landing" rule). GgHighSiState does not draw it.
 *
 * Absent / not an object → nothing. A served `fault_text` → ONE error line, no fold, no table. Else ONE closed <details>
 * whose summary is the served `summary_text`; its body MOUNTS ONLY WHILE OPEN (a closed fold of many name-days costs no
 * DOM). Inside, in this order, each only when served: the title, the as-of, the base line, the first-listed-that-day line,
 * the empty line, the pattern table (the served heads, the "Shuffled" column among them, rows in the served order), the
 * where line, the day-shape lines, the day tables (ONE scroll box, the 🏁 width rule; inside a day the counted rows first,
 * then the rows first listed that day under the served `new_label` — never above it — then the rows served with group
 * "other" (on the list before the day but not graded, or no listing day on file) under the served `other_label`, never
 * under `new_label` [2026-11-26 refix]), the shown line, the pending line,
 * then a nested <details> for the served rule label → the rule text + the honesty paragraph.
 * This file types no word and formats no number: it never sorts, counts or fetches; `n` / `n_days` are never printed; every
 * string passes the servedText guard (a NaN / undefined / null / number / empty string prints nothing). A descriptive
 * ledger — never a gate, sort, push or lane input. UNMEASURED.
 *
 * 🏁 FOLLOW (2026-11-26, spec sishares §3.6, WP fe). Ajay: "lets track them in our list of SI. and maintain a track record
 * of our stocks". After the day tables, before the rule fold: ONE nested closed <details data-testid="gg-st-follow">
 * whose summary is the served follow `summary_text`; its body MOUNTS ONLY WHILE OPEN: the title, the caveat, the as-of,
 * the base lines, the empty line, the names table, the served pinned label + the pinned table (or the served
 * `pinned_empty_text`), the shown / pending lines, then a nested rule fold. Same guards as the rest of the file: every
 * string served, no number formatted, no sort, no fetch; a names / pinned row with no served symbol is dropped; a junk
 * href → plain text; `follow` absent / null / not an object → nothing. The day table needs no change (its +5 column
 * arrives as a served head + cell). */
import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  ggHref, type GgSiFollowBlock, type GgSiFollowName, type GgSiTrackBlock, type GgSiTrackDay, type GgSiTrackHead,
  type GgSiTrackPattern, type GgSiTrackRow, type GgSiTrackShape,
} from '../lib/gajjala';
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

function Piece({ v, className }: { v: unknown; className: string }) {
  return servedText(v) ? <span className={className}>{v}</span> : null;
}

/** The served-shape guard for a head list: `[key, label]` pairs of served strings, in the SERVED order. */
function headsOf(v: unknown): GgSiTrackHead[] {
  if (!Array.isArray(v)) return [];
  return v.filter((h): h is GgSiTrackHead => {
    if (!Array.isArray(h)) return false;
    const [k, label] = h;
    return servedText(k) && servedText(label);
  });
}

/** Which served pattern field a served pattern head key prints (the keys of `pattern_heads`); an unknown key reads the
 *  row's own field of that name. */
const PAT_FIELD: Record<string, keyof GgSiTrackPattern> = {
  label: 'label', with: 'with_text', without: 'without_text', diff: 'diff_text', shuffle: 'shuffle_text', word: 'word',
};

function patCell(p: GgSiTrackPattern, key: string): unknown {
  const f = PAT_FIELD[key];
  return f ? p[f] : (p as Record<string, unknown>)[key];
}

function Patterns({ heads, rows }: { heads: GgSiTrackHead[]; rows: GgSiTrackPattern[] }) {
  return (
    <div className="gg-tr-scroll gg-st-scroll" data-testid="gg-st-patterns-box">
      <table className="gg-tr-table gg-st-table" data-testid="gg-st-patterns">
        <thead>
          <tr>{heads.map(([k, label]) => <th key={k} data-testid={`gg-st-pat-head-${k}`}>{label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((p, i) => {
            const id = servedText(p.key) ? p.key : String(i);
            return (
              <tr key={`${id}-${i}`} data-testid={`gg-st-pat-${id}`} title={servedText(p.title) ? p.title : undefined}>
                {heads.map(([k], j) => {
                  const v = patCell(p, k);
                  return (
                    <td key={k} className="gg-tr-cell">
                      {servedText(v) ? v : null}
                      {j ? null : <Piece v={p.known_text} className="gg-st-known" />}
                      {j ? null : <Piece v={p.unknown_text} className="gg-st-unknown" />}
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

function Shape({ s, i }: { s: GgSiTrackShape; i: number }) {
  if (![s.label, s.win_text, s.rest_text].some(servedText)) return null;
  return (
    <p className="gg-dv-line gg-st-shape" data-testid={`gg-st-shape-${i}`}>
      <Piece v={s.label} className="gg-st-shape-label" />
      <Piece v={s.win_text} className="gg-st-shape-win" />
      <Piece v={s.rest_text} className="gg-st-shape-rest" />
    </p>
  );
}

/** The served-shape guard for a day's rows: the rows that carry a served symbol, in the SERVED order. */
function rowsOf(d: GgSiTrackDay): GgSiTrackRow[] {
  return Array.isArray(d.rows) ? d.rows.filter((r): r is GgSiTrackRow => isObj(r) && servedText(r.symbol)) : [];
}

function Row({ row, heads, day }: { row: GgSiTrackRow; heads: GgSiTrackHead[]; day: string }) {
  const sym = row.symbol as string;
  const href = ggHref(row.href);
  const cells = isObj(row.cells) ? row.cells : {};
  const chips = Array.isArray(row.chips) ? row.chips.filter(servedText) : [];
  const cls = [servedText(row.win) ? 'gg-tr-row-win' : '', row.counted === true ? '' : 'gg-st-new'].filter(Boolean).join(' ');
  return (
    <tr className={cls || undefined} data-testid={`gg-st-row-${day}-${sym}`} data-counted={row.counted === true}
        title={servedText(row.title) ? row.title : undefined}>
      {heads.map(([k], j) => {
        if (j) {
          const v = cells[k];
          return <td key={k} className="gg-tr-cell">{servedText(v) ? v : null}</td>;
        }
        return (
          <td key={k} className="gg-tr-cell gg-st-sym">
            {href ? <Link to={href}>{sym}</Link> : sym}
            <Piece v={row.win} className="gg-tr-flag gg-tr-flag-win" />
            {chips.map((c, ci) => <span key={`${c}-${ci}`} className="gg-tr-chip">{c}</span>)}
          </td>
        );
      })}
    </tr>
  );
}

function Day({ d, i, heads }: { d: GgSiTrackDay; i: number; heads: GgSiTrackHead[] }) {
  const rows = rowsOf(d);
  if (!rows.length) return null;
  const id = servedText(d.date) ? d.date : String(i);
  const counted = rows.filter((r) => r.counted === true);
  const other = rows.filter((r) => r.counted !== true && r.group === 'other');
  const fresh = rows.filter((r) => r.counted !== true && r.group !== 'other');
  return (
    <div className="gg-st-day" data-testid={`gg-st-day-${id}`}>
      <Line v={d.label} testid={`gg-st-day-label-${id}`} className="gg-dv-day" />
      <table className="gg-tr-table gg-st-table">
        <thead>
          <tr>{heads.map(([k, label]) => <th key={k}>{label}</th>)}</tr>
        </thead>
        <tbody>
          {counted.map((r, j) => <Row key={`${r.symbol}-${j}`} row={r} heads={heads} day={id} />)}
          {fresh.length && servedText(d.new_label) ? (
            <tr className="gg-st-newhead" data-testid={`gg-st-newlabel-${id}`}>
              <td colSpan={heads.length}>{d.new_label}</td>
            </tr>
          ) : null}
          {fresh.map((r, j) => <Row key={`${r.symbol}-${j}`} row={r} heads={heads} day={id} />)}
          {other.length && servedText(d.other_label) ? (
            <tr className="gg-st-newhead" data-testid={`gg-st-otherlabel-${id}`}>
              <td colSpan={heads.length}>{d.other_label}</td>
            </tr>
          ) : null}
          {other.map((r, j) => <Row key={`${r.symbol}-o${j}`} row={r} heads={heads} day={id} />)}
        </tbody>
      </table>
    </div>
  );
}

/** The served-shape guard for a follow table's rows: objects that carry a served symbol, in the SERVED order. */
function namesOf(v: unknown): GgSiFollowName[] {
  return Array.isArray(v) ? v.filter((r): r is GgSiFollowName => isObj(r) && servedText(r.symbol)) : [];
}

/** One follow table (names or pinned): the served heads; the first column the symbol (a link only through ggHref), every
 *  other column the served cell of that head key (a non-string / empty cell prints nothing). */
function FollowTable({ heads, rows, testid, rowid }: { heads: GgSiTrackHead[]; rows: GgSiFollowName[]; testid: string; rowid: string }) {
  return (
    <div className="gg-tr-scroll gg-st-scroll" data-testid={`${testid}-box`}>
      <table className="gg-tr-table gg-st-table" data-testid={testid}>
        <thead>
          <tr>{heads.map(([k, label]) => <th key={k}>{label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const sym = r.symbol as string;
            const href = ggHref(r.href);
            const cells = isObj(r.cells) ? r.cells : {};
            return (
              <tr key={`${sym}-${i}`} data-testid={`${rowid}-${sym}`}>
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

function FollowBody({ f }: { f: GgSiFollowBlock }) {
  const base = Array.isArray(f.base_lines) ? f.base_lines : [];
  const nHeads = headsOf(f.names_heads);
  const names = nHeads.length ? namesOf(f.names) : [];
  const pHeads = headsOf(f.pinned_heads);
  const pinned = pHeads.length ? namesOf(f.pinned) : [];
  return (
    <div className="gg-st-body gg-st-follow-body">
      <Line v={f.title} testid="gg-st-follow-title" className="gg-dv-line gg-st-title" />
      <Line v={f.caveat} testid="gg-st-follow-caveat" className="gg-dv-line" />
      <Line v={f.asof_text} testid="gg-st-follow-asof" />
      {base.map((l, i) => <Line key={String(i)} v={l} testid={`gg-st-follow-base-${i}`} className="gg-dv-line" />)}
      <Line v={f.empty_text} testid="gg-st-follow-empty" className="gg-dv-line" />
      {names.length ? <FollowTable heads={nHeads} rows={names} testid="gg-st-follow-names" rowid="gg-st-follow-name" /> : null}
      <Line v={f.pinned_label} testid="gg-st-follow-pinned-label" className="gg-dv-line gg-st-title" />
      {pinned.length
        ? <FollowTable heads={pHeads} rows={pinned} testid="gg-st-follow-pinned" rowid="gg-st-follow-pin" />
        : <Line v={f.pinned_empty_text} testid="gg-st-follow-pinned-empty" />}
      <Line v={f.shown_text} testid="gg-st-follow-shown" />
      <Line v={f.pending_text} testid="gg-st-follow-pending" />
      {servedText(f.rule_label) ? (
        <details className="gg-st-rule gg-tr-rule" data-testid="gg-st-follow-rule">
          <summary>{f.rule_label}</summary>
          <Line v={f.rule_text} testid="gg-st-follow-rule-text" className="gg-dv-line" />
        </details>
      ) : null}
    </div>
  );
}

/** The 🏁 follow fold: absent / null / not an object / no served summary → nothing; else ONE closed <details> whose body
 *  mounts only while open. */
function Follow({ f }: { f: unknown }) {
  const [open, setOpen] = useState(false);
  if (!isObj(f) || !servedText(f.summary_text)) return null;
  const block = f as GgSiFollowBlock;
  return (
    <details className="gg-st-follow" data-testid="gg-st-follow" open={open}
             onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary data-testid="gg-st-follow-summary">{block.summary_text}</summary>
      {open ? <FollowBody f={block} /> : null}
    </details>
  );
}

function Body({ b }: { b: GgSiTrackBlock }) {
  const patHeads = headsOf(b.pattern_heads);
  const patterns = Array.isArray(b.patterns) ? b.patterns.filter((p): p is GgSiTrackPattern => isObj(p)) : [];
  const shapes = Array.isArray(b.shape_rows) ? b.shape_rows.filter((s): s is GgSiTrackShape => isObj(s)) : [];
  const heads = headsOf(b.heads);
  const days = heads.length && Array.isArray(b.days) ? b.days.filter((d): d is GgSiTrackDay => isObj(d)) : [];
  const dayNodes: ReactNode[] = days.map((d, i) => <Day key={`${servedText(d.date) ? d.date : ''}-${i}`} d={d} i={i} heads={heads} />);
  const anyDay = days.some((d) => rowsOf(d).length);
  return (
    <div className="gg-st-body">
      <Line v={b.title} testid="gg-st-title" className="gg-dv-line gg-st-title" />
      <Line v={b.asof_text} testid="gg-st-asof" />
      <Line v={b.base_text} testid="gg-st-base" className="gg-dv-line" />
      <Line v={b.new_today_text} testid="gg-st-new-today" />
      <Line v={b.empty_text} testid="gg-st-empty" className="gg-dv-line" />
      {patHeads.length && patterns.length ? <Patterns heads={patHeads} rows={patterns} /> : null}
      <Line v={b.where_text} testid="gg-st-where" />
      {shapes.map((s, i) => <Shape key={String(i)} s={s} i={i} />)}
      {anyDay ? <div className="gg-tr-scroll gg-st-scroll" data-testid="gg-st-days">{dayNodes}</div> : null}
      <Line v={b.shown_text} testid="gg-st-shown" />
      <Line v={b.pending_text} testid="gg-st-pending" />
      <Follow f={b.follow} />
      {servedText(b.rule_label) ? (
        <details className="gg-st-rule gg-tr-rule" data-testid="gg-st-rule">
          <summary>{b.rule_label}</summary>
          <Line v={b.rule_text} testid="gg-st-rule-text" className="gg-dv-line" />
          <Line v={b.honesty} testid="gg-st-honesty" />
        </details>
      ) : null}
    </div>
  );
}

export function GgSiTrackSection({ block }: { block: GgSiTrackBlock | null | undefined }) {
  const [open, setOpen] = useState(false);
  if (!isObj(block)) return null;
  const b = block as GgSiTrackBlock;
  if (servedText(b.fault_text)) {
    return <p className="gg-dv-line cm-note cm-note-err" data-testid="gg-st-fault">{b.fault_text}</p>;
  }
  if (!servedText(b.summary_text)) return null;
  return (
    <details className="gg-st" data-testid="gg-st" open={open}
             onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary data-testid="gg-st-summary">{b.summary_text}</summary>
      {open ? <Body b={b} /> : null}
    </details>
  );
}
