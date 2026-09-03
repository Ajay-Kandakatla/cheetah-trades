/* PromoTagTape — where was the price when the account posted, where did it
 * go? Ajay 2026-09-02: "did they actually PSA it before the blow up or after…
 * I am looking for the price points and time on a graph."
 *
 * 5-min closes (pre/post market shaded) from a session before the first tag
 * to now, a marker at every roster tag, and the backend's before / mid-run /
 * after read. Plain SVG — no chart lib, one fetch per expanded row. */
import { useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';

type Bar = { t: number; o: number; h: number; l: number; c: number; v: number; s: string };
type Tag = { handle: string; tier: 'S' | 'A' | 'B'; at: string; which: 'first' | 'last' | 'post'; sample?: string | null; msg_id?: number | null;
  price_at?: number | null; before_pct?: number | null; peak_after_pct?: number | null };
export type TapePayload = {
  ticker: string; bars: Bar[]; tags: Tag[]; n_bars: number; tf: string;
  verdict: string | null; read: string | null; price_at_tag?: number | null;
  before_pct?: number | null; peak_pct?: number | null; now_pct?: number | null;
  mins_to_peak?: number | null; peak_at?: string | null; note?: string;
};

const TIER_COLORS: Record<string, string> = { S: 'var(--negative, #e5484d)', A: '#e8a33d', B: 'var(--muted, #8b8fa3)' };
const VERDICT_STYLE: Record<string, string> = {
  BEFORE_THE_MOVE: 'var(--positive, #46a758)', MID_RUN: '#e8a33d',
  AFTER_THE_MOVE: 'var(--negative, #e5484d)', NO_RUN: 'var(--text-muted, #94a3b8)', NO_TAPE_AFTER: 'var(--text-muted, #94a3b8)',
};

export const etStamp = (ms: number) =>
  new Date(ms).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York' })
    .replace(' AM', 'a').replace(' PM', 'p').replace(',', ' ·') + ' ET';

/* Pure geometry so the test can pin marker placement. */
export function layout(bars: Bar[], tags: Tag[], w: number, h: number) {
  if (!bars.length) return null;
  const t0 = bars[0].t, t1 = bars[bars.length - 1].t;
  const lo = Math.min(...bars.map((b) => b.l)), hi = Math.max(...bars.map((b) => b.h));
  const span = Math.max(1, t1 - t0), range = Math.max(1e-9, hi - lo);
  const x = (t: number) => ((Math.min(Math.max(t, t0), t1) - t0) / span) * (w - 8) + 4;
  const y = (p: number) => h - 14 - ((p - lo) / range) * (h - 26);
  const path = bars.map((b, i) => `${i ? 'L' : 'M'}${x(b.t).toFixed(1)},${y(b.c).toFixed(1)}`).join(' ');
  const ext: { x0: number; x1: number }[] = [];
  let run: { x0: number; x1: number } | null = null;
  bars.forEach((b, i) => {
    const isExt = b.s === 'premarket' || b.s === 'afterhours';
    const xb = x(b.t), xn = i + 1 < bars.length ? x(bars[i + 1].t) : w - 4;
    if (isExt) { if (run) run.x1 = xn; else run = { x0: xb, x1: xn }; }
    else if (run) { ext.push(run); run = null; }
  });
  if (run) ext.push(run);
  const markers = tags.map((tg) => {
    const ms = Date.parse(tg.at);
    const at = [...bars].reverse().find((b) => b.t <= ms) ?? bars[0];
    return { ...tg, ms, x: x(ms), y: y(at.c), price: at.c };
  });
  return { x, y, lo, hi, path, ext, markers, t0, t1 };
}

export function PromoTagTape({ ticker, data: preset }: { ticker: string; data?: TapePayload | null }) {
  const [data, setData] = useState<TapePayload | null>(preset ?? null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (preset) return;
    let live = true;
    fetch(`${API}/catalysts/promo-circuit/tape/${encodeURIComponent(ticker)}`, { credentials: 'include' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => { if (live) setData(j); })
      .catch((e) => { if (live) setErr(String(e?.message ?? e)); });
    return () => { live = false; };
  }, [ticker, preset]);

  if (err) return <div className="cm-note cm-note-warn">Tape unavailable: {err}</div>;
  if (!data) return <div className="cm-note">Loading the tape around the tag…</div>;
  const W = 720, H = 110;
  const g = layout(data.bars, data.tags, W, H);
  if (!g) return <div className="day-empty">No intraday bars for {ticker} yet.</div>;
  const first = g.markers.find((m) => m.which === 'first');
  const last = data.bars[data.bars.length - 1];
  return (
    <div className="ptt">
      <div className="ptt__read" style={{ color: VERDICT_STYLE[data.verdict ?? ''] ?? 'inherit' }}>
        {data.read ?? 'No read yet'}
      </div>
      <svg className="ptt__svg" viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img"
           aria-label={`${ticker} 5-minute tape around the promo tags`}>
        {g.ext.map((e, i) => <rect key={i} x={e.x0} y={0} width={Math.max(1, e.x1 - e.x0)} height={H - 14} className="ptt__ext" />)}
        <path d={g.path} className="ptt__line" fill="none" />
        {g.markers.map((m, i) => (
          <g key={i} className="ptt__tag">
            <line x1={m.x} x2={m.x} y1={4} y2={H - 14} stroke={TIER_COLORS[m.tier] ?? TIER_COLORS.B}
                  strokeDasharray={m.which === 'first' ? undefined : '3 3'} />
            <circle cx={m.x} cy={m.y} r={3.5} fill={TIER_COLORS[m.tier] ?? TIER_COLORS.B} />
            <title>{`@${m.handle} ${m.which} post · ${etStamp(m.ms)} · $${m.price.toFixed(2)}`
              + (m.before_pct != null ? `\n${m.before_pct >= 0 ? '+' : ''}${m.before_pct.toFixed(1)}% in the hour before` : '')
              + (m.peak_after_pct != null ? ` · ${m.peak_after_pct >= 0 ? '+' : ''}${m.peak_after_pct.toFixed(1)}% to the peak after` : '')
              + (m.sample ? `\n“${m.sample}”` : '')}</title>
          </g>
        ))}
        <text x={4} y={H - 3} className="ptt__axis">{etStamp(g.t0)}</text>
        <text x={W - 4} y={H - 3} textAnchor="end" className="ptt__axis">{etStamp(g.t1)} · ${last.c.toFixed(2)}</text>
        <text x={W - 4} y={11} textAnchor="end" className="ptt__axis">hi ${g.hi.toFixed(2)}</text>
        <text x={4} y={11} className="ptt__axis">lo ${g.lo.toFixed(2)}</text>
      </svg>
      {/* The actual announcements, in order — time, account, words, price then, what had
          already happened, what followed (Ajay: "actual announcement time vs the price action"). */}
      <table className="ptt__posts mono">
        <tbody>
          {g.markers.map((m, i) => (
            <tr key={i}>
              <td className="pcw__dim">{etStamp(m.ms)}</td>
              <td style={{ color: TIER_COLORS[m.tier] ?? TIER_COLORS.B }}>
                <a href={`https://stocktwits.com/${encodeURIComponent(m.handle)}`} target="_blank" rel="noreferrer" className="pcw__acct-link">@{m.handle}</a>
              </td>
              <td className="ptt__posts-body">{m.sample ? `“${m.sample}”` : (m.which === 'last' ? 'last post' : '')}</td>
              <td className="og__num">${m.price.toFixed(2)}</td>
              <td className={`og__num ${(m.before_pct ?? 0) >= 3 ? 'og__dn' : 'pcw__dim'}`} title="move in the hour BEFORE this post">
                {m.before_pct != null ? `${m.before_pct >= 0 ? '+' : ''}${m.before_pct.toFixed(1)}% before` : ''}
              </td>
              <td className={`og__num ${(m.peak_after_pct ?? 0) >= 5 ? 'og__up' : 'pcw__dim'}`} title="peak AFTER this post">
                {m.peak_after_pct != null ? `${m.peak_after_pct >= 0 ? '+' : ''}${m.peak_after_pct.toFixed(1)}% after` : ''}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="ptt__legend mono">
        {first ? <span>● first tag {etStamp(first.ms)} @ ${first.price.toFixed(2)}</span> : null}
        {data.peak_pct != null ? <span> · peak {data.peak_pct >= 0 ? '+' : ''}{data.peak_pct.toFixed(1)}% {data.peak_at ? `at ${etStamp(Date.parse(data.peak_at))}` : ''}</span> : null}
        {data.now_pct != null ? <span> · now {data.now_pct >= 0 ? '+' : ''}{data.now_pct.toFixed(1)}%</span> : null}
        <span className="pcw__dim"> · {data.tf} · shaded = pre/post market</span>
      </div>
    </div>
  );
}

/* ── Inline mini tape — Ajay 2026-09-02: "the small graph of when they
 * announced vs where it is" on EVERY row, not behind a toggle. Lite payload
 * (15-min closes + the markers + the read), fetched once per ticker per page
 * life and only when the row scrolls into view; clicking it opens the full tape. */
type LiteBar = { t: number; c: number; s: string };
export type LitePayload = Omit<TapePayload, 'bars'> & { bars: LiteBar[]; lite?: boolean };
const liteCache = new Map<string, Promise<LitePayload>>();
export function fetchLiteTape(ticker: string): Promise<LitePayload> {
  let p = liteCache.get(ticker);
  if (!p) {
    p = fetch(`${API}/catalysts/promo-circuit/tape/${encodeURIComponent(ticker)}?lite=1`, { credentials: 'include' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() as Promise<LitePayload>; });
    p.catch(() => liteCache.delete(ticker));          // a failed fetch may retry on the next mount
    liteCache.set(ticker, p);
  }
  return p;
}
/** Tests only — the cache is module-global. */
export function _resetLiteCache() { liteCache.clear(); }

/* Pure geometry for the sparkline: closes only, full height, no axis band. */
export function miniLayout(bars: LiteBar[], tags: Pick<Tag, 'at' | 'which' | 'tier'>[], w: number, h: number) {
  if (!bars?.length) return null;
  const t0 = bars[0].t, t1 = bars[bars.length - 1].t;
  const lo = Math.min(...bars.map((b) => b.c)), hi = Math.max(...bars.map((b) => b.c));
  const span = Math.max(1, t1 - t0), range = Math.max(1e-9, hi - lo);
  const x = (t: number) => ((Math.min(Math.max(t, t0), t1) - t0) / span) * (w - 6) + 3;
  const y = (p: number) => h - 3 - ((p - lo) / range) * (h - 6);
  const path = bars.map((b, i) => `${i ? 'L' : 'M'}${x(b.t).toFixed(1)},${y(b.c).toFixed(1)}`).join(' ');
  const ext: { x0: number; x1: number }[] = [];
  let run: { x0: number; x1: number } | null = null;
  bars.forEach((b, i) => {
    const isExt = b.s === 'premarket' || b.s === 'afterhours';
    const xb = x(b.t), xn = i + 1 < bars.length ? x(bars[i + 1].t) : w - 3;
    if (isExt) { if (run) run.x1 = xn; else run = { x0: xb, x1: xn }; }
    else if (run) { ext.push(run); run = null; }
  });
  if (run) ext.push(run);
  const first = tags.find((t) => t.which === 'first') ?? tags[0];
  let marker: { x: number; y: number; price: number; ms: number } | null = null;
  if (first) {
    const ms = Date.parse(first.at);
    const at = [...bars].reverse().find((b) => b.t <= ms) ?? bars[0];
    marker = { x: x(ms), y: y(at.c), price: at.c, ms };
  }
  const last = bars[bars.length - 1];
  return { path, ext, marker, last: { x: x(last.t), y: y(last.c), price: last.c }, lo, hi };
}

const pctS = (v: number | null | undefined) => (v == null ? '' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`);

export function MiniTape({ ticker, onOpen }: { ticker: string; onOpen?: () => void }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [seen, setSeen] = useState(typeof IntersectionObserver === 'undefined');
  const [data, setData] = useState<LitePayload | null>(null);
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
    fetchLiteTape(ticker).then((j) => { if (live) setData(j); }).catch(() => { if (live) setErr(true); });
    return () => { live = false; };
  }, [seen, ticker]);

  const W = 120, H = 30;
  const g = data ? miniLayout(data.bars ?? [], data.tags ?? [], W, H) : null;
  const up = !!g && g.marker != null && g.last.price >= g.marker.price;
  const title = data && g
    ? (data.read ?? 'No read yet')
      + (g.marker ? `\nfirst tag ${etStamp(g.marker.ms)} @ $${g.marker.price.toFixed(2)}` : '')
      + ` · now $${g.last.price.toFixed(2)} ${pctS(data.now_pct)}`
      + (data.peak_pct != null ? ` · peak ${pctS(data.peak_pct)}` : '')
      + '\nclick for the full tape'
    : 'Price path since the tag';
  return (
    <span ref={ref} className={`ptt__mini${onOpen ? ' is-clickable' : ''}`} title={title}
          onClick={onOpen} role={onOpen ? 'button' : undefined} tabIndex={onOpen ? 0 : undefined}
          onKeyDown={onOpen ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(); } } : undefined}
          data-verdict={data?.verdict ?? undefined}>
      {err ? <span className="pcw__dim">—</span>
        : !data ? <span className="pcw__dim">…</span>
        : !g ? <span className="pcw__dim">no tape</span>
        : (
          <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label={`${ticker} price path since the tag`}>
            {g.ext.map((e, i) => <rect key={i} x={e.x0} y={0} width={Math.max(1, e.x1 - e.x0)} height={H} className="ptt__ext" />)}
            <path d={g.path} className={`ptt__mini-line ${up ? 'is-up' : 'is-dn'}`} fill="none" />
            {g.marker ? (
              <g className="ptt__mini-tag">
                <line x1={g.marker.x} x2={g.marker.x} y1={1} y2={H - 1} stroke={VERDICT_STYLE[data.verdict ?? ''] ?? TIER_COLORS.B} />
                <circle cx={g.marker.x} cy={g.marker.y} r={2.6} fill={VERDICT_STYLE[data.verdict ?? ''] ?? TIER_COLORS.B} />
              </g>
            ) : null}
            <circle cx={g.last.x} cy={g.last.y} r={2} className="ptt__mini-now" />
          </svg>
        )}
    </span>
  );
}
