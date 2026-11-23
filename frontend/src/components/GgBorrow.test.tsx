/* 💸 GgBorrow chip / short / label (2026-11-22, spec borrow §3.3 / §4 fe part A).
 *
 * Ajay 2026-11-22: "What is short borrow fee? Is that a real time value I saw AKAN has a high short borrow fee" — "yes i
 * need that please".
 *
 * The served words print verbatim (hover = the served title), through the REAL hook and lib with fetch stubbed. A form
 * the server serves as null draws NOTHING (no wrapper, no space) — an absent name's chip / short draws the moment the
 * server serves one [C1]. Source guards: the three FE files type no word and compare no served field; the CSS is the
 * neutral look and wraps on the phone; no Watch file names the component [C4]. */
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GgBorrowChip, GgBorrowLabel } from './GgBorrow';
import { _resetBorrowCache } from '../hooks/useBorrow';

const DBGI = {
  state: 'listed', symbol: 'DBGI', name: 'DIGITAL BRANDS GROUP INC',
  chip: '💸 Borrow 196% · 100K avail', short: '💸 196%',
  label: '💸 Borrow 196% a year · 100K shares available · IBKR file 2026.11.22 22:57:25',
  title: "Interactive Brokers borrow fee for DBGI (IBKR's row: DIGITAL BRANDS GROUP INC): served title.", stale: false,
  fee_pct: 196.2308, rebate_pct: -192.3508, available: 100000, available_floor: false,
};
const OLDN = {
  ...DBGI, symbol: 'OLDN', stale: true,
  chip: '💸 Borrow 196% · 100K avail · file 3h old', short: '💸 196% · file 3h old',
  label: '💸 Borrow 196% a year · 100K shares available · IBKR file 2026.11.22 22:57:25 · file 3h old', title: 'served stale title',
};
const AESG = { ...DBGI, symbol: 'AESG', chip: '💸 Borrow fee n/a · 90 avail', short: null, label: 'served label AESG', title: 'served title AESG' };
const AKAN = {
  state: 'absent', symbol: 'AKAN', name: null, chip: null, short: null, label: "💸 not in IBKR's borrow file",
  title: "AKAN is not in IBKR's borrow file: served title.", stale: false, fee_pct: null, rebate_pct: null, available: null, available_floor: false,
};
const UNRD = { ...AKAN, state: 'unread', symbol: 'UNRD', label: "💸 IBKR's borrow file could not be read", title: 'served unread title' };
const valid = (over: Record<string, unknown> = {}) => ({
  kind: 'ibkr_borrow', status: 'ok', stale: false, items: { DBGI, OLDN, AESG, AKAN, UNRD }, asked: 5, n: 5, max_symbols: 200,
  refreshing: false, retry_after_sec: null, keep_sec: 3600, ...over,
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

beforeEach(() => { _resetBorrowCache(); body = valid(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetBorrowCache(); });

describe('chip / short / label print the served text verbatim', () => {
  it('the chip prints the served chip, the served title, the testid, cm-badge gg-brw, data-brw-state', async () => {
    stub();
    render(<GgBorrowChip symbol="DBGI" testid="gg-brw-DBGI" />);
    const el = await screen.findByTestId('gg-brw-DBGI');
    expect(el.tagName).toBe('SPAN');
    expect(el.textContent).toBe(DBGI.chip);
    expect(el.getAttribute('title')).toBe(DBGI.title);
    expect(el.className).toBe('cm-badge gg-brw');
    expect(el.getAttribute('data-brw-state')).toBe('listed');
  });

  it('form="short" prints the served short form; a given className rides in front of gg-brw', async () => {
    stub();
    render(<GgBorrowChip symbol="DBGI" testid="t" className="x-chip" form="short" />);
    const el = await screen.findByTestId('t');
    expect(el.textContent).toBe(DBGI.short);
    expect(el.className).toBe('x-chip gg-brw');
    expect(el.getAttribute('title')).toBe(DBGI.title);
  });

  it('lead puts ONE space before the chip; without lead there is none', async () => {
    stub();
    const { container } = render(<div><GgBorrowChip symbol="DBGI" testid="a" lead /></div>);
    await screen.findByTestId('a');
    expect(container.firstElementChild!.firstChild!.nodeType).toBe(Node.TEXT_NODE);
    expect(container.firstElementChild!.firstChild!.textContent).toBe(' ');
    cleanup();
    const r2 = render(<div><GgBorrowChip symbol="DBGI" testid="b" /></div>);
    await screen.findByTestId('b');
    expect(r2.container.firstElementChild!.firstChild!.nodeType).toBe(Node.ELEMENT_NODE);
  });

  it('the label prints the served label and title as a DIV with cm-note gg-line gg-brw-label', async () => {
    stub();
    render(<GgBorrowLabel symbol="DBGI" testid="gg-brw-label-DBGI" />);
    const el = await screen.findByTestId('gg-brw-label-DBGI');
    expect(el.tagName).toBe('DIV');
    expect(el.textContent).toBe(DBGI.label);
    expect(el.getAttribute('title')).toBe(DBGI.title);
    expect(el.className).toBe('cm-note gg-line gg-brw-label');
    expect(el.getAttribute('data-brw-state')).toBe('listed');
  });

  it('stale → gg-brw-stale and the served " · file 3h old" text on chip, short and label', async () => {
    stub();
    render(<>
      <GgBorrowChip symbol="OLDN" testid="c" />
      <GgBorrowChip symbol="OLDN" testid="s" form="short" />
      <GgBorrowLabel symbol="OLDN" testid="l" />
    </>);
    const c = await screen.findByTestId('c');
    expect(c.className).toBe('cm-badge gg-brw gg-brw-stale');
    expect(c.textContent).toBe(OLDN.chip);
    expect(screen.getByTestId('s').textContent).toBe(OLDN.short);
    expect(screen.getByTestId('l').className).toBe('cm-note gg-line gg-brw-label gg-brw-stale');
    for (const id of ['c', 's', 'l']) expect(screen.getByTestId(id).textContent).toMatch(/ · file 3h old$/);
  });

  it('[C1] an absent item served WITH a chip and a short prints both (the server switch needs no FE change)', async () => {
    body = valid({ items: { AKAN: { ...AKAN, chip: "💸 not in IBKR's file", short: '💸 not in file' } } });
    stub();
    render(<>
      <GgBorrowChip symbol="AKAN" testid="c" />
      <GgBorrowChip symbol="AKAN" testid="s" form="short" />
      <GgBorrowLabel symbol="AKAN" testid="l" />
    </>);
    expect((await screen.findByTestId('c')).textContent).toBe("💸 not in IBKR's file");
    expect(screen.getByTestId('s').textContent).toBe('💸 not in file');
    expect(screen.getByTestId('l').textContent).toBe(AKAN.label);
    for (const id of ['c', 's', 'l']) expect(screen.getByTestId(id).getAttribute('data-brw-state')).toBe('absent');
  });

  it('chips, shorts and labels for five names on one screen cost ONE GET carrying each name once', async () => {
    const f = stub();
    render(<>
      <GgBorrowChip symbol="DBGI" testid="a" />
      <GgBorrowChip symbol="OLDN" testid="b" />
      <GgBorrowChip symbol="AESG" testid="c" form="short" />
      <GgBorrowLabel symbol="AKAN" testid="d" />
      <GgBorrowLabel symbol="DBGI" testid="e" />
    </>);
    await screen.findByTestId('d');
    expect(f).toHaveBeenCalledTimes(1);
    const u = new URL(String(f.mock.calls[0][0]));
    expect(u.pathname).toBe('/short-interest/borrow');
    expect((u.searchParams.get('symbols') || '').split(',').sort()).toEqual(['AESG', 'AKAN', 'DBGI', 'OLDN']);
  });
});

describe('NEGATIVES — a null form draws nothing', () => {
  for (const sym of ['AKAN', 'UNRD'] as const) {
    it(`${sym} (served chip: null / short: null) → the label only; chip and short leave the parent HTML unchanged`, async () => {
      const f = stub();
      const { container } = render(<div className="row"><b>X</b><GgBorrowChip symbol={sym} testid="c" lead />
        <GgBorrowChip symbol={sym} testid="s" form="short" /><i>Y</i></div>);
      await settle(f);
      expect(container.innerHTML).toBe('<div class="row"><b>X</b><i>Y</i></div>');
      cleanup();
      _resetBorrowCache();
      stub();
      render(<GgBorrowLabel symbol={sym} testid="l" />);
      const l = await screen.findByTestId('l');
      expect(l.textContent).toBe(sym === 'AKAN' ? AKAN.label : UNRD.label);
      expect(l.getAttribute('data-brw-state')).toBe(sym === 'AKAN' ? 'absent' : 'unread');
    });
  }

  it('AESG (fee NA, served short: null) → the chip draws, the short draws nothing', async () => {
    const f = stub();
    const { container } = render(<><GgBorrowChip symbol="AESG" testid="c" /><span data-testid="gap" /><GgBorrowChip symbol="AESG" testid="s" form="short" /></>);
    await settle(f);
    expect(screen.getByTestId('c').textContent).toBe(AESG.chip);
    expect(screen.queryByTestId('s')).toBeNull();
    expect(screen.getByTestId('gap').nextSibling).toBeNull();
    expect(container.querySelectorAll('.gg-brw')).toHaveLength(1);
  });

  it('a name the payload does not serve → the HTML equals the same mount without it (no wrapper, no space)', async () => {
    const f = stub();
    const { container } = render(<div className="row"><b>X</b><GgBorrowChip symbol="ZZZZ" testid="z" lead /><GgBorrowLabel symbol="ZZZZ" testid="zl" /><i>Y</i></div>);
    await settle(f);
    const html = container.innerHTML;
    expect(html).toBe('<div class="row"><b>X</b><i>Y</i></div>');
  });

  it('exact match: DBGI served → a DBGIW and a DBG chip draw nothing', async () => {
    const f = stub();
    const { container } = render(<><GgBorrowChip symbol="DBGIW" testid="a" /><GgBorrowLabel symbol="DBG" testid="b" /></>);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  for (const [name, b] of [
    ['{}', {}], ['an array', [DBGI]], ['null', null],
    ['the 🔒 body', { kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, items: { DBGI: { state: 'on', chip: 'x', short: 'y', label: 'z', title: 't' } }, fault_text: null }],
    ['the 🩳 map body', { items: { DBGI: { symbol: 'DBGI', status: 'ok', chip: 'x', title: 'y', rows: [] } }, n: 1, max_symbols: 200 }],
  ] as const) {
    it(`foreign body (${name}) → nothing on the chip, the short and the label`, async () => {
      body = b;
      const f = stub();
      const { container } = render(<><GgBorrowChip symbol="DBGI" testid="a" /><GgBorrowChip symbol="DBGI" testid="s" form="short" />
        <GgBorrowLabel symbol="DBGI" testid="b" /></>);
      await settle(f);
      expect(container.innerHTML).toBe('');
    });
  }

  for (const mode of ['reject', 'sync'] as const) {
    it(`the request fails (${mode}) → nothing, no crash, one GET`, async () => {
      const f = stub(mode);
      const { container } = render(<><GgBorrowChip symbol="DBGI" testid="a" /><GgBorrowLabel symbol="DBGI" testid="b" /></>);
      await settle(f);
      expect(container.innerHTML).toBe('');
      expect(f).toHaveBeenCalledTimes(1);
    });
  }

  it('an ok read never carries gg-brw-stale', async () => {
    stub();
    render(<><GgBorrowChip symbol="DBGI" testid="a" /><GgBorrowLabel symbol="DBGI" testid="b" /></>);
    expect((await screen.findByTestId('a')).className).not.toContain('gg-brw-stale');
    expect(screen.getByTestId('b').className).not.toContain('gg-brw-stale');
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
const FE_FILES = ['src/components/GgBorrow.tsx', 'src/hooks/useBorrow.ts', 'src/lib/borrow.ts'];
const NEW_FILES = [...FE_FILES, 'src/styles/ggBorrow.css', 'src/lib/borrow.test.ts', 'src/hooks/useBorrow.test.ts',
  'src/components/GgBorrow.test.tsx'];
const WORDS = /💸|IBKR|Interactive Brokers|\bavail\b|a year|borrow file|not in file/;
const PAYLOAD_FIELDS = '(?:keep_sec|retry_after_sec|refreshing|stale|items|state|chip|short|label|title|fee_pct|rebate_pct|available|available_floor|max_symbols|asked|n)';
const COMPARE = new RegExp(`\\.${PAYLOAD_FIELDS}\\b[^\\n;]*?\\s(>=|<=|>|<)\\s|\\s(>=|<=|>|<)\\s[\\w.?]*\\.${PAYLOAD_FIELDS}\\b`);
const WATCH_FILES = ['src/components/GajjalaWatchTile.tsx', 'src/components/GajjalaWatchBoard.tsx', 'src/lib/gajjalaWatch.ts'];
const NAMES_IT = /GgBorrow|useBorrow|gg-brw/;

describe('source guards', () => {
  it('the three FE files type no served word outside comments, and no toFixed', async () => {
    for (const f of FE_FILES) {
      const src = await readSource(f);
      expect(code(src), f).not.toMatch(WORDS);
      expect(code(src), f).not.toMatch(/toFixed/);
    }
  });

  it('the path and the kind pass the word guard (case-sensitive)', async () => {
    const lib = code(await readSource('src/lib/borrow.ts'));
    expect(lib).toContain("'/short-interest/borrow'");
    expect(lib).toContain("'ibkr_borrow'");
    expect(lib).not.toMatch(WORDS);
  });

  it('no >= / < compare on a served payload field in the three FE files', async () => {
    for (const f of FE_FILES) expect(code(await readSource(f)), f).not.toMatch(COMPARE);
  });

  it('NEGATIVE: each guard fires on a file that types a word or compares a served field', () => {
    for (const w of ["'💸 Borrow'", "'IBKR'", "'Interactive Brokers'", "'100K avail'", "'196% a year'", "'borrow file'", "'not in file'"]) {
      expect(code(`const x = ${w};`), w).toMatch(WORDS);
    }
    expect(code("/* 💸 IBKR a year */ const y = 1;")).not.toMatch(WORDS);
    expect(code("// IBKR borrow file\nconst y = 1;")).not.toMatch(WORDS);
    expect(code("const p = '/short-interest/borrow'; const k = 'ibkr_borrow'; const a = r.available;")).not.toMatch(WORDS);
    expect(code('if (p.keep_sec >= 5) go();')).toMatch(COMPARE);
    expect(code('if (5 < p.retry_after_sec) go();')).toMatch(COMPARE);
    expect(code('if (it.fee_pct > 10) go();')).toMatch(COMPARE);
    expect(code('const ms = Math.max(5, p.keep_sec);')).not.toMatch(COMPARE);
    expect(code('const s = n.toFixed(1);')).toMatch(/toFixed/);
  });

  it('no b-word in any new FE file (Reversal, never the b-word)', async () => {
    for (const f of NEW_FILES) expect(await readSource(f), f).not.toMatch(new RegExp('boun' + 'c', 'i'));
  });

  it('the look is neutral: no --warn, no font-weight 700, .gg-brw sets no color, no Watch (.ggw-) rule', async () => {
    const css = await readSource('src/styles/ggBorrow.css');
    expect(css).not.toMatch(/--warn/);
    expect(css).not.toMatch(/font-weight:\s*(700|bold)/);
    expect(css).not.toMatch(/\.ggw-/);
    expect(css).not.toMatch(/gg-htb/);
    const brw = rule(css, '.gg-brw');
    expect(brw).not.toBeNull();
    expect(brw).not.toMatch(/(^|[;\s])color\s*:/);
    expect(rule(css, '.gg-brw-label')).toMatch(/font-weight:\s*600/);
    expect(rule(css, '.gg-brw-stale')).toMatch(/color:\s*var\(--ink-subtle/);
    expect(css).toMatch(/\.gg-all-table td\.gg-all-si \.gg-brw \{[^}]*white-space:\s*nowrap/);
  });

  it('📱 .gg-brw wraps: white-space normal, overflow-wrap anywhere, min-width 0, max-width 100%', async () => {
    const brw = rule(await readSource('src/styles/ggBorrow.css'), '.gg-brw')!;
    expect(brw).toMatch(/white-space:\s*normal/);
    expect(brw).toMatch(/overflow-wrap:\s*anywhere/);
    expect(brw).toMatch(/min-width:\s*0\b/);
    expect(brw).toMatch(/max-width:\s*100%/);
  });

  it('NEGATIVE: a sheet without the rule, with the alarm look or with a Watch rule fails the same matchers', () => {
    const PRE = '.gg-brw { font-weight: 700; color: var(--warn); }\n.ggw-chip.gg-brw { flex: 0 1 auto; }';
    const r = rule(PRE, '.gg-brw')!;
    expect(r).not.toMatch(/white-space:\s*normal/);
    expect(r).toMatch(/(^|[;\s])color\s*:/);
    expect(PRE).toMatch(/--warn/);
    expect(PRE).toMatch(/font-weight:\s*(700|bold)/);
    expect(PRE).toMatch(/\.ggw-/);
    expect(rule('.other { x: 1 }', '.gg-brw')).toBeNull();
  });

  it('the component imports its own sheet; the board sheets carry no gg-brw', async () => {
    expect(await readSource('src/components/GgBorrow.tsx')).toContain("import '../styles/ggBorrow.css';");
    for (const f of ['src/styles/gajjala.css', 'src/styles/gajjalaWatch.css']) expect(await readSource(f), f).not.toMatch(/gg-brw/);
  });

  it('the 🔒 and 🩳 FE files are not edited for it (siblings only)', async () => {
    for (const f of ['src/components/GgHardToBorrow.tsx', 'src/hooks/useRegSho.ts', 'src/lib/regSho.ts', 'src/styles/ggHardToBorrow.css',
      'src/components/GgShortInterestLabel.tsx', 'src/components/GgSiExtremeNote.tsx', 'src/components/ShortInterestChip.tsx',
      'src/hooks/useShortInterest.ts', 'src/lib/shortInterest.ts', 'src/components/GajjalaWatchTags.tsx']) {
      expect(await readSource(f), f).not.toMatch(NAMES_IT);
    }
  });

  it('[C4] no Watch file names GgBorrow / useBorrow / gg-brw (the 👀 Watch mount is not built — his call)', async () => {
    for (const f of WATCH_FILES) expect(await readSource(f), f).not.toMatch(NAMES_IT);
  });

  it('NEGATIVE: the Watch guard fires on a file that mounts the chip', () => {
    expect("import { GgBorrowChip } from './GgBorrow';").toMatch(NAMES_IT);
    expect('<span className="ggw-chip gg-brw" />').toMatch(NAMES_IT);
    expect("const { read } = useBorrow(sym);").toMatch(NAMES_IT);
  });
});
