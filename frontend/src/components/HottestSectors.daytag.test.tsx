/* 📰 Sector day-tags on the 🔥 Hottest board — Ajay 2026-09-19:
 *
 *   "Also for the hot sectors if you see any postive news I would like you to
 *    see a bullish and bearish case result for a stocks and add it to the
 *    sector as a tag for that day."
 *
 * The assertions that carry the feature are the ones that stop a fluent
 * paragraph of LLM prose from reading as a call: BOTH cases always render,
 * neither is given more room than the other, and the tile says on its face
 * that nothing here is measured.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HottestSectors, dayTagChipLabel, dayTagTitle, type HsDayTag } from './HottestSectors';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';

const TAG: HsDayTag = {
  date: '2026-09-19',
  sector: 'Technology',
  symbol: 'NVDA',
  company: 'Nvidia',
  positive: true,
  why_positive: 'a supply agreement was announced',
  bull: 'The announced agreement extends demand visibility past the current '
      + 'quarter, and the sector is leading the benchmark over five days.',
  bear: 'The same agreement concentrates revenue in one counterparty, and the '
      + 'name is already extended against its own sector over twenty-one days.',
  headline_count: 4,
  headlines: [
    { title: 'Chipmaker signs multi-year supply agreement', source: 'Reuters',
      url: 'https://example.test/story', published: 1_789_800_000 },
    { title: 'Analysts raise estimates after the deal', source: 'Yahoo',
      url: 'https://example.test/two', published: 1_789_790_000 },
  ],
  trigger: {
    title: 'Chipmaker signs multi-year supply agreement',
    url: 'https://example.test/story',
    source: 'Reuters',
    published: 1_789_800_000,
  },
  facts: { sector: 'Technology', symbol: 'NVDA' },
  read_by: 'local',
  measured: false,
};

const NAME = {
  symbol: 'NVDA', name: 'Nvidia', industry: 'Semiconductors',
  rel_1d: 1.2, rel_5d: 3.0, rel_21d: 8.0,
  sales_yoy: 55.0, sales_tier: 'explosive', q_eps_yoy: 60.0,
  net_margin: 50.0, eq_score: 80, next_earnings: null,
};

function payload(day_tag: HsDayTag | null) {
  return {
    as_of: '2026-09-19', benchmark: 'RSP', sorted_by: 'rel_5d',
    legs: ['rel_1d', 'rel_5d', 'rel_21d'],
    day_tags_as_of: day_tag ? day_tag.date : null,
    sectors: [{
      group: 'Technology', n_full: 305, sampled_of: 305, sampled_used: 40,
      basis: 'rotation grid sample', n_measured: 40,
      rel_1d: 0.5, rel_5d: 2.0, rel_21d: 4.0,
      names: [NAME], names_total: 305,
      industries: [{
        group: 'Semiconductors', n_full: 23, ranked: true, thin: false,
        basis: 'rotation grid sample',
        rel_1d: 0.5, rel_5d: 2.0, rel_21d: 4.0, names: [NAME], names_total: 23,
      }],
      day_tag,
    }],
  };
}

function stub(body: unknown) {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(() =>
    Promise.resolve({ ok: true, status: 200, json: async () => body })));
}
function memStorage() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(), key: (i: number) => [...m.keys()][i] ?? null,
    get length() { return m.size; },
  };
}
const view = () => render(<MemoryRouter><HottestSectors /></MemoryRouter>);

beforeEach(() => { vi.stubGlobal('localStorage', memStorage()); _resetSignalWatchlist(); });
afterEach(() => { vi.unstubAllGlobals(); _resetSignalWatchlist(); });

describe('the chip', () => {
  it('names the stock the tag is about', () => {
    expect(dayTagChipLabel(TAG)).toBe('📰 NVDA');
  });

  it('renders beside the sector when the day produced a tag', async () => {
    stub(payload(TAG));
    view();
    expect(await screen.findByTitle(/bull case AND a bear case/i)).toBeTruthy();
    expect(screen.getByText('📰 NVDA')).toBeTruthy();
  });

  it('IS ABSENT when the sector has no tag — the board is unchanged', async () => {
    stub(payload(null));
    view();
    await screen.findByRole('button', { name: /Technology/ });
    expect(screen.queryByText('📰 NVDA')).toBeNull();
    expect(screen.queryByText(/Bull case/i)).toBeNull();
  });

  it('the tooltip leads with what this is NOT', () => {
    const t = dayTagTitle(TAG);
    expect(t).toMatch(/NOT measured/);
    expect(t).toMatch(/not a signal/i);
    expect(t).toMatch(/not advice/i);
    expect(t).toMatch(/4 headlines read by local/);
  });

  it('the tooltip does not claim headlines it does not have', () => {
    const t = dayTagTitle({ ...TAG, headline_count: 1, read_by: null });
    expect(t).toMatch(/1 headline read/);
    expect(t).not.toMatch(/1 headlines/);
    expect(t).not.toMatch(/read by null/);
  });
});

describe('the expanded tag', () => {
  async function open() {
    stub(payload(TAG));
    view();
    fireEvent.click(await screen.findByText('📰 NVDA'));
    return waitFor(() => screen.getByText(/Bull case/i));
  }

  it('shows BOTH cases, never one', async () => {
    await open();
    expect(screen.getByText(/Bull case/i)).toBeTruthy();
    expect(screen.getByText(/Bear case/i)).toBeTruthy();
    expect(screen.getByText(/extends demand visibility/)).toBeTruthy();
    expect(screen.getByText(/concentrates revenue in one counterparty/)).toBeTruthy();
  });

  it('gives the two cases EQUAL WEIGHT — same element, same class shape', async () => {
    await open();
    const cases = document.querySelectorAll('.hs-daytag__case');
    expect(cases.length).toBe(2);
    // A bear case rendered in a smaller/quieter container than the bull case
    // is how a briefing turns into a recommendation without anyone deciding to.
    expect(cases[0].className).toContain('hs-daytag__case');
    expect(cases[1].className).toContain('hs-daytag__case');
    expect(cases[0].querySelector('p')?.tagName)
      .toBe(cases[1].querySelector('p')?.tagName);
  });

  it('says on its face that nothing here is measured', async () => {
    await open();
    const foot = document.querySelector('.hs-daytag__foot');
    expect(foot?.textContent).toMatch(/Nothing here is measured/i);
    expect(foot?.textContent).toMatch(/no edge is claimed/i);
    expect(foot?.textContent).toMatch(/gates no alert/i);
  });

  it('links the headline that triggered it, with its source', async () => {
    await open();
    // Scoped: the trigger title also appears in the "headlines read" list.
    const trig = document.querySelector('.hs-daytag__trigger')!;
    const a = within(trig as HTMLElement).getByText('Chipmaker signs multi-year supply agreement');
    expect(a.getAttribute('href')).toBe('https://example.test/story');
    expect(a.getAttribute('rel')).toBe('noreferrer');
    expect(document.querySelector('.hs-daytag__src')?.textContent).toMatch(/Reuters/);
  });

  it('SHOWS EVERY HEADLINE IT READ, so the grounding can be checked', async () => {
    // "Grounded in the headlines" is only a claim if you cannot see them.
    await open();
    const reads = document.querySelector('.hs-daytag__reads');
    expect(reads?.querySelector('summary')?.textContent).toMatch(/2 headlines read/);
    expect(reads?.querySelectorAll('li').length).toBe(2);
    expect(reads?.textContent).toMatch(/Analysts raise estimates after the deal/);
  });

  it('does not render an empty reads list when there is only the trigger', async () => {
    stub(payload({ ...TAG, headlines: [TAG.headlines![0]] }));
    view();
    fireEvent.click(await screen.findByText('📰 NVDA'));
    await waitFor(() => screen.getByText(/Bull case/i));
    expect(document.querySelector('.hs-daytag__reads')).toBeNull();
  });

  it('survives a tag with no headlines array at all', async () => {
    stub(payload({ ...TAG, headlines: null }));
    view();
    fireEvent.click(await screen.findByText('📰 NVDA'));
    await waitFor(() => screen.getByText(/Bull case/i));
    expect(document.querySelector('.hs-daytag__reads')).toBeNull();
    expect(screen.getByText(/Bear case/i)).toBeTruthy();
  });

  it('carries its own DATE, so a weekend board says which day it is from', async () => {
    await open();
    expect(document.querySelector('.hs-daytag__meta')?.textContent)
      .toMatch(/2026-09-19/);
  });

  it('names who read it, so it can never pass as measurement', async () => {
    await open();
    expect(document.querySelector('.hs-daytag__meta')?.textContent)
      .toMatch(/read by local/);
  });

  it('a NEUTRAL read says so instead of implying positive', async () => {
    stub(payload({ ...TAG, positive: false }));
    view();
    fireEvent.click(await screen.findByText('📰 NVDA'));
    await waitFor(() => screen.getByText(/reads neutral \/ mixed/i));
    expect(screen.queryByText(/reads positive/i)).toBeNull();
    // Both cases still render — a neutral day is still two-sided.
    expect(screen.getByText(/Bull case/i)).toBeTruthy();
    expect(screen.getByText(/Bear case/i)).toBeTruthy();
  });

  it('survives a tag with no trigger headline', async () => {
    stub(payload({ ...TAG, trigger: null }));
    view();
    fireEvent.click(await screen.findByText('📰 NVDA'));
    await waitFor(() => screen.getByText(/Bull case/i));
    expect(document.querySelector('.hs-daytag__trigger')).toBeNull();
    expect(screen.getByText(/Bear case/i)).toBeTruthy();
  });

  it('collapses again on a second click', async () => {
    await open();
    fireEvent.click(screen.getByText('📰 NVDA'));
    await waitFor(() => expect(screen.queryByText(/Bull case/i)).toBeNull());
  });
});

describe('the tag does not disturb the board', () => {
  it('opening the tag does NOT expand the sector itself', async () => {
    // Two independent disclosures on one row. Clicking the 📰 chip must not
    // drag the sector's membership open underneath it.
    stub(payload(TAG));
    view();
    const sectorBtn = await screen.findByRole('button', { name: /Technology/ });
    fireEvent.click(await screen.findByText('📰 NVDA'));
    await waitFor(() => screen.getByText(/Bull case/i));
    expect(sectorBtn.getAttribute('aria-expanded')).toBe('false');
  });

  it('the sector still opens normally with the tag present', async () => {
    stub(payload(TAG));
    view();
    const sectorBtn = await screen.findByRole('button', { name: /Technology/ });
    fireEvent.click(sectorBtn);
    await waitFor(() => expect(sectorBtn.getAttribute('aria-expanded')).toBe('true'));
    // And the tag chip is still there, un-toggled, after the sector opened.
    const chip = screen.getByText('📰 NVDA');
    expect(chip.getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByText(/Bull case/i)).toBeNull();
  });

  it('the sector row keeps its own numbers beside the chip', async () => {
    stub(payload(TAG));
    view();
    const row = (await screen.findByText('📰 NVDA')).closest('tr')!;
    // n_full still prints; the chip took no column and displaced nothing.
    expect(within(row).getByText(/305/)).toBeTruthy();
    expect(within(row).getByText('+2.0%')).toBeTruthy();
  });
});
