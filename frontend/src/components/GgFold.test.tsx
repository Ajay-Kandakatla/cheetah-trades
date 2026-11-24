import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/* 🧹 GgFold (2026-11-24, ggclean spec §3.2 / §4 fold-core). Ajay: "Hide all of this nouce besides the scan button and
 * log trade button no explantions on the landing pages anymor" · "Add all of this too" · "Collapse all of this too".
 * GgFoldToggle / GgFoldBody / GgSubState / the two contexts. vitest runs with css: false → visibility is read through the
 * `hidden` attribute (toBeVisible) only; the stylesheet is guarded by reading its source. Every printed string below is a
 * SENTINEL ("served …"). NEGATIVES: null key → nothing / no wrapper; open fold → no state lines; unsafe hrefs → text;
 * blank / non-string text dropped; [C5] no hook-order warning when the key source flips; the CSS guard fails a sheet
 * without the [hidden] twin. */

const track = vi.fn();
vi.mock('../lib/usageTracker', () => ({ trackFeature: (k: string) => track(k) }));

import {
  GG_FOLD_GLYPH, GG_FOLD_TITLE, GgFoldBody, GgFoldToggle, GgHeadPageContext, GgSubFoldContext, GgSubState,
  type GgSubStateLine, useGgSubFold,
} from './GgFold';
import { resetGgFold, setGgFold } from '../lib/ggFold';
import { useContext } from 'react';

function fakeStorage(opts: { getThrows?: boolean; setThrows?: boolean } = {}) {
  const map = new Map<string, string>();
  return {
    map,
    get length() { return map.size; },
    clear: () => map.clear(),
    key: (i: number) => [...map.keys()][i] ?? null,
    getItem: (k: string) => { if (opts.getThrows) throw new Error('blocked'); return map.has(k) ? map.get(k)! : null; },
    setItem: (k: string, v: string) => { if (opts.setThrows) throw new Error('quota'); map.set(k, String(v)); },
    removeItem: (k: string) => { map.delete(k); },
  };
}

let ls: ReturnType<typeof fakeStorage>;
beforeEach(() => {
  ls = fakeStorage();
  vi.stubGlobal('localStorage', ls);
  resetGgFold();
  track.mockReset();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); resetGgFold(); });

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const Ctx = ({ k, children }: { k: string | null; children: React.ReactNode }) => (
  <MemoryRouter><GgSubFoldContext.Provider value={k}>{children}</GgSubFoldContext.Provider></MemoryRouter>
);

describe('GgFoldBody', () => {
  it('closed by default: children mounted but not visible; open → visible', () => {
    render(<GgFoldBody k="header" id="gg-head-body" testid="body"><p data-testid="kid">served line</p></GgFoldBody>);
    const body = screen.getByTestId('body');
    expect(body).toHaveAttribute('hidden');
    expect(body).toHaveAttribute('id', 'gg-head-body');
    expect(body).toHaveAttribute('data-fold', 'header');
    expect(body).toHaveClass('gg-fold-body');
    expect(screen.getByTestId('kid')).toBeInTheDocument();
    expect(screen.getByTestId('kid')).not.toBeVisible();
    act(() => setGgFold('header', true));
    expect(screen.getByTestId('kid')).toBeVisible();
    expect(body).not.toHaveAttribute('hidden');
  });
  it('stored "1" → open on first render', () => {
    ls.map.set('gg-fold:header', '1');
    render(<GgFoldBody k="header" testid="body"><p data-testid="kid">served line</p></GgFoldBody>);
    expect(screen.getByTestId('kid')).toBeVisible();
  });
  it('NEGATIVE: key null → no wrapper element (the container HTML equals the children\'s)', () => {
    const { container } = render(<GgFoldBody k={null} testid="body"><p data-testid="kid">served line</p><span>served two</span></GgFoldBody>);
    const bare = render(<><p data-testid="kid">served line</p><span>served two</span></>).container;
    expect(container.innerHTML).toBe(bare.innerHTML);
    expect(container.querySelector('.gg-fold-body')).toBeNull();
    expect(screen.queryByTestId('body')).toBeNull();
  });
  it('NEGATIVE: no k and no context → no wrapper', () => {
    const { container } = render(<GgFoldBody testid="body"><i>served</i></GgFoldBody>);
    expect(container.innerHTML).toBe('<i>served</i>');
  });
  it('reads the context key when k is absent; several bodies on one key move together, another key does not', () => {
    render(
      <Ctx k="sub:high_si">
        <GgFoldBody testid="a"><i>a</i></GgFoldBody>
        <GgFoldBody testid="b"><i>b</i></GgFoldBody>
        <GgFoldBody k="sub:bull_flag" testid="c"><i>c</i></GgFoldBody>
      </Ctx>,
    );
    expect(screen.getByTestId('a')).toHaveAttribute('data-fold', 'sub:high_si');
    act(() => setGgFold('sub:high_si', true));
    expect(screen.getByTestId('a')).toBeVisible();
    expect(screen.getByTestId('b')).toBeVisible();
    expect(screen.getByTestId('c')).not.toBeVisible();
  });
  it('NEGATIVE: getItem throws → closed and renders', () => {
    vi.stubGlobal('localStorage', fakeStorage({ getThrows: true }));
    render(<GgFoldBody k="header" testid="body"><i data-testid="kid">served</i></GgFoldBody>);
    expect(screen.getByTestId('kid')).not.toBeVisible();
  });
});

describe('GgFoldToggle', () => {
  it('glyph, title, aria-label, aria-controls; aria-expanded follows; writes "1" then "0"', () => {
    render(<GgFoldToggle k="header" testid="t" controls="gg-head-body" />);
    const t = screen.getByTestId('t');
    expect(t.tagName).toBe('BUTTON');
    expect(t).toHaveAttribute('type', 'button');
    expect(t).toHaveClass('gg-fold-toggle');
    expect(t.textContent).toBe(GG_FOLD_GLYPH);
    expect(GG_FOLD_GLYPH).toBe('ⓘ');
    expect(t).toHaveAttribute('title', GG_FOLD_TITLE);
    expect(t).toHaveAttribute('aria-label', GG_FOLD_TITLE);
    expect(t).toHaveAttribute('aria-controls', 'gg-head-body');
    expect(t).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(t);
    expect(t).toHaveAttribute('aria-expanded', 'true');
    expect(ls.map.get('gg-fold:header')).toBe('1');
    fireEvent.click(t);
    expect(t).toHaveAttribute('aria-expanded', 'false');
    expect(ls.map.get('gg-fold:header')).toBe('0');
  });
  it('toggle and body move together; a remount (fresh page) reads the stored state back', () => {
    const r = render(<><GgFoldToggle k="header" testid="t" /><GgFoldBody k="header" testid="b"><i data-testid="kid">x</i></GgFoldBody></>);
    fireEvent.click(screen.getByTestId('t'));
    expect(screen.getByTestId('kid')).toBeVisible();
    r.unmount();
    resetGgFold();
    render(<GgFoldBody k="header" testid="b"><i data-testid="kid">x</i></GgFoldBody>);
    expect(screen.getByTestId('kid')).toBeVisible();
  });
  it('trackFeature on open only', () => {
    render(<GgFoldToggle k="sub:high_si" testid="t" />);
    fireEvent.click(screen.getByTestId('t'));
    expect(track).toHaveBeenCalledTimes(1);
    expect(track).toHaveBeenCalledWith('gg-fold:sub:high_si');
    fireEvent.click(screen.getByTestId('t'));                 // closing — NEGATIVE: not counted
    expect(track).toHaveBeenCalledTimes(1);
  });
  it('NEGATIVE: key null → renders nothing; no k and no context → nothing', () => {
    const a = render(<GgFoldToggle k={null} testid="t" />);
    expect(a.container.innerHTML).toBe('');
    const b = render(<GgFoldToggle testid="t2" />);
    expect(b.container.innerHTML).toBe('');
  });
  it('reads the context key when k is absent', () => {
    render(<Ctx k="sub:all_strategies"><GgFoldToggle testid="t" /></Ctx>);
    fireEvent.click(screen.getByTestId('t'));
    expect(ls.map.get('gg-fold:sub:all_strategies')).toBe('1');
  });
  it('NEGATIVE: setItem throws → still toggles for the visit, no throw', () => {
    vi.stubGlobal('localStorage', fakeStorage({ setThrows: true }));
    render(<><GgFoldToggle k="header" testid="t" /><GgFoldBody k="header" testid="b"><i data-testid="kid">x</i></GgFoldBody></>);
    expect(() => fireEvent.click(screen.getByTestId('t'))).not.toThrow();
    expect(screen.getByTestId('t')).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('kid')).toBeVisible();
  });
});

describe('[C5] unconditional hooks — the key source flips on one instance', () => {
  it('k absent → k="x" → k={null} under a context key: no hook-order warning, each render resolves the right key', () => {
    const err = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    ls.map.set('gg-fold:ctx', '1');
    const tree = (k?: string | null) => (
      <Ctx k="ctx">
        <GgFoldToggle {...(k === undefined ? {} : { k })} testid="t" />
        <GgFoldBody {...(k === undefined ? {} : { k })} testid="b"><i>served</i></GgFoldBody>
      </Ctx>
    );
    const r = render(tree());
    expect(screen.getByTestId('t')).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('b')).toHaveAttribute('data-fold', 'ctx');
    r.rerender(tree('x'));
    expect(screen.getByTestId('t')).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByTestId('b')).toHaveAttribute('data-fold', 'x');
    r.rerender(tree(null));
    expect(screen.queryByTestId('t')).toBeNull();
    expect(screen.queryByTestId('b')).toBeNull();
    r.rerender(tree());
    expect(screen.getByTestId('b')).toHaveAttribute('data-fold', 'ctx');
    expect(err).not.toHaveBeenCalled();
  });
  it('source: no useContext inside a ternary in GgFold.tsx', async () => {
    const src = await readSource('src/components/GgFold.tsx');
    expect(src).not.toMatch(/\?[^;:\n]*useContext\(/);
    expect(src).not.toMatch(/:\s*useContext\(/);
  });
  it('NEGATIVE: the same matcher fires on the conditional form', () => {
    expect('const key = k !== undefined ? k : useContext(GgSubFoldContext);').toMatch(/:\s*useContext\(/);
  });
});

describe('contexts', () => {
  it('useGgSubFold reads GgSubFoldContext; no provider → no fold', () => {
    let seen: { on: boolean; open: boolean } | null = null;
    const Probe = () => { const f = useGgSubFold(); seen = { on: f.on, open: f.open }; return null; };
    render(<Probe />);
    expect(seen).toEqual({ on: false, open: true });
    render(<Ctx k="sub:x"><Probe /></Ctx>);
    expect(seen).toEqual({ on: true, open: false });
  });
  it('GgHeadPageContext carries a node; default null', () => {
    const Probe = () => <>{useContext(GgHeadPageContext)}</>;
    expect(render(<Probe />).container.innerHTML).toBe('');
    render(<GgHeadPageContext.Provider value={<b data-testid="pg">served row</b>}><Probe /></GgHeadPageContext.Provider>);
    expect(screen.getByTestId('pg')).toHaveTextContent('served row');
  });
});

describe('GgSubState', () => {
  const LINES: GgSubStateLine[] = [
    { kind: 'empty', key: 'empty', text: 'served empty' },
    { kind: 'chartless', key: 'AAA', text: 'served AAA listed', href: '/chart-maps/x?s=AAA' },
    { kind: 'chartless', key: 'BBB', text: 'served BBB listed', href: null },
    { kind: 'faults', key: 'faults', text: 'served faults' },
    { kind: 'fault', key: 'ssr', text: 'served ssr fault' },
  ];
  it('on + closed → the lines verbatim in order, with the panel classes; a safe href → link', () => {
    render(<Ctx k="sub:high_si"><GgSubState lines={LINES} /></Ctx>);
    const root = screen.getByTestId('gg-substate');
    expect(root).toHaveClass('gg-dv', 'gg-substate');
    expect([...root.children].map((c) => c.textContent)).toEqual(LINES.map((l) => l.text));
    expect([...root.children].map((c) => c.getAttribute('data-testid'))).toEqual([
      'gg-substate-empty', 'gg-substate-chartless-AAA', 'gg-substate-chartless-BBB', 'gg-substate-faults', 'gg-substate-fault-ssr',
    ]);
    expect(screen.getByTestId('gg-substate-empty').className).toBe('gg-dv-line');
    expect(screen.getByTestId('gg-substate-chartless-AAA').className).toBe('gg-dv-line gg-dv-chartless');
    expect(screen.getByTestId('gg-substate-faults').className).toBe('gg-dv-line cm-note');
    expect(screen.getByTestId('gg-substate-fault-ssr').className).toBe('gg-dv-line cm-note cm-note-err');
    expect(screen.getByTestId('gg-substate-chartless-AAA').querySelector('a')).toHaveAttribute('href', '/chart-maps/x?s=AAA');
    expect(screen.getByTestId('gg-substate-chartless-BBB').querySelector('a')).toBeNull();
  });
  it('NEGATIVE: fold open → nothing (the panel shows them in place, never twice)', () => {
    ls.map.set('gg-fold:sub:high_si', '1');
    const { container } = render(<Ctx k="sub:high_si"><GgSubState lines={LINES} /></Ctx>);
    expect(container.innerHTML).toBe('');
  });
  it('opening the fold removes the lines; closing brings them back', () => {
    render(<Ctx k="sub:high_si"><GgSubState lines={LINES} /></Ctx>);
    act(() => setGgFold('sub:high_si', true));
    expect(screen.queryByTestId('gg-substate')).toBeNull();
    act(() => setGgFold('sub:high_si', false));
    expect(screen.getByTestId('gg-substate')).toBeInTheDocument();
  });
  it('NEGATIVE: no context → nothing; no line → no root', () => {
    expect(render(<MemoryRouter><GgSubState lines={LINES} /></MemoryRouter>).container.innerHTML).toBe('');
    expect(render(<Ctx k="sub:x"><GgSubState lines={[]} /></Ctx>).container.innerHTML).toBe('');
  });
  it('NEGATIVE: //evil and javascript: hrefs → plain text', () => {
    render(
      <Ctx k="sub:x">
        <GgSubState lines={[
          { kind: 'chartless', key: 'EV', text: 'served ev', href: '//evil.example/x' },
          { kind: 'chartless', key: 'JS', text: 'served js', href: 'javascript:alert(1)' },
          { kind: 'chartless', key: 'HT', text: 'served ht', href: 'https://elsewhere.example/' },
        ]} />
      </Ctx>,
    );
    for (const id of ['EV', 'JS', 'HT']) {
      const p = screen.getByTestId(`gg-substate-chartless-${id}`);
      expect(p.querySelector('a')).toBeNull();
      expect(p.textContent).toBe(`served ${id.toLowerCase()}`);
    }
  });
  it('NEGATIVE: a non-string / blank text is dropped; all dropped → no root', () => {
    const junk = [
      { kind: 'empty', key: 'e', text: '' },
      { kind: 'faults', key: 'f', text: '   ' },
      { kind: 'fault', key: 'n', text: NaN },
      { kind: 'fault', key: 'u', text: undefined },
      { kind: 'chartless', key: 'z', text: 3 },
      null,
      { kind: 'other', key: 'o', text: 'served unknown kind' },
    ] as unknown as GgSubStateLine[];
    expect(render(<Ctx k="sub:x"><GgSubState lines={junk} /></Ctx>).container.innerHTML).toBe('');
    render(<Ctx k="sub:y"><GgSubState lines={[...junk, { kind: 'faults', key: 'f', text: 'served kept' }]} /></Ctx>);
    expect(screen.getByTestId('gg-substate').children).toHaveLength(1);
    expect(screen.getByTestId('gg-substate-faults')).toHaveTextContent('served kept');
  });
});

describe('CSS guards — ggFold.css (source read; vitest runs css: false)', () => {
  const rule = (css: string, sel: string): string | null => {
    const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const m = css.match(new RegExp(`(?:^|[}\\s,])${esc}\\s*\\{([^}]*)\\}`, 'm'));
    return m ? m[1] : null;
  };
  const hasTwin = (css: string) => /\.gg-fold-body\[hidden\]\s*\{\s*display:\s*none/.test(css)
    && /(?:^|\n)\.gg-fold-body\s*\{[^}]*display:\s*flex/.test(css);
  it('the [hidden] twin sits beside the .gg-fold-body display rule', async () => {
    const css = await readSource('src/styles/ggFold.css');
    expect(hasTwin(css)).toBe(true);
    const lines = css.split('\n');
    const a = lines.findIndex((l) => /^\.gg-fold-body\s*\{/.test(l));
    const b = lines.findIndex((l) => /^\.gg-fold-body\[hidden\]/.test(l));
    expect(b).toBe(a + 1);
  });
  it('NEGATIVE: a sheet without the twin fails the same matcher', () => {
    expect(hasTwin('.gg-fold-body { display: flex; flex-direction: column; }\n')).toBe(false);
    expect(hasTwin('.gg-fold-body[hidden] { display: none; }\n')).toBe(false);
  });
  it('.gg-actions wraps without overflowing; [C2] ⓘ at the row\'s right end', async () => {
    const css = await readSource('src/styles/ggFold.css');
    const act_ = rule(css, '.gg-actions') ?? '';
    expect(act_).toMatch(/display:\s*flex/);
    expect(act_).toMatch(/flex-wrap:\s*wrap/);
    expect(act_).toMatch(/min-width:\s*0/);
    const right = css.match(/([^{}]*\.gg-actions\s*>\s*\.gg-fold-toggle[^{}]*)\{([^}]*)\}/);
    expect(right).not.toBeNull();
    expect(right![2]).toMatch(/margin-left:\s*auto/);
    expect(right![1]).toMatch(/\.cm-phase\s*>\s*\.gg-fold-toggle/);
    expect(right![1]).toMatch(/\.gg-all-head\s*>\s*\.gg-fold-toggle/);
    expect(rule(css, '.gg-actions .gg-rescan') ?? '').toMatch(/margin-left:\s*0/);
  });
  it('NEGATIVE: no white-space: nowrap on .gg-fold-body; no new colour token', async () => {
    const css = await readSource('src/styles/ggFold.css');
    for (const m of css.matchAll(/([^{}]*)\{([^}]*)\}/g)) {
      if (/\.gg-fold-body/.test(m[1])) expect(m[2]).not.toMatch(/white-space:\s*nowrap/);
    }
    const tokens = new Set([...css.matchAll(/var\((--[a-z-]+)/g)].map((m) => m[1]));
    for (const t of tokens) expect(['--ink-subtle', '--hairline', '--ink'], t).toContain(t);
  });
});

describe('source guards — GgFold.tsx', () => {
  const code = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
  /* the non-printing literals: module paths, class names, testids, kinds, the button type — and the glyph + the one word */
  const ALLOWED = new Set([
    'react', 'react-router-dom', '../lib/gajjala', '../lib/ggFold', '../lib/usageTracker', '../styles/ggFold.css',
    'ⓘ', 'details', 'button', 'gg-fold-toggle', 'gg-fold-body', 'gg-dv gg-substate', 'gg-substate',
    'gg-dv-line', 'gg-dv-line gg-dv-chartless', 'gg-dv-line cm-note', 'gg-dv-line cm-note cm-note-err',
    'gg-substate-empty', 'gg-substate-faults', 'empty', 'chartless', 'faults', 'fault', 'kind', 'string', 'object', '',
  ]);
  const literals = (s: string) => [...code(s).matchAll(/'([^'\\]*)'|"([^"\\]*)"/g)].map((m) => m[1] ?? m[2]);
  const jsxText = (s: string) => [...code(s).matchAll(/>([^<>{}]*[^\s<>{}][^<>{}]*)<\//g)].map((m) => m[1].trim());
  it('the only typed word printed is GG_FOLD_TITLE (and the glyph)', async () => {
    const src = await readSource('src/components/GgFold.tsx');
    for (const l of literals(src)) expect(ALLOWED.has(l), l).toBe(true);
    expect(jsxText(src)).toEqual([]);
    expect(code(src).match(/'details'/g)).toHaveLength(1);
    expect(code(src)).toMatch(/export const GG_FOLD_TITLE = 'details'/);
  });
  it('NEGATIVE: the guards fire on a typed word', () => {
    expect(literals("const x = 'show more';").every((l) => ALLOWED.has(l))).toBe(false);
    expect(jsxText('const y = <p>show more</p>;')).toEqual(['show more']);
    expect(jsxText('const z = <p>{served}</p>;')).toEqual([]);
  });
  it('rendered: title / aria-label / text are the glyph and GG_FOLD_TITLE only', () => {
    const { container } = render(<GgFoldToggle k="header" />);
    expect(container.textContent).toBe('ⓘ');
    const attrs = [...container.querySelectorAll('*')].flatMap((e) => [e.getAttribute('title'), e.getAttribute('aria-label')])
      .filter(Boolean);
    expect(new Set(attrs)).toEqual(new Set(['details']));
  });
  it('no b-word, no email in GgFold.tsx / ggFold.css', async () => {
    for (const f of ['src/components/GgFold.tsx', 'src/styles/ggFold.css']) {
      const src = await readSource(f);
      expect(src, f).not.toMatch(/bounc/i);
      expect(src, f).not.toMatch(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/);
    }
  });
});
