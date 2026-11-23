/* 🎾 parseAxis keeps a served `axis.lead` (2026-11-23, rswatch spec §3.5, WP fe-live test 1).
 * Ajay 2026-11-23: "In the reversal squeeze can you make the charts same as in watch list please".
 * The 🎾 card's 5-minute frame serves the prior session's tail in `lead` slots AHEAD of today's 04:00 (start_epoch /
 * from_et unchanged). The key is kept ONLY for a served integer > 0. NEGATIVES: absent / 0 / negative / 1.5 / a string /
 * NaN / Infinity → NO `lead` key at all, the rest of the axis identical; every frame of the committed Watch fixture parses
 * with no `lead` key (a Watch payload parses byte-identical). */
import { describe, expect, it } from 'vitest';
import watchFixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import { parseFrame, parseGgw, type GgwBoard } from './gajjalaWatch';

const START = Date.UTC(2026, 10, 23, 9, 0, 0) / 1000;

const rawFrame = (axisExtra: Record<string, unknown> = {}) => ({
  tf: '5m', label: '5-min',
  tile: { symbol: 'LEAD', bars: [{ t: '2026-11-20 15:20', o: 1, h: 1.1, l: 0.9, c: 1, v: 10 },
    { t: '2026-11-23 04:05', o: 1, h: 1.1, l: 0.9, c: 1, v: 10 }], curves: [] },
  axis: {
    slots: 252, x: [3, 60], shade: [{ from_slot: 12, to_slot: 60, kind: 'ah' }], ticks: [{ slot: 0, label: 'Nov 20' }],
    start_epoch: START, frame_min: 5, from_et: '04:00', to_et: '20:00', ...axisExtra,
  },
});

describe('🎾 parseAxis — served axis.lead', () => {
  it('keeps a served integer > 0', () => {
    const f = parseFrame(rawFrame({ lead: 60 }), 'LEAD')!;
    expect(f.axis!.lead).toBe(60);
    const plain = parseFrame(rawFrame(), 'LEAD')!;
    expect(f.axis).toEqual({ ...plain.axis, lead: 60 });
  });

  it.each([
    ['absent', undefined],
    ['zero', 0],
    ['negative', -60],
    ['a fraction', 1.5],
    ['a string', '60'],
    ['NaN', NaN],
    ['Infinity', Infinity],
    ['null', null],
  ])('NEGATIVE %s → no lead key at all, the rest of the axis unchanged', (_name, lead) => {
    const raw = lead === undefined ? rawFrame() : rawFrame({ lead });
    const f = parseFrame(raw, 'LEAD')!;
    expect(f.axis).not.toBeNull();
    expect('lead' in f.axis!).toBe(false);
    expect(f.axis).toEqual(parseFrame(rawFrame(), 'LEAD')!.axis);
  });

  it('NEGATIVE every frame of the committed Watch fixture parses with no lead key', () => {
    const b = parseGgw(watchFixture) as GgwBoard;
    expect(b && b.state).toBe('ok');
    let n = 0;
    for (const r of b.rows) {
      for (const f of r.frames) {
        if (!f.axis) continue;
        n += 1;
        expect('lead' in f.axis).toBe(false);
      }
    }
    expect(n).toBeGreaterThan(0);
  });
});
