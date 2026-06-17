import { describe, it, expect } from 'vitest';
import { marchToTarget, stageMeta } from './breakoutTargets';

/* "Marching toward R1 / R2" — distance from current price to the next trade-plan
   target (Ajay 2026-06-16: "if they are s2 and if they marching towards r1 or
   r2"). Locks the three branches (below R1 / between R1 and R2 / past R2), the
   % math, and the negatives (no price, no targets). */

describe('marchToTarget', () => {
  it('marches toward R1 when price is below R1', () => {
    // price 100, R1 110 (+10%), R2 120
    const m = marchToTarget(100, 110, 120);
    expect(m.state).toBe('to_r1');
    expect(m.label).toBe('→ R1');
    expect(m.pct).toBeCloseTo(10, 5);          // active target = R1
    expect(m.toR1Pct).toBeCloseTo(10, 5);
    expect(m.toR2Pct).toBeCloseTo(20, 5);
  });

  it('marches toward R2 once price has cleared R1 but is below R2', () => {
    // price 112 is above R1 (110), below R2 (120) → +7.142...% to R2
    const m = marchToTarget(112, 110, 120);
    expect(m.state).toBe('to_r2');
    expect(m.label).toBe('→ R2');
    expect(m.pct).toBeCloseTo(((120 - 112) / 112) * 100, 5);
    expect(m.toR1Pct).toBeCloseTo(((110 - 112) / 112) * 100, 5);  // negative, R1 below
  });

  it('flags Past R2 when price is at or above R2', () => {
    const m = marchToTarget(125, 110, 120);
    expect(m.state).toBe('past_r2');
    expect(m.label).toBe('Past R2');
    expect(m.pct).toBeNull();                   // no forward target → sinks in sort
  });

  it('treats price exactly at R2 as past R2 (boundary)', () => {
    expect(marchToTarget(120, 110, 120).state).toBe('past_r2');
  });

  it('treats price exactly at R1 as marching to R2 (boundary)', () => {
    // price == R1 is NOT below R1, so the active target becomes R2
    const m = marchToTarget(110, 110, 120);
    expect(m.state).toBe('to_r2');
    expect(m.pct).toBeCloseTo(((120 - 110) / 110) * 100, 5);
  });

  it('returns none when price is missing or non-positive (negative)', () => {
    expect(marchToTarget(null, 110, 120).state).toBe('none');
    expect(marchToTarget(undefined, 110, 120).state).toBe('none');
    expect(marchToTarget(0, 110, 120).state).toBe('none');
    expect(marchToTarget(-5, 110, 120).pct).toBeNull();
  });

  it('returns none (with no pct) when the row has no R1/R2 targets (negative)', () => {
    const m = marchToTarget(100, null, null);
    expect(m.state).toBe('none');
    expect(m.pct).toBeNull();
    expect(m.toR1Pct).toBeNull();
    expect(m.toR2Pct).toBeNull();
  });
});

describe('stageMeta', () => {
  it('marks Stage 2 as the buyable stage (green + isStage2)', () => {
    const s = stageMeta(2, 'Stage 2');
    expect(s.isStage2).toBe(true);
    expect(s.tone).toContain('10b981');         // positive/green
    expect(s.label).toBe('Stage 2');
  });

  it('marks Stage 4 as avoid (red, not Stage 2)', () => {
    const s = stageMeta(4, 'Stage 4');
    expect(s.isStage2).toBe(false);
    expect(s.tone).toContain('f87171');         // negative/red
  });

  it('mutes Stage 1 / Stage 3 and the unknown case (negative)', () => {
    expect(stageMeta(1).isStage2).toBe(false);
    expect(stageMeta(3).tone).toContain('94a3b8');   // slate
    const unknown = stageMeta(null, null);
    expect(unknown.isStage2).toBe(false);
    expect(unknown.label).toBe('—');
  });
});
