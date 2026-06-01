/**
 * RealtimeChips — live decision signals on a SEPA card:
 *
 *   🟢 Accum +$1.2M / 🔴 Distrib -$840K
 *        Real-time accumulation/distribution from the trade tape (this session),
 *        classified vs the NBBO (buy = lifted offer, sell = hit bid). Dark-pool
 *        share + dark-buy ratio in the tooltip (stealth institutional buying).
 *   🩳 Short 12.9% · 4.2d
 *        FINRA bi-monthly short interest — shown only when squeeze fuel is
 *        elevated/high (pct-primary). Days-to-cover + settlement trend in tip.
 *
 * Lazy + viewport-gated via useRealtimeSignals. Accumulation polls every 6s
 * while the card is visible; both chips are absent (not errored) off-hours or
 * for names with no data.
 */
import { useRealtimeSignals } from '../hooks/useRealtimeSignals';

interface Props {
  symbol: string;
}

function fmtMoney(n: number | null | undefined): string {
  if (n == null) return '—';
  const a = Math.abs(n);
  const sign = n < 0 ? '−' : '+';
  if (a >= 1e9) return `${sign}$${(a / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${sign}$${(a / 1e3).toFixed(0)}K`;
  return `${sign}$${a.toFixed(0)}`;
}

const pct = (x: number | null | undefined): number => Math.round((x ?? 0) * 100);

export function RealtimeChips({ symbol }: Props) {
  const { ref, shortInterest, accumulation } = useRealtimeSignals(symbol);

  const acc = accumulation;
  const signal = acc && !acc.warming_up ? acc.signal : undefined;
  const net = acc?.session?.net_dollars;
  const darkPct = acc?.session?.dark_pct;
  const darkBuy = acc?.session?.dark_buy_ratio;
  const showAccum = signal === 'accumulation' || signal === 'distribution';

  const si = shortInterest;
  const squeeze = si?.available ? si.squeeze : undefined;
  const showSqueeze = squeeze === 'elevated' || squeeze === 'high';

  return (
    <div ref={ref} style={{ display: 'contents' }}>
      {showAccum && (
        <span
          className={`rt-chip ${signal === 'accumulation' ? 'rt-accum' : 'rt-distrib'}`}
          title={
            `Live tape (this session): ${signal}. ` +
            `Net ${fmtMoney(net)} buyer-dollars ${net != null && net >= 0 ? 'into' : 'out of'} the stock. ` +
            `Buy = trade lifted the offer, sell = hit the bid (quote test vs NBBO).` +
            (darkPct != null ? `\nDark-pool: ${pct(darkPct)}% of volume off-exchange` : '') +
            (darkBuy != null ? `, ${pct(darkBuy)}% of it buyer-initiated (stealth accumulation).` : '.')
          }
        >
          {signal === 'accumulation' ? '🟢 Accum' : '🔴 Distrib'} {fmtMoney(net)}
          {darkPct != null && darkPct >= 0.45 && darkBuy != null && darkBuy >= 0.55 ? ' 🌑' : ''}
        </span>
      )}
      {showSqueeze && (
        <span
          className={`si-chip ${squeeze === 'high' ? 'si-high' : 'si-elev'}`}
          title={
            `Short interest (settled ${si?.settlement_date ?? '—'}): ` +
            `${si?.pct_of_shares != null ? `${si.pct_of_shares}% of shares outstanding` : 'n/a'}` +
            `${si?.days_to_cover != null ? ` · ${si.days_to_cover} days-to-cover` : ''}` +
            `${si?.si_change_pct != null ? ` · ${si.si_change_pct > 0 ? '+' : ''}${si.si_change_pct}% vs prior settlement` : ''}` +
            `.\nSqueeze fuel: ${squeeze} (FINRA bi-monthly; % of shares outstanding, not free float).`
          }
        >
          🩳 Short {si?.pct_of_shares != null ? `${si.pct_of_shares}%` : (squeeze ?? '')}
          {si?.days_to_cover != null ? ` · ${si.days_to_cover}d` : ''}
        </span>
      )}
    </div>
  );
}
