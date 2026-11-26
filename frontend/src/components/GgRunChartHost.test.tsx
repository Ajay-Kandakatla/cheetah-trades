/* 📅 The lazy host of the continuous runner chart (2026-11-26, spec runcharts rev 2 §3.8 / §4.3, package fe-mount).
 *
 * Ajay 2026-11-26: "I want you to have continous charts for previous day runners … I wanna able to horizontal scroll tp
 * check continuity like he does".
 *
 * The REAL host and the REAL open store (lib/ggRunChart.ts); the chart is a stub (its own tests live with fe-chart) and
 * the usage tracker a spy. NEGATIVES: nothing drawn before an open; a one-name list gets no ‹ ›; a step is not a new
 * open; unmounting the host (leaving 🚩) closes the store, so a re-mount draws nothing; the host never imports the chart
 * or lightweight-charts statically. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const H = vi.hoisted(() => ({ props: [] as any[] }));
vi.mock('./GgRunChart', () => ({
  default: (p: any) => {
    H.props.push(p);
    return (
      <div data-testid="ggrc-stub" data-symbol={p.symbol} data-list={(p.list ?? []).join(',')}
           data-step={p.onStep ? 'yes' : 'no'}>
        <button type="button" data-testid="stub-close" onClick={p.onClose}>x</button>
        {p.onStep && <button type="button" data-testid="stub-next" onClick={() => p.onStep(1)}>›</button>}
      </div>
    );
  },
}));
vi.mock('../lib/usageTracker', () => ({ trackFeature: vi.fn() }));

import GgRunChartHost from './GgRunChartHost';
import { closeGgRunChart, openGgRunChart, useGgRunChartOpen } from '../lib/ggRunChart';
import { trackFeature } from '../lib/usageTracker';

const LIST = ['MEDS', 'MSS', 'CIGL'];
const tracked = () => (trackFeature as any).mock.calls.filter((c: any[]) => c[0] === 'gg-run-chart:open').length;

function Probe() {
  const o = useGgRunChartOpen();
  return <i data-testid="probe">{o ? `${o.symbol}|${o.list.join(',')}` : 'closed'}</i>;
}

async function settle() { await act(async () => { await new Promise((r) => setTimeout(r, 0)); }); }

beforeEach(() => { H.props.length = 0; (trackFeature as any).mockClear(); act(() => closeGgRunChart()); });
afterEach(() => { cleanup(); act(() => closeGgRunChart()); });

describe('📅 GgRunChartHost', () => {
  it('renders nothing until openGgRunChart', async () => {
    const { container } = render(<GgRunChartHost />);
    await settle();
    expect(container.innerHTML).toBe('');
    expect(screen.queryByTestId('ggrc-stub')).toBeNull();
    expect(H.props).toEqual([]);
    expect(tracked()).toBe(0);
  });

  it('an open hands the chart the symbol and the list; onClose clears it', async () => {
    render(<><GgRunChartHost /><Probe /></>);
    act(() => openGgRunChart('MSS', LIST));
    const stub = await screen.findByTestId('ggrc-stub');
    expect(stub.getAttribute('data-symbol')).toBe('MSS');
    expect(stub.getAttribute('data-list')).toBe('MEDS,MSS,CIGL');
    expect(stub.getAttribute('data-step')).toBe('yes');
    fireEvent.click(screen.getByTestId('stub-close'));
    await settle();
    expect(screen.queryByTestId('ggrc-stub')).toBeNull();
    expect(screen.getByTestId('probe').textContent).toBe('closed');
  });

  it('onStep moves inside the list (the store steps, the chart gets the new symbol)', async () => {
    render(<GgRunChartHost />);
    act(() => openGgRunChart('MEDS', LIST));
    await screen.findByTestId('ggrc-stub');
    fireEvent.click(screen.getByTestId('stub-next'));
    await settle();
    expect(screen.getByTestId('ggrc-stub').getAttribute('data-symbol')).toBe('MSS');
  });

  it('NEGATIVE: a one-name list → onStep is null', async () => {
    render(<GgRunChartHost />);
    act(() => openGgRunChart('MEDS', ['MEDS']));
    const stub = await screen.findByTestId('ggrc-stub');
    expect(stub.getAttribute('data-step')).toBe('no');
    expect(H.props.at(-1).onStep).toBeNull();
    expect(screen.queryByTestId('stub-next')).toBeNull();
  });

  it('trackFeature once per open — NEGATIVE: a ‹ › step is not a new open; a close + reopen is', async () => {
    render(<GgRunChartHost />);
    act(() => openGgRunChart('MEDS', LIST));
    await screen.findByTestId('ggrc-stub');
    expect(tracked()).toBe(1);
    fireEvent.click(screen.getByTestId('stub-next'));
    await settle();
    expect(tracked()).toBe(1);
    act(() => closeGgRunChart());
    await settle();
    expect(tracked()).toBe(1);
    act(() => openGgRunChart('CIGL', LIST));
    await screen.findByTestId('ggrc-stub');
    expect(tracked()).toBe(2);
  });

  it('NEGATIVE: unmounting the host while a chart is open closes the store; a re-mount renders nothing', async () => {
    const probe = render(<Probe />);
    const host = render(<GgRunChartHost />);
    act(() => openGgRunChart('MEDS', LIST));
    await screen.findByTestId('ggrc-stub');
    expect(probe.getByTestId('probe').textContent).toBe('MEDS|MEDS,MSS,CIGL');
    host.unmount();
    await settle();
    expect(probe.getByTestId('probe').textContent).toBe('closed');
    const again = render(<GgRunChartHost />);
    await settle();
    expect(again.container.innerHTML).toBe('');
    expect(screen.queryByTestId('ggrc-stub')).toBeNull();
  });
});

describe('📅 GgRunChartHost — source guards', () => {
  async function read(rel: string): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    return fs.readFileSync(`${root}/src/${rel}`, 'utf8');
  }

  it('the chart is loaded through lazyWithReload, never statically, never raw React.lazy', async () => {
    const src = await read('components/GgRunChartHost.tsx');
    expect(src).toMatch(/lazyWithReload\(\(\) => import\('\.\/GgRunChart'\)\)/);
    expect(src).not.toMatch(/from '\.\/GgRunChart'/);
    expect(src).not.toMatch(/lightweight-charts/);
    expect(src).not.toMatch(/\blazy\(/);
    expect(src).toMatch(/closeGgRunChart\(\), \[\]\)/);
  });

  it('NEGATIVE: the matcher rejects a static import', () => {
    const bad = "import GgRunChart from './GgRunChart';";
    expect(bad).toMatch(/from '\.\/GgRunChart'/);
  });
});
