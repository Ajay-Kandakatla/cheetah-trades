import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { GgHighSiBlock, GgSsrNewBlock } from '../lib/gajjala';

/* ⛔ GgSsrNewSection (2026-11-24, spec ssrlist §3.4 / §4 W3). Ajay: "What are the SSR stocks today" · "Can you add it to
 * short interest tab" · "The new ones".
 * Every string below is a SENTINEL ("served …") — the component types no word, so every assertion compares the DOM to the
 * served value. NEGATIVES: a null / non-object block draws nothing; NaN / number / '' texts print nothing; a served fault
 * line means no fold and no empty line; a closed fold mounts no row; rows print in the SERVED order; an unsafe href is
 * plain text; n / n_untiered are never printed; the sheet keeps exactly one nowrap; no word typed in the source. */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));

import { GgSsrNewSection } from './GgSsrNew';
import { GgHighSiPanel } from './GgHighSi';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const clone = (x: any) => JSON.parse(JSON.stringify(x));
const stripCode = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1');
const wrap = { wrapper: ({ children }: any) => <MemoryRouter>{children}</MemoryRouter> };
const tids = (c: HTMLElement) => [...c.querySelectorAll('[data-testid^="gg-ssrn"]')].map((e) => e.getAttribute('data-testid'));

const ROW = (sym: string, extra: Record<string, unknown> = {}) => ({
  symbol: sym, href: `/sepa/${sym}`, at_text: `served at ${sym}`, drop_text: `served drop ${sym}`,
  source_text: `served src ${sym}`, mark_text: null, si_text: `served si ${sym}`, ...extra,
});

const BLOCK: GgSsrNewBlock = {
  title: 'served ssrn title', counts_text: 'served counts', tier_note: 'served tier note', window_text: 'served window',
  asof_text: 'served as of', status_text: 'served status', partial_text: 'served partial', si_note: 'served si note',
  list_note: 'served list note', faults_text: 'served faults', fault_text: null, empty_text: null,
  order_note: 'served order', rule_label: 'served rule label', rule_text: 'served rule text', note_text: 'served note',
  withheld_text: 'served withheld', n: 4242, n_untiered: 3131,
  groups: [
    { key: 'list_high', summary: 'served list high summary', count: 2, open: false,
      rows: [ROW('ZZB', { mark_text: 'served mark ZZB' }), ROW('AAA')] },
    { key: 'rest', summary: 'served rest summary', count: 1, open: false, rows: [ROW('MMM')] },
  ],
};
const ALWAYS = ['gg-ssrn-title', 'gg-ssrn-counts', 'gg-ssrn-tier-note', 'gg-ssrn-window', 'gg-ssrn-asof', 'gg-ssrn-status',
  'gg-ssrn-partial', 'gg-ssrn-si-note', 'gg-ssrn-list-note', 'gg-ssrn-faults'];
const RULE_IN = ['gg-ssrn-rule-text', 'gg-ssrn-note', 'gg-ssrn-order', 'gg-ssrn-withheld'];

/** Every served string of a block, the row pieces of OPEN folds included. */
const SERVED = (b: any, openKeys: string[] = []): string[] => {
  const out = [b.title, b.counts_text, b.tier_note, b.window_text, b.asof_text, b.status_text, b.partial_text, b.si_note,
    b.list_note, b.faults_text, b.fault_text, b.empty_text, b.rule_label, b.rule_text, b.note_text, b.order_note, b.withheld_text];
  for (const g of b.groups || []) {
    out.push(g.summary);
    if (openKeys.includes(g.key)) for (const r of g.rows || []) out.push(r.symbol, r.at_text, r.drop_text, r.source_text, r.mark_text, r.si_text);
  }
  return out.filter((x) => typeof x === 'string');
};

function openFold(el: HTMLElement) {
  (el as HTMLDetailsElement).open = true;
  fireEvent(el, new Event('toggle'));
}

afterEach(() => { vi.restoreAllMocks(); });

describe('⛔ GgSsrNewSection', () => {
  /* WIDENED 2026-11-24 (ggclean): ALWAYS VISIBLE = outside this section's own rule / row folds. On the 🚩 board the whole
   * 🩳 panel (this section with it) sits inside the sub's closed ⓘ fold (GajjalaBoard) — the section itself is unchanged. */
  it('1. every served line verbatim in the §3.4 order (tier note right under the counts); the rule fold closed under the served label', () => {
    const { container } = render(<GgSsrNewSection block={clone(BLOCK)} />, wrap);
    const root = screen.getByTestId('gg-ssrn');
    expect(root.tagName).toBe('SECTION');
    expect(root.className).toBe('gg-ssrn');
    expect(screen.getByTestId('gg-ssrn-title').tagName).toBe('H4');
    const want: Record<string, string> = {
      'gg-ssrn-title': 'served ssrn title', 'gg-ssrn-counts': 'served counts', 'gg-ssrn-tier-note': 'served tier note',
      'gg-ssrn-window': 'served window', 'gg-ssrn-asof': 'served as of', 'gg-ssrn-status': 'served status',
      'gg-ssrn-partial': 'served partial', 'gg-ssrn-si-note': 'served si note', 'gg-ssrn-list-note': 'served list note',
      'gg-ssrn-faults': 'served faults', 'gg-ssrn-rule-text': 'served rule text', 'gg-ssrn-note': 'served note',
      'gg-ssrn-order': 'served order', 'gg-ssrn-withheld': 'served withheld',
    };
    for (const [t, v] of Object.entries(want)) expect(screen.getByTestId(t).textContent, t).toBe(v);
    expect(screen.getByTestId('gg-ssrn-partial').className).toContain('cm-note');
    expect(tids(container)).toEqual(['gg-ssrn', ...ALWAYS, 'gg-ssrn-g-list_high', 'gg-ssrn-g-rest', 'gg-ssrn-rule', ...RULE_IN]);
    const rule = screen.getByTestId('gg-ssrn-rule');
    expect(rule.tagName).toBe('DETAILS');
    expect(rule.hasAttribute('open')).toBe(false);
    expect(rule.querySelector('summary')!.textContent).toBe('served rule label');
    expect(root.lastElementChild).toBe(rule);
    for (const t of ALWAYS) expect(screen.getByTestId(t).closest('details'), t).toBeNull();
    expect(screen.getByTestId('gg-ssrn-g-list_high').querySelector('summary')!.textContent).toBe('served list high summary');
  });

  it('1b. NEGATIVE: no served rule label → no rule fold, though its texts are served', () => {
    for (const v of [null, undefined, NaN, 3, '', '  ']) {
      const { unmount } = render(<GgSsrNewSection block={{ ...clone(BLOCK), rule_label: v as any }} />, wrap);
      expect(screen.queryByTestId('gg-ssrn-rule'), String(v)).toBeNull();
      expect(screen.queryByTestId('gg-ssrn-rule-text')).toBeNull();
      unmount();
    }
  });

  it('2. NEGATIVE: null / undefined / string / number / NaN / array block → nothing; {} → the bare root only', () => {
    for (const b of [null, undefined, 'served', 7, NaN, true, []] as any[]) {
      const { container, unmount } = render(<GgSsrNewSection block={b} />, wrap);
      expect(container.innerHTML, String(b)).toBe('');
      unmount();
    }
    const { container } = render(<GgSsrNewSection block={{}} />, wrap);
    expect(tids(container)).toEqual(['gg-ssrn']);
    expect(screen.getByTestId('gg-ssrn').textContent).toBe('');
  });

  it('3. NEGATIVE: NaN / number / "" / undefined in any text or row piece prints nothing; n / n_untiered never printed', () => {
    const junk = [NaN, 5, '', undefined, '   ', 0];
    const keys = ['title', 'counts_text', 'tier_note', 'window_text', 'asof_text', 'status_text', 'partial_text', 'si_note',
      'list_note', 'faults_text', 'fault_text', 'empty_text', 'order_note', 'rule_label', 'rule_text', 'note_text', 'withheld_text'];
    const b: any = { n: 4242, n_untiered: 3131 };
    keys.forEach((k, i) => { b[k] = junk[i % junk.length]; });
    b.groups = [{ key: 'rest', summary: 'served rest summary', open: true,
      rows: [{ symbol: 'QQQ', href: null, at_text: NaN, drop_text: 7, source_text: '', mark_text: undefined, si_text: null }] }];
    const { container } = render(<GgSsrNewSection block={b} />, wrap);
    expect(tids(container)).toEqual(['gg-ssrn', 'gg-ssrn-g-rest', 'gg-ssrn-row-QQQ']);
    const text = screen.getByTestId('gg-ssrn').textContent || '';
    expect(text).toBe('served rest summaryQQQ');
    expect(text).not.toMatch(/NaN|undefined|null|\d/);
    expect(screen.getByTestId('gg-ssrn-row-QQQ').querySelectorAll('span')).toHaveLength(1);
    // the full block: neither count is printed anywhere
    const { unmount } = render(<GgSsrNewSection block={{ ...clone(BLOCK), groups: clone(BLOCK.groups).map((g: any) => ({ ...g, open: true })) }} />, wrap);
    const all = document.body.textContent || '';
    expect(all).not.toContain('4242');
    expect(all).not.toContain('3131');
    unmount();
  });

  it('4. NEGATIVE: a served fault line → no fold and no empty line, though both are served', () => {
    const b = { ...clone(BLOCK), fault_text: 'served fault', empty_text: 'served empty',
      groups: [{ key: 'rest', summary: 'served rest summary', open: true, rows: [ROW('MMM')] }] };
    const { container } = render(<GgSsrNewSection block={b} />, wrap);
    const f = screen.getByTestId('gg-ssrn-fault');
    expect(f.textContent).toBe('served fault');
    expect(f.className).toBe('gg-ssrn-line cm-note cm-note-err');
    expect(screen.queryByTestId('gg-ssrn-empty')).toBeNull();
    expect(container.querySelector('[data-testid^="gg-ssrn-g-"]')).toBeNull();
    expect(container.querySelector('[data-testid^="gg-ssrn-row-"]')).toBeNull();
    // the positive twin: no fault → the empty line prints as served
    const { unmount } = render(<GgSsrNewSection block={{ ...clone(BLOCK), groups: [], empty_text: 'served empty two' }} />, wrap);
    expect(screen.getByTestId('gg-ssrn-empty').textContent).toBe('served empty two');
    unmount();
  });

  it('5. a closed fold mounts no row; toggling it open mounts them, closing unmounts; served open: true mounts at first paint', () => {
    const { container, unmount } = render(<GgSsrNewSection block={clone(BLOCK)} />, wrap);
    const fold = screen.getByTestId('gg-ssrn-g-list_high');
    expect(fold.tagName).toBe('DETAILS');
    expect(fold.hasAttribute('open')).toBe(false);
    expect(container.querySelector('[data-testid^="gg-ssrn-row-"]')).toBeNull();
    expect(fold.querySelector('ul')).toBeNull();
    openFold(fold);
    expect(screen.getByTestId('gg-ssrn-row-ZZB')).toBeTruthy();
    expect(screen.getByTestId('gg-ssrn-row-AAA')).toBeTruthy();
    expect(screen.queryByTestId('gg-ssrn-row-MMM')).toBeNull();   // the other fold stays closed
    (fold as HTMLDetailsElement).open = false;
    fireEvent(fold, new Event('toggle'));
    expect(screen.queryByTestId('gg-ssrn-row-ZZB')).toBeNull();
    unmount();
    const b = clone(BLOCK);
    b.groups[1].open = true;
    render(<GgSsrNewSection block={b} />, wrap);
    expect(screen.getByTestId('gg-ssrn-g-rest').hasAttribute('open')).toBe(true);
    expect(screen.getByTestId('gg-ssrn-row-MMM')).toBeTruthy();
    expect(screen.queryByTestId('gg-ssrn-row-ZZB')).toBeNull();
    // NEGATIVE: a truthy non-boolean open is not "open"
    for (const v of ['true', 1, 'yes']) {
      const { unmount: u } = render(<GgSsrNewSection block={{ ...clone(BLOCK), groups: [{ ...clone(BLOCK.groups![1]), open: v }] } as any} />, wrap);
      expect(document.querySelectorAll('[data-testid="gg-ssrn-row-MMM"]'), String(v)).toHaveLength(1);   // only the earlier render's
      u();
    }
  });

  it('5b. a row prints its served pieces, each in its own span, ticker first; the mark only when served', () => {
    const b = clone(BLOCK);
    b.groups[0].open = true;
    render(<GgSsrNewSection block={b} />, wrap);
    const zzb = screen.getByTestId('gg-ssrn-row-ZZB');
    expect([...zzb.children].map((c) => c.textContent)).toEqual(['ZZB', 'served at ZZB', 'served drop ZZB', 'served src ZZB',
      'served mark ZZB', 'served si ZZB']);
    expect([...screen.getByTestId('gg-ssrn-row-AAA').children].map((c) => c.textContent)).toEqual(['AAA', 'served at AAA',
      'served drop AAA', 'served src AAA', 'served si AAA']);
  });

  it('6. NEGATIVE: rows print in the SERVED order (deliberately unsorted); the summary prints verbatim even when it disagrees with the rows', () => {
    const b = { ...clone(BLOCK), groups: [{ key: 'high', summary: 'served high summary — 99', count: 99, open: true,
      rows: [ROW('ZZZ'), ROW('AAA'), ROW('MMM'), ROW('BBB')] }] };
    render(<GgSsrNewSection block={b} />, wrap);
    const fold = screen.getByTestId('gg-ssrn-g-high');
    expect(fold.querySelector('summary')!.textContent).toBe('served high summary — 99');
    const order = [...fold.querySelectorAll('[data-testid^="gg-ssrn-row-"]')].map((e) => e.getAttribute('data-testid'));
    expect(order).toEqual(['gg-ssrn-row-ZZZ', 'gg-ssrn-row-AAA', 'gg-ssrn-row-MMM', 'gg-ssrn-row-BBB']);
  });

  it('6b. folds print in the SERVED order (never re-ordered by key)', () => {
    const b = { ...clone(BLOCK), groups: [
      { key: 'rest', summary: 'served rest', open: false, rows: [ROW('A')] },
      { key: 'list_high', summary: 'served lh', open: false, rows: [ROW('B')] },
    ] };
    const { container } = render(<GgSsrNewSection block={b} />, wrap);
    expect([...container.querySelectorAll('[data-testid^="gg-ssrn-g-"]')].map((e) => e.getAttribute('data-testid')))
      .toEqual(['gg-ssrn-g-rest', 'gg-ssrn-g-list_high']);
  });

  it('7. NEGATIVE: a group with no summary, rows not a list, or no served symbol → not drawn; junk groups / rows skipped', () => {
    const b = { ...clone(BLOCK), groups: [
      { key: 'a', summary: null, open: true, rows: [ROW('AAA')] },
      { key: 'b', summary: NaN, open: true, rows: [ROW('BBB')] },
      { key: 'c', summary: 'served c', open: true, rows: 'served' },
      { key: 'd', summary: 'served d', open: true, rows: [{ symbol: null }, { symbol: 7 }, { symbol: '' }, null, 3, 'x'] },
      { key: 'e', summary: 'served e', open: true, rows: [] },
      null, 7, 'served', [],
      { key: 'f', summary: 'served f', open: true, rows: [null, { symbol: 'FFF' }, { symbol: NaN }] },
    ] };
    const { container } = render(<GgSsrNewSection block={b as any} />, wrap);
    expect([...container.querySelectorAll('[data-testid^="gg-ssrn-g-"]')].map((e) => e.getAttribute('data-testid'))).toEqual(['gg-ssrn-g-f']);
    expect([...container.querySelectorAll('[data-testid^="gg-ssrn-row-"]')].map((e) => e.getAttribute('data-testid'))).toEqual(['gg-ssrn-row-FFF']);
    const { container: c2 } = render(<GgSsrNewSection block={{ ...clone(BLOCK), groups: 'served' as any }} />, wrap);
    expect(c2.querySelector('[data-testid^="gg-ssrn-g-"]')).toBeNull();
    expect(screen.getAllByTestId('gg-ssrn-title').length).toBeGreaterThan(0);
  });

  it('8. a safe href → a link; NEGATIVE //evil, http://…, javascript:, a number, null → plain text', () => {
    const b = { ...clone(BLOCK), groups: [{ key: 'rest', summary: 'served rest', open: true, rows: [
      ROW('AAA', { href: '/chart-maps?tab=gajjala&sym=AAA' }), ROW('EVL', { href: '//evil.example/x' }),
      ROW('HTP', { href: 'http://evil.example/x' }), ROW('JSX', { href: 'javascript:alert(1)' }),
      ROW('NUM', { href: 7 }), ROW('NUL', { href: null }),
    ] }] };
    render(<GgSsrNewSection block={b as any} />, wrap);
    const a = screen.getByTestId('gg-ssrn-row-AAA').querySelector('a')!;
    expect(a.getAttribute('href')).toBe('/chart-maps?tab=gajjala&sym=AAA');
    expect(a.textContent).toBe('AAA');
    for (const s of ['EVL', 'HTP', 'JSX', 'NUM', 'NUL']) {
      const row = screen.getByTestId(`gg-ssrn-row-${s}`);
      expect(row.querySelector('a'), s).toBeNull();
      expect(row.firstElementChild!.textContent).toBe(s);
    }
  });

  it('9. NEGATIVE: no typed word — the rendered text minus the served strings is empty (folds closed and open)', () => {
    const closed = clone(BLOCK);
    const { unmount } = render(<GgSsrNewSection block={closed} />, wrap);
    let text = screen.getByTestId('gg-ssrn').textContent || '';
    for (const s of SERVED(closed).sort((x, y) => y.length - x.length)) text = text.split(s).join('');
    expect(text.trim()).toBe('');
    unmount();
    const opened = clone(BLOCK);
    opened.groups.forEach((g: any) => { g.open = true; });
    opened.empty_text = 'served empty';
    render(<GgSsrNewSection block={opened} />, wrap);
    let t2 = screen.getByTestId('gg-ssrn').textContent || '';
    for (const s of SERVED(opened, ['list_high', 'rest']).sort((x, y) => y.length - x.length)) t2 = t2.split(s).join('');
    expect(t2.trim()).toBe('');
  });

  it('10. in the panel: after gg-hs-faults, before gg-hs-rule; lastElementChild still gg-hs-honesty; NEGATIVE no ssr_new → no gg-ssrn', () => {
    const HS: GgHighSiBlock = {
      title: 'served hs title', rule_label: 'served hs rule label', rule_text: 'served hs rule', honesty: 'served honesty',
      counts_text: 'served hs counts', faults_text: 'served hs faults', n: 3, chartless: [], ssr_new: clone(BLOCK),
    };
    const { unmount } = render(<GgHighSiPanel block={clone(HS)} />, wrap);
    const panel = screen.getByTestId('gg-hs');
    const sec = screen.getByTestId('gg-ssrn');
    expect(sec.parentElement).toBe(panel);
    const kids = [...panel.children].map((e) => e.getAttribute('data-testid'));
    const i = kids.indexOf('gg-ssrn');
    expect(kids[i - 1]).toBe('gg-hs-faults');
    expect(kids[i + 1]).toBe('gg-hs-rule');
    expect(panel.lastElementChild!.getAttribute('data-testid')).toBe('gg-hs-honesty');
    expect(screen.getByTestId('gg-hs-rule').contains(sec)).toBe(false);
    // the panel's own gg-hs* order is untouched (no gg-ssrn testid starts with gg-hs)
    expect([...panel.querySelectorAll('[data-testid^="gg-hs"]')].map((e) => e.getAttribute('data-testid')))
      .toEqual(['gg-hs-title', 'gg-hs-counts', 'gg-hs-faults', 'gg-hs-rule', 'gg-hs-rule-text', 'gg-hs-honesty']);
    unmount();
    for (const v of [undefined, null, 'served', 7]) {
      const r = render(<GgHighSiPanel block={{ ...clone(HS), ssr_new: v as any }} />, wrap);
      expect(r.container.querySelector('[data-testid^="gg-ssrn"]'), String(v)).toBeNull();
      expect(screen.getByTestId('gg-hs-honesty')).toBeTruthy();
      r.unmount();
    }
  });

  it('11. phone: .gg-ssrn and .gg-ssrn-row wrap (min-width 0 + overflow-wrap anywhere); NEGATIVE one nowrap, no width, no inline style, no alarm colour, no bold', async () => {
    const css = await readSource('src/styles/ggSsr.css');
    const rule = (sel: string) => {
      const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const m = css.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
      return m ? m[2] : null;
    };
    for (const sel of ['.gg-ssrn', '.gg-ssrn-row']) {
      const r = rule(sel);
      expect(r, sel).not.toBeNull();
      expect(r!, sel).toMatch(/min-width:\s*0\b/);
      expect(r!, sel).toMatch(/overflow-wrap:\s*anywhere/);
    }
    expect(rule('.gg-ssrn-rows')).toMatch(/grid-template-columns:\s*repeat\(auto-fill, minmax\(17rem, 1fr\)\)/);
    expect(css.match(/nowrap/g) || []).toHaveLength(1);
    const mine = css.slice(css.indexOf('.gg-ssrn'));
    expect(css.indexOf('.gg-ssrn')).toBeGreaterThan(css.indexOf('@media (min-width: 641px)'));
    expect(mine).not.toMatch(/nowrap|@media/);
    expect(mine).not.toMatch(/(^|[;{\s])width\s*:/);
    expect(mine).not.toMatch(/(^|[;{\s])(color|background)\s*:/);
    expect(css).not.toMatch(/--warn|--bad|--danger|--red/);
    expect(css).not.toMatch(/font-weight:\s*(700|bold)/);
    for (const f of ['src/styles/gajjala.css', 'src/styles/gajjalaWatch.css']) expect(await readSource(f), f).not.toMatch(/gg-ssrn/);
    const b = clone(BLOCK);
    b.groups.forEach((g: any) => { g.open = true; });
    const { container } = render(<GgSsrNewSection block={b} />, wrap);
    for (const el of container.querySelectorAll('*')) expect((el as HTMLElement).getAttribute('style'), el.tagName).toBeNull();
    expect(screen.getByTestId('gg-ssrn-row-ZZB').className).toBe('gg-ssrn-row');
  });

  it('11b. NEGATIVE: the CSS guards fire on a sheet that adds nowrap, a width or an alarm colour', () => {
    const bad = '.gg-ssrn-row { white-space: nowrap; width: 20rem; color: var(--warn); }';
    expect(bad).toMatch(/nowrap/);
    expect(bad).toMatch(/(^|[;{\s])width\s*:/);
    expect(bad).toMatch(/--warn/);
    expect('.x { min-width: 0; max-width: 100%; }').not.toMatch(/(^|[;{\s])width\s*:/);
  });

  it('12. NEGATIVE source guards: no fetch, no hook but useState, no number formatting, no sort, the filters are the shape guard only, no word', async () => {
    const src = await readSource('src/components/GgSsrNew.tsx');
    const code = stripCode(src);
    expect(code).not.toMatch(/fetch\(/);
    expect([...code.matchAll(/\buse[A-Z]\w*\(/g)].map((m) => m[0])).toEqual(['useState(']);
    expect(code).not.toMatch(/useSsr/);
    expect(code).not.toMatch(/toFixed|Intl\b|toLocaleString/);
    expect(code).not.toMatch(/\.sort\(|\.reverse\(|\.slice\(/);
    expect((code.match(/\.filter\(/g) || []).length).toBe(3);   // rows: served symbol · groups: object + summary · groups: ≥1 row
    expect(code).not.toMatch(/shorting|short sale|short-sale|restriction/i);
    expect(src).not.toMatch(new RegExp('boun' + 'c', 'i'));
    expect(src).toContain("import '../styles/ggSsr.css';");
    expect(src).not.toMatch(/from '\.\/GajjalaBoard'|from '\.\.\/hooks\//);
    expect(src).toMatch(/function servedText\(v: unknown\): v is string \{/);
    // the only JSX text children are served values — no typed word between tags
    expect(code).not.toMatch(/>\s*[A-Za-z][A-Za-z ]*\s*</);
    // n / n_untiered / count are never read
    expect(code).not.toMatch(/\.n\b|\.n_untiered\b|\.count\b/);
    // every testid starts gg-ssrn, never gg-hs
    const ids = [...code.matchAll(/data-testid=\{?[`'"]([^`'"]+)/g)].map((m) => m[1]);
    expect(ids.length).toBeGreaterThan(0);
    for (const id of ids) expect(id).toMatch(/^gg-ssrn/);
    expect([...code.matchAll(/testid="([^"]+)"/g)].map((m) => m[1]).every((id) => id.startsWith('gg-ssrn'))).toBe(true);
    const lib = stripCode(await readSource('src/lib/gajjala.ts'));
    expect((lib.match(/'high_si'/g) || []).length).toBe(3);
    expect(lib).toMatch(/ssr_new\?: GgSsrNewBlock \| null;/);
  });

  it('12b. NEGATIVE: the source guards fire on a file that types a word, sorts, or uses another hook', () => {
    expect(stripCode("const x = 'no shorting';")).toMatch(/shorting|short sale|restriction/i);
    expect(stripCode('/* restriction */ const y = 1;')).not.toMatch(/restriction/i);
    expect(stripCode('rows.sort((a, b) => a - b)')).toMatch(/\.sort\(/);
    expect([...stripCode('const r = useSsr(s); const [o] = useState(false);').matchAll(/\buse[A-Z]\w*\(/g)].map((m) => m[0]))
      .not.toEqual(['useState(']);
    expect('<span>served</span><p>Typed words</p>').toMatch(/>\s*[A-Za-z][A-Za-z ]*\s*</);
  });

  it('the panel edit is one digit-free line: GgHighSi.tsx mounts the section once, after the faults line', async () => {
    const src = await readSource('src/components/GgHighSi.tsx');
    expect((src.match(/<GgSsrNewSection block=\{block\.ssr_new\} \/>/g) || []).length).toBe(1);
    expect(src).toContain("import { GgSsrNewSection } from './GgSsrNew';");
    const lines = src.split('\n');
    const at = lines.findIndex((l) => l.includes('<GgSsrNewSection'));
    expect(lines[at - 1]).toContain('gg-hs-faults');
    expect(lines[at + 1]).toContain('{folded ? (');
    expect(lines[at]).not.toMatch(/\d/);
  });
});
