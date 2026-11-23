/* 🔒 GgHardToBorrow chip / label / fault (2026-11-22, spec htb §3.3 / §4 fe).
 *
 * Ajay 2026-11-22: "add a tag to stocks tickers like short interest, name the tag " hard to borrow" threshold security"
 *
 * The served words print verbatim (hover = the served title), through the REAL hook and lib with fetch stubbed. NOTHING
 * renders without a valid payload (no wrapper, no space). Source guards: the three FE files type no tag word, compare no
 * served field; the CSS is the neutral look (no --warn, no 700) and wraps on the phone. */
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GgHardToBorrowChip, GgHardToBorrowFault, GgHardToBorrowLabel } from './GgHardToBorrow';
import { _resetRegShoCache } from '../hooks/useRegSho';

const AKAN = {
  state: 'on', symbol: 'AKAN', market: 'nasdaq', exchange: 'Nasdaq', as_of: '2026-11-20', stale: false,
  chip: '🔒 Hard to borrow · threshold security · 11/20',
  short: '🔒 Hard to borrow · 11/20',
  label: '🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20',
  title: '🔒 Hard to borrow — AKAN is a Reg SHO threshold security on the Nasdaq list for 2026-11-20: served hover.',
};
const OLDN = {
  ...AKAN, symbol: 'OLDN', as_of: '2026-11-17', stale: true,
  chip: '🔒 Hard to borrow · threshold security · 11/17 · stale', short: '🔒 Hard to borrow · 11/17 · stale',
  label: '🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/17 · stale', title: 'served stale title',
};
const ACONW = { ...AKAN, symbol: 'ACONW', chip: 'served chip ACONW', short: 'served short ACONW', label: 'served label ACONW', title: 't' };
const valid = (over: Record<string, unknown> = {}) => ({
  kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, n: 3, items: { AKAN, OLDN, ACONW },
  fault_text: null, refreshing: false, retry_after_sec: null, ...over,
});

let body: unknown = valid();
function stub(mode: 'ok' | 'reject' | 'sync' = 'ok') {
  const f = vi.fn((url: string) => {
    if (mode === 'sync') throw new Error('sync');
    if (mode === 'reject') return Promise.reject(new Error('down'));
    void url;
    return Promise.resolve({ ok: true, json: async () => JSON.parse(JSON.stringify(body)) } as unknown as Response);
  });
  vi.stubGlobal('fetch', f);
  return f;
}
const settle = (f: ReturnType<typeof vi.fn>) =>
  waitFor(() => expect(f).toHaveBeenCalled()).then(() => new Promise((r) => setTimeout(r, 10)));

beforeEach(() => { _resetRegShoCache(); body = valid(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetRegShoCache(); });

describe('chip / label / fault print the served text verbatim', () => {
  it('the chip prints the served chip, the served title, the given testid, cm-badge gg-htb, market + as-of attributes', async () => {
    stub();
    render(<GgHardToBorrowChip symbol="AKAN" testid="gg-htb-AKAN" />);
    const el = await screen.findByTestId('gg-htb-AKAN');
    expect(el.tagName).toBe('SPAN');
    expect(el.textContent).toBe(AKAN.chip);
    expect(el.getAttribute('title')).toBe(AKAN.title);
    expect(el.className).toBe('cm-badge gg-htb');
    expect(el.getAttribute('data-htb-market')).toBe('nasdaq');
    expect(el.getAttribute('data-htb-asof')).toBe('2026-11-20');
  });

  it('form="short" prints the served short form; a given className rides in front of gg-htb', async () => {
    stub();
    render(<GgHardToBorrowChip symbol="AKAN" testid="t" className="ggw-chip" form="short" />);
    const el = await screen.findByTestId('t');
    expect(el.textContent).toBe(AKAN.short);
    expect(el.className).toBe('ggw-chip gg-htb');
    expect(el.getAttribute('title')).toBe(AKAN.title);
  });

  it('lead puts ONE space before the chip (the card chip row); without lead there is none', async () => {
    stub();
    const { container } = render(<div><GgHardToBorrowChip symbol="AKAN" testid="a" lead /></div>);
    await screen.findByTestId('a');
    expect(container.firstElementChild!.firstChild!.nodeType).toBe(Node.TEXT_NODE);
    expect(container.firstElementChild!.firstChild!.textContent).toBe(' ');
    cleanup();
    const r2 = render(<div><GgHardToBorrowChip symbol="AKAN" testid="b" /></div>);
    await screen.findByTestId('b');
    expect(r2.container.firstElementChild!.firstChild!.nodeType).toBe(Node.ELEMENT_NODE);
  });

  it('the label prints the served label, the served title, cm-note gg-line gg-htb-label, as a DIV', async () => {
    stub();
    render(<GgHardToBorrowLabel symbol="AKAN" testid="gg-htb-label-AKAN" />);
    const el = await screen.findByTestId('gg-htb-label-AKAN');
    expect(el.tagName).toBe('DIV');
    expect(el.textContent).toBe(AKAN.label);
    expect(el.getAttribute('title')).toBe(AKAN.title);
    expect(el.className).toBe('cm-note gg-line gg-htb-label');
  });

  it('the fault prints the served fault_text verbatim as a DIV with cm-note cm-note-err gg-htb-fault; inline → SPAN', async () => {
    body = valid({ fault_text: 'served fault sentence' });
    stub();
    render(<>
      <GgHardToBorrowFault testid="f1" />
      <GgHardToBorrowFault testid="f2" className="ggw-line ggw-warn" inline />
    </>);
    const a = await screen.findByTestId('f1');
    expect(a.tagName).toBe('DIV');
    expect(a.textContent).toBe('served fault sentence');
    expect(a.className).toBe('cm-note cm-note-err gg-htb-fault');
    const b = screen.getByTestId('f2');
    expect(b.tagName).toBe('SPAN');
    expect(b.className).toBe('ggw-line ggw-warn gg-htb-fault');
  });

  it('stale → gg-htb-stale and the served " · stale" text on chip, short and label', async () => {
    stub();
    render(<>
      <GgHardToBorrowChip symbol="OLDN" testid="c" />
      <GgHardToBorrowChip symbol="OLDN" testid="s" form="short" />
      <GgHardToBorrowLabel symbol="OLDN" testid="l" />
    </>);
    const c = await screen.findByTestId('c');
    expect(c.className).toBe('cm-badge gg-htb gg-htb-stale');
    expect(c.textContent).toBe(OLDN.chip);
    expect(screen.getByTestId('s').textContent).toBe(OLDN.short);
    expect(screen.getByTestId('l').className).toBe('cm-note gg-line gg-htb-label gg-htb-stale');
    for (const id of ['c', 's', 'l']) expect(screen.getByTestId(id).textContent).toMatch(/ · stale$/);
  });

  it('three chips + a label + a fault on one screen cost ONE GET', async () => {
    const f = stub();
    render(<>
      <GgHardToBorrowChip symbol="AKAN" testid="a" />
      <GgHardToBorrowChip symbol="OLDN" testid="b" />
      <GgHardToBorrowChip symbol="ACONW" testid="c" form="short" />
      <GgHardToBorrowLabel symbol="AKAN" testid="d" />
      <GgHardToBorrowFault testid="e" />
    </>);
    await screen.findByTestId('d');
    expect(f).toHaveBeenCalledTimes(1);
    expect(String(f.mock.calls[0][0])).toMatch(/\/short-interest\/reg-sho$/);
  });
});

describe('NEGATIVES — nothing renders without a served tag', () => {
  it('not on the list → the HTML equals the same mount with the tag absent (no wrapper, no space)', async () => {
    const f = stub();
    const { container } = render(<div className="row"><b>X</b><GgHardToBorrowChip symbol="ZZZZ" testid="z" lead /><GgHardToBorrowLabel symbol="ZZZZ" testid="zl" /><i>Y</i></div>);
    await settle(f);
    const html = container.innerHTML;
    expect(html).toBe('<div class="row"><b>X</b><i>Y</i></div>');
    cleanup();
    const bare = render(<div className="row"><b>X</b><i>Y</i></div>);
    expect(html).toBe(bare.container.innerHTML);
  });

  it('unknown (valid payload, complete: false, name absent) → no chip; the payload did not say off', async () => {
    body = valid({ complete: false, items: { AKAN } });
    const f = stub();
    const { container } = render(<GgHardToBorrowChip symbol="HAWK" testid="h" />);
    await settle(f);
    expect(container.innerHTML).toBe('');
    expect(JSON.stringify(body)).not.toContain('"off"');
  });

  for (const [name, b] of [
    ['{}', {}], ['an array', [AKAN]], ['null', null],
    ['the SI map body', { items: { AKAN: { symbol: 'AKAN', status: 'ok', chip: 'x', title: 'y', rows: [] } }, n: 1, max_symbols: 200 }],
    ['a Watch board body', { title: 'served Watch', rows: [{ symbol: 'AKAN' }], remove_label: 'x' }],
  ] as const) {
    it(`foreign body (${name}) → nothing on the chip, the label and the fault`, async () => {
      body = b;
      const f = stub();
      const { container } = render(<><GgHardToBorrowChip symbol="AKAN" testid="a" /><GgHardToBorrowLabel symbol="AKAN" testid="b" />
        <GgHardToBorrowFault testid="c" /></>);
      await settle(f);
      expect(container.innerHTML).toBe('');
    });
  }

  for (const [name, over] of [
    ["state 'off'", { state: 'off' }], ["state 'unknown'", { state: 'unknown' }],
    ['blank chip', { chip: ' ' }], ['blank short', { short: '' }], ['blank label', { label: '' }], ['blank title', { title: '' }],
  ] as const) {
    it(`an item with ${name} → no tag`, async () => {
      body = valid({ items: { AKAN: { ...AKAN, ...over } } });
      const f = stub();
      const { container } = render(<><GgHardToBorrowChip symbol="AKAN" testid="a" /><GgHardToBorrowChip symbol="AKAN" testid="s" form="short" />
        <GgHardToBorrowLabel symbol="AKAN" testid="b" /></>);
      await settle(f);
      expect(container.innerHTML).toBe('');
    });
  }

  it('exact match: AKAN listed, an AKANW chip → nothing; ACONW listed, an ACON chip → nothing', async () => {
    const f = stub();
    const { container } = render(<><GgHardToBorrowChip symbol="AKANW" testid="a" /><GgHardToBorrowLabel symbol="ACON" testid="b" /></>);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  for (const mode of ['reject', 'sync'] as const) {
    it(`the request fails (${mode}) → nothing, no crash, NO fault line`, async () => {
      body = valid({ fault_text: 'served fault sentence' });
      const f = stub(mode);
      const { container } = render(<><GgHardToBorrowChip symbol="AKAN" testid="a" /><GgHardToBorrowLabel symbol="AKAN" testid="b" />
        <GgHardToBorrowFault testid="c" /><GgHardToBorrowFault testid="d" inline /></>);
      await settle(f);
      expect(container.innerHTML).toBe('');
      expect(f).toHaveBeenCalledTimes(1);
    });
  }

  it('an ok tag never carries gg-htb-stale', async () => {
    stub();
    render(<><GgHardToBorrowChip symbol="AKAN" testid="a" /><GgHardToBorrowLabel symbol="AKAN" testid="b" /></>);
    expect((await screen.findByTestId('a')).className).not.toContain('gg-htb-stale');
    expect(screen.getByTestId('b').className).not.toContain('gg-htb-stale');
  });

  it('the fault draws only for a non-empty served fault_text: null, blank, and null-while-refreshing → nothing', async () => {
    for (const over of [{ fault_text: null }, { fault_text: '   ' }, { fault_text: null, refreshing: true, retry_after_sec: 20, items: {} }]) {
      _resetRegShoCache();
      body = valid(over);
      const f = stub();
      const { container, unmount } = render(<><GgHardToBorrowFault testid="c" /><GgHardToBorrowFault testid="d" inline /></>);
      await settle(f);
      expect(container.innerHTML, JSON.stringify(over)).toBe('');
      unmount();
      vi.unstubAllGlobals();
    }
  });
});

/* ── source guards (jsdom has no layout) ── */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
/** The source with block and line comments removed. */
const code = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1');
/** The declarations of the FIRST top-level rule whose selector is exactly `sel`. */
function rule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}
const FE_FILES = ['src/components/GgHardToBorrow.tsx', 'src/hooks/useRegSho.ts', 'src/lib/regSho.ts'];
const NEW_FILES = [...FE_FILES, 'src/styles/ggHardToBorrow.css', 'src/lib/regSho.test.ts', 'src/hooks/useRegSho.test.ts',
  'src/components/GgHardToBorrow.test.tsx', 'src/components/GgHardToBorrow.payload.test.tsx',
  'src/components/GajjalaBoard.htb.test.tsx', 'src/components/GajjalaWatchTile.htb.test.tsx',
  'src/components/GajjalaWatchBoard.htb.test.tsx', 'src/components/GgAllTable.htb.test.tsx'];
const TAG_WORDS = /Hard to borrow|threshold security|Reg SHO/i;
const PAYLOAD_FIELDS = '(?:fault_text|refreshing|retry_after_sec|complete|as_of|asOf|stale|items|chip|short|label|title|n)';
const COMPARE = new RegExp(`\\.${PAYLOAD_FIELDS}\\b[^\\n;]*?\\s(>=|<=|>|<)\\s|\\s(>=|<=|>|<)\\s[\\w.?]*\\.${PAYLOAD_FIELDS}\\b`);

describe('source guards', () => {
  it('the three FE files type no tag word outside comments, and no toFixed', async () => {
    for (const f of FE_FILES) {
      const src = await readSource(f);
      expect(code(src), f).not.toMatch(TAG_WORDS);
      expect(code(src), f).not.toMatch(/toFixed/);
    }
  });

  it('no >= / < compare on a served payload field in the three FE files', async () => {
    for (const f of FE_FILES) expect(code(await readSource(f)), f).not.toMatch(COMPARE);
  });

  it('NEGATIVE: the guards fire on a file that types a word or compares a served field', () => {
    expect(code("const x = 'Hard to borrow';")).toMatch(TAG_WORDS);
    expect(code('/* Hard to borrow */ const y = 1;')).not.toMatch(TAG_WORDS);
    expect(code('if (p.retry_after_sec >= 5) go();')).toMatch(COMPARE);
    expect(code('if (5 >= p.retry_after_sec) go();')).toMatch(COMPARE);
    expect(code('if (p.items.length < 3) go();')).toMatch(COMPARE);
    expect(code('const s = n.toFixed(1);')).toMatch(/toFixed/);
  });

  it('no b-word in any new FE file (Reversal, never the b-word)', async () => {
    for (const f of NEW_FILES) expect(await readSource(f), f).not.toMatch(new RegExp('boun' + 'c', 'i'));
  });

  it('[C12] the look is not the alarm: no --warn, no font-weight 700, and .gg-htb sets no color', async () => {
    const css = await readSource('src/styles/ggHardToBorrow.css');
    expect(css).not.toMatch(/--warn/);
    expect(css).not.toMatch(/font-weight:\s*(700|bold)/);
    const htb = rule(css, '.gg-htb');
    expect(htb).not.toBeNull();
    expect(htb).not.toMatch(/(^|[;\s])color\s*:/);
    expect(rule(css, '.gg-htb-label')).toMatch(/font-weight:\s*600/);
  });

  it('📱 .gg-htb wraps: white-space normal, overflow-wrap anywhere, min-width 0', async () => {
    const htb = rule(await readSource('src/styles/ggHardToBorrow.css'), '.gg-htb')!;
    expect(htb).toMatch(/white-space:\s*normal/);
    expect(htb).toMatch(/overflow-wrap:\s*anywhere/);
    expect(htb).toMatch(/min-width:\s*0\b/);
  });

  it('NEGATIVE: a sheet without the rule (or with the alarm look) fails the same matchers', () => {
    const PRE = '.gg-htb { font-weight: 700; color: var(--warn); }';
    const r = rule(PRE, '.gg-htb')!;
    expect(r).not.toMatch(/white-space:\s*normal/);
    expect(r).toMatch(/(^|[;\s])color\s*:/);
    expect(PRE).toMatch(/--warn/);
    expect(rule('.other { x: 1 }', '.gg-htb')).toBeNull();
  });

  it('the component imports its own sheet and the board CSS files are not edited for it', async () => {
    expect(await readSource('src/components/GgHardToBorrow.tsx')).toContain("import '../styles/ggHardToBorrow.css';");
    for (const f of ['src/styles/gajjala.css', 'src/styles/gajjalaWatch.css']) expect(await readSource(f), f).not.toMatch(/gg-htb/);
  });

  it('the SI components are not edited (siblings only)', async () => {
    for (const f of ['src/components/GgShortInterestLabel.tsx', 'src/components/GgSiExtremeNote.tsx',
      'src/components/ShortInterestChip.tsx', 'src/components/GajjalaWatchTags.tsx']) {
      expect(await readSource(f), f).not.toMatch(/HardToBorrow|regSho|RegSho/);
    }
  });
});
