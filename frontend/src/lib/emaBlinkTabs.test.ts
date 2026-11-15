/* 🔀 The tab-button dot feed (2026-11-15, ema-blink spec §3.9 / §4 WP-F (a), (d), (e)). Ajay: "Or atleast closing in
 * on other tabs for me." ONE setTimeout chain at the SERVED refresh_sec; refresh_sec 0 → one GET; hidden / failed →
 * no chain (never a tight loop). CSS guards read the two style files; no email in any new file. NEGATIVES throughout. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import {
  EMA_BLINK_TABS_PATH, emaBlinkTabDot, parseEmaBlinkTabs, useEmaBlinkTabs,
} from './emaBlinkTabs';
import { EMA_BLINK_TIERS } from './emaBlink';

const FEED = (refresh_sec: number, extra: Record<string, unknown> = {}) => ({
  as_of: '2026-11-16T14:40:00Z', session: '2026-11-16', in_window: refresh_sec > 0, refresh_sec,
  info: 'served info', n_means: 'served n_means',
  tabs: {
    gajjala: { n: 3, crossed_up: 1, closing_in: 2, tier: 'fresh', frame: '5m',
               top: { symbol: 'ABCD', tier: 'fresh', closeness: 0 }, text: '3 cards served words' },
    gajjala_1m: { n: 0, crossed_up: 0, closing_in: 0, tier: null, frame: '1m', top: null, text: null },
    gajjala_watch: null,
    ...extra,
  },
});

let vis: DocumentVisibilityState = 'visible';
let calls: string[] = [];
let answer: () => Promise<unknown> = async () => FEED(60);

beforeEach(() => {
  vi.useFakeTimers();
  vis = 'visible';
  calls = [];
  answer = async () => FEED(60);
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => vis });
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL) => {
    calls.push(String(u));
    const body = await answer();
    return { ok: true, status: 200, json: async () => body } as unknown as Response;
  }));
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

const flush = async () => { await act(async () => { await vi.advanceTimersByTimeAsync(0); }); };
const advance = async (ms: number) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); };
const setVis = async (v: DocumentVisibilityState) => {
  vis = v;
  await act(async () => { document.dispatchEvent(new Event('visibilitychange')); await vi.advanceTimersByTimeAsync(0); });
};

describe('(a) the chain — one GET on mount, re-GET at the SERVED refresh_sec', () => {
  it('GETs the route once on mount and re-GETs after refresh_sec, not before', async () => {
    const { result } = renderHook(() => useEmaBlinkTabs(true));
    await flush();
    expect(calls).toHaveLength(1);
    expect(calls[0].endsWith(EMA_BLINK_TABS_PATH)).toBe(true);
    expect(EMA_BLINK_TABS_PATH).toBe('/chart-maps/ema-blink');
    expect(result.current?.refresh_sec).toBe(60);
    await advance(59_000);
    expect(calls).toHaveLength(1);
    await advance(1_000);
    expect(calls).toHaveLength(2);
    await advance(60_000);
    expect(calls).toHaveLength(3);
  });

  it('follows a CHANGED served refresh_sec (the server owns the cadence)', async () => {
    answer = async () => FEED(30);
    renderHook(() => useEmaBlinkTabs(true));
    await flush();
    await advance(30_000);
    expect(calls).toHaveLength(2);
  });

  it('NEGATIVE: refresh_sec 0 → that one GET, no chain', async () => {
    answer = async () => FEED(0);
    const { result } = renderHook(() => useEmaBlinkTabs(true));
    await flush();
    expect(result.current?.tabs.gajjala?.n).toBe(3);   // the single read still feeds the dots
    await advance(10 * 60_000);
    expect(calls).toHaveLength(1);
  });

  it('NEGATIVE: refresh_sec 0 → re-GET only on the next visibility change back to the page', async () => {
    answer = async () => FEED(0);
    renderHook(() => useEmaBlinkTabs(true));
    await flush();
    await setVis('hidden');
    expect(calls).toHaveLength(1);
    await setVis('visible');
    expect(calls).toHaveLength(2);
    await advance(10 * 60_000);
    expect(calls).toHaveLength(2);
  });

  it('NEGATIVE: never GETs while hidden — the chain rests and resumes on visible', async () => {
    renderHook(() => useEmaBlinkTabs(true));
    await flush();
    await setVis('hidden');
    await advance(5 * 60_000);
    expect(calls).toHaveLength(1);
    await setVis('visible');
    expect(calls).toHaveLength(2);
    await advance(60_000);
    expect(calls).toHaveLength(3);
  });

  it('NEGATIVE: a visibility change while the chain is armed does not add a GET', async () => {
    renderHook(() => useEmaBlinkTabs(true));
    await flush();
    await setVis('hidden');
    await setVis('visible');
    expect(calls).toHaveLength(1);
    await advance(60_000);
    expect(calls).toHaveLength(2);
  });

  it('NEGATIVE: a failed GET stops the chain — no tight loop, at most one request per refresh_sec', async () => {
    const { result } = renderHook(() => useEmaBlinkTabs(true));
    await flush();
    expect(result.current?.tabs.gajjala?.tier).toBe('fresh');
    answer = async () => { throw new Error('502'); };
    await advance(60_000);
    expect(calls).toHaveLength(2);
    await advance(30 * 60_000);
    expect(calls).toHaveLength(2);
    expect(result.current?.tabs.gajjala?.tier).toBe('fresh');   // the last good feed stays
    answer = async () => FEED(60);
    await setVis('hidden');
    await setVis('visible');
    expect(calls).toHaveLength(3);
    await advance(60_000);
    expect(calls).toHaveLength(4);
  });

  it('NEGATIVE: an HTTP error (ok:false) is a failed GET — no chain', async () => {
    vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL) => {
      calls.push(String(u));
      return { ok: false, status: 500, json: async () => ({}) } as unknown as Response;
    }));
    const { result } = renderHook(() => useEmaBlinkTabs(true));
    await flush();
    await advance(30 * 60_000);
    expect(calls).toHaveLength(1);
    expect(result.current).toBeNull();
  });

  it('NEGATIVE: a junk body is no feed and no chain', async () => {
    answer = async () => 'junk';
    const { result } = renderHook(() => useEmaBlinkTabs(true));
    await flush();
    await advance(30 * 60_000);
    expect(calls).toHaveLength(1);
    expect(result.current).toBeNull();
  });

  it('NEGATIVE: disabled → no GET at all', async () => {
    const { result } = renderHook(() => useEmaBlinkTabs(false));
    await flush();
    await advance(5 * 60_000);
    expect(calls).toHaveLength(0);
    expect(result.current).toBeNull();
  });

  it('NEGATIVE: unmount clears the chain', async () => {
    const { unmount } = renderHook(() => useEmaBlinkTabs(true));
    await flush();
    unmount();
    await advance(5 * 60_000);
    vis = 'visible';
    document.dispatchEvent(new Event('visibilitychange'));
    expect(calls).toHaveLength(1);
  });
});

describe('the parse + the per-tab dot pick', () => {
  it('a dot only for a served tab with n > 0 and a known tier; the words are served', () => {
    const f = parseEmaBlinkTabs(FEED(60, {
      luk: { n: 2, tier: 'closing', text: 'luk words' },
      gajjala_audited: { n: 4, tier: 'warp', text: 'x' },
      gajjala_neg: { n: -1, tier: 'fresh', text: 'x' },
      gajjala_str: { n: '3', tier: 'fresh', text: 'x' },
      gajjala_tierless: { n: 5, tier: null, text: 'x' },
    }))!;
    expect(emaBlinkTabDot(f, 'gajjala')).toEqual({ tier: 'fresh', text: '3 cards served words', n: 3 });
    expect(emaBlinkTabDot(f, 'luk')).toEqual({ tier: 'closing', text: 'luk words', n: 2 });
    expect(emaBlinkTabDot(f, 'gajjala_1m')).toBeNull();        // n: 0
    expect(emaBlinkTabDot(f, 'gajjala_watch')).toBeNull();     // null (not the owner)
    expect(emaBlinkTabDot(f, 'gajjala_audited')).toBeNull();   // an unknown tier
    expect(emaBlinkTabDot(f, 'gajjala_neg')).toBeNull();
    expect(emaBlinkTabDot(f, 'gajjala_str')).toBeNull();
    expect(emaBlinkTabDot(f, 'gajjala_tierless')).toBeNull();
    expect(emaBlinkTabDot(f, 'zones')).toBeNull();             // a tab the server did not name
    expect(emaBlinkTabDot(null, 'gajjala')).toBeNull();
  });
  it('NEGATIVE: junk payloads parse to null or to no tabs', () => {
    for (const j of [null, undefined, 3, 'x', []]) expect(parseEmaBlinkTabs(j)).toBeNull();
    const f = parseEmaBlinkTabs({ tabs: 'nope', refresh_sec: -5 })!;
    expect(f.tabs).toEqual({});
    expect(f.refresh_sec).toBe(0);
    expect(parseEmaBlinkTabs({ refresh_sec: Number.NaN })!.refresh_sec).toBe(0);
    expect(parseEmaBlinkTabs({ refresh_sec: '60' })!.refresh_sec).toBe(0);
  });
});

/* ---- (d) CSS source guards — read both files ---- */
async function readSrc(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  return fs.readFileSync(`${(globalThis as any).process.cwd()}/${rel}`, 'utf8');
}
const TAB_CSS = 'src/styles/emaBlinkTab.css';
const CARD_CSS = 'src/styles/emaBlinkCard.css';
const stripComments = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '');

/** tier → pulse seconds, from every rule whose selector names `.ema-blink-<tier>` and whose body sets an animation. */
function durations(css: string): Record<string, number> {
  const out: Record<string, number> = {};
  const src = stripComments(css).replace(/@media[^{]*\{[\s\S]*?\}\s*\}/g, '');
  for (const m of src.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const sel = m[1], body = m[2];
    const d = body.match(/animation(?:-duration)?\s*:\s*(?:[\w-]+\s+)?([\d.]+)(m?s)\b/);
    if (!d) continue;
    const sec = d[2] === 'ms' ? Number(d[1]) / 1000 : Number(d[1]);
    for (const t of EMA_BLINK_TIERS) {
      if (new RegExp(`\\.ema-blink-${t}(?![\\w-])`).test(sel)) out[t] = sec;
    }
  }
  return out;
}
const keyframeBody = (css: string) => {
  const m = stripComments(css).match(/@keyframes\s+[\w-]+\s*\{([\s\S]*?\})\s*\}/);
  return m ? m[1].replace(/\s+/g, '').replace(/;}/g, '}') : null;
};

describe('(d) CSS source guards', () => {
  it('the tab dot is absolute inside the relative .cm-tab, 6 px, never catches a click', async () => {
    const css = stripComments(await readSrc(TAB_CSS));
    expect(css).toMatch(/\.cm-tabs\s+\.cm-tab\s*\{\s*position:\s*relative;?\s*\}/);
    const rule = css.match(/\.cm-tab-blink\s*\{([^}]*)\}/)![1];
    expect(rule).toMatch(/position:\s*absolute/);
    expect(rule).toMatch(/width:\s*6px/);
    expect(rule).toMatch(/height:\s*6px/);
    expect(rule).toMatch(/pointer-events:\s*none/);
    expect(rule).toMatch(/right:\s*4px/);
  });
  it('the tab duration table EQUALS the card file\'s and is strictly monotone in tier order (fresh fastest)', async () => {
    const tab = durations(await readSrc(TAB_CSS));
    const card = durations(await readSrc(CARD_CSS));
    expect(Object.keys(tab).sort()).toEqual([...EMA_BLINK_TIERS].sort());
    expect(tab).toEqual(card);
    const seq = EMA_BLINK_TIERS.map((t) => tab[t]);
    for (let i = 1; i < seq.length; i++) expect(seq[i]).toBeGreaterThan(seq[i - 1]);
  });
  it('the same keyframes body as the card dot', async () => {
    const a = keyframeBody(await readSrc(TAB_CSS));
    expect(a).not.toBeNull();
    expect(a).toBe(keyframeBody(await readSrc(CARD_CSS)));
  });
  it('reduced motion → animation none, at a specificity that beats every per-tier rule', async () => {
    const css = stripComments(await readSrc(TAB_CSS));
    const m = css.match(/@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{\s*([^{]+)\{([^}]*)\}/)!;
    expect(m).not.toBeNull();
    expect(m[2]).toMatch(/animation:\s*none/);
    const classes = (s: string) => (s.match(/\.[\w-]+/g) || []).length;
    const perTier = [...css.matchAll(/([^{}@]*\.cm-tab-blink\.ema-blink-[\w-]+)\s*\{/g)].map((x) => classes(x[1]));
    expect(perTier.length).toBe(EMA_BLINK_TIERS.length);
    expect(classes(m[1])).toBeGreaterThan(Math.max(...perTier));
  });
  it('NEGATIVE: the duration parser sees no table in a file without one', () => {
    expect(durations('.x { color: red }')).toEqual({});
    expect(durations('.ema-blink-closing_in { animation: p 1s linear }')).toEqual({});
  });
});

describe('(e) no email in any new file', () => {
  it('the WP-F files carry no address', async () => {
    const files = [
      'src/lib/emaBlinkTabs.ts', TAB_CSS, 'src/lib/emaBlinkTabs.test.ts', 'src/pages/ChartMaps.emaBlinkTabs.test.tsx',
    ];
    for (const f of files) {
      const src = await readSrc(f);
      expect(src, f).not.toMatch(/[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}/);
      expect(src.toLowerCase(), f).not.toContain(['kanda', 'katla'].join(''));
    }
  });
});
