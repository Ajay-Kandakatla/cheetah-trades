import { describe, expect, it } from 'vitest';
import { hoverLines, timeTicks, type CmBar } from './chartMaps';

/* 🕐 Axis + hover on the 1-minute and weekly Support frames (2026-10-26).
 *
 * Ajay: "Can you build me 1 min bar chart and also 1 week bar chart in the
 * supply and demand".
 *
 * No axis code changed: 1-minute stamps ("YYYY-MM-DD HH:MM", RIGHT-labelled,
 * so the 04:00 minute reads 04:01) take the session path; weekly stamps are
 * Friday dates and take the month path. These pin that both land where they
 * should on the existing `timeTicks`. */

const pad = (n: number) => String(n).padStart(2, '0');

/** 960 one-minute bars for 2026-10-26, stamped 04:01 … 20:00 as the backend
 *  serves them: `pre` through the 09:30 stamp, RTH 09:31 … 16:00, `ah` after. */
function minuteBars(): CmBar[] {
  const out: CmBar[] = [];
  for (let k = 1; k <= 960; k++) {
    const mins = 4 * 60 + k;
    const hm = `${pad(Math.floor(mins / 60))}:${pad(mins % 60)}`;
    const c = 100 + k * 0.01;
    const bar: CmBar = { t: `2026-10-26 ${hm}`, o: c - 0.01, h: c + 0.02, l: c - 0.03, c, v: 100 + k };
    if (hm < '09:31') bar.s = 'pre';
    else if (hm > '16:00') bar.s = 'ah';
    out.push(bar);
  }
  return out;
}

/** 260 Friday-dated weekly bars ending 2026-10-30. */
function weeklyBars(): CmBar[] {
  const out: CmBar[] = [];
  const end = Date.UTC(2026, 9, 30);
  for (let k = 259; k >= 0; k--) {
    const d = new Date(end - k * 7 * 86_400_000);
    const c = 50 + (259 - k) * 0.1;
    out.push({ t: d.toISOString().slice(0, 10), o: c - 0.2, h: c + 0.5, l: c - 0.6, c, v: 1_000 });
  }
  return out;
}

describe('🕐 the 1-minute and weekly frames on the existing axis', () => {
  it('1-minute bars take the session axis', () => {
    const bars = minuteBars();
    expect(bars.length).toBe(960);
    expect(bars[0].t).toBe('2026-10-26 04:01');
    expect(bars[959].t).toBe('2026-10-26 20:00');
    const openAt = bars.findIndex((b) => b.t.endsWith('09:31'));
    const closeAt = bars.findIndex((b) => b.t.endsWith('16:00'));
    expect(timeTicks(bars)).toEqual([
      { i: 0, label: 'Oct 26' },
      { i: openAt, label: 'open' },
      { i: closeAt, label: '16:00' },
    ]);
  });

  it('weekly bars take the month axis', () => {
    const bars = weeklyBars();
    for (const b of bars) expect(new Date(`${b.t}T00:00:00Z`).getUTCDay(), b.t).toBe(5);
    const ticks = timeTicks(bars);
    expect(ticks.length).toBeGreaterThan(0);
    expect(ticks.length).toBeLessThanOrEqual(8);
    for (const t of ticks) {
      expect(t.label).toMatch(/^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)( '\d\d)?$/);
    }
  });

  it('NEGATIVE: a weekly axis never shows a session tick', () => {
    const labels = timeTicks(weeklyBars()).map((t) => t.label);
    expect(labels).not.toContain('open');
    expect(labels).not.toContain('16:00');
  });

  it('the hover readout names the forming week and a pre-market minute', () => {
    const forming: CmBar = { t: '2026-10-30', o: 1, h: 2, l: 0.5, c: 1.5, v: 10, s: 'forming' };
    expect(hoverLines(forming)[0]).toBe('2026-10-30 · forming');
    const pre = minuteBars()[0];
    expect(hoverLines(pre)[0]).toBe('2026-10-26 04:01 · pre');
    // NEGATIVE: an RTH minute carries no tape tag.
    const rth = minuteBars().find((b) => b.t.endsWith('10:00'))!;
    expect(hoverLines(rth)[0]).toBe('2026-10-26 10:00');
  });
});
