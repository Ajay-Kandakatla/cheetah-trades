import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import OverlayLegend from './OverlayLegend';
import { OVERLAY_GROUPS } from '../lib/chartOverlays';

const groups = OVERLAY_GROUPS.filter((g) =>
  ['demand', 'order_block', 'trade'].includes(g.key));

describe('OverlayLegend', () => {
  it('renders a labelled checkbox per present family, checked when visible', () => {
    render(<OverlayLegend present={groups} hidden={new Set(['order_block'])}
                          onToggle={() => {}} />);
    expect(screen.getByText('Ledger')).toBeTruthy();
    const demand = screen.getByLabelText(/Support \/ demand/) as HTMLInputElement;
    const ob = screen.getByLabelText(/Order blocks/) as HTMLInputElement;
    expect(demand.checked).toBe(true);
    expect(ob.checked).toBe(false);
  });

  it('reports toggles by family key', () => {
    const onToggle = vi.fn();
    render(<OverlayLegend present={groups} hidden={new Set()} onToggle={onToggle} />);
    fireEvent.click(screen.getByLabelText(/Order blocks/));
    expect(onToggle).toHaveBeenCalledWith('order_block');
  });

  it('offers "show all" only when something is hidden, and unhides everything', () => {
    const onToggle = vi.fn();
    const { rerender } = render(
      <OverlayLegend present={groups} hidden={new Set()} onToggle={onToggle} />);
    expect(screen.queryByText('show all')).toBeNull();
    rerender(<OverlayLegend present={groups}
                            hidden={new Set(['order_block', 'trade'])}
                            onToggle={onToggle} />);
    fireEvent.click(screen.getByText('show all'));
    expect(onToggle).toHaveBeenCalledWith('order_block');
    expect(onToggle).toHaveBeenCalledWith('trade');
  });

  it('renders nothing when the view draws no known overlays', () => {
    const { container } = render(
      <OverlayLegend present={[]} hidden={new Set()} onToggle={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
});
