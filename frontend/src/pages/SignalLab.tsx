/* Signal Lab page — chrome around the shared SignalLabBoard (which also
 * mounts as the Chart Maps ⚡ Signals tab). */
import { SignalLabBoard } from '../components/SignalLabBoard';

export function SignalLabPage() {
  return (
    <div className="cm-page">
      <header className="cm-pagehead">
        <div className="cm-pagehead__col">
          <div className="eyebrow">1-minute entries</div>
          <h1 className="display cm-pagehead__title">⚡ Signal Lab</h1>
          <p className="lede">
            Your tickers, live BUY / SELL tags on 1-minute candles — the
            opening range, liquidity sweeps and BOS/CHoCH structure this app
            already computes, composed into the five-step entry. Signals fire
            on closed bars only and never repaint.
          </p>
        </div>
      </header>
      <SignalLabBoard />
    </div>
  );
}
