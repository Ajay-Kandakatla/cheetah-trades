import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BondeBoard, { type BondeBoardData } from './BondeBoard';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { BONDE_LIVE_COST_SENTENCE } from '../lib/bondeLive';

/* 📈 Bonde — the LIVE leg, the trackers and the held-out footnote (2026-09-20).
 *
 * The negatives are the file. Three of them pin rules that a board can break
 * while looking perfectly fine:
 *   · a close-basis payload must blank EVERY Today cell, including rows that
 *     still carry a number;
 *   · a failed ↻ must leave the good board standing;
 *   · a late first response must lose to the newer one.
 *
 * The board shape below is §3.6's PINNED shape (P6 owns the backend): IOVA is
 * held out with its two period labels, a ⚡ pivot row carries `tier: null`, and
 * `period_ok` appears as all three of true / false / null.
 */

const row = (symbol: string, over: Partial<any> = {}) => ({
  symbol, name: `${symbol} Inc`, tier: 'explosive',
  growth_yoy_pct: 120, base_rev: 5_000_000, latest_rev: 11_000_000,
  rev_added: 6_000_000, base_state: 'ok', sales_score: 100,
  accelerating: true, consecutive_growth_q: 4, sales_led: true,
  pivot: null, is_new: false, period_ok: true, period: 'FY2026 Q2',
  today_pct: null, today_basis: 'close', ...over,
});

const LIVE_D1 = {
  basis: 'live', live: true, market_closed: null, in_session: true,
  session_window: '9:30-16:00 ET', as_of: '2026-09-18T14:14:09+00:00',
  close_as_of: '2026-09-17', symbols: 4, live_names: 4, reason: null,
  tape_session: 'rth', note: 'Today is each name’s own move so far in this session.',
};

const CLOSE_D1 = {
  basis: 'close', live: false, market_closed: 'weekend', in_session: false,
  session_window: '9:30-16:00 ET', as_of: null, close_as_of: '2026-09-19',
  symbols: 4, live_names: 0, reason: 'the market is closed (weekend)',
  tape_session: 'closed', note: 'Every column comes from the 2026-09-19 scan.',
};

const NOTE = 'His screen: 1,051 of 2,076 pass. 164 passers are held OUT of the '
  + 'tiers because their newest quarter and its ‘year-ago’ slot are not four fiscal '
  + 'quarters apart; the 🚀 growth board refuses the same rows. Listed under the board.';

const payload = (over: Partial<BondeBoardData> = {}): BondeBoardData => ({
  sections: {
    pivot: [row('SNDK', { tier: null, period_ok: false, growth_yoy_pct: null,
                          prior_yoy_pct: null, accelerating: null,
                          pivot: { gap_pct: 12.4, vol_mult: 6.1, hours_ago: 3 } })],
    explosive: [row('PTGX', { today_pct: 3.2 })],
    strong: [row('TWLO', { tier: 'strong', period_ok: null, period: null,
                           today_pct: -1.1 })],
    steady: [],
    rejected: [row('HPQ', { tier: 'steady', today_pct: 0.4 })],
  },
  counts: { pivot: 1, explosive: 69, strong: 304, steady: 677, rejected: 120 },
  caps: { pivot: 60, explosive: 60, strong: 60, steady: 40, rejected: 40 },
  n_pass: 1051, n_tiered: 887, n_rejected: 120, n_scanned: 2076,
  n_new: 1, new_days: 30,
  n_period_mismatch: 164,
  period_mismatch_symbols: [
    { symbol: 'IOVA', tier: 'explosive', latest: 'FY2026 Q2', year_ago: 'FY2025 Q1' },
    { symbol: 'DELL', tier: 'explosive', latest: 'FY2026 Q2', year_ago: 'FY2025 Q1' },
  ],
  d1: LIVE_D1,
  regime: { is_bull: true, label: 'confirmed_uptrend', score: 70, scanners_paused: false },
  note: NOTE, scan_ts: '2026-09-17T21:00:00+00:00', ...over,
});

/** Route by URL: the board GET, the bounce-room POST and the watchlist GET are
 *  three different payloads, and handing the board body to all three is how a
 *  render test starts asserting against a shape nothing serves. */
function routedFetch(board: BondeBoardData | (() => Promise<any>), watch: string[] = []) {
  return vi.fn(async (url: any, init?: any) => {
    const u = String(url);
    if (u.includes('/supply-demand/bounce-room') || init?.method === 'POST') {
      return { ok: true, status: 200,
               json: async () => ({ rows: [], params: {}, store_date: null }) } as any;
    }
    if (u.includes('/signal-lab/watchlist')) {
      return { ok: true, status: 200,
               json: async () => ({ symbols: watch, held: [], watch_n: watch.length }) } as any;
    }
    if (typeof board === 'function') return board();
    return { ok: true, status: 200, json: async () => board } as any;
  });
}

const draw = (f: any) => {
  vi.stubGlobal('fetch', f);
  return render(
    <MemoryRouter><BondeBoard /></MemoryRouter>,
  );
};

beforeEach(() => {
  vi.unstubAllGlobals();
  _resetBounceRoomCache();
  _resetSignalWatchlist();
});
afterEach(() => { vi.unstubAllGlobals(); });

// ───────────────────────────────────────────────── the Today column
describe('the Today column', () => {
  it('prints a signed move per row on the live basis', async () => {
    draw(routedFetch(payload()));
    expect(await screen.findByTestId('bd-today-PTGX')).toHaveTextContent('+3.2%');
    expect(screen.getByTestId('bd-today-TWLO')).toHaveTextContent('−1.1%');
    expect(screen.getAllByText('Today').length).toBeGreaterThan(0);
  });

  it('NEGATIVE — a close-basis board blanks EVERY cell, numbers and all', async () => {
    // Rows still carry today_pct here. The basis is what decides.
    draw(routedFetch(payload({ d1: CLOSE_D1 })));
    expect(await screen.findByTestId('bd-today-PTGX')).toHaveTextContent('—');
    expect(screen.getByTestId('bd-today-TWLO')).toHaveTextContent('—');
    expect(screen.getByTestId('bd-today-HPQ')).toHaveTextContent('—');
  });

  it('the basis line says live, with the ET clock', async () => {
    draw(routedFetch(payload()));
    const el = await screen.findByTestId('bonde-basis');
    expect(el.textContent).toContain('Today = live print');
    expect(el.textContent).toContain('as of 10:14 ET');
    expect(el.textContent).toContain('live print on 4 of 4');
  });

  it('NEGATIVE — the basis line says last close and names the date + reason', async () => {
    draw(routedFetch(payload({ d1: CLOSE_D1 })));
    const el = await screen.findByTestId('bonde-basis');
    expect(el.textContent).toContain('Today = last close 2026-09-19');
    expect(el.textContent).toContain('the market is closed (weekend)');
    expect(el.textContent).not.toContain('live print');
  });
});

// ───────────────────────────────────────────────── the ↻ button
describe('↻ Live prices', () => {
  it('reads "↻ Live prices" — the label says what it does', async () => {
    draw(routedFetch(payload()));
    const b = await screen.findByTestId('bonde-rescan');
    expect(b.textContent).toBe('↻ Live prices');
    // NEGATIVE: never "Re-scan" — this board does not scan on the request path.
    expect(b.textContent).not.toMatch(/scan/i);
  });

  it('NEGATIVE — disabled with the CALENDAR’S own words when the tape is shut', async () => {
    draw(routedFetch(payload({ d1: CLOSE_D1 })));
    const b = await screen.findByTestId('bonde-rescan') as HTMLButtonElement;
    expect(b.disabled).toBe(true);
    expect(b.title).toContain('the market is closed (weekend)');
  });

  it('warned but NOT disabled outside the regular session', async () => {
    // He reads extended-hours prints elsewhere; taking the read away would
    // remove a surface he asked for. Warn, do not block.
    draw(routedFetch(payload({
      d1: { ...LIVE_D1, market_closed: null, in_session: false },
    })));
    const b = await screen.findByTestId('bonde-rescan') as HTMLButtonElement;
    expect(b.disabled).toBe(false);
    expect(b.title).toContain('the session is shut (9:30-16:00 ET)');
  });

  it('re-reads the board on click', async () => {
    const f = routedFetch(payload());
    draw(f);
    await screen.findByTestId('bd-today-PTGX');
    const boardCalls = () => f.mock.calls.filter((c) => String(c[0]).includes('/bonde/board')).length;
    const before = boardCalls();
    fireEvent.click(screen.getByTestId('bonde-rescan'));
    await waitFor(() => expect(boardCalls()).toBe(before + 1));
  });

  it('NEGATIVE — a failed re-read keeps the good board and says so', async () => {
    let n = 0;
    const f = vi.fn(async (url: any, init?: any) => {
      const u = String(url);
      if (u.includes('/supply-demand/bounce-room') || init?.method === 'POST') {
        return { ok: true, status: 200, json: async () => ({ rows: [], params: {} }) } as any;
      }
      if (u.includes('/signal-lab/watchlist')) {
        return { ok: true, status: 200, json: async () => ({ symbols: [], held: [] }) } as any;
      }
      n += 1;
      if (n === 1) return { ok: true, status: 200, json: async () => payload() } as any;
      return { ok: false, status: 503, json: async () => ({}) } as any;
    });
    draw(f);
    await screen.findByTestId('bd-today-PTGX');
    fireEvent.click(screen.getByTestId('bonde-rescan'));
    await screen.findByTestId('bonde-err');
    // the rows are still there
    expect(screen.getByTestId('bd-today-PTGX')).toBeTruthy();
    expect(screen.getByTestId('bonde-err').textContent).toContain('503');
  });

  it('a slow first read paints its OWN answer, and the next click replaces it whole', async () => {
    /* LATEST WINS, the observable half. The loader stamps each read with a
     * sequence number and drops any answer that is not the newest; the
     * in-flight guard (next test) is what stops the button from ever starting
     * two at once, so the reachable failure is a re-read that MERGES with the
     * old one and leaves a stale clock in the basis line. It must not. */
    let release: ((v: any) => void) | null = null;
    let n = 0;
    const f = vi.fn(async (url: any, init?: any) => {
      const u = String(url);
      if (u.includes('/supply-demand/bounce-room') || init?.method === 'POST') {
        return { ok: true, status: 200, json: async () => ({ rows: [], params: {} }) } as any;
      }
      if (u.includes('/signal-lab/watchlist')) {
        return { ok: true, status: 200, json: async () => ({ symbols: [], held: [] }) } as any;
      }
      n += 1;
      if (n === 1) return new Promise((res) => { release = res; });   // hangs
      return { ok: true, status: 200,
               json: async () => payload({ d1: { ...LIVE_D1, as_of: '2026-09-18T15:30:00+00:00' } }) } as any;
    });
    draw(f);
    await waitFor(() => expect(release).not.toBeNull());
    // the hanging read paints nothing until it answers, then paints its own
    await act(async () => {
      release!({ ok: true, status: 200,
                 json: async () => payload({ d1: { ...LIVE_D1, as_of: '2026-09-18T14:14:09+00:00' } }) });
    });
    await screen.findByTestId('bonde-basis');
    expect(screen.getByTestId('bonde-basis').textContent).toContain('10:14 ET');
    // and a SECOND click's answer replaces it wholesale — no merge, no stale clock
    fireEvent.click(screen.getByTestId('bonde-rescan'));
    await waitFor(() => expect(screen.getByTestId('bonde-basis').textContent).toContain('11:30 ET'));
    expect(screen.getByTestId('bonde-basis').textContent).not.toContain('10:14 ET');

  });

  it('NEGATIVE — a second click while a read is in flight fires no second request', async () => {
    let release: ((v: any) => void) | null = null;
    let n = 0;
    const f = vi.fn(async (url: any, init?: any) => {
      const u = String(url);
      if (u.includes('/supply-demand/bounce-room') || init?.method === 'POST') {
        return { ok: true, status: 200, json: async () => ({ rows: [], params: {} }) } as any;
      }
      if (u.includes('/signal-lab/watchlist')) {
        return { ok: true, status: 200, json: async () => ({ symbols: [], held: [] }) } as any;
      }
      n += 1;
      if (n === 1) return { ok: true, status: 200, json: async () => payload() } as any;
      return new Promise((res) => { release = res; });               // #2 hangs
    });
    draw(f);
    await screen.findByTestId('bd-today-PTGX');
    const boardCalls = () => f.mock.calls.filter((c) => String(c[0]).includes('/bonde/board')).length;
    fireEvent.click(screen.getByTestId('bonde-rescan'));
    await waitFor(() => expect(release).not.toBeNull());
    fireEvent.click(screen.getByTestId('bonde-rescan'));
    fireEvent.click(screen.getByTestId('bonde-rescan'));
    expect(boardCalls()).toBe(2);
    await act(async () => {
      release!({ ok: true, status: 200, json: async () => payload() });
    });
  });

  it('the ⓘ names 2 calls and never Hottest’s 1,721 names', async () => {
    draw(routedFetch(payload()));
    await screen.findByTestId('bd-today-PTGX');
    fireEvent.click(screen.getByRole('button', { name: /Bonde — what/ }));
    const panel = document.querySelector('.info-button');
    expect(panel?.textContent).toContain(BONDE_LIVE_COST_SENTENCE);
    expect(panel?.textContent).toContain('2 Massive snapshot calls');
    expect(panel?.textContent).not.toContain('1,721');
    expect(panel?.textContent).not.toMatch(/\b7 snapshot\b/);
  });
});

// ───────────────────────────────────────────────── trackers
describe('trackers', () => {
  it('every row carries a non-compact + Signals button', async () => {
    draw(routedFetch(payload()));
    const b = await screen.findByTestId('watch-PTGX');
    expect(b.textContent).toContain('Signals');     // never a bare "+"
    for (const s of ['SNDK', 'TWLO', 'HPQ']) expect(screen.getByTestId(`watch-${s}`)).toBeTruthy();
  });

  it('📡 tracked only keeps the watchlist names and hides the rest', async () => {
    draw(routedFetch(payload(), ['PTGX']));
    await screen.findByTestId('bd-today-PTGX');
    await waitFor(() => expect((screen.getByTestId('watch-PTGX') as HTMLButtonElement)
      .getAttribute('aria-pressed')).toBe('true'));
    fireEvent.click(screen.getByLabelText(/tracked only/i, { selector: 'input' }));
    await waitFor(() => expect(screen.queryByTestId('bd-today-TWLO')).toBeNull());
    expect(screen.getByTestId('bd-today-PTGX')).toBeTruthy();
  });

  it('NEGATIVE — 📡 composes with ✨ new only rather than replacing it', async () => {
    // PTGX is tracked but NOT new; SNDK is new but NOT tracked. Both boxes on
    // must leave nothing, not "whichever filter ran last".
    draw(routedFetch(payload({
      sections: {
        ...payload().sections,
        explosive: [row('PTGX', { today_pct: 3.2, is_new: false })],
        pivot: [row('SNDK', { tier: null, period_ok: false, is_new: true,
                              first_seen: '2026-09-18T00:00:00+00:00',
                              pivot: { gap_pct: 12.4, vol_mult: 6.1, hours_ago: 3 } })],
      },
    }), ['PTGX']));
    await screen.findByTestId('bd-today-PTGX');
    await waitFor(() => expect((screen.getByTestId('watch-PTGX') as HTMLButtonElement)
      .getAttribute('aria-pressed')).toBe('true'));
    fireEvent.click(screen.getByLabelText(/tracked only/i, { selector: 'input' }));
    fireEvent.click(screen.getByLabelText(/new arrivals only/i, { selector: 'input' }));
    await waitFor(() => expect(screen.queryByTestId('bd-today-PTGX')).toBeNull());
    expect(screen.queryByTestId('bd-today-SNDK')).toBeNull();
  });

  it('✨ NEW carries the arrival DATE on the badge', async () => {
    draw(routedFetch(payload({
      sections: { ...payload().sections,
                  explosive: [row('PTGX', { is_new: true, today_pct: 3.2,
                                            first_seen: '2026-09-18T00:00:00+00:00' })] },
    })));
    const badge = await screen.findByTestId('bd-new-PTGX');
    expect(badge.textContent).toBe('✨ NEW · 09-18');
    expect(badge.title).toContain('2026-09-18');
  });

  it('NEGATIVE — an arrival with no first_seen still badges, without a date', async () => {
    draw(routedFetch(payload({
      sections: { ...payload().sections,
                  explosive: [row('PTGX', { is_new: true, first_seen: null })] },
    })));
    const badge = await screen.findByTestId('bd-new-PTGX');
    expect(badge.textContent).toBe('✨ NEW');
  });
});

// ─────────────────────────────────── the held-out footnote + the pair marks
describe('held out — the pair that is not four quarters apart', () => {
  it('lists the count, the served sentence and every row', async () => {
    draw(routedFetch(payload()));
    const block = await screen.findByTestId('bonde-heldout');
    expect(block.textContent).toContain('Held out — quarter not four apart (164)');
    expect(block.textContent).toContain('164 passers are held OUT');
    expect(block.textContent).toContain('IOVA');
    expect(block.textContent).toContain('explosive');
    expect(block.textContent).toContain('FY2026 Q2');
    expect(block.textContent).toContain('FY2025 Q1');
  });

  it('NEGATIVE — a held-out name is in NO tier section', async () => {
    draw(routedFetch(payload()));
    await screen.findByTestId('bonde-heldout');
    expect(screen.queryByTestId('bd-today-IOVA')).toBeNull();
    expect(screen.queryByTestId('watch-IOVA')).toBeNull();
  });

  it('NEGATIVE — the block is absent when nothing was held out', async () => {
    draw(routedFetch(payload({ n_period_mismatch: 0, period_mismatch_symbols: [],
                               note: 'His screen: 1,051 of 2,076 pass.' })));
    await screen.findByTestId('bd-today-PTGX');
    expect(screen.queryByTestId('bonde-heldout')).toBeNull();
  });

  it('period_ok false → ⚠ pair, null → unverified, true → nothing', async () => {
    draw(routedFetch(payload()));
    await screen.findByTestId('bd-today-PTGX');
    expect(screen.getByTestId('bd-pair-SNDK').textContent).toBe('⚠ pair');
    expect(screen.getByTestId('bd-pair-TWLO').textContent).toBe('unverified');
    expect(screen.queryByTestId('bd-pair-PTGX')).toBeNull();
  });

  it('NEGATIVE — a ⚡ pivot row whose tier was withheld renders an em-dash', async () => {
    draw(routedFetch(payload()));
    await screen.findByTestId('bd-today-PTGX');
    expect(screen.getByTestId('bd-tier-SNDK').textContent).toBe('—');
  });
});

describe('the word "bounce" never reaches the rendered page', () => {
  it('nothing he reads says it', async () => {
    const { container } = draw(routedFetch(payload()));
    await screen.findByTestId('bd-today-PTGX');
    expect(container.textContent?.toLowerCase()).not.toContain('bounce');
  });
});

/* 📋 HIS SURFACE, the real payload (2026-09-20).
 *
 * Rule: verify on the surface he reads, not the one convenient to test. The
 * api container runs origin/main, so the branch API is served on :8001 and its
 * `/bonde/board` answer is written to the scratchpad; this renders THAT JSON
 * through the real component. It SKIPS when the file is absent, so the suite
 * still runs on a machine that never curled the branch — and says so, rather
 * than passing green on a fixture nobody produced. */
const LIVE_BOARD_JSON: string =
  (globalThis as any).process?.env?.BONDE_BOARD_LIVE_JSON
  || '/private/tmp/claude-501/-Users-ajay-clinet-test/'
     + '2ced0bf8-920d-4009-be24-082dc21c5651/scratchpad/bonde-picks-v4/board_live.json';

async function readLiveBoard(): Promise<BondeBoardData | null> {
  try {
    // Non-literal specifier on purpose: the project carries no node types, and
    // the browser build must never try to resolve this.
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    if (!fs?.existsSync?.(LIVE_BOARD_JSON)) return null;
    return JSON.parse(fs.readFileSync(LIVE_BOARD_JSON, 'utf8'));
  } catch {
    return null;
  }
}

const LIVE_BOARD = await readLiveBoard();

describe.skipIf(!LIVE_BOARD)('📋 the REAL /bonde/board payload renders his pick line', () => {
  it('the legend appears exactly once', async () => {
    draw(routedFetch(LIVE_BOARD as BondeBoardData));
    await waitFor(() => expect(screen.getAllByTestId('bonde-criteria').length).toBe(1));
  });

  it('every drawn row has a chip line', async () => {
    const { container } = draw(routedFetch(LIVE_BOARD as BondeBoardData));
    await waitFor(() => expect(container.querySelector('.bd-rows')).toBeTruthy());
    const rows = [...container.querySelectorAll('.bd-row:not(.bd-hdr)')];
    expect(rows.length).toBeGreaterThan(0);
    for (const r of rows) expect(r.querySelector('.bd-pick')).toBeTruthy();
  });

  it('NEGATIVE — no chip reads ✓ where the served leg is unknown', async () => {
    const { container } = draw(routedFetch(LIVE_BOARD as BondeBoardData));
    await waitFor(() => expect(container.querySelector('.bd-pick')).toBeTruthy());
    const d = LIVE_BOARD as any;
    for (const rows of Object.values(d.sections || {}) as any[]) {
      for (const r of rows || []) {
        for (const [key, leg] of Object.entries((r.pick?.legs || {}) as any)) {
          if ((leg as any).ok !== null && (leg as any).ok !== undefined) continue;
          const chip = screen.queryByTestId(`bd-pick-${r.symbol}-${key}`);
          if (!chip) continue;
          expect(chip.textContent, `${r.symbol}.${key}`).not.toContain('✓');
          expect(chip.textContent, `${r.symbol}.${key}`).not.toContain('✗');
        }
      }
    }
  });

  it('NEGATIVE — no row text is a tally out of 14', async () => {
    const { container } = draw(routedFetch(LIVE_BOARD as BondeBoardData));
    await waitFor(() => expect(container.querySelector('.bd-pick')).toBeTruthy());
    expect(container.textContent || '').not.toMatch(/\/14\b/);
  });
});
