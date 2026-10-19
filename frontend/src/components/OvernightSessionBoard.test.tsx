import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/* 🌙 Overnight session board (BUILD_SPEC16 §3.7 + AMENDMENTS16 A1). The
 * fixture is the §3.4 payload shape with numbers from the 2026-10-19 probe
 * (QQQ last regular close 709.80, TSLA 354.72, a ~15-minute trade age). Every
 * sentence is served; the board prints them verbatim and composes none. */

vi.mock('../hooks/useWatchlist', () => ({
  useWatchlist: () => ({ rows: [{ ticker: 'TWLO' }, { ticker: 'qqq' }], loading: false }),
}));
vi.mock('./OvernightGappers', () => ({
  OvernightGappers: () => <div data-testid="gappers-mock" />,
}));

import OvernightSessionBoard from './OvernightSessionBoard';
import OvernightTab from './OvernightTab';

const row = (over: any = {}) => ({
  symbol: 'TSLA', name: 'Tesla, Inc. Common Stock', type: 'CS', base_close: 354.72, base_date: '2026-10-16',
  price: 361.1, src: 'q', price_time: '2026-10-19T00:47:00-04:00', price_time_et: 'Mon 0:47 ET', price_age_sec: 0,
  spread_pct: 0.04, pct: 1.7986, on_volume: 210_000, on_dollar: 75_831_000, on_trades: 4_100, on_bar: true,
  prior_pct: -2.13, prior_dollar_vol: 22_140_000_000, leveraged: false, lev_label: null, ref: false, ...over,
});

const SERVED = {
  session: 'SERVED-SESSION 🌙 Overnight session open — Sun 20:00 → Mon 04:00 ET (trade date Mon 10-19). Read every 10 minutes.',
  last: 'SERVED-LAST Last read Mon 0:50 ET.',
  stale: 'SERVED-STALE Last read Mon 0:50 ET — late: the next was due by Mon 1:15 ET (host asleep or the job failed).',
  counts: 'SERVED-COUNTS 6,267 names (last regular close ≥ $2 on ≥ $1M traded) · 6,142 priced this session …',
  price: 'SERVED-PRICE Now = … the trades in this read are a median 16 minutes old; quotes are live. …',
  lev: 'SERVED-LEV Leveraged and inverse ETFs are tagged from the fund’s own name …: 412 tagged.',
  unm: 'SERVED-UNM UNMEASURED — this says what moved overnight, never what to buy. Not advice.',
  empty: 'SERVED-EMPTY No overnight read stored yet — the first pass runs at 20:00 ET on a session night.',
  old: 'SERVED-OLD Showing the Mon 10-19 session’s last read (Mon 3:50 ET).',
  disc: 'SERVED-DISC Not advice.',
};

const payload = (over: any = {}, readOver: any = {}) => ({
  session: { open: true, trade_date: '2026-10-19', opens_at: '2026-10-18T20:00:00-04:00', closes_at: '2026-10-19T04:00:00-04:00',
             next_open: '2026-10-19T20:00:00-04:00', line: SERVED.session },
  read: {
    trade_date: '2026-10-19', base_date: '2026-10-16', as_of: '2026-10-19T00:50:00-04:00', as_of_et: 'Mon 0:50 ET',
    current: true, complete: true, reason: null,
    counts: { universe: 6267, ref_complete: true, batches: 32, batches_failed: 0, batches_skipped: 0, calls: 32, retries: 0,
              not_on_feed: 40, no_price: 85, no_base: 0, priced: 6142, on_trade: 1200, on_quote: 4942, listed: 750, thin: 5392,
              leveraged_tagged: 412, lev_unknown: 0, trade_age_median_sec: 960 },
    refs: [
      row({ symbol: 'SPY', name: 'SPDR S&P 500 ETF Trust', type: 'ETF', base_close: 664.39, price: 662.3, pct: -0.3146, ref: true, price_time_et: 'Mon 0:48 ET' }),
      row({ symbol: 'QQQ', name: 'Invesco QQQ Trust', type: 'ETF', base_close: 709.8, price: 706.81, pct: -0.4212, ref: true, src: 't',
            price_age_sec: 993, price_time_et: 'Mon 0:33 ET' }),
      row({ symbol: 'IWM', type: 'ETF', base_close: 243.1, price: 243.9, pct: 0.329, ref: true }),
      row({ symbol: 'DIA', type: 'ETF', base_close: 462.2, price: 461.5, pct: -0.1514, ref: true }),
    ],
    rows: [
      row({ symbol: 'SOXL', name: 'Direxion Daily Semiconductor Bull 3X Shares', type: 'ETF', base_close: 38.2, price: 40.66, pct: 6.44,
            leveraged: true, lev_label: '3× ETF', on_dollar: 41_800_000, src: 't', price_age_sec: 900, price_time_et: 'Mon 0:35 ET' }),
      row({ symbol: 'TWLO', name: 'Twilio Inc.', base_close: 102.3, price: 105.1, pct: 2.737, on_dollar: 612_000, prior_pct: 1.2 }),
      row(),
      row({ symbol: 'ZZZQ', name: null, base_close: 4.1, price: 4.0, pct: -2.439, on_dollar: 26_000, prior_pct: null, leveraged: null }),
    ],
    sort: 'gainers', hide_leveraged: false, n_hidden_leveraged: 0, n_listed: 4, ...readOver,
  },
  last_pass: { as_of: '2026-10-19T00:50:00-04:00', as_of_et: 'Mon 0:50 ET', ok: true, reason: null, stale: false, line: SERVED.last },
  sorts: [{ key: 'gainers', label: 'SERVED-SORT 📈 gainers' }, { key: 'losers', label: 'SERVED-SORT 📉 losers' },
          { key: 'dollar', label: 'SERVED-SORT 💵 dollars' }],
  lines: { counts: SERVED.counts, price_rule: SERVED.price, leveraged: SERVED.lev, unmeasured: SERVED.unm, empty: SERVED.empty, read_old: SERVED.old },
  refresh_sec: 300,
  disclaimer: SERVED.disc,
  ...over,
});

const ok = (body: any) => ({ ok: true, status: 200, json: () => Promise.resolve(body) } as any);

function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.search}</div>;
}

const draw = (search = '?tab=overnight', onPick = vi.fn()) => {
  const r = render(
    <MemoryRouter initialEntries={[`/chart-maps${search}`]}>
      <OvernightSessionBoard onPick={onPick} />
      <Loc />
    </MemoryRouter>,
  );
  return { ...r, onPick };
};
const locQ = () => new URLSearchParams(screen.getByTestId('loc').textContent || '');

let hidden = false;
beforeEach(() => {
  hidden = false;
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden });
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('OvernightSessionBoard — served lines, verbatim', () => {
  it('prints session.line, last_pass.line, lines.counts, the price rule, the leverage rule, UNMEASURED and the disclaimer', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload())));
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-table')).toBeTruthy());
    expect(screen.getByTestId('ons-session-line').textContent).toBe(SERVED.session);
    expect(screen.getByTestId('ons-last-pass').textContent).toBe(SERVED.last);
    expect(screen.getByTestId('ons-counts').textContent).toBe(SERVED.counts);
    expect(screen.getByTestId('ons-price-rule').textContent).toBe(SERVED.price);
    expect(screen.getByTestId('ons-lev-line').textContent).toBe(SERVED.lev);
    expect(screen.getByTestId('ons-unmeasured').textContent).toBe(SERVED.unm);
    expect(screen.getByTestId('ons-disclaimer').textContent).toBe(SERVED.disc);
  });

  it('a stale last pass prints amber; NEGATIVE a fresh one does not', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload({
      last_pass: { as_of: 'x', as_of_et: 'Mon 0:50 ET', ok: true, reason: null, stale: true, line: SERVED.stale } }))));
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-last-pass')).toBeTruthy());
    expect(screen.getByTestId('ons-last-pass').className).toContain('ons-stale');
    expect(screen.getByTestId('ons-last-pass').textContent).toBe(SERVED.stale);
  });

  it('a failed last pass (ok false) prints the served line once, error-styled — the reason it ends with appears exactly once', async () => {
    const REASON = 'Alpaca overnight feed refused (HTTP 403)';
    const LINE = `SERVED-FAILED Last pass Mon 1:00 ET failed — ${REASON}`;
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload({
      last_pass: { as_of: 'x', as_of_et: 'Mon 1:00 ET', ok: false, stale: false, reason: REASON, line: LINE } }))));
    const { container } = draw();
    await waitFor(() => expect(screen.getByTestId('ons-last-pass')).toBeTruthy());
    expect(screen.getByTestId('ons-last-pass').textContent).toBe(LINE);
    expect(screen.getByTestId('ons-last-pass').className).toContain('ons-error');
    expect((container.textContent || '').split(REASON).length - 1).toBe(1);
  });

  it('NEGATIVE: an ok last pass carries no error style and prints no served reason', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload({
      last_pass: { as_of: 'x', as_of_et: 'Mon 0:50 ET', ok: true, stale: false, reason: 'SERVED-REASON should not show', line: SERVED.last } }))));
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-last-pass')).toBeTruthy());
    expect(screen.getByTestId('ons-last-pass').className).not.toContain('ons-error');
    expect(document.body.textContent).not.toContain('should not show');
  });

  it('NEGATIVE: a fresh last pass is not amber', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload())));
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-last-pass')).toBeTruthy());
    expect(screen.getByTestId('ons-last-pass').className).not.toContain('ons-stale');
  });

  it('a closed-session read (current false) prints lines.read_old; NEGATIVE a current read does not', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload({}, { current: false }))));
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-read-old')).toBeTruthy());
    expect(screen.getByTestId('ons-read-old').textContent).toBe(SERVED.old);
  });

  it('NEGATIVE: a current read never prints read_old', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload())));
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-table')).toBeTruthy());
    expect(screen.queryByTestId('ons-read-old')).toBeNull();
  });

  it('NEGATIVE: read null → lines.empty, no table, no counts', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload({ read: null }))));
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-empty')).toBeTruthy());
    expect(screen.getByTestId('ons-empty').textContent).toBe(SERVED.empty);
    expect(screen.queryByTestId('ons-table')).toBeNull();
    expect(screen.queryByTestId('ons-counts')).toBeNull();
    expect(screen.queryByTestId('ons-refs')).toBeNull();
  });
});

describe('OvernightSessionBoard — refs and the table', () => {
  it('refs come first in the served order (SPY QQQ IWM DIA) with pct, price, src and time', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload())));
    const { container } = draw();
    await waitFor(() => expect(screen.getByTestId('ons-refs')).toBeTruthy());
    const refs = [...container.querySelectorAll('.ons-ref .ons-ref-sym')].map((e) => e.textContent);
    expect(refs).toEqual(['SPY', 'QQQ', 'IWM', 'DIA']);
    const qqq = screen.getByTestId('ons-ref-QQQ');
    expect(qqq.textContent).toContain('-0.42%');
    expect(qqq.textContent).toContain('$706.81');
    expect(qqq.textContent).toContain('Mon 0:33 ET');
    expect(within(qqq).getByTestId('ons-src-t')).toBeTruthy();
    // the refs strip sits above the table
    const all = container.innerHTML;
    expect(all.indexOf('ons-refs')).toBeLessThan(all.indexOf('ons-table'));
  });

  it('table columns and one row\'s values', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload())));
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-table')).toBeTruthy());
    const heads = [...screen.getByTestId('ons-table').querySelectorAll('th')].map((th) => th.textContent);
    expect(heads).toEqual(['⭐', 'Symbol', 'Overnight %', 'Now', 'Base close', 'Overnight $ vol', 'Prior-session %', 'Time of print', 'Src']);
    const tds = [...screen.getByTestId('ons-row-TSLA').querySelectorAll('td')].map((td) => td.textContent);
    expect(tds[1]).toContain('TSLA');
    expect(tds[1]).toContain('Tesla, Inc. Common Stock');
    expect(tds[2]).toBe('+1.80%');
    expect(tds[3]).toContain('$361.10');
    expect(tds[4]).toContain('$354.72');
    expect(tds[4]).toContain('2026-10-16');
    expect(tds[5]).toBe('$75.8M');
    expect(tds[6]).toBe('-2.13%');
    expect(tds[7]).toBe('Mon 0:47 ET');
    expect(tds[8]).toBe('bid/ask midpoint');
  });

  it('the rows keep the served order (no client-side re-sort)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload())));
    const { container } = draw();
    await waitFor(() => expect(screen.getByTestId('ons-table')).toBeTruthy());
    const syms = [...container.querySelectorAll('tbody .ons-sym-t')].map((e) => e.textContent);
    expect(syms).toEqual(['SOXL', 'TWLO', 'TSLA', 'ZZZQ']);
  });

  it('the q chip marks only src q rows; the t chip only src t rows — indicative and delayed on hover (A1/A4)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload())));
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-table')).toBeTruthy());
    const tsla = screen.getByTestId('ons-row-TSLA');
    const soxl = screen.getByTestId('ons-row-SOXL');
    expect(within(tsla).getByTestId('ons-src-q').textContent).toBe('q');
    expect(within(tsla).queryByTestId('ons-src-t')).toBeNull();
    expect(within(soxl).getByTestId('ons-src-t').textContent).toBe('t');
    expect(within(soxl).queryByTestId('ons-src-q')).toBeNull();
    const t = within(soxl).getByTestId('ons-src-t').getAttribute('title') || '';
    expect(t).toMatch(/indicative/);
    expect(t).toMatch(/delayed/);
    expect(t).not.toMatch(/live/i);
    // the row's age on hover (900 s → 15 minutes)
    expect(soxl.querySelector('.ons-time')?.getAttribute('title')).toContain('15 min old');
  });

  it('⭐ only on a watchlist symbol (case-insensitive)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload())));
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-table')).toBeTruthy());
    expect(within(screen.getByTestId('ons-row-TWLO')).getByTestId('ons-star')).toBeTruthy();
  });

  it('NEGATIVE: no ⭐ on names off the watchlist', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload())));
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-table')).toBeTruthy());
    for (const s of ['SOXL', 'TSLA', 'ZZZQ']) expect(within(screen.getByTestId(`ons-row-${s}`)).queryByTestId('ons-star'), s).toBeNull();
  });

  it('the served lev_label chips a leveraged fund; NEGATIVE none on a stock or an unknown', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload())));
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-table')).toBeTruthy());
    expect(within(screen.getByTestId('ons-row-SOXL')).getByTestId('ons-lev-chip').textContent).toBe('3× ETF');
    expect(within(screen.getByTestId('ons-row-TSLA')).queryByTestId('ons-lev-chip')).toBeNull();
    expect(within(screen.getByTestId('ons-row-ZZZQ')).queryByTestId('ons-lev-chip')).toBeNull();
  });

  it('NEGATIVE: a null prior_pct prints a dash, never 0', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload())));
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-table')).toBeTruthy());
    const tds = [...screen.getByTestId('ons-row-ZZZQ').querySelectorAll('td')].map((td) => td.textContent);
    expect(tds[6]).toBe('—');
  });

  it('a row click hands the symbol to onPick (the Support tab)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload())));
    const { onPick } = draw();
    await waitFor(() => expect(screen.getByTestId('ons-table')).toBeTruthy());
    fireEvent.click(screen.getByTestId('ons-row-TWLO'));
    fireEvent.click(screen.getByTestId('ons-ref-QQQ'));
    expect(onPick.mock.calls).toEqual([['TWLO'], ['QQQ']]);
  });
});

describe('OvernightSessionBoard — controls', () => {
  it('sort buttons are labelled from the served sorts; the served read.sort is active', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload())));
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-sort-gainers')).toBeTruthy());
    expect(screen.getByTestId('ons-sort-gainers').textContent).toBe('SERVED-SORT 📈 gainers');
    expect(screen.getByTestId('ons-sort-losers').textContent).toBe('SERVED-SORT 📉 losers');
    expect(screen.getByTestId('ons-sort-dollar').textContent).toBe('SERVED-SORT 💵 dollars');
    expect(screen.getByTestId('ons-sort-gainers').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('ons-sort-losers').getAttribute('aria-pressed')).toBe('false');
  });

  it('NEGATIVE: no typed sort label — a served sorts list of one renders one button with its words only', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok(payload({ sorts: [{ key: 'dollar', label: 'only-this' }] }))));
    const { container } = draw();
    await waitFor(() => expect(screen.getByTestId('ons-sort-dollar')).toBeTruthy());
    expect(container.querySelectorAll('.ons-sorts button').length).toBe(1);
    expect(container.textContent).not.toMatch(/Top gainers|Top losers|Most \$ traded/);
  });

  it('a sort click writes on_sort and refetches with sort=', async () => {
    const f = vi.fn().mockResolvedValue(ok(payload()));
    vi.stubGlobal('fetch', f);
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-sort-losers')).toBeTruthy());
    fireEvent.click(screen.getByTestId('ons-sort-losers'));
    expect(locQ().get('on_sort')).toBe('losers');
    await waitFor(() => expect(f.mock.calls.some((c) => /sort=losers/.test(String(c[0])))).toBe(true));
  });

  it('Hide leveraged ETFs writes on_lev=1, sends hide_lev=true and shows the served n_hidden_leveraged', async () => {
    const f = vi.fn().mockImplementation((u: string) => Promise.resolve(ok(
      /hide_lev=true/.test(u) ? payload({}, { hide_leveraged: true, n_hidden_leveraged: 37 }) : payload())));
    vi.stubGlobal('fetch', f);
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-hide-lev')).toBeTruthy());
    expect(screen.queryByTestId('ons-hidden-n')).toBeNull();
    fireEvent.click(screen.getByTestId('ons-hide-lev'));
    expect(locQ().get('on_lev')).toBe('1');
    await waitFor(() => expect(screen.getByTestId('ons-hidden-n').textContent).toContain('37'));
    expect(screen.getByTestId('ons-hide-lev').getAttribute('aria-pressed')).toBe('true');
    // a second tap shows them again and drops the param
    fireEvent.click(screen.getByTestId('ons-hide-lev'));
    expect(locQ().has('on_lev')).toBe(false);
  });

  it('NEGATIVE: on_lev of any other value does not hide (and sends no hide_lev)', async () => {
    const f = vi.fn().mockResolvedValue(ok(payload()));
    vi.stubGlobal('fetch', f);
    draw('?tab=overnight&on_lev=yes');
    await waitFor(() => expect(screen.getByTestId('ons-hide-lev')).toBeTruthy());
    expect(screen.getByTestId('ons-hide-lev').getAttribute('aria-pressed')).toBe('false');
    for (const c of f.mock.calls) expect(String(c[0])).not.toMatch(/hide_lev/);
  });
});

describe('OvernightSessionBoard — fetch life cycle', () => {
  it('NEGATIVE: a fetch error keeps the last payload on screen with an error line', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const f = vi.fn()
      .mockResolvedValueOnce(ok(payload()))
      .mockResolvedValueOnce({ ok: false, status: 503, json: () => Promise.resolve({}) } as any);
    vi.stubGlobal('fetch', f);
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-table')).toBeTruthy());
    await act(async () => { vi.advanceTimersByTime(300_000); });
    await waitFor(() => expect(screen.getByTestId('ons-error')).toBeTruthy());
    expect(screen.getByTestId('ons-error').textContent).toMatch(/503/);
    expect(screen.getByTestId('ons-table')).toBeTruthy();
    expect(screen.getByTestId('ons-session-line').textContent).toBe(SERVED.session);
  });

  it('refetches at the served refresh_sec; NEGATIVE not while the document is hidden', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const f = vi.fn().mockResolvedValue(ok(payload({ refresh_sec: 1800 })));
    vi.stubGlobal('fetch', f);
    draw();
    await waitFor(() => expect(screen.getByTestId('ons-table')).toBeTruthy());
    expect(f).toHaveBeenCalledTimes(1);
    hidden = true;
    await act(async () => { vi.advanceTimersByTime(1800_000); });
    expect(f).toHaveBeenCalledTimes(1);
    hidden = false;
    await act(async () => { vi.advanceTimersByTime(1800_000); });
    await waitFor(() => expect(f).toHaveBeenCalledTimes(2));
  });
});

describe('OvernightTab with the real board', () => {
  const tab = (search: string) => render(
    <MemoryRouter initialEntries={[`/chart-maps${search}`]}>
      <OvernightTab onPick={vi.fn()} />
    </MemoryRouter>,
  );

  it('the session sub fetches /overnight/session (positive control)', async () => {
    const f = vi.fn().mockResolvedValue(ok(payload()));
    vi.stubGlobal('fetch', f);
    tab('?tab=overnight');
    await waitFor(() => expect(f.mock.calls.some((c) => /\/overnight\/session/.test(String(c[0])))).toBe(true));
  });

  it('NEGATIVE: the Gappers sub never fetches /overnight/session', async () => {
    const f = vi.fn().mockResolvedValue(ok(payload()));
    vi.stubGlobal('fetch', f);
    tab('?tab=overnight&on_sub=gappers');
    expect(screen.getByTestId('gappers-mock')).toBeTruthy();
    await new Promise((r) => setTimeout(r, 20));
    for (const c of f.mock.calls) expect(String(c[0])).not.toMatch(/\/overnight\/session/);
  });
});
