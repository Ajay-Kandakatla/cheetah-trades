import { describe, it, expect } from 'vitest';
import { leakChip } from './pivotLeak';

describe('leakChip — general SEPA card 🚱 flag', () => {
  const leaky = { leaky: true, leaks: 2, last_leak_bars_ago: 3 };

  it('shows on a leaky buyable with counts in the tooltip', () => {
    const c = leakChip(leaky, { buyable: true });
    expect(c).not.toBeNull();
    expect(c!.label).toContain('leaky pivot');
    expect(c!.title).toContain('2 times');
    expect(c!.title).toContain('3 days ago');
  });

  it('shows on setup-ready too, singularizes correctly', () => {
    const c = leakChip({ leaky: true, leaks: 1, last_leak_bars_ago: 1 }, { setupReady: true });
    expect(c!.title).toContain('1 time ');
    expect(c!.title).toContain('1 day ago');
  });

  it('hidden when not leaky, not decision-relevant, or data is missing', () => {
    expect(leakChip({ leaky: false, leaks: 1 }, { buyable: true })).toBeNull();
    expect(leakChip(leaky, {})).toBeNull();                       // plain leader
    expect(leakChip(null, { buyable: true })).toBeNull();
    expect(leakChip(undefined, { buyable: true })).toBeNull();    // old scans
  });

  it('survives partial payloads without NaN text', () => {
    const c = leakChip({ leaky: true }, { buyable: true });
    expect(c!.title).toContain('several');
    expect(c!.title).not.toContain('NaN');
  });
});
