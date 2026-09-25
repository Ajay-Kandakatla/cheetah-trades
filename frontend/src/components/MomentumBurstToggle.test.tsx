/* ⚡ MomentumBurstToggle — the checkbox, its count, and the two honest
 * suffixes that appear only when they are not zero. */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MomentumBurstToggle } from './MomentumBurstToggle';
import { BURST_DISAMBIGUATION } from '../lib/momentumBurst';

const RULE = 'Rule: served rule sentence. UNMEASURED.';
const NOTE = 'Pre-market — served note.';

const draw = (over: Partial<Parameters<typeof MomentumBurstToggle>[0]> = {}) => {
  const onChange = vi.fn();
  const r = render(
    <MomentumBurstToggle checked={false} onChange={onChange} count={2} unknown={0} behind={0}
                         rule={RULE} note={NOTE} tiles={5} {...over} />,
  );
  return { ...r, onChange };
};

describe('MomentumBurstToggle', () => {
  it('shows the label and the count, and the title carries the rule and "hides nothing"', () => {
    const { container } = draw();
    const label = container.querySelector('label.mb-toggle')!;
    expect(label.textContent).toContain('⚡ Momentum burst');
    expect(container.querySelector('.mb-count')!.textContent).toBe(' · 2');
    const title = label.getAttribute('title')!;
    expect(title).toContain(RULE);
    expect(title).toContain(BURST_DISAMBIGUATION);
    expect(title).toContain('hides nothing');
    expect(title).toContain('Counted over the 5 tiles on this page');
  });

  it('NEGATIVE: no "unknown" and no "behind 🎯" suffix at zero', () => {
    const { container } = draw({ unknown: 0, behind: 0 });
    expect(container.querySelector('.mb-unknown')).toBeNull();
    expect(container.querySelector('.mb-behind')).toBeNull();
    expect(container.textContent).not.toMatch(/unknown|behind/);
  });

  it('prints the unknown count with the served note as its title, and the behind-🎯 count', () => {
    const { container } = draw({ unknown: 5, behind: 1 });
    const unk = container.querySelector('.mb-unknown')!;
    expect(unk.textContent).toBe(' · 5 unknown');
    expect(unk.getAttribute('title')).toBe(NOTE);
    const beh = container.querySelector('.mb-behind')!;
    expect(beh.textContent).toBe(' · 1 behind 🎯');
    expect(beh.getAttribute('title')).toMatch(/never hides a name/);
  });

  it('the count can be zero and still shows (the box is never a hidden control)', () => {
    const { container } = draw({ count: 0 });
    expect(container.querySelector('.mb-count')!.textContent).toBe(' · 0');
  });

  it('fires onChange with the new state, both ways', () => {
    const { onChange, unmount } = draw();
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onChange).toHaveBeenLastCalledWith(true);
    unmount();
    const on = draw({ checked: true });
    expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByRole('checkbox'));
    expect(on.onChange).toHaveBeenLastCalledWith(false);
  });

  it('NEGATIVE: a missing served rule does not print "undefined" into the hover', () => {
    const { container } = draw({ rule: undefined });
    expect(container.querySelector('label')!.getAttribute('title')).not.toContain('undefined');
  });
});
