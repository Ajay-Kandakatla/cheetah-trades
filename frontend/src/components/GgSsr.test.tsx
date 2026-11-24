/* ⛔ GgSsr chip / short / label / fault (2026-11-23, spec ssr §3.10 / §4 W4).
 *
 * Ajay 2026-11-23: "No shorting at the bid (SEC short-sale restriction)
 * Can we check or this for other stocks too?"
 *
 * The served words print verbatim (hover = the served title), through the REAL hook and lib with fetch stubbed. A form
 * the server serves as null draws NOTHING (no wrapper, no space); off and the quiet unknowns arrive as no item. Source
 * guards: the three FE files type no word and compare no served field and carry no admin email; the CSS is the neutral
 * look and wraps on the 430 px phone, `nowrap` only inside the fitted-tile media rule. Strings are stand-ins for served
 * ones (the spec §3.7 shapes). */
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GgSsrChip, GgSsrFault, GgSsrLabel } from './GgSsr';
import { _resetSsrCache } from '../hooks/useSsr';

const AKAN = {
  state: 'on', symbol: 'AKAN', source: 'computed', chip: '⛔ SSR · served chip · thru Tue 11/24 · computed', short: '⛔ SSR thru 11/24 · computed',
  label: '⛔ SSR on · served label · through Tue 11/24 · computed from the house\'s bars', title: 'served title AKAN', drop_pct: -13.0,
};
const GIPR = {
  state: 'on', symbol: 'GIPR', source: 'official', chip: '⛔ SSR · served chip · thru Mon 11/23', short: '⛔ SSR thru 11/23',
  label: '⛔ SSR on · served label · through Mon 11/23 · Nasdaq list', title: 'served title GIPR',
};
const PXED = { state: 'unknown', symbol: 'PXED', why: 'corp_action', chip: null, short: null, label: '⛔ SSR not read', title: 'served title PXED' };
const valid = (over: Record<string, unknown> = {}) => ({
  kind: 'ssr_rule_201', status: 'ok', items: { AKAN, GIPR, PXED },
  states: { AKAN: 'on', GIPR: 'on', PXED: 'unknown', AAPL: 'off', ZZCO: 'unknown' }, whys: { PXED: 'corp_action', ZZCO: 'computed_only' },
  asked: 5, n: 3, max_symbols: 200, fault_text: null, refreshing: false, retry_after_sec: null, keep_sec: 300, ...over,
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

beforeEach(() => { _resetSsrCache(); body = valid(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetSsrCache(); });

describe('chip / short / label / fault print the served text verbatim', () => {
  it('the chip prints the served chip, the served title, the testid, cm-badge gg-ssr, data-ssr-state', async () => {
    stub();
    render(<GgSsrChip symbol="GIPR" testid="gg-ssr-GIPR" />);
    const el = await screen.findByTestId('gg-ssr-GIPR');
    expect(el.tagName).toBe('SPAN');
    expect(el.textContent).toBe(GIPR.chip);
    expect(el.getAttribute('title')).toBe(GIPR.title);
    expect(el.className).toBe('cm-badge gg-ssr');
    expect(el.getAttribute('data-ssr-state')).toBe('on');
  });

  it('a computed read prints the served " · computed" tail verbatim (the FE adds nothing)', async () => {
    stub();
    render(<><GgSsrChip symbol="AKAN" testid="c" /><GgSsrChip symbol="AKAN" testid="s" form="short" /><GgSsrLabel symbol="AKAN" testid="l" /></>);
    expect((await screen.findByTestId('c')).textContent).toBe(AKAN.chip);
    expect(screen.getByTestId('s').textContent).toBe(AKAN.short);
    expect(screen.getByTestId('l').textContent).toBe(AKAN.label);
  });

  it('form="short" prints the served short form; a given className rides in front of gg-ssr', async () => {
    stub();
    render(<GgSsrChip symbol="GIPR" testid="t" className="ggw-chip" form="short" />);
    const el = await screen.findByTestId('t');
    expect(el.textContent).toBe(GIPR.short);
    expect(el.className).toBe('ggw-chip gg-ssr');
    expect(el.getAttribute('title')).toBe(GIPR.title);
  });

  it('lead puts ONE space before the chip; without lead there is none', async () => {
    stub();
    const { container } = render(<div><GgSsrChip symbol="GIPR" testid="a" lead /></div>);
    await screen.findByTestId('a');
    expect(container.firstElementChild!.firstChild!.nodeType).toBe(Node.TEXT_NODE);
    expect(container.firstElementChild!.firstChild!.textContent).toBe(' ');
    expect(container.firstElementChild!.childNodes).toHaveLength(2);
    cleanup();
    const r2 = render(<div><GgSsrChip symbol="GIPR" testid="b" /></div>);
    await screen.findByTestId('b');
    expect(r2.container.firstElementChild!.firstChild!.nodeType).toBe(Node.ELEMENT_NODE);
  });

  it('the label prints the served label and title as a DIV with cm-note gg-line gg-ssr-label', async () => {
    stub();
    render(<GgSsrLabel symbol="GIPR" testid="gg-ssr-label-GIPR" />);
    const el = await screen.findByTestId('gg-ssr-label-GIPR');
    expect(el.tagName).toBe('DIV');
    expect(el.textContent).toBe(GIPR.label);
    expect(el.getAttribute('title')).toBe(GIPR.title);
    expect(el.className).toBe('cm-note gg-line gg-ssr-label');
    expect(el.getAttribute('data-ssr-state')).toBe('on');
  });

  it('the fault prints the served fault_text as one DIV (cm-note cm-note-err gg-ssr-fault); a className replaces the default', async () => {
    body = valid({ fault_text: '⛔ SSR tags may be missing: served source text.' });
    stub();
    render(<><GgSsrChip symbol="GIPR" testid="c" /><GgSsrFault testid="f1" /><GgSsrFault testid="f2" className="x-line" /></>);
    const f1 = await screen.findByTestId('f1');
    expect(f1.tagName).toBe('DIV');
    expect(f1.textContent).toBe('⛔ SSR tags may be missing: served source text.');
    expect(f1.className).toBe('cm-note cm-note-err gg-ssr-fault');
    expect(screen.getByTestId('f2').className).toBe('x-line gg-ssr-fault');
  });

  it('chips, shorts and labels for five names on one screen cost ONE GET carrying each name once', async () => {
    const f = stub();
    render(<>
      <GgSsrChip symbol="AKAN" testid="a" />
      <GgSsrChip symbol="GIPR" testid="b" />
      <GgSsrChip symbol="AAPL" testid="c" form="short" />
      <GgSsrLabel symbol="PXED" testid="d" />
      <GgSsrLabel symbol="ZZCO" testid="e" />
      <GgSsrFault testid="f" />
    </>);
    await screen.findByTestId('d');
    expect(f).toHaveBeenCalledTimes(1);
    const u = new URL(String(f.mock.calls[0][0]));
    expect(u.pathname).toBe('/short-interest/ssr');
    expect((u.searchParams.get('symbols') || '').split(',').sort()).toEqual(['AAPL', 'AKAN', 'GIPR', 'PXED', 'ZZCO']);
  });
});

describe('NEGATIVES — off, quiet unknowns and null forms draw nothing', () => {
  for (const sym of ['AAPL', 'ZZCO'] as const) {
    it(`${sym} (${sym === 'AAPL' ? 'off' : 'computed_only'} — no item) → chip, short and label leave the parent HTML unchanged`, async () => {
      const f = stub();
      const { container } = render(<div className="row"><b>X</b><GgSsrChip symbol={sym} testid="c" lead />
        <GgSsrChip symbol={sym} testid="s" form="short" lead /><GgSsrLabel symbol={sym} testid="l" /><i>Y</i></div>);
      await settle(f);
      expect(container.innerHTML).toBe('<div class="row"><b>X</b><i>Y</i></div>');
    });
  }

  it('PXED (unknown, served chip: null / short: null) → the label only; no chip, no short, no stray space', async () => {
    const f = stub();
    const { container } = render(<div className="row"><b>X</b><GgSsrChip symbol="PXED" testid="c" lead />
      <GgSsrChip symbol="PXED" testid="s" form="short" lead /><GgSsrLabel symbol="PXED" testid="l" /><i>Y</i></div>);
    await settle(f);
    const l = await screen.findByTestId('l');
    expect(l.textContent).toBe(PXED.label);
    expect(l.getAttribute('data-ssr-state')).toBe('unknown');
    expect(screen.queryByTestId('c')).toBeNull();
    expect(screen.queryByTestId('s')).toBeNull();
    expect(container.innerHTML).toBe(`<div class="row"><b>X</b>${l.outerHTML}<i>Y</i></div>`);
  });

  it('no fault_text served → the fault draws nothing', async () => {
    const f = stub();
    const { container } = render(<div className="row"><GgSsrChip symbol="GIPR" testid="c" /><GgSsrFault testid="f" /></div>);
    await settle(f);
    await screen.findByTestId('c');
    expect(screen.queryByTestId('f')).toBeNull();
    expect(container.querySelector('.gg-ssr-fault')).toBeNull();
  });

  it('exact match: GIPR served → a GIPRW and a GIP chip draw nothing', async () => {
    const f = stub();
    const { container } = render(<><GgSsrChip symbol="GIPRW" testid="a" /><GgSsrLabel symbol="GIP" testid="b" /></>);
    await settle(f);
    expect(container.innerHTML).toBe('');
  });

  for (const [name, b] of [
    ['{}', {}], ['an array', [GIPR]], ['null', null],
    ['the 🔒 body', { kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, items: { GIPR: { state: 'on', chip: 'x', short: 'y', label: 'z', title: 't' } }, fault_text: 'x' }],
    ['the 💸 body', { kind: 'ibkr_borrow', status: 'ok', items: { GIPR: { state: 'listed', chip: 'x', short: 'y', label: 'z', title: 't', stale: false } }, max_symbols: 200 }],
    ['the 🩳 map body', { items: { GIPR: { symbol: 'GIPR', status: 'ok', chip: 'x', title: 'y', rows: [] } }, n: 1, max_symbols: 200 }],
  ] as const) {
    it(`no valid payload (${name}) → nothing on the chip, the short, the label and the fault`, async () => {
      body = b;
      const f = stub();
      const { container } = render(<><GgSsrChip symbol="GIPR" testid="a" /><GgSsrChip symbol="GIPR" testid="s" form="short" />
        <GgSsrLabel symbol="GIPR" testid="b" /><GgSsrFault testid="f" /></>);
      await settle(f);
      expect(container.innerHTML).toBe('');
    });
  }

  for (const mode of ['reject', 'sync'] as const) {
    it(`the request fails (${mode}) → nothing, no crash, one GET`, async () => {
      const f = stub(mode);
      const { container } = render(<><GgSsrChip symbol="GIPR" testid="a" /><GgSsrLabel symbol="GIPR" testid="b" /><GgSsrFault testid="f" /></>);
      await settle(f);
      expect(container.innerHTML).toBe('');
      expect(f).toHaveBeenCalledTimes(1);
    });
  }
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
/** The sheet with every @media block removed (what applies at the 430 px phone width for a min-width query). */
const outsideMedia = (css: string) => css.replace(/@media[^{]*\{(?:[^{}]*\{[^}]*\})*[^}]*\}/g, '');
const FE_FILES = ['src/components/GgSsr.tsx', 'src/hooks/useSsr.ts', 'src/lib/ssr.ts'];
const NEW_FILES = [...FE_FILES, 'src/styles/ggSsr.css', 'src/lib/ssr.test.ts', 'src/hooks/useSsr.test.ts', 'src/components/GgSsr.test.tsx',
  'src/components/GgSsr.payload.test.tsx', 'src/components/GajjalaBoard.ssr.test.tsx', 'src/components/GajjalaWatchTile.ssr.test.tsx'];
/** Case-sensitive tag words + case-insensitive rule words (the path '/short-interest/ssr' and 'ssr_rule_201' must pass). */
const WORDS_CS = /⛔|\bSSR\b|\bthru\b|Rule 201/;
const WORDS_CI = /shorting|short sale|short-sale|restriction|through|not read|computed|circuit breaker|best bid|at the bid/i;
const WORDS = { test: (s: string) => WORDS_CS.test(s) || WORDS_CI.test(s) };
const typed = (s: string) => WORDS.test(s);
const PAYLOAD_FIELDS = '(?:keep_sec|retry_after_sec|refreshing|items|state|chip|short|label|title|fault_text|drop_pct|prior_close|through|off_from|triggered_on|max_symbols|asked|n)';
const COMPARE = new RegExp(`\\.${PAYLOAD_FIELDS}\\b[^\\n;]*?\\s(>=|<=|>|<)\\s|\\s(>=|<=|>|<)\\s[\\w.?]*\\.${PAYLOAD_FIELDS}\\b`);
const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|ajaykandakatla|kathakoo/i;

describe('source guards', () => {
  it('the three FE files type no served SSR word outside comments, and no toFixed', async () => {
    for (const f of FE_FILES) {
      const src = await readSource(f);
      expect(typed(code(src)), f).toBe(false);
      expect(code(src), f).not.toMatch(/toFixed/);
    }
  });

  it('the path and the kind pass the word guard; the lib rejects by SSR_KIND', async () => {
    const lib = code(await readSource('src/lib/ssr.ts'));
    expect(lib).toContain("'/short-interest/ssr'");
    expect(lib).toContain("'ssr_rule_201'");
    expect(lib).toMatch(/j\.kind !== SSR_KIND/);
    expect(typed(lib)).toBe(false);
  });

  it('no >= / < compare on a served payload field in the three FE files', async () => {
    for (const f of FE_FILES) expect(code(await readSource(f)), f).not.toMatch(COMPARE);
  });

  it('no admin email (no email at all) in any of the three FE files', async () => {
    for (const f of FE_FILES) expect(await readSource(f), f).not.toMatch(EMAIL);
  });

  it('NEGATIVE: each guard fires on a file that types a word, compares a served field or carries an email', () => {
    for (const w of ["'⛔ SSR'", "'no shorting at the bid'", "'short sale'", "'restriction'", "'thru'", "'through Tue'", "'not read'",
      "' · computed'", "'Rule 201'"]) {
      expect(typed(code(`const x = ${w};`)), w).toBe(true);
    }
    expect(typed(code('/* ⛔ SSR no shorting at the bid */ const y = 1;'))).toBe(false);
    expect(typed(code('// short sale restriction\nconst y = 1;'))).toBe(false);
    expect(typed(code("const p = '/short-interest/ssr'; const k = 'ssr_rule_201'; const s = r.short; throw new Error('not an ssr payload');"))).toBe(false);
    expect(code('if (p.keep_sec >= 5) go();')).toMatch(COMPARE);
    expect(code('if (5 < p.retry_after_sec) go();')).toMatch(COMPARE);
    expect(code('if (it.drop_pct < -10) go();')).toMatch(COMPARE);
    expect(code('const ms = Math.max(5, p.keep_sec);')).not.toMatch(COMPARE);
    expect(code('const s = n.toFixed(1);')).toMatch(/toFixed/);
    expect("const who = 'someone@example.com';").toMatch(EMAIL);
  });

  it('no b-word in any new FE file (Reversal, never the b-word)', async () => {
    for (const f of NEW_FILES) expect(await readSource(f), f).not.toMatch(new RegExp('boun' + 'c', 'i'));
  });

  it('the look is neutral: no --warn, no --bad, no font-weight 700, .gg-ssr sets no color or background', async () => {
    const css = await readSource('src/styles/ggSsr.css');
    expect(css).not.toMatch(/--warn|--bad|--danger|--red/);
    expect(css).not.toMatch(/font-weight:\s*(700|bold)/);
    const ssr = rule(css, '.gg-ssr');
    expect(ssr).not.toBeNull();
    expect(ssr).not.toMatch(/(^|[;\s])(color|background)\s*:/);
    expect(rule(css, '.gg-ssr-label')).toMatch(/font-weight:\s*600/);
  });

  it('📱 .gg-ssr wraps at 430 px: white-space normal, overflow-wrap anywhere, min-width 0, max-width 100%', async () => {
    const ssr = rule(await readSource('src/styles/ggSsr.css'), '.gg-ssr')!;
    expect(ssr).toMatch(/white-space:\s*normal/);
    expect(ssr).toMatch(/overflow-wrap:\s*anywhere/);
    expect(ssr).toMatch(/min-width:\s*0\b/);
    expect(ssr).toMatch(/max-width:\s*100%/);
  });

  it('📱 NEGATIVE: no nowrap on .gg-ssr outside the fitted-tile media rule (min-width: 641px)', async () => {
    const css = await readSource('src/styles/ggSsr.css');
    expect(outsideMedia(css)).not.toMatch(/nowrap/);
    const media = css.match(/@media \(min-width: 641px\) \{([\s\S]*?)\n\}/);
    expect(media).not.toBeNull();
    expect(media![1]).toMatch(/\.ggw-grid--fit \.ggw-chip\.gg-ssr \{[^}]*white-space:\s*nowrap[^}]*text-overflow:\s*ellipsis/);
    expect(css.match(/nowrap/g) || []).toHaveLength(1);
  });

  it('NEGATIVE: the phone guards fail on a sheet that sets nowrap on .gg-ssr at every width, or has no wrap rule', () => {
    const BAD = '.gg-ssr { white-space: nowrap; color: var(--warn); }';
    expect(outsideMedia(BAD)).toMatch(/nowrap/);
    expect(rule(BAD, '.gg-ssr')).not.toMatch(/white-space:\s*normal/);
    expect(rule(BAD, '.gg-ssr')).toMatch(/(^|[;\s])color\s*:/);
    expect(rule('.other { x: 1 }', '.gg-ssr')).toBeNull();
    const OK = '@media (min-width: 641px) {\n  .a .b { white-space: nowrap; }\n}\n.c { x: 1 }';
    expect(outsideMedia(OK)).not.toMatch(/nowrap/);
  });

  it('the component imports its own sheet; the board sheets carry no gg-ssr', async () => {
    expect(await readSource('src/components/GgSsr.tsx')).toContain("import '../styles/ggSsr.css';");
    for (const f of ['src/styles/gajjala.css', 'src/styles/gajjalaWatch.css']) expect(await readSource(f), f).not.toMatch(/gg-ssr/);
  });

  it('the 🔒, 💸 and 🩳 FE files are not edited for it (siblings only)', async () => {
    for (const f of ['src/components/GgHardToBorrow.tsx', 'src/hooks/useRegSho.ts', 'src/lib/regSho.ts', 'src/styles/ggHardToBorrow.css',
      'src/components/GgBorrow.tsx', 'src/hooks/useBorrow.ts', 'src/lib/borrow.ts', 'src/styles/ggBorrow.css',
      'src/components/GgShortInterestLabel.tsx', 'src/components/GgSiExtremeNote.tsx', 'src/components/ShortInterestChip.tsx']) {
      expect(await readSource(f), f).not.toMatch(/GgSsr|useSsr|gg-ssr/);
    }
  });

  it('NOT placed on the 📋 All strategies table (HIS CALL 6)', async () => {
    expect(await readSource('src/components/GgAllTable.tsx')).not.toMatch(/GgSsr|useSsr|gg-ssr/);
  });
});
