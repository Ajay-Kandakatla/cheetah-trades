/* 🧘 GgLike components (2026-11-27, spec gglike §3.9, WP fe-core).
 *
 * Every piece prints served strings only: the chip (hover = served title), the check list (closed until the chip is
 * tapped; ⓘ info rows muted, never the ✗ class), the toggle with the live count, the count line (nothing while OFF),
 * the fold note (note, separation, census, then the rows). Source guards: the component and lib files type no served
 * word; the sheet wraps on a 430 px phone. Strings are stand-ins shaped like the served ones (spec §3.5). */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GgLikeCard, GgLikeChip, GgLikeHiddenLine, GgLikeList, GgLikeNote, GgLikeToggle } from './GgLike';
import { ggLikeSplit, parseGgLike, parseGgLikeBoard } from '../lib/ggLike';
import type { GgLike, GgLikeBoard } from '../lib/ggLike';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const code = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1');
const literals = (src: string) => [...src.matchAll(/'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`/g)].map((m) => m[0]);
const SERVED_CS = /GG-like|\bEMA\b/;
const SERVED_CI = /tennis|(^|[^-\w])hidden($|[^-\w])|still shown|show all|can.t tell|under high|unmeasured|observed|\brang\b|alert/i;
const typed = (src: string) => literals(code(src)).some((l) => SERVED_CS.test(l) || SERVED_CI.test(l));
function rule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}

const NOT_RAW = {
  verdict: 'not', tone: 'no', chip: 'S-CHIP-NOT', title: 'S-TITLE-NOT',
  reason: { code: 'near_high', label: 'S-REASON' }, keep: false,
  checks: [
    { key: 'base_bars', ok: true, info: false, mark: '✓', label: 'S-L-BASE', value: 'S-V-BASE', need: 'S-N-BASE' },
    { key: 'lower_highs', ok: null, info: true, mark: 'ⓘ', label: 'S-L-INFO', value: 'S-V-INFO', need: null },
    { key: 'near_high', ok: false, info: false, mark: '✗', label: 'S-L-HIGH', value: 'S-V-HIGH', need: 'S-N-HIGH' },
    { key: 'tennis_drop', ok: null, info: false, mark: 'n/a', label: 'S-L-TEN', value: 'S-V-TEN', need: 'S-N-TEN' },
  ],
  info: 'S-INFO', source: 'ring', source_text: 'S-SOURCE',
};
const NOT = parseGgLike(NOT_RAW) as GgLike;
const OK = parseGgLike({ ...NOT_RAW, verdict: 'gg_like', tone: 'ok', chip: 'S-CHIP-OK', reason: null, info: null, source_text: null }) as GgLike;
const BOARD = parseGgLikeBoard({
  label: 'S-LABEL', label_n_text: '{label} · {n}', hint: 'S-HINT', hidden_text: '{n} S-HID', reason_text: '{n} {label}',
  kept_text: '{n} S-KEPT', unknown_text: '{n} S-UNK', none_text: '{n} S-NONE', all_hidden_text: 'S-ALL-HIDDEN',
  show_all_text: 'S-SHOW-ALL', note: 'S-NOTE', separation_text: 'S-SEP', census_text: 'S-CENSUS', rows: ['S-ROW-1', 'S-ROW-2'],
}) as GgLikeBoard;

afterEach(() => cleanup());

describe('GgLikeChip', () => {
  it('a span without onToggle: served chip text, served title, tone class', () => {
    render(<GgLikeChip like={NOT} sym="DKI" />);
    const el = screen.getByTestId('gg-like-chip-DKI');
    expect(el.tagName).toBe('SPAN');
    expect(el.textContent).toBe('S-CHIP-NOT');
    expect(el.getAttribute('title')).toBe('S-TITLE-NOT');
    expect(el.className).toBe('gg-like-chip gg-like-no');
    expect(el.hasAttribute('aria-expanded')).toBe(false);
  });
  it('a button with onToggle: aria-expanded follows open, click calls onToggle', () => {
    const f = vi.fn();
    const { rerender } = render(<GgLikeChip like={OK} sym="ABC" onToggle={f} />);
    const el = screen.getByTestId('gg-like-chip-ABC');
    expect(el.tagName).toBe('BUTTON');
    expect(el.className).toBe('gg-like-chip gg-like-ok');
    expect(el.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(el);
    expect(f).toHaveBeenCalledTimes(1);
    rerender(<GgLikeChip like={OK} sym="ABC" open onToggle={f} />);
    expect(screen.getByTestId('gg-like-chip-ABC').getAttribute('aria-expanded')).toBe('true');
  });
  it('NEGATIVE: a null title sets no title attribute', () => {
    render(<GgLikeChip like={{ ...NOT, title: null }} sym="X" />);
    expect(screen.getByTestId('gg-like-chip-X').hasAttribute('title')).toBe(false);
  });
});

describe('GgLikeList', () => {
  it('counted rows in served order, then info rows, then info, source text and note', () => {
    render(<GgLikeList like={NOT} sym="DKI" note="S-EXTRA" />);
    const list = screen.getByTestId('gg-like-list-DKI');
    const keys = [...list.querySelectorAll('li')].map((li) => li.getAttribute('data-gg-like-key'));
    expect(keys).toEqual(['base_bars', 'near_high', 'tennis_drop', 'lower_highs']);
    const lines = [...list.querySelectorAll('p')].map((p) => p.textContent);
    expect(lines).toEqual(['S-INFO', 'S-SOURCE', 'S-EXTRA']);
    expect(list.textContent).toContain('S-V-HIGH');
    expect(list.textContent).toContain('S-N-HIGH');
  });
  it('row classes: ✓ ok, ✗ no, n/a na — marks served', () => {
    render(<GgLikeList like={NOT} sym="DKI" />);
    const li = (k: string) => screen.getByTestId('gg-like-list-DKI').querySelector(`[data-gg-like-key="${k}"]`)!;
    expect(li('base_bars').className).toBe('gg-like-row gg-like-row--ok');
    expect(li('near_high').className).toBe('gg-like-row gg-like-row--no');
    expect(li('tennis_drop').className).toBe('gg-like-row gg-like-row--na');
    expect(li('near_high').querySelector('.gg-like-mark')!.textContent).toBe('✗');
    expect(li('tennis_drop').querySelector('.gg-like-mark')!.textContent).toBe('n/a');
  });
  it('[C4] an info row draws ⓘ and the muted info class, never the ✗ class — even when served ok:false', () => {
    const lk = { ...NOT, checks: [{ key: 'lower_highs', ok: false, info: true, mark: '✗', label: 'S-L-INFO', value: '3', need: null }] };
    render(<GgLikeList like={lk} sym="I" />);
    const li = screen.getByTestId('gg-like-list-I').querySelector('li')!;
    expect(li.className).toBe('gg-like-row gg-like-row--info');
    expect(li.className).not.toMatch(/--no/);
    expect(li.querySelector('.gg-like-mark')!.textContent).toBe('ⓘ');
  });
  it('NEGATIVE: no info / source / note → no extra lines; null value / need draw no span', () => {
    render(<GgLikeList like={OK} sym="OK" />);
    const list = screen.getByTestId('gg-like-list-OK');
    expect(list.querySelectorAll('p')).toHaveLength(0);
    const info = list.querySelector('[data-gg-like-key="lower_highs"]')!;
    expect(info.querySelector('.gg-like-need')).toBeNull();
  });
});

describe('GgLikeCard', () => {
  it('the list is closed until the chip is tapped, and closes again', () => {
    render(<GgLikeCard like={NOT} sym="DKI" note="S-EXTRA" />);
    expect(screen.queryByTestId('gg-like-list-DKI')).toBeNull();
    const chip = screen.getByTestId('gg-like-chip-DKI');
    expect(chip.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(chip);
    expect(screen.getByTestId('gg-like-list-DKI').textContent).toContain('S-EXTRA');
    expect(chip.getAttribute('aria-expanded')).toBe('true');
    fireEvent.click(chip);
    expect(screen.queryByTestId('gg-like-list-DKI')).toBeNull();
  });
  it('one chip, no other visible text while closed', () => {
    render(<GgLikeCard like={NOT} sym="DKI" />);
    expect(screen.getByTestId('gg-like-card-DKI').textContent).toBe('S-CHIP-NOT');
  });
  it('NEGATIVE: a null block draws nothing', () => {
    const { container } = render(<div className="pills"><b>X</b><GgLikeCard like={null} sym="N" /></div>);
    expect(container.innerHTML).toBe('<div class="pills"><b>X</b></div>');
  });
});

describe('GgLikeToggle', () => {
  it('a cm-phase-btn with the served label and the live count, aria-pressed, served hint', () => {
    const f = vi.fn();
    const { rerender } = render(<GgLikeToggle board={BOARD} n={0} on={false} onToggle={f} testid="t" />);
    const b = screen.getByTestId('t');
    expect(b.tagName).toBe('BUTTON');
    expect(b.textContent).toBe('S-LABEL · 0');
    expect(b.className).toBe('cm-phase-btn gg-like-toggle');
    expect(b.getAttribute('aria-pressed')).toBe('false');
    expect(b.getAttribute('title')).toBe('S-HINT');
    fireEvent.click(b);
    expect(f).toHaveBeenCalledTimes(1);
    rerender(<GgLikeToggle board={BOARD} n={6} on onToggle={f} testid="t" />);
    expect(screen.getByTestId('t').textContent).toBe('S-LABEL · 6');
    expect(screen.getByTestId('t').className).toBe('cm-phase-btn gg-like-toggle cm-phase-on');
    expect(screen.getByTestId('t').getAttribute('aria-pressed')).toBe('true');
  });
  it('NEGATIVE: no label_n_text → the bare served label', () => {
    render(<GgLikeToggle board={{ ...BOARD, label_n_text: null, hint: null }} n={3} on={false} onToggle={() => {}} testid="t" />);
    expect(screen.getByTestId('t').textContent).toBe('S-LABEL');
    expect(screen.getByTestId('t').hasAttribute('title')).toBe(false);
  });
});

describe('GgLikeHiddenLine', () => {
  const rows = [{ s: 'A', g: NOT }, { s: 'B', g: { ...NOT, keep: true } }, { s: 'C', g: null }];
  const of = (r: { g: GgLike | null }) => r.g;

  it('ON: the served count line and the served show all button', () => {
    const f = vi.fn();
    render(<GgLikeHiddenLine board={BOARD} split={ggLikeSplit(rows, of, true)} onShowAll={f} testid="h" />);
    expect(screen.getByTestId('h').textContent).toContain('1 S-HID (1 S-REASON) · 1 S-KEPT · 1 S-NONE');
    fireEvent.click(screen.getByTestId('h-show-all'));
    expect(f).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('h-show-all').textContent).toBe('S-SHOW-ALL');
  });
  it('[C3] every card hidden → the line starts with all_hidden_text and still offers show all', () => {
    render(<GgLikeHiddenLine board={BOARD} split={ggLikeSplit([{ s: 'A', g: NOT }], of, true)} onShowAll={() => {}} testid="h" />);
    expect(screen.getByTestId('h').querySelector('.gg-like-hidden-line')!.textContent!.startsWith('S-ALL-HIDDEN')).toBe(true);
    expect(screen.getByTestId('h-show-all')).toBeTruthy();
  });
  it('[T10] ON with nothing hidden, kept, can\'t-tell or unchecked → show all is still drawn, no invented line words', () => {
    const f = vi.fn();
    const all = [{ s: 'A', g: OK }];
    render(<GgLikeHiddenLine board={BOARD} split={ggLikeSplit(all, of, true)} onShowAll={f} testid="h" on />);
    const h = screen.getByTestId('h');
    expect(h.querySelector('.gg-like-hidden-line')).toBeNull();
    expect(h.textContent).toBe('S-SHOW-ALL');
    fireEvent.click(screen.getByTestId('h-show-all'));
    expect(f).toHaveBeenCalledTimes(1);
  });
  it('[T10] ON with an EMPTY board → show all is still drawn', () => {
    render(<GgLikeHiddenLine board={BOARD} split={ggLikeSplit([] as { g: GgLike | null }[], of, true)} onShowAll={() => {}} testid="h" on />);
    expect(screen.getByTestId('h-show-all').textContent).toBe('S-SHOW-ALL');
  });
  it('NEGATIVE [T10]: the same empty-line split WITHOUT on, or with on={false}, draws nothing', () => {
    const all = [{ s: 'A', g: OK }];
    const a = render(<div><GgLikeHiddenLine board={BOARD} split={ggLikeSplit(all, of, true)} onShowAll={() => {}} testid="h" /></div>);
    expect(a.container.innerHTML).toBe('<div></div>');
    a.unmount();
    const b = render(<div><GgLikeHiddenLine board={BOARD} split={ggLikeSplit(all, of, true)} onShowAll={() => {}} testid="h" on={false} /></div>);
    expect(b.container.innerHTML).toBe('<div></div>');
  });
  it('NEGATIVE: renders nothing while OFF', () => {
    const { container } = render(<div><GgLikeHiddenLine board={BOARD} split={ggLikeSplit(rows, of, false)} onShowAll={() => {}} testid="h" /></div>);
    expect(container.innerHTML).toBe('<div></div>');
  });
});

describe('GgLikeNote', () => {
  it('[C3, C5] prints note, separation_text, census_text, then the rows, in that order', () => {
    render(<GgLikeNote board={BOARD} testid="n" />);
    const n = screen.getByTestId('n');
    const texts = [...n.querySelectorAll('p, li')].map((e) => e.textContent);
    expect(texts).toEqual(['S-NOTE', 'S-SEP', 'S-CENSUS', 'S-ROW-1', 'S-ROW-2']);
  });
  it('NEGATIVE: null sentences are skipped; nothing served → nothing drawn', () => {
    render(<GgLikeNote board={{ ...BOARD, separation_text: null }} testid="n" />);
    expect(screen.getByTestId('n').textContent).not.toContain('S-SEP');
    cleanup();
    const { container } = render(<div><GgLikeNote board={{ ...BOARD, note: null, separation_text: null, census_text: null, rows: [] }} testid="n" /></div>);
    expect(container.innerHTML).toBe('<div></div>');
  });
});

describe('source guards', () => {
  const FE = ['src/components/GgLike.tsx', 'src/lib/ggLike.ts'];

  it('the component and lib files type no served word in a string literal', async () => {
    for (const f of FE) expect(typed(await readSource(f)), f).toBe(false);
  });
  it('no b-word and no email in the new files', async () => {
    for (const f of [...FE, 'src/styles/ggLike.css', 'src/lib/ggLike.test.ts', 'src/components/GgLike.test.tsx']) {
      const src = await readSource(f);
      expect(src, f).not.toMatch(new RegExp('boun' + 'c', 'i'));
      expect(src, f).not.toMatch(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/);
    }
  });
  it('the component file never mentions the Watch key', async () => {
    for (const f of FE) expect(await readSource(f), f).not.toMatch(/gg-like-only:watch/);
  });
  it('NEGATIVE: the guard fires on a file that types a served word', () => {
    for (const w of ["'🧘 GG-like'", "'8% tennis ball'", "'under 21 EMA'", "'3 hidden'", "'still shown'", "'show all'",
      "\"can't tell\"", "'23% under high'", "'UNMEASURED'"]) {
      expect(typed(`const x = ${w};`), w).toBe(true);
    }
    expect(typed('/* 🧘 GG-like, tennis, EMA, hidden */ const y = 1;')).toBe(false);
    expect(typed("// GG-like tennis\nconst c = 'gg-like-chip'; const k = 'gg-like-only:board';")).toBe(false);
    expect(typed('<span aria-hidden="true" className="gg-like-hidden gg-like-hidden-line" />')).toBe(false);
  });
});

describe('📱 CSS wrap guard (430 px)', () => {
  it('.gg-like-chip wraps: white-space normal, overflow-wrap anywhere, min-width 0, max-width 100%', async () => {
    const chip = rule(await readSource('src/styles/ggLike.css'), '.gg-like-chip');
    expect(chip).not.toBeNull();
    expect(chip).toMatch(/white-space:\s*normal/);
    expect(chip).toMatch(/overflow-wrap:\s*anywhere/);
    expect(chip).toMatch(/min-width:\s*0\b/);
    expect(chip).toMatch(/max-width:\s*100%/);
  });
  it('list rows wrap; the info row is muted; no nowrap anywhere in the sheet', async () => {
    const css = await readSource('src/styles/ggLike.css');
    expect(rule(css, '.gg-like-row')).toMatch(/flex-wrap:\s*wrap/);
    expect(rule(css, '.gg-like-row')).toMatch(/overflow-wrap:\s*anywhere/);
    expect(rule(css, '.gg-like-row--info')).toMatch(/--ink-subtle/);
    expect(css).not.toMatch(/nowrap/);
  });
  it('the component imports its own sheet', async () => {
    expect(await readSource('src/components/GgLike.tsx')).toContain("import '../styles/ggLike.css';");
  });
  it('NEGATIVE: the guard fails on a sheet that sets nowrap on the chip or has no wrap rule', () => {
    const BAD = '.gg-like-chip { white-space: nowrap; }';
    expect(rule(BAD, '.gg-like-chip')).not.toMatch(/white-space:\s*normal/);
    expect(BAD).toMatch(/nowrap/);
    expect(rule('.other { x: 1 }', '.gg-like-chip')).toBeNull();
  });
});
