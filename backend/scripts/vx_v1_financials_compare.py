"""vX vs v1 financials — the 2026-09-30 old-vs-new comparison, re-runnable
until the vX sunset (2026-10-09).

Run the SAME script twice inside the api container and diff the two JSONs:

  old: the LAST vX commit (0b708d20) copied into the container's /tmp/vxold
       (never into /app), run with PYTHONPATH=/tmp/vxold and mode `old` — vX
       410 brownouts are retried every 5 s, 12 times.
  new: the migrated tree the same way (/tmp/v1new), mode `new`.

Writes /tmp/cmp_<mode>.json. Results are recorded in
docs/sepa/massive_fundamentals_v1.md ("Old vs new").
"""
import json, sys, time, os, math
import requests
MODE = sys.argv[1]
SYMS = ["AAPL","NVDA","MU","SMCI","HRMY","CRWV","MSFT","AVGO","CMG","WMT","META","GOOGL","BRK.B","ARR","DX","SM","RKT","CRWD","LLY","PLTR","ORCL","IOVA","ASO","NTSK"]
if MODE == "old":
    _orig = requests.Session.request
    def _retry(self, method, url, *a, **k):
        for i in range(12):
            r = _orig(self, method, url, *a, **k)
            if "reference/financials" in str(url) and r.status_code == 410:
                time.sleep(5); continue
            return r
        return r
    requests.Session.request = _retry
from sepa import canslim, longterm, board_metrics as BM, capital_returns as CR
def clean(o):
    if isinstance(o, float):
        return None if not math.isfinite(o) else round(o, 4)
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    return o
out = {}
for s in SYMS:
    row = {}
    try:
        m = canslim._fetch_massive_financials(s)
        row["canslim"] = None if m is None else {k: m.get(k) for k in ("q_eps_growth_pct","y_eps_growth_pct","rev_growth_q_pct","q_period_series","eps_q_series","rev_q_series","ni_q_series","inv_q_series")}
        if m is None and MODE == "new":
            row["canslim_err"] = canslim._massive_last_error.get(s)
    except Exception as e:
        row["canslim_exc"] = type(e).__name__
    try:
        lt = longterm.metrics(s)
        row["longterm"] = {k: lt.get(k) for k in ("ok","reason","error","years","metrics","coverage")}
    except Exception as e:
        row["longterm_exc"] = type(e).__name__
    try:
        q = BM._fetch_quarters(s)
        live = BM._live_shares(s)
        row["shares_yoy"] = BM.shares_yoy(q, live)
        cr = CR.compute(q)
        row["capital"] = {k: cr.get(k) for k in ("period","period_end","filing_date","period_is_derived","roce_pct","roic_pct","roe_pct","asset_turnover","effective_tax_rate","ttm_ebit","ttm_net_income","ttm_revenue","ttm_operating_cash_flow","roe_basis","reasons")}
        row["n_quarters"] = len(q)
    except Exception as e:
        row["bm_exc"] = "%s %s" % (type(e).__name__, getattr(e, "reason", ""))
    out[s] = clean(row)
    print(s, "done", file=sys.stderr, flush=True)
json.dump(out, open("/tmp/cmp_%s.json" % MODE, "w"), indent=1, default=str)
print("wrote", MODE)
