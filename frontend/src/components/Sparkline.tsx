import { useEffect, useRef } from 'react';

interface Props {
  values: number[] | undefined;
  width?: number;
  height?: number;
}

/**
 * Canvas sparkline — zero external dependencies. Draws a smooth path
 * colored green/red based on whether the trend is up or down.
 */
export function Sparkline({ values, width = 84, height = 28 }: Props) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const c = ref.current;
    if (!c || !values || values.length < 2) return;
    const ctx = c.getContext('2d')!;
    const dpr = window.devicePixelRatio || 1;
    c.width = width * dpr;
    c.height = height * dpr;
    c.style.width = `${width}px`;
    c.style.height = `${height}px`;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = Math.max(max - min, 0.0001);
    const up = values[values.length - 1] >= values[0];
    const color = up ? '#10b981' : '#ef4444';

    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    values.forEach((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Area fill
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fillStyle = up ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)';
    ctx.fill();
  }, [values, width, height]);

  if (!values || values.length < 2) {
    return <span className="sparkline-empty">—</span>;
  }
  return <canvas ref={ref} className="sparkline" />;
}
