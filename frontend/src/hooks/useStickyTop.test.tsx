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

/* 2026-09-28 — the pinned Chart Maps tab strip publishes its own height as
 * --cm-tabs-h on the page root through the same hook. */
function Custom({ h = 38 }: { h?: number }) {
  const host = useRef<HTMLDivElement>(null);
  const ref = useRef<HTMLDivElement>(null);
  useStickyTop(ref, true, { varName: '--cm-tabs-h', host });
  return <div ref={host} data-testid="host"><div ref={ref} data-h={h}>bar</div></div>;
}

describe('useStickyTop — custom variable on a custom host', () => {
  afterEach(() => { vi.restoreAllMocks(); setStickyTop(null); });
  const mockH = () => vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    return { height: Number(this.dataset.h ?? 0) } as DOMRect;
  });

  it('the custom variable lands on the host element', () => {
    mockH();
    const { getByTestId } = render(<Custom h={38.2} />);
    expect(getByTestId('host').style.getPropertyValue('--cm-tabs-h')).toBe('38px');
  });

  it('NEGATIVE: the <html> --sticky-top is untouched by a custom-var call', () => {
    mockH();
    setStickyTop(52);
    render(<Custom />);
    expect(varOf()).toBe('52px');
    expect(document.documentElement.style.getPropertyValue('--cm-tabs-h')).toBe('');
  });

  it('unmount removes only the custom variable', () => {
    mockH();
    setStickyTop(52);
    const { getByTestId, unmount } = render(<Custom />);
    const host = getByTestId('host');
    host.style.setProperty('--other', '1px');
    unmount();
    expect(host.style.getPropertyValue('--cm-tabs-h')).toBe('');
    expect(host.style.getPropertyValue('--other')).toBe('1px');
    expect(varOf()).toBe('52px');
  });
});
