import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from '../lib/__fixtures__/longTerm.payload.json';
import ownerOnly from '../lib/__fixtures__/longTerm.owner_only.json';

/* 📅 Long Term board (2026-11-12, long-term spec §3.10 / §3.13, WP-FE). Ajay: "Save this entire list for me. In a New
 * tab - Long Term …" and "Yeah I wanna find out the ones that are actually great in fundamentals and growth and sales
 * and no debt but not growing in price action yet..". The board prints the served payload verbatim (a hand fixture in
 * the §3.10 shape; the real-payload fixture lands with the main session's probe). NEGATIVES throughout.
 *
 * [C8] The four house chips are vi.mock'ed to INERT markers: their own wording (🎯 READY and its served title) is
 * contract-mandated and outside this tab's word rule, so the banned-vocabulary scan reads only what THIS board renders. */

vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <i data-testid={`house-growth-${symbol}`} /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: ({ symbol }: any) => <i data-testid={`house-short-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <i data-testid="house-explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <i data-testid="house-enterable" /> }));
const roomCalls: string[][] = [];
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: (symbols: string[]) => {
    roomCalls.push([...symbols]);
    return { map: new Map(), payload: null, loading: false, error: null, pending: 0 };
  },
}));

import LongTermBoard from './LongTermBoard';
import { FETCH_FAILED, LT_PATH } from '../lib/longTerm';

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));
const SAVED = ['MANH', 'AMD', 'FIGS', 'ANET', 'NVDA', 'MPWR', 'XPEL', 'TSM'];
/** The ONE allowed sentence (backend words.NOT_A_SIGNAL); the seed's caveat carries it without the full stop. */
const NOT_A_SIGNAL = /None of these lists is a buy signal\.?/g;
const BANNED = /\b(buy|buying|bought|sell|selling|sold|entry|entries|exit|exits)\b/i;
const ATTRIBUTION = new RegExp(['g' + 'hee', 'jhun' + 'jhunwala', 'junjun' + 'wala', 'big ' + 'bull'].join('|'), 'i');

type Answer = { ok?: boolean; status?: number; body?: unknown; reject?: boolean };
function stub(answer: Answer) {
  const f = vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes(LT_PATH)) {
      if (answer.reject) throw new Error('network');
      return { ok: answer.ok ?? true, status: answer.status ?? 200, json: async () => clone(answer.body) };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  });
  vi.stubGlobal('fetch', f);
  return f;
}
async function mount(answer: Answer) {
  const f = stub(answer);
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=long_term']}><LongTermBoard /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.lt-board:not([data-state="loading"])')).not.toBeNull());
  return { ...r, f };
}
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const ltCalls = (f: ReturnType<typeof stub>) => f.mock.calls.filter((c) => String(c[0]).includes(LT_PATH));

afterEach(() => { vi.unstubAllGlobals(); roomCalls.length = 0; });

describe('📅 LongTermBoard — ready: the sections in the served order', () => {
  it('header → digest → 🧭 → 🌱 → ⚠️ → categories (seed order) → forward → history → rules', async () => {
    const { container } = await mount({ body: fixture });
    const order = [...container.querySelectorAll('[data-section]')].map((n) => n.getAttribute('data-section'));
    expect(order).toEqual(['header', 'digest', 'zones', 'started_moving', 'changed',
      'category', 'category', 'category', 'category', 'forward', 'history', 'rules']);
    const cats = [...container.querySelectorAll('[data-section="category"]')].map((n) => n.getAttribute('data-testid'));
    expect(cats).toEqual(fixture.categories.map((c) => `lt-cat-${c.key}`));
  });
  it('prints the served header verbatim: title, note, his words, next-run line, per-source as-of lines', async () => {
    await mount({ body: fixture });
    expect(screen.getByTestId('lt-title')).toHaveTextContent(fixture.title);
    expect(screen.getByTestId('lt-note')).toHaveTextContent(fixture.note);
    expect(screen.getByTestId('lt-his-words')).toHaveTextContent(fixture.his_words[0]);
    expect(screen.getByTestId('lt-next-run')).toHaveTextContent(fixture.as_of.next_run_text);
    for (const s of fixture.as_of.sources) expect(screen.getByTestId('lt-sources')).toHaveTextContent(s.as_of_text);
  });
  it('the digest: served title, lines and the push-off line', async () => {
    await mount({ body: fixture });
    const d = screen.getByTestId('lt-digest');
    expect(d).toHaveTextContent(fixture.digest.title);
    for (const l of fixture.digest.lines) expect(d).toHaveTextContent(l);
    expect(d).toHaveTextContent(fixture.digest.pushed_text);
  });
  it('🧭 at-zone strip from the served zones (title, each name + served text, note)', async () => {
    await mount({ body: fixture });
    const z = screen.getByTestId('lt-zones');
    expect(z).toHaveTextContent(fixture.zones.as_of_text);
    for (const hit of fixture.zones.at_zone) expect(screen.getByTestId(`lt-zone-${hit.symbol}`)).toHaveTextContent(hit.zone_text);
    expect(z).toHaveTextContent(fixture.zones.rows_note);
  });
  it('🌱 started moving lists the served name and text', async () => {
    await mount({ body: fixture });
    expect(screen.getByTestId('lt-started-NVDA')).toHaveTextContent(fixture.started_moving[0].text);
  });
});

describe('📅 LongTermBoard — saved rows', () => {
  it('a multi-chip row draws ONCE with every chip (NVDA 🌱 + 🧭, ANET 💎 📈 🧭); NEGATIVE: never twice', async () => {
    await mount({ body: fixture });
    expect(screen.getAllByTestId('lt-row-NVDA')).toHaveLength(1);
    expect(screen.getAllByTestId('lt-row-ANET')).toHaveLength(1);
    expect(screen.getByTestId('lt-chips-NVDA')).toHaveTextContent('🌱');
    expect(screen.getByTestId('lt-chips-NVDA')).toHaveTextContent('🧭');
    for (const g of ['💎', '📈', '🧭']) expect(screen.getByTestId('lt-chips-ANET')).toHaveTextContent(g);
  });
  it('NEGATIVE: a row the server put in ⚠️ changed is not drawn again under its category', async () => {
    const p = clone(fixture);
    await mount({ body: p });
    expect(screen.getAllByTestId('lt-row-MANH')).toHaveLength(1);
    expect(within(screen.getByTestId('lt-changed')).getByTestId('lt-row-MANH')).toBeTruthy();
    expect(within(screen.getByTestId('lt-cat-capital_quality')).queryByTestId('lt-row-MANH')).toBeNull();
  });
  it('stage, sales (quarter end + read date), status, fields, 🧭 block, events and caveat tag are the served texts', async () => {
    await mount({ body: fixture });
    const nvda = fixture.categories[2].rows[0];
    expect(screen.getByTestId('lt-stage-NVDA')).toHaveTextContent(nvda.stage.text);
    expect(screen.getByTestId('lt-sales-NVDA')).toHaveTextContent('quarter ended 2026-10-26');
    expect(screen.getByTestId('lt-status-NVDA')).toHaveTextContent(nvda.status.text);
    expect(screen.getByTestId('lt-pankaj-NVDA')).toHaveTextContent(nvda.pankaj!.zone_text);
    expect(screen.getByTestId('lt-field-MPWR-quiet_strong-liab_to_equity')).toHaveTextContent('Liabilities / equity: 0.21');
    expect(screen.getByTestId('lt-field-MPWR-quiet_strong-liab_to_equity').className).toMatch(/lt-v-pass/);
    expect(screen.getByTestId('lt-field-MPWR-quiet_strong-liab_to_equity').className).toMatch(/lt-k-fundamental/);
    expect(screen.getByTestId('lt-row-NVDA')).toHaveTextContent(nvda.caveat_tag);
  });
  it('a null field / name / sector / sales text prints "—"', async () => {
    await mount({ body: fixture });
    expect(screen.getByTestId('lt-field-AMD-s2_growth-c_strong_q_eps')).toHaveTextContent('Quarterly EPS: —');
    expect(screen.getByTestId('lt-sales-XPEL')).toHaveTextContent(/^—$/);
    expect(screen.getByTestId('lt-row-XPEL')).toHaveTextContent('—');
  });
  it('NEGATIVE: no "NaN", "Infinity", "undefined" or "null" anywhere on the page', async () => {
    const { container } = await mount({ body: fixture });
    expect(container.textContent).not.toMatch(/NaN|Infinity|undefined|\bnull\b/);
  });
});

describe('📅 LongTermBoard — ⚠️ only for changed; moved is neutral', () => {
  it('⚠️ changed renders when the served list is non-empty', async () => {
    await mount({ body: fixture });
    expect(screen.getByTestId('lt-changed')).toHaveTextContent('⚠️');
  });
  it('NEGATIVE: no changed rows → no ⚠️ section and the board itself types no ⚠️', async () => {
    const p = clone(fixture) as any;
    p.changed = [];
    p.digest = null;
    p.categories[1].rows = p.categories[1].rows.filter((r: any) => r.symbol !== 'MANH');
    const { container } = await mount({ body: p });
    expect(screen.queryByTestId('lt-changed')).toBeNull();
    expect(container.textContent).not.toContain('⚠️');
  });
  it('the served moved line renders on its category; NEGATIVE: no ⚠️ in that node', async () => {
    await mount({ body: fixture });
    const m = screen.getByTestId('lt-moved-quiet_strong');
    expect(m).toHaveTextContent(fixture.categories[2].moved_text!);
    expect(m.textContent).not.toContain('⚠️');
    expect(m.className).not.toMatch(/lt-changed/);
  });
  it('NEGATIVE: a category with no moved line renders no moved node', async () => {
    await mount({ body: fixture });
    expect(screen.queryByTestId('lt-moved-s2_growth')).toBeNull();
  });
});

describe('📅 LongTermBoard — the weekly top strip (unsaved)', () => {
  it('✨ only on a served `new`; NEGATIVE: none on an old strip name', async () => {
    await mount({ body: fixture });
    expect(screen.getByTestId('lt-new-RDDT')).toHaveTextContent('✨');
    expect(screen.queryByTestId('lt-new-HOOD')).toBeNull();
    expect(screen.getByTestId('lt-top-HOOD')).toHaveTextContent('RS rank 97');
    expect(screen.getByTestId('lt-strip-s2_growth')).toHaveTextContent(fixture.categories[0].top_text!);
  });
  it('NEGATIVE: strip rows carry no house chips and are not saved rows', async () => {
    await mount({ body: fixture });
    const strip = screen.getByTestId('lt-strip-s2_growth');
    expect(strip.querySelector('[data-testid^="house-"]')).toBeNull();
    expect(screen.queryByTestId('lt-row-RDDT')).toBeNull();
    expect(roomCalls.every((c) => !c.includes('RDDT') && !c.includes('HOOD'))).toBe(true);
  });
  it('NEGATIVE: 🧭 serves no strip (top [] and top_text null) → no strip node', async () => {
    await mount({ body: fixture });
    expect(screen.queryByTestId('lt-strip-pankaj')).toBeNull();
  });
});

describe('📅 LongTermBoard — house chips from ONE useBounceRoom', () => {
  it('every saved row mounts the four house chips; every room call asks for exactly the saved rows on screen', async () => {
    await mount({ body: fixture });
    for (const s of SAVED) {
      const h = screen.getByTestId(`lt-house-${s}`);
      expect(within(h).getByTestId(`house-growth-${s}`)).toBeTruthy();
      expect(within(h).getByTestId(`house-short-${s}`)).toBeTruthy();
      expect(within(h).getByTestId('house-explosive')).toBeTruthy();
      expect(within(h).getByTestId('house-enterable')).toBeTruthy();
    }
    const loaded = roomCalls.filter((c) => c.length);
    expect(loaded.length).toBeGreaterThan(0);
    for (const c of loaded) expect(c).toEqual(SAVED);
  });
  it('the board source calls useBounceRoom exactly once; NEGATIVE: no per-row hook call', async () => {
    const src = await readSource('src/components/LongTermBoard.tsx');
    expect(src.match(/useBounceRoom\(/g)).toHaveLength(1);
  });
});

describe('📅 LongTermBoard — the other states', () => {
  it('owner_only renders ONLY the served reason; NEGATIVE: no rows, no header, the room asked for nothing', async () => {
    const { container, f } = await mount({ body: ownerOnly });
    expect(container.querySelector('.lt-board')!.getAttribute('data-state')).toBe('owner_only');
    expect(screen.getByTestId('lt-reason')).toHaveTextContent(ownerOnly.reason);
    expect(container.textContent).toBe(ownerOnly.reason);
    expect(container.querySelector('[data-testid^="lt-row-"]')).toBeNull();
    expect(screen.queryByTestId('lt-header')).toBeNull();
    expect(roomCalls.length).toBeGreaterThan(0);
    for (const c of roomCalls) expect(c).toEqual([]);
    expect(f.mock.calls.filter((c) => String(c[0]).includes('bounce-room'))).toHaveLength(0);
  });
  it('error renders the served reason only', async () => {
    const { container } = await mount({ body: { state: 'error', reason: 'The saved list could not be read on the server.', title: '📅 Long Term' } });
    expect(container.textContent).toBe('The saved list could not be read on the server.');
    for (const c of roomCalls) expect(c).toEqual([]);
  });
  it('seed_only renders every saved row and the next-run text; NEGATIVE: no digest', async () => {
    const p = clone(fixture) as any;
    p.state = 'seed_only';
    p.digest = null;
    p.history = [];
    await mount({ body: p });
    for (const s of SAVED) expect(screen.getAllByTestId(`lt-row-${s}`)).toHaveLength(1);
    expect(screen.getByTestId('lt-next-run')).toHaveTextContent(fixture.as_of.next_run_text);
    expect(screen.queryByTestId('lt-digest')).toBeNull();
    expect(screen.queryByTestId('lt-history')).toBeNull();
  });
  it('a rejected fetch prints FETCH_FAILED', async () => {
    await mount({ reject: true });
    expect(screen.getByTestId('lt-reason')).toHaveTextContent(FETCH_FAILED);
  });
  it('NEGATIVE: an HTTP error or a body with no known state also prints FETCH_FAILED (never a blank board)', async () => {
    await mount({ ok: false, status: 500, body: {} });
    expect(screen.getByTestId('lt-reason')).toHaveTextContent(FETCH_FAILED);
    vi.unstubAllGlobals();
    document.body.innerHTML = '';
    await mount({ body: { rows: [] } });
    expect(screen.getByTestId('lt-reason')).toHaveTextContent(FETCH_FAILED);
  });
  it('ONE fetch of the board on mount; NEGATIVE: no polling timer in the source', async () => {
    const { f } = await mount({ body: fixture });
    await new Promise((r) => setTimeout(r, 30));
    expect(ltCalls(f)).toHaveLength(1);
    const src = await readSource('src/components/LongTermBoard.tsx');
    expect(src).not.toMatch(/setInterval|setTimeout/);
  });
});

describe('📅 LongTermBoard — forward record', () => {
  it('too_early → the served line and counts line; NEGATIVE: no chart', async () => {
    await mount({ body: fixture });
    expect(screen.getByTestId('lt-forward-line')).toHaveTextContent(fixture.forward.line);
    expect(screen.getByTestId('lt-forward')).toHaveTextContent(fixture.forward.counts_line);
    expect(screen.queryByTestId('lt-chart')).toBeNull();
  });
  it('past too_early → one polyline per served series (three), labelled from the payload', async () => {
    const p = clone(fixture) as any;
    p.forward.too_early = false;
    p.forward.line = 'Since the 2026-11-13 open (22 sessions): served line.';
    p.forward.points = [
      { date: '2026-11-13', list_pct: 0.4, rsp_pct: 0.2, spy_pct: 0.3 },
      { date: '2026-11-20', list_pct: 1.2, rsp_pct: 0.5, spy_pct: 0.9 },
      { date: '2026-11-27', list_pct: -0.6, rsp_pct: 0.1, spy_pct: 0.4 },
    ];
    await mount({ body: p });
    const svg = screen.getByTestId('lt-chart');
    expect(svg.querySelectorAll('polyline')).toHaveLength(3);
    expect([...svg.querySelectorAll('polyline')].map((n) => n.getAttribute('data-series'))).toEqual(['list_pct', 'rsp_pct', 'spy_pct']);
    for (const s of p.forward.series) expect(screen.getByTestId('lt-forward')).toHaveTextContent(s.label);
  });
});

describe('📅 LongTermBoard — words (spec SERVED-WORD RULE, C8)', () => {
  it('NEGATIVE: rendered text (house chips mocked) has no buy/sell vocabulary after the one allowed sentence, and no b-word', async () => {
    const { container } = await mount({ body: fixture });
    const text = (container.textContent || '').replace(NOT_A_SIGNAL, '');
    expect(text).not.toMatch(BANNED);
    expect(text).not.toMatch(/bounce/i);
    expect(text).not.toMatch(ATTRIBUTION);
  });
  it('NEGATIVE: the matcher is live — a served "buy" word would be caught', () => {
    expect('Buy CL1'.replace(NOT_A_SIGNAL, '')).toMatch(BANNED);
    expect('None of these lists is a buy signal.'.replace(NOT_A_SIGNAL, '')).not.toMatch(BANNED);
  });
  it('NEGATIVE: the board / helper / stylesheet / fixture sources carry no banned word, no b-word, no attribution', async () => {
    for (const rel of ['src/components/LongTermBoard.tsx', 'src/lib/longTerm.ts', 'src/styles/longTerm.css',
      'src/lib/__fixtures__/longTerm.payload.json', 'src/lib/__fixtures__/longTerm.owner_only.json']) {
      const src = (await readSource(rel)).replace(NOT_A_SIGNAL, '');
      expect(src, rel).not.toMatch(BANNED);
      expect(src, rel).not.toMatch(/\bbounce\b/i);
      expect(src, rel).not.toMatch(ATTRIBUTION);
    }
  });
  it('NEGATIVE: no digit in a JSX text literal of the board (every number is served)', async () => {
    const src = (await readSource('src/components/LongTermBoard.tsx'))
      .replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
    /* JSX text sits between `>` or `}` and `<` or `{` (e.g. `> · {`, `}: {`); strict — TS code between braces counts too. */
    const literals = [...src.matchAll(/>([^<>{}]*)[<{]/g), ...src.matchAll(/\}([^<>{}]*)[<{]/g)].map((m) => m[1]).filter((t) => t.trim());
    expect(literals.length).toBeGreaterThan(0);
    for (const t of literals) expect(t, t).not.toMatch(/\d/);
  });
  it('the NO_TOGGLE phrase is in the source; NEGATIVE: no ExplosiveFirstToggle, no 🎯 filter', async () => {
    const src = await readSource('src/components/LongTermBoard.tsx');
    expect(src).toContain('his saved list keeps its saved order');
    expect(src).not.toMatch(/<ExplosiveFirstToggle/);
    expect(src).not.toMatch(/EnterableFilter|enterableFilter/);
  });
  it('owner_only is handled in the board source', async () => {
    const src = await readSource('src/components/LongTermBoard.tsx');
    expect(src).toContain("state === 'owner_only'");
  });
});
