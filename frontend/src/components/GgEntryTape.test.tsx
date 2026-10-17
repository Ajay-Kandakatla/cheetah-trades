/* 🕰️ GgEntryTape (2026-10-16, DECISIONS11 D1 / D8, BUILD_SPEC11 §3.7, §4 WP-B1) — the Gajjala A+ entry tape draws the
 * SERVED levels / rules / dots and shows only SERVED strings; the mini is lazy and fetched once per id; the source types
 * no word, number or percent (the contracts check 2 regex). */
import { render, screen, waitFor, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GgEntryTape, GgEntryMiniTape, GG_TAPE_PATH, ggTapeMarks, _resetGgLiteCache, type GgTapePayload } from './GgEntryTape';
import { TAPE_DASH, TAPE_H } from './TapeChart';

const T0 = Date.UTC(2026, 9, 14, 19, 0);        // 15:00 ET
const iso = (ms: number) => new Date(ms).toISOString();
const bar = (t: number, c: number, s = 'rth') => ({ t, o: c, h: c + 0.01, l: c - 0.01, c, v: 1000, s });
const BARS = [bar(T0 - 5 * 60_000, 1.18, 'rth'), bar(T0, 1.2), bar(T0 + 5 * 60_000, 1.23), bar(T0 + 10 * 60_000, 1.3), bar(T0 + 65 * 60_000, 1.4, 'afterhours')];

const payload = (over: Partial<GgTapePayload> = {}): GgTapePayload => ({
  id: '2026-10-14|SYM|bull_flag|aplus', ticker: 'SYM', tf: 'served tf words', lite: false, bars: BARS, n_bars: BARS.length,
  hlines: [
    { key: 'trigger', px: 1.22, tone: 'buy', label: 'served trigger label' },
    { key: 'stop', px: 1.00, tone: 'stop', label: 'served stop label' },
    { key: 'target', px: 1.28, tone: 'target', label: 'served target label' },
  ],
  rules: [
    { key: 'alert', at: iso(T0), style: 'solid', tone: 'alert', label: 'served alert rule' },
    { key: 'fill', at: iso(T0 + 60_000), style: 'dashed', tone: 'fill', label: 'served fill rule' },
  ],
  dots: [
    { key: 'fill', at: iso(T0 + 60_000), px: 1.22, tone: 'fill', label: 'served fill dot' },
    { key: 'exit', at: iso(T0 + 2 * 60_000), px: 1.28, tone: 'target', label: 'served exit dot' },
  ],
  axis: { bl: 'served bl', br: 'served br', tl: 'served tl', tr: 'served tr' },
  legend: 'served legend words', read: 'served read line', title: 'served title line', tone: 'up', note: null,
  aria: 'served aria words', as_of: iso(T0), ...over,
});

afterEach(() => { vi.unstubAllGlobals(); _resetGgLiteCache(); });

describe('GgEntryTape — the full tape (preset payload)', () => {
  it('(1) the rendered text is EXACTLY the served strings, in order; dashed rule 3 3, solid none', () => {
    const p = payload({ note: 'served note words' });
    const { container } = render(<GgEntryTape id={p.id} data={p} />);
    const want = p.read! + p.hlines!.map((h) => h.label).join('') + p.rules.map((r) => r.label).join('')
      + p.dots!.map((d) => d.label).join('') + p.axis!.bl + p.axis!.br + p.axis!.tr + p.axis!.tl + p.legend! + p.note!;
    expect(container.textContent).toBe(want);
    expect(screen.getByTestId('gg-tape-read').textContent).toBe(p.read);
    expect(screen.getByTestId('gg-tape-legend').textContent).toBe(p.legend);
    expect(screen.getByTestId('gg-tape-note').textContent).toBe(p.note);
    const svg = container.querySelector('svg.ptt__svg')!;
    expect(svg.getAttribute('aria-label')).toBe(p.aria);
    expect(svg.querySelectorAll('g.gg-tape-hline').length).toBe(3);
    expect(svg.querySelectorAll('g.gg-tape-hline.gg-tape-buy, g.gg-tape-hline.gg-tape-stop, g.gg-tape-hline.gg-tape-target').length).toBe(3);
    const alert = svg.querySelector('g.gg-tape-mark.gg-tape-alert line')!;
    const fill = svg.querySelector('g.gg-tape-mark.gg-tape-fill line')!;
    expect(alert.hasAttribute('stroke-dasharray')).toBe(false);
    expect(fill.getAttribute('stroke-dasharray')).toBe(TAPE_DASH);
    expect(svg.querySelectorAll('g.gg-tape-mark line').length).toBe(2);       // two rules
    expect(svg.querySelectorAll('g.gg-tape-mark circle').length).toBe(2);     // two dots
    expect(svg.querySelectorAll('g.gg-tape-mark.gg-tape-target circle').length).toBe(1);
    // the served levels widen the range (§3.7 extraPx = hline + dot prices): the stop well under the bars is the new lo,
    // drawn on the plot's bottom edge — NEGATIVE: dropped extraPx would put it below the plot (off the svg)
    const stopY = Number(svg.querySelector('g.gg-tape-hline.gg-tape-stop line')!.getAttribute('y1'));
    expect(stopY).toBeGreaterThanOrEqual(12);
    expect(stopY).toBeLessThanOrEqual(TAPE_H - 14);
    expect(stopY).toBe(96);
    expect(svg.querySelector('g.gg-tape-hline.gg-tape-stop line')!.getAttribute('y2')).toBe('96');
  });

  it('ggTapeMarks: rules then dots; the dot carries its served px, the rule none', () => {
    const m = ggTapeMarks(payload());
    expect(m.map((x) => x.title)).toEqual(['served alert rule', 'served fill rule', 'served fill dot', 'served exit dot']);
    expect(m[0].rule).toEqual({ dash: undefined });
    expect(m[1].rule).toEqual({ dash: TAPE_DASH });
    expect(m[2].px).toBe(1.22);
    expect(m[0].px).toBeUndefined();
    expect(m[0].dot).toBeUndefined();
    expect(m[3].group).toBe('gg-tape-mark gg-tape-target');
  });

  it('(2) NEGATIVE: hlines / rules / dots [] → no hline / mark elements; bars [] → no svg, only the served note', () => {
    const p = payload({ hlines: [], rules: [], dots: [] });
    const { container } = render(<GgEntryTape id={p.id} data={p} />);
    expect(container.querySelector('svg')).not.toBeNull();
    expect(container.querySelectorAll('g').length).toBe(0);
    expect(container.querySelectorAll('svg line').length).toBe(0);
    expect(container.querySelectorAll('svg circle').length).toBe(0);
    expect(container.querySelectorAll('svg title').length).toBe(0);
    // the route's fault shape (AMENDMENTS11 F19): legend / read / axis None → no svg, only the served note
    const fault = payload({ bars: [], n_bars: 0, hlines: [], rules: [], dots: [], axis: null as any, legend: null as any, read: null as any, note: 'served fault note' });
    const f = render(<GgEntryTape id={fault.id} data={fault} />).container;
    expect(f.querySelector('svg')).toBeNull();
    expect(f.querySelector('[data-testid="gg-tape-legend"]')).toBeNull();
    expect(f.querySelector('[data-testid="gg-tape-read"]')).toBeNull();
    expect(f.textContent).toBe('served fault note');
  });

  it('(2b) NEGATIVE: the served no-bars shape (tape.py keeps legend + read + axis) → no svg, NO legend for an undrawn chart', () => {
    const empty = payload({ bars: [], n_bars: 0, note: 'served no-bars note' });
    expect(empty.legend).toBeTruthy();
    expect(empty.read).toBeTruthy();
    const b = render(<GgEntryTape id={empty.id} data={empty} />).container;
    expect(b.querySelector('svg')).toBeNull();
    expect(b.querySelector('[data-testid="gg-tape-legend"]')).toBeNull();
    expect(b.textContent).not.toContain(empty.legend!);
    expect(b.textContent).not.toContain(empty.axis!.bl);
    expect(b.querySelector('[data-testid="gg-tape-note"]')!.textContent).toBe('served no-bars note');
    // BUILD_SPEC11 §3.7 renders the served read ungated ({read ? …}); the read + the note are all that remain
    expect(b.querySelector('[data-testid="gg-tape-read"]')!.textContent).toBe(empty.read);
    expect(b.textContent).toBe(empty.read! + 'served no-bars note');
  });

  it('(3) fetches /chart-maps/gajjala/entry-tape?id= + encodeURIComponent(id) (a REPLAY id round-trips); HTTP 502 → — only', async () => {
    const id = 'REPLAY:2026-10-12|RPL|bull_flag';
    const p = payload({ id });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => p }));
    render(<GgEntryTape id={id} />);
    await waitFor(() => expect(screen.getByTestId('gg-tape-read').textContent).toBe(p.read));
    const url = (fetch as any).mock.calls[0][0] as string;
    expect(url.endsWith(`${GG_TAPE_PATH}?id=${encodeURIComponent(id)}`)).toBe(true);
    expect(decodeURIComponent(url.split('?id=')[1])).toBe(id);
    expect((fetch as any).mock.calls[0][1]).toEqual({ credentials: 'include' });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 502, json: async () => ({}) }));
    const bad = render(<GgEntryTape id="2026-10-14|BAD|bull_flag|aplus" />);
    await waitFor(() => expect(bad.container.textContent).toBe('—'));
    expect(bad.container.querySelector('svg')).toBeNull();
  });

  it('loading shows the glyph only', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const { container } = render(<GgEntryTape id="x|Y|z|aplus" />);
    expect(container.textContent).toBe('…');
  });
});

describe('GgEntryMiniTape — lazy, once per id, served title / tone', () => {
  function stubIO() {
    const cbs: ((es: any[]) => void)[] = [];
    class IO { cb: (es: any[]) => void; constructor(cb: any) { this.cb = cb; cbs.push(cb); } observe() {} disconnect() {} unobserve() {} takeRecords() { return []; } }
    vi.stubGlobal('IntersectionObserver', IO as any);
    return { fire: () => act(() => { cbs.forEach((cb) => cb([{ isIntersecting: true }])); }) };
  }

  it('(4) NEGATIVE: an observer that never fires → 0 fetches; fired → 1 fetch with &lite=1; a second mount → still 1', async () => {
    const io = stubIO();
    const lite = { ...payload({ lite: true, tone: 'up', title: 'served mini title' }), bars: BARS.map((b) => ({ t: b.t, c: b.c, s: b.s })) };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => lite }));
    const id = '2026-10-14|SYM|bull_flag|aplus';
    const a = render(<GgEntryMiniTape id={id} width={100} />);
    await new Promise((r) => setTimeout(r, 20));
    expect((fetch as any).mock.calls.length).toBe(0);
    expect(a.container.textContent).toBe('…');
    io.fire();
    await waitFor(() => expect(a.container.querySelector('[data-testid="gg-tape-mini"] svg')).not.toBeNull());
    expect((fetch as any).mock.calls.length).toBe(1);
    expect((fetch as any).mock.calls[0][0]).toMatch(new RegExp(`${GG_TAPE_PATH}\\?id=${encodeURIComponent(id).replace(/\|/g, '\\|')}&lite=1$`));
    const mini = a.getByTestId('gg-tape-mini');
    expect(mini.getAttribute('title')).toBe('served mini title');
    expect(mini.querySelector('path')!.getAttribute('class')).toBe('ptt__mini-line is-up');
    expect(mini.querySelector('svg')!.getAttribute('aria-label')).toBe(lite.aria);
    expect(mini.querySelectorAll('g.ptt__mini-tag.gg-tape-alert line').length).toBe(1);
    a.unmount();
    const b = render(<GgEntryMiniTape id={id} />);
    io.fire();
    await waitFor(() => expect(b.container.querySelector('svg')).not.toBeNull());
    expect((fetch as any).mock.calls.length).toBe(1);                // the page cache
  });

  it('the served tone dn → is-dn; a click calls onOpen; HTTP 502 → — and the next mount retries', async () => {
    const lite = { ...payload({ lite: true, tone: 'dn' }), bars: BARS.map((b) => ({ t: b.t, c: b.c, s: b.s })) };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => lite }));
    const onOpen = vi.fn();
    const r = render(<GgEntryMiniTape id="dn|SYM|x|aplus" onOpen={onOpen} />);      // jsdom: no IntersectionObserver → seen at once
    await waitFor(() => expect(r.container.querySelector('svg')).not.toBeNull());
    const mini = r.getByTestId('gg-tape-mini');
    expect(mini.className).toBe('ptt__mini is-clickable');
    expect(mini.querySelector('path')!.getAttribute('class')).toBe('ptt__mini-line is-dn');
    mini.click();
    expect(onOpen).toHaveBeenCalledTimes(1);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 502, json: async () => ({}) }));
    const bad = render(<GgEntryMiniTape id="bad|SYM|x|aplus" />);
    await waitFor(() => expect(bad.container.textContent).toBe('—'));
    bad.unmount();
    render(<GgEntryMiniTape id="bad|SYM|x|aplus" />);
    await waitFor(() => expect((fetch as any).mock.calls.length).toBe(2));   // a failed fetch was evicted
  });

  it('NEGATIVE: tone null reads is-dn (never up); no bars → the glyph, no svg', async () => {
    const lite = { ...payload({ lite: true, tone: null, bars: [], n_bars: 0 }) };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => lite }));
    const r = render(<GgEntryMiniTape id="empty|SYM|x|aplus" />);
    await waitFor(() => expect(r.container.textContent).toBe('—'));
    expect(r.container.querySelector('svg')).toBeNull();
  });
});

describe('GgEntryTape.tsx source — types no word, number or percent (contracts check 2)', () => {
  const root = (globalThis as any).process?.cwd?.() || '.';
  async function readSource(rel: string): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));     // tsc-safe (the GajjalaBoard.potential.test precedent)
    return (mod?.default || mod).readFileSync(`${root}/${rel}`, 'utf8');
  }
  const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
  function scan(src: string): string[] {
    const code = strip(src);
    const errs: string[] = [];
    if (!/import\s*\{[^}]*\bTapeChart\b[^}]*\bTapeSpark\b[^}]*\}\s*from\s*'\.\/TapeChart'/.test(code)) errs.push('imports TapeChart + TapeSpark');
    if (!code.includes("GG_TAPE_PATH = '/chart-maps/gajjala/entry-tape'")) errs.push('GG_TAPE_PATH');
    const bad = code.match(/toFixed|Math\.|%|etStamp\(|toLocale|Intl\./);
    if (bad) errs.push(`banned ${bad[0]}`);
    for (const m of code.matchAll(/>([^<>{}\n]+)</g)) {
      const t = m[1].trim();
      if (t && t !== '…' && t !== '—') errs.push(`JSX text "${t}"`);
    }
    return errs;
  }

  it('(5) the shipped file passes the scan', async () => {
    expect(scan(await readSource('src/components/GgEntryTape.tsx'))).toEqual([]);
  });

  it('(5) NEGATIVE: a .toFixed( / a % / a typed JSX word in a copy fails it', async () => {
    const src = await readSource('src/components/GgEntryTape.tsx');
    expect(scan(src.replace('label: h.label', 'label: h.px.toFixed(2)')).join(' ')).toContain('banned toFixed');
    expect(scan(src.replace("? ' is-clickable' : ''", "? ' is-clickable' : '%'")).join(' ')).toContain('banned %');
    expect(scan(src.replace('<span className="pcw__dim">…</span>', '<span className="pcw__dim">Loading the tape</span>')).join(' ')).toContain('JSX text "Loading the tape"');
  });
});
