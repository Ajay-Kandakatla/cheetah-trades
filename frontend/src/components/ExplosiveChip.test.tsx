import { describe, it, expect, vi, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import { ExplosiveChip } from './ExplosiveChip';
import type { ExplosiveRead, ExplosiveStudy } from '../lib/bounceRoom';

/* 🧨 ExplosiveChip — the rules it must never break:
 *   1. no read → NO chip (coverage is honest; a missing band is not a verdict);
 *   2. the null / pending branch is MUTED and never wears the `good` tone — a
 *      fallback ordering dressed as a signal is the Keltner/AMD mistake;
 *   3. it NEVER fetches: every board already holds the read;
 *   4. the tooltip says what the study says, including that the read is
 *      closed-bar and, on the tile path, that today's low is not in it.
 */
const STUDY: ExplosiveStudy = {
  headline: 'MEASURED 2026-09-15: NO SIGNAL SEPARATES (no lift beyond 5.1pp) — ranked by floor-held + room instead',
  body: 'one regime, 2025-03 → 2026-08',
};

const NULL_READ: ExplosiveRead = {
  score: null, grade: null, intact: true, session_low: true,
  components: [{ key: 'room_pct', label: 'room 30%' }, { key: 'intact', label: 'floor held' }],
  room: { state: 'ROOM', room_pct: 30, atr_days: 3, band: null, at_highs: false },
  measured: { status: 'no_signal', mdl: 5.1 },
};

describe('ExplosiveChip', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('renders NOTHING without a read (negative)', () => {
    const { container } = render(<ExplosiveChip read={null} study={STUDY} />);
    expect(container.innerHTML).toBe('');
    expect(render(<ExplosiveChip study={STUDY} />).container.innerHTML).toBe('');
  });

  it('never fetches — the page already holds the read', () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    render(<ExplosiveChip read={NULL_READ} study={STUDY} />);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('null branch: muted tone, room + floor text, and NEVER the good class', () => {
    const { container } = render(<ExplosiveChip read={NULL_READ} study={STUDY} />);
    const el = container.querySelector('span')!;
    expect(el.textContent).toBe('🧨 room +30% · floor held');
    expect(el.className).toContain('cm-badge-explosive-muted');
    expect(el.className).not.toContain('good');
    expect(el.className).not.toContain('cm-badge-growth');
  });

  it('pending behaves exactly like no_signal (negative — nothing waits on the study)', () => {
    const pending = { ...NULL_READ, measured: { status: 'pending' } };
    const { container } = render(<ExplosiveChip read={pending} study={{ ...STUDY, status: 'pending' }} />);
    expect(container.querySelector('span')!.className).toContain('explosive-muted');
    expect(container.textContent).toContain('floor held');
  });

  it('separates branch: the served score, no muted class', () => {
    const sep = { ...NULL_READ, score: 0.82, grade: 'high' as const, measured: { status: 'separates' } };
    const { container } = render(<ExplosiveChip read={sep} study={STUDY} />);
    const el = container.querySelector('span')!;
    expect(el.textContent).toBe('🧨 0.82');
    expect(el.className).toContain('cm-badge-explosive');
    expect(el.className).not.toContain('explosive-muted');
    expect(el.className).not.toContain('good');
  });

  it('the "next-open" suffix appears ONLY under convention N', () => {
    const sep = { ...NULL_READ, score: 0.82, measured: { status: 'separates' } };
    expect(render(<ExplosiveChip read={{ ...sep, convention: 'N' }} />).container.textContent)
      .toContain('next-open');
    expect(render(<ExplosiveChip read={{ ...sep, convention: 'P' }} />).container.textContent)
      .not.toContain('next-open');
    expect(render(<ExplosiveChip read={sep} />).container.textContent).not.toContain('next-open');
  });

  it('the tooltip carries the components, the study headline and the closed-bar note', () => {
    const { container } = render(<ExplosiveChip read={NULL_READ} study={STUDY} />);
    const t = container.querySelector('span')!.getAttribute('title')!;
    expect(t).toContain('room 30% · floor held');
    expect(t).toContain(STUDY.headline);
    expect(t).toContain('closed-bar read; live volume not included');
    expect(t).not.toContain("today's low not in the read");
  });

  it('says today’s low is missing on the tile path (session_low false)', () => {
    const { container } = render(<ExplosiveChip read={{ ...NULL_READ, session_low: false }} study={STUDY} />);
    expect(container.querySelector('span')!.getAttribute('title'))
      .toContain("today's low not in the read");
  });

  it('wears the class family of the surface it is dropped into', () => {
    for (const cls of ['cm-badge', 'hs-badge', 'sb-chip', 'bd-gchip', 'eg']) {
      const { container } = render(<ExplosiveChip read={NULL_READ} className={cls} />);
      expect(container.querySelector('span')!.className).toContain(`${cls}-explosive`);
    }
  });
});
