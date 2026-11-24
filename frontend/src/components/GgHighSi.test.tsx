import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { GgBoard, GgHighSiBlock } from '../lib/gajjala';

/* 🩳 GgHighSiPanel (2026-11-23, high SI spec §3.8 / §4 WP fe-sub). Ajay: "Can you create a tab similarly like Divergent with
 * high charging tested, SHO tag, and low floats similar to what we've done in Divergent tab under Gazilla?" [voice typing:
 * "high charging tested" = high short interest, "Gazilla" = Gajjala] · "New tab like divergence*".
 * Every string below is a SENTINEL ("served …") — the component types no word (the ⓘ fallback summary aside), so every
 * assertion compares the DOM to the served value. NEGATIVES: a null / undefined / non-object block prints nothing; NaN /
 * number / '' / undefined texts print nothing (the three new lines — adds, disagree, no tier — included); the empty line
 * only when n === 0 and no chartless line; the push sentence printed as served whatever it says; no digit typed in the
 * component; no b-word. */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));

import { GgHighSiPanel } from './GgHighSi';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const clone = (x: any) => JSON.parse(JSON.stringify(x));

const HS_BLOCK: GgHighSiBlock = {
  title: 'served hs title', ask_text: 'served his words', rule_label: 'served rule label', rule_text: 'served rule text',
  honesty: 'served honesty', cohort_text: 'served cohort', counts_text: 'served counts', adds_text: 'served adds',
  asof_text: 'served as of', sho_text: 'served sho', push_text: 'served push off sentence', order_note: 'served order',
  shown_text: 'served shown', excluded_text: 'served excluded', disagree_text: 'served disagree',
  no_tier_text: 'served no tier', n: 3, n_read: 102, faults_text: null, empty_text: 'served empty', chartless: [],
};
/* Type pin: the board carries the block under `high_si` (null on a fault, absent on an older API). */
const _boardPin: Pick<GgBoard, 'high_si'>[] = [{ high_si: HS_BLOCK }, { high_si: null }, {}];
void _boardPin;

const SERVED = (b: any): string[] => [b.title, b.ask_text, b.counts_text, b.adds_text, b.asof_text, b.sho_text, b.push_text,
  b.order_note, b.shown_text, b.n === 0 ? b.empty_text : null, ...(b.chartless || []).map((c: any) => (typeof c?.text === 'string' && c.text.trim() ? c.text : c?.state_label)),
  b.faults_text, b.rule_label, b.rule_text, b.cohort_text, b.excluded_text, b.disagree_text, b.no_tier_text, b.honesty]
  .filter((x) => typeof x === 'string');
const wrap = { wrapper: ({ children }: any) => <MemoryRouter>{children}</MemoryRouter> };
const tids = (c: HTMLElement) => [...c.querySelectorAll('[data-testid^="gg-hs"]')].map((e) => e.getAttribute('data-testid'));
const ALWAYS = ['gg-hs-title', 'gg-hs-ask', 'gg-hs-counts', 'gg-hs-adds', 'gg-hs-asof', 'gg-hs-sho', 'gg-hs-push',
  'gg-hs-order', 'gg-hs-shown'];
const FOLDED = ['gg-hs-rule-text', 'gg-hs-cohort', 'gg-hs-excluded', 'gg-hs-disagree', 'gg-hs-notier'];

afterEach(() => { vi.restoreAllMocks(); });

describe('🩳 GgHighSiPanel', () => {
  it('prints every served line verbatim in order: title → ask → counts → adds → as-of → 🔒 → push → order → shown → rule fold → honesty LAST', () => {
    const { container } = render(<GgHighSiPanel block={clone(HS_BLOCK)} />, wrap);
    expect(screen.getByTestId('gg-hs-title').tagName).toBe('H3');
    expect(screen.getByTestId('gg-hs-title').textContent).toBe('served hs title');
    expect(screen.getByTestId('gg-hs-ask').tagName).toBe('BLOCKQUOTE');
    expect(screen.getByTestId('gg-hs-ask').textContent).toBe('served his words');
    expect(screen.getByTestId('gg-hs-counts').textContent).toBe('served counts');
    expect(screen.getByTestId('gg-hs-adds').textContent).toBe('served adds');
    expect(screen.getByTestId('gg-hs-asof').textContent).toBe('served as of');
    expect(screen.getByTestId('gg-hs-sho').textContent).toBe('served sho');
    expect(screen.getByTestId('gg-hs-push').textContent).toBe('served push off sentence');
    expect(screen.getByTestId('gg-hs-order').textContent).toBe('served order');
    expect(screen.getByTestId('gg-hs-shown').textContent).toBe('served shown');
    const rule = screen.getByTestId('gg-hs-rule');
    expect(rule.tagName).toBe('DETAILS');
    expect(rule.hasAttribute('open')).toBe(false);
    expect(rule.querySelector('summary')!.textContent).toBe('served rule label');
    expect(screen.getByTestId('gg-hs-rule-text').textContent).toBe('served rule text');
    expect(screen.getByTestId('gg-hs-honesty').textContent).toBe('served honesty');
    expect(tids(container)).toEqual(['gg-hs', ...ALWAYS, 'gg-hs-rule', ...FOLDED, 'gg-hs-honesty']);
    const panel = screen.getByTestId('gg-hs');
    expect(panel.className).toBe('gg-dv');
    expect(panel.tagName).toBe('SECTION');
    expect(panel.lastElementChild!.getAttribute('data-testid')).toBe('gg-hs-honesty');
  });

  it('the always-visible lines sit OUTSIDE the <details>; the rule, the cohort and the three name lists sit INSIDE it', () => {
    render(<GgHighSiPanel block={clone(HS_BLOCK)} />, wrap);
    const rule = screen.getByTestId('gg-hs-rule');
    for (const t of [...ALWAYS, 'gg-hs-honesty']) expect(rule.contains(screen.getByTestId(t)), t).toBe(false);
    for (const t of FOLDED) expect(rule.contains(screen.getByTestId(t)), t).toBe(true);
    // the three name lists come in the served order: over the cap → the floats disagree → no tier word
    const inner = [...rule.querySelectorAll('[data-testid]')].map((e) => e.getAttribute('data-testid'));
    expect(inner).toEqual(FOLDED);
  });

  it('gg-hs-adds is ALWAYS visible (outside the fold) and printed verbatim', () => {
    render(<GgHighSiPanel block={{ ...clone(HS_BLOCK), adds_text: 'served of the 3 listed here: 2 qualified today · 1 carried' }} />, wrap);
    const adds = screen.getByTestId('gg-hs-adds');
    expect(adds.textContent).toBe('served of the 3 listed here: 2 qualified today · 1 carried');
    expect(adds.closest('details')).toBeNull();
    expect(screen.getByTestId('gg-hs-counts').compareDocumentPosition(adds) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('the push sentence prints as served — the 🔕 off line and the 🔔 live line alike, never rewritten', () => {
    const off = '🔕 served no phone alert rings from this list — the cross push is switched off.';
    const live = '🔔 served rings your phone on a cross above … UNMEASURED — information only, not an entry. Not advice.';
    for (const p of [off, live]) {
      const { unmount } = render(<GgHighSiPanel block={{ ...clone(HS_BLOCK), push_text: p }} />, wrap);
      expect(screen.getByTestId('gg-hs-push').textContent).toBe(p);
      expect(screen.getByTestId('gg-hs-push').closest('details')).toBeNull();
      unmount();
    }
    // NEGATIVE: no push sentence served → no push line (the panel never composes one)
    render(<GgHighSiPanel block={{ ...clone(HS_BLOCK), push_text: null }} />, wrap);
    expect(screen.queryByTestId('gg-hs-push')).toBeNull();
  });

  it('NEGATIVE: no FE-typed sentence — the rendered text minus the served strings is empty', () => {
    const b = { ...clone(HS_BLOCK), chartless: [{ symbol: 'ZZZ', at_text: 'x', state_label: 'served chartless', href: null }],
      faults_text: 'served faults' };
    render(<GgHighSiPanel block={b} />, wrap);
    let text = screen.getByTestId('gg-hs').textContent || '';
    for (const s of SERVED(b).sort((x, y) => y.length - x.length)) text = text.split(s).join('');
    expect(text.trim()).toBe('');
  });

  it('NEGATIVE: a null / undefined / non-object block draws nothing', () => {
    for (const b of [null, undefined, 'served', 7, NaN, true] as any[]) {
      const { container, unmount } = render(<GgHighSiPanel block={b} />, wrap);
      expect(container.innerHTML, String(b)).toBe('');
      unmount();
    }
  });

  it('NEGATIVE: an empty object block draws only the bare root — no line, no fold, no "undefined"', () => {
    const { container } = render(<GgHighSiPanel block={{}} />, wrap);
    expect(tids(container)).toEqual(['gg-hs']);
    expect(screen.getByTestId('gg-hs').textContent).toBe('');
  });

  it('NEGATIVE: NaN / number / "" / undefined texts print nothing — never "NaN" or "undefined" (the three new lines included)', () => {
    const b = { ...clone(HS_BLOCK), title: NaN, ask_text: 5, counts_text: '', adds_text: NaN, asof_text: undefined,
      sho_text: '   ', push_text: 0, order_note: null, shown_text: NaN, honesty: NaN, faults_text: 0, rule_text: NaN,
      cohort_text: 7, excluded_text: undefined, disagree_text: NaN, no_tier_text: '' };
    const { container } = render(<GgHighSiPanel block={b as any} />, wrap);
    expect(tids(container)).toEqual(['gg-hs']);
    expect(screen.getByTestId('gg-hs').textContent).not.toMatch(/NaN|undefined|null|\d/);
  });

  for (const [field, tid] of [['adds_text', 'gg-hs-adds'], ['disagree_text', 'gg-hs-disagree'], ['no_tier_text', 'gg-hs-notier'],
    ['excluded_text', 'gg-hs-excluded'], ['cohort_text', 'gg-hs-cohort'], ['sho_text', 'gg-hs-sho'], ['asof_text', 'gg-hs-asof'],
    ['counts_text', 'gg-hs-counts'], ['shown_text', 'gg-hs-shown']] as const) {
    it(`${field}: printed only when a string; NEGATIVE null / undefined / NaN / number / "" → no ${tid} node, the rest stand`, () => {
      for (const v of [null, undefined, NaN, 3, '', '   ']) {
        const { unmount } = render(<GgHighSiPanel block={{ ...clone(HS_BLOCK), [field]: v as any }} />, wrap);
        expect(screen.queryByTestId(tid), `${field}=${String(v)}`).toBeNull();
        expect(screen.getByTestId('gg-hs-title').textContent).toBe('served hs title');
        expect(screen.getByTestId('gg-hs-honesty').textContent).toBe('served honesty');
        expect(screen.getByTestId('gg-hs').textContent).not.toMatch(/NaN|undefined/);
        unmount();
      }
    });
  }

  it('the fold draws when only a name list is served (no rule text) under the ⓘ fallback; NEGATIVE nothing foldable → no fold', () => {
    const { unmount } = render(<GgHighSiPanel block={{ ...clone(HS_BLOCK), rule_text: null, rule_label: null, cohort_text: null,
      excluded_text: null, no_tier_text: null }} />, wrap);
    const rule = screen.getByTestId('gg-hs-rule');
    expect(rule.querySelector('summary')!.textContent).toBe('ⓘ');
    expect(screen.queryByTestId('gg-hs-rule-text')).toBeNull();
    expect(rule.contains(screen.getByTestId('gg-hs-disagree'))).toBe(true);
    unmount();
    render(<GgHighSiPanel block={{ ...clone(HS_BLOCK), rule_text: null, cohort_text: null, excluded_text: null,
      disagree_text: null, no_tier_text: NaN as any }} />, wrap);
    expect(screen.queryByTestId('gg-hs-rule')).toBeNull();
    expect(screen.getByTestId('gg-hs-honesty')).toBeTruthy();
  });

  it('n === 0 + empty_text → the served empty line; NEGATIVE n > 0, n null, or a chartless line → no empty line', () => {
    const { unmount } = render(<GgHighSiPanel block={{ ...clone(HS_BLOCK), n: 0 }} />, wrap);
    expect(screen.getByTestId('gg-hs-empty').textContent).toBe('served empty');
    expect(screen.getByTestId('gg-hs-empty').closest('details')).toBeNull();
    unmount();
    for (const n of [3, null, undefined, NaN, '0']) {
      const r = render(<GgHighSiPanel block={{ ...clone(HS_BLOCK), n: n as any }} />, wrap);
      expect(screen.queryByTestId('gg-hs-empty'), String(n)).toBeNull();
      r.unmount();
    }
    render(<GgHighSiPanel block={{ ...clone(HS_BLOCK), n: 0,
      chartless: [{ symbol: 'ZZZ', at_text: 'x', state_label: 'served chartless ZZZ', href: null }] }} />, wrap);
    expect(screen.queryByTestId('gg-hs-empty')).toBeNull();
    expect(screen.getByTestId('gg-hs-chartless-ZZZ').textContent).toBe('served chartless ZZZ');
  });

  it('NEGATIVE: n === 0 with no served empty_text → no empty line (the FE never types one)', () => {
    render(<GgHighSiPanel block={{ ...clone(HS_BLOCK), n: 0, empty_text: NaN as any }} />, wrap);
    expect(screen.queryByTestId('gg-hs-empty')).toBeNull();
  });

  it('chartless: a served href → a Link through ggHref; NEGATIVE an unsafe href → plain text; a row with no state_label → nothing', () => {
    const b = { ...clone(HS_BLOCK), chartless: [
      { symbol: 'AAA', at_text: 'x', state_label: 'served chartless AAA', href: '/sepa/AAA?tab=supply' },
      { symbol: 'BBB', at_text: 'x', state_label: 'served chartless BBB', href: 'javascript:alert(1)' },
      { symbol: 'DDD', at_text: 'x', state_label: 'served chartless DDD', href: '//evil.example/x' },
      { symbol: 'CCC', at_text: 'x', state_label: NaN, href: '/sepa/CCC' },
      null, 7,
    ] };
    render(<GgHighSiPanel block={b as any} />, wrap);
    expect(screen.getByTestId('gg-hs-chartless-AAA').querySelector('a')!.getAttribute('href')).toBe('/sepa/AAA?tab=supply');
    expect(screen.getByTestId('gg-hs-chartless-BBB').querySelector('a')).toBeNull();
    expect(screen.getByTestId('gg-hs-chartless-BBB').textContent).toBe('served chartless BBB');
    expect(screen.getByTestId('gg-hs-chartless-DDD').querySelector('a')).toBeNull();
    expect(screen.queryByTestId('gg-hs-chartless-CCC')).toBeNull();
    // the chartless lines are always visible, before the fold
    expect(screen.getByTestId('gg-hs-chartless-AAA').closest('details')).toBeNull();
  });

  it('2026-11-23 refix: the chartless line prints the served text (it names the ticker), not the tier-only state_label', () => {
    /* the real served shape (high_si._cards): state_label "🩳 High short interest" carries no ticker; text does */
    const b = { ...clone(HS_BLOCK), chartless: [
      { symbol: 'HIGH', at_text: null, state_label: 'served tier only', text: 'served HIGH listed', href: '/sepa/HIGH' },
      { symbol: 'TXT', at_text: null, state_label: null, text: 'served TXT listed', href: null },
      { symbol: 'NAN', at_text: null, state_label: 'served fallback NAN', text: NaN, href: null },
      { symbol: 'EMP', at_text: null, state_label: 'served fallback EMP', text: '  ', href: null },
      { symbol: 'NUM', at_text: null, state_label: 7, text: 8, href: null },
      { symbol: 'NONE', at_text: null, state_label: undefined, text: null, href: null },
    ] };
    render(<GgHighSiPanel block={b as any} />, wrap);
    const high = screen.getByTestId('gg-hs-chartless-HIGH');
    expect(high.textContent).toBe('served HIGH listed');
    expect(high.textContent).toContain('HIGH');
    expect(high.textContent).not.toContain('served tier only');
    expect(high.querySelector('a')!.textContent).toBe('served HIGH listed');
    // a name whose read raised (state_label null) still prints its served text — never dropped from the words
    expect(screen.getByTestId('gg-hs-chartless-TXT').textContent).toBe('served TXT listed');
    // NEGATIVE: a NaN / blank text falls back to the served state_label
    expect(screen.getByTestId('gg-hs-chartless-NAN').textContent).toBe('served fallback NAN');
    expect(screen.getByTestId('gg-hs-chartless-EMP').textContent).toBe('served fallback EMP');
    // NEGATIVE: neither served as a string → no line
    expect(screen.queryByTestId('gg-hs-chartless-NUM')).toBeNull();
    expect(screen.queryByTestId('gg-hs-chartless-NONE')).toBeNull();
  });

  it('NEGATIVE: chartless not a list → no chartless line, no crash', () => {
    render(<GgHighSiPanel block={{ ...clone(HS_BLOCK), chartless: 'served' as any }} />, wrap);
    expect(screen.queryByTestId(/^gg-hs-chartless-/)).toBeNull();
    expect(screen.getByTestId('gg-hs-title')).toBeTruthy();
  });

  it('faults_text prints when served (outside the fold); NEGATIVE absent → no node', () => {
    const { unmount } = render(<GgHighSiPanel block={{ ...clone(HS_BLOCK), faults_text: 'served faults' }} />, wrap);
    expect(screen.getByTestId('gg-hs-faults').textContent).toBe('served faults');
    expect(screen.getByTestId('gg-hs-faults').closest('details')).toBeNull();
    unmount();
    render(<GgHighSiPanel block={clone(HS_BLOCK)} />, wrap);
    expect(screen.queryByTestId('gg-hs-faults')).toBeNull();
  });

  it('phone (430 px): the root is the gg-dv class (min-width: 0 + overflow-wrap: anywhere); NEGATIVE no inline width, no nowrap', async () => {
    const { container } = render(<GgHighSiPanel block={clone(HS_BLOCK)} />, wrap);
    for (const el of container.querySelectorAll('*')) {
      const st = (el as HTMLElement).getAttribute('style') || '';
      expect(st, el.tagName).not.toMatch(/width|nowrap/i);
    }
    const css = await readSource('src/styles/gajjala.css');
    const rule = /\n\.gg-dv \{([^}]*)\}/.exec(css);
    expect(rule, '.gg-dv rule').toBeTruthy();
    expect(rule![1]).toMatch(/min-width: 0/);
    expect(rule![1]).toMatch(/overflow-wrap: anywhere/);
    expect(rule![1]).not.toMatch(/nowrap|(^|;)\s*width:/);
    const line = /\n\.gg-dv-line \{([^}]*)\}/.exec(css);
    expect(line![1]).toMatch(/min-width: 0/);
    expect(line![1]).toMatch(/overflow-wrap: anywhere/);
  });

  it('NEGATIVE source guards: no digit typed in the code, no b-word, no number formatting, its own servedText guard, nothing from the board', async () => {
    const src = await readSource('src/components/GgHighSi.tsx');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
    // the only digits in the code are structural: the `n === 0` empty test and the <h3> title tag — no printed number
    expect(code.match(/\d/g)).toHaveLength(3);
    expect(code.replace('block.n === 0', '').replace(/<\/?h3[ >]/g, '')).not.toMatch(/\d/);
    expect(src).not.toMatch(/bounc/i);
    expect(src).not.toMatch(/toFixed\(|toLocaleString\(|Intl\./);
    expect(src).toMatch(/function servedText\(v: unknown\): v is string \{/);
    expect(src).not.toMatch(/from '\.\/GajjalaBoard'/);
    expect(src).toMatch(/className="gg-dv"/);
    // no typed word inside a testid'd node: every node body is a served value
    expect(code).not.toMatch(/gg-hs-[a-z-]+"[^>]*>[A-Za-z]/);
    // the panel knows nothing of the push mode
    expect(code).not.toMatch(/push_mode|PUSH_MODE|'live'|'off'/);
  });
});
