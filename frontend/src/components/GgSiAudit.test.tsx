import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { resetGgFold } from '../lib/ggFold';
import { GG_HIGH_SI_SUB, type GgHighSiBlock, type GgSiAuditBlock } from '../lib/gajjala';

/* 🧮 GgSiAuditSection — the nightly float and share-count source audit inside the 🩳 sub's panel (2026-11-26, spec
 * floatguard §3.9 / §4.3, WP fe). Ajay 2026-11-26 ~21:20 ET: "Also the Float share count issue and SI discrepancy happened
 * too many times need to do something about it".
 * Every string below is a SENTINEL ("served …") shaped like source_audit.served_block — the component types no word and
 * formats no number, so every assertion compares the DOM to the served value.
 * Pinned: ONE closed <details data-testid="gg-sa">, its summary the served summary; open → the title, the as-of, the empty
 * line, the table from the served heads + rows[].cells (the ticker linked through ggHref, `data-contested` on a contested
 * row, `data-held` on a held one), the shown line, a nested CLOSED rule fold → rule text + honesty. Mounted once in
 * GgHighSiPanel right after the 🏁, on the same digit-free line.
 * NEGATIVES: block null / undefined / a string / an array / a number → nothing; `fault_text` → one line, no fold, no table;
 * no `summary_text` → nothing; a NaN / number / '' / null cell prints nothing (never "NaN" / "undefined"); a row with no
 * symbol is dropped; an href that fails ggHref is plain text; junk heads → no table, no crash; the panel DOM is identical
 * without the key; GgHighSiState never draws it; the file types no tier word, no "sources disagree", no digit, no number
 * formatting. */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));

import { GgSiAuditSection } from './GgSiAudit';
import { GgHighSiPanel, GgHighSiState } from './GgHighSi';
import { GgSubFoldContext } from './GgFold';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const clone = (x: any) => JSON.parse(JSON.stringify(x));
const wrap = { wrapper: ({ children }: any) => <MemoryRouter>{children}</MemoryRouter> };
const openFold = (el: HTMLElement) => {
  (el as HTMLDetailsElement).open = true;
  fireEvent(el, new Event('toggle'));
};

const SA: GgSiAuditBlock = {
  title: 'served sa title', summary_text: 'served sa summary', asof_text: 'served sa as of',
  heads: [['ticker', 'served Ticker'], ['on', 'served Listed on'], ['float', 'served Float we use'],
    ['other', 'served Second float'], ['apart', 'served Apart'], ['shares', 'served Shares out we use'],
    ['counts', 'served Share counts on file'], ['word', 'served Chip word']],
  rows: [
    { symbol: 'CON', href: '/chart-maps/CON?tf=5m', contested: true, held: false, differ: true,
      cells: { on: 'served on con', float: 'served float con', other: 'served other con', apart: 'served apart con',
        shares: 'served shares con', counts: 'served counts con', word: 'served word con' } },
    { symbol: 'HLD', href: '/chart-maps/HLD?tf=5m', contested: true, held: true, differ: true,
      cells: { on: 'served on hld', float: 'served float hld', other: 'served other hld', apart: 'served apart hld',
        shares: 'served shares hld', counts: 'served counts hld', word: 'served word hld' } },
    { symbol: 'PLN', href: '/chart-maps/PLN?tf=5m', contested: false, held: false, differ: false,
      cells: { on: 'served on pln', float: 'served float pln', other: null, apart: null,
        shares: 'served shares pln', counts: 'served counts pln', word: 'served word pln' } },
  ],
  shown_text: 'served sa shown', rule_label: 'served sa rule label', rule_text: 'served sa rule text',
  honesty: 'served sa honesty', fault_text: null, empty_text: null, n: 3, n_differ: 2, n_contested: 2, n_window: 1,
};

const HS: GgHighSiBlock = {
  title: 'served hs title', ask_text: 'served his words', rule_label: 'served rule label', rule_text: 'served rule text',
  honesty: 'served honesty', counts_text: 'served counts', push_text: 'served push', n: 2, faults_text: null,
  empty_text: 'served empty', chartless: [],
};
const ST = { summary_text: 'served st summary', title: 'served st title' };

beforeEach(() => { resetGgFold(); });

describe('🧮 GgSiAuditSection — standalone', () => {
  it('ONE closed <details> whose summary is the served summary; the body is not mounted while closed', () => {
    const { container } = render(<GgSiAuditSection block={clone(SA)} />, wrap);
    const fold = screen.getByTestId('gg-sa');
    expect(fold.tagName).toBe('DETAILS');
    expect(fold.hasAttribute('open')).toBe(false);
    expect(screen.getByTestId('gg-sa-summary').textContent).toBe(SA.summary_text);
    expect(container.querySelectorAll('[data-testid="gg-sa"]')).toHaveLength(1);
    // NEGATIVE: closed → no title, no table in the DOM; only the served summary prints
    expect(screen.queryByTestId('gg-sa-title')).toBeNull();
    expect(container.querySelector('table')).toBeNull();
    expect(container.textContent).toBe(SA.summary_text);
  });

  it('open: the served lines in order, the table from the served heads + cells, the ticker linked, contested / held marked', () => {
    const { container } = render(<GgSiAuditSection block={clone(SA)} />, wrap);
    openFold(screen.getByTestId('gg-sa'));
    const order = [...container.querySelectorAll('[data-testid^="gg-sa-"]')].map((e) => e.getAttribute('data-testid'))
      .filter((t) => ['gg-sa-summary', 'gg-sa-title', 'gg-sa-asof', 'gg-sa-table', 'gg-sa-shown', 'gg-sa-rule'].includes(t!));
    expect(order).toEqual(['gg-sa-summary', 'gg-sa-title', 'gg-sa-asof', 'gg-sa-table', 'gg-sa-shown', 'gg-sa-rule']);
    expect(screen.getByTestId('gg-sa-title').textContent).toBe(SA.title);
    expect(screen.getByTestId('gg-sa-asof').textContent).toBe(SA.asof_text);
    expect(screen.getByTestId('gg-sa-shown').textContent).toBe(SA.shown_text);
    const table = screen.getByTestId('gg-sa-table');
    expect(table.className).toContain('gg-tr-table');
    expect(screen.getByTestId('gg-sa-box').className).toContain('gg-tr-scroll');
    expect([...table.querySelectorAll('th')].map((th) => th.textContent)).toEqual(SA.heads!.map(([, l]) => l));
    const trs = [...table.querySelectorAll('tbody tr')];
    expect(trs.map((t) => t.getAttribute('data-testid'))).toEqual(['gg-sa-row-CON', 'gg-sa-row-HLD', 'gg-sa-row-PLN']);
    const con = screen.getByTestId('gg-sa-row-CON');
    expect([...con.querySelectorAll('td')].map((td) => td.textContent)).toEqual(
      ['CON', ...SA.heads!.slice(1).map(([k]) => (SA.rows![0].cells as any)[k])]);
    const a = con.querySelector('a')!;
    expect(a.getAttribute('href')).toBe('/chart-maps/CON?tf=5m');
    expect(a.textContent).toBe('CON');
    // contested / held as served
    expect(con.getAttribute('data-contested')).toBe('true');
    expect(con.hasAttribute('data-held')).toBe(false);
    const hld = screen.getByTestId('gg-sa-row-HLD');
    expect(hld.getAttribute('data-contested')).toBe('true');
    expect(hld.getAttribute('data-held')).toBe('true');
    // NEGATIVE: a plain row carries neither mark
    const pln = screen.getByTestId('gg-sa-row-PLN');
    expect(pln.hasAttribute('data-contested')).toBe(false);
    expect(pln.hasAttribute('data-held')).toBe(false);
  });

  it('the rule fold is nested inside the body and CLOSED; it holds the served rule text and honesty', () => {
    render(<GgSiAuditSection block={clone(SA)} />, wrap);
    const fold = screen.getByTestId('gg-sa');
    openFold(fold);
    const rule = screen.getByTestId('gg-sa-rule');
    expect(rule.tagName).toBe('DETAILS');
    expect(fold.contains(rule)).toBe(true);
    expect(rule.hasAttribute('open')).toBe(false);
    expect(rule.querySelector('summary')!.textContent).toBe(SA.rule_label);
    expect(rule.contains(screen.getByTestId('gg-sa-rule-text'))).toBe(true);
    expect(screen.getByTestId('gg-sa-rule-text').textContent).toBe(SA.rule_text);
    expect(rule.contains(screen.getByTestId('gg-sa-honesty'))).toBe(true);
    expect(screen.getByTestId('gg-sa-honesty').textContent).toBe(SA.honesty);
  });

  it('the served empty line prints; NEGATIVE no rows → no table', () => {
    const b = { ...clone(SA), rows: [], empty_text: 'served sa nothing yet' };
    const { container } = render(<GgSiAuditSection block={b} />, wrap);
    openFold(screen.getByTestId('gg-sa'));
    expect(screen.getByTestId('gg-sa-empty').textContent).toBe('served sa nothing yet');
    expect(container.querySelector('table')).toBeNull();
  });

  it('every text node is a served string — no typed word, never "NaN" / "undefined" / "null"', () => {
    const { container } = render(<GgSiAuditSection block={clone(SA)} />, wrap);
    openFold(screen.getByTestId('gg-sa'));
    openFold(screen.getByTestId('gg-sa-rule'));
    const served = new Set<string>([SA.title, SA.summary_text, SA.asof_text, SA.shown_text, SA.rule_label, SA.rule_text,
      SA.honesty, ...SA.heads!.map(([, l]) => l), ...SA.rows!.map((r) => r.symbol as string),
      ...SA.rows!.flatMap((r) => Object.values(r.cells || {}).filter((v): v is string => typeof v === 'string'))] as string[]);
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    const texts: string[] = [];
    for (let n = walker.nextNode(); n; n = walker.nextNode()) if (n.textContent!.trim()) texts.push(n.textContent!);
    expect(texts.length).toBeGreaterThan(10);
    for (const t of texts) expect(served.has(t), t).toBe(true);
    expect(container.textContent).not.toMatch(/NaN|undefined|null/);
  });

  it('NEGATIVE: block null / undefined / a string / an array / a number / true → nothing', () => {
    for (const v of [null, undefined, 'served sa summary', [clone(SA)], 3, true]) {
      const r = render(<GgSiAuditSection block={v as any} />, wrap);
      expect(r.container.innerHTML).toBe('');
      r.unmount();
    }
  });

  it('NEGATIVE: a served fault_text → ONE error line, no fold, no table, no summary', () => {
    const { container } = render(<GgSiAuditSection block={{ ...clone(SA), fault_text: 'served sa fault' }} />, wrap);
    expect(screen.getByTestId('gg-sa-fault').textContent).toBe('served sa fault');
    expect(screen.getByTestId('gg-sa-fault').className).toBe('gg-dv-line cm-note cm-note-err');
    expect(container.querySelector('details')).toBeNull();
    expect(container.querySelector('table')).toBeNull();
    expect(container.textContent).toBe('served sa fault');
    const only = render(<GgSiAuditSection block={{ fault_text: 'served sa fault only' }} />, wrap);
    expect(only.container.textContent).toBe('served sa fault only');
  });

  it('NEGATIVE: no served summary_text (absent / null / "" / NaN / a number) → nothing, even with rows', () => {
    for (const s of [undefined, null, '', '   ', NaN, 7]) {
      const r = render(<GgSiAuditSection block={{ ...clone(SA), summary_text: s as any }} />, wrap);
      expect(r.container.innerHTML).toBe('');
      r.unmount();
    }
  });

  it('NEGATIVE: a NaN / number / "" / null / undefined / object cell prints nothing; a NaN line prints nothing', () => {
    const b: any = clone(SA);
    b.rows = [{ symbol: 'JNK', href: null, contested: 'true', held: 1,
      cells: { on: NaN, float: 7, other: '', apart: null, shares: { x: 1 }, counts: [], word: undefined } }];
    b.title = NaN; b.asof_text = 12; b.shown_text = ''; b.empty_text = undefined;
    const { container } = render(<GgSiAuditSection block={b} />, wrap);
    openFold(screen.getByTestId('gg-sa'));
    const row = screen.getByTestId('gg-sa-row-JNK');
    expect([...row.querySelectorAll('td')].map((td) => td.textContent)).toEqual(['JNK', '', '', '', '', '', '', '']);
    // a non-boolean contested / held is never a mark
    expect(row.hasAttribute('data-contested')).toBe(false);
    expect(row.hasAttribute('data-held')).toBe(false);
    for (const t of ['gg-sa-title', 'gg-sa-asof', 'gg-sa-shown', 'gg-sa-empty']) expect(screen.queryByTestId(t)).toBeNull();
    expect(container.textContent).not.toMatch(/NaN|undefined|null|\[object/);
    expect(container.textContent).not.toMatch(/\d/);
  });

  it('NEGATIVE: a row with no served symbol (or not an object) is dropped; cells not an object → empty cells', () => {
    const b: any = clone(SA);
    b.rows = [{ ...b.rows[0], symbol: null }, { ...b.rows[1], symbol: '' }, 'XYZ', null, 4, [],
      { ...b.rows[2], cells: 'junk' }];
    render(<GgSiAuditSection block={b} />, wrap);
    openFold(screen.getByTestId('gg-sa'));
    const trs = [...screen.getByTestId('gg-sa-table').querySelectorAll('tbody tr')];
    expect(trs.map((t) => t.getAttribute('data-testid'))).toEqual(['gg-sa-row-PLN']);
    expect([...trs[0].querySelectorAll('td')].map((td) => td.textContent)).toEqual(['PLN', '', '', '', '', '', '', '']);
  });

  it('NEGATIVE: an href that fails ggHref is plain text — never a link', () => {
    for (const href of ['//evil.example/x', 'https://evil.example/x', 'javascript:alert(1)', '', null, 5]) {
      const b: any = clone(SA);
      b.rows = [{ ...b.rows[0], href }];
      const r = render(<GgSiAuditSection block={b} />, wrap);
      openFold(r.getByTestId('gg-sa'));
      const row = r.getByTestId('gg-sa-row-CON');
      expect(row.querySelector('a')).toBeNull();
      expect(row.querySelector('td')!.textContent).toBe('CON');
      r.unmount();
    }
  });

  it('NEGATIVE: junk heads (absent / not a list / bad pairs) → no table, no crash; the other lines still print', () => {
    for (const heads of [undefined, null, 'ticker', [['ticker']], [[3, 'x']], [['ticker', '']], [null]]) {
      const r = render(<GgSiAuditSection block={{ ...clone(SA), heads: heads as any }} />, wrap);
      openFold(r.getByTestId('gg-sa'));
      expect(r.container.querySelector('table')).toBeNull();
      expect(r.getByTestId('gg-sa-title').textContent).toBe(SA.title);
      r.unmount();
    }
    // rows not a list → no table
    const r = render(<GgSiAuditSection block={{ ...clone(SA), rows: 'junk' as any }} />, wrap);
    openFold(r.getByTestId('gg-sa'));
    expect(r.container.querySelector('table')).toBeNull();
  });

  it('NEGATIVE: no served rule_label → no rule fold (the FE never types one)', () => {
    const { container } = render(<GgSiAuditSection block={{ ...clone(SA), rule_label: null }} />, wrap);
    openFold(screen.getByTestId('gg-sa'));
    expect(screen.queryByTestId('gg-sa-rule')).toBeNull();
    expect(container.querySelectorAll('details')).toHaveLength(1);
  });
});

describe('🧮 inside the 🩳 panel — mounted after the 🏁, drawn once, the panel otherwise unchanged', () => {
  const withSa = (sa: unknown, st: unknown = ST) => ({ ...clone(HS), si_track: st, si_audit: sa }) as GgHighSiBlock;

  it('the 🧮 sits INSIDE gg-hs right after the 🏁 section, closed, ONCE', () => {
    const { container } = render(<GgHighSiPanel block={withSa(clone(SA))} />, wrap);
    const panel = screen.getByTestId('gg-hs');
    const fold = screen.getByTestId('gg-sa');
    expect(panel.contains(fold)).toBe(true);
    expect(screen.getByTestId('gg-st').nextElementSibling).toBe(fold);
    expect(fold.nextElementSibling).toBe(screen.getByTestId('gg-hs-rule'));
    expect(fold.hasAttribute('open')).toBe(false);
    expect(container.querySelectorAll('[data-testid="gg-sa"]')).toHaveLength(1);
    // NEGATIVE: the panel's own rule fold does not hold it
    expect(screen.getByTestId('gg-hs-rule').contains(fold)).toBe(false);
  });

  it('a served fault prints its one line in the panel and the panel lines stand', () => {
    render(<GgHighSiPanel block={withSa({ fault_text: 'served sa fault' })} />, wrap);
    expect(screen.getByTestId('gg-sa-fault').textContent).toBe('served sa fault');
    expect(screen.getByTestId('gg-hs-title').textContent).toBe(HS.title);
    expect(screen.getByTestId('gg-hs-counts').textContent).toBe(HS.counts_text);
  });

  it('NEGATIVE: si_audit absent / null / junk → the panel DOM is byte-identical to a block without the key', () => {
    const base = render(<GgHighSiPanel block={{ ...clone(HS), si_track: ST } as GgHighSiBlock} />, wrap);
    const html = base.container.innerHTML;
    base.unmount();
    expect(html).not.toMatch(/gg-sa/);
    for (const v of [null, undefined, 3, 'x', [], {}, { summary_text: null }, { summary_text: '' }]) {
      const r = render(<GgHighSiPanel block={withSa(v)} />, wrap);
      expect(r.container.innerHTML).toBe(html);
      r.unmount();
    }
  });

  it('NEGATIVE: GgHighSiState prints exactly as without the block (nothing of the 🧮 outside the fold)', () => {
    const state = (b: GgHighSiBlock) => render(
      <GgSubFoldContext.Provider value={`sub:${GG_HIGH_SI_SUB}`}><GgHighSiState block={b} /></GgSubFoldContext.Provider>, wrap);
    const over = { n: 0, faults_text: 'served faults' };
    const a = state({ ...clone(HS), ...over });
    expect(a.container.textContent).toContain('served faults');
    const html = a.container.innerHTML;
    a.unmount();
    for (const sa of [clone(SA), { fault_text: 'served sa fault' }]) {
      const b = state({ ...clone(HS), ...over, si_audit: sa });
      expect(b.container.innerHTML).toBe(html);
      expect(b.container.textContent).not.toMatch(/served sa/);
      b.unmount();
    }
  });

  it('source: GgHighSi mounts the 🧮 once, on the 🏁 line right after it; the line is digit-free; GgHighSiState never names it', async () => {
    const src = await readSource('src/components/GgHighSi.tsx');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
    expect(code.split('<GgSiAuditSection').length - 1).toBe(1);
    expect(src).toContain("import { GgSiAuditSection } from './GgSiAudit';");
    const lines = src.split('\n');
    const at = lines.findIndex((l) => l.includes('<GgSiAuditSection'));
    expect(lines[at]).toMatch(/<GgSiTrackSection block=\{block\.si_track\} \/><GgSiAuditSection block=\{block\.si_audit\} \/>$/);
    expect(lines[at]).toContain('<GgSsrNewSection block={block.ssr_new} />');
    expect(lines[at]).not.toMatch(/\d/);
    expect(lines[at + 1]).toContain('{folded ? (');
    const state = code.slice(code.indexOf('export function GgHighSiState('), code.indexOf('export function GgHighSiPanel('));
    expect(state).not.toMatch(/si_audit|GgSiAudit/);
  });
});

describe('🧮 source guards on GgSiAudit.tsx', () => {
  const TIER = /\b(EXTREME|High|Elevated|Moderate|Low)\b/;

  it('NEGATIVE: no tier word, no "sources disagree", no digit in the code, no typed JSX text, no number formatting, no sort / fetch', async () => {
    const src = await readSource('src/components/GgSiAudit.tsx');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
    expect(src).not.toMatch(TIER);
    expect(src).not.toMatch(/sources disagree/i);
    expect(code).not.toMatch(/\d/);
    expect(code).not.toMatch(/<[a-z][^<>]*>\s*[^\s<{][^<{]*<\//);
    expect(src).not.toMatch(/toFixed\(|toLocaleString\(|toPrecision\(|Intl\.|\.sort\(/);
    expect(code).not.toMatch(/\bfetch\(/);
    expect(src).not.toMatch(/bounc/i);
    expect(src).toMatch(/function servedText\(v: unknown\): v is string \{/);
    expect(src).not.toMatch(/from '\.\/GajjalaBoard'/);
    expect(src).toMatch(/ggHref\(r\.href\)/);
  });

  it('the guards themselves fire on planted lines', () => {
    expect("const w = 'EXTREME';").toMatch(TIER);
    expect('<td>High</td>').toMatch(TIER);
    expect('GgHighSiBlock').not.toMatch(TIER);
    expect('<p className="x">Typed words</p>').toMatch(/<[a-z][^<>]*>\s*[^\s<{][^<{]*<\//);
    expect('<p className="x">{v}</p>').not.toMatch(/<[a-z][^<>]*>\s*[^\s<{][^<{]*<\//);
  });
});
