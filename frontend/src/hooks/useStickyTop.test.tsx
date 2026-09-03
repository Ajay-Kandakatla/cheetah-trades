import { render } from '@testing-library/react';
import { useRef } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { STICKY_TOP_VAR, setStickyTop, useStickyTop } from './useStickyTop';

/* Ajay 2026-09-02: "Keep the headers static on scroll until the end of the
 * table" — on phones the nav itself is sticky, so the table headers must sit
 * under its measured height, published here as --sticky-top. */
function Bar({ active = true, h = 46 }: { active?: boolean; h?: number }) {
  const ref = useRef<HTMLElement>(null);
  useStickyTop(ref, active);
  return <header ref={ref} data-h={h}>nav</header>;
}
const varOf = () => document.documentElement.style.getPropertyValue(STICKY_TOP_VAR);

describe('useStickyTop', () => {
  afterEach(() => { vi.restoreAllMocks(); setStickyTop(null); });

  it('publishes the measured bar height on <html> and removes it on unmount', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      return { height: Number(this.dataset.h ?? 0) } as DOMRect;
    });
    const { unmount } = render(<Bar h={46.4} />);
    expect(varOf()).toBe('46px');
    unmount();
    expect(varOf()).toBe('');
  });

  it('NEGATIVE: inactive (desktop nav scrolls away) or zero height leaves the variable unset', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ height: 46 } as DOMRect);
    render(<Bar active={false} />);
    expect(varOf()).toBe('');
    setStickyTop(0);
    expect(varOf()).toBe('');
    setStickyTop(null);
    expect(varOf()).toBe('');
  });

  it('re-measures when the bar resizes (gauge badge appears) via ResizeObserver', () => {
    let cb: (() => void) | null = null;
    const observe = vi.fn(), disconnect = vi.fn();
    vi.stubGlobal('ResizeObserver', class { constructor(f: () => void) { cb = f; } observe = observe; disconnect = disconnect; });
    let h = 40;
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(() => ({ height: h } as DOMRect));
    const { unmount } = render(<Bar />);
    expect(varOf()).toBe('40px');
    expect(observe).toHaveBeenCalledTimes(1);
    h = 58; cb!();
    expect(varOf()).toBe('58px');
    unmount();
    expect(disconnect).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });
});
