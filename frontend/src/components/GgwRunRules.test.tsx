/* ▶ GgwRunRules — the button, the panel and the hook, alone (2026-11-24, spec ggrun §3.5 / §4 fe-run).
 * Ajay 2026-11-24: "…so can check for patterns mid day when I can add a small slide in in the chart window for giving
 * verbatim of passed rules and failed rules of that stock like you do in other tabs..".
 * Positives: the panel prints title, as-of, scanner, float, volume, note and per setup label / state pill / gate sentence
 * (right under the pill) / plan / tally / rows VERBATIM, in served order; the hook makes ONE POST per tap.
 * NEGATIVES: a served non-ok sentence prints alone; a `none` setup has no ✓ and no list; a null gate prints no node; a
 * shuffled order is drawn as served; busy → disabled + aria-busy, two clicks → ONE POST; ✕ while busy closes, enables
 * the button and the late answer prints NOTHING; 404 → nothing; 500 + served detail → that string; 500 without / a
 * reject / junk → GGW_RUN.failed; the files type no rule word, no owner check, no timer; the CSS guards.
 * Every word in the fixture is a stand-in for a served one. */
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { GgwRunButton, GgwRunPanel, useGgwRun, type GgwRunState } from './GgwRunRules';
import { API } from '../lib/apiBase';
import { GGW_RUN, ggwRunPath, ggwRunTitle, parseGgwRun, type GgwRunAnswer } from '../lib/ggwRun';
import runSrc from './GgwRunRules.tsx?raw';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const SETUP = (setup: string, extra: Record<string, unknown> = {}) => ({
  setup, label: `served label ${setup}`, state: 'partial', state_label: `served state words ${setup}`, gate_text: null,
  plan_text: `served plan ${setup}`, variant_label: null, grade_label: null, vol_dried_text: null, frame: '5m',
  as_of_bar_t: '2026-11-24 10:35',
  criteria: [
    { key: `${setup}_a`, label: `served row a ${setup}`, ok: true, value: 'served value a', need: 'served need a' },
    { key: `${setup}_b`, label: `served row b ${setup}`, ok: false, value: null, need: null },
  ],
  tally_text: `served tally ${setup}`, ...extra,
});
const RAW = {
  state: 'ok', symbol: 'OMH', title: 'served title OMH', text: null,
  as_of: { bar_t5: '2026-11-24 10:35', bar_t15: '2026-11-24 10:30', read_at_et: '10:36:12', text: 'served as-of line' },
  reused_text: 'served reused line', scanner: { listed: false, text: 'served scanner line' }, float_text: 'served float line',
  volume_text: 'served volume line', note: 'served note line',
  setups: [
    SETUP('reversal_squeeze', { state: 'none', state_label: 'served none words', gate_text: 'served gate sentence',
      criteria: [], tally_text: null, plan_text: null, frame: null }),
    SETUP('bull_flag', { variant_label: 'served variant', grade_label: 'served grade', vol_dried_text: 'served dried' }),
    SETUP('kiss_fly'), SETUP('horizontal_fade'), SETUP('intraday_vcp'),
  ],
};
const done = (raw: unknown = RAW): GgwRunState => ({ phase: 'done', a: parseGgwRun(clone(raw)) as GgwRunAnswer });
const panel = (state: GgwRunState | null, onClose = () => {}) => render(<GgwRunPanel sym="OMH" state={state} onClose={onClose} />);
const T = (id: string) => screen.queryByTestId(id);

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('GgwRunPanel — the served words, verbatim', () => {
  it('prints title, reused, as-of, scanner, float, volume, note — each verbatim, in that order', () => {
    panel(done());
    const p = screen.getByTestId('ggw-run-OMH');
    expect(p.tagName).toBe('ASIDE');
    expect(p.getAttribute('role')).toBe('region');
    expect(p.getAttribute('aria-label')).toBe('served title OMH');
    expect(T('ggw-run-title')!.textContent).toBe('served title OMH');
    const ids = ['ggw-run-reused', 'ggw-run-asof', 'ggw-run-scanner', 'ggw-run-float', 'ggw-run-volume'];
    const words = ['served reused line', 'served as-of line', 'served scanner line', 'served float line', 'served volume line'];
    ids.forEach((id, i) => expect(T(id)!.textContent, id).toBe(words[i]));
    expect(T('ggw-run-note')!.textContent).toBe('served note line');
    const order = Array.from(p.querySelectorAll('[data-testid]')).map((e) => e.getAttribute('data-testid'));
    const at = (id: string) => order.indexOf(id);
    for (let i = 1; i < ids.length; i += 1) expect(at(ids[i - 1])).toBeLessThan(at(ids[i]));
    expect(at('ggw-run-volume')).toBeLessThan(at('ggw-run-setup-reversal_squeeze'));
    expect(at('ggw-run-setup-intraday_vcp')).toBeLessThan(at('ggw-run-note'));
    expect(T('ggw-run-text')).toBeNull();
    expect(T('ggw-run-busy')).toBeNull();
  });
  it('per setup: label, state pill, plan, tally, rows verbatim; the gate sentence RIGHT under the pill', () => {
    panel(done());
    const rs = screen.getByTestId('ggw-run-setup-reversal_squeeze');
    expect(rs.getAttribute('data-state')).toBe('none');
    expect(rs.querySelector('h4')!.textContent).toBe('served label reversal_squeeze');
    const pill = within(rs).getByTestId('ggw-run-state-reversal_squeeze');
    expect(pill.className).toBe('gg-state gg-state-none');
    expect(pill.textContent).toBe('served none words');
    const gate = within(rs).getByTestId('ggw-run-gate-reversal_squeeze');
    expect(gate.textContent).toBe('served gate sentence');
    expect(pill.nextElementSibling).toBe(gate);
    const bf = screen.getByTestId('ggw-run-setup-bull_flag');
    expect(within(bf).getByTestId('ggw-run-state-bull_flag').className).toBe('gg-state gg-state-partial');
    expect(within(bf).getByTestId('ggw-run-plan-bull_flag').textContent).toBe('served plan bull_flag');
    expect(within(bf).getByTestId('ggw-run-tally-bull_flag').textContent).toBe('served tally bull_flag');
    expect(within(bf).getByTestId('ggw-run-variant-bull_flag').textContent).toBe('served variant');
    expect(within(bf).getByTestId('ggw-run-grade-bull_flag').textContent).toBe('served grade');
    expect(within(bf).getByTestId('ggw-run-vol-dried-bull_flag').textContent).toBe('served dried');
    const lis = Array.from(bf.querySelectorAll('ul.gg-criteria > li'));
    expect(lis.map((l) => [l.className, l.textContent])).toEqual([
      ['gg-ok', '✓ served row a bull_flag — served value a (served need a)'],
      ['gg-miss', '✗ served row b bull_flag'],
    ]);
  });
  it('five sections, 🎾 first, in SERVED order; NEGATIVE: a shuffled served order is drawn as served', () => {
    const { container } = panel(done());
    const secs = () => Array.from(container.querySelectorAll('section')).map((s) => s.getAttribute('data-testid'));
    expect(secs()).toEqual(['reversal_squeeze', 'bull_flag', 'kiss_fly', 'horizontal_fade', 'intraday_vcp'].map((s) => `ggw-run-setup-${s}`));
    cleanup();
    const b = clone(RAW);
    b.setups = [b.setups[2], b.setups[4], b.setups[0], b.setups[3], b.setups[1]];
    const r = panel(done(b));
    expect(Array.from(r.container.querySelectorAll('section')).map((s) => s.getAttribute('data-testid')))
      .toEqual(['kiss_fly', 'intraday_vcp', 'reversal_squeeze', 'horizontal_fade', 'bull_flag'].map((s) => `ggw-run-setup-${s}`));
  });
  it('NEGATIVE: a `none` setup → no .gg-ok, no gg-criteria list, no plan, no tally', () => {
    panel(done());
    const rs = screen.getByTestId('ggw-run-setup-reversal_squeeze');
    expect(rs.querySelector('.gg-ok')).toBeNull();
    expect(rs.querySelector('.gg-criteria')).toBeNull();
    expect(within(rs).queryByTestId('ggw-run-plan-reversal_squeeze')).toBeNull();
    expect(within(rs).queryByTestId('ggw-run-tally-reversal_squeeze')).toBeNull();
  });
  it('NEGATIVE: a null gate_text prints no gate node (on the four other setups, and on 🎾 when not served)', () => {
    panel(done());
    for (const s of ['bull_flag', 'kiss_fly', 'horizontal_fade', 'intraday_vcp']) expect(T(`ggw-run-gate-${s}`), s).toBeNull();
    expect(document.querySelectorAll('.ggw-run-gate')).toHaveLength(1);
    cleanup();
    const b = clone(RAW);
    b.setups[0].gate_text = null;
    panel(done(b));
    expect(document.querySelectorAll('.ggw-run-gate')).toHaveLength(0);
  });
  it('NEGATIVE: a served non-ok sentence (not listed / closed / no prints / busy) prints ALONE — no section, no ✓', () => {
    for (const st of ['not_listed', 'closed', 'no_prints', 'busy']) {
      const raw = { state: st, symbol: 'OMH', title: 'served title OMH', text: `served ${st} sentence`, as_of: null,
        reused_text: null, scanner: null, float_text: null, volume_text: null, note: 'served note line', setups: [] };
      const { container } = panel(done(raw));
      expect(T('ggw-run-text')!.textContent, st).toBe(`served ${st} sentence`);
      expect(container.querySelector('section'), st).toBeNull();
      expect(container.querySelector('.gg-ok, .gg-criteria'), st).toBeNull();
      expect(container.textContent, st).not.toContain('✓');
      for (const id of ['ggw-run-asof', 'ggw-run-scanner', 'ggw-run-float', 'ggw-run-volume', 'ggw-run-reused', 'ggw-run-busy']) {
        expect(T(id), `${st} ${id}`).toBeNull();
      }
      cleanup();
    }
  });
  it('busy: the busy word only, the fallback title, an enabled ✕; failed: the failed text', () => {
    const onClose = vi.fn();
    panel({ phase: 'busy' }, onClose);
    const p = screen.getByTestId('ggw-run-OMH');
    expect(p.getAttribute('aria-busy')).toBe('true');
    expect(T('ggw-run-busy')!.textContent).toBe(GGW_RUN.busy);
    expect(T('ggw-run-title')!.textContent).toBe(ggwRunTitle('OMH'));
    expect(p.querySelectorAll('p')).toHaveLength(1);
    const x = screen.getByTestId('ggw-run-close-OMH') as HTMLButtonElement;
    expect(x.disabled).toBe(false);
    expect(x.textContent).toBe(GGW_RUN.close);
    fireEvent.click(x);
    expect(onClose).toHaveBeenCalledWith('OMH');
    cleanup();
    panel({ phase: 'failed', text: 'served detail words' });
    expect(T('ggw-run-text')!.textContent).toBe('served detail words');
    expect(T('ggw-run-title')!.textContent).toBe(ggwRunTitle('OMH'));
    expect(document.querySelector('section')).toBeNull();
  });
  it('NEGATIVE: state null → nothing at all', () => {
    const { container } = panel(null);
    expect(container.innerHTML).toBe('');
  });
});

describe('GgwRunButton', () => {
  it('"▶ Rules", titled by the symbol, aria-expanded on an open state; busy → disabled + aria-busy', () => {
    const onRun = vi.fn();
    const { rerender } = render(<GgwRunButton sym="OMH" state={null} onRun={onRun} />);
    const b = screen.getByTestId('ggw-run-btn-OMH') as HTMLButtonElement;
    expect(b.textContent).toBe('▶ Rules');
    expect(b.className).toBe('ggw-btn ggw-run-btn');
    expect(b.getAttribute('title')).toBe(ggwRunTitle('OMH'));
    expect(b.getAttribute('aria-label')).toBe(ggwRunTitle('OMH'));
    expect(b.getAttribute('aria-expanded')).toBe('false');
    expect(b.hasAttribute('aria-busy')).toBe(false);
    fireEvent.click(b);
    expect(onRun).toHaveBeenCalledWith('OMH');
    rerender(<GgwRunButton sym="OMH" state={{ phase: 'busy' }} onRun={onRun} />);
    expect(b.disabled).toBe(true);
    expect(b.getAttribute('aria-busy')).toBe('true');
    expect(b.getAttribute('aria-expanded')).toBe('true');
    rerender(<GgwRunButton sym="OMH" state={done()} onRun={onRun} />);
    expect(b.disabled).toBe(false);
    expect(b.getAttribute('aria-expanded')).toBe('true');
  });
});

/* ── the hook, through a tiny harness (the board's own wiring is tested on the real board) ── */
function Harness({ syms = ['OMH'] }: { syms?: string[] }) {
  const r = useGgwRun();
  return (
    <div>
      {syms.map((s) => (
        <div key={s} data-testid={`h-${s}`}>
          <GgwRunButton sym={s} state={r.stateOf(s)} onRun={r.run} />
          <GgwRunPanel sym={s} state={r.stateOf(s)} onClose={r.close} />
        </div>
      ))}
    </div>
  );
}
type Pending = { resolve: (r: Response) => void; reject: (e: unknown) => void; url: string; init?: RequestInit };
let pend: Pending[] = [];
const resp = (status: number, body: unknown, junk = false) => ({
  ok: status >= 200 && status < 300, status,
  json: async () => { if (junk) throw new SyntaxError('junk'); return body; },
} as unknown as Response);
const flush = async () => { for (let i = 0; i < 5; i += 1) await act(async () => { await Promise.resolve(); }); };

describe('useGgwRun — ONE POST per tap, the token, the outcomes', () => {
  beforeEach(() => {
    pend = [];
    vi.stubGlobal('fetch', vi.fn((u: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((resolve, reject) => {
      pend.push({ resolve, reject, url: String(u), init });
    })));
  });
  const btn = (s = 'OMH') => screen.getByTestId(`ggw-run-btn-${s}`) as HTMLButtonElement;

  it('a tap → ONE POST to ${API}${ggwRunPath(sym)} (credentials include, no-store); the panel opens AT ONCE busy; the answer prints', async () => {
    render(<Harness />);
    fireEvent.click(btn());
    expect(pend).toHaveLength(1);
    expect(pend[0].url).toBe(`${API}${ggwRunPath('OMH')}`);
    expect(pend[0].init).toMatchObject({ method: 'POST', credentials: 'include', cache: 'no-store' });
    expect(T('ggw-run-busy')!.textContent).toBe(GGW_RUN.busy);
    expect((screen.getByTestId('ggw-run-close-OMH') as HTMLButtonElement).disabled).toBe(false);
    await act(async () => { pend[0].resolve(resp(200, clone(RAW))); });
    await flush();
    expect(T('ggw-run-busy')).toBeNull();
    expect(T('ggw-run-title')!.textContent).toBe('served title OMH');
    expect(btn().disabled).toBe(false);
  });
  it('NEGATIVE: busy → button disabled + aria-busy; two clicks in one tick → ONE POST', async () => {
    render(<Harness />);
    const b = btn();
    act(() => { b.click(); b.click(); });
    expect(pend).toHaveLength(1);
    expect(btn().disabled).toBe(true);
    expect(btn().getAttribute('aria-busy')).toBe('true');
  });
  it('NEGATIVE: ✕ while busy → the panel closes, the button is enabled, and the late answer prints NOTHING', async () => {
    render(<Harness />);
    fireEvent.click(btn());
    fireEvent.click(screen.getByTestId('ggw-run-close-OMH'));
    expect(T('ggw-run-OMH')).toBeNull();
    expect(btn().disabled).toBe(false);
    expect(btn().getAttribute('aria-expanded')).toBe('false');
    await act(async () => { pend[0].resolve(resp(200, clone(RAW))); });
    await flush();
    expect(T('ggw-run-OMH')).toBeNull();
    expect(document.body.textContent).not.toContain('served title OMH');
  });
  it('✕ while busy then ▶ again → a NEW POST; the OLD answer is dropped, the new one prints', async () => {
    render(<Harness />);
    fireEvent.click(btn());
    fireEvent.click(screen.getByTestId('ggw-run-close-OMH'));
    fireEvent.click(btn());
    expect(pend).toHaveLength(2);
    await act(async () => { pend[0].resolve(resp(200, { ...clone(RAW), title: 'served OLD title' })); });
    await flush();
    expect(T('ggw-run-busy')!.textContent).toBe(GGW_RUN.busy);
    expect(document.body.textContent).not.toContain('served OLD title');
    await act(async () => { pend[1].resolve(resp(200, clone(RAW))); });
    await flush();
    expect(T('ggw-run-title')!.textContent).toBe('served title OMH');
  });
  it('a second ▶ after an answer re-runs (a new POST)', async () => {
    render(<Harness />);
    fireEvent.click(btn());
    await act(async () => { pend[0].resolve(resp(200, clone(RAW))); });
    await flush();
    fireEvent.click(btn());
    expect(pend).toHaveLength(2);
    expect(T('ggw-run-busy')!.textContent).toBe(GGW_RUN.busy);
  });
  it('NEGATIVE: 404 → no panel, nothing printed, the button enabled', async () => {
    const { container } = render(<Harness />);
    fireEvent.click(btn());
    await act(async () => { pend[0].resolve(resp(404, { detail: 'served 404 detail' })); });
    await flush();
    expect(T('ggw-run-OMH')).toBeNull();
    expect(container.textContent).toBe('▶ Rules');
    expect(btn().disabled).toBe(false);
  });
  it('NEGATIVE: 500 with a served detail → that string; 500 without / a reject / junk JSON / junk body → GGW_RUN.failed', async () => {
    const cases: Array<[string, (p: Pending) => void, string]> = [
      ['500 detail', (p) => p.resolve(resp(500, { detail: 'served 500 detail' })), 'served 500 detail'],
      ['500 empty detail', (p) => p.resolve(resp(500, { detail: '  ' })), GGW_RUN.failed],
      ['500 no body', (p) => p.resolve(resp(500, null, true)), GGW_RUN.failed],
      ['reject', (p) => p.reject(new TypeError('network')), GGW_RUN.failed],
      ['junk JSON', (p) => p.resolve(resp(200, null, true)), GGW_RUN.failed],
      ['junk body', (p) => p.resolve(resp(200, { nope: 1 })), GGW_RUN.failed],
    ];
    for (const [name, answer, want] of cases) {
      pend = [];
      render(<Harness />);
      fireEvent.click(btn());
      await act(async () => { answer(pend[0]); });
      await flush();
      expect(T('ggw-run-text')?.textContent, name).toBe(want);
      expect(document.querySelector('section'), name).toBeNull();
      expect(btn().disabled, name).toBe(false);
      cleanup();
    }
  });
  it('per-symbol: two names run at once; ✕ on one never touches the other', async () => {
    render(<Harness syms={['OMH', 'AMD']} />);
    fireEvent.click(btn('OMH'));
    fireEvent.click(btn('AMD'));
    expect(pend.map((p) => p.url)).toEqual([`${API}${ggwRunPath('OMH')}`, `${API}${ggwRunPath('AMD')}`]);
    fireEvent.click(screen.getByTestId('ggw-run-close-OMH'));
    await act(async () => { pend[1].resolve(resp(200, { ...clone(RAW), symbol: 'AMD', title: 'served title AMD' })); });
    await flush();
    expect(T('ggw-run-OMH')).toBeNull();
    expect(within(screen.getByTestId('h-AMD')).getByTestId('ggw-run-title').textContent).toBe('served title AMD');
  });
  it('NEGATIVE: unmounted before the answer → no error, nothing set', async () => {
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { unmount } = render(<Harness />);
    fireEvent.click(btn());
    unmount();
    await act(async () => { pend[0].resolve(resp(200, clone(RAW))); });
    await flush();
    expect(err).not.toHaveBeenCalled();
  });
});

/* ── source + CSS guards ── */
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
/** Every quoted / template literal of the code (comments stripped). The served KEY `float_text` and the spec-named
 *  testid `ggw-run-float` are identifiers, not printed words. */
const literalsOf = (src: string): string[] => Array.from(noComments(src)
  .matchAll(/'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`/g))
  .map((m) => m[0].replace(/float_text|ggw-run-float/g, ''));
const RULE_WORDS = [/K3/, /volume dried/i, /tennis/i, /Squeeze/i, /A\+/, /forming/i, /partial/i, /float/i, /Yahoo/i, /Massive/i];
/** JSX text between tags (comments stripped) — never a typed word. */
const jsxTextOf = (src: string): string[] => Array.from(noComments(src).matchAll(/>([^<>{}\n]+)</g))
  .map((m) => m[1].trim()).filter((t) => t && !/[()?:&|=;,]/.test(t));

describe('GgwRunRules.tsx source guard', () => {
  it('NEGATIVE: no rule or state word in a literal or in JSX text; no isOwner, no @, no timer; never gajjala.css', () => {
    expect(runSrc.length).toBeGreaterThan(1000);
    const lits = literalsOf(runSrc);
    expect(lits.length).toBeGreaterThan(10);
    for (const l of lits) for (const w of RULE_WORDS) expect(l, `${w} in ${l}`).not.toMatch(w);
    expect(jsxTextOf(runSrc)).toEqual([]);
    const code = noComments(runSrc);
    expect(code).not.toMatch(/isOwner/);
    expect(code).not.toMatch(/@/);
    expect(code).not.toMatch(/setTimeout|setInterval/);
    expect(runSrc).not.toMatch(/styles\/gajjala\.css/);
    expect(runSrc).toContain("import '../styles/ggwRun.css';");
    expect(code.match(/method: 'POST'/g)).toHaveLength(1);
  });
});

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
/** The body of the FIRST rule whose selector list is exactly `sel` (anywhere, media blocks included). */
function rule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|[\\n{]\\s*)${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}
const zOf = (body: string | null) => Number(/z-index:\s*(\d+)/.exec(body ?? '')?.[1] ?? NaN);
const decl = (body: string | null, prop: string) => new RegExp(`(^|;|\\s)${prop}:\\s*([^;]+);`).exec(body ?? '')?.[2]?.trim() ?? null;

describe('ggwRun.css guards', () => {
  let css = '';
  let watchCss = '';
  let ggCss = '';
  beforeAll(async () => {
    css = await readSource('src/styles/ggwRun.css');
    watchCss = await readSource('src/styles/gajjalaWatch.css');
    ggCss = await readSource('src/styles/gajjala.css');
  });
  it('the panel: absolute in .ggw-charts--run, from the left, min-width 0, scrolls; every text child wraps', () => {
    expect(rule(css, '.ggw-charts--run')).toMatch(/position:\s*relative/);
    const p = rule(css, '.ggw-run');
    expect(p).toMatch(/position:\s*absolute/);
    expect(p).toMatch(/left:\s*0/);
    expect(p).toMatch(/min-width:\s*0/);
    expect(p).toMatch(/overflow-y:\s*auto/);
    expect(p).toMatch(/animation:\s*ggw-run-in/);
    expect(css).toMatch(/@keyframes ggw-run-in\s*\{\s*from\s*\{\s*transform:\s*translateX\(-100%\)/);
    const text = rule(css, '.ggw-run p, .ggw-run h4, .ggw-run b, .ggw-run span, .ggw-run li');
    expect(text).toMatch(/overflow-wrap:\s*anywhere/);
    expect(text).toMatch(/min-width:\s*0/);
    expect(text).toMatch(/white-space:\s*normal/);
  });
  it('≤ 640 px: full width; reduced motion: no animation on the panel or the busy button', () => {
    expect(css).toMatch(/@media \(max-width: 640px\)\s*\{\s*\.ggw-run\s*\{[^}]*width:\s*100%/);
    const rm = /@media \(prefers-reduced-motion: reduce\)\s*\{([\s\S]*?)\n\}/.exec(css)?.[1] ?? '';
    expect(rm).toMatch(/\.ggw-run\s*\{\s*animation:\s*none/);
    expect(rm).toMatch(/\.ggw-run-btn\[aria-busy="true"\]\s*\{\s*animation:\s*none/);
  });
  it('[C8b] NEGATIVE: the panel z-index is LOWER than the ⋯ drawer z-index of gajjalaWatch.css', () => {
    const zRun = zOf(rule(css, '.ggw-run'));
    const drawers = Array.from(watchCss.matchAll(/([^{}\n]*\.ggw-drawer)\s*\{([^}]*)\}/g))
      .map((m) => zOf(m[2])).filter((z) => Number.isFinite(z));
    expect(drawers.length).toBeGreaterThan(0);
    expect(Number.isFinite(zRun)).toBe(true);
    for (const z of drawers) expect(zRun).toBeLessThan(z);
  });
  it('[C8d] the head is sticky at top 0 with a solid background', () => {
    const h = rule(css, '.ggw-run-head');
    expect(h).toMatch(/position:\s*sticky/);
    expect(h).toMatch(/top:\s*0/);
    expect(decl(h, 'background')).toMatch(/^rgb\(13, 17, 23\)$/);
  });
  it('[C8a] the fitted pending host takes the room and scrolls (flex 1 1 0, min-height 0, overflow-y auto)', () => {
    const m = /@media \(min-width: 641px\)\s*\{\s*\.ggw-grid--fit \.ggw-run-host\s*\{([^}]*)\}/.exec(css);
    expect(m).not.toBeNull();
    expect(m![1]).toMatch(/flex:\s*1 1 0/);
    expect(m![1]).toMatch(/min-height:\s*0/);
    expect(m![1]).toMatch(/overflow-y:\s*auto/);
    expect(rule(css, '.ggw-run-host .ggw-run')).toMatch(/position:\s*static/);
  });
  it('the scoped .gg-ok / .gg-miss / .gg-unjudged colours equal gajjala.css; the state pills too', () => {
    for (const k of ['gg-ok', 'gg-miss', 'gg-unjudged']) {
      const want = decl(rule(ggCss, `.gg-criteria .${k}`), 'color');
      expect(want, k).not.toBeNull();
      expect(decl(rule(css, `.ggw-run .gg-criteria .${k}`), 'color'), k).toBe(want);
    }
    expect(rule(css, '.ggw-run .gg-state-stopped')).toBe(rule(ggCss, '.gg-state-stopped'));
    expect(rule(css, '.ggw-run .gg-state-partial')).toBe(rule(ggCss, '.gg-state-partial'));
    expect(rule(css, '.ggw-run .gg-state-aplus, .ggw-run .gg-state-triggered'))
      .toBe(rule(ggCss, '.gg-state-aplus, .gg-state-triggered'));
  });
  it('NEGATIVE: nothing unscoped — every .gg- selector of ggwRun.css sits under .ggw-run', () => {
    const sels = Array.from(css.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{/g)).map((m) => m[1].trim());
    for (const s of sels) for (const part of s.split(',')) {
      if (/\.gg-/.test(part)) expect(part.trim(), part).toMatch(/^\.ggw-run /);
    }
  });
});
