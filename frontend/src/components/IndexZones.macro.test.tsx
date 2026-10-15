import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import IndexZones, {
  INDEX_ZONE_SYMBOLS, IZ_MACRO, _resetIndexZonesFallback, izDefaultRes, izMacroOpen,
  izMacroState, izMacroThrough, izMacroWhere, izPrice, izProgressText, izView, izWindowLabel,
} from './IndexZones';
import { ChartMaps } from '../pages/ChartMaps';
import { IZ_OPEN_PARAM } from '../lib/chartMaps';
import type { CmIndexZoneProgress, CmIndexZoneRead, CmIndexZones } from '../lib/chartMaps';
import FIXTURE from './__fixtures__/index_zones_2026_10_15.json';

/* 🧭 macro rows — TLT / UUP / GLD under the SPY / QQQ cards (2026-10-15).
 *
 * Ajay, verbatim: "how can.I check us bonds and us dollar and gold can you add
 * them to the SPY and QQQ please? I wanna see their progress".
 *
 * The rules: the rows print the SERVED texts (index_zones.progress_read) and
 * do no arithmetic on a move; a symbol the overnight job has not stored says
 * so and never reads as zero; one row opens at a time through ?iz_open=, to
 * the SAME card SPY and QQQ draw; the header's date is SPY / QQQ's, and a row
 * on another session prints `through {date}` itself.
 *
 * The captured fixture (main session, M1: a GET before and after the first
 * hand-run) is never edited by hand.
 */

const FIX = FIXTURE as unknown as {
  captured_at: string;
  before_first_run: CmIndexZones;
  after_first_run: CmIndexZones;
};
const AFTER = FIX.after_first_run;
const BEFORE = FIX.before_first_run;
const MACRO_SYMS = IZ_MACRO.map((m) => m.symbol);

vi.mock('../lib/usageTracker', () => ({ trackFeature: vi.fn() }));
vi.mock('../hooks/useMyFeatures', () => ({
  useMyFeatures: () => ({ loaded: true, features: new Set(['chart-maps']), catalog: [], email: null }),
}));

/** Every standalone render needs a fetch (the strip's fallback, the chart
 *  chrome). 404 on the strip's own endpoint unless a doc is handed in. */
function stubQuiet(indexZones?: unknown) {
  return vi.fn(async (url: string) => {
    if (String(url).includes('/supply-demand/index-zones')) {
      return indexZones === undefined
        ? ({ ok: false, status: 404, json: async () => ({}) } as Response)
        : ({ ok: true, status: 200, json: async () => indexZones } as Response);
    }
    return { ok: true, status: 200, json: async () => ({}) } as Response;
  });
}

function Probe() {
  const loc = useLocation();
  return <output data-testid="probe">{loc.search}</output>;
}

const draw = (data?: CmIndexZones | null, at = '/') => render(
  <MemoryRouter initialEntries={[at]}><IndexZones data={data} /><Probe /></MemoryRouter>,
);
const search = () => new URLSearchParams(screen.getByTestId('probe').textContent || '');

/** The ?raw reader for `index_zones.MACRO` — the exact multi-line literal
 *  BUILD_SPEC3 §3.1 fixes. null when the literal is not there as written. */
function readMacro(src: string): Array<[string, string]> | null {
  const m = /^MACRO = \(\n([\s\S]*?)\n\)\n/m.exec(src);
  if (!m) return null;
  const pairs = [...m[1].matchAll(/\("([A-Z]+)", "([^"]+)"\)/g)].map((x) => [x[1], x[2]] as [string, string]);
  return pairs.length ? pairs : null;
}
function readIndexes(src: string): string[] | null {
  const m = /^INDEXES = \(([^)]*)\)/m.exec(src);
  if (!m) return null;
  return [...m[1].matchAll(/"([A-Z]+)"/g)].map((x) => x[1]);
}

/** A minimal labelled unit read — NOT a measurement. */
function unit(symbol: string, asOf: string | null, progress: CmIndexZoneProgress | null,
              extra: Partial<CmIndexZoneRead> = {}): CmIndexZoneRead {
  return {
    symbol, name: symbol, as_of: asOf, close: 50, available: true, source: 'computed',
    bands: [], resolutions: {}, progress, ...extra,
  } as CmIndexZoneRead;
}
function prog(over: Partial<CmIndexZoneProgress> = {}): CmIndexZoneProgress {
  return {
    through: '2026-10-14', ret_5d: 1.5, ret_21d: -2.25, today_pct: 0.5, today_prev_close: 50,
    today_state: 'read', windows: { ret_5d: 5, ret_21d: 21 },
    text: { today: '+0.5%', ret_5d: '+1.5%', ret_21d: '−2.3%' },
    note: 'Today: the live print 50.25 against the 2026-10-14 close 50.00. 5d and 21d: the last 5 and 21 closed sessions through the 2026-10-14 close.',
    ...over,
  };
}

beforeEach(() => {
  _resetIndexZonesFallback();
  vi.stubGlobal('fetch', stubQuiet());
});
afterEach(() => vi.unstubAllGlobals());

/* ── F1: the ?raw pins ─────────────────────────────────────────────────────── */

describe('F1 — IZ_MACRO and INDEX_ZONE_SYMBOLS mirror index_zones.py', () => {
  it('MACRO pairs == IZ_MACRO (order included); INDEXES == INDEX_ZONE_SYMBOLS', async () => {
    const { default: src } = await import('../../../backend/supply_demand/index_zones.py?raw');
    expect(readMacro(src)).toEqual(IZ_MACRO.map((m) => [m.symbol, m.label]));
    expect(readIndexes(src)).toEqual([...INDEX_ZONE_SYMBOLS]);
  });

  it('NEGATIVE: the reader returns null for MACROS, an indented MACRO and an empty file', () => {
    const body = '\n    ("TLT", "US bonds (20y+)"),\n)\n';
    expect(readMacro(`MACRO = (${body}`)).toEqual([['TLT', 'US bonds (20y+)']]);
    expect(readMacro(`MACROS = (${body}`)).toBeNull();
    expect(readMacro(`  MACRO = (${body}`)).toBeNull();
    expect(readMacro('')).toBeNull();
    expect(readIndexes('')).toBeNull();
  });
});

/* ── F2: the strip ─────────────────────────────────────────────────────────── */

describe('F2 — the strip: title, aria-label, three collapsed rows under the cards', () => {
  it('names the strip, and lists TLT / UUP / GLD after QQQ, all collapsed', () => {
    draw(AFTER);
    expect(screen.getByRole('complementary', { name: 'SPY, QQQ and macro zones' })).toBeTruthy();
    expect(screen.getByText('🧭 SPY · QQQ · macro zones')).toBeTruthy();
    const list = screen.getByTestId('index-macro');
    expect(list.getAttribute('aria-label')).toBe('US bonds, US dollar and gold');
    const rows = [...list.querySelectorAll(':scope > li')].map((li) => li.getAttribute('data-testid'));
    expect(rows).toEqual(['index-macro-TLT', 'index-macro-UUP', 'index-macro-GLD']);
    const qqq = screen.getByTestId('index-zone-QQQ');
    for (const sym of MACRO_SYMS) {
      const row = screen.getByTestId(`index-macro-${sym}`);
      // eslint-disable-next-line no-bitwise
      expect(qqq.compareDocumentPosition(row) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(screen.getByTestId(`index-macro-toggle-${sym}`).getAttribute('aria-expanded')).toBe('false');
      expect(row.getAttribute('data-open')).toBe('false');
      expect(screen.queryByTestId(`index-macro-card-${sym}`)).toBeNull();
      // Collapsed rows draw no card of their own.
      expect(screen.queryByTestId(`index-zone-${sym}`)).toBeNull();
    }
  });

  it('NEGATIVE: the SPY / QQQ cards still draw their charts and full ladders', () => {
    draw(AFTER);
    for (const sym of INDEX_ZONE_SYMBOLS) {
      const read = AFTER.indexes![sym]!;
      const fine = read.resolutions!.fine!.bands!.length;
      expect(screen.getByTestId(`index-zone-chart-${sym}`)).toBeTruthy();
      expect(within(screen.getByTestId(`index-zone-ladder-${sym}`)).getAllByRole('listitem'))
        .toHaveLength(fine);
      // …and they draw no progress line (HIS CALL #7).
      expect(screen.getByTestId(`index-zone-${sym}`).textContent).not.toContain(read.progress!.note!);
    }
    expect(screen.queryByTestId('index-macro-SPY')).toBeNull();
    expect(screen.queryByTestId('index-macro-QQQ')).toBeNull();
  });
});

/* ── F3: the captured fixture, after the first run ─────────────────────────── */

describe('F3 — after_first_run: every cell is the served value, verbatim', () => {
  it('today / 5d / 21d / px / where / title come straight off the payload', () => {
    draw(AFTER);
    for (const sym of MACRO_SYMS) {
      const read = AFTER.indexes![sym]!;
      const p = read.progress!;
      const row = screen.getByTestId(`index-macro-${sym}`);
      expect(row.getAttribute('data-state')).toBe('read');
      expect(screen.getByTestId(`index-macro-today-${sym}`).textContent).toBe(`today ${p.text!.today}`);
      expect(screen.getByTestId(`index-macro-5d-${sym}`).textContent)
        .toBe(`${p.windows!.ret_5d}d ${p.text!.ret_5d}`);
      expect(screen.getByTestId(`index-macro-21d-${sym}`).textContent)
        .toBe(`${p.windows!.ret_21d}d ${p.text!.ret_21d}`);
      const px = read.live_px != null ? `${izPrice(read.live_px)} live` : `${izPrice(read.close)} close`;
      expect(screen.getByTestId(`index-macro-px-${sym}`).textContent).toBe(px);
      const view = izView(read, izDefaultRes(read, AFTER.default_resolution ?? null));
      expect(screen.getByTestId(`index-macro-where-${sym}`).textContent).toBe(izMacroWhere(read, view));
      expect(row.getAttribute('title')).toBe(p.note);
      expect(screen.getByTestId(`index-macro-label-${sym}`).textContent)
        .toBe(IZ_MACRO.find((m) => m.symbol === sym)!.label);
    }
    const text = screen.getByTestId('index-zones').textContent || '';
    expect(text).not.toMatch(/NaN|undefined|null/);
  });

  it('the served band phrase on the captured doc reads as expected (TLT between, UUP above)', () => {
    draw(AFTER);
    expect(screen.getByTestId('index-macro-where-TLT').textContent)
      .toBe('live: between two stored bands, 0.08% from the nearest band');
    expect(screen.getByTestId('index-macro-where-UUP').textContent)
      .toBe('live: above every stored band, 1.38% from the nearest band');
  });
});

/* ── F4: the captured fixture, before the first run ────────────────────────── */

describe('F4 — before_first_run: pending, never blank-as-zero', () => {
  it('every macro row says it is not stored yet and computes overnight', () => {
    draw(BEFORE);
    for (const sym of MACRO_SYMS) {
      const row = screen.getByTestId(`index-macro-${sym}`);
      expect(row.getAttribute('data-state')).toBe('pending');
      const t = screen.getByTestId(`index-macro-pending-${sym}`).textContent || '';
      expect(t).toMatch(/not stored yet/);
      expect(t).toMatch(/computes overnight/);
      // NEGATIVE — no number dressed as a move, and no zero.
      expect(row.textContent).not.toMatch(/\d\s*%|%\s*\d/);
      expect(row.textContent).not.toMatch(/0\.0/);
      expect(screen.queryByTestId(`index-macro-today-${sym}`)).toBeNull();
      expect(row.getAttribute('title')).toBe('');
    }
    // SPY / QQQ are unaffected.
    for (const sym of INDEX_ZONE_SYMBOLS) {
      expect(screen.getByTestId(`index-zone-chart-${sym}`)).toBeTruthy();
      expect(screen.getByTestId(`index-zone-ladder-${sym}`)).toBeTruthy();
    }
  });

  it('a pending row opens to the existing placeholder card', () => {
    draw(BEFORE);
    fireEvent.click(screen.getByTestId('index-macro-toggle-TLT'));
    const card = screen.getByTestId('index-macro-card-TLT');
    expect(within(card).getByTestId('index-zone-empty-TLT')).toBeTruthy();
    expect(within(card).queryByTestId('index-macro-note-TLT')).toBeNull();
  });
});

/* ── F5: expand, one at a time, in the URL ─────────────────────────────────── */

describe('F5 — ?iz_open= opens one row in place, survives reload', () => {
  it('click TLT opens the SAME card; UUP swaps; UUP again closes and drops the param', () => {
    draw(AFTER, '/?tab=zones&universe=full');
    fireEvent.click(screen.getByTestId('index-macro-toggle-TLT'));
    const card = screen.getByTestId('index-macro-card-TLT');
    expect(within(card).getByTestId('index-zone-TLT')).toBeTruthy();
    expect(within(card).getByTestId('index-zone-chart-TLT')).toBeTruthy();
    expect(screen.getByTestId('index-macro-toggle-TLT').getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByTestId('index-macro-toggle-TLT').getAttribute('aria-controls')).toBe('index-macro-card-TLT');
    expect(card.id).toBe('index-macro-card-TLT');
    expect(search().get(IZ_OPEN_PARAM)).toBe('TLT');
    // Every other param rides along.
    expect(search().get('tab')).toBe('zones');
    expect(search().get('universe')).toBe('full');

    fireEvent.click(screen.getByTestId('index-macro-toggle-UUP'));
    expect(screen.queryByTestId('index-macro-card-TLT')).toBeNull();
    expect(screen.getByTestId('index-macro-card-UUP')).toBeTruthy();
    expect(search().get(IZ_OPEN_PARAM)).toBe('UUP');

    fireEvent.click(screen.getByTestId('index-macro-toggle-UUP'));
    expect(screen.queryByTestId('index-macro-card-UUP')).toBeNull();
    expect(search().has(IZ_OPEN_PARAM)).toBe(false);
    expect(search().get('universe')).toBe('full');
  });

  it('reload: ?iz_open=GLD opens GLD on first render', () => {
    draw(AFTER, '/?iz_open=GLD');
    expect(screen.getByTestId('index-macro-card-GLD')).toBeTruthy();
    expect(screen.getByTestId('index-macro-GLD').getAttribute('data-open')).toBe('true');
    expect(screen.queryByTestId('index-macro-card-TLT')).toBeNull();
    expect(screen.queryByTestId('index-macro-card-UUP')).toBeNull();
  });

  it('NEGATIVE: ?iz_open=SPY / XYZ / empty opens nothing and does not throw', () => {
    for (const q of ['/?iz_open=SPY', '/?iz_open=XYZ', '/?iz_open=']) {
      const { unmount } = draw(AFTER, q);
      for (const sym of MACRO_SYMS) expect(screen.queryByTestId(`index-macro-card-${sym}`)).toBeNull();
      // SPY keeps its one card — no second copy under the rows.
      expect(screen.getAllByTestId('index-zone-SPY')).toHaveLength(1);
      unmount();
    }
    expect(izMacroOpen('gld')).toBe('GLD');
    expect(izMacroOpen(' tlt ')).toBe('TLT');
    expect(izMacroOpen('SPY')).toBeNull();
    expect(izMacroOpen('XYZ')).toBeNull();
    expect(izMacroOpen('')).toBeNull();
    expect(izMacroOpen(null)).toBeNull();
  });
});

/* ── F6: today states and the strip phases ─────────────────────────────────── */

describe('F6 — a blank today prints the served dash and carries the served reason', () => {
  const notes: Record<string, string> = {
    basis_behind: 'Today is not read: the stored close is 2026-10-13, not the 2026-10-14 session — the overnight job has not stored that close yet.',
    no_session: 'Today is not read: 2026-10-17 is not a market session.',
    no_print: 'Today is not read: no print dated 2026-10-15 yet.',
  };
  for (const state of ['basis_behind', 'no_session', 'no_print'] as const) {
    it(`${state}: today cell is "today —", the title is the served note`, () => {
      const read = unit('TLT', '2026-10-14', prog({
        today_state: state, today_pct: null, today_prev_close: null,
        text: { today: '—', ret_5d: '+1.5%', ret_21d: '−2.3%' }, note: notes[state],
      }));
      draw({ date: '2026-10-15', as_of: '2026-10-14', indexes: { TLT: read } });
      expect(screen.getByTestId('index-macro-today-TLT').textContent).toBe('today —');
      expect(screen.getByTestId('index-macro-TLT').getAttribute('title')).toBe(notes[state]);
      expect(screen.getByTestId('index-macro-TLT').textContent).not.toMatch(/\+0\.0%/);
    });
  }

  it('NEGATIVE: a missing text never becomes a formatted number', () => {
    const read = unit('TLT', '2026-10-14', prog({ text: null, today_pct: 1.234, ret_5d: 0 }));
    expect(izProgressText(read, 'today')).toBe('—');
    expect(izProgressText(read, 'ret_5d')).toBe('—');
    expect(izProgressText(null, 'ret_21d')).toBe('—');
    expect(izWindowLabel(read, 'ret_5d')).toBe('5d');
    expect(izWindowLabel(unit('TLT', null, prog({ windows: null })), 'ret_21d')).toBe('');
    draw({ indexes: { TLT: read } });
    expect(screen.getByTestId('index-macro-today-TLT').textContent).toBe('today —');
    expect(screen.getByTestId('index-macro-5d-TLT').textContent).toBe('5d —');
    for (const k of ['today', '5d', '21d']) {
      expect(screen.getByTestId(`index-macro-${k}-TLT`).textContent).not.toMatch(/1\.2|0\.0|\d%/);
    }
  });

  it('available:false → the unavailable line with the served reason', () => {
    const read = unit('UUP', null, null, { available: false, reason: 'nothing stored for it' });
    draw({ date: '2026-10-15', indexes: { UUP: read } });
    expect(screen.getByTestId('index-macro-UUP').getAttribute('data-state')).toBe('unavailable');
    expect(screen.getByTestId('index-macro-unavailable-UUP').textContent)
      .toBe('US dollar — no stored structure: nothing stored for it');
    expect(screen.queryByTestId('index-macro-today-UUP')).toBeNull();
  });

  it('loading: its own copy while the strip request is in flight', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
    draw(undefined);
    for (const sym of MACRO_SYMS) {
      expect(screen.getByTestId(`index-macro-loading-${sym}`).textContent)
        .toBe(`Reading the stored structure for ${sym}…`);
      expect(screen.queryByTestId(`index-macro-pending-${sym}`)).toBeNull();
    }
  });

  it('error: a request failure, not an empty store', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline'); }));
    draw(undefined);
    await waitFor(() => expect(screen.getByTestId('index-macro-error-TLT')).toBeTruthy());
    expect(screen.getByTestId('index-macro-error-TLT').textContent)
      .toBe('Could not load TLT — a request failure, not an empty store.');
    expect(screen.queryByTestId('index-macro-pending-TLT')).toBeNull();
  });

  it('izMacroState names five facts (negative on each boundary)', () => {
    expect(izMacroState(unit('TLT', 'x', null), 'read')).toBe('read');
    expect(izMacroState(unit('TLT', 'x', null, { available: false }), 'read')).toBe('unavailable');
    expect(izMacroState(undefined, 'read')).toBe('pending');
    expect(izMacroState(null, 'empty')).toBe('pending');
    expect(izMacroState(undefined, 'loading')).toBe('loading');
    expect(izMacroState(undefined, 'error')).toBe('error');
  });
});

/* ── F7: wording ───────────────────────────────────────────────────────────── */

describe('F7 — NEGATIVE: the rows say nothing that reads as advice or a forecast', () => {
  const banned = [
    /bounce/i, /forecast/i, /predict/i, /\bwill\b/i, /\bshould\b/i, /\bbuy\b/i, /\bsell\b/i,
    /\bentry\b/i, /\btarget\b/i, /\bedge\b/i, /win rate/i,
  ];
  for (const [name, doc] of [['after', AFTER], ['before', BEFORE]] as const) {
    it(`${name}_first_run, collapsed and with a row open`, () => {
      const { unmount } = draw(doc);
      const collapsed = screen.getByTestId('index-macro').textContent || '';
      for (const re of banned) expect(collapsed).not.toMatch(re);
      unmount();
      draw(doc, '/?iz_open=GLD');
      const open = screen.getByTestId('index-macro').textContent || '';
      for (const re of banned) expect(open).not.toMatch(re);
    });
  }
});

/* ── F8: pinned on ChartMaps ───────────────────────────────────────────────── */

function stubBoard(payload: unknown) {
  return vi.fn(async (url: string) => {
    if (String(url).includes('/supply-demand/index-zones')) {
      return { ok: false, status: 404, json: async () => ({}) } as Response;
    }
    const tab = new URL(url, 'http://x').searchParams.get('tab');
    if (tab === 'zones') return { ok: true, status: 200, json: async () => payload } as Response;
    return { ok: true, status: 200, json: async () => ({ tab, count: 0, tiles: [] }) } as Response;
  });
}

describe('F8 — the rows ride the strip on Chart Maps ▸ Back in Demand', () => {
  it('?tab=zones with the captured payload draws the three rows', async () => {
    vi.stubGlobal('fetch', stubBoard({ tab: 'zones', count: 0, tiles: [], index_zones: AFTER }));
    render(<MemoryRouter initialEntries={['/chart-maps?tab=zones']}><ChartMaps /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('index-macro')).toBeTruthy());
    await waitFor(() => expect(screen.getByTestId('index-macro-TLT').getAttribute('data-state')).toBe('read'));
    for (const sym of MACRO_SYMS) expect(screen.getByTestId(`index-macro-${sym}`)).toBeTruthy();
  });

  it('NEGATIVE: ?tab=vcp draws no macro rows', async () => {
    vi.stubGlobal('fetch', stubBoard({ tab: 'zones', count: 0, tiles: [], index_zones: AFTER }));
    render(<MemoryRouter initialEntries={['/chart-maps?tab=vcp']}><ChartMaps /></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole('tab', { name: /Strong VCP/ })).toBeTruthy());
    expect(screen.queryByTestId('index-macro')).toBeNull();
  });
});

/* ── F9: the per-row date ──────────────────────────────────────────────────── */

describe('F9 — a row on another session prints "through {date}"', () => {
  it('UUP stored through 2026-09-01 under a 2026-10-14 header says so; TLT does not', () => {
    const tlt = unit('TLT', '2026-10-14', prog());
    const uup = unit('UUP', '2026-09-01', prog({
      through: '2026-09-01', today_state: 'basis_behind', today_pct: null, today_prev_close: null,
      text: { today: '—', ret_5d: '+0.3%', ret_21d: '+3.2%' },
    }));
    draw({ date: '2026-10-15', as_of: '2026-10-14', indexes: { TLT: tlt, UUP: uup } });
    const cell = screen.getByTestId('index-macro-through-UUP');
    expect(cell.textContent).toBe('through 2026-09-01');
    expect(screen.getByTestId('index-macro-toggle-UUP').contains(cell)).toBe(true);
    expect(screen.queryByTestId('index-macro-through-TLT')).toBeNull();
    expect(screen.getByTestId('index-macro-today-UUP').textContent).toBe('today —');
  });

  it('on both captured docs, the cell appears iff the row date differs from the payload as_of', () => {
    for (const doc of [AFTER, BEFORE]) {
      const { unmount } = draw(doc);
      for (const sym of MACRO_SYMS) {
        const read = doc.indexes?.[sym];
        const t = read?.progress?.through;
        const own = (typeof t === 'string' && t) ? t : (read?.as_of || null);
        const want = Boolean(read && own && doc.as_of && own !== doc.as_of);
        expect(Boolean(screen.queryByTestId(`index-macro-through-${sym}`))).toBe(want);
      }
      unmount();
    }
  });

  it('NEGATIVES: no progress, no payload as_of, an empty through — no cell, never "null"/"undefined"', () => {
    expect(izMacroThrough(unit('TLT', '2026-10-14', null), '2026-10-14')).toBeNull();
    expect(izMacroThrough(unit('TLT', '2026-10-14', prog()), null)).toBeNull();
    expect(izMacroThrough(unit('TLT', '2026-10-14', prog()), undefined)).toBeNull();
    expect(izMacroThrough(unit('TLT', '2026-10-14', prog()), '')).toBeNull();
    expect(izMacroThrough(unit('TLT', '2026-10-14', prog({ through: '' })), '2026-10-14')).toBeNull();
    expect(izMacroThrough(unit('TLT', null, prog({ through: null })), '2026-10-14')).toBeNull();
    expect(izMacroThrough(undefined, '2026-10-14')).toBeNull();
    // A null progress falls back to the read's own as_of.
    expect(izMacroThrough(unit('TLT', '2026-09-01', null), '2026-10-14')).toBe('through 2026-09-01');
    // An empty through is missing too: it falls back to the read's own as_of, like a null one.
    expect(izMacroThrough(unit('TLT', '2026-09-01', prog({ through: '' })), '2026-10-14')).toBe('through 2026-09-01');
    draw({ as_of: null, indexes: { TLT: unit('TLT', '2026-09-01', prog({ through: '2026-09-01' })) } });
    expect(screen.queryByTestId('index-macro-through-TLT')).toBeNull();
    expect(screen.getByTestId('index-macro').textContent).not.toMatch(/null|undefined/);
  });
});

/* ── F10: the opened row draws the served note ─────────────────────────────── */

describe('F10 — the opened row shows the served note before the card', () => {
  it('click TLT → the note is the served progress.note, inside the card, before index-zone-TLT', () => {
    draw(AFTER);
    for (const sym of MACRO_SYMS) expect(screen.queryByTestId(`index-macro-note-${sym}`)).toBeNull();
    fireEvent.click(screen.getByTestId('index-macro-toggle-TLT'));
    const card = screen.getByTestId('index-macro-card-TLT');
    const note = within(card).getByTestId('index-macro-note-TLT');
    expect(note.textContent).toBe(AFTER.indexes!.TLT!.progress!.note);
    const zone = within(card).getByTestId('index-zone-TLT');
    // eslint-disable-next-line no-bitwise
    expect(note.compareDocumentPosition(zone) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByTestId('index-macro-note-UUP')).toBeNull();
  });

  it('NEGATIVE: progress null or an empty note draws no note element', () => {
    for (const p of [null, prog({ note: '' })]) {
      const { unmount } = draw({ indexes: { TLT: unit('TLT', '2026-10-14', p) } }, '/?iz_open=TLT');
      expect(screen.getByTestId('index-macro-card-TLT')).toBeTruthy();
      expect(screen.queryByTestId('index-macro-note-TLT')).toBeNull();
      expect(screen.getByTestId('index-macro-card-TLT').textContent).not.toMatch(/undefined/);
      unmount();
    }
  });
});

/* ── izMacroWhere: served fields only ──────────────────────────────────────── */

describe('izMacroWhere — the band phrase, from served fields only', () => {
  const band = { kind: 'demand' as const, lo: 49, hi: 51, side: 'in' as const, dist_pct: 0 };
  it('live branches, then the closed close against its nearest band', () => {
    const r = unit('GLD', '2026-10-14', null);
    expect(izMacroWhere({ ...r, live_px: 50, live_in_band: band, live_side: 'in' }, {}))
      .toBe('live: in the demand band 49.00 – 51.00');
    expect(izMacroWhere({ ...r, live_px: 50, live_side: 'below', live_dist_pct: -1.5 }, {}))
      .toBe('live: below every stored band, 1.50% from the nearest band');
    expect(izMacroWhere(r, { in_band: band })).toBe('at the 2026-10-14 close: inside a demand band 49.00 – 51.00');
    expect(izMacroWhere(r, {
      ceiling: { lo: 52, hi: 53, dist_pct: 2.1, kind: 'supply' },
      floor: { lo: 47, hi: 48, dist_pct: 0.9, kind: 'demand' },
    })).toBe('at the 2026-10-14 close: nearest band 0.90% below (demand)');
    expect(izMacroWhere(r, { ceiling: { lo: 52, hi: 53, dist_pct: 0.4, kind: 'supply' } }))
      .toBe('at the 2026-10-14 close: nearest band 0.40% above (supply)');
  });
  it('NEGATIVE: nothing served → "no stored band", never a number and never "edge"', () => {
    const r = unit('GLD', null, null);
    expect(izMacroWhere(r, {})).toBe('at the close: no stored band');
    expect(izMacroWhere({ ...r, live_px: null, live_side: 'above' }, {})).toBe('at the close: no stored band');
    expect(izMacroWhere({ ...r, live_px: 50, live_side: 'above' }, {}))
      .toBe('live: above every stored band, — from the nearest band');
    expect(izMacroWhere(r, {})).not.toMatch(/\bedge\b/);
  });
});
