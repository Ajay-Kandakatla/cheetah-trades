/* 🏆 past-winner tag on 🎬 Replays cards (2026-11-22). Ajay, verbatim: "MEDS was a part winner that went up after
 * hours.. Please actually add a past winner tag in our new ones looks for past winnings please if found again..".
 * The day card and the 🏆 row print the served chip text (text only — no reel-by-file URL exists). NEGATIVES: no served
 * list → no chip; "+N more" only when served; the phone sheet wraps the chip. */
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import dayFixture from './__fixtures__/replays_2026_11_17.json';
import ReplaysBoard from './ReplaysBoard';
import ReplaysPastWinners from './ReplaysPastWinners';
import { API } from '../lib/apiBase';
import { RP_WINNERS_PATH } from '../lib/replays';

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));
const pw = (text: string, day = '2026-09-16') => ({ day, kind: 'single_day', close_gain_pct: 274.69, file: `${day}_MEDS_45x.mp4`, sub: 'winners', text });

function dayWithTags(): any {
  const d: any = clone((dayFixture as any).ready);
  const gp = d.groups[0].videos[0];
  gp.past_winner = [pw('🏆 past winner 09-16 +601% multi-day'), pw('🏆 past winner 09-16 +275%'), pw('🏆 past winner 09-15 +87%', '2026-09-15')];
  gp.past_winner_count = 5;
  gp.past_winner_more_text = '+2 more';
  const vivk = d.groups[1].videos[0];
  vivk.past_winner = [pw('🏆 past winner 11-03 +130%', '2026-11-03')];
  vivk.past_winner_count = 1;
  vivk.past_winner_more_text = null;
  return d;
}
const WIN: any = {
  title: '🏆 Past winners', tab: 'replays', state: 'ready', text: null, note: 'n', window: 'w', window_note: 'wn',
  summary_text: '2 videos', counts: {},
  rows: [{ key: 'sym-MEDS', symbol: 'MEDS', wins_text: '2 wins', videos: [
    { file: '2026-09-16_MEDS_45x.mp4', sub: 'winners', src: '/chart-maps/replays/winners/video/winners/2026-09-16_MEDS_45x.mp4',
      symbol: 'MEDS', kind_text: 'single-day', gain_text: '+275% on the close', spike_print: false,
      past_winner: [pw('🏆 won before 09-15 +87%', '2026-09-15')], past_winner_count: 1, past_winner_more_text: null },

    { file: '2026-09-15_MEDS_45x.mp4', sub: 'winners', src: '/chart-maps/replays/winners/video/winners/2026-09-15_MEDS_45x.mp4',
      symbol: 'MEDS', kind_text: 'single-day', gain_text: '+87% on the close', spike_print: false },
  ] }],
};

function stub(body: (url: string) => unknown) {
  const f = vi.fn(async (url: string) => ({ ok: true, status: 200, json: async () => clone(body(String(url))) }));
  vi.stubGlobal('fetch', f);
  return f;
}
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
function rule(src: string, sel: string): string | null {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = src.match(new RegExp(`(^|\\n)${esc}\\s*\\{([^}]*)\\}`));
  return m ? m[2] : null;
}

afterEach(() => { vi.unstubAllGlobals(); });

describe('🏆 tag on the day cards', () => {
  it('a tagged card prints each served chip, then "+N more"; text only (no link, no button)', async () => {
    stub(() => dayWithTags());
    const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=replays']}><ReplaysBoard /></MemoryRouter>);
    await waitFor(() => expect(r.container.querySelector('.rp-board[data-state="ready"]')).not.toBeNull());
    const gp = r.getByTestId('rp-card-GP_bull_flag_24x.mp4');
    expect(Array.from(gp.querySelectorAll('[data-testid="rp-pastwin"]')).map((e) => e.textContent)).toEqual([
      '🏆 past winner 09-16 +601% multi-day', '🏆 past winner 09-16 +275%', '🏆 past winner 09-15 +87%']);
    expect(gp.querySelector('[data-testid="rp-pastwin-more"]')!.textContent).toBe('+2 more');
    for (const chip of Array.from(gp.querySelectorAll('.rp-pastwin'))) {
      expect(chip.tagName).toBe('SPAN');
      expect(chip.closest('.rp-chips')).not.toBeNull();
      expect(chip.querySelector('a, button')).toBeNull();
    }
  });
  it('NEGATIVE: one win with a null more text → one chip, no "+N more"', async () => {
    stub(() => dayWithTags());
    const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=replays']}><ReplaysBoard /></MemoryRouter>);
    await waitFor(() => expect(r.container.querySelector('.rp-board[data-state="ready"]')).not.toBeNull());
    const vivk = r.getByTestId('rp-card-VIVK_kiss_fly_24x.mp4');
    expect(vivk.querySelectorAll('[data-testid="rp-pastwin"]')).toHaveLength(1);
    expect(vivk.querySelector('[data-testid="rp-pastwin-more"]')).toBeNull();
  });
  it('NEGATIVE: a card with no served past win prints no 🏆 chip (and the untagged fixture prints none at all)', async () => {
    stub(() => dayWithTags());
    let r = render(<MemoryRouter initialEntries={['/chart-maps?tab=replays']}><ReplaysBoard /></MemoryRouter>);
    await waitFor(() => expect(r.container.querySelector('.rp-board[data-state="ready"]')).not.toBeNull());
    const cenn = r.getByTestId('rp-card-CENN_reversal_squeeze_24x.mp4');
    expect(cenn.querySelector('.rp-pastwin')).toBeNull();
    expect(cenn.textContent).not.toContain('🏆');
    r.unmount();
    vi.unstubAllGlobals();
    stub(() => (dayFixture as any).ready);
    r = render(<MemoryRouter initialEntries={['/chart-maps?tab=replays']}><ReplaysBoard /></MemoryRouter>);
    await waitFor(() => expect(r.container.querySelector('.rp-board[data-state="ready"]')).not.toBeNull());
    expect(r.container.querySelector('.rp-board .rp-pastwin')).toBeNull();
  });
});

describe('🏆 "won before" on the 🏆 rows', () => {
  it('the later MEDS row carries its served chip; NEGATIVE: the earlier row carries none', async () => {
    stub((url) => (url === `${API}${RP_WINNERS_PATH}` ? WIN : (dayFixture as any).ready));
    const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=replays&winners=1&sym=MEDS']}><ReplaysPastWinners /></MemoryRouter>);
    await waitFor(() => expect(r.getByTestId('rpw-section').getAttribute('data-state')).toBe('loaded'));
    const later = r.getByTestId('rpw-row-winners-2026-09-16_MEDS_45x.mp4');
    expect(Array.from(later.querySelectorAll('[data-testid="rpw-pastwin"]')).map((e) => e.textContent)).toEqual(['🏆 won before 09-15 +87%']);
    expect(later.querySelector('[data-testid="rpw-pastwin-more"]')).toBeNull();
    const earlier = r.getByTestId('rpw-row-winners-2026-09-15_MEDS_45x.mp4');
    expect(earlier.querySelector('.rp-pastwin')).toBeNull();
  });
});

describe('📱 the chip wraps at 430 px (source guards)', () => {
  it('.rp-pastwin: min-width 0 + max-width 100% + wrapping text — NEGATIVE: a nowrap chip fails', async () => {
    const src = await readSource('src/styles/replays.css');
    const d = rule(src, '.rp-pastwin');
    const ok = (x: string | null) => !!x && /min-width:\s*0/.test(x) && /max-width:\s*100%/.test(x)
      && /white-space:\s*normal/.test(x) && /overflow-wrap:\s*anywhere/.test(x);
    expect(ok(d)).toBe(true);
    expect(ok(rule('.rp-pastwin { white-space: nowrap; }', '.rp-pastwin'))).toBe(false);
    expect(src).not.toMatch(/white-space:\s*nowrap/);
  });
  it('NEGATIVE: the FE types no chip word — both components print rpPastWinChips output only', async () => {
    for (const f of ['src/components/ReplaysBoard.tsx', 'src/components/ReplaysPastWinners.tsx']) {
      const tsx = await readSource(f);
      expect(tsx).toContain('rpPastWinChips(v)');
      expect(tsx).not.toMatch(/past winner|won before|more'/);
    }
  });
});
