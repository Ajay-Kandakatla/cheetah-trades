/* /alerts — the 📌 trader hold (BUILD_SPEC26 A2; critic F2, 2026-10-27).
 *
 * Ajay 2026-10-27: "Add them to Gajjals, they are pretty good". A 📌 add's 🧠
 * push is HELD while today's volume is under GG's floor. Its words are SERVED
 * (backend trader_names.TRADER_HOLD_TEXT, via alert_status: `held_text` on the
 * row, `trader_held_text` on the pass) — this page prints them and types none.
 * Fixtures are synthetic; the served sentence below stands in for the backend's.
 */
import { describe, it, expect } from 'vitest';
import { GAJJALA_POTENTIAL_KEYS, ggPotentialChipText, ggPotentialRowWord } from './Alerts';

async function readSource(rel: string): Promise<string> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fs: any = mod?.default || mod;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const SERVED = 'held: SERVED-WORDS-FROM-THE-BACKEND';
const item = (extra: Record<string, unknown> = {}) => ({
  date: '2026-10-27', symbol: 'MXCT', setup: 'bull_flag', at: '2026-10-27T10:41:00-04:00', kind: 'armed',
  text: 'MXCT · line', url: null, push_state: null, push_at: null, held: 'trader_under_floor', ...extra,
});

describe('Alerts — the 📌 trader hold prints its served words (2026-10-27)', () => {
  it('a row carrying held_text prints it verbatim', () => {
    expect(ggPotentialRowWord(item({ held_text: SERVED }))).toBe(SERVED);
  });

  it('NEGATIVE: a settled push outranks the hold — a sent potential never reads held', () => {
    expect(ggPotentialRowWord(item({ held_text: SERVED, push_state: 'pushed' }))).toBe('📲 sent');
  });

  it('NEGATIVE: null / "" / absent held_text → the reason words as before, never an empty row', () => {
    for (const ht of [null, '', '   ', undefined]) {
      expect(ggPotentialRowWord(item({ held_text: ht }))).toBe('held: trader under floor');
    }
    expect(ggPotentialRowWord(item({ held: 'muted', held_text: null }))).toBe('held: his first 15 minutes');
  });

  it('trader_held is a 🧠 counter chip, worded from the served pass text', () => {
    expect(GAJJALA_POTENTIAL_KEYS).toContain('trader_held');
    expect(ggPotentialChipText('trader_held', 2, SERVED)).toBe(`2 ${SERVED}`);
  });

  it('NEGATIVE: no served words (an older API) → the generic counter words, never invented ones', () => {
    for (const t of [null, undefined, '', '  ']) expect(ggPotentialChipText('trader_held', 3, t)).toBe('3 trader held');
    expect(ggPotentialChipText('muted', 1, SERVED)).toBe('1 held: his first 15 minutes');   // other chips ignore it
  });

  it('NEGATIVE: Alerts.tsx types no 📌 hold words in code', async () => {
    const src = (await readSource('src/pages/Alerts.tsx'))
      .replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/[^\n]*/g, '$1');
    expect(src).not.toMatch(/📌|volume floor|listed and read/);
    expect(src).toContain('it.held_text');
    expect(src).toContain('pass?.trader_held_text');
  });
});
