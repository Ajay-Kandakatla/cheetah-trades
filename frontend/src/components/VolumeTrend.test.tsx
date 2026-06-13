import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { VolumeTrend } from './VolumeTrend';

/* VolumeTrend — the multi-day accumulation read on every SEPA card. Positive
   render paths AND the negatives (no data must render NOTHING, not an empty
   box). */

describe('VolumeTrend', () => {
  it('renders nothing when vol is null (negative)', () => {
    const { container } = render(<VolumeTrend vol={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when there is no spark, strength, or day counts (negative)', () => {
    const { container } = render(<VolumeTrend vol={{}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows an accumulating verdict + plain-English caption from the day counts', () => {
    render(<VolumeTrend vol={{
      accumulation_strength: 'accumulating',
      accumulation_days_25: 9,
      distribution_days_25: 3,
      up_down_vol_ratio: 1.4,
      cmf_signal: 'inflow',
    }} />);
    expect(screen.getByText(/accumulating/i)).toBeInTheDocument();
    expect(screen.getByText(/9 up-volume days vs 3 down/i)).toBeInTheDocument();
    expect(screen.getByText(/money flowing in/i)).toBeInTheDocument();
  });

  it('draws one sparkline bar per vol_spark entry and a distributing verdict', () => {
    const { container } = render(<VolumeTrend vol={{
      accumulation_strength: 'distributing',
      vol_spark: [100, -200, 150, -50],
      avg_vol_50: 120,
    }} />);
    expect(container.querySelectorAll('.vol-trend__bar')).toHaveLength(4);
    expect(screen.getByText(/distributing/i)).toBeInTheDocument();
  });

  it('infers "building" from day counts when strength is absent', () => {
    render(<VolumeTrend vol={{ accumulation_days_25: 10, distribution_days_25: 2 }} />);
    expect(screen.getByText(/building/i)).toBeInTheDocument();
  });
});
