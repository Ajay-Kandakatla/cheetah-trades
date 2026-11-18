/* GgDivergence — 🧨 the Divergence record sub on 🚩 Gajjala's 5-min tab (2026-11-18, divergence spec §3.8).
 *
 * Ajay 2026-11-18: "Do we still capture divergence alerts? Can you add a tab for in in Gajjals 5 min please" and "yes
 * should do a track recird fir the divergence aftger EMA 9 Cross over bullish Cuz I am missing A+ i can chase the
 * divergency atleast like in these cases I would caught a good chunk of returns".
 *
 * Two pieces, both drawn from the SERVED block only (divergence_tab.block):
 *  - GgDivergencePanel — above the cards: the served title, his words, the two in-sample lines, the OOS / cohort / window
 *    / order lines, the listings that drew no card (served lines) and the served fault line, the served rule folded, the
 *    served honesty LAST.
 *  - GgDivergenceTrack — below the cards: the 🏁 fold on 🚩's exported GgTr* pieces (LukTrackRecord's shape): served span
 *    chips (?span= rides the GET), served category / sort chips (FE-only, no GET), the served RTH / after-hours count
 *    lines, the served OOS line (progress OR counts — whichever is served, as handed), one table per served day (no Tape
 *    column), the served more / empty / in-sample lines, the served rule folded, the served honesty LAST. A fold that
 *    could not be built prints the served fault line only.
 * A record, never a signal: no alert, no gate, no trade. This file types no word and no number; every string passes the
 * servedText guard (a NaN / undefined / non-string prints nothing). UNMEASURED. */
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import {
  GG_CAT_PARAM, GG_SORT_PARAM, GG_SPAN_PARAM, ggCatDays, ggCatOn, ggHref, ggSortRows, ggTrSort,
  type GgDivergenceBlock, type GgDivergenceTrack as GgDivergenceTrackBlock, type GgTrCell, type GgTrDay, type GgTrRow,
} from '../lib/gajjala';
import { GgTrCats, GgTrHead, GgTrSorts, GgTrTapeRow, ggTrTapeAt } from './GajjalaBoard';
import '../styles/gajjala.css';

/** The board's servedText guard (GajjalaBoard keeps its trailing export line fixed — the dedupe contract test): a served
 *  line prints only when it is a non-empty string — NaN / undefined / null / a number prints nothing. */
function servedText(v: unknown): v is string {
  return typeof v === 'string' && v.trim() !== '';
}

/** 🧨 the panel above the cards. A null / absent block (an older API, or a read fault — the board's served empty note
 *  says so) draws nothing. */
export function GgDivergencePanel({ block }: { block: GgDivergenceBlock | null | undefined }) {
  if (!block || typeof block !== 'object') return null;
  const rth = block.is_line?.rth?.text;
  const ah = block.is_line?.ah?.text;
  const chartless = (Array.isArray(block.chartless) ? block.chartless : [])
    .filter((c) => !!c && typeof c === 'object' && servedText(c.state_label));
  const showEmpty = block.n_today === 0 && !chartless.length && servedText(block.empty_text);
  return (
    <section className="gg-dv" data-testid="gg-dv">
      {servedText(block.title) ? <h3 className="gg-dv-title" data-testid="gg-dv-title">{block.title}</h3> : null}
      {servedText(block.ask_text) ? (
        <blockquote className="gg-dv-ask gg-muted" data-testid="gg-dv-ask">{block.ask_text}</blockquote>
      ) : null}
      {servedText(rth) ? <p className="gg-dv-line" data-testid="gg-dv-is-rth">{rth}</p> : null}
      {servedText(ah) ? <p className="gg-dv-line" data-testid="gg-dv-is-ah">{ah}</p> : null}
      {servedText(block.oos_text) ? <p className="gg-dv-line" data-testid="gg-dv-oos">{block.oos_text}</p> : null}
      {servedText(block.cohort_text) ? <p className="gg-dv-line gg-muted" data-testid="gg-dv-cohort">{block.cohort_text}</p> : null}
      {servedText(block.window_text) ? <p className="gg-dv-line gg-muted" data-testid="gg-dv-window">{block.window_text}</p> : null}
      {servedText(block.order_note) ? <p className="gg-dv-line gg-muted" data-testid="gg-dv-order">{block.order_note}</p> : null}
      {showEmpty ? <p className="gg-dv-line" data-testid="gg-dv-empty">{block.empty_text}</p> : null}
      {chartless.map((c, i) => {
        const href = ggHref(c.href);
        const key = servedText(c.symbol) ? c.symbol : String(i);
        return (
          <p key={`${key}-${i}`} className="gg-dv-line gg-dv-chartless" data-testid={`gg-dv-chartless-${key}`}>
            {href ? <Link to={href}>{c.state_label}</Link> : c.state_label}
          </p>
        );
      })}
      {servedText(block.faults_text) ? <p className="gg-dv-line cm-note" data-testid="gg-dv-faults">{block.faults_text}</p> : null}
      {servedText(block.rule_label) && servedText(block.rule_text) ? (
        <details className="gg-dv-rule" data-testid="gg-dv-rule">
          <summary>{block.rule_label}</summary>
          <p className="gg-dv-line">{block.rule_text}</p>
        </details>
      ) : null}
      {servedText(block.honesty) ? <p className="gg-dv-line gg-muted" data-testid="gg-dv-honesty">{block.honesty}</p> : null}
    </section>
  );
}

/** A served cell: an object with a string `text` (the board's trCellOf test, by typeof only). */
const isCell = (v: unknown): v is GgTrCell => !!v && typeof v === 'object' && typeof (v as GgTrCell).text === 'string';

/** A served head whose row value is not a cell but whose `<head>_text` is a served string (the 🧨 `window` / `ring`
 *  columns) — handed to TrRowCells' default branch as that served text, verbatim. Nothing composed. */
function dvRow(row: GgTrRow, heads: { key: string }[]): GgTrRow {
  const r = row as unknown as Record<string, unknown>;
  let out: Record<string, unknown> | null = null;
  for (const h of heads) {
    if (!h || typeof h.key !== 'string' || h.key === 'symbol' || isCell(r[h.key])) continue;
    const t = r[`${h.key}_text`];
    if (!servedText(t)) continue;
    out = out || { ...r };
    out[h.key] = { state: h.key, text: t };
  }
  return (out ?? r) as unknown as GgTrRow;
}

/** 🏁 the Divergence fold below the cards. `tr` null + a served fault line → that line only; neither → nothing. */
export function GgDivergenceTrack({ tr, faultText }: {
  tr: GgDivergenceTrackBlock | null | undefined; faultText?: string | null;
}) {
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  if (!tr || typeof tr !== 'object') {
    return servedText(faultText) ? <div className="cm-note gg-dv-line" data-testid="gg-dv-tr-fault">{faultText}</div> : null;
  }
  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value == null) next.delete(key); else next.set(key, value);
    setParams(next, { replace: true });
  };
  const spanHref = (key: string) => {
    const next = new URLSearchParams(location.search);
    next.set(GG_SPAN_PARAM, key);
    return `${location.pathname}?${next.toString()}`;
  };
  const cat = params.get(GG_CAT_PARAM);
  const sort = params.get(GG_SORT_PARAM);
  const spans = (Array.isArray(tr.spans) ? tr.spans : [])
    .filter((s) => !!s && servedText(s.key) && servedText(s.label));
  const heads = (Array.isArray(tr.heads) ? tr.heads : []).filter((h) => !!h && servedText(h.key) && typeof h.label === 'string');
  const cats = tr.categories ?? null;
  const sortItem = ggTrSort(sort, tr);
  const days: GgTrDay[] = (Array.isArray(tr.days) ? tr.days : [])
    .filter((d) => !!d && typeof d === 'object' && servedText(d.date))
    .map((d) => ({
      date: d.date, label: servedText(d.label) ? d.label : d.date,
      rows: (Array.isArray(d.rows) ? d.rows : []).filter((r) => !!r && typeof r === 'object').map((r) => dvRow(r, heads)),
    }));
  const listDays = ggCatDays(days, cat, cats);
  const shownDays = listDays.map((d) => ({ ...d, rows: ggSortRows(d.rows || [], sortItem, tr.bucket_order) }));
  const catEmpty = ggCatOn(cat, cats) && !listDays.length && days.some((d) => !!d.rows.length);
  const tapeAt = ggTrTapeAt(heads);
  const oosLine = servedText(tr.oos_progress_text) ? tr.oos_progress_text
    : servedText(tr.oos_counts_text) ? tr.oos_counts_text : null;
  const oosTid = servedText(tr.oos_progress_text) ? 'gg-dv-tr-oos-progress' : 'gg-dv-tr-oos-counts';
  const rth = tr.counts_text?.rth;
  const ah = tr.counts_text?.ah;
  return (
    <details open className="gg-track-record gg-dv gg-dv-tr" data-testid="gg-dv-tr">
      <summary className="gg-dv-tr-summary" data-testid="gg-dv-tr-title">{servedText(tr.title) ? tr.title : null}</summary>
      {spans.length ? (
        <div className="cm-phase gg-dv-spans" role="group" aria-label="span" data-testid="gg-dv-tr-spans">
          {spans.map((s) => (
            <Link key={s.key} to={spanHref(s.key)} replace
                  className={`cm-phase-btn${s.key === tr.span ? ' cm-phase-on' : ''}`}
                  aria-current={s.key === tr.span ? 'true' : undefined}
                  data-testid={`gg-dv-tr-span-${s.key}`}>{s.label}</Link>
          ))}
        </div>
      ) : null}
      <GgTrCats cats={cats} cat={cat} onCat={(k) => setParam(GG_CAT_PARAM, k === cats?.[0]?.key ? null : k)} />
      <GgTrSorts sorts={tr.sorts} on={sortItem}
                 onSort={(k) => setParam(GG_SORT_PARAM, k === tr.sort_default ? null : k)} />
      {servedText(rth) ? <p className="gg-dv-line" data-testid="gg-dv-tr-counts-rth">{rth}</p> : null}
      {servedText(ah) ? <p className="gg-dv-line" data-testid="gg-dv-tr-counts-ah">{ah}</p> : null}
      {oosLine ? <p className="gg-dv-line gg-muted" data-testid={oosTid}>{oosLine}</p> : null}
      {servedText(tr.today_text) ? <p className="gg-dv-line gg-muted" data-testid="gg-dv-tr-today">{tr.today_text}</p> : null}
      {catEmpty && servedText(tr.category_empty_text) ? (
        <div className="cm-note" data-testid="gg-dv-tr-cat-empty">{tr.category_empty_text}</div>
      ) : null}
      {shownDays.map((d) => (
        <div key={d.date} className="gg-tr-day">
          <h4 className="gg-dv-day" data-testid={`gg-dv-tr-day-${d.date}`}>{d.label}</h4>
          <div className="gg-tr-scroll">
            <table className="gg-tr-table gg-dv-tr-table">
              <GgTrHead heads={heads} views={null} at={tapeAt} />
              <tbody>
                {d.rows.map((r, i) => (
                  <GgTrTapeRow key={r.key ?? r.id ?? i} row={r} heads={heads} views={null} at={tapeAt} tid="gg-dv-tr" />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
      {servedText(tr.more_text) ? <p className="gg-dv-line gg-muted" data-testid="gg-dv-tr-more">{tr.more_text}</p> : null}
      {!days.length && servedText(tr.empty_text) ? (
        <p className="gg-dv-line gg-muted" data-testid="gg-dv-tr-empty">{tr.empty_text}</p>
      ) : null}
      {servedText(tr.is_text) ? <p className="gg-dv-line gg-muted" data-testid="gg-dv-tr-is">{tr.is_text}</p> : null}
      {servedText(tr.rule_text) ? (
        <details className="gg-dv-rule" data-testid="gg-dv-tr-rule">
          <summary>{servedText(tr.rule_label) ? tr.rule_label : 'ⓘ'}</summary>
          <p className="gg-dv-line">{tr.rule_text}</p>
        </details>
      ) : null}
      {servedText(tr.honesty) ? <p className="gg-dv-line gg-muted" data-testid="gg-dv-tr-honesty">{tr.honesty}</p> : null}
    </details>
  );
}
