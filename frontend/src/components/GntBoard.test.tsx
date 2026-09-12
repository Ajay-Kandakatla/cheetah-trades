/* 📌 GnT board (2026-09-12).
 *
 * Ajay: "I wanna track his stocks for investing".
 *
 * Every test here exists because a bare ticker list INVERTS him. He mixes
 * forward ideas with past-tense recaps of closed trades, several of them puts,
 * and one of his posts carries both directions at once.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import GntBoard, { ageText, zoneText } from './GntBoard';
import type { GntTicker } from './GntBoard';

const FRESH: GntTicker = {
  symbol: 'SPCX', mentions: 1, flags: ['long', 'watch'], age_days: 0, fresh: true,
  covered: false, zone: null, growth: null,
  last_post: { id: '1', url: 'https://x.com/GnT_Trades/status/1',
               created_at: '2026-09-11T19:37:00+00:00',
               text: '$SPCX reclaiming 150 into the close. Definitely on watch next week' },
};
const PUTS: GntTicker = {
  symbol: 'QQQX', mentions: 1, flags: ['puts', 'recap'], age_days: 410, fresh: false,
  covered: true, zone: { missing: false, in_band: false, intact: null }, growth: null,
  last_post: { id: '2', url: 'https://x.com/GnT_Trades/status/2',
               created_at: '2025-07-29T00:00:00+00:00',
               text: 'Great day on $QQQX puts, +$12K' },
};
const INTACT: GntTicker = {
  symbol: 'BBY', mentions: 1, flags: ['watch'], age_days: 0, fresh: true,
  covered: true, zone: { missing: false, in_band: true, intact: true },
  growth: { sales: 145.9, eps: 185, refused: false },
  last_post: { id: '3', url: 'u', created_at: '2026-09-11T19:16:00+00:00',
               text: 'Consumer discretionary names mostly lagging but $BBY has a nice look' },
};

const PAYLOAD = {
  handle: 'GnT_Trades', display: 'Tito Adhikary', profile_url: 'https://x.com/GnT_Trades',
  usic: { year: 2025, division: '$20,000+ Enhanced Growth', return_pct: 2115.1, rank: 1,
          source: '@USICOfficial, quoted in his pinned post 2026-01-29',
          note: 'A contest return, self-selected and unaudited by this app. The enhanced-growth divisions permit concentration and leverage that this app’s own risk rules forbid.' },
  n_posts: 106, n_tickers: 3, n_fresh: 2, fresh_days: 14,
  newest_post_at: '2026-09-11T20:18:00+00:00', newest_age_days: 0,
  tickers: [FRESH, INTACT, PUTS],
  disclaimer: 'His posts, NOT advice and NOT a portfolio. He posts forward ideas AND '
            + 'past-tense recaps of closed trades, several of them PUTS — read the '
            + 'sentence, not the ticker.',
};

const stub = (body: unknown, ok = true) => vi.stubGlobal('fetch', vi.fn(async () => ({
  ok, status: ok ? 200 : 503, json: async () => body,
}) as unknown as Response));
const mount = () => render(<MemoryRouter><GntBoard /></MemoryRouter>);
afterEach(() => vi.unstubAllGlobals());

describe('ageText — is this an idea or history?', () => {
  it('reads at a glance across every scale', () => {
    expect(ageText(0)).toBe('today');
    expect(ageText(1)).toBe('1d');
    expect(ageText(12)).toBe('12d');
    expect(ageText(60)).toBe('2mo');
    expect(ageText(410)).toBe('1.1y');
  });
  it('NEGATIVE: an unknown age is an em-dash, never "today"', () => {
    expect(ageText(null)).toBe('—');
    expect(ageText(undefined)).toBe('—');
  });
});

describe('zoneText — our read, in the growth board’s own vocabulary', () => {
  it('says when a name is not even scanned — the SPCX case', () => {
    const z = zoneText(FRESH);
    expect(z.text).toBe('not scanned');
    expect(z.title).toMatch(/can ever see it/);
  });
  it('an intact floor reads as the measured gate', () => {
    expect(zoneText(INTACT).text).toBe('🧲 intact');
  });
  it('NEGATIVE: an unanswered floor check is not called pierced', () => {
    const t = { ...INTACT, zone: { missing: false, in_band: true, intact: null } };
    expect(zoneText(t).text).toBe('in band, floor ?');
  });
  it('NEGATIVE: coverage is checked BEFORE the band, so an unscanned name never claims one', () => {
    const t = { ...FRESH, covered: false, zone: { in_band: true, intact: true } };
    expect(zoneText(t).text).toBe('not scanned');
  });
});

describe('GntBoard', () => {
  it('leads every row with his actual words, not just the ticker', async () => {
    stub(PAYLOAD);
    mount();
    expect(await screen.findByText(/reclaiming 150 into the close/)).toBeInTheDocument();
    expect(screen.getByText(/has a nice look/)).toBeInTheDocument();
  });

  it('THE CENTRAL ONE: a put recap is marked bearish, never shown as a pick', async () => {
    stub({ ...PAYLOAD, n_fresh: 3,
           tickers: [{ ...PUTS, fresh: true, age_days: 1 }] });
    mount();
    const chip = await screen.findByTitle(/mentions puts — a BEARISH trade/);
    expect(chip).toHaveTextContent('puts');
    expect(screen.getByTitle(/RECAP of a trade already closed/)).toBeInTheDocument();
  });

  it('NEGATIVE: no row ever renders a long/short VERDICT', async () => {
    // His own post carries both directions across its tickers, so a badge
    // would be provably wrong. Chips are evidence words only.
    stub(PAYLOAD);
    mount();
    await waitFor(() => expect(screen.getByText(/nice look/)).toBeInTheDocument());
    for (const word of [/^buy$/i, /^sell$/i, /bullish/i, /bearish signal/i, /entry:/i]) {
      expect(screen.queryByText(word)).not.toBeInTheDocument();
    }
  });

  it('opens on the last 14 days, and the history is one click away', async () => {
    stub(PAYLOAD);
    mount();
    await waitFor(() => expect(screen.getByText(/nice look/)).toBeInTheDocument());
    // the 410-day-old put recap is hidden by default
    expect(screen.queryByText(/Great day on/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox', { name: /last 14 days only/ }));
    expect(screen.getByText(/Great day on/)).toBeInTheDocument();
  });

  it('prints the championship WITH its source and its caveat', async () => {
    stub(PAYLOAD);
    mount();
    expect(await screen.findByText(/USIC 2025 #1 · 2115.1%/)).toBeInTheDocument();
    expect(screen.getByText(/concentration and leverage/)).toBeInTheDocument();
  });

  it('says "read the sentence, not the ticker" on the board itself', async () => {
    stub(PAYLOAD);
    mount();
    expect(await screen.findByText(/Read the sentence, not the ticker/)).toBeInTheDocument();
    expect(screen.getByText(/NOT advice and NOT a portfolio/)).toBeInTheDocument();
  });

  it('NEGATIVE: an empty tracker says the cron owns it, not "no ideas"', async () => {
    stub({ ...PAYLOAD, tickers: [], n_fresh: 0, n_posts: 0 });
    mount();
    fireEvent.click(await screen.findByRole('checkbox', { name: /last 14 days only/ }));
    expect(screen.getByText(/runs twice a day/)).toBeInTheDocument();
  });

  it('NEGATIVE: a failed fetch says so instead of rendering an empty board', async () => {
    stub({}, false);
    mount();
    expect(await screen.findByText(/⛔ HTTP 503/)).toBeInTheDocument();
  });
});

/* ── Two champions, one board (2026-09-12) ─────────────────────────────────
 * Ajay: "Also track their mentions for me.. Martin Luk +969.8% (stocks)".
 * A switcher rather than a second tab, so the caveats cannot drift apart. */
describe('GntBoard — the trader switcher', () => {
  afterEach(() => vi.unstubAllGlobals());

  function spy(payload: unknown) {
    const seen: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      seen.push(String(url));
      return { ok: true, status: 200, json: async () => payload } as unknown as Response;
    }));
    return seen;
  }

  it('opens on GnT and switching refetches the OTHER feed', async () => {
    const seen = spy(PAYLOAD);
    mount();
    await waitFor(() => expect(seen.length).toBeGreaterThan(0));
    expect(seen[0]).toContain('/traders/gnt');

    fireEvent.click(screen.getByRole('tab', { name: /Martin Luk/ }));
    await waitFor(() => expect(seen.length).toBeGreaterThan(1));
    expect(seen[seen.length - 1]).toContain('/traders/martinluk');
  });

  it('marks exactly one trader selected at a time', async () => {
    stub(PAYLOAD);
    mount();
    await waitFor(() => expect(screen.getByText(/nice look/)).toBeInTheDocument());
    const on = screen.getAllByRole('tab').filter((t) => t.getAttribute('aria-selected') === 'true');
    expect(on).toHaveLength(1);
    expect(on[0]).toHaveTextContent('Tito Adhikary');
  });

  it('NEGATIVE: the shared caveat renders whichever trader is shown', async () => {
    stub({ ...PAYLOAD, display: 'Martin Luk', handle: 'martinlukkt' });
    mount();
    expect(await screen.findByText(/Read the sentence, not the ticker/)).toBeInTheDocument();
    expect(screen.getByText(/NOT advice and NOT a portfolio/)).toBeInTheDocument();
  });
});
