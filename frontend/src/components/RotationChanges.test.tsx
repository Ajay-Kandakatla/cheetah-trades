/* 🔄 What changed (2026-09-12).
 *
 * Ajay: "this whole thing is super messay ... I am trying to see what changed
 * if there is no change continously same sectors continue to show the top for
 * example energy has been continous."
 *
 * The behaviour that matters: when nothing moved, the strip SAYS SO with the
 * streak — "no rank change since 2026-09-11 · Energy #1 · 8d still leading" —
 * instead of rendering nothing (reads as a broken scan) or re-rendering the
 * whole board (what he called messy).
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import RotationChanges, {
  headline, moverLines, streakText, grainTag, MAX_MOVERS,
} from './RotationChanges';

const QUIET = {
  grain: 'all', as_of: '2026-09-12', baseline: '2026-09-11', quiet: true,
  grains: {
    sectors: { top: ['Energy', 'Technology'], streaks: { Energy: 8, Technology: 2 },
               entered: [], left: [], moved: [], quiet: true },
    themes: { top: ['ai_semis'], streaks: { ai_semis: 3 },
              entered: [], left: [], moved: [], quiet: true },
  },
};

const MOVED = {
  grain: 'all', as_of: '2026-09-12', baseline: '2026-09-11', quiet: false,
  grains: {
    sectors: { top: ['Energy'], streaks: { Energy: 8 }, entered: [], left: [],
               moved: [{ group: 'Utilities', rank: 3, prev_rank: 7, delta: 4 }],
               quiet: false },
    themes: { top: ['robotics'], streaks: { robotics: 1 },
              entered: [{ group: 'robotics', rank: 2, prev_rank: 9 }],
              left: [{ group: 'quantum', rank: 11, prev_rank: 5 }],
              moved: [{ group: 'robotics', rank: 2, prev_rank: 9, delta: 7 }],
              quiet: false },
  },
};

function stub(body: unknown, ok = true) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok, status: ok ? 200 : 503, json: () => Promise.resolve(body),
  } as any));
}
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

// ───────────────────────────────────────────────────────────── pure helpers
describe('streakText — "Energy has been continous"', () => {
  it('turns a held rank into ONE fact with its length', () => {
    expect(streakText('Energy', 1, 8)).toBe('Energy #1 · 8d');
  });

  it('NEGATIVE: a one-session streak is not worth the pixels', () => {
    expect(streakText('Energy', 1, 1)).toBe('Energy #1');
    expect(streakText('Energy', 1, null)).toBe('Energy #1');
    expect(streakText('Energy', 1, undefined)).toBe('Energy #1');
  });
});

describe('headline', () => {
  it('names the SECTOR leader — the grain he asked about', () => {
    expect(headline(QUIET)).toEqual({ group: 'Energy', days: 8 });
  });

  it('falls through to a finer grain when the build carries no sectors', () => {
    expect(headline({ grains: { themes: { top: ['ai_semis'], streaks: { ai_semis: 3 } } } }))
      .toEqual({ group: 'ai_semis', days: 3 });
  });

  it('NEGATIVE: an empty payload invents no leader', () => {
    expect(headline({})).toBeNull();
    expect(headline({ grains: { sectors: { top: [] } } })).toBeNull();
  });
});

describe('moverLines', () => {
  it('puts CROSSINGS ahead of re-orderings inside the band', () => {
    const { lines } = moverLines(MOVED);
    expect(lines[0].text).toContain('robotics');
    expect(lines[0].kind).toBe('in');
    expect(lines.map((l) => l.kind)).toEqual(['in', 'out', 'up']);
  });

  it('prints a group ONCE even when it both entered and moved', () => {
    const { lines } = moverLines(MOVED);
    expect(lines.filter((l) => l.text.includes('robotics')).length).toBe(1);
  });

  it('encodes direction, not just movement: rank 7→3 is a CLIMB', () => {
    const { lines } = moverLines(MOVED);
    const util = lines.find((l) => l.text.includes('Utilities'))!;
    expect(util.text).toBe('▲ Utilities 7→3');
    expect(util.kind).toBe('up');
  });

  it('NEGATIVE: what does not fit is COUNTED, never silently dropped', () => {
    const many = Array.from({ length: 9 }, (_, i) => (
      { group: `g${i}`, rank: i + 1, prev_rank: i + 6, delta: 5 }));
    const { lines, extra } = moverLines(
      { grains: { themes: { entered: [], left: [], moved: many } } });
    expect(lines.length).toBe(MAX_MOVERS);
    expect(extra).toBe(9 - MAX_MOVERS);
  });

  it('NEGATIVE: a quiet payload yields no mover chips at all', () => {
    expect(moverLines(QUIET)).toEqual({ lines: [], extra: 0 });
  });

  it('grainTag says WHERE a move happened', () => {
    expect(grainTag('cohorts')).toBe('cohort');
    expect(grainTag('industries')).toBe('industry');
    expect(grainTag('sectors')).toBe('sector');
    expect(grainTag('themes')).toBe('theme');
  });
});

// ────────────────────────────────────────────────────────────── the render
describe('RotationChanges', () => {
  it('says NO CHANGE in words, with the streak — the answer he asked for', async () => {
    stub(QUIET);
    render(<RotationChanges />);
    expect(await screen.findByText(/no rank change since 2026-09-11/)).toBeInTheDocument();
    expect(screen.getByText(/Energy #1 · 8d still leading/)).toBeInTheDocument();
  });

  it('leads with the delta when something DID move', async () => {
    stub(MOVED);
    render(<RotationChanges />);
    expect(await screen.findByText('＋ robotics 9→2')).toBeInTheDocument();
    expect(screen.getByText('－ quantum 5→11')).toBeInTheDocument();
    expect(screen.getByText('▲ Utilities 7→3')).toBeInTheDocument();
    // the steady leader survives a busy day — it is the continuity he reads for
    expect(screen.getByText(/steady: Energy #1 · 8d/)).toBeInTheDocument();
    expect(screen.queryByText(/no rank change/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: the first session says so instead of inventing a shift', async () => {
    stub({ grain: 'all', quiet: true, baseline: null,
           reason: 'first snapshot — no prior session to compare',
           grains: { sectors: { top: ['Energy'], streaks: { Energy: 1 },
                                entered: [], left: [], moved: [], quiet: true } } });
    render(<RotationChanges />);
    expect(await screen.findByText(/first snapshot — no prior session to compare/))
      .toBeInTheDocument();
    // no baseline date is claimed
    expect(screen.queryByText(/no rank change since/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: a payload with no grains renders NOTHING, not a machine reason', async () => {
    stub({ grain: 'all', quiet: true, baseline: null, reason: 'no as_of', grains: {} });
    const { container } = render(<RotationChanges />);
    await act(async () => { await Promise.resolve(); });
    expect(container.querySelector('.rc')).toBeNull();
    expect(screen.queryByText(/no as_of/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: a failed fetch is silent — it rides above a strip that works', async () => {
    stub({}, false);
    const { container } = render(<RotationChanges />);
    await act(async () => { await Promise.resolve(); });
    expect(container.querySelector('.rc')).toBeNull();
  });
});
