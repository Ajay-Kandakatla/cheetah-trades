/* Ajay 2026-10-21 ~16:20 ET: the chatter panel printed "all subs returned errors
 * (rate-limit?)" for both Reddit lanes and a raw curl error with a libcurl URL for
 * StockTwits, with zero counts, while api.stocktwits.com was down for everyone.
 * BUILD_SPEC23 B: the backend serves every outage sentence; the panel prints it,
 * keeps the last good StockTwits read under a served stale line, and never prints
 * a reason that carries a URL or curl text (an older API). */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ChatterPanel } from './ChatterPanel';
import src from './ChatterPanel.tsx?raw';

const NOW = Math.floor(Date.now() / 1000);

const REDDIT_KEY_SENTENCE =
  'Reddit closed anonymous access (http 404) — a Reddit app key is needed (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in backend/.env)';
const ST_TIMEOUT = 'StockTwits is not answering (timed out after 10s)';

function redditLane(reason: string) {
  return { available: false, reason, reason_code: 'gone', threads: [], mentions_7d: 0, mentions_prior_7d: 0 };
}

function payload(stocktwits: Record<string, unknown>, reddit = REDDIT_KEY_SENTENCE) {
  return {
    symbol: 'MASK',
    company_name: null,
    fetched_at: NOW,
    fetched_at_iso: new Date(NOW * 1000).toISOString(),
    thoughtful: redditLane(reddit),
    momentum: redditLane(reddit),
    stocktwits,
    hn: { available: true, stories: [], n: 0 },
    summary: {
      mentions_7d: 0, mentions_prior_7d: 0, mention_velocity: 0, sentiment_ratio: 0.75,
      stocktwits_bullish: 3, stocktwits_bearish: 1, hn_stories: 0, momentum_label: 'quiet',
    },
    cached: false,
  };
}

const MSG = {
  id: 11, body: 'MASK holding the 21 day line', user: 'trader1', followers: 0,
  sentiment: 'Bullish', created: new Date((NOW - 7200) * 1000).toISOString(), url: 'https://stocktwits.com/x/11',
};

const STALE_BLOCK = {
  available: true, messages: [MSG], bullish: 3, bearish: 1, neutral: 2, total: 6,
  stale: true, stale_since: NOW - 2 * 3600, stale_reason: ST_TIMEOUT,
  reason_code: 'timeout', last_attempt_at: NOW,
};

const FRESH_BLOCK = { available: true, messages: [MSG], bullish: 3, bearish: 1, neutral: 2, total: 6 };

function serve(body: unknown) {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })));
}

async function mount(body: unknown) {
  serve(body);
  const out = render(<ChatterPanel symbol="MASK" />);
  await waitFor(() => expect(screen.getByText('Reddit · Momentum')).toBeInTheDocument());
  return out;
}

afterEach(() => { vi.unstubAllGlobals(); });

describe('ChatterPanel — StockTwits stale keep', () => {
  it('a stale block renders its counts, its messages and the served stale line', async () => {
    await mount(payload(STALE_BLOCK));
    expect(screen.getByText(/3 bullish · 1 bearish · 2 neutral/)).toBeInTheDocument();
    expect(screen.getByText('MASK holding the 21 day line')).toBeInTheDocument();
    expect(screen.getByTestId('stocktwits-stale')).toHaveTextContent(
      'StockTwits is not answering (timed out after 10s) · showing the read from 2h ago',
    );
  });

  it('NEGATIVE: a fresh block renders no stale line', async () => {
    await mount(payload(FRESH_BLOCK));
    expect(screen.queryByTestId('stocktwits-stale')).toBeNull();
    expect(screen.queryByText(/showing the read from/)).toBeNull();
    expect(screen.getByText('MASK holding the 21 day line')).toBeInTheDocument();
  });

  it('NEGATIVE: stale: true without a numeric stale_since renders no stale line', async () => {
    const { stale_since: _drop, ...noSince } = STALE_BLOCK;
    await mount(payload(noSince));
    expect(screen.queryByTestId('stocktwits-stale')).toBeNull();
  });
});

describe('ChatterPanel — unavailable lanes print the served sentence', () => {
  it('an unavailable StockTwits block renders the served sentence', async () => {
    const sentence = `${ST_TIMEOUT} · no earlier read`;
    await mount(payload({
      available: false, reason: sentence, reason_code: 'timeout',
      messages: [], bullish: 0, bearish: 0, neutral: 0, total: 0,
    }));
    expect(screen.getByText(sentence)).toBeInTheDocument();
    expect(screen.queryByTestId('stocktwits-stale')).toBeNull();
  });

  it('the Reddit lanes render the served sentence verbatim', async () => {
    await mount(payload(FRESH_BLOCK));
    expect(screen.getAllByText(REDDIT_KEY_SENTENCE)).toHaveLength(2);
    expect(screen.queryByText(/rate-limit\?/)).toBeNull();
  });

  it('NEGATIVE: a reason carrying https://curl.se prints "unavailable", never the URL', async () => {
    const leaky = 'fetch failed: Failed to perform, curl: (28) Operation timed out after 10003 milliseconds '
      + 'with 0 bytes received. See https://curl.se/libcurl/c/libcurl-errors.html first for more details.';
    const { container } = await mount(payload({
      available: false, reason: leaky, messages: [], bullish: 0, bearish: 0, neutral: 0, total: 0,
    }, 'see http://old.reddit.com/r/stocks for details'));
    expect(screen.getAllByText('unavailable')).toHaveLength(3);
    const text = container.textContent ?? '';
    expect(text).not.toContain('curl');
    expect(text).not.toContain('https://');
    expect(text).not.toContain('http://');
    expect(text).not.toContain('fetch failed');
  });

  it('NEGATIVE: a stale_reason carrying a URL is scrubbed too', async () => {
    await mount(payload({ ...STALE_BLOCK, stale_reason: 'curl: (28) see https://curl.se/x' }));
    const line = screen.getByTestId('stocktwits-stale');
    expect(line).toHaveTextContent('unavailable · showing the read from 2h ago');
    expect(line.textContent).not.toContain('curl');
  });

  it('NEGATIVE: an absent reason falls back to "No data"', async () => {
    await mount(payload({ available: false, messages: [], bullish: 0, bearish: 0, neutral: 0, total: 0 }));
    expect(screen.getByText('No data')).toBeInTheDocument();
  });
});

describe('ChatterPanel source — no typed outage sentence', () => {
  it.each([
    'StockTwits is', 'Reddit closed', 'Reddit refused', 'Reddit rate limit', 'Reddit is not',
    'Reddit answered', 'no earlier read', 'rate-limit?', 'fetch failed',
  ])('NEGATIVE: ChatterPanel.tsx does not type %j', (needle) => {
    expect(src).not.toContain(needle);
  });

  it('prints the served stale_reason and carries the scrub', () => {
    expect(src).toContain('servedReason(data.stocktwits.stale_reason)');
    expect(src).toMatch(/const UNSAFE_REASON = \/https\?:\\\/\\\/\|curl\/i;/);
  });
});
