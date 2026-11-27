/* 🕐 2026-11-27 (spec sicheck §3.6 D1): PatternChart's `barMin` prop on a REAL served tile — NXAT's 5-minute frame of
 * 2026-11-27 as tab._tile_frame(doc, "5m") serves it from gajjala_reads "2026-11-27|NXAT" (read-only container probe,
 * 2026-11-27 ~10:15 ET; the bars below were written by that probe, none typed). Its 08:10 bar (v 771,509) is the 08:05–08:10 bar:
 * the stamp is the bar's END. With barMin={5} the hover prints the range; without it, exactly today's text. */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import { HOVER_TIP_W, hoverLines, hoverTipWidth, type CmBar, type CmTile } from '../lib/chartMaps';

afterEach(cleanup);

/* NXAT 2026-11-27 tile.bars5 (74 bars, 2026-11-27 04:05 → 2026-11-27 10:10), probe-written. */
const NXAT_5M: CmBar[] = [
  {"t":"2026-11-27 04:05","o":0.84,"h":0.8501,"l":0.75,"c":0.7761,"v":236485.983229,"s":"pre"},
  {"t":"2026-11-27 04:10","o":0.7761,"h":0.84,"l":0.7761,"c":0.8,"v":122501.0,"s":"pre"},
  {"t":"2026-11-27 04:15","o":0.8,"h":0.829,"l":0.762,"c":0.8248,"v":89443.0,"s":"pre"},
  {"t":"2026-11-27 04:20","o":0.8199,"h":0.95,"l":0.8,"c":0.8124,"v":1190967.392857,"s":"pre"},
  {"t":"2026-11-27 04:25","o":0.8131,"h":0.8151,"l":0.78,"c":0.8083,"v":304028.0,"s":"pre"},
  {"t":"2026-11-27 04:30","o":0.8083,"h":0.8179,"l":0.79,"c":0.8,"v":108975.0,"s":"pre"},
  {"t":"2026-11-27 04:35","o":0.8002,"h":0.8002,"l":0.7665,"c":0.7799,"v":128050.0,"s":"pre"},
  {"t":"2026-11-27 04:40","o":0.7759,"h":0.815,"l":0.7751,"c":0.8141,"v":83547.0,"s":"pre"},
  {"t":"2026-11-27 04:45","o":0.8141,"h":0.87,"l":0.8003,"c":0.83,"v":295362.0,"s":"pre"},
  {"t":"2026-11-27 04:50","o":0.8231,"h":0.916,"l":0.8141,"c":0.8599,"v":990950.0,"s":"pre"},
  {"t":"2026-11-27 04:55","o":0.8523,"h":0.9211,"l":0.8384,"c":0.8939,"v":686347.0,"s":"pre"},
  {"t":"2026-11-27 05:00","o":0.8805,"h":0.9,"l":0.85,"c":0.8532,"v":414486.0,"s":"pre"},
  {"t":"2026-11-27 05:05","o":0.8572,"h":0.9141,"l":0.8384,"c":0.89,"v":421443.0,"s":"pre"},
  {"t":"2026-11-27 05:10","o":0.88,"h":0.88,"l":0.835,"c":0.8545,"v":285536.0,"s":"pre"},
  {"t":"2026-11-27 05:15","o":0.8508,"h":0.864,"l":0.838,"c":0.86,"v":124370.0,"s":"pre"},
  {"t":"2026-11-27 05:20","o":0.8465,"h":0.86,"l":0.8169,"c":0.82,"v":108195.0,"s":"pre"},
  {"t":"2026-11-27 05:25","o":0.8197,"h":0.8736,"l":0.8191,"c":0.8692,"v":79118.0,"s":"pre"},
  {"t":"2026-11-27 05:30","o":0.8693,"h":0.8694,"l":0.8399,"c":0.85,"v":86801.0,"s":"pre"},
  {"t":"2026-11-27 05:35","o":0.84,"h":0.9,"l":0.8397,"c":0.8778,"v":259696.0,"s":"pre"},
  {"t":"2026-11-27 05:40","o":0.8778,"h":0.9002,"l":0.86,"c":0.875,"v":307677.0,"s":"pre"},
  {"t":"2026-11-27 05:45","o":0.8752,"h":0.923,"l":0.8521,"c":0.9227,"v":300196.0,"s":"pre"},
  {"t":"2026-11-27 05:50","o":0.9226,"h":0.925,"l":0.8414,"c":0.8516,"v":680796.0,"s":"pre"},
  {"t":"2026-11-27 05:55","o":0.8493,"h":0.8669,"l":0.845,"c":0.8501,"v":199860.0,"s":"pre"},
  {"t":"2026-11-27 06:00","o":0.8528,"h":0.86,"l":0.84,"c":0.8599,"v":105302.0,"s":"pre"},
  {"t":"2026-11-27 06:05","o":0.8599,"h":0.86,"l":0.8474,"c":0.8589,"v":74800.0,"s":"pre"},
  {"t":"2026-11-27 06:10","o":0.8592,"h":0.8895,"l":0.847,"c":0.8509,"v":180199.0,"s":"pre"},
  {"t":"2026-11-27 06:15","o":0.8488,"h":0.8736,"l":0.8435,"c":0.8528,"v":99249.0,"s":"pre"},
  {"t":"2026-11-27 06:20","o":0.8522,"h":0.8585,"l":0.8439,"c":0.8503,"v":51557.0,"s":"pre"},
  {"t":"2026-11-27 06:25","o":0.8503,"h":0.8699,"l":0.8503,"c":0.8629,"v":37597.0,"s":"pre"},
  {"t":"2026-11-27 06:30","o":0.8611,"h":0.8611,"l":0.8446,"c":0.8528,"v":41415.0,"s":"pre"},
  {"t":"2026-11-27 06:35","o":0.85,"h":0.8675,"l":0.85,"c":0.8501,"v":47904.0,"s":"pre"},
  {"t":"2026-11-27 06:40","o":0.855,"h":0.866,"l":0.84,"c":0.855,"v":86211.0,"s":"pre"},
  {"t":"2026-11-27 06:45","o":0.855,"h":0.8585,"l":0.846,"c":0.8584,"v":37270.0,"s":"pre"},
  {"t":"2026-11-27 06:50","o":0.8585,"h":0.8585,"l":0.853,"c":0.853,"v":13205.0,"s":"pre"},
  {"t":"2026-11-27 06:55","o":0.8544,"h":0.856,"l":0.82,"c":0.823,"v":163248.0,"s":"pre"},
  {"t":"2026-11-27 07:00","o":0.82,"h":0.843,"l":0.8179,"c":0.8334,"v":94092.0,"s":"pre"},
  {"t":"2026-11-27 07:05","o":0.8204,"h":0.839,"l":0.8011,"c":0.8022,"v":162925.0,"s":"pre"},
  {"t":"2026-11-27 07:10","o":0.8026,"h":0.836,"l":0.8022,"c":0.826,"v":114252.0,"s":"pre"},
  {"t":"2026-11-27 07:15","o":0.826,"h":0.8362,"l":0.7654,"c":0.819,"v":270867.0,"s":"pre"},
  {"t":"2026-11-27 07:20","o":0.8184,"h":0.8236,"l":0.7712,"c":0.7948,"v":112685.0,"s":"pre"},
  {"t":"2026-11-27 07:25","o":0.7951,"h":0.7951,"l":0.77,"c":0.77,"v":91977.0,"s":"pre"},
  {"t":"2026-11-27 07:30","o":0.7707,"h":0.78,"l":0.7695,"c":0.7695,"v":74265.0,"s":"pre"},
  {"t":"2026-11-27 07:35","o":0.7781,"h":0.7781,"l":0.75,"c":0.7599,"v":136148.0,"s":"pre"},
  {"t":"2026-11-27 07:40","o":0.7551,"h":0.7775,"l":0.7525,"c":0.77,"v":75227.0,"s":"pre"},
  {"t":"2026-11-27 07:45","o":0.7697,"h":0.78,"l":0.755,"c":0.78,"v":46294.0,"s":"pre"},
  {"t":"2026-11-27 07:50","o":0.78,"h":0.819,"l":0.7792,"c":0.81,"v":329792.0,"s":"pre"},
  {"t":"2026-11-27 07:55","o":0.81,"h":0.81,"l":0.79,"c":0.7955,"v":73868.0,"s":"pre"},
  {"t":"2026-11-27 08:00","o":0.7946,"h":0.7949,"l":0.78,"c":0.79,"v":101727.0,"s":"pre"},
  {"t":"2026-11-27 08:05","o":0.7943,"h":0.85,"l":0.7937,"c":0.8415,"v":257133.0,"s":"pre"},
  {"t":"2026-11-27 08:10","o":0.8334,"h":0.88,"l":0.82,"c":0.8399,"v":771509.0,"s":"pre"},
  {"t":"2026-11-27 08:15","o":0.8398,"h":0.86,"l":0.8,"c":0.8066,"v":346183.0,"s":"pre"},
  {"t":"2026-11-27 08:20","o":0.8066,"h":0.8335,"l":0.8051,"c":0.8272,"v":94855.194919,"s":"pre"},
  {"t":"2026-11-27 08:25","o":0.8272,"h":0.8309,"l":0.8,"c":0.8001,"v":73516.0,"s":"pre"},
  {"t":"2026-11-27 08:30","o":0.8001,"h":0.8148,"l":0.7875,"c":0.811,"v":90955.0,"s":"pre"},
  {"t":"2026-11-27 08:35","o":0.81,"h":0.8139,"l":0.7932,"c":0.7933,"v":70406.0,"s":"pre"},
  {"t":"2026-11-27 08:40","o":0.7933,"h":0.8001,"l":0.77,"c":0.7921,"v":92120.0,"s":"pre"},
  {"t":"2026-11-27 08:45","o":0.8,"h":0.8,"l":0.78,"c":0.796,"v":39564.0,"s":"pre"},
  {"t":"2026-11-27 08:50","o":0.796,"h":0.799,"l":0.7809,"c":0.7855,"v":36507.0,"s":"pre"},
  {"t":"2026-11-27 08:55","o":0.7936,"h":0.7999,"l":0.7856,"c":0.7934,"v":32577.0,"s":"pre"},
  {"t":"2026-11-27 09:00","o":0.7997,"h":0.7998,"l":0.7844,"c":0.7855,"v":39258.0,"s":"pre"},
  {"t":"2026-11-27 09:05","o":0.7855,"h":0.7856,"l":0.77,"c":0.7774,"v":51600.0,"s":"pre"},
  {"t":"2026-11-27 09:10","o":0.7774,"h":0.79,"l":0.7731,"c":0.775,"v":61525.0,"s":"pre"},
  {"t":"2026-11-27 09:15","o":0.7799,"h":0.8161,"l":0.775,"c":0.8001,"v":46082.0,"s":"pre"},
  {"t":"2026-11-27 09:20","o":0.8025,"h":0.8247,"l":0.8,"c":0.8035,"v":69007.0,"s":"pre"},
  {"t":"2026-11-27 09:25","o":0.8197,"h":0.8197,"l":0.8044,"c":0.8105,"v":53769.0,"s":"pre"},
  {"t":"2026-11-27 09:30","o":0.8105,"h":0.85,"l":0.8034,"c":0.82,"v":156940.0,"s":"pre"},
  {"t":"2026-11-27 09:35","o":0.85,"h":0.95,"l":0.8,"c":0.8001,"v":3701022.365435},
  {"t":"2026-11-27 09:40","o":0.8,"h":0.8399,"l":0.74,"c":0.8075,"v":1836210.167929},
  {"t":"2026-11-27 09:45","o":0.8001,"h":0.867,"l":0.7843,"c":0.8346,"v":990327.575907},
  {"t":"2026-11-27 09:50","o":0.8347,"h":0.8546,"l":0.8,"c":0.8082,"v":527574.573597},
  {"t":"2026-11-27 09:55","o":0.8081,"h":0.86,"l":0.805,"c":0.8545,"v":636400.4451240001},
  {"t":"2026-11-27 10:00","o":0.8501,"h":0.945,"l":0.8371,"c":0.9025,"v":2274085.607717},
  {"t":"2026-11-27 10:05","o":0.9025,"h":0.9199,"l":0.8508,"c":0.8713,"v":1604892.4900520002},
  {"t":"2026-11-27 10:10","o":0.8717,"h":0.9,"l":0.8411,"c":0.8614,"v":846785.102706},
];

const tile = (): CmTile => ({
  symbol: 'NXAT', href: '/sepa/NXAT', bars: NXAT_5M, bands: [], lines: [], stats: [], why: '', curves: [], markers: [],
} as unknown as CmTile);

const draw = (props: Record<string, unknown> = {}) =>
  render(<MemoryRouter><PatternChart tile={tile()} chartOnly {...props} /></MemoryRouter>);

/** The hover readout <g>'s tooltip: its box width and its text lines, or null when no tooltip is drawn. */
const readTip = (svg: SVGSVGElement) => {
  const g = svg.querySelector('g[pointer-events="none"]');
  if (!g) return null;
  const box = Array.from(g.querySelectorAll('g > rect')).find((r) => r.getAttribute('rx') === '4');
  if (!box) return null;
  const lines = Array.from(box.parentElement!.querySelectorAll('text')).map((t) => t.textContent || '');
  return { w: Number(box.getAttribute('width')), lines };
};

/** Sweep the pointer across the plot until the tooltip names the bar stamped `stamp`. */
const hoverBar = (svg: SVGSVGElement, stamp: string) => {
  (svg as any).getBoundingClientRect = () => ({ left: 0, top: 0, width: 620, height: 190, right: 620, bottom: 190, x: 0, y: 0 });
  for (let x = 0; x < 620; x += 1) {
    fireEvent.mouseMove(svg, { clientX: x, clientY: 60 });
    const tip = readTip(svg);
    if (tip && tip.lines[3] === 'Vol 772K' && tip.lines[1].startsWith('O 0.83')) return tip;
  }
  throw new Error(`no hover position shows ${stamp}`);
};

describe('PatternChart barMin on NXAT 5-min (a real served tile)', () => {
  const b0810 = NXAT_5M.find((b) => b.t === '2026-11-27 08:10')!;

  it('the served 08:10 bar is the 771,509 bar (probe value)', () => {
    expect(b0810.v).toBe(771509);
    expect(b0810.s).toBe('pre');
  });

  it('barMin={5}: the hover prints 08:05–08:10 and the box widens to fit it', () => {
    const { container } = draw({ barMin: 5 });
    const tip = hoverBar(container.querySelector('svg')!, '08:10');
    expect(tip.lines[0]).toBe('2026-11-27 08:05–08:10 · pre');
    expect(tip.lines).toEqual(hoverLines(b0810, 5));
    expect(tip.w).toBe(hoverTipWidth(b0810, 5));
    expect(tip.w).toBeGreaterThan(HOVER_TIP_W);
  });

  it('NEGATIVE: without barMin the hover prints exactly today\'s text and the box keeps 104', () => {
    const { container } = draw();
    const tip = hoverBar(container.querySelector('svg')!, '08:10');
    expect(tip.lines[0]).toBe('2026-11-27 08:10 · pre');
    expect(tip.lines).toEqual(hoverLines(b0810));
    expect(tip.w).toBe(104);
  });

  it('NEGATIVE: lines 2–4 (OHLC, the shortVol volume line) are the same with and without barMin', () => {
    const on = hoverBar(draw({ barMin: 5 }).container.querySelector('svg')!, '08:10');
    cleanup();
    const off = hoverBar(draw().container.querySelector('svg')!, '08:10');
    expect(on.lines.slice(1)).toEqual(off.lines.slice(1));
    expect(on.lines[3]).toBe('Vol 772K');
  });

  it('NEGATIVE: barMin 0 / NaN / a fraction → today\'s text and 104', () => {
    for (const m of [0, NaN, 2.5]) {
      const tip = hoverBar(draw({ barMin: m }).container.querySelector('svg')!, '08:10');
      expect(tip.lines[0]).toBe('2026-11-27 08:10 · pre');
      expect(tip.w).toBe(104);
      cleanup();
    }
  });

  it('NEGATIVE: the svg without a hover is byte-identical with and without barMin', () => {
    const a = draw({ barMin: 5 }).container.innerHTML;
    cleanup();
    const b = draw().container.innerHTML;
    expect(a).toBe(b);
  });
});

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('barMin is passed by the 🚩 board and the 👀 Watch tile only', () => {
  it('GajjalaBoard passes tfBarMin(t.tf); GajjalaWatchTile passes tfBarMin(f.tf) — once each', async () => {
    const board = await readSource('src/components/GajjalaBoard.tsx');
    const watch = await readSource('src/components/GajjalaWatchTile.tsx');
    expect(board.match(/barMin=\{tfBarMin\(t\.tf\) \?\? undefined\}/g)).toHaveLength(1);
    expect(board.match(/barMin=/g)).toHaveLength(1);
    expect(watch.match(/barMin=\{tfBarMin\(f\.tf\) \?\? undefined\}/g)).toHaveLength(1);
    expect(watch.match(/barMin=/g)).toHaveLength(1);
  });
  it('NEGATIVE: no other component file passes barMin to PatternChart (every other tab byte-identical)', async () => {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    const dir = `${root}/src/components`;
    const hits = (fs.readdirSync(dir) as string[])
      .filter((f) => /\.tsx$/.test(f) && !/\.test\.tsx$/.test(f))
      .filter((f) => /barMin=/.test(fs.readFileSync(`${dir}/${f}`, 'utf8')))
      .sort();
    expect(hits).toEqual(['GajjalaBoard.tsx', 'GajjalaWatchTile.tsx']);
  });
});
