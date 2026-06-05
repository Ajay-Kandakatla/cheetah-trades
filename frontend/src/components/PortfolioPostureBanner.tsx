/* PortfolioPostureBanner — the top-down defensive read at the top of the portfolio.

   Ajay 2026-06-05: "the portfolio should be my guiding indicator that also factors
   the whole market being red." Shows the market POSTURE (risk_off / caution /
   constructive) + the book's defensive playbook when the tape is weak. The SAME
   posture drives the per-holding hold/sell verdict (position_lens overlay), so the
   banner explains why every card below has stepped to TIGHTEN/REDUCE. Not advice. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

type Posture = {
  posture: 'risk_off' | 'caution' | 'constructive' | string;
  level?: string | null;
  score?: number | null;
  breadth_red_pct?: number | null;
  safe_to_long?: boolean | null;
  drivers?: string[];
};

export function PortfolioPostureBanner() {
  const [p, setP] = useState<Posture | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetch(`${API}/market/posture`, { credentials: 'include' })
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => { if (alive && j) setP(j); })
        .catch(() => { /* fail quiet */ });
    load();
    const t = setInterval(load, 60_000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  // Only surface when defensiveness matters — a constructive tape needs no banner.
  if (!p || p.posture === 'constructive') return null;
  const riskOff = p.posture === 'risk_off';

  return (
    <div className={`port-posture ${riskOff ? 'is-riskoff' : 'is-caution'}`} role="status">
      <div className="port-posture__head">
        {riskOff ? '⚠️ Market is risk-off' : '⚠️ Market caution'}
        {p.drivers && p.drivers.length ? (
          <span className="port-posture__drivers"> · {p.drivers.join(' · ')}</span>
        ) : null}
      </div>
      <div className="port-posture__body">
        {riskOff
          ? 'The general market drives ~3 of 4 stocks (O’Neil “M”). Minervini’s playbook in a weak tape — tighten stops, take partial profits, raise cash. Your holdings below are stepped to TIGHTEN (and to REDUCE where the name itself is also weakening). Analytical gauge, not advice.'
          : 'Mixed tape — stay selective and keep stops tight. Analytical gauge, not advice.'}
      </div>
    </div>
  );
}
