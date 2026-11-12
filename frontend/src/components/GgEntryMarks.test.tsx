/**
 * 🟢 ✨ Gajjala entry marks (2026-11-12, spec §3.5 / §4 WP-FE). Ajay 2026-11-12: "Can you show me green on these tabs some
 * indicators ... an Indicator or new tickers with in last 30 mins like blinkers or something would be nice".
 *
 * Pins: the lib validators + the served-`until` clock (fake timers: lit at until − 1 s, gone after until + 1 s); the two
 * components draw only served words (no text node in the chip badge); SOURCE guards on GgEntryMarks.tsx (no typed word)
 * and on ggEntryMarks.css (longhands only, absolute badge/dot in the chip's top padding band, the 720 px phone rule, the
 * reduced-motion block) — each CSS guard shown to REJECT a broken copy (NEGATIVE); a live-patched tile keeps `new_mark`.
 */
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GgNewMark, GgSubMarksView } from './GgEntryMarks';
import { markLive, msUntil, validGreen, validMark, validNew } from '../lib/ggEntryMarks';
import { patchTiles, type CardLiveAnswer } from '../lib/cardLive';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const NOW = Date.parse('2026-11-12T20:10:00Z');
const iso = (ms: number) => new Date(ms).toISOString();
const GREEN = { n: 2, label: '2', title: 'served green title' };
const NEW = { n: 1, until: iso(NOW + 60_000), title: 'served new title' };
const MARK = { kind: 'listed', at_et: '15:01', until: iso(NOW + 60_000), text: 'served card text', title: 'served card title' };

afterEach(() => { cleanup(); vi.useRealTimers(); });

describe('lib/ggEntryMarks — validators and the served clock', () => {
  it('markLive: a parseable `until` ahead of now → true; at / behind now → false', () => {
    expect(markLive(iso(NOW + 1), NOW)).toBe(true);
    expect(markLive(iso(NOW), NOW)).toBe(false);
    expect(markLive(iso(NOW - 1000), NOW)).toBe(false);
    expect(markLive('2026-11-12T20:40:00+00:00', NOW)).toBe(true);
  });
  it('NEGATIVE: markLive on anything unparseable → false', () => {
    for (const u of [undefined, null, '', '  ', 'soon', 42, {}, [], 'NaN']) expect(markLive(u, NOW)).toBe(false);
    expect(markLive(iso(NOW + 1000), Number.NaN)).toBe(false);
  });
  it('msUntil: the gap to the served until, null when not live', () => {
    expect(msUntil(iso(NOW + 5000), NOW)).toBe(5000);
    expect(msUntil(iso(NOW - 5000), NOW)).toBeNull();
    expect(msUntil('nope', NOW)).toBeNull();
  });
  it('validGreen / validNew / validMark accept the served shapes', () => {
    expect(validGreen(GREEN)).toBe(true);
    expect(validNew(NEW)).toBe(true);
    expect(validMark(MARK)).toBe(true);
  });
  it('NEGATIVE: n 0 / negative / fractional, missing label, non-string title → invalid', () => {
    for (const g of [{ ...GREEN, n: 0 }, { ...GREEN, n: -1 }, { ...GREEN, n: 1.5 }, { ...GREEN, n: '2' },
                     { ...GREEN, label: '' }, { n: 2, title: 't' }, { ...GREEN, title: 7 }, { n: 2, label: '2' },
                     null, undefined, 'x', []]) {
      expect(validGreen(g)).toBe(false);
    }
    for (const x of [{ ...NEW, n: 0 }, { ...NEW, until: '' }, { ...NEW, title: null }, null]) expect(validNew(x)).toBe(false);
    for (const x of [{ ...MARK, text: '' }, { ...MARK, until: null }, { ...MARK, title: 3 }, null, 'x']) expect(validMark(x)).toBe(false);
  });
});

describe('GgSubMarksView — the chip badge + blinker', () => {
  it('green: data-label == served label, title == served title, NO text node', () => {
    render(<button data-testid="chip">{'🚩 Bull Flag · 3'}<GgSubMarksView subKey="bull_flag" block={{ green: GREEN }} /></button>);
    const g = screen.getByTestId('gg-sub-green-bull_flag');
    expect(g).toHaveAttribute('data-label', '2');
    expect(g).toHaveAttribute('title', 'served green title');
    expect(g).toHaveAttribute('aria-label', 'served green title');
    expect(g.textContent).toBe('');
    expect(g.childNodes).toHaveLength(0);
    expect(screen.getByTestId('chip').textContent).toBe('🚩 Bull Flag · 3');
  });
  it('NEGATIVE: no block / invalid green → nothing drawn', () => {
    for (const block of [undefined, null, {}, { green: { ...GREEN, n: 0 } }, { green: { ...GREEN, label: '' } },
                         { green: { ...GREEN, title: 9 as any } }, { green: null }]) {
      const { container, unmount } = render(<div><GgSubMarksView subKey="kiss_fly" block={block as any} /></div>);
      expect(container.querySelector('.gg-sub-green')).toBeNull();
      expect(container.querySelector('.gg-sub-new')).toBeNull();
      unmount();
    }
  });
  it('new: a future until → the dot with the served title; a past until → none', () => {
    const { unmount } = render(<GgSubMarksView subKey="kiss_fly" block={{ new: { ...NEW, until: iso(Date.now() + 600_000) } }} />);
    expect(screen.getByTestId('gg-sub-new-kiss_fly')).toHaveAttribute('title', 'served new title');
    expect(screen.getByTestId('gg-sub-new-kiss_fly').textContent).toBe('');
    unmount();
    render(<GgSubMarksView subKey="kiss_fly" block={{ new: { ...NEW, until: iso(Date.now() - 1000) } }} />);
    expect(screen.queryByTestId('gg-sub-new-kiss_fly')).toBeNull();
  });
  it('NEGATIVE: an unparseable until → no dot', () => {
    render(<GgSubMarksView subKey="kiss_fly" block={{ new: { ...NEW, until: 'in thirty minutes' } }} />);
    expect(screen.queryByTestId('gg-sub-new-kiss_fly')).toBeNull();
  });
  it('fake timers: present at until − 1 s, gone after until + 1 s (the green stays)', () => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    render(<GgSubMarksView subKey="kiss_fly" block={{ green: GREEN, new: { ...NEW, until: iso(NOW + 10_000) } }} />);
    expect(screen.getByTestId('gg-sub-new-kiss_fly')).toBeTruthy();
    act(() => { vi.advanceTimersByTime(9_000); });
    expect(screen.getByTestId('gg-sub-new-kiss_fly')).toBeTruthy();
    act(() => { vi.advanceTimersByTime(2_000); });
    expect(screen.queryByTestId('gg-sub-new-kiss_fly')).toBeNull();
    expect(screen.getByTestId('gg-sub-green-kiss_fly')).toBeTruthy();
  });
  it('the timer is cleared on unmount (no pending timer left behind)', () => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    const { unmount } = render(<GgSubMarksView subKey="x" block={{ new: { ...NEW, until: iso(NOW + 10_000) } }} />);
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe('GgNewMark — the card blinker', () => {
  it('a live mark → the dot + the served text, title == served title', () => {
    render(<GgNewMark mark={{ ...MARK, until: iso(Date.now() + 600_000) }} sym="RIME" />);
    const m = screen.getByTestId('gg-new-RIME');
    expect(m.textContent).toBe('served card text');
    expect(m).toHaveAttribute('title', 'served card title');
    expect(m.querySelector('.gg-new-dot')?.getAttribute('aria-hidden')).toBe('true');
  });
  it('NEGATIVE: expired / absent / invalid → nothing', () => {
    for (const mark of [{ ...MARK, until: iso(Date.now() - 1) }, undefined, null, { ...MARK, text: '' }, { ...MARK, until: 'x' }]) {
      const { container, unmount } = render(<div><GgNewMark mark={mark} sym="RIME" /></div>);
      expect((container.firstChild as HTMLElement).innerHTML).toBe('');
      unmount();
    }
  });
  it('fake timers: disappears at the served until', () => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    render(<GgNewMark mark={{ ...MARK, until: iso(NOW + 30_000) }} sym="RIME" />);
    act(() => { vi.advanceTimersByTime(29_000); });
    expect(screen.getByTestId('gg-new-RIME')).toBeTruthy();
    act(() => { vi.advanceTimersByTime(2_000); });
    expect(screen.queryByTestId('gg-new-RIME')).toBeNull();
  });
});

/* ---- source guards ---- */

function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
}
/** Literal JSX text between tags (anything but whitespace and braces) — the component must have none. */
function jsxText(src: string): string[] {
  const out: string[] = [];
  const re = />([^<>{}]*)</g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(stripComments(src)))) if (m[1].trim()) out.push(m[1].trim());
  return out;
}
/** Every quoted / template literal whose whitespace-split tokens hold a typed word or a digit. */
function typedWords(src: string): string[] {
  const out: string[] = [];
  const re = /(['"`])((?:\\.|(?!\1)[^\\])*)\1/g;
  let m: RegExpExecArray | null;
  const body = stripComments(src).replace(/^import[^\n]*\n/gm, '');
  while ((m = re.exec(body))) {
    for (const tok of m[2].split(/\s+/)) {
      if (/^(A\+|ready|armed|new|ET|green)$/i.test(tok) || (/\d/.test(tok) && !/^\$\{/.test(tok))) out.push(tok);
    }
  }
  return out;
}

describe('GgEntryMarks.tsx — the FE types no word', () => {
  it('no JSX text, no typed mark word or digit in any literal', async () => {
    const src = await readSource('src/components/GgEntryMarks.tsx');
    expect(jsxText(src)).toEqual([]);
    expect(typedWords(src)).toEqual([]);
  });
  it('NEGATIVE: the guards catch a typed word', () => {
    expect(jsxText('const a = <span>new</span>;')).toEqual(['new']);
    expect(jsxText('const a = <b>A+ ready</b>;')).toEqual(['A+ ready']);
    expect(typedWords("const a = <span>{'armed'}</span>;")).toEqual(['armed']);
    expect(typedWords('const a = `new ${x} ET`;')).toEqual(['new', 'ET']);
    expect(typedWords("const a = 'in 30 minutes';")).toEqual(['30']);
  });
});

type Block = { prelude: string; body: string };
/** Top-level blocks of a stylesheet (comments stripped), braces balanced — an @media body is parsed by calling it again. */
function blocks(css: string): Block[] {
  const s = stripComments(css);
  const out: Block[] = [];
  let i = 0;
  while (i < s.length) {
    const open = s.indexOf('{', i);
    if (open < 0) break;
    let depth = 1;
    let j = open + 1;
    while (j < s.length && depth) { if (s[j] === '{') depth++; else if (s[j] === '}') depth--; j++; }
    out.push({ prelude: s.slice(i, open).trim(), body: s.slice(open + 1, j - 1) });
    i = j;
  }
  return out;
}
const decls = (body: string): Record<string, string> => Object.fromEntries(
  body.split(';').map((d) => d.trim()).filter(Boolean).map((d) => {
    const k = d.indexOf(':');
    return [d.slice(0, k).trim(), d.slice(k + 1).trim()];
  }));
const selectors = (prelude: string) => prelude.split(',').map((x) => x.trim());
const ruleOf = (bs: Block[], sel: string) => {
  const b = bs.find((x) => !x.prelude.startsWith('@') && selectors(x.prelude).includes(sel));
  return b ? decls(b.body) : null;
};
const media = (bs: Block[], query: RegExp) => bs.filter((b) => /^@media/.test(b.prelude) && query.test(b.prelude));

function noFontShorthand(css: string): boolean {
  return !blocks(css).some(function walk(b: Block): boolean {
    if (b.prelude.startsWith('@media')) return blocks(b.body).some(walk);
    if (b.prelude.startsWith('@keyframes')) return false;
    return Object.keys(decls(b.body)).includes('font');
  });
}
function badgeInPaddingBand(css: string): boolean {
  const bs = blocks(css);
  const g = ruleOf(bs, '.gg-sub-green');
  const n = ruleOf(bs, '.gg-sub-new');
  const chip = ruleOf(bs, '.gg-subs .cat-tab');
  return !!g && !!n && !!chip && chip.position === 'relative'
    && g.position === 'absolute' && g.top === '0' && g.height === '9px'
    && n.position === 'absolute' && n.top === '1px' && n.height === '7px';
}
function phoneRule(css: string): boolean {
  return media(blocks(css), /\(max-width:\s*720px\)/).some((m) => {
    const g = ruleOf(blocks(m.body), '.gg-sub-green');
    return !!g && g.height === '11px' && g['line-height'] === '11px';
  });
}
function reducedMotion(css: string): boolean {
  return media(blocks(css), /\(prefers-reduced-motion:\s*reduce\)/).some((m) => {
    const inner = blocks(m.body);
    return ['.gg-sub-new', '.gg-new-dot'].every((sel) => ruleOf(inner, sel)?.animation === 'none');
  });
}

describe('ggEntryMarks.css — longhands, padding band, phone, reduced motion (C3)', () => {
  const CSS = () => readSource('src/styles/ggEntryMarks.css');

  it('no font shorthand anywhere; the badge draws its label from data-label', async () => {
    const css = await CSS();
    expect(noFontShorthand(css)).toBe(true);
    expect(ruleOf(blocks(css), '.gg-sub-green::before')?.content).toBe('attr(data-label)');
  });
  it('NEGATIVE: a copy with `font: 700 10px/1 inherit` fails the guard (top level and inside @media)', async () => {
    const css = await CSS();
    expect(noFontShorthand(css.replace('font-family: inherit;', 'font: 700 10px/1 inherit;'))).toBe(false);
    expect(noFontShorthand(css.replace('font-size: 10px; }', 'font: 700 10px/1 inherit; }'))).toBe(false);
  });
  it('the badge and the dot are absolute in the chip top padding band (top 0 / 9px; top 1px / 7px)', async () => {
    expect(badgeInPaddingBand(await CSS())).toBe(true);
  });
  it('NEGATIVE: a copy without `position: absolute` (either one) fails', async () => {
    const css = await CSS();
    const firstAbs = css.indexOf('position: absolute;');
    expect(badgeInPaddingBand(css.slice(0, firstAbs) + css.slice(firstAbs + 'position: absolute;'.length))).toBe(false);
    const lastAbs = css.lastIndexOf('position: absolute;');
    expect(badgeInPaddingBand(css.slice(0, lastAbs) + css.slice(lastAbs + 'position: absolute;'.length))).toBe(false);
    expect(badgeInPaddingBand(css.replace('.gg-subs .cat-tab { position: relative; }', ''))).toBe(false);
  });
  it('the phone rule sits in @media (max-width: 720px): 11px badge', async () => {
    expect(phoneRule(await CSS())).toBe(true);
  });
  it('NEGATIVE: the 11px rule outside the 720px block fails', async () => {
    const css = await CSS();
    expect(phoneRule(css.split('@media (max-width: 720px)').join('@media (max-width: 640px)'))).toBe(false);
  });
  it('reduced motion turns the animation off on BOTH .gg-sub-new and .gg-new-dot', async () => {
    expect(reducedMotion(await CSS())).toBe(true);
  });
  it('NEGATIVE: a copy with the reduced-motion block removed fails; one selector dropped fails', async () => {
    const css = await CSS();
    const cut = css.replace(/@media \(prefers-reduced-motion: reduce\) \{[\s\S]*?\}\s*\}/, '');
    expect(cut).not.toContain('prefers-reduced-motion');
    expect(reducedMotion(cut)).toBe(false);
    expect(reducedMotion(css.replace('.gg-sub-new, .gg-new-dot { animation: none; }', '.gg-new-dot { animation: none; }'))).toBe(false);
  });
  it('phone: .gg-new-mark has min-width 0 and wraps', async () => {
    const r = ruleOf(blocks(await CSS()), '.gg-new-mark');
    expect(r?.['min-width']).toBe('0');
    expect(r?.['white-space']).toBe('normal');
    expect(r?.['overflow-wrap']).toBe('anywhere');
  });
});

describe('live patch keeps the served mark', () => {
  it('a tile through cardLive.patchTiles keeps new_mark (the patched tile is a new object)', () => {
    const tile: any = { symbol: 'RIME', bars: [{ t: '2026-11-12T15:00', o: 1, h: 1, l: 1, c: 1, v: 1 }], lines: [], new_mark: MARK };
    const answer = {
      session: null, as_of_epoch: 0, as_of: '', footer: { live: null, stale: null }, now_labels: [], cap: 1, asked: 1,
      served: 1, missing: [], fault: null,
      quotes: { RIME: { bar: null, prev_t: null, now: { price: 2, label: 'now', session: null, add_line: true, as_of_epoch: null, as_of: null } } },
    } as CardLiveAnswer;
    const [out] = patchTiles([tile], answer);
    expect(out).not.toBe(tile);
    expect((out as any).lines).toHaveLength(1);
    expect((out as any).new_mark).toEqual(MARK);
  });
});
