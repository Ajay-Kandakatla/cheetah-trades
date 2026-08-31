import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HotSectors, { chipLabel } from './HotSectors';

const PAYLOAD = {
  as_of: '2026-08-31', start: '2026-06-01', benchmark: 'RSP',
  ranked_by: 'rel_21d',
  in: [
    { group: 'Technology · large caps', sector: 'Technology', tier: 'large',
      index: 'S&P 500', n: 25, rel_21d: 5.7, rel_window: -8.17 },
    { group: 'Energy · small caps', sector: 'Energy', tier: 'small',
      index: 'S&P 600', n: 25, rel_21d: 5.11, rel_window: 6.32 },
  ],
  out: [
    { group: 'Real Estate · small caps', sector: 'Real Estate', tier: 'small',
      index: 'S&P 600', n: 25, rel_21d: -7.44, rel_window: -2.39 },
  ],
};

function stub(body: any, ok = true) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok, status: ok ? 200 : 503, json: () => Promise.resolve(body),
  } as any));
}

const draw = () => render(<MemoryRouter><HotSectors /></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('HotSectors', () => {
  it('renders cohort chips with signed 21-day numbers', async () => {
    stub(PAYLOAD);
    draw();
    await waitFor(() =>
      expect(screen.getByText('Technology · large caps +5.7%')).toBeTruthy());
    expect(screen.getByText('Energy · small caps +5.1%')).toBeTruthy();
    expect(screen.getByText('Real Estate · small caps -7.4%')).toBeTruthy();
    expect(screen.getByText(/money in/i)).toBeTruthy();
    expect(screen.getByText(/money out/i)).toBeTruthy();
    expect(screen.getByText(/vs RSP/)).toBeTruthy();
  });

  it('links to the full rotation page', async () => {
    stub(PAYLOAD);
    draw();
    await waitFor(() => expect(screen.getByText(/full rotation/)).toBeTruthy());
    expect(screen.getByRole('link', { name: /full rotation/ }))
      .toHaveAttribute('href', '/rotation');
  });

  it('renders NOTHING on error — a strip must never break its page', async () => {
    stub({ error: 'boom' }, false);
    const { container } = draw();
    await new Promise((r) => setTimeout(r, 0));
    expect(container.querySelector('.hs')).toBeNull();
  });

  it('renders nothing while loading and nothing when empty', async () => {
    stub({ in: [], out: [] });
    const { container } = draw();
    await new Promise((r) => setTimeout(r, 0));
    expect(container.querySelector('.hs')).toBeNull();
  });

  it('chipLabel never prints "null%"', () => {
    expect(chipLabel({ group: 'X', rel_21d: null })).toBe('X');
    expect(chipLabel({ group: 'X', rel_21d: 2.15 })).toBe('X +2.1%');
    expect(chipLabel({ group: 'X', rel_21d: -0.24 })).toBe('X -0.2%');
  });
});
