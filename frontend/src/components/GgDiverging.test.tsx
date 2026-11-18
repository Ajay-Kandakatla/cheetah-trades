import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

/* 🌱 GgDivergingPanel (2026-11-18, diverging spec §3.9 / §4 WP-B). Ajay: "For the divergence thing create a separate tab
 * that are potentially diverging with uptrend and volume breakout." Every string below is a SENTINEL ("served …") — the
 * component types no word (the ⓘ fallback summary aside), so every assertion compares the DOM to the served value.
 * NEGATIVES: a null / undefined block prints nothing; NaN / number / '' texts print nothing; bars_text null → no node;
 * the empty line only when n === 0; no FE-typed sentence; no b-word in the source. */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));

import { GgDivergingPanel } from './GgDiverging';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const clone = (x: any) => JSON.parse(JSON.stringify(x));

const DG_BLOCK = {
  title: 'served dg title', ask_text: 'served his words', pick_texts: ['served pick one', 'served pick two'],
  rule_label: 'served rule label', rule_text: 'served rule text', honesty: 'served honesty',
  cohort_text: 'served cohort', window_text: 'served window', bars_text: 'served bars line', order_note: 'served order',
  n: 1, n_read: 73, faults_text: null, empty_text: 'served empty', chartless: [],
};
const SERVED = (b: any): string[] => [b.title, b.ask_text, ...(b.pick_texts || []), b.cohort_text, b.window_text, b.bars_text,
  b.order_note, b.n === 0 ? b.empty_text : null, ...(b.chartless || []).map((c: any) => c.state_label), b.faults_text,
  b.rule_label, b.rule_text, b.honesty].filter((x) => typeof x === 'string');
const wrap = { wrapper: ({ children }: any) => <MemoryRouter>{children}</MemoryRouter> };
const tids = (c: HTMLElement) => [...c.querySelectorAll('[data-testid^="gg-dg"]')].map((e) => e.getAttribute('data-testid'));

afterEach(() => { vi.restoreAllMocks(); });

describe('🌱 GgDivergingPanel', () => {
  it('prints every served line verbatim in order: title → ask → picks → cohort → window → bars → order → rule → honesty LAST', () => {
    const { container } = render(<GgDivergingPanel block={clone(DG_BLOCK)} />, wrap);
    expect(screen.getByTestId('gg-dg-title').tagName).toBe('H3');
    expect(screen.getByTestId('gg-dg-title').textContent).toBe('served dg title');
    expect(screen.getByTestId('gg-dg-ask').tagName).toBe('BLOCKQUOTE');
    expect(screen.getByTestId('gg-dg-ask').textContent).toBe('served his words');
    expect(screen.getByTestId('gg-dg-pick-0').tagName).toBe('BLOCKQUOTE');
    expect(screen.getByTestId('gg-dg-pick-0').textContent).toBe('served pick one');
    expect(screen.getByTestId('gg-dg-pick-1').textContent).toBe('served pick two');
    expect(screen.getByTestId('gg-dg-cohort').textContent).toBe('served cohort');
    expect(screen.getByTestId('gg-dg-window').textContent).toBe('served window');
    expect(screen.getByTestId('gg-dg-bars').textContent).toBe('served bars line');
    expect(screen.getByTestId('gg-dg-order').textContent).toBe('served order');
    const rule = screen.getByTestId('gg-dg-rule');
    expect(rule.tagName).toBe('DETAILS');
    expect(rule.hasAttribute('open')).toBe(false);
    expect(rule.querySelector('summary')!.textContent).toBe('served rule label');
    expect(rule.querySelector('p')!.textContent).toBe('served rule text');
    expect(screen.getByTestId('gg-dg-honesty').textContent).toBe('served honesty');
    expect(tids(container)).toEqual(['gg-dg', 'gg-dg-title', 'gg-dg-ask', 'gg-dg-pick-0', 'gg-dg-pick-1', 'gg-dg-cohort',
      'gg-dg-window', 'gg-dg-bars', 'gg-dg-order', 'gg-dg-rule', 'gg-dg-honesty']);
    const panel = screen.getByTestId('gg-dg');
    expect(panel.className).toBe('gg-dv');
    expect(panel.lastElementChild!.getAttribute('data-testid')).toBe('gg-dg-honesty');
  });

  it('NEGATIVE: no FE-typed sentence — the rendered text minus the served strings is empty', () => {
    const b = { ...clone(DG_BLOCK), chartless: [{ symbol: 'ZZZ', at_text: 'x', state_label: 'served chartless', href: null }],
      faults_text: 'served faults' };
    render(<GgDivergingPanel block={b} />, wrap);
    let text = screen.getByTestId('gg-dg').textContent || '';
    for (const s of SERVED(b).sort((x, y) => y.length - x.length)) text = text.split(s).join('');
    expect(text.trim()).toBe('');
  });

  it('bars_text: printed only when a string; NEGATIVE null / NaN / number / "" → no gg-dg-bars node', () => {
    for (const v of [null, undefined, NaN, 3, '', '   ']) {
      const { unmount } = render(<GgDivergingPanel block={{ ...clone(DG_BLOCK), bars_text: v as any }} />, wrap);
      expect(screen.queryByTestId('gg-dg-bars'), String(v)).toBeNull();
      expect(screen.getByTestId('gg-dg-window').textContent).toBe('served window');
      unmount();
    }
  });

  it('NEGATIVE: a null / undefined / non-object block draws nothing', () => {
    for (const b of [null, undefined, 'served', 7] as any[]) {
      const { container, unmount } = render(<GgDivergingPanel block={b} />, wrap);
      expect(container.innerHTML, String(b)).toBe('');
      unmount();
    }
  });

  it('NEGATIVE: NaN / number / "" / undefined texts print nothing — never "NaN" or "undefined"', () => {
    const b = { ...clone(DG_BLOCK), title: NaN, ask_text: 5, pick_texts: [NaN, '', 'served pick ok', 7], cohort_text: '',
      window_text: undefined, order_note: null, honesty: NaN, faults_text: 0, rule_text: NaN };
    render(<GgDivergingPanel block={b as any} />, wrap);
    for (const t of ['gg-dg-title', 'gg-dg-ask', 'gg-dg-cohort', 'gg-dg-window', 'gg-dg-order', 'gg-dg-honesty',
      'gg-dg-faults', 'gg-dg-rule', 'gg-dg-pick-1']) expect(screen.queryByTestId(t), t).toBeNull();
    expect(screen.getByTestId('gg-dg-pick-0').textContent).toBe('served pick ok');
    expect(screen.getByTestId('gg-dg').textContent).not.toMatch(/NaN|undefined|null/);
  });

  it('pick_texts not a list → no pick lines', () => {
    render(<GgDivergingPanel block={{ ...clone(DG_BLOCK), pick_texts: 'served pick' as any }} />, wrap);
    expect(screen.queryByTestId(/^gg-dg-pick-/)).toBeNull();
  });

  it('the rule folds under ⓘ when no label is served; NEGATIVE no rule_text → no fold', () => {
    const { unmount } = render(<GgDivergingPanel block={{ ...clone(DG_BLOCK), rule_label: null }} />, wrap);
    expect(screen.getByTestId('gg-dg-rule').querySelector('summary')!.textContent).toBe('ⓘ');
    unmount();
    render(<GgDivergingPanel block={{ ...clone(DG_BLOCK), rule_text: null }} />, wrap);
    expect(screen.queryByTestId('gg-dg-rule')).toBeNull();
  });

  it('n === 0 + empty_text → the served empty line; NEGATIVE n === 1, or a chartless line, → no empty line', () => {
    const { unmount } = render(<GgDivergingPanel block={{ ...clone(DG_BLOCK), n: 0 }} />, wrap);
    expect(screen.getByTestId('gg-dg-empty').textContent).toBe('served empty');
    unmount();
    const r1 = render(<GgDivergingPanel block={clone(DG_BLOCK)} />, wrap);
    expect(screen.queryByTestId('gg-dg-empty')).toBeNull();
    r1.unmount();
    render(<GgDivergingPanel block={{ ...clone(DG_BLOCK), n: 0,
      chartless: [{ symbol: 'ZZZ', at_text: 'x', state_label: 'served chartless ZZZ', href: null }] }} />, wrap);
    expect(screen.queryByTestId('gg-dg-empty')).toBeNull();
    expect(screen.getByTestId('gg-dg-chartless-ZZZ').textContent).toBe('served chartless ZZZ');
  });

  it('chartless: a served href → a Link; NEGATIVE an unsafe href → plain text; a row with no state_label → nothing', () => {
    const b = { ...clone(DG_BLOCK), chartless: [
      { symbol: 'AAA', at_text: 'x', state_label: 'served chartless AAA', href: '/sepa/AAA?tab=supply' },
      { symbol: 'BBB', at_text: 'x', state_label: 'served chartless BBB', href: 'javascript:alert(1)' },
      { symbol: 'CCC', at_text: 'x', state_label: NaN, href: '/sepa/CCC' },
      null,
    ] };
    render(<GgDivergingPanel block={b as any} />, wrap);
    expect(screen.getByTestId('gg-dg-chartless-AAA').querySelector('a')!.getAttribute('href')).toBe('/sepa/AAA?tab=supply');
    expect(screen.getByTestId('gg-dg-chartless-BBB').querySelector('a')).toBeNull();
    expect(screen.getByTestId('gg-dg-chartless-BBB').textContent).toBe('served chartless BBB');
    expect(screen.queryByTestId('gg-dg-chartless-CCC')).toBeNull();
  });

  it('faults_text prints when served; NEGATIVE absent → no node', () => {
    const { unmount } = render(<GgDivergingPanel block={{ ...clone(DG_BLOCK), faults_text: 'served faults' }} />, wrap);
    expect(screen.getByTestId('gg-dg-faults').textContent).toBe('served faults');
    unmount();
    render(<GgDivergingPanel block={clone(DG_BLOCK)} />, wrap);
    expect(screen.queryByTestId('gg-dg-faults')).toBeNull();
  });

  it('NEGATIVE source guards: no b-word, no number formatting, its own servedText guard, nothing from the board', async () => {
    const src = await readSource('src/components/GgDiverging.tsx');
    expect(src).not.toMatch(/bounc/i);
    expect(src).not.toMatch(/toFixed\(|toLocaleString\(/);
    expect(src).toMatch(/function servedText\(v: unknown\): v is string \{/);
    expect(src).not.toMatch(/from '\.\/GajjalaBoard'/);
    expect(src).toMatch(/className="gg-dv"/);
    expect(src).not.toMatch(/gg-dg-[a-z]+"[^>]*>[A-Za-z]/);
  });
});
