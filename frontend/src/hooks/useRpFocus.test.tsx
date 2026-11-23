/* useRpFocus (2026-11-22, pwjump spec §3.4). Ajay: "focus me on that video at that. time". Scroll ONCE per key, when ready
 * and mounted. NEGATIVES: not ready never scrolls; a late element is still caught; no scrollIntoView never throws. */
import { render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useRpFocus } from './useRpFocus';

function Probe({ k, ready, show = true }: { k: string; ready: boolean; show?: boolean }) {
  const ref = useRpFocus<HTMLDivElement>(k, ready);
  return show ? <div ref={ref} data-testid="t" tabIndex={-1}>x</div> : <span>none</span>;
}

const orig = (Element.prototype as any).scrollIntoView;
let spy: ReturnType<typeof vi.fn>;
beforeEach(() => { spy = vi.fn(); (Element.prototype as any).scrollIntoView = spy; });
afterEach(() => { (Element.prototype as any).scrollIntoView = orig; });

describe('useRpFocus', () => {
  it('scrolls once for a key (block start) and focuses without scrolling; same key → no second scroll', () => {
    const r = render(<Probe k="a|1" ready />);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][0]).toEqual({ block: 'start' });
    expect(spy.mock.instances[0]).toBe(r.getByTestId('t'));
    expect(document.activeElement).toBe(r.getByTestId('t'));
    r.rerender(<Probe k="a|1" ready />);
    r.rerender(<Probe k="a|1" ready />);
    expect(spy).toHaveBeenCalledTimes(1);
  });
  it('a NEW key scrolls again; "" then the same key scrolls again', () => {
    const r = render(<Probe k="a|1" ready />);
    r.rerender(<Probe k="a|2" ready />);
    expect(spy).toHaveBeenCalledTimes(2);
    r.rerender(<Probe k="" ready />);
    expect(spy).toHaveBeenCalledTimes(2);
    r.rerender(<Probe k="a|2" ready />);
    expect(spy).toHaveBeenCalledTimes(3);
  });
  it('NEGATIVE: ready === false never scrolls; the scroll happens once it turns true', () => {
    const r = render(<Probe k="a|1" ready={false} />);
    r.rerender(<Probe k="a|1" ready={false} />);
    expect(spy).not.toHaveBeenCalled();
    r.rerender(<Probe k="a|1" ready />);
    expect(spy).toHaveBeenCalledTimes(1);
  });
  it('NEGATIVE: an element that mounts one render after the key is still scrolled to', () => {
    const r = render(<Probe k="a|1" ready show={false} />);
    expect(spy).not.toHaveBeenCalled();
    r.rerender(<Probe k="a|1" ready show />);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.instances[0]).toBe(r.getByTestId('t'));
  });
  it('NEGATIVE: an empty key never scrolls', () => {
    render(<Probe k="" ready />);
    expect(spy).not.toHaveBeenCalled();
  });
  it('NEGATIVE: with no scrollIntoView on the element nothing throws', () => {
    (Element.prototype as any).scrollIntoView = undefined;
    expect(() => render(<Probe k="a|1" ready />)).not.toThrow();
  });
});
