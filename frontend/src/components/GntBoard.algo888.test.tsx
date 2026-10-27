/* 📌 algo888 on the tracked-traders board (2026-10-27, BUILD_SPEC26 §3.4 / §4 WP-C).
 *
 * Ajay: "Can you track this guy please? and his tickers" and "Add them to Gajjals, they are pretty good".
 *
 * FIXTURES ARE SYNTHETIC — typed from the served shapes of traders/feed.py board() (spec §3.1 / §3.2): `source`,
 * `source_text`, `claim_text` (null when he claims nothing), `gajjala_text` (null unless flagged), `style`, `profile`,
 * and `usic` with NO fallback. The words below are test data; the board prints only what is served.
 *
 * The negative that matters: before this build a claim-less trader was served GnT's championship (+2,115.1%). A
 * claim-less payload must print no USIC line at all.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import GntBoard, { TRADER_TABS } from './GntBoard';
import type { GntPayload, GntTicker } from './GntBoard';

const GPUS: GntTicker = {
  symbol: 'GPUS', mentions: 2, flags: [], age_days: 0, fresh: true,
  covered: false, zone: null, growth: null,
  last_post: { id: 'st667434074', url: 'https://stocktwits.com/algo888/message/667434074',
               created_at: '2026-10-27T13:41:58+00:00', text: '$GPUS my 100,000 position is up huge!!!' },
};

/* SYNTHETIC served payload for the StockTwits account (spec §3.1 / §3.2 shapes). */
const SOURCE_TEXT = 'on StockTwits';
const GAJJALA_TEXT = '📌 His fresh names join 🚩 Gajjala’s scan as candidates — your call 2026-10-27 '
  + '(“Add them to Gajjals, they are pretty good”); GG’s rules decide every read and every A+.';
const STYLE = 'In his own words on StockTwits, 2026-10-27 (ET): “@WC25 That;s how I pump.... LOL” (08:55, message 667428905).';
const ALGO: GntPayload = {
  handle: 'algo888', display: 'algo888', profile_url: 'https://stocktwits.com/algo888',
  usic: null, source: 'stocktwits', source_text: SOURCE_TEXT, claim_text: null,
  gajjala_text: GAJJALA_TEXT, style: STYLE,
  profile: { user_id: 2124563, followers: 3846, following: 0, joined: '2019-06-06', ideas: 114049,
             bio: 'served bio', read: '2026-10-27 from his StockTwits stream page' },
  n_posts: 30, n_tickers: 1, n_fresh: 1, fresh_days: 14,
  newest_post_at: '2026-10-27T13:56:49+00:00', newest_age_days: 0,
  tickers: [GPUS],
  disclaimer: 'served disclaimer',
};

/* SYNTHETIC served payload for GnT on the new API (claim_text served beside the usic block). */
const CLAIM = 'USIC 2025 #1 · 2115.1% ($20,000+ Enhanced Growth)';
const GNT_NEW: GntPayload = {
  handle: 'GnT_Trades', display: 'Tito Adhikary', profile_url: 'https://x.com/GnT_Trades',
  usic: { year: 2025, division: '$20,000+ Enhanced Growth', return_pct: 2115.1, rank: 1, note: 'served caveat' },
  source: 'x', source_text: 'on X', claim_text: CLAIM, gajjala_text: null, style: null,
  n_posts: 1, n_tickers: 1, n_fresh: 1, fresh_days: 14, newest_age_days: 0,
  tickers: [{ ...GPUS, symbol: 'SPCX', last_post: { id: '1', text: '$SPCX reclaiming 150 into the close' } }],
  disclaimer: 'served disclaimer',
};

function spy(payload: unknown) {
  const seen: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    seen.push(String(url));
    return { ok: true, status: 200, json: async () => payload } as unknown as Response;
  }));
  return seen;
}
const mount = (trader?: string) =>
  render(<MemoryRouter>{trader ? <GntBoard trader={trader} /> : <GntBoard />}</MemoryRouter>);

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('📌 algo888 — the tab', () => {
  it('TRADER_TABS appends algo888 last (gnt stays the default, first)', () => {
    expect(TRADER_TABS.map((t) => t.key)).toEqual(['gnt', 'martinluk', 'algo888']);
  });

  it('the tab is present and clicking it fetches /traders/algo888', async () => {
    const seen = spy(GNT_NEW);
    mount();
    await waitFor(() => expect(seen.length).toBeGreaterThan(0));
    expect(seen[0]).toContain('/traders/gnt');
    fireEvent.click(await screen.findByRole('tab', { name: 'algo888' }));
    await waitFor(() => expect(seen.some((u) => u.includes('/traders/algo888'))).toBe(true));
  });
});

describe('📌 algo888 — the served header and notes', () => {
  it('NEGATIVE: a claim-less payload prints no USIC line (never GnT’s 2115)', async () => {
    spy(ALGO);
    const { container } = mount('algo888');
    await screen.findByText(/my 100,000 position/);
    expect(screen.queryByTestId('gnt-claim')).toBeNull();
    expect(container.querySelector('.gnt-usic')).toBeNull();
    expect(container.textContent).not.toMatch(/USIC/);
    expect(container.textContent).not.toMatch(/2115|2,115/);
  });

  it('claim_text is printed verbatim when served, and the legacy line is not printed beside it', async () => {
    spy(GNT_NEW);
    const { container } = mount();
    const claim = await screen.findByTestId('gnt-claim');
    expect(claim.textContent).toBe(` · ${CLAIM}`);
    expect(container.querySelectorAll('.gnt-usic')).toHaveLength(1);
  });

  it('source_text, gajjala_text and style are printed verbatim when served', async () => {
    spy(ALGO);
    mount('algo888');
    expect((await screen.findByTestId('gnt-source')).textContent).toBe(` · ${SOURCE_TEXT}`);
    expect(screen.getByTestId('gnt-gajjala').textContent).toBe(GAJJALA_TEXT);
    const style = screen.getByTestId('gnt-style');
    expect(style.textContent).toBe(STYLE);
    expect(style.classList.contains('gnt-dim')).toBe(true);
    expect(screen.getByRole('link', { name: /@algo888/ }).getAttribute('href')).toBe('https://stocktwits.com/algo888');
  });

  for (const [name, v] of [['null', null], ['empty', ''], ['absent', undefined]] as const) {
    it(`NEGATIVE: source_text, gajjala_text and style ${name} → none of the three printed`, async () => {
      const p: any = { ...ALGO, source_text: v, gajjala_text: v, style: v };
      if (v === undefined) { delete p.source_text; delete p.gajjala_text; delete p.style; }
      spy(p);
      mount('algo888');
      await screen.findByText(/my 100,000 position/);
      expect(screen.queryByTestId('gnt-source')).toBeNull();
      expect(screen.queryByTestId('gnt-gajjala')).toBeNull();
      expect(screen.queryByTestId('gnt-style')).toBeNull();
    });
  }

  it('NEGATIVE: an unflagged account (gajjala_text null) prints no Gajjala line', async () => {
    spy(GNT_NEW);
    mount();
    await screen.findByTestId('gnt-claim');
    expect(screen.queryByTestId('gnt-gajjala')).toBeNull();
    expect(screen.queryByText(/Gajjala/)).toBeNull();
  });
});

describe('📌 algo888 — the board types no served word', () => {
  it('NEGATIVE: GntBoard.tsx types no "StockTwits" and no "algo888" outside TRADER_TABS', async () => {
    const src = await readSource('src/components/GntBoard.tsx');
    const a = src.indexOf('export const TRADER_TABS');
    expect(a).toBeGreaterThan(-1);
    const e = src.indexOf('];', a);
    expect(src.slice(a, e)).toContain("{ key: 'algo888', label: 'algo888' }");
    const rest = src.slice(0, a) + src.slice(e);
    expect(rest).not.toMatch(/stocktwits/i);
    expect(rest).not.toMatch(/algo888/i);
  });

  it('NEGATIVE: the board types no claim words of its own for the new fields (they print the served value)', async () => {
    const src = await readSource('src/components/GntBoard.tsx');
    for (const need of ['{d.source_text}', '{d.claim_text}', '{d.gajjala_text}', '{d.style}']) expect(src).toContain(need);
    for (const id of ['gnt-source', 'gnt-claim', 'gnt-gajjala', 'gnt-style']) expect(src).toContain(`data-testid="${id}"`);
  });
});
