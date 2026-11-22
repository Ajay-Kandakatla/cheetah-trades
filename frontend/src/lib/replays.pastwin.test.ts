/* 🏆 past-winner tag — the pure chip helper (2026-11-22). Ajay, verbatim: "MEDS was a part winner that went up after
 * hours.. Please actually add a past winner tag in our new ones looks for past winnings please if found again..".
 * Every chip word is SERVED; no list → no chip. NEGATIVES throughout. */
import { describe, expect, it } from 'vitest';
import { rpPastWinChips } from './replays';

const win = (text: unknown): any => ({ day: '2026-09-16', kind: 'single_day', close_gain_pct: 274.7, file: 'x.mp4', sub: 'winners', text });

describe('rpPastWinChips', () => {
  it('prints each served text in served order, then the served "+N more"', () => {
    const r = rpPastWinChips({
      past_winner: [win('🏆 past winner 09-16 +601% multi-day'), win('🏆 past winner 09-16 +275%'), win('🏆 past winner 09-15 +87%')],
      past_winner_count: 5, past_winner_more_text: '+2 more',
    });
    expect(r.wins).toEqual(['🏆 past winner 09-16 +601% multi-day', '🏆 past winner 09-16 +275%', '🏆 past winner 09-15 +87%']);
    expect(r.more).toBe('+2 more');
  });
  it('NEGATIVE: no served list (no past win) → no chip at all', () => {
    expect(rpPastWinChips({})).toEqual({ wins: [], more: '' });
    expect(rpPastWinChips(null)).toEqual({ wins: [], more: '' });
    expect(rpPastWinChips(undefined)).toEqual({ wins: [], more: '' });
    expect(rpPastWinChips({ past_winner: null })).toEqual({ wins: [], more: '' });
    expect(rpPastWinChips({ past_winner: 'x' as any })).toEqual({ wins: [], more: '' });
  });
  it('NEGATIVE: an empty list never prints a stray "+N more"', () => {
    expect(rpPastWinChips({ past_winner: [], past_winner_more_text: '+2 more' })).toEqual({ wins: [], more: '' });
  });
  it('NEGATIVE: junk entries and non-string texts are dropped; the FE composes no word', () => {
    const r = rpPastWinChips({ past_winner: [null as any, 5 as any, win(7), win(''), win('🏆 past winner 09-15 +87%')],
      past_winner_more_text: 3 as any });
    expect(r).toEqual({ wins: ['🏆 past winner 09-15 +87%'], more: '' });
  });
  it('NEGATIVE: exactly three wins with a null more text → no "+N more"', () => {
    const r = rpPastWinChips({ past_winner: [win('a'), win('b'), win('c')], past_winner_count: 3, past_winner_more_text: null });
    expect(r.wins).toHaveLength(3);
    expect(r.more).toBe('');
  });
});
