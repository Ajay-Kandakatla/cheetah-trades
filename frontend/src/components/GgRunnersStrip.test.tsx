import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GG_RUNNERS_PATH, GGR_OPEN_KEY } from '../lib/ggRunners';
import { GGW_PHONE_MQ } from '../lib/gajjalaWatch';
import { usePhone } from './GajjalaWatchTile';

/* 📅 Previous day runners — the strip (2026-11-22, spec watch_org rev 4 §3.6 / §4 WP-FE-STRIP).
 *
 * Ajay 2026-11-22: "remove hot sectors mess from Gajjalas top view I need a new thing there.. use that space between the
 * parent tab of Gajjala and watch tab to be for previous day runners but remove them if they don’t run the current day".
 *
 * The REAL component, the REAL lib hook and the REAL GgWatchButton (its list store mocked to an owner answer); fetch is
 * stubbed with the §3.4 payload shape carrying the §3.8 probe oracle (Ran Fri 11-20, 18 names; CHSN 🚫 last). NEGATIVES:
 * owner_only / off / garbage / NaN draw nothing; error draws the sentence only; junk fold sizes and a junk ggr.open
 * never crash; the source files hold no threshold, clock time or sentence literal and no own media query. */

vi.mock('../lib/ggWatchList', async (orig) => {
  const m: any = await orig();
  return {
    ...m,
    useGgwList: () => ({
      phase: 'ok', symbols: ['MSS'], full: false, full_text: null, busy: null, msg: null,
      labels: { add: '➕', remove: '➖', add_title: 'Add {sym}', remove_title: 'Remove {sym}' },
    }),
  };
});

import GgRunnersStrip from './GgRunnersStrip';

const SYMS = ['MEDS', 'MSS', 'CIGL', 'MRM', 'ZJK', 'SRTM', 'WETO', 'LVWR', 'AKAN', 'YOUL', 'GOVX', 'AMCI', 'IMCC',
  'INV', 'ELOG', 'LABT', 'AZIO', 'CHSN'];
const PCT = [165.2, 150.7, 128.1, 125.4, 105.9, 86.4, 67.5, 65.4, 63.3, 58.4, 55.0, 52.0, 50.0, 48.0, 46.0, 44.3,
  40.0, 144.1];

const row = (symbol: string, i: number) => ({
  symbol, run_pct: PCT[i], run_text: `+${Math.floor(PCT[i])}%`, timing: 'intraday', timing_text: '☀️ intraday',
  peak_et: '12:50', float_text: `float-${symbol}`, float_title: `float title ${symbol}`,
  past_winner_text: symbol === 'MEDS' ? '🏆 09-16' : null, past_winner_title: symbol === 'MEDS' ? '09-16 multi-day' : null,
  broker_text: symbol === 'CHSN' ? '🚫' : null, today_state: null, today_pct: null, today_text: null,
  title: `title ${symbol}`,
});

const OK = (): Record<string, any> => ({
  state: 'ok', title: '📅 Previous day runners — Fri 11-20', text: '18', hint: 'served hint words',
  day: '2026-11-20', day_word: 'Fri', today: '2026-11-23', live: true, cut_active: false, cut_at: '09:45',
  refresh_sec: 300, fold_at: 8, fold_at_phone: 3, more_text: '+{n} more', less_text: 'show less',
  n: 18, n_running: 0, n_not_read: 0, no_bars: 0, as_of_et: null, stale: false,
  rows: SYMS.map(row), removed: [], removed_text: null,
});

let body: unknown;
let fetchMock: ReturnType<typeof vi.fn>;
let phone = false;

function stubMatchMedia() {
  vi.stubGlobal('matchMedia', (q: string) => ({
    matches: phone && q === GGW_PHONE_MQ, media: q, onchange: null,
    addEventListener: () => undefined, removeEventListener: () => undefined,
    addListener: () => undefined, removeListener: () => undefined, dispatchEvent: () => false,
  }));
}

/** An in-memory store (the emaFrames.test precedent — this jsdom build has no usable localStorage). */
function mem() {
  const m = new Map<string, string>();
  return { getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
           removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear() };
}

beforeEach(() => {
  vi.stubGlobal('localStorage', mem());
  phone = false;
  body = OK();
  fetchMock = vi.fn(async (url: string) => {
    if (!String(url).endsWith(GG_RUNNERS_PATH)) throw new Error(`unexpected fetch ${url}`);
    return { ok: true, json: async () => body };
  });
  vi.stubGlobal('fetch', fetchMock);
  stubMatchMedia();
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

const chipSyms = () => screen.queryAllByTestId(/^ggr-chip-/).map((e) => e.getAttribute('data-testid')!.slice(9));
const miniSyms = () => screen.queryAllByTestId(/^ggr-mini-/).map((e) => e.getAttribute('data-testid')!.slice(9));

async function mount(props: { fold?: boolean } = {}) {
  const r = render(<GgRunnersStrip {...props} />);
  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  await act(async () => { await Promise.resolve(); });
  return r;
}

describe('📅 strip — desktop', () => {
  it('title, count, hint and the first fold_at chips in served order + "+n more"', async () => {
    await mount();
    await screen.findByTestId('ggr-strip');
    expect(screen.getByTestId('ggr-title')).toHaveTextContent('📅 Previous day runners — Fri 11-20');
    expect(screen.getByTestId('ggr-count').textContent).toBe('18');
    expect(screen.getByTestId('ggr-hint').tagName).toBe('DETAILS');
    expect(screen.getByTestId('ggr-hint')).toHaveTextContent('served hint words');
    expect(chipSyms()).toEqual(SYMS.slice(0, 8));
    expect(screen.getByTestId('ggr-more').textContent).toBe('+10 more');
    expect(miniSyms()).toEqual([]);
  });

  it('a full chip carries run, timing, float (title), 🏆 (title), the row title and the ➕ GgWatchButton', async () => {
    await mount();
    const c = await screen.findByTestId('ggr-chip-MEDS');
    expect(c).toHaveAttribute('title', 'title MEDS');
    expect(c).toHaveTextContent('MEDS');
    expect(c).toHaveTextContent('+165%');
    expect(c).toHaveTextContent('☀️ intraday');
    expect(within(c).getByText('float-MEDS')).toHaveAttribute('title', 'float title MEDS');
    expect(within(c).getByText('🏆 09-16')).toHaveAttribute('title', '09-16 multi-day');
    expect(within(c).getByTestId('ggw-card-btn-MEDS').textContent).toBe('➕');
    expect(screen.getByTestId('ggw-card-btn-MSS').textContent).toBe('➖');
  });

  it('"+n more" opens every chip, "show less" folds, remembered in ggr.open', async () => {
    const r = await mount();
    fireEvent.click(await screen.findByTestId('ggr-more'));
    expect(chipSyms()).toEqual(SYMS);
    expect(chipSyms().at(-1)).toBe('CHSN');
    expect(screen.getByTestId('ggr-chip-CHSN').className).toContain('is-broker');
    expect(screen.getByTestId('ggr-more').textContent).toBe('show less');
    expect(localStorage.getItem(GGR_OPEN_KEY)).toBe('open');
    r.unmount();
    await mount();
    await screen.findByTestId('ggr-chip-CHSN');
    expect(chipSyms()).toEqual(SYMS);
    fireEvent.click(screen.getByTestId('ggr-more'));
    expect(chipSyms()).toEqual(SYMS.slice(0, 8));
    expect(localStorage.getItem(GGR_OPEN_KEY)).toBeNull();
  });

  it('fold={false} → every chip, no ggr-more', async () => {
    await mount({ fold: false });
    await screen.findByTestId('ggr-chip-CHSN');
    expect(chipSyms()).toEqual(SYMS);
    expect(screen.queryByTestId('ggr-more')).toBeNull();
  });

  it('rows ≤ fold_at → every chip, no ggr-more', async () => {
    body = { ...OK(), rows: SYMS.slice(0, 5).map(row) };
    await mount();
    await screen.findByTestId('ggr-chip-ZJK');
    expect(chipSyms()).toEqual(SYMS.slice(0, 5));
    expect(screen.queryByTestId('ggr-more')).toBeNull();
  });

  it('removed list in a CLOSED <details>, each "{symbol} {run_text} · {text}"', async () => {
    body = { ...OK(), cut_active: true, removed_text: '11 not … served',
      removed: [{ symbol: 'VIVS', run_text: '+241%', today_pct: 20.0, text: 'today +20.0% since 09:30' },
        { symbol: 'POAS', run_text: '+105%', today_pct: 3.1, text: 'today +3.1% since 09:30' }] };
    await mount();
    const d = await screen.findByTestId('ggr-removed');
    expect(d.tagName).toBe('DETAILS');
    expect(d).not.toHaveAttribute('open');
    expect(d.querySelector('summary')!.textContent).toBe('11 not … served');
    expect(screen.getByTestId('ggr-removed-VIVS').textContent).toBe('VIVS +241% · today +20.0% since 09:30');
    expect(screen.queryByTestId('ggr-chip-VIVS')).toBeNull();
  });

  it('the count prints the served text verbatim incl. the not-read and stale tails', async () => {
    const t = "3 running today of 14 · 2 not read yet · today's read is from 10:02 ET — nothing removed";
    body = { ...OK(), cut_active: true, text: t, stale: true, as_of_et: '10:02' };
    await mount();
    expect((await screen.findByTestId('ggr-count')).textContent).toBe(t);
  });
});

describe('📱 strip — phone (usePhone, the Watch media query)', () => {
  beforeEach(() => { phone = true; });

  it('usePhone is the Watch export the strip reuses', () => {
    expect(typeof usePhone).toBe('function');
  });

  it('folded = ONE line: title · count · first fold_at_phone minis · ggr-more; no full chip, no ➕', async () => {
    await mount();
    const s = await screen.findByTestId('ggr-strip');
    expect(s.querySelector('.ggr-line')).not.toBeNull();
    expect(miniSyms()).toEqual(['MEDS', 'MSS', 'CIGL']);
    expect(screen.getByTestId('ggr-mini-MEDS').textContent).toBe('MEDS +165%');
    expect(chipSyms()).toEqual([]);
    expect(screen.queryAllByTestId(/^ggw-card-btn-/)).toEqual([]);
    expect(screen.queryByText('☀️ intraday')).toBeNull();
    expect(screen.queryByText('🏆 09-16')).toBeNull();
    expect(screen.getByTestId('ggr-title')).toBeInTheDocument();
    expect(screen.getByTestId('ggr-count').textContent).toBe('18');
    expect(screen.getByTestId('ggr-more').textContent).toBe('+15 more');
  });

  it('open → every FULL chip (with ➕), "show less" folds back to the one line', async () => {
    await mount();
    fireEvent.click(await screen.findByTestId('ggr-more'));
    expect(chipSyms()).toEqual(SYMS);
    expect(miniSyms()).toEqual([]);
    expect(screen.getByTestId('ggw-card-btn-MEDS')).toBeInTheDocument();
    expect(localStorage.getItem(GGR_OPEN_KEY)).toBe('open');
    fireEvent.click(screen.getByTestId('ggr-more'));
    expect(miniSyms()).toEqual(['MEDS', 'MSS', 'CIGL']);
  });

  it('fold={false} on the phone → every full chip, no ggr-more', async () => {
    await mount({ fold: false });
    await screen.findByTestId('ggr-chip-CHSN');
    expect(chipSyms()).toEqual(SYMS);
    expect(screen.queryByTestId('ggr-more')).toBeNull();
  });

  it.each([0, 'x', null, 2.5, -3])('NEGATIVE: fold_at_phone %s → every mini, never a crash', async (v) => {
    body = { ...OK(), fold_at_phone: v };
    await mount();
    await screen.findByTestId('ggr-mini-CHSN');
    expect(miniSyms()).toEqual(SYMS);
    expect(screen.getByTestId('ggr-more')).toBeInTheDocument();
  });
});

describe('📅 strip — NEGATIVES', () => {
  it.each([
    ['owner_only', { state: 'owner_only' }],
    ['off', { state: 'off' }],
    ['unknown state', { ...OK(), state: 'later' }],
    ['NaN n', { ...OK(), n: NaN }],
    ['NaN run_pct', { ...OK(), rows: [{ ...row('MEDS', 0), run_pct: NaN }] }],
  ])('%s → renders nothing, no NaN text', async (_k, b) => {
    body = b;
    const { container } = await mount();
    await act(async () => { await Promise.resolve(); });
    expect(screen.queryByTestId('ggr-strip')).toBeNull();
    expect(container.textContent).not.toContain('NaN');
    expect(container.innerHTML).toBe('');
  });

  it('garbage JSON → renders nothing', async () => {
    fetchMock.mockImplementation(async () => ({ ok: true, json: async () => { throw new SyntaxError('bad'); } }));
    const { container } = await mount();
    await act(async () => { await Promise.resolve(); });
    expect(container.innerHTML).toBe('');
  });

  it('error → the served sentence only, no chips, no more', async () => {
    body = { state: 'error', text: "Last session's runners could not be read — served." };
    await mount();
    const s = await screen.findByTestId('ggr-strip');
    expect(screen.getByTestId('ggr-count').textContent).toBe("Last session's runners could not be read — served.");
    expect(screen.queryByTestId('ggr-title')).toBeNull();
    expect(chipSyms()).toEqual([]);
    expect(screen.queryByTestId('ggr-more')).toBeNull();
    expect(s.textContent).toBe("Last session's runners could not be read — served.");
  });

  it('empty → head + served text, no chips', async () => {
    body = { ...OK(), state: 'empty', text: 'served empty words', rows: [] };
    await mount();
    expect((await screen.findByTestId('ggr-count')).textContent).toBe('served empty words');
    expect(chipSyms()).toEqual([]);
  });

  it('a row missing run_text is dropped', async () => {
    body = { ...OK(), rows: [{ ...row('MEDS', 0), run_text: null }, row('MSS', 1)] };
    await mount();
    await screen.findByTestId('ggr-chip-MSS');
    expect(chipSyms()).toEqual(['MSS']);
  });

  it.each(['1', 'true', '{', 'OPEN'])('junk ggr.open %s → folded', async (v) => {
    localStorage.setItem(GGR_OPEN_KEY, v);
    await mount();
    await screen.findByTestId('ggr-more');
    expect(chipSyms()).toEqual(SYMS.slice(0, 8));
  });

  it('fold_at junk on desktop → every chip, no ggr-more', async () => {
    body = { ...OK(), fold_at: 'eight' };
    await mount();
    await screen.findByTestId('ggr-chip-CHSN');
    expect(chipSyms()).toEqual(SYMS);
    expect(screen.queryByTestId('ggr-more')).toBeNull();
  });

  it('no served more/less words → every chip, no FE-typed button', async () => {
    body = { ...OK(), more_text: null };
    await mount();
    await screen.findByTestId('ggr-chip-CHSN');
    expect(screen.queryByTestId('ggr-more')).toBeNull();
  });
});

/* SOURCE guards: jsdom has no layout and the FE must type no threshold / time / sentence. */
describe('📅 strip — source guards', () => {
  async function read(rel: string): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    return fs.readFileSync(`${root}/src/${rel}`, 'utf8');
  }
  const FILES = ['lib/ggRunners.ts', 'components/GgRunnersStrip.tsx', 'styles/ggRunners.css'];
  const rule = (src: string, sel: string): string | null => {
    const m = src.match(new RegExp(`(^|\\n)\\s*${sel.replace('.', '\\.')}\\s*\\{([^}]*)\\}`));
    return m ? m[2] : null;
  };

  it('430 px: .ggr-chips wraps and may shrink; .ggr-line may shrink; .ggr-chip may shrink', async () => {
    const css = await read('styles/ggRunners.css');
    const chips = rule(css, '.ggr-chips')!;
    expect(chips).toMatch(/flex-wrap:\s*wrap/);
    expect(chips).toMatch(/min-width:\s*0/);
    expect(rule(css, '.ggr-line')!).toMatch(/min-width:\s*0/);
    expect(rule(css, '.ggr-chip')!).toMatch(/min-width:\s*0/);
  });

  it('NEGATIVE: the matcher rejects a stylesheet that lost the rule', () => {
    const bad = '.ggr-chips { display: flex; gap: 4px; }\n.ggr-line { display: flex; }';
    expect(rule(bad, '.ggr-chips')!).not.toMatch(/flex-wrap:\s*wrap/);
    expect(rule(bad, '.ggr-line')!).not.toMatch(/min-width:\s*0/);
  });

  it.each(FILES)('%s holds no threshold / clock / sentence literal, no EventSource, no own media query', async (f) => {
    const src = await read(f);
    for (const lit of ['+40', '25', '09:45', 'Ran ', 'running', 'not read', 'EventSource', 'matchMedia(']) {
      expect(src.includes(lit), `${f} contains ${lit}`).toBe(false);
    }
  });

  it('the component reuses GgWatchButton + usePhone and never imports HotSectors or pages/', async () => {
    const src = await read('components/GgRunnersStrip.tsx');
    expect(src).toMatch(/import \{ GgWatchButton \} from '\.\/GgWatchButton'/);
    expect(src).toMatch(/import \{ usePhone \} from '\.\/GajjalaWatchTile'/);
    expect(src).not.toMatch(/HotSectors/);
    expect(src).not.toMatch(/from '\.\.\/pages\//);
    expect(src).not.toMatch(/ggw-card-btn/);
  });
});
