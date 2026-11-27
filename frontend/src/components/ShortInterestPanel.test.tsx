import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ShortInterestPanel } from './ShortInterestPanel';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetRulesInfoCache } from '../hooks/useRulesInfo';
import { SI_NOT_WARMED_TEXT, SI_REQUEST_FAILED_TEXT } from '../lib/shortInterest';

/* 🩳 ShortInterestPanel — the ticker page's full read (Ajay 2026-10-03: "also
 * the individual tickers please"). Served rows in order; the explainer is the
 * ℹ️ rules section; nothing computed here. */

const ROWS = [
  { k: 'Settlement', v: '2026-09-15 (FINRA; published ~2026-09-24)' },
  { k: 'Shares short', v: '120,015,346 · +7.8% vs 2026-08-31 (111,323,398)' },
  { k: '% of float', v: '33.6% — float 357,328,674 (yfinance floatShares (shares_cache), as of 2026-09-04)' },
  { k: '% of shares outstanding', v: '33.2% — 361,687,337 (yfinance sharesOutstanding (shares_cache), as of 2026-09-04)' },
  { k: 'Days to cover', v: "4.13 — shares short ÷ 29,047,980 average daily volume (the provider's window)" },
  { k: 'Freshness', v: 'current — next settlement 2026-09-30, due ~2026-10-13' },
  { k: 'Source', v: 'FINRA short interest (Rule 4560) via Massive /stocks/v1/short-interest' },
];
const MISS_ROW = { k: 'Short interest', v: 'not read — no FINRA record at the last warm' };
const ITEMS: Record<string, unknown> = {
  EOSE: { symbol: 'EOSE', status: 'ok', chip: '🩳 SI 33.6% float · 4.1d · 9/15', title: 't', rows: ROWS },
  MISS: { symbol: 'MISS', status: 'no_record', chip: null, title: 'no record', rows: [MISS_ROW] },
  POM: { symbol: 'POM', status: 'ok', chip: '🩳 served pom chip', title: 't', rows: ROWS,
    basis: { status: 'ok', pending: false, issuances: [
      { form: '6-K', filed: '2026-11-04', url: 'https://www.sec.gov/Archives/edgar/data/1877971/000121390026116021/ea0310863-6k_pomdoctor.htm',
        label: 'served 6-K 11/4 filing', text: 'served pom issuance text' },
      { form: '6-K', filed: '2026-10-01', url: 'https://www.sec.gov.evil.com/Archives/edgar/data/1/x/y.htm', label: 'served evil label', text: 'x' },
      { form: '6-K', filed: '2026-09-01', url: null, label: 'served no link label', text: 'y' },
      { form: '6-K', filed: '2026-08-01', url: 'https://www.sec.gov/Archives/edgar/data/1/x/z.htm', label: '', text: 'z' },
    ] } },
  JUNK: { symbol: 'JUNK', status: 'ok', chip: '🩳 served junk chip', title: 't', rows: ROWS,
    basis: { status: 'ok', issuances: [{ url: 'javascript:alert(1)', label: 'served js label' },
      { url: 'http://www.sec.gov/Archives/edgar/data/1/x/y.htm', label: 'served http label' }] } },
  OLD: { symbol: 'OLD', status: 'ok', chip: '🩳 served old chip', title: 't', rows: ROWS, basis: { status: 'ok', issuances: 'x' } },
};
const PICKS = ['What it is: shares sold short and not yet bought back.', 'Not a forecast. UNMEASURED on this app’s universe.'];

function stub({ si = true, rules = true }: { si?: boolean | 'hang'; rules?: boolean } = {}) {
  const f = vi.fn((url: string) => {
    const u = String(url);
    if (u.includes('/short-interest/map')) {
      if (si === 'hang') return new Promise<Response>(() => {});
      if (!si) return Promise.reject(new Error('down'));
      const q = decodeURIComponent(u.split('symbols=')[1] || '').split(',');
      const items: Record<string, unknown> = {};
      for (const s of q) if (ITEMS[s]) items[s] = ITEMS[s];
      return Promise.resolve({ ok: true, json: async () => ({ items, n: 1, max_symbols: 200 }) } as unknown as Response);
    }
    if (u.includes('/supply-demand/rules')) {
      if (!rules) return Promise.resolve({ ok: false, status: 500, json: async () => ({}) } as unknown as Response);
      return Promise.resolve({ ok: true, json: async () => ({ sections: { short_interest: {
        title: 'Short interest', emoji: '🩳', picks: PICKS, stops: [], alerts: [], note: 'n' } } }) } as unknown as Response);
    }
    return Promise.reject(new Error(`unexpected ${u}`));
  });
  vi.stubGlobal('fetch', f);
  return f;
}

describe('ShortInterestPanel', () => {
  beforeEach(() => { _resetShortInterestCache(); _resetRulesInfoCache(); });
  afterEach(() => vi.unstubAllGlobals());

  it('renders the served rows in order and the explainer from the rules section', async () => {
    stub();
    render(<ShortInterestPanel symbol="eose" />);
    const panel = await screen.findByTestId('si-panel');
    expect(panel.textContent).toContain('🩳 Short interest');
    const ks = Array.from(panel.querySelectorAll('dt')).map((e) => e.textContent);
    const vs = Array.from(panel.querySelectorAll('dd')).map((e) => e.textContent);
    expect(ks).toEqual(ROWS.map((r) => r.k));
    expect(vs).toEqual(ROWS.map((r) => r.v));
    await waitFor(() => expect(panel.querySelector('details summary')?.textContent).toBe('What this number is (and is not)'));
    expect(Array.from(panel.querySelectorAll('details li')).map((e) => e.textContent)).toEqual(PICKS);
  });

  it('NEGATIVE: not loaded → nothing', async () => {
    stub({ si: 'hang' });
    const { container } = render(<ShortInterestPanel symbol="EOSE" />);
    await new Promise((r) => setTimeout(r, 120));
    expect(container.innerHTML).toBe('');
  });

  it('NEGATIVE: loaded and absent → the not-read line, never a number', async () => {
    stub();
    render(<ShortInterestPanel symbol="NOPE" />);
    const panel = await screen.findByTestId('si-panel');
    expect(panel.textContent).toContain(SI_NOT_WARMED_TEXT);
    expect(panel.querySelector('dl')).toBeNull();
    expect(panel.textContent?.replace(SI_NOT_WARMED_TEXT, '')).not.toMatch(/\d/);
  });

  it('NEGATIVE: no_record → its single served row, no numbers', async () => {
    stub();
    render(<ShortInterestPanel symbol="MISS" />);
    const panel = await screen.findByTestId('si-panel');
    expect(Array.from(panel.querySelectorAll('dt')).map((e) => e.textContent)).toEqual([MISS_ROW.k]);
    expect(Array.from(panel.querySelectorAll('dd')).map((e) => e.textContent)).toEqual([MISS_ROW.v]);
    expect(panel.querySelector('dl')?.textContent).not.toMatch(/\d/);
  });

  it('NEGATIVE: the rules fetch fails → the rows still render and no explainer shows', async () => {
    const f = stub({ rules: false });
    render(<ShortInterestPanel symbol="EOSE" />);
    const panel = await screen.findByTestId('si-panel');
    await waitFor(() => expect(f.mock.calls.some((c) => String(c[0]).includes('/supply-demand/rules'))).toBe(true));
    await new Promise((r) => setTimeout(r, 0));
    expect(panel.querySelectorAll('dt')).toHaveLength(ROWS.length);
    expect(panel.querySelector('details')).toBeNull();
  });

  it('NEGATIVE: the short-interest fetch fails → "request failed", never "no record" (no crash, no zero)', async () => {
    stub({ si: false });
    render(<ShortInterestPanel symbol="EOSE" />);
    const panel = await screen.findByTestId('si-panel');
    expect(panel.textContent).toContain(SI_REQUEST_FAILED_TEXT);
    expect(panel.textContent).not.toContain(SI_NOT_WARMED_TEXT);
    expect(panel.querySelector('dl')).toBeNull();
    expect(panel.textContent?.replace(SI_REQUEST_FAILED_TEXT, '').replace(/What this number is[\s\S]*$/, '')).not.toMatch(/\d/);
  });

  it('🩳 2026-11-26: the served 6-K issuance → a link under the rows, new tab, rel noopener noreferrer, the served label', async () => {
    stub();
    render(<ShortInterestPanel symbol="POM" />);
    const panel = await screen.findByTestId('si-panel');
    const list = await screen.findByTestId('si-issuances');
    expect(panel.querySelector('dl')!.compareDocumentPosition(list) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const links = [...list.querySelectorAll('a')];
    expect(links.map((a) => a.textContent)).toEqual(['served 6-K 11/4 filing']);
    const a = links[0];
    expect(a.getAttribute('href')).toBe('https://www.sec.gov/Archives/edgar/data/1877971/000121390026116021/ea0310863-6k_pomdoctor.htm');
    expect(a.getAttribute('target')).toBe('_blank');
    expect(a.getAttribute('rel')).toBe('noopener noreferrer');
    expect(a.getAttribute('title')).toBe('served pom issuance text');
    // NEGATIVE: a look-alike host, no link, an empty label → nothing printed for them
    expect(panel.textContent).not.toMatch(/served evil label|served no link label/);
    expect(panel.querySelectorAll('a')).toHaveLength(1);
  });

  it('NEGATIVE: no issuance with a good link (javascript: / http:// / non-array / none) → the panel is unchanged', async () => {
    stub();
    const base = render(<ShortInterestPanel symbol="EOSE" />);
    await screen.findByTestId('si-panel');
    await waitFor(() => expect(base.container.querySelector('details')).not.toBeNull());
    const html = base.container.innerHTML.replace(/EOSE/g, '');
    base.unmount();
    expect(html).not.toMatch(/si-issuances/);
    for (const sym of ['JUNK', 'OLD']) {
      const r = render(<ShortInterestPanel symbol={sym} />);
      await screen.findByTestId('si-panel');
      await waitFor(() => expect(r.container.querySelector('details')).not.toBeNull());
      expect(r.container.querySelector('[data-testid="si-issuances"], a'), sym).toBeNull();
      expect(r.container.innerHTML.replace(new RegExp(sym, 'g'), ''), sym).toBe(html);
      r.unmount();
    }
  });

  it('NEGATIVE: loaded and absent is "no record", never "request failed"', async () => {
    stub();
    render(<ShortInterestPanel symbol="NOPE" />);
    const panel = await screen.findByTestId('si-panel');
    expect(panel.textContent).not.toContain(SI_REQUEST_FAILED_TEXT);
  });
});
