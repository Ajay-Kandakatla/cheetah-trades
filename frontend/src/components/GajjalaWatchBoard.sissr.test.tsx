/* ⛔🩳🔒 👀 Watch — the tagged-potentials section, the board (2026-11-25, spec sissr §3.7 / §4 WP fe-watch).
 * Ajay 2026-11-24 ~23:20 ET (verbatim in spec sissr §0): the 🩳 / ⛔ / 🔒 tagged names that become 🧠 potentials go on the
 * Watch "and give them a time stamp of the day". The real board, fetch stubbed, on the BE golden (be-watch writes
 * ggwSiSsr.golden.json): the ⛔🩳🔒 section is served AFTER ✅ with `folded_default: true`. Phone: ONE folded header line
 * under ✅ until he taps it; desktop: no headers. The row prints its SERVED time chip (text + hover) and its served auto
 * chip; × → DELETE with the served remove_title. The live interest posts ⛔🩳🔒 after ✅ (verifier HIGH) and none while
 * folded on the phone. The board is unchanged — it is generic over served section keys. NEGATIVES: a ⛔🩳🔒 row never
 * joins his pick (an `aplus` block served too); an empty section draws no header; a head with missing / junk counts draws
 * nothing; the section hint lives only in ℹ️ (and the header's hover); a junk `why` → an ordinary 🤖 row; 430 px wraps. */
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import gold from '../lib/__fixtures__/ggwSiSsr.golden.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GGW_COLLAPSED_KEY, GGW_LIVE_PATH, GGW_OPENED_KEY, GGW_PATH, GGW_PICK_KEY } from '../lib/gajjalaWatch';

/* the live bus is not under test here — a no-op subscription (the GajjalaWatchBoard.live pattern) */
vi.mock('../lib/eventBus', () => ({ subscribe: () => () => {} }));

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const G = (): any => {
  const b = clone(gold as any);
  b.refresh_sec = 0;
  b.next_window_sec = null;
  delete b.pending_poll_sec;
  delete b.pending_wait_max_sec;
  return b;
};
const GL = (): any => ({ ...G(), refresh_sec: 60 });
const SISSR = ['AKAN', 'GMEX'];
const servedRow = (sym: string): any => (gold as any).rows.find((r: any) => r.symbol === sym);
const servedSec = (key: string): any => (gold as any).sections.find((s: any) => s.key === key);

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
const res = (body: unknown) => ({ ok: true, json: async () => body }) as unknown as Response;

type Call = { url: string; method: string; body?: string };
let serve: () => any = G;
let calls: Call[] = [];
let phoneNow = true;
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });

async function mount(search = '') {
  vi.stubGlobal('matchMedia', (qq: string) => ({ matches: phoneNow, media: qq, addEventListener: () => {}, removeEventListener: () => {} }));
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method || 'GET').toUpperCase();
    calls.push({ url, method, body: init?.body as string | undefined });
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) return res({ state: 'ok', stream: { on: true, state: 'live' }, symbols: [] });
    if (method === 'DELETE') return res({ state: 'dismissed', symbols: ['OMH', 'NVDA'], symbol: null, text: 'served-dismissed' });
    if (url.includes(GGW_PATH)) return res(serve());
    return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
  }));
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?tab=gajjala_watch${search}`]}><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 5; i += 1) await flush();
  return r.container;
}
const q = (c: HTMLElement, id: string) => c.querySelector(`[data-testid="${id}"]`) as HTMLElement | null;
const tile = (c: HTMLElement, s: string) => q(c, `ggw-tile-${s}`);
const isShown = (c: HTMLElement, s: string) => !!tile(c, s) && !tile(c, s)!.hidden;
const store = () => window.localStorage;
const gridKids = (c: HTMLElement) => Array.from(c.querySelector('.ggw-grid')!.children).map((e) => e.getAttribute('data-testid'));
const posts = () => calls.filter((x) => x.method === 'POST' && x.url.endsWith(GGW_LIVE_PATH));
const lastPosted = (): string[] => JSON.parse(posts()[posts().length - 1].body as string).symbols;

const origScroll = (Element.prototype as any).scrollIntoView;
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(Date.parse('2026-11-13T19:40:00.000Z'));
  vi.stubGlobal('localStorage', memStorage());
  vi.stubGlobal('EventSource', function EventSource() {} as unknown as typeof EventSource);
  serve = G;
  phoneNow = true;
  (Element.prototype as any).scrollIntoView = function () {};
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  (Element.prototype as any).scrollIntoView = origScroll;
});

describe('📱 phone: ⛔🩳🔒 is one folded header line under ✅', { timeout: 20000 }, () => {
  it('the ⛔🩳🔒 header comes right after ✅, folded ("▸" + the served words); its tiles hidden; the others open', async () => {
    const c = await mount();
    const kids = gridKids(c);
    expect(kids.slice(kids.indexOf('ggw-section-rules'))).toEqual([
      'ggw-section-rules', 'ggw-tile-RON', 'ggw-section-sissr', 'ggw-tile-AKAN', 'ggw-tile-GMEX',
    ]);
    const btn = q(c, 'ggw-section-btn-sissr')!;
    expect(btn.textContent).toBe(`▸ ${servedSec('sissr').text}`);
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    expect(q(c, 'ggw-section-sissr')!.classList.contains('ggw-section--folded')).toBe(true);
    for (const s of SISSR) expect(isShown(c, s)).toBe(false);
    for (const s of ['OMH', 'NVDA', 'AAA', 'MMM', 'ZZT']) expect(isShown(c, s)).toBe(true);
    /* ✅ and ⛔🩳🔒 folded = two header lines and no tile under them */
    expect(isShown(c, 'RON')).toBe(false);
  });
  it('a tap opens ⛔🩳🔒 (ggw.opened, ggw.collapsed untouched); ✅ stays folded; a 2nd tap folds it', async () => {
    const c = await mount();
    fireEvent.click(q(c, 'ggw-section-btn-sissr')!);
    await flush();
    expect(q(c, 'ggw-section-btn-sissr')!.textContent).toBe(`▾ ${servedSec('sissr').text}`);
    for (const s of SISSR) expect(isShown(c, s)).toBe(true);
    expect(isShown(c, 'RON')).toBe(false);
    expect(JSON.parse(store().getItem(GGW_OPENED_KEY)!)).toEqual(['sissr']);
    expect(store().getItem(GGW_COLLAPSED_KEY)).toBeNull();
    fireEvent.click(q(c, 'ggw-section-btn-sissr')!);
    await flush();
    for (const s of SISSR) expect(isShown(c, s)).toBe(false);
  });
  it('?focus= (a push link) on a ⛔🩳🔒 name opens its section', async () => {
    const c = await mount('&focus=GMEX');
    for (let i = 0; i < 3; i += 1) await flush();
    expect(isShown(c, 'GMEX')).toBe(true);
    expect(q(c, 'ggw-section-btn-sissr')!.getAttribute('aria-expanded')).toBe('true');
    expect(q(c, 'ggw-section-btn-rules')!.getAttribute('aria-expanded')).toBe('false');
  });
});

describe('⛔🩳🔒 the row prints served words only', { timeout: 20000 }, () => {
  it('the time chip = the served when text and hover, verbatim; the auto chip = the served text', async () => {
    phoneNow = false;
    const c = await mount('&per=9');
    for (const s of SISSR) {
      const r = servedRow(s);
      const when = q(c, `ggw-when-${s}`)!;
      expect(when.textContent).toBe(r.org.when.text);
      expect(when.getAttribute('title')).toBe(r.org.when.title);
      const auto = tile(c, s)!.querySelector('[data-testid="ggw-auto"]')!;
      expect(auto.textContent).toBe(r.auto.text);
    }
    /* the golden's own words: the stamp of the day + the setup; the 🧠-since clause only where the times differ */
    expect(q(c, 'ggw-when-AKAN')!.textContent).toBe('⛔ 11-13 14:31 ET · ➖ Horizontal Fade');
    expect(q(c, 'ggw-when-AKAN')!.getAttribute('title')).not.toContain('🧠 since');
    expect(q(c, 'ggw-when-GMEX')!.getAttribute('title')).toContain('🧠 since 09:30 ET');
  });
  it('NEGATIVE: the FE composes nothing — a changed served text / title shows the changed words, digits included', async () => {
    phoneNow = false;
    serve = () => {
      const b = G();
      const r = b.rows.find((x: any) => x.symbol === 'AKAN');
      r.org.when.text = 'served-when-text-zz';
      r.org.when.title = 'served-when-title-zz';
      r.auto.text = 'served-auto-text-zz';
      return b;
    };
    const c = await mount('&per=9');
    expect(q(c, 'ggw-when-AKAN')!.textContent).toBe('served-when-text-zz');
    expect(q(c, 'ggw-when-AKAN')!.getAttribute('title')).toBe('served-when-title-zz');
    expect(tile(c, 'AKAN')!.querySelector('[data-testid="ggw-auto"]')!.textContent).toBe('served-auto-text-zz');
    expect(tile(c, 'AKAN')!.textContent).not.toContain('14:31');
  });
  it('× on a ⛔🩳🔒 row → ONE DELETE of that name; the button title is the served remove_title', async () => {
    phoneNow = false;
    const c = await mount('&per=9');
    const rm = tile(c, 'AKAN')!.querySelector('.ggw-remove') as HTMLButtonElement;
    expect(rm.getAttribute('title')).toBe(servedRow('AKAN').auto.remove_title);
    fireEvent.click(rm);
    for (let i = 0; i < 3; i += 1) await flush();
    const del = calls.filter((x) => x.method === 'DELETE');
    expect(del).toHaveLength(1);
    expect(decodeURIComponent(del[0].url.split('/').pop() as string)).toBe('AKAN');
  });
});

describe('⛔🩳🔒 the live interest (verifier HIGH)', { timeout: 20000 }, () => {
  it('desktop: every row posted — 👤 / 🎯 / 🤖 → ✅ → ⛔🩳🔒, even when the server serves ⛔🩳🔒 first', async () => {
    phoneNow = false;
    serve = () => {
      const b = GL();
      const s = b.rows.filter((r: any) => r.auto?.why === 'sissr');
      b.rows = [...s.reverse(), ...b.rows.filter((r: any) => r.auto?.why !== 'sissr')];
      return b;
    };
    await mount('&per=9');
    expect(lastPosted()).toEqual(['OMH', 'NVDA', 'AAA', 'MMM', 'ZZT', 'RON', 'GMEX', 'AKAN']);
  });
  it('phone: both folded → neither posts; ⛔🩳🔒 opened → posted last; ✅ opened too → ✅ before ⛔🩳🔒', async () => {
    serve = GL;
    const c = await mount();
    expect(lastPosted()).toEqual(['OMH', 'NVDA', 'AAA', 'MMM', 'ZZT']);
    fireEvent.click(q(c, 'ggw-section-btn-sissr')!);
    for (let i = 0; i < 3; i += 1) await flush();
    expect(lastPosted()).toEqual(['OMH', 'NVDA', 'AAA', 'MMM', 'ZZT', 'AKAN', 'GMEX']);
    fireEvent.click(q(c, 'ggw-section-btn-rules')!);
    for (let i = 0; i < 3; i += 1) await flush();
    expect(lastPosted()).toEqual(['OMH', 'NVDA', 'AAA', 'MMM', 'ZZT', 'RON', 'AKAN', 'GMEX']);
  });
  it('NEGATIVE: a junk why on a ⛔🩳🔒-grouped row → treated as 🤖 (posted with the rest, before ✅)', async () => {
    phoneNow = false;
    serve = () => {
      const b = GL();
      b.rows.find((r: any) => r.symbol === 'GMEX').auto.why = 'SISSR';
      return b;
    };
    await mount('&per=9');
    expect(lastPosted()).toEqual(['OMH', 'NVDA', 'AAA', 'MMM', 'ZZT', 'GMEX', 'RON', 'AKAN']);
  });
});

describe('⛔🩳🔒 NEGATIVES', { timeout: 20000 }, () => {
  it('a ⛔🩳🔒 row never joins his pick — just added, unseen, an aplus block served: a pick of OMH stays OMH', async () => {
    phoneNow = false;
    serve = () => {
      const b = G();
      for (const r of b.rows) r.added_at = '2026-11-13T19:39:00Z';
      for (const r of b.rows) if (r.auto?.why === 'sissr') r.aplus = { tag: '🎯', text: 'served-aplus', title: null, items: [] };
      return b;
    };
    store().setItem(GGW_PICK_KEY, 'OMH');
    const c = await mount();
    expect(isShown(c, 'OMH')).toBe(true);
    for (const s of SISSR) expect(isShown(c, s)).toBe(false);
    const pick = store().getItem(GGW_PICK_KEY)!.split(',');
    for (const s of SISSR) expect(pick).not.toContain(s);
  });
  it('an empty ⛔🩳🔒 section (served n 0, no rows) draws no header; the board is otherwise the same', async () => {
    serve = () => {
      const b = G();
      b.rows = b.rows.filter((r: any) => r.auto?.why !== 'sissr');
      const s = b.sections.find((x: any) => x.key === 'sissr');
      s.n = 0; s.symbols = []; s.text = 'served-head-sissr · 0';
      return b;
    };
    const c = await mount();
    expect(q(c, 'ggw-section-sissr')).toBeNull();
    expect(q(c, 'ggw-section-btn-sissr')).toBeNull();
    expect(c.querySelector('.ggw-grid')!.textContent).not.toContain('served-head-sissr');
    expect(gridKids(c).slice(-2)).toEqual(['ggw-section-rules', 'ggw-tile-RON']);
  });
  it('a head with missing / junk / served ⛔🩳🔒 counts draws nothing — the head is byte-equal', async () => {
    const heads = [
      { state: 'ok', n: 1, keep_sessions: 5, text: null, not_seated_n: 1 },
      { state: 'ok', n: 1, keep_sessions: 5, text: null, not_seated_n: 1, sissr_n: 'x', sissr_not_eligible_n: -3 },
      { state: 'ok', n: 1, keep_sessions: 5, text: null, not_seated_n: 1, sissr_n: 4417, sissr_not_eligible_n: 4419 },
    ];
    serve = () => ({ ...G(), rules: heads[0] });
    const base = (await mount()).querySelector('.ggw-head')!.innerHTML;
    cleanup();
    for (const rules of heads.slice(1)) {
      serve = () => ({ ...G(), rules });
      const c = await mount();
      expect(c.querySelector('.ggw-head')!.innerHTML).toBe(base);
      expect(c.querySelector('.ggw-head')!.textContent).not.toMatch(/4417|4419/);
      cleanup();
    }
  });
  it('the section hint lives ONLY in ℹ️ (and the header hover) — no explanation line outside it', async () => {
    const hint = servedSec('sissr').hint as string;
    const c = await mount();
    const inInfo = q(c, 'ggw-info-section-sissr')!;
    expect(inInfo.textContent).toBe(hint);
    expect(inInfo.closest('details.ggw-info')).not.toBeNull();
    const withHint = Array.from(c.querySelectorAll('*')).filter((e) => e.children.length === 0 && (e.textContent ?? '').includes(hint));
    expect(withHint).toHaveLength(1);
    expect(withHint[0]).toBe(inInfo);
    expect(q(c, 'ggw-section-btn-sissr')!.getAttribute('title')).toBe(hint);
  });
  it('no b-word and no admin email in anything the ⛔🩳🔒 rows render', async () => {
    phoneNow = false;
    const c = await mount('&per=9');
    for (const s of SISSR) {
      const t = tile(c, s)!;
      const words = [t.textContent ?? '', ...Array.from(t.querySelectorAll('[title]')).map((e) => e.getAttribute('title') ?? '')].join(' ');
      expect(words).not.toMatch(/[Bb]ounce/);
      expect(words).not.toContain('@gmail');
    }
  });
});

describe('📱 430 px (jsdom has no layout — source guards on the stylesheet the board imports)', () => {
  async function css(): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    return fs.readFileSync(`${root}/src/styles/gajjalaWatch.css`, 'utf8');
  }
  const rule = (src: string, sel: string): string | null => {
    const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
    return m ? m[2] : null;
  };
  it('the time chip and the auto chip wrap (.ggw-chip / .ggw-prov > .ggw-chip); the header wraps', async () => {
    const src = await css();
    for (const sel of ['.ggw-chip', '.ggw-prov > .ggw-chip']) {
      const r = rule(src, sel)!;
      for (const re of [/white-space:\s*normal/, /overflow-wrap:\s*anywhere/, /min-width:\s*0/, /max-width:\s*100%/]) expect(r).toMatch(re);
    }
    expect(rule(src, '.ggw-prov')).toMatch(/flex-wrap:\s*wrap/);
    expect(rule(src, '.ggw-section-btn')).toMatch(/white-space:\s*normal/);
    /* NEGATIVE: a nowrap chip would fail */
    expect(rule('.ggw-chip { white-space: nowrap; }', '.ggw-chip')).not.toMatch(/white-space:\s*normal/);
  });
  it('on the phone the ⛔🩳🔒 chips are .ggw-chip inside .ggw-prov; the tile carries no inline width', async () => {
    const c = await mount();
    fireEvent.click(q(c, 'ggw-section-btn-sissr')!);
    await flush();
    const when = q(c, 'ggw-when-AKAN')!;
    expect(when.classList.contains('ggw-chip')).toBe(true);
    expect(when.parentElement!.classList.contains('ggw-prov')).toBe(true);
    expect(tile(c, 'AKAN')!.getAttribute('style') ?? '').not.toMatch(/width/);
  });
});
