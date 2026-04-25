import { useEffect, useRef } from 'react';

interface Props {
  values: number[] | undefined;
  width?: number;
  height?: number;
}

/**
 * Canvas sparkline — zero external dependencies. Path color follows the
 * direction of the series (green up / red down) and is pulled from CSS tokens
 * so it respects light/dark theme.
 */
export function Sparkline({ values, width = 96, height = 28 }: Props) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const c = ref.current;
    if (!c || !values || values.length < 2) return;
    const ctx = c.getContext('2d');
    if (!ctx) return;

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

    // Pull colors from theme tokens so dark/light swap works
    const rootStyle = getComputedStyle(document.documentElement);
    const stroke =
      rootStyle.getPropertyValue(up ? '--positive' : '--negative').trim() ||
      (up ? '#3F7A50' : '#A34848');

    ctx.strokeStyle = stroke;
    ctx.lineWidth = 1.1;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    values.forEach((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Subtle wash below the line
    const tint = up ? 'rgba(63,122,80,0.08)' : 'rgba(163,72,72,0.08)';
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fillStyle = tint;
    ctx.fill();
  }, [values, width, height]);

  if (!values || values.length < 2) {
    return <span className="cm-sparkline-empty">—</span>;
  }
  return <canvas ref={ref} className="cm-sparkline" />;
}
