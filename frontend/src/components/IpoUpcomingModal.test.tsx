import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { IpoUpcomingModal } from './IpoUpcomingModal';

/* 🗓️ "Coming up" drill-in — the expected-listing fact sheet (2026-09-20).
 *
 * Ajay: "Can you gather similar info about these please like the ticket and
 * make them clicable the onesin IPO tab that are future".
 *
 * The payload below is the MEASURED Amaero (AMRO) shape from the spec: a
 * name-only EDGAR resolution, no price range in the filing, and the revenue
 * and net-loss quotes coming from TWO DIFFERENT TABLES with different units
 * and different periods. That last fact is why these tests exist: one units
 * line printed under both quotes would read "$6,305" and "$(18,378)" as the
 * same scale, which they are not.
 *
 * The negatives are the point of the rest: EDGAR down, EDGAR with no hit, a
 * refused request, a filing that names another symbol, and every field blank
 * — none of which may print NaN, undefined, null or a zero at him. */

const ROW = {
  symbol: 'AMRO', name: 'Amaero Inc.', date: '2026-09-23',
  exchange: 'NASDAQ Global Select', price: '7.06', numberOfShares: 7456500,
  totalSharesValue: 60539323.5, status: 'expected',
};

const NOTE = 'Read off the registration filing on EDGAR and Finnhub’s IPO calendar. '
  + 'Nothing here is measured, nothing here is a signal, nothing here is ranked — and an '
  + 'expected deal is a plan: dates move and deals are withdrawn.';

const PAYLOAD = {
  ok: true,
  symbol: 'AMRO',
  calendar_row: ROW,
  company: {
    name: 'Amaero Inc.', cik: '0002141616', sic: '3390',
    sic_description: 'Miscellaneous Primary Metal Products',
    state: 'DE', fiscal_year_end: '1231',
  },
  filing: {
    form: 'S-1/A', filed: '2026-09-18', accession: '0001193125-26-395150',
    primary_document: 'project_alchemy_-_s-1a_2.htm',
    url: 'https://www.sec.gov/Archives/edgar/data/2141616/000119312526395150/project_alchemy_-_s-1a_2.htm',
    overview: 'We are a leading U.S.-based producer of high-value refractory and titanium '
      + 'alloy spherical metal powders.',
    proposed_symbol_line: 'We have applied to list our common stock on the Nasdaq Global '
      + 'Select Market (the “Nasdaq”) under the symbol “AMRO.”',
    symbol_in_filing: 'AMRO',
    shares_offered_line: 'We are selling 7,456,500 shares of our common stock.',
    price_line: 'The initial public offering price of our common stock will be determined '
      + 'through negotiations between us and the underwriters.',
    underwriters: ['Stifel', 'Baird', 'Lake Street'],
    revenue_line: 'Total revenues from contracts with customers $ 6,305 $ 1,317 $ 4,988 379 %',
    revenue_units_line: '(in thousands)',
    revenue_period_line: 'Year ended December 31, 2025',
    net_loss_line: 'Net loss attributable to stockholders (1) $ (18,378 ) $ (12,725 ) '
      + '$ (13,433 ) $ (8,731 )',
    net_loss_units_line: 'in thousands, except share and per share data',
    net_loss_period_line: 'Six Months ended June 30, 2025',
    extracted_at: '2026-09-20T14:02:11Z',
    parse_note: null,
  },
  headlines: [
    { title: 'Amaero prices IPO at $7.06', url: 'https://example.com/a',
      source: 'Reuters', published: Date.UTC(2026, 8, 19) / 1000 },
    { title: 'Amaero files amended S-1', url: 'https://example.com/b',
      source: 'Bloomberg', published: Date.UTC(2026, 8, 18) / 1000 },
  ],
  headlines_window_days: 7,
  headlines_at: '2026-09-20T14:02:11Z',
  resolution: { method: 'name', query: '"Amaero Inc."', hits: 6, reason: null },
  error: null,
  cached: false,
  resolved_at: '2026-09-20T14:02:11Z',
  sources: {
    edgar_search_url: 'https://efts.sec.gov/LATEST/search-index?q=%22Amaero%20Inc.%22',
    submissions_url: 'https://data.sec.gov/submissions/CIK0002141616.json',
    filing_url: 'https://www.sec.gov/Archives/edgar/data/2141616/000119312526395150/project_alchemy_-_s-1a_2.htm',
  },
  note: NOTE,
};

const okFetch = (body: unknown) =>
  vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve(body) });

const badFetch = (status: number, body: unknown) =>
  vi.fn().mockResolvedValue({ ok: false, status, json: () => Promise.resolve(body) });

const txt = (id: string) => screen.getByTestId(id).textContent || '';

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('IpoUpcomingModal — the header facts', () => {
  it('prints the calendar row while EDGAR is still being read', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    expect(screen.getByTestId('ipo-drill-loading').textContent).toContain('EDGAR');
    const facts = txt('ipo-drill-facts');
    expect(facts).toContain('2026-09-23');
    expect(facts).toContain('NASDAQ Global Select');
    expect(facts).toContain('7.06');
    // verbatim: the share count keeps the feed's own formatting (none)
    expect(facts).toContain('7456500');
    expect(facts).toContain('expected');
    expect(txt('ipo-drill-head')).toContain('Amaero Inc.');
  });

  it('asks the drill-in route with the session cookie', async () => {
    const f = okFetch(PAYLOAD);
    vi.stubGlobal('fetch', f);
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    await screen.findByTestId('ipo-drill-sec-what');
    expect(String(f.mock.calls[0][0])).toContain('/chart-maps/ipo/upcoming/AMRO');
    expect(f.mock.calls[0][1]).toMatchObject({ credentials: 'include' });
  });
});

describe('IpoUpcomingModal — the fact sheet', () => {
  it('renders all six sections', async () => {
    vi.stubGlobal('fetch', okFetch(PAYLOAD));
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    await screen.findByTestId('ipo-drill-sec-what');
    for (const s of ['what', 'deal', 'printed', 'industry', 'headlines', 'sources']) {
      expect(screen.getByTestId(`ipo-drill-sec-${s}`)).toBeTruthy();
    }
  });

  it('prints what they do, the deal and the industry as served', async () => {
    vi.stubGlobal('fetch', okFetch(PAYLOAD));
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    await screen.findByTestId('ipo-drill-sec-what');
    expect(txt('ipo-drill-sec-what')).toContain('refractory and titanium alloy spherical metal powders');
    const deal = txt('ipo-drill-sec-deal');
    expect(deal).toContain('“AMRO.”');
    expect(deal).toContain('We are selling 7,456,500 shares of our common stock.');
    expect(deal).toContain('will be determined through negotiations');
    expect(deal).toContain('Stifel · Baird · Lake Street');
    const ind = txt('ipo-drill-sec-industry');
    expect(ind).toContain('Miscellaneous Primary Metal Products (3390)');
    expect(ind).toContain('DE');
    expect(ind).toContain('1231');
    expect(txt('ipo-drill-sec-printed')).toContain('S-1/A filed 2026-09-18');
  });

  it('gives EACH quote the units and periods of its OWN table', async () => {
    vi.stubGlobal('fetch', okFetch(PAYLOAD));
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    await screen.findByTestId('ipo-drill-quote-revenue');
    const rev = txt('ipo-drill-quote-revenue');
    const net = txt('ipo-drill-quote-net-loss');
    expect(rev).toContain('Total revenues from contracts with customers $ 6,305');
    expect(rev).toContain('(in thousands)');
    expect(rev).toContain('Year ended December 31, 2025');
    expect(net).toContain('Net loss attributable to stockholders (1) $ (18,378 )');
    expect(net).toContain('except share and per share data');
    expect(net).toContain('Six Months ended June 30, 2025');
    // the two tables are DIFFERENT tables — one units line for both is the bug
    expect(rev).not.toContain('Six Months ended June 30, 2025');
    expect(net).not.toContain('Year ended December 31, 2025');
    expect(txt('ipo-drill-sec-printed')).toContain('Nothing here is converted.');
  });

  it('lists the headlines with their dates and the three source links', async () => {
    vi.stubGlobal('fetch', okFetch(PAYLOAD));
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    await screen.findByTestId('ipo-drill-sec-headlines');
    const h = txt('ipo-drill-sec-headlines');
    expect(h).toContain('Amaero prices IPO at $7.06');
    expect(h).toContain('Reuters');
    expect(h).toContain('2026-09-19');
    const src = screen.getByTestId('ipo-drill-sec-sources');
    expect(src.textContent).toContain('EDGAR full-text search');
    expect(src.textContent).toContain('EDGAR submissions');
    expect(src.textContent).toContain('Prospectus');
    expect(src.querySelectorAll('a[rel="noreferrer"]').length).toBe(3);
  });

  it('NEGATIVE: a headline with no url is a title, never a link to "—"', async () => {
    const p = { ...PAYLOAD, headlines: [
      { title: 'Amaero sets terms', url: null, source: 'Renaissance', published: Date.UTC(2026, 8, 19) / 1000 },
      ...PAYLOAD.headlines,
    ] };
    vi.stubGlobal('fetch', okFetch(p));
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    const sec = await screen.findByTestId('ipo-drill-sec-headlines');
    expect(sec.textContent).toContain('Amaero sets terms');
    const hrefs = [...sec.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    expect(hrefs).not.toContain('—');
    expect(hrefs.every((h) => h && h.startsWith('http'))).toBe(true);
    expect(sec.querySelectorAll('a').length).toBe(PAYLOAD.headlines.length);
  });

  it('prints the SERVED note, never one typed into this file', async () => {
    vi.stubGlobal('fetch', okFetch(PAYLOAD));
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    await screen.findByTestId('ipo-drill-note');
    expect(txt('ipo-drill-note')).toBe(NOTE);
  });

  it('NEGATIVE: a ms stamp on a headline prints a blank, not a year-57,000 date', async () => {
    vi.stubGlobal('fetch', okFetch({
      ...PAYLOAD,
      headlines: [{ title: 'Amaero files', url: 'https://example.com/c',
                    source: 'Reuters', published: 1_758_000_000_000 }],
    }));
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    await screen.findByTestId('ipo-drill-sec-headlines');
    const h = txt('ipo-drill-sec-headlines');
    expect(h).toContain('Amaero files');
    expect(h).toContain('—');
    expect(h).not.toContain('57');
  });
});

describe('IpoUpcomingModal — the negatives', () => {
  it('NEGATIVE: EDGAR found nothing — the calendar facts and the sentence, no crash', async () => {
    const err = 'no registration filing found for this name on EDGAR full-text search '
      + '(S-1/F-1/424B4, last 365 days)';
    vi.stubGlobal('fetch', okFetch({
      ...PAYLOAD, filing: null, company: null, error: err,
      sources: { edgar_search_url: PAYLOAD.sources.edgar_search_url,
                 submissions_url: null, filing_url: null },
    }));
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    await screen.findByTestId('ipo-drill-err');
    expect(txt('ipo-drill-err')).toBe(err);
    expect(txt('ipo-drill-facts')).toContain('2026-09-23');
    // the sections still stand, empty
    expect(txt('ipo-drill-sec-what')).toContain('no Overview paragraph found in the filing');
    expect(txt('ipo-drill-sec-deal')).toContain('Underwriters—');
    expect(txt('ipo-drill-sec-industry')).toContain('SIC—');
    expect(txt('ipo-drill-note')).toBe(NOTE);
  });

  it('NEGATIVE: the request is refused — the 404 sentence is shown VERBATIM', async () => {
    const detail = 'ZZZZ is not an expected listing in the next 30 days on Finnhub’s IPO calendar.';
    vi.stubGlobal('fetch', badFetch(404, { detail }));
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    await screen.findByTestId('ipo-drill-err');
    expect(txt('ipo-drill-err')).toBe(detail);
    expect(txt('ipo-drill-facts')).toContain('NASDAQ Global Select');
  });

  it('NEGATIVE: the fetch rejects — a plain sentence, the facts, and NO note', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    await screen.findByTestId('ipo-drill-err');
    expect(txt('ipo-drill-err')).toBe("Couldn't load the filing facts for AMRO.");
    expect(txt('ipo-drill-facts')).toContain('7456500');
    expect(screen.queryByTestId('ipo-drill-note')).toBeNull();
    expect(screen.queryByTestId('ipo-drill-sec-what')).toBeNull();
  });

  it('NEGATIVE: every blank prints an em dash — no NaN, undefined, null or zero', async () => {
    vi.stubGlobal('fetch', okFetch({
      ...PAYLOAD,
      company: { name: null, cik: null, sic: null, sic_description: null,
                 state: null, fiscal_year_end: null },
      filing: {
        ...PAYLOAD.filing,
        proposed_symbol_line: null, shares_offered_line: null, price_line: null,
        underwriters: [], symbol_in_filing: null,
        revenue_line: null, revenue_units_line: null, revenue_period_line: null,
        net_loss_line: null, net_loss_units_line: null, net_loss_period_line: null,
      },
      headlines: [],
    }));
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    await screen.findByTestId('ipo-drill-sec-deal');
    const deal = txt('ipo-drill-sec-deal');
    expect(deal).toBe('THE DEALSymbol line—Shares—Price—Underwriters—');
    expect(/\d/.test(deal)).toBe(false);
    const rev = txt('ipo-drill-quote-revenue');
    expect(rev).toContain('not found in the filing — read the linked document');
    expect(txt('ipo-drill-quote-net-loss'))
      .toContain('not found in the filing — read the linked document');
    expect(txt('ipo-drill-sec-industry')).toBe('INDUSTRYSIC—State—FY end (MMDD as filed)—');
    expect(txt('ipo-drill-sec-headlines')).toContain('No headlines in the last 7 days');
    for (const bad of ['NaN', 'undefined', 'null']) {
      expect(deal).not.toContain(bad);
      expect(rev).not.toContain(bad);
      expect(txt('ipo-drill-sec-industry')).not.toContain(bad);
      expect(txt('ipo-drill-sec-headlines')).not.toContain(bad);
    }
  });

  it('says so when the filing names a DIFFERENT symbol', async () => {
    vi.stubGlobal('fetch', okFetch({
      ...PAYLOAD,
      filing: { ...PAYLOAD.filing, symbol_in_filing: '3DA' },
    }));
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    await screen.findByTestId('ipo-drill-symbol-mismatch');
    expect(txt('ipo-drill-symbol-mismatch'))
      .toBe('The filing names the symbol 3DA; the calendar says AMRO.');
  });

  it('NEGATIVE: the same symbol says nothing — a match is not news', async () => {
    vi.stubGlobal('fetch', okFetch(PAYLOAD));
    render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    await screen.findByTestId('ipo-drill-sec-deal');
    expect(screen.queryByTestId('ipo-drill-symbol-mismatch')).toBeNull();
    expect(txt('ipo-drill-sec-deal')).not.toContain('the calendar says');
  });

  it('NEGATIVE: nothing on the sheet is a chip, a state or a read', async () => {
    vi.stubGlobal('fetch', okFetch(PAYLOAD));
    const { container } = render(<IpoUpcomingModal row={ROW} onClose={() => {}} />);
    await screen.findByTestId('ipo-drill-note');
    const sheet = screen.getByTestId('ipo-drill');
    expect(sheet.querySelectorAll('[class*="chip"]').length).toBe(0);
    const all = sheet.textContent || '';
    for (const word of ['READY', 'WATCH', 'BLOCKED']) expect(all).not.toContain(word);
    expect(container).toBeTruthy();
  });
});

describe('IpoUpcomingModal — closing', () => {
  it('Escape closes', async () => {
    vi.stubGlobal('fetch', okFetch(PAYLOAD));
    const onClose = vi.fn();
    render(<IpoUpcomingModal row={ROW} onClose={onClose} />);
    await screen.findByTestId('ipo-drill');
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('the backdrop closes and the × closes', async () => {
    vi.stubGlobal('fetch', okFetch(PAYLOAD));
    const onClose = vi.fn();
    render(<IpoUpcomingModal row={ROW} onClose={onClose} />);
    fireEvent.click(await screen.findByTestId('ipo-drill'));
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId('ipo-drill-close'));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('NEGATIVE: a click INSIDE the sheet does not close it', async () => {
    vi.stubGlobal('fetch', okFetch(PAYLOAD));
    const onClose = vi.fn();
    render(<IpoUpcomingModal row={ROW} onClose={onClose} />);
    await screen.findByTestId('ipo-drill-note');
    const panel = document.querySelector('.ipo-drill') as HTMLElement;
    expect(panel).toBeTruthy();
    fireEvent.click(panel);
    await waitFor(() => expect(onClose).not.toHaveBeenCalled());
  });
});
