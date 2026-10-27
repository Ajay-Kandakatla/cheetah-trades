import { useState, type ReactElement } from 'react';
import type { GgTrAplus, GgTrApCell, GgTrApChart, GgTrApGroup, GgTrApItem } from '../lib/gajjala';

/* 🎯 A+ wins vs losses on Gajjala's 🏁 Track record (2026-10-26, BUILD_SPEC25 §3.6 + AMENDMENT A1).
 *
 * Ajay: "Once done can you give me a  A+ filter in the track record I wanna see how many of the A+ were successful draw
 * some charts to show the winning vs losing percentages of A+ trades please" — then "I need these charts on Track Record
 * page" (A1: the block sits on the list view always, whenever `tr.aplus` is served).
 *
 * GEOMETRY ONLY. Every title, label, count, percent and sentence is SERVED by ledger.aplus_block (the house rule: the FE
 * types no served word or number). This file draws rect sizes from the served integers `n` / `total` and nothing else;
 * the labels are HTML (they wrap at 430 px), never SVG text. The horizon toggle is local state (never the URL, never a
 * fetch). UNMEASURED — a ledger graded by GG's trade math, not a backtest; the 2026-10-14 study read no edge. */

/** The viewBox of one horizontal bar, and of one by-day column (the SVG stretches to its CSS box). */
export const AP_VB_W = 100;
export const AP_BAR_H = 8;
export const AP_COL_W = 10;
export const AP_COL_H = 60;

export type ApSegment = { key: string; x: number; w: number };

/* The typeof names come from typeof of a value, so this file carries no word literal (the house rule for a served surface). */
const NUM = typeof 0;
const STR = typeof '';
const OBJ = typeof {};
const fin = (v: unknown): v is number => typeof v === NUM && Number.isFinite(v);
const has = (v: unknown): v is string => typeof v === STR && (v as string).trim().length > 0;
const isKey = (v: unknown): v is string => typeof v === STR;
const vb = (w: number, h: number) => [0, 0, w, h].join(' ');

/** The stacked segments of one served cell: one per item with a finite n above zero, in the served order; its width =
 *  n / scale of `length`, x cumulative. A scale that is not a finite number above zero → no segment (never a throw). */
export function apSegments(items: ReadonlyArray<GgTrApItem> | null | undefined, scale: number, length: number): ApSegment[] {
  if (!fin(scale) || scale <= 0 || !fin(length) || length <= 0) return [];
  const out: ApSegment[] = [];
  let x = 0;
  for (const it of items || []) {
    if (!it || !fin(it.n) || it.n <= 0) continue;
    const w = (it.n / scale) * length;
    out.push({ key: String(it.key), x, w });
    x += w;
  }
  return out;
}

const itemsOf = (c: GgTrApCell | null | undefined): GgTrApItem[] =>
  (Array.isArray(c?.items) ? c!.items : []).filter((i) => !!i && isKey(i.key));
const textOf = (items: GgTrApItem[], key: string) => items.find((i) => i.key === key)?.text;
const isCell = (v: unknown): v is GgTrApCell => !!v && typeof v === OBJ && Array.isArray((v as GgTrApCell).items);
/** A group's served cell for the picked horizon key (a served key — never a typed one); none → null. */
function cellOf(g: GgTrApGroup | null | undefined, h: string): GgTrApCell | null {
  const v = g ? (g as unknown as Record<string, unknown>)[h] : null;
  return isCell(v) ? v : null;
}
/** The largest served `total` of the picked horizon — the one scale every bar of a chart shares. */
function maxTotal(groups: GgTrApGroup[], h: string): number {
  let m = 0;
  for (const g of groups) {
    const t = cellOf(g, h)?.total;
    if (fin(t) && t > m) m = t;
  }
  return m;
}

type ChartProps = { chart: GgTrApChart; h: string };

/** outcomes — per served bar: its served label + pct_text, one stacked bar scaled to ITS served total, a served legend. */
function ApOutcomes({ chart }: ChartProps) {
  const bars = (Array.isArray((chart as { bars?: unknown }).bars) ? (chart as { bars: (GgTrApCell & { key: string; label: string })[] }).bars : [])
    .filter((b) => isCell(b) && isKey(b.key));
  return (
    <>
      {bars.map((bar) => {
        const items = itemsOf(bar);
        return (
          <div key={bar.key} className="gg-ap-bar" data-testid={`gg-ap-bar-${bar.key}`}>
            <div className="gg-ap-head">
              {has(bar.label) ? <span className="gg-ap-label">{bar.label}</span> : null}
              {has(bar.pct_text) ? <span className="gg-muted" data-testid={`gg-ap-pct-${bar.key}`}>{bar.pct_text}</span> : null}
            </div>
            <svg className="gg-ap-svg" viewBox={vb(AP_VB_W, AP_BAR_H)} preserveAspectRatio="none" role="img"
                 aria-label={bar.text} data-testid={`gg-ap-svg-${bar.key}`}>
              {apSegments(items, bar.total, AP_VB_W).map((s) => (
                <rect key={s.key} className={`gg-ap-seg gg-ap-${s.key}`} x={s.x} y={0} width={s.w} height={AP_BAR_H}>
                  {has(textOf(items, s.key)) ? <title>{textOf(items, s.key)}</title> : null}
                </rect>
              ))}
            </svg>
            <div className="gg-ap-legend">
              {items.filter((i) => has(i.text)).map((i) => (
                <span key={i.key} className="gg-ap-key" data-testid={`gg-ap-legend-${bar.key}-${i.key}`}>
                  <i className={`gg-ap-sw gg-ap-${i.key}`} aria-hidden="true" />
                  {i.text}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </>
  );
}

/** by_setup — per served row: its served label, one bar scaled to the MAX served total of the picked horizon, its served text. */
function ApBySetup({ chart, h }: ChartProps) {
  const rows = (Array.isArray((chart as { rows?: unknown }).rows) ? (chart as { rows: GgTrApGroup[] }).rows : [])
    .filter((r) => !!r && isKey(r.key) && !!cellOf(r, h));
  const scale = maxTotal(rows, h);
  return (
    <>
      {rows.map((r) => {
        const c = cellOf(r, h)!;
        const items = itemsOf(c);
        return (
          <div key={r.key} className="gg-ap-row" data-testid={`gg-ap-row-${r.key}`}>
            {has(r.label) ? <span className="gg-ap-label">{r.label}</span> : <span />}
            <div className="gg-ap-rowbar">
              <svg className="gg-ap-svg" viewBox={vb(AP_VB_W, AP_BAR_H)} preserveAspectRatio="none" role="img"
                   aria-label={c.text} data-testid={`gg-ap-svg-${r.key}`}>
                {apSegments(items, scale, AP_VB_W).map((s) => (
                  <rect key={s.key} className={`gg-ap-seg gg-ap-${s.key}`} x={s.x} y={0} width={s.w} height={AP_BAR_H}>
                    {has(textOf(items, s.key)) ? <title>{textOf(items, s.key)}</title> : null}
                  </rect>
                ))}
              </svg>
              {has(c.text) ? <span className="gg-muted" data-testid={`gg-ap-text-${r.key}`}>{c.text}</span> : null}
            </div>
          </div>
        );
      })}
    </>
  );
}

/** by_day — inside the house scroll box, one column per served alert day (served order): a bar stacked from the bottom,
 *  scaled to the MAX served total of the picked horizon; the served label + short_text under it; the cell text as its title. */
function ApByDay({ chart, h }: ChartProps) {
  const cols = (Array.isArray((chart as { cols?: unknown }).cols) ? (chart as { cols: GgTrApGroup[] }).cols : [])
    .filter((c) => !!c && isKey(c.key) && !!cellOf(c, h));
  const scale = maxTotal(cols, h);
  return (
    <div className="gg-tr-scroll">
      <div className="gg-ap-cols">
        {cols.map((col) => {
          const c = cellOf(col, h)!;
          const items = itemsOf(c);
          return (
            <div key={col.key} className="gg-ap-col" data-testid={`gg-ap-col-${col.key}`}>
              <svg className="gg-ap-colsvg" viewBox={vb(AP_COL_W, AP_COL_H)} preserveAspectRatio="none" role="img"
                   aria-label={c.text} data-testid={`gg-ap-svg-${col.key}`}>
                {has(c.text) ? <title>{c.text}</title> : null}
                {apSegments(items, scale, AP_COL_H).map((s) => (
                  <rect key={s.key} className={`gg-ap-seg gg-ap-${s.key}`} x={0} y={AP_COL_H - s.x - s.w} width={AP_COL_W} height={s.w} />
                ))}
              </svg>
              {has(col.label) ? <span className="gg-ap-col-label">{col.label}</span> : null}
              {has(c.short_text) ? <span className="gg-muted">{c.short_text}</span> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** The served chart keys this file draws (ledger.APLUS_CHART_KEYS); `toggle` = the chart follows the horizon toggle.
 *  A served key not in here is skipped (never a guess at its shape). */
const DRAW: Record<string, { C: (p: ChartProps) => ReactElement; toggle: boolean }> = {
  outcomes: { C: ApOutcomes, toggle: false },
  by_setup: { C: ApBySetup, toggle: true },
  by_day: { C: ApByDay, toggle: true },
};
const drawOf = (key: unknown) => (isKey(key) && Object.prototype.hasOwnProperty.call(DRAW, key) ? DRAW[key] : null);

/** 🎯 the served A+ block: title, the served counts / split / replayed lines, the horizon toggle (only when a by-setup or
 *  by-day chart is served), the charts in the served order, the served more line, the served honesty folded LAST. The
 *  served `empty_text` (no A+ on the span) → the title + that one line only. A null block → nothing. */
export default function GajjalaAplusCharts({ block }: { block: GgTrAplus | null | undefined }) {
  const [picked, setPicked] = useState<string | null>(null);
  if (!block) return null;
  if (has(block.empty_text)) {
    return (
      <section className="gg-ap" data-testid="gg-ap">
        {has(block.title) ? <h4 className="gg-pb-h gg-ap-title" data-testid="gg-ap-title">{block.title}</h4> : null}
        <div className="cm-note" data-testid="gg-ap-empty">{block.empty_text}</div>
      </section>
    );
  }
  const horizons = (Array.isArray(block.horizons) ? block.horizons : [])
    .filter((x) => !!x && has(x.key) && has(x.label));
  const keys = horizons.map((x) => x.key);
  const h = picked && keys.includes(picked) ? picked
    : has(block.horizon_default) && keys.includes(block.horizon_default) ? block.horizon_default
      : keys[0] ?? block.horizon_default;
  const charts = (Array.isArray(block.charts) ? block.charts : []).filter((c) => !!c && !!drawOf(c.key));
  const toggle = horizons.length > 0 && charts.some((c) => drawOf(c.key)!.toggle);
  return (
    <section className="gg-ap" data-testid="gg-ap">
      {has(block.title) ? <h4 className="gg-pb-h gg-ap-title" data-testid="gg-ap-title">{block.title}</h4> : null}
      {has(block.counts_text?.same) ? <div className="cm-foot" data-testid="gg-ap-counts-same">{block.counts_text!.same}</div> : null}
      {has(block.counts_text?.next) ? <div className="cm-foot" data-testid="gg-ap-counts-next">{block.counts_text!.next}</div> : null}
      {has(block.split_text) ? <div className="gg-muted" data-testid="gg-ap-split">{block.split_text}</div> : null}
      {has(block.replayed_note) ? <div className="gg-muted" data-testid="gg-ap-replayed-note">{block.replayed_note}</div> : null}
      {toggle ? (
        <div className="cm-phase gg-ap-hs" role="tablist" data-testid="gg-ap-hs">
          {horizons.map((x) => (
            <button key={x.key} role="tab" aria-selected={x.key === h} data-testid={`gg-ap-h-${x.key}`}
                    className={`cm-phase-btn${x.key === h ? ' cm-phase-on' : ''}`}
                    onClick={() => setPicked(x.key)}>
              {x.label}
            </button>
          ))}
        </div>
      ) : null}
      {charts.map((c) => {
        const D = drawOf(c.key)!;
        return (
          <div key={c.key} className="gg-ap-chart" data-testid={`gg-ap-chart-${c.key}`}>
            {has(c.title) ? <div className="gg-ap-chart-title">{c.title}</div> : null}
            <D.C chart={c} h={h} />
          </div>
        );
      })}
      {has(block.more_text) ? <div className="gg-muted" data-testid="gg-ap-more">{block.more_text}</div> : null}
      {has(block.honesty) ? (
        <details className="gg-aplus-note gg-ap-honesty" data-testid="gg-ap-honesty"><summary>ⓘ</summary>{block.honesty}</details>
      ) : null}
    </section>
  );
}
