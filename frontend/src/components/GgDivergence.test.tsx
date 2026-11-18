import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

/* 🧨 GgDivergencePanel + GgDivergenceTrack (2026-11-18, divergence spec §3.8 / WP-C). Ajay: "yes should do a track recird
 * fir the divergence aftger EMA 9 Cross over bullish". Every string below is a SENTINEL ("served …") — the components type
 * no word, so every assertion compares the DOM to the served value. NEGATIVES: a NaN / undefined / number text prints
 * nothing; never both OOS lines; an absent block / fold prints nothing; no rule / unit word typed in the source. */

vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({ PatternChart: () => <div /> }));

import { GgDivergencePanel, GgDivergenceTrack } from './GgDivergence';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const clone = (x: any) => JSON.parse(JSON.stringify(x));

const DV_BLOCK = {
  title: 'served dv title', ask_text: 'served his words', rule_label: 'served rule label', rule_text: 'served rule text',
  honesty: 'served honesty',
  is_line: { rth: { text: 'served IS rth line', n: 56 }, ah: { text: 'served IS ah line', n: 32 } },
  oos_text: 'served oos text', oos_sessions: ['2026-11-17'], oos_spec_sha256: 'abc', oos_done_n: 1, oos_sealed: true,
  oos_seal_et: '2026-11-30 20:00', cohort_text: 'served cohort', window_text: 'served window', n_today: 2, n_open: 1,
  n_exited: 1, empty_text: 'served empty', order_note: 'served order note', chartless: [], faults_text: null,
  track_record: null, track_record_fault_text: null,
};
const cell = (state: string, text: string) => ({ state, text });
const row = (key: string, sym: string, bucket: string, extra: Record<string, unknown> = {}) => ({
  key, id: key, date: '2026-11-18', symbol: sym, window: 'rth', window_text: `served window ${sym}`, at_et: '10:05',
  at_text: `served at ${sym}`, ring_text: `served ring ${sym}`, entry: cell('ok', `served entry ${sym}`),
  exit: cell('ok', `served exit ${sym}`), gross: cell(bucket, `served gross ${sym}`), net: cell(bucket, `served net ${sym}`),
  bucket, bucket_text: `served bucket ${bucket}`, flag_text: bucket === 'win' || bucket === 'loss' ? `served flag ${sym}` : null,
  href: null, ...extra,
});
const DV_TRACK = {
  title: 'served fold title', span: 'today', spans: [{ key: 'today', label: 'served Today' }, { key: '10d', label: 'served 10d' }],
  heads: [{ key: 'symbol', label: 'served Ticker' }, { key: 'window', label: 'served Window' }, { key: 'at', label: 'served Listed' },
    { key: 'ring', label: 'served Rang' }, { key: 'entry', label: 'served Entry' }, { key: 'exit', label: 'served Exit' },
    { key: 'gross', label: 'served Gross' }, { key: 'net', label: 'served Net' }],
  days: [{ date: '2026-11-18', label: 'served day label', rows: [
    row('L1', 'AAA', 'loss'), row('W1', 'BBB', 'win'),
    row('D1', 'AAA', 'loss', { dup_of: 'L1', dup_text: 'served dup chip', flag_text: null }),
  ] }],
  counts_text: { rth: 'served counts rth', ah: 'served counts ah' },
  oos_progress_text: 'served oos progress', is_text: 'served is text',
  categories: [{ key: 'all', text: 'served all 3', n: 3 }, { key: 'win', text: 'served win 1', n: 1 },
    { key: 'loss', text: 'served loss 1', n: 1 }],
  category_param: 'cat', category_empty_text: 'served cat empty',
  sorts: [{ key: 'served', label: 'served order', bucket_sort: false }, { key: 'wins', label: 'served wins first', bucket_sort: true }],
  sort_param: 'sort', sort_default: 'served', bucket_order: ['win', 'loss', 'open', 'flat', 'out'],
  grade_at_et: '20:15', today_text: 'served today text', empty_text: 'served fold empty', more_text: 'served more',
  rule_text: 'served fold rule', honesty: 'served fold honesty',
};

let lastSearch = '';
function Probe() { lastSearch = useLocation().search; return null; }
const at = (q = '') => ({ wrapper: ({ children }: any) => (
  <MemoryRouter initialEntries={[`/chart-maps?tab=gajjala&sub=divergence${q}`]}>{children}<Probe /></MemoryRouter>) });

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🧨 GgDivergencePanel', () => {
  it('prints title / his words / IS rth + ah / oos / cohort / window / order verbatim; honesty LAST; rule fold closed', () => {
    render(<GgDivergencePanel block={clone(DV_BLOCK)} />, at());
    expect(screen.getByTestId('gg-dv-title').tagName).toBe('H3');
    expect(screen.getByTestId('gg-dv-title').textContent).toBe('served dv title');
    expect(screen.getByTestId('gg-dv-ask').tagName).toBe('BLOCKQUOTE');
    expect(screen.getByTestId('gg-dv-ask').textContent).toBe('served his words');
    expect(screen.getByTestId('gg-dv-is-rth').textContent).toBe('served IS rth line');
    expect(screen.getByTestId('gg-dv-is-ah').textContent).toBe('served IS ah line');
    expect(screen.getByTestId('gg-dv-oos').textContent).toBe('served oos text');
    expect(screen.getByTestId('gg-dv-cohort').textContent).toBe('served cohort');
    expect(screen.getByTestId('gg-dv-window').textContent).toBe('served window');
    expect(screen.getByTestId('gg-dv-order').textContent).toBe('served order note');
    const rule = screen.getByTestId('gg-dv-rule') as HTMLDetailsElement;
    expect(rule.open).toBe(false);
    expect(rule.querySelector('summary')!.textContent).toBe('served rule label');
    expect(rule.textContent).toContain('served rule text');
    const sec = screen.getByTestId('gg-dv');
    expect(sec.lastElementChild).toBe(screen.getByTestId('gg-dv-honesty'));
    expect(screen.getByTestId('gg-dv-honesty').textContent).toBe('served honesty');
    // NEGATIVE: n_today > 0 → no empty line
    expect(screen.queryByTestId('gg-dv-empty')).toBeNull();
  });

  it('chartless lines + faults_text print when served (served words only); NEGATIVE: nothing when absent', () => {
    const b = clone(DV_BLOCK);
    b.chartless = [{ symbol: 'ZZZ', at_text: '10:05 ET', state_label: 'served chartless ZZZ', href: '/chart-maps?tab=gajjala&focus=ZZZ' },
      { symbol: 'YYY', at_text: '10:10 ET', state_label: 'served chartless YYY', href: 'https://evil.example' }];
    b.faults_text = 'served faults';
    const { unmount } = render(<GgDivergencePanel block={b} />, at());
    expect(screen.getByTestId('gg-dv-chartless-ZZZ').textContent).toBe('served chartless ZZZ');
    expect(screen.getByTestId('gg-dv-chartless-ZZZ').querySelector('a')).toBeTruthy();
    // NEGATIVE: an href that is not an in-app path → text, no link
    expect(screen.getByTestId('gg-dv-chartless-YYY').querySelector('a')).toBeNull();
    expect(screen.getByTestId('gg-dv-faults').textContent).toBe('served faults');
    unmount();
    render(<GgDivergencePanel block={clone(DV_BLOCK)} />, at());
    expect(screen.queryByTestId(/^gg-dv-chartless-/)).toBeNull();
    expect(screen.queryByTestId('gg-dv-faults')).toBeNull();
  });

  it('the served empty line prints when the served n_today is 0; NEGATIVE: not otherwise', () => {
    const b = { ...clone(DV_BLOCK), n_today: 0 };
    render(<GgDivergencePanel block={b} />, at());
    expect(screen.getByTestId('gg-dv-empty').textContent).toBe('served empty');
  });

  it('NEGATIVE: NaN / undefined / number / empty texts print nothing (never "NaN" / "undefined")', () => {
    const b: any = clone(DV_BLOCK);
    b.title = NaN; b.ask_text = undefined; b.oos_text = 42; b.cohort_text = '  '; b.is_line = { rth: { text: NaN }, ah: null };
    b.honesty = null; b.rule_text = undefined; b.chartless = [{ symbol: 'X', state_label: NaN }, null, 'junk'];
    b.faults_text = NaN;
    const { container } = render(<GgDivergencePanel block={b} />, at());
    for (const tid of ['gg-dv-title', 'gg-dv-ask', 'gg-dv-oos', 'gg-dv-cohort', 'gg-dv-is-rth', 'gg-dv-is-ah', 'gg-dv-honesty',
      'gg-dv-rule', 'gg-dv-faults', 'gg-dv-chartless-X']) expect(screen.queryByTestId(tid), tid).toBeNull();
    expect(container.textContent).not.toMatch(/NaN|undefined|null|42/);
  });

  it('NEGATIVE: a null / absent block (an older API) draws nothing', () => {
    for (const b of [null, undefined]) {
      const { container, unmount } = render(<GgDivergencePanel block={b as any} />, at());
      expect(container.innerHTML).toBe('');
      unmount();
    }
  });
});

describe('🧨 GgDivergenceTrack — the 🏁 fold', () => {
  it('an open fold: served title, heads in served order, rows with their served cells, flags, dup chip, lines', () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    render(<GgDivergenceTrack tr={clone(DV_TRACK)} />, at());
    const fold = screen.getByTestId('gg-dv-tr') as HTMLDetailsElement;
    expect(fold.tagName).toBe('DETAILS');
    expect(fold.open).toBe(true);
    expect(screen.getByTestId('gg-dv-tr-title').textContent).toBe('served fold title');
    const ths = [...fold.querySelectorAll('thead th')].map((t) => t.textContent);
    expect(ths).toEqual(DV_TRACK.heads.map((h) => h.label));   // no Tape column (views null)
    expect(screen.getByTestId('gg-tr-net-L1').textContent).toBe('served net AAA');
    expect(screen.getByTestId('gg-tr-gross-W1').textContent).toBe('served gross BBB');
    expect(screen.getByTestId('gg-tr-entry-W1').textContent).toBe('served entry BBB');
    // the served window / ring words print in their columns (verbatim)
    expect(screen.getByTestId('gg-tr-window-W1').textContent).toBe('served window BBB');
    expect(screen.getByTestId('gg-tr-ring-W1').textContent).toBe('served ring BBB');
    expect(screen.getByTestId('gg-tr-flag-W1').textContent).toBe('served flag BBB');
    expect(screen.getByTestId('gg-tr-flag-L1').textContent).toBe('served flag AAA');
    expect(screen.getByTestId('gg-tr-dup-D1').textContent).toBe('served dup chip');
    expect(screen.queryByTestId('gg-tr-flag-D1')).toBeNull();
    expect(screen.getByTestId('gg-dv-tr-counts-rth').textContent).toBe('served counts rth');
    expect(screen.getByTestId('gg-dv-tr-counts-ah').textContent).toBe('served counts ah');
    expect(screen.getByTestId('gg-dv-tr-oos-progress').textContent).toBe('served oos progress');
    expect(screen.queryByTestId('gg-dv-tr-oos-counts')).toBeNull();
    expect(screen.getByTestId('gg-dv-tr-is').textContent).toBe('served is text');
    expect(screen.getByTestId('gg-dv-tr-day-2026-11-18').textContent).toBe('served day label');
    expect(fold.lastElementChild).toBe(screen.getByTestId('gg-dv-tr-honesty'));
    expect(screen.getByTestId('gg-dv-tr-row-W1').closest('.gg-tr-scroll')).toBeTruthy();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('oos_counts_text prints when served (after the seal) — as handed, never composed; never both', () => {
    const tr: any = clone(DV_TRACK);
    delete tr.oos_progress_text;
    tr.oos_counts_text = 'served oos counts';
    const { unmount } = render(<GgDivergenceTrack tr={tr} />, at());
    expect(screen.getByTestId('gg-dv-tr-oos-counts').textContent).toBe('served oos counts');
    expect(screen.queryByTestId('gg-dv-tr-oos-progress')).toBeNull();
    unmount();
    // NEGATIVE: both served (a backend slip) → ONE line only
    const both: any = { ...clone(DV_TRACK), oos_counts_text: 'served oos counts' };
    const { container } = render(<GgDivergenceTrack tr={both} />, at());
    expect(container.querySelectorAll('[data-testid^="gg-dv-tr-oos-"]')).toHaveLength(1);
    // NEGATIVE: neither served → no line
  });

  it('a cat chip filters FE-only (no fetch); sort chips reorder FE-only; a span chip writes `span`', () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    render(<GgDivergenceTrack tr={clone(DV_TRACK)} />, at());
    fireEvent.click(screen.getByTestId('gg-tr-cat-win'));
    expect(lastSearch).toContain('cat=win');
    expect(screen.getByTestId('gg-dv-tr-row-W1')).toBeTruthy();
    expect(screen.queryByTestId('gg-dv-tr-row-L1')).toBeNull();
    expect(screen.queryByTestId('gg-dv-tr-row-D1')).toBeNull();
    fireEvent.click(screen.getByTestId('gg-tr-cat-all'));
    expect(lastSearch).not.toContain('cat=');
    const order = () => [...document.querySelectorAll('[data-testid^="gg-dv-tr-row-"]')].map((r) => r.getAttribute('data-testid'));
    expect(order()).toEqual(['gg-dv-tr-row-L1', 'gg-dv-tr-row-W1', 'gg-dv-tr-row-D1']);
    fireEvent.click(screen.getByTestId('gg-tr-sort-wins'));
    expect(lastSearch).toContain('sort=wins');
    expect(order()).toEqual(['gg-dv-tr-row-W1', 'gg-dv-tr-row-L1', 'gg-dv-tr-row-D1']);
    fireEvent.click(screen.getByTestId('gg-dv-tr-span-10d'));
    expect(lastSearch).toContain('span=10d');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('a cat chip with no row left → the served category empty line', () => {
    const tr: any = clone(DV_TRACK);
    tr.categories = [...tr.categories, { key: 'open', text: 'served open 0', n: 0 }];
    render(<GgDivergenceTrack tr={tr} />, at('&cat=open'));
    expect(screen.getByTestId('gg-dv-tr-cat-empty').textContent).toBe('served cat empty');
  });

  it('NEGATIVE: tr null + a served fault line → that line only; neither → nothing', () => {
    const { unmount } = render(<GgDivergenceTrack tr={null} faultText="served fold fault" />, at());
    expect(screen.getByTestId('gg-dv-tr-fault').textContent).toBe('served fold fault');
    expect(screen.queryByTestId('gg-dv-tr')).toBeNull();
    unmount();
    for (const f of [null, undefined, NaN, '']) {
      const { container, unmount: u } = render(<GgDivergenceTrack tr={null} faultText={f as any} />, at());
      expect(container.innerHTML).toBe('');
      u();
    }
  });

  it('NEGATIVE: NaN / undefined texts in the fold print nothing; no days → the served empty line', () => {
    const tr: any = clone(DV_TRACK);
    tr.days = []; tr.counts_text = { rth: NaN, ah: undefined }; tr.oos_progress_text = NaN; tr.is_text = undefined;
    tr.honesty = 7; tr.more_text = null; tr.today_text = undefined; tr.title = NaN;
    const { container } = render(<GgDivergenceTrack tr={tr} />, at());
    expect(screen.getByTestId('gg-dv-tr-empty').textContent).toBe('served fold empty');
    for (const tid of ['gg-dv-tr-counts-rth', 'gg-dv-tr-counts-ah', 'gg-dv-tr-oos-progress', 'gg-dv-tr-oos-counts',
      'gg-dv-tr-is', 'gg-dv-tr-honesty', 'gg-dv-tr-more', 'gg-dv-tr-today']) expect(screen.queryByTestId(tid), tid).toBeNull();
    expect(container.textContent).not.toMatch(/NaN|undefined/);
  });
});

describe('🧨 source guards', () => {
  it('NEGATIVE: GgDivergence.tsx composes no word — no rule / unit / grade word outside comments, ids and class names', async () => {
    const src = await readSource('src/components/GgDivergence.tsx');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '')
      .replace(/data-testid=\{?[`'"][^`'"]*[`'"]\}?/g, '').replace(/className=\{?[`'"][^`'"]*[`'"]\}?/g, '');
    for (const w of [/ATR/, /divergence —/i, /\bnet\b/i, /\bwon\b/i, /\bEMA\b/, /%/, /\bOOS\b/, /\bsealed\b/i, /chart not stored/i,
      /\brecord\b/, /\bRTH\b/, /after hours/i]) expect(code, String(w)).not.toMatch(w);
    // GgTr* imported from the board, never copied
    expect(src).toMatch(/import \{[^}]*GgTrCats[^}]*GgTrHead[^}]*GgTrSorts[^}]*GgTrTapeRow[^}]*ggTrTapeAt[^}]*\} from '\.\/GajjalaBoard'/);
    expect(src).not.toMatch(/function GgTr/);
    expect(src).not.toMatch(/boun/i);
  });
  it('the phone guard: .gg-dv wraps (min-width:0 + overflow-wrap:anywhere)', async () => {
    const css = await readSource('src/styles/gajjala.css');
    const m = /\.gg-dv \{([^}]*)\}/.exec(css);
    expect(m, '.gg-dv rule').toBeTruthy();
    expect(m![1]).toMatch(/min-width:\s*0/);
    expect(m![1]).toMatch(/overflow-wrap:\s*anywhere/);
    expect(css).toMatch(/\.gg-dv-line \{[^}]*overflow-wrap:\s*anywhere/);
  });
});
