/* 🛡️ 🚀 growth — the critic round (2026-10-07 c), over the REAL capture.
 *
 * Ajay 2026-10-07: "yes please also no #s for SNDK can you do a deep analysis
 * of data and make sure you do a sanity chcek fo missing data pieces over all."
 *
 * The served words the critic MEASURED as wrong must be gone from what the
 * board actually serves, and the new "Massive not used at research time"
 * bucket must reach the screen through the real component. The FE composes
 * none of it — every string here is a served string. */
import { describe, expect, it, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import FIXTURE from './__fixtures__/resiliency_tab_2026_10_07.json';
import ResiliencyBoardNote from './ResiliencyBoardNote';
import type { CmResiliencyBoard, CmTile } from '../lib/chartMaps';

const RAW = FIXTURE as unknown as Record<string, { resiliency_board?: CmResiliencyBoard; tiles?: CmTile[] }>;
const GROWTH = RAW.res_growth;
const allText = JSON.stringify(FIXTURE);

afterEach(cleanup);

describe('🚀 growth words after the critic round (2026-10-07 c)', () => {
  it('the served line and fold carry the massive_unused bucket and render verbatim', () => {
    const rb = GROWTH.resiliency_board!;
    expect(rb.growth_line).toMatch(/\d+ Massive not used at research time/);
    const lines = rb.growth_gaps!.lines;
    const mu = lines.find((l) => l.startsWith('Massive not used at research time ('));
    expect(mu, 'the fold has a massive_unused line').toBeTruthy();
    expect(mu!).toContain('fell back to yfinance');
    const { getByTestId } = render(
      <ResiliencyBoardNote board={rb} sorts={[]} sort="res_growth"
                           onSort={() => {}} onToggleFilter={() => {}} onToggleMode={() => {}} />);
    expect(getByTestId('cm-res-growth').textContent).toBe(rb.growth_line);
    expect(getByTestId('cm-res-growth-gaps').textContent || '').toContain(mu!);
  });

  it('NEGATIVE: no served text calls the series "the filings" or says "neither provider"', () => {
    expect(allText).not.toContain('own quarterly filings');
    expect(allText).not.toContain('neither provider');
    expect(allText).not.toContain('a research refresh realigns them');
  });
});
