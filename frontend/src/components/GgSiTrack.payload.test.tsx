import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GgSiTrackSection } from './GgSiTrack';
import type { GgSiTrackBlock } from '../lib/gajjala';

/* 🏁 The SERVED SI track record block through the real component (2026-11-26, spec sitrack §3.7 B, §4 main-session).
 * Ajay 2026-11-26: "I want us to track these patters for future from SI like a track recprd with in SI stocks itself".
 *
 * Reads the golden the backend pins `si_track.served_block` against (backend/tests/fixtures/
 * gajjala_si_track_block_golden_2026_11_26.json, WP5 — a fixed three-session fixture), or a live block:
 * SI_TRACK_LIVE_BLOCK=<abs path> (the `si_track` value of a GET of the 🩳 sub, or the whole 🩳 block that holds it).
 * GgSiTrack.test.tsx pins the component on SENTINEL strings; this file pins that the BACKEND's keys are the keys the
 * component reads: every served line, pattern cell, shape, day cell and chip reaches the DOM verbatim, in the served
 * order, and nothing else does. No skip: a missing file FAILS.
 * NEGATIVES: closed on first paint (no body); a null served line prints nothing; the patterns keep the served order
 * (⛔ SSR first, 🩳 EXTREME second) with no gap_up row; a counted:false row never sits above the served new_label;
 * a served fault → one error line, no table; no word, no number of the component's own (every text node is a served
 * string); the body never prints `n` / `n_days`; no served string says signal / edge / SHOWN alone. */

const NODE = { fs: 'node:fs', path: 'node:path', url: 'node:url' };
const ENV: string | undefined = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.SI_TRACK_LIVE_BLOCK;

async function load(): Promise<GgSiTrackBlock & Record<string, any>> {
  const fs = await import(/* @vite-ignore */ NODE.fs);
  const path = await import(/* @vite-ignore */ NODE.path);
  const url = await import(/* @vite-ignore */ NODE.url);
  const here = path.dirname(url.fileURLToPath(import.meta.url));
  const file: string = ENV
    ? (path.isAbsolute(ENV) ? ENV : path.resolve((globalThis as any).process.cwd(), ENV))
    : path.resolve(here, '../../../backend/tests/fixtures/gajjala_si_track_block_golden_2026_11_26.json');
  if (!fs.existsSync(file)) throw new Error(`si_track block not found: ${file}`);
  const j = JSON.parse(fs.readFileSync(file, 'utf8'));
  const b = j && typeof j === 'object' && j.si_track && typeof j.si_track === 'object' ? j.si_track : j;
  if (!b || typeof b !== 'object' || Array.isArray(b)) throw new Error(`no si_track block in ${file}`);
  return b;
}

const servedText = (x: unknown): x is string => typeof x === 'string' && x.trim() !== '';
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const wrap = { wrapper: ({ children }: any) => <MemoryRouter>{children}</MemoryRouter> };
const openFold = (el: HTMLElement) => {
  (el as HTMLDetailsElement).open = true;
  fireEvent(el, new Event('toggle'));
};
function strings(x: unknown, out: Set<string> = new Set()): Set<string> {
  if (typeof x === 'string') out.add(x);
  else if (Array.isArray(x)) x.forEach((v) => strings(v, out));
  else if (x && typeof x === 'object') Object.values(x).forEach((v) => strings(v, out));
  return out;
}
const textNodes = (el: HTMLElement): string[] => {
  const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  const out: string[] = [];
  for (let n = w.nextNode(); n; n = w.nextNode()) if ((n.textContent || '').trim()) out.push(n.textContent as string);
  return out;
};
const LINES: [string, string][] = [
  ['title', 'gg-st-title'], ['asof_text', 'gg-st-asof'], ['base_text', 'gg-st-base'], ['new_today_text', 'gg-st-new-today'],
  ['empty_text', 'gg-st-empty'], ['where_text', 'gg-st-where'], ['shown_text', 'gg-st-shown'],
  ['pending_text', 'gg-st-pending'],
];
/** The served pattern head keys the component maps to a pattern field (GgSiTrack.tsx PAT_FIELD). */
const PAT_FIELD: Record<string, string> = {
  label: 'label', with: 'with_text', without: 'without_text', diff: 'diff_text', shuffle: 'shuffle_text', word: 'word',
};

afterEach(() => { vi.restoreAllMocks(); });

describe('🏁 served si_track block → GgSiTrackSection, verbatim', () => {
  it('the block file exists and carries the frozen §3.7 keys (fails loudly, never skips)', async () => {
    const b = await load();
    for (const k of ['title', 'summary_text', 'base_text', 'new_today_text', 'pattern_heads', 'patterns', 'where_text',
      'shape_rows', 'heads', 'days', 'shown_text', 'pending_text', 'asof_text', 'rule_label', 'rule_text', 'honesty',
      'fault_text', 'empty_text', 'n', 'n_days']) expect(Object.prototype.hasOwnProperty.call(b, k), k).toBe(true);
    // the served pattern heads are exactly the keys the component maps, in the served order
    expect((b.pattern_heads || []).map(([k]) => k)).toEqual(['label', 'with', 'without', 'diff', 'shuffle', 'word']);
    for (const [k] of b.pattern_heads || []) expect(PAT_FIELD[k], k).toBeTruthy();
    // every day row carries one served cell per served day head
    const heads = (b.heads || []).map(([k]) => k);
    expect(heads[0]).toBe('ticker');
    for (const d of b.days || []) for (const r of d.rows || []) {
      expect(Object.keys(r.cells || {}).sort(), `${d.date} ${r.symbol}`).toEqual([...heads].sort());
      expect(typeof r.counted).toBe('boolean');
    }
    if (!ENV) {
      expect(b.summary_text).toBe('🏁 SI track record · 4 of 6 ran +40%');
      expect(b.patterns!.map((p) => p.key)).toEqual(
        ['ssr_open', 'tier_extreme', 'regsho_on', 'regsho_past', 'dilution_before', 'split_before', 'prev_winner']);
      expect(b.days!.map((d) => d.date)).toEqual(['2026-11-20', '2026-11-19', '2026-11-18']);
      expect(b.fault_text).toBeNull();
      expect(b.shown_text).toBeNull();
    }
  });

  it('closed on first paint: ONE <details>, summary = the served summary_text, no body in the DOM', async () => {
    const b = await load();
    const { container } = render(<GgSiTrackSection block={clone(b)} />, wrap);
    const fold = screen.getByTestId('gg-st');
    expect(fold.tagName).toBe('DETAILS');
    expect(fold.hasAttribute('open')).toBe(false);
    expect(screen.getByTestId('gg-st-summary').textContent).toBe(b.summary_text);
    expect(container.querySelectorAll('[data-testid="gg-st"]')).toHaveLength(1);
    // NEGATIVE: nothing of the body while closed
    expect(container.querySelector('table')).toBeNull();
    expect(container.textContent).toBe(b.summary_text);
  });

  it('open: every served line verbatim; a null line prints nothing; n / n_days never printed', async () => {
    const b = await load();
    const { container } = render(<GgSiTrackSection block={clone(b)} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    for (const [k, tid] of LINES) {
      const v = (b as any)[k];
      if (servedText(v)) expect(screen.getByTestId(tid).textContent, k).toBe(v);
      else expect(screen.queryByTestId(tid), k).toBeNull();
    }
    if (!ENV) {
      expect(screen.queryByTestId('gg-st-shown')).toBeNull();
      expect(screen.queryByTestId('gg-st-empty')).toBeNull();
    }
    const rule = screen.getByTestId('gg-st-rule');
    expect(rule.tagName).toBe('DETAILS');
    expect(rule.hasAttribute('open')).toBe(false);
    expect(rule.querySelector('summary')!.textContent).toBe(b.rule_label);
    expect(screen.getByTestId('gg-st-rule-text').textContent).toBe(b.rule_text);
    expect(screen.getByTestId('gg-st-honesty').textContent).toBe(b.honesty);
    // NEGATIVE: the counts are served for the page logic only — never a text node of their own
    const nodes = textNodes(container);
    for (const k of ['n', 'n_days']) expect(nodes).not.toContain(String((b as any)[k]));
  });

  it('the pattern table: the served heads, the rows in the served order (⛔ SSR first, 🩳 EXTREME second), every cell verbatim', async () => {
    const b = await load();
    render(<GgSiTrackSection block={clone(b)} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    const table = screen.getByTestId('gg-st-patterns');
    expect([...table.querySelectorAll('th')].map((th) => th.textContent)).toEqual(b.pattern_heads!.map(([, l]) => l));
    const rows = [...table.querySelectorAll('tbody tr')];
    expect(rows.map((r) => r.getAttribute('data-testid'))).toEqual(b.patterns!.map((p) => `gg-st-pat-${p.key}`));
    expect(rows[0].getAttribute('data-testid')).toBe('gg-st-pat-ssr_open');
    expect(rows[1].getAttribute('data-testid')).toBe('gg-st-pat-tier_extreme');
    // NEGATIVE [C4]: gap_up is a day shape, never a pattern row
    expect(screen.queryByTestId('gg-st-pat-gap_up')).toBeNull();
    b.patterns!.forEach((p, i) => {
      const tds = [...rows[i].querySelectorAll('td')];
      const first = [p.label, p.known_text, p.unknown_text].filter(servedText).join('');
      expect(tds[0].textContent, p.key!).toBe(first);
      b.pattern_heads!.slice(1).forEach(([k], j) => {
        const v = (p as any)[PAT_FIELD[k]];
        expect(tds[j + 1].textContent, `${p.key} ${k}`).toBe(servedText(v) ? v : '');
      });
      if (servedText(p.title)) expect(rows[i].getAttribute('title')).toBe(p.title);
      else expect(rows[i].hasAttribute('title')).toBe(false);
    });
  });

  it('the shape lines: one per served shape, label + winners + the rest, verbatim, in the served order', async () => {
    const b = await load();
    render(<GgSiTrackSection block={clone(b)} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    const shapes = (b.shape_rows || []).filter((s) => [s.label, s.win_text, s.rest_text].some(servedText));
    if (!ENV) expect(shapes).toHaveLength(6);
    (b.shape_rows || []).forEach((s, i) => {
      const want = [s.label, s.win_text, s.rest_text].filter(servedText).join('');
      if (want) expect(screen.getByTestId(`gg-st-shape-${i}`).textContent).toBe(want);
      else expect(screen.queryByTestId(`gg-st-shape-${i}`)).toBeNull();
    });
  });

  it('the day tables: ONE scroll box, the served days in order, every cell verbatim; counted rows above the new_label, the rest under it', async () => {
    const b = await load();
    render(<GgSiTrackSection block={clone(b)} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    const box = screen.getByTestId('gg-st-days');
    expect(box.className).toContain('gg-tr-scroll');
    const days = (b.days || []).filter((d) => (d.rows || []).length);
    expect(box.querySelectorAll('table')).toHaveLength(days.length);
    expect([...box.querySelectorAll('[data-testid^="gg-st-day-label-"]')].map((e) => e.textContent))
      .toEqual(days.map((d) => d.label));
    let sawNew = false;
    for (const d of days) {
      const el = screen.getByTestId(`gg-st-day-${d.date}`);
      expect([...el.querySelectorAll('th')].map((th) => th.textContent)).toEqual(b.heads!.map(([, l]) => l));
      const counted = d.rows!.filter((r) => r.counted === true), fresh = d.rows!.filter((r) => r.counted !== true);
      const want = [...counted.map((r) => `gg-st-row-${d.date}-${r.symbol}`),
        ...(fresh.length ? [`gg-st-newlabel-${d.date}`] : []), ...fresh.map((r) => `gg-st-row-${d.date}-${r.symbol}`)];
      expect([...el.querySelectorAll('tbody tr')].map((t) => t.getAttribute('data-testid')), d.date!).toEqual(want);
      if (fresh.length) {
        sawNew = true;
        expect(screen.getByTestId(`gg-st-newlabel-${d.date}`).textContent).toBe(d.new_label);
      } else expect(screen.queryByTestId(`gg-st-newlabel-${d.date}`)).toBeNull();
      for (const r of d.rows!) {
        const tr = screen.getByTestId(`gg-st-row-${d.date}-${r.symbol}`);
        expect(tr.getAttribute('data-counted')).toBe(String(r.counted === true));
        const tds = [...tr.querySelectorAll('td')].map((td) => td.textContent);
        const sym = [r.symbol, r.win, ...(r.chips || [])].filter(servedText).join('');
        expect(tds, `${d.date} ${r.symbol}`).toEqual([sym, ...b.heads!.slice(1).map(([k]) => {
          const v = (r.cells as any)?.[k];
          return servedText(v) ? v : '';
        })]);
        const link = tr.querySelector('a');
        if (servedText(r.href)) expect(link?.getAttribute('href')).toBe(r.href);
        if (servedText(r.title)) expect(tr.getAttribute('title')).toBe(r.title);
      }
    }
    // the golden holds one first-listed-that-day row (CCC on 11-18) — it sits under the label
    if (!ENV) {
      expect(sawNew).toBe(true);
      const trs = [...screen.getByTestId('gg-st-day-2026-11-18').querySelectorAll('tbody tr')].map((t) => t.getAttribute('data-testid'));
      expect(trs).toEqual(['gg-st-row-2026-11-18-AAA', 'gg-st-newlabel-2026-11-18', 'gg-st-row-2026-11-18-CCC']);
    }
  });

  it('NEGATIVE: the component types no word and no number — every text node is a served string; no served string says signal / edge / SHOWN alone', async () => {
    const b = await load();
    const { container } = render(<GgSiTrackSection block={clone(b)} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    const served = strings(b);
    for (const t of textNodes(container)) expect(served.has(t), `typed by the FE: "${t}"`).toBe(true);
    for (const s of served) {
      expect(/\b(signal|edge)s?\b/i.test(s), s).toBe(false);
      expect(/\bSHOWN\b/.test(s.replace(/NOT SHOWN/g, '')), s).toBe(false);
      expect(/bounc/i.test(s), s).toBe(false);
    }
  });

  it('NEGATIVE: the same block with a served fault → ONE error line, no fold, no table', async () => {
    const b = clone(await load());
    (b as any).fault_text = '🏁 served fault line';
    const { container } = render(<GgSiTrackSection block={b} />, wrap);
    expect(screen.getByTestId('gg-st-fault').textContent).toBe('🏁 served fault line');
    expect(screen.queryByTestId('gg-st')).toBeNull();
    expect(container.querySelector('table')).toBeNull();
    expect(container.textContent).toBe('🏁 served fault line');
  });

  it('NEGATIVE: the served lines nulled / NaN / numbers → nothing printed for them, the rest of the block still draws', async () => {
    const b = clone(await load()) as any;
    for (const [k] of LINES) b[k] = k === 'base_text' ? Number.NaN : k === 'where_text' ? 7 : null;
    b.days[0].rows[0].cells.high = 12.5;
    render(<GgSiTrackSection block={b} />, wrap);
    openFold(screen.getByTestId('gg-st'));
    for (const [, tid] of LINES) expect(screen.queryByTestId(tid), tid).toBeNull();
    const d0 = b.days[0], r0 = d0.rows[0];
    const tds = [...screen.getByTestId(`gg-st-row-${d0.date}-${r0.symbol}`).querySelectorAll('td')];
    const hi = (b.heads as [string, string][]).findIndex(([k]) => k === 'high');
    expect(tds[hi].textContent).toBe('');
    expect(screen.getByTestId('gg-st-patterns')).toBeTruthy();
  });
});
