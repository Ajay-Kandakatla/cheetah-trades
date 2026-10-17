/* GgEntryTape — 🕰️ the Promo Circuit tape drawn for ONE Gajjala A+ entry (2026-10-16, DECISIONS11 D1, BUILD_SPEC11 §3.7).
 * Ajay: "We have a Promo Circuit tab in Catalyst tab. Can you use the graph component from  that to show what
 * happened to Entries alert of Gajjala with all the 100% criteria satisfier. One you alert it from the alert system
 * you built please"
 *
 * The same drawing as the Promo tape (TapeChart / TapeSpark — one engine): 5-minute closes, pre / post market shaded,
 * plus the entry's levels (trigger / stop / +1R) as horizontal lines, the alert (solid) and the fill (dashed) as
 * vertical rules, and dots where it filled and where it exited. EVERY word, number and percent on it is SERVED by
 * GET /chart-maps/gajjala/entry-tape (backend chart_maps/gajjala/tape.py — ENTRY_TAPE_WORDS, the ledger's own grade
 * texts); this file types none — only the glyphs for loading and for a failed read. UNMEASURED: a picture of what each
 * alert did, never a study (the 2026-10-14 study read no edge). */
import { useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { layout, miniLayout, TapeChart, TapeSpark, TAPE_W, TAPE_H, SPARK_H, TAPE_DASH, TAPE_DOT_R,
  type TapeMark, type TapeCorners } from './TapeChart';
import '../styles/gg_tape.css';

export const GG_TAPE_PATH = '/chart-maps/gajjala/entry-tape';

export type GgTapeBar = { t: number; o?: number | null; h?: number | null; l?: number | null; c: number; v?: number | null; s: string };
export type GgTapeLine = { key: string; px: number; tone: string; label: string };
export type GgTapeRule = { key: string; at: string; style: 'solid' | 'dashed' | string; tone: string; label: string };
export type GgTapeDot = { key: string; at: string; px: number; tone: string; label: string };
export type GgTapePayload = { id: string; ticker: string; tf: string; lite: boolean; bars: GgTapeBar[]; n_bars: number;
  hlines?: GgTapeLine[]; rules: GgTapeRule[]; dots?: GgTapeDot[]; axis?: { bl: string; br: string; tl: string; tr: string };
  legend?: string; read?: string; title: string; tone: 'up' | 'dn' | null; note: string | null; aria: string; as_of: string };

const NO_CORNERS: TapeCorners = { bl: '', br: '', tl: '', tr: '' };

/* The served rules then the served dots, as TapeChart marks — the label is the mark's title, the tone its class. */
export function ggTapeMarks(p: GgTapePayload): TapeMark[] {
  const rules: TapeMark[] = (p.rules ?? []).map((r) => ({
    at: r.at, group: `gg-tape-mark gg-tape-${r.tone}`,
    rule: { dash: r.style === 'dashed' ? TAPE_DASH : undefined }, title: r.label,
  }));
  const dots: TapeMark[] = (p.dots ?? []).map((d) => ({
    at: d.at, group: `gg-tape-mark gg-tape-${d.tone}`, px: d.px, dot: { r: TAPE_DOT_R }, title: d.label,
  }));
  return [...rules, ...dots];
}

/* The full tape — a preset payload skips the fetch (the Promo pattern). */
export function GgEntryTape({ id, data: preset }: { id: string; data?: GgTapePayload | null }) {
  const [data, setData] = useState<GgTapePayload | null>(preset ?? null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    if (preset) return;
    let live = true;
    fetch(`${API}${GG_TAPE_PATH}?id=${encodeURIComponent(id)}`, { credentials: 'include' })
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then((j) => { if (live) setData(j); })
      .catch(() => { if (live) setErr(true); });
    return () => { live = false; };
  }, [id, preset]);

  if (err) return <div className="ptt gg-tape" data-testid="gg-tape"><span className="pcw__dim">—</span></div>;
  if (!data) return <div className="ptt gg-tape" data-testid="gg-tape"><span className="pcw__dim">…</span></div>;
  const hlines = (data.hlines ?? []).map((h) => ({ px: h.px, className: `gg-tape-hline gg-tape-${h.tone}`, label: h.label }));
  const extraPx = [...(data.hlines ?? []).map((h) => h.px), ...(data.dots ?? []).map((d) => d.px)];
  const g = layout(data.bars ?? [], ggTapeMarks(data), TAPE_W, TAPE_H, extraPx);
  return (
    <div className="ptt gg-tape" data-testid="gg-tape">
      {data.read ? <div className="ptt__read" data-testid="gg-tape-read">{data.read}</div> : null}
      {g ? (
        <TapeChart g={g} width={TAPE_W} height={TAPE_H} svgClass="ptt__svg" lineClass="ptt__line" ariaLabel={data.aria}
                   hlines={hlines} corners={data.axis ?? NO_CORNERS} />
      ) : null}
      {g && data.legend ? <div className="ptt__legend mono" data-testid="gg-tape-legend">{data.legend}</div> : null}
      {data.note ? <div className="cm-note" data-testid="gg-tape-note">{data.note}</div> : null}
    </div>
  );
}

/* The row's mini tape — fetched once per id per page life (lite), only when the row scrolls into view. */
const ggLiteCache = new Map<string, Promise<GgTapePayload>>();
export function fetchGgLiteTape(id: string): Promise<GgTapePayload> {
  let p = ggLiteCache.get(id);
  if (!p) {
    p = fetch(`${API}${GG_TAPE_PATH}?id=${encodeURIComponent(id)}&lite=1`, { credentials: 'include' })
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json() as Promise<GgTapePayload>; });
    p.catch(() => ggLiteCache.delete(id));          // a failed fetch may retry on the next mount
    ggLiteCache.set(id, p);
  }
  return p;
}
/** Tests only — the cache is module-global. */
export function _resetGgLiteCache() { ggLiteCache.clear(); }

export function GgEntryMiniTape({ id, onOpen, width = 100 }: { id: string; onOpen?: () => void; width?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [seen, setSeen] = useState(typeof IntersectionObserver === 'undefined');
  const [data, setData] = useState<GgTapePayload | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    if (seen || !ref.current) return;
    const io = new IntersectionObserver((es) => {
      if (es.some((e) => e.isIntersecting)) { setSeen(true); io.disconnect(); }
    }, { rootMargin: '240px' });
    io.observe(ref.current);
    return () => io.disconnect();
  }, [seen]);
  useEffect(() => {
    if (!seen) return;
    let live = true;
    fetchGgLiteTape(id).then((j) => { if (live) setData(j); }).catch(() => { if (live) setErr(true); });
    return () => { live = false; };
  }, [seen, id]);

  const g = data ? miniLayout(data.bars ?? [], (data.rules ?? []).slice(0, 1), width, SPARK_H) : null;
  return (
    <span ref={ref} className={`ptt__mini${onOpen ? ' is-clickable' : ''}`} data-testid="gg-tape-mini"
          title={data?.title ?? undefined}
          onClick={onOpen} role={onOpen ? 'button' : undefined} tabIndex={onOpen ? 0 : undefined}
          onKeyDown={onOpen ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(); } } : undefined}>
      {err ? <span className="pcw__dim">—</span>
        : !data ? <span className="pcw__dim">…</span>
        : !g ? <span className="pcw__dim">—</span>
        : (
          <TapeSpark g={g} width={width} height={SPARK_H} ariaLabel={data.aria} up={data.tone === 'up'}
                     markGroup="ptt__mini-tag gg-tape-alert" />
        )}
    </span>
  );
}
