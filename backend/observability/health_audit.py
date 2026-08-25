"""Health audit — fail-safe observability for silently-failing critical data.

Runs a battery of IN-PROCESS checks (no auth, no HTTP self-calls) against the
app's own data + compute layer, on a cron. On a CRITICAL miss it pushes the
owner (existing web-push), writes a structured line to the app log file, and
persists the result to Mongo + a JSON artifact. Optional external sinks let any
platform watch it:

  • Healthchecks.io dead-man's-switch  — env HEALTHCHECKS_URL (pinged every run;
    `/fail` on critical). If the audit cron itself dies, Healthchecks alerts.
  • Generic webhook                    — env OBSERVABILITY_WEBHOOK_URL (POSTs the
    audit summary; works with Datadog events / New Relic / Better Stack / Slack).
  • Rotating log file                  — point any agent (Datadog/Splunk/Vector)
    at ~/.cheetah/logs/cheetah.log for full log observability.

Cadence (crontab): a heartbeat a few times a day catches a dead pipeline within
hours; a digest every 2 days summarizes even when green. NOT a trading signal.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:
    _ET = None

from .logsetup import LOG_DIR, LOG_PATH, install_file_handler, install_redaction

log = logging.getLogger("observability.health_audit")

HEALTH_DIR = Path(os.getenv("CHEETAH_HEALTH_DIR", str(Path.home() / ".cheetah" / "health")))
AUDIT_PATH = HEALTH_DIR / "latest_audit.json"
STATE_PATH = HEALTH_DIR / "alert_state.json"

CRITICAL = "critical"
WARN = "warn"

# Freshness thresholds (hours / days) — tune here.
SCAN_MAX_AGE_WEEKDAY_H = 30
SCAN_MAX_AGE_WEEKEND_H = 96
PULLBACK_MAX_AGE_WEEKDAY_H = 30
MACRO_MAX_AGE_H = 8
PRICE_MAX_AGE_DAYS = 5
LOG_TAIL_LINES = 5000
LOG_ERROR_WARN_THRESHOLD = 60


# ── small helpers ────────────────────────────────────────────────────────────
def _now_et() -> datetime:
    return datetime.now(_ET) if _ET else datetime.utcnow()


def _is_weekend() -> bool:
    return _now_et().weekday() >= 5


def _age_hours(epoch) -> Optional[float]:
    try:
        return round((time.time() - float(epoch)) / 3600.0, 1)
    except (TypeError, ValueError):
        return None


def _ok(name, category, detail="", value=None):
    return {"name": name, "category": category, "ok": True,
            "severity": None, "detail": detail, "value": value}


def _fail(name, category, severity, detail="", value=None):
    return {"name": name, "category": category, "ok": False,
            "severity": severity, "detail": detail, "value": value}


def _tail(path: Path, n: int) -> list:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return list(deque(f, maxlen=n))


# ── checks (each returns one result dict; errors degrade to a WARN) ──────────
def check_mongo():
    try:
        from sepa import history
        db = history._get_db()
        if db is None:
            return _fail("mongo", "infra", CRITICAL, "Mongo handle is None")
        db.command("ping")
        return _ok("mongo", "infra", "reachable")
    except Exception as exc:
        return _fail("mongo", "infra", CRITICAL, f"ping failed: {exc}")


def check_scan_fresh():
    try:
        from sepa import scanner
        latest = scanner.load_latest()
        if not latest:
            return _fail("scan_fresh", "data", CRITICAL, "no latest scan on disk")
        age = _age_hours(latest.get("generated_at"))
        if age is None:
            return _fail("scan_fresh", "data", WARN, "scan missing generated_at")
        cap = SCAN_MAX_AGE_WEEKEND_H if _is_weekend() else SCAN_MAX_AGE_WEEKDAY_H
        if age > cap:
            return _fail("scan_fresh", "data", CRITICAL,
                         f"latest scan {age}h old (cap {cap}h) — fast-scan cron may be down", age)
        return _ok("scan_fresh", "data", f"{age}h old", age)
    except Exception as exc:
        return _fail("scan_fresh", "data", WARN, f"check error: {exc}")


def check_scan_nonempty():
    try:
        from sepa import scanner
        latest = scanner.load_latest() or {}
        analyzed = latest.get("analyzed")
        if not analyzed:
            return _fail("scan_nonempty", "data", CRITICAL,
                         "0 symbols analyzed in the latest scan", analyzed)
        return _ok("scan_nonempty", "data",
                   f"{analyzed} analyzed, {latest.get('candidate_count')} candidates", analyzed)
    except Exception as exc:
        return _fail("scan_nonempty", "data", WARN, f"check error: {exc}")


def check_price_cache():
    try:
        from sepa import prices
        df = prices.load_prices("SPY")
        if df is None or not len(df):
            return _fail("price_cache", "data", CRITICAL, "no SPY price data in cache")
        last = date.fromisoformat(str(df.index[-1])[:10])
        age_days = (date.today() - last).days
        if age_days > PRICE_MAX_AGE_DAYS:
            return _fail("price_cache", "data", CRITICAL,
                         f"SPY last bar {age_days}d old — price pipeline stale", age_days)
        return _ok("price_cache", "data", f"SPY bar {age_days}d old", age_days)
    except Exception as exc:
        return _fail("price_cache", "data", WARN, f"check error: {exc}")


def check_market_gauge():
    try:
        from sepa import market_gauge
        g = market_gauge.compute()
        s = g.get("score")
        if not isinstance(s, (int, float)) or not (0 <= s <= 100):
            return _fail("market_gauge", "compute", WARN, f"bad score {s}")
        return _ok("market_gauge", "compute", f"score {s} ({g.get('state')})", s)
    except Exception as exc:
        return _fail("market_gauge", "compute", WARN, f"compute raised: {exc}")


def check_macro_risk():
    try:
        from sepa import macro_risk
        m = macro_risk.get_market()
        if not m:
            return _fail("macro_risk", "data", WARN, "no macro read")
        age = _age_hours(m.get("as_of")) if isinstance(m.get("as_of"), (int, float)) else None
        if age is not None and age > MACRO_MAX_AGE_H:
            return _fail("macro_risk", "data", WARN, f"macro read {age}h old", age)
        return _ok("macro_risk", "data", f"level {m.get('level')}", m.get("level"))
    except Exception as exc:
        return _fail("macro_risk", "data", WARN, f"check error: {exc}")


def check_pullback_artifact():
    try:
        from sepa import pullback_ma
        p = pullback_ma.load_latest_pullback()
        if not p:
            return _fail("pullback_artifact", "data", WARN,
                         "no pullback artifact yet (cron not run)")
        age = _age_hours(p.get("generated_at"))
        cap = SCAN_MAX_AGE_WEEKEND_H if _is_weekend() else PULLBACK_MAX_AGE_WEEKDAY_H
        if age is not None and age > cap:
            return _fail("pullback_artifact", "data", WARN, f"pullback {age}h old", age)
        return _ok("pullback_artifact", "data", f"{p.get('candidate_count')} candidates",
                   p.get("candidate_count"))
    except Exception as exc:
        return _fail("pullback_artifact", "data", WARN, f"check error: {exc}")


def check_log_errors():
    try:
        if not LOG_PATH.exists():
            return _ok("log_errors", "logs", "no log file yet")
        lines = _tail(LOG_PATH, LOG_TAIL_LINES)
        errs = sum(1 for ln in lines
                   if ("ERROR" in ln or "Traceback" in ln or "CRITICAL" in ln))
        if errs > LOG_ERROR_WARN_THRESHOLD:
            return _fail("log_errors", "logs", WARN,
                         f"{errs} error lines in the last {len(lines)} log lines", errs)
        return _ok("log_errors", "logs", f"{errs} errors / {len(lines)} recent lines", errs)
    except Exception as exc:
        return _fail("log_errors", "logs", WARN, f"check error: {exc}")


def check_disk():
    try:
        import shutil
        probe = LOG_DIR if LOG_DIR.exists() else Path("/")
        free_gb = round(shutil.disk_usage(str(probe)).free / (1024 ** 3), 1)
        if free_gb < 1.0:
            return _fail("disk", "infra", WARN, f"only {free_gb}GB free on the scans volume", free_gb)
        return _ok("disk", "infra", f"{free_gb}GB free", free_gb)
    except Exception as exc:
        return _fail("disk", "infra", WARN, f"check error: {exc}")


def check_13f_quarter_current():
    """Is the institutional-holder data still reporting a quarter that is long
    past its SEC deadline?

    Deliberately NOT an age check. The 13F cache refreshes every 24h, so
    `cached_at` is always fresh while the CONTENT sits a quarter behind — on
    2026-08-16 the APGE payload was minutes old and still said Q1 2026. Only a
    cadence check catches that (Ajay: "The accumulations are dated now").

    WARN, never CRITICAL: a provider lagging a quarter is worth seeing on the
    monthly sweep, not worth a push.
    """
    try:
        from . import period_freshness as pf
        res = pf.audit_whales_cache()
        if not res.get("ok") and res.get("reason"):
            return _fail("13f_quarter_current", "data", WARN,
                         res["reason"], res.get("expected_quarter"))
        if not res.get("ok"):
            return _fail("13f_quarter_current", "data", WARN,
                         res.get("detail", ""), res.get("rolled_pct"))
        return _ok("13f_quarter_current", "data",
                   res.get("detail", ""), res.get("rolled_pct"))
    except Exception as exc:
        return _fail("13f_quarter_current", "data", WARN, f"check error: {exc}")


def check_universe_counts():
    """Is every ticker list still the size it should be?

    Ajay 2026-08-16: "May be add a count checks for returned values for all the
    tickers API like Russel 3000 and S&P 500 as well."

    This is the check that would have caught the bug that prompted it:
    `load_universe("sp1500_plus")` silently returned the curated 158 names, so
    /supply-demand ran a 158-name scan while its UI said "S&P 1500". Nothing
    errored — the list was simply a different list.

    WARN, never CRITICAL. A source going stale means a narrower scan, not a
    wrong trade, and Ajay's push keep-set is deliberately three kinds.
    """
    try:
        from sepa import universe as U
        res = U.universe_counts()
        failing = res.get("_failing") or []
        n = len([k for k in res if k != "_failing"])
        if failing:
            detail = ", ".join(
                f"{k}={res[k].get('count')} (want {res[k]['expected'][0]}-"
                f"{res[k]['expected'][1]})" for k in failing)
            return _fail("universe_counts", "data", WARN,
                         f"{len(failing)}/{n} ticker lists outside their sane "
                         f"range: {detail}", len(failing))
        return _ok("universe_counts", "data",
                   f"all {n} ticker lists within their sane range", 0)
    except Exception as exc:
        return _fail("universe_counts", "data", WARN,
                     f"universe count check failed: {exc}", None)


def check_symbol_liveness():
    """Has any symbol we cover stopped printing bars?

    Ajay 2026-08-16: "look at this issue with SATS stocks" — the page said SATS
    was delisted while it traded at $91.89 (EchoStar had renamed to ECHO).

    check_price_cache above asks how OLD the cache is, and it was right every
    day: SQ's price document refreshed on schedule for 576 days with the same
    dead bars inside it. This asks when each symbol's newest bar actually
    printed, which is the only question that catches a rename.

    WARN, never CRITICAL. A dead ticker narrows the scan; it does not place a
    trade, and the push keep-set is deliberately three kinds.
    """
    try:
        from . import symbol_liveness as sl
        res = sl.scan()
        n = res.get("stopped") or 0
        if res.get("renames_regressed"):
            return _fail("symbol_liveness", "data", WARN, res.get("detail", ""), n)
        if not res.get("ok"):
            names = ", ".join(r["symbol"] for r in (res.get("symbols") or [])[:8])
            return _fail("symbol_liveness", "data", WARN,
                         f"{n} symbols have stopped printing bars: {names}"
                         f"{' …' if n > 8 else ''}", n)
        return _ok("symbol_liveness", "data",
                   f"all {res.get('fresh', 0)} symbols printing bars", 0)
    except Exception as exc:
        return _fail("symbol_liveness", "data", WARN,
                     f"symbol liveness check failed: {exc}", None)


def _mongo_db():
    from sepa import history
    return history._get_db()


def check_demand_scan_fresh():
    """The demand/supply/deep boards' scan actually ran today.

    Ajay 2026-08-25: "This had happened before where some scans failed
    silently." The demand cache is api-process memory this audit can't read,
    but every scan also writes per-day rows to the demand_history collection —
    that write is the evidence. WARN, not CRITICAL: the boards self-warm on
    the next page visit, so a missed cron is degradation, not an outage.
    """
    try:
        db = _mongo_db()
        if db is None:
            return _fail("demand_scan", "data", WARN, "Mongo unavailable")
        et = _now_et()
        # Weekend/Monday-premarket: Friday's run is the newest expectation.
        lookback = 4 if et.weekday() in (5, 6, 0) else 2
        days = [(et.date() - timedelta(days=i)).isoformat() for i in range(lookback)]
        n = db.demand_board_runs.count_documents({"et_date": {"$in": days}})
        if n == 0:
            return _fail("demand_scan", "data", WARN,
                         f"no demand-board runs recorded for {days} — the "
                         f"demand scan may be silently down", 0)
        return _ok("demand_scan", "data", f"{n} run(s) recorded over {days}", n)
    except Exception as exc:
        return _fail("demand_scan", "data", WARN, f"check error: {exc}")


def check_trade_flash_heartbeat():
    """The 5-minute trade-flash watch is actually ticking during the session.

    A quiet tape legitimately produces ZERO events, so the events collection
    cannot prove the job ran — the cli stamps an engine_heartbeat instead
    (same plumbing the alerts engine uses) and this reads it. Outside market
    hours the check passes vacuously.
    """
    try:
        et = _now_et()
        in_session = (et.weekday() < 5
                      and (et.hour, et.minute) >= (9, 45)
                      and et.hour < 16)
        if not in_session:
            return _ok("trade_flash", "engine", "market closed — not expected to tick")
        db = _mongo_db()
        if db is None:
            return _fail("trade_flash", "engine", WARN, "Mongo unavailable")
        doc = db.engine_heartbeat.find_one({"name": "trade_flash"})
        if not doc or not doc.get("ts"):
            return _fail("trade_flash", "engine", WARN,
                         "no trade-flash heartbeat ever recorded")
        age_min = (time.time() - float(doc["ts"])) / 60.0
        if age_min > 20:
            return _fail("trade_flash", "engine", WARN,
                         f"trade-flash watch last ticked {age_min:.0f}m ago "
                         f"(runs every 5m in session)", round(age_min, 1))
        return _ok("trade_flash", "engine", f"ticked {age_min:.0f}m ago",
                   round(age_min, 1))
    except Exception as exc:
        return _fail("trade_flash", "engine", WARN, f"check error: {exc}")


def check_zero_dte_ledger():
    """The 0DTE board's ledger froze a run this morning (weekdays)."""
    try:
        et = _now_et()
        if et.weekday() >= 5:
            return _ok("zero_dte_ledger", "data", "weekend — no run expected")
        if (et.hour, et.minute) < (10, 15):
            return _ok("zero_dte_ledger", "data", "before the 10:00 record run")
        db = _mongo_db()
        if db is None:
            return _fail("zero_dte_ledger", "data", WARN, "Mongo unavailable")
        doc = db.zero_dte_runs.find_one({"et_date": et.date().isoformat()})
        if not doc:
            return _fail("zero_dte_ledger", "data", WARN,
                         f"no 0DTE run recorded for {et.date()} (10:00 cron)")
        return _ok("zero_dte_ledger", "data", f"recorded for {et.date()}")
    except Exception as exc:
        return _fail("zero_dte_ledger", "data", WARN, f"check error: {exc}")


def check_research_cache_age():
    """The weekly Bonde-fundamentals research refresh is not falling behind.

    Feeds the Deep Demand and Gabbar sales gates. Cron: Sunday 20:00 ET,
    TTL 8 days — WARN once the bulk of the cache is older than the TTL
    would ever allow after a healthy Sunday run.
    """
    try:
        from sepa import research
        st = research.status()
        if not st.get("available"):
            return _fail("research_cache", "data", WARN,
                         f"research cache unavailable: {st.get('reason')}")
        total, fresh = st.get("total") or 0, st.get("fresh") or 0
        if total == 0:
            return _fail("research_cache", "data", WARN, "research cache empty")
        pct = fresh / total * 100.0
        if pct < 60.0:
            return _fail("research_cache", "data", WARN,
                         f"only {fresh}/{total} blobs fresh ({pct:.0f}%) — "
                         f"Sunday research-refresh may be failing",
                         round(pct, 1))
        return _ok("research_cache", "data", f"{fresh}/{total} fresh ({pct:.0f}%)",
                   round(pct, 1))
    except Exception as exc:
        return _fail("research_cache", "data", WARN, f"check error: {exc}")


CHECKS = [
    check_mongo, check_scan_fresh, check_scan_nonempty, check_price_cache,
    check_market_gauge, check_macro_risk, check_pullback_artifact,
    check_log_errors, check_disk, check_13f_quarter_current,
    check_universe_counts, check_symbol_liveness,
    # The scans that could fail with no visible trace before 2026-08-25 —
    # added the day the pullback artifact was found 96h stale with the audit
    # WARNing into a void (Ajay: "some scans failed silently").
    check_demand_scan_fresh, check_trade_flash_heartbeat,
    check_zero_dte_ledger, check_research_cache_age,
]


# ── persistence + external sinks (all best-effort) ───────────────────────────
def _persist(audit: dict) -> None:
    try:
        HEALTH_DIR.mkdir(parents=True, exist_ok=True)
        AUDIT_PATH.write_text(json.dumps(audit, default=str))
    except Exception as exc:
        log.debug("health persist file failed: %s", exc)
    try:
        from sepa import history
        db = history._get_db()
        if db is not None:
            db.health_audit_history.insert_one(dict(audit, _ingested=int(time.time())))
            db.health_audit_history.delete_many(
                {"generated_at": {"$lt": int(time.time()) - 30 * 86400}})
    except Exception as exc:
        log.debug("health persist mongo failed: %s", exc)


def _http_get(url: str) -> None:
    try:
        import requests
        requests.get(url, timeout=5)
    except Exception as exc:
        log.debug("healthcheck ping failed %s: %s", url, exc)


def _ping_healthchecks(status: str) -> None:
    url = os.getenv("HEALTHCHECKS_URL")
    if not url:
        return
    _http_get(url.rstrip("/") + "/fail" if status == "critical" else url)


def _post_webhook(audit: dict) -> None:
    url = os.getenv("OBSERVABILITY_WEBHOOK_URL")
    if not url:
        return
    try:
        import requests
        requests.post(url, timeout=5, json={
            "source": "cheetah-health-audit",
            "status": audit["status"],
            "n_critical": audit["n_critical"],
            "n_warn": audit["n_warn"],
            "failing": [c for c in audit["checks"] if not c["ok"]],
            "generated_at_iso": audit["generated_at_iso"],
        })
    except Exception as exc:
        log.debug("observability webhook failed: %s", exc)


def _owner_email() -> Optional[str]:
    try:
        from auth import HOUSE_OWNER_EMAILS
        return HOUSE_OWNER_EMAILS[0] if HOUSE_OWNER_EMAILS else None
    except Exception:
        return None


def _push(title: str, body: str) -> None:
    try:
        from push import sender
        payload = {"title": title, "body": body[:300], "tag": "health-audit",
                   "url": "/health", "kind": "health"}
        owner = _owner_email()
        # kind=None => always deliver (a fail-safe alert must not be muted by prefs).
        if owner:
            sender.send_to_user(owner, payload, kind=None)
        else:
            sender.send_to_all(payload, kind=None)
    except Exception as exc:
        log.warning("health push failed: %s", exc)


def _load_state() -> dict:
    try:
        if STATE_PATH.exists():
            return json.loads(STATE_PATH.read_text())
    except Exception:
        pass
    return {}


def _save_state(state: dict) -> None:
    try:
        HEALTH_DIR.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state))
    except Exception:
        pass


def _maybe_alert(audit: dict, crit: list, digest: bool) -> None:
    # De-dupe: alert at most ONCE PER ET DAY per failing check (a daily reminder
    # while broken, never spam within a day).
    today = _now_et().strftime("%Y-%m-%d")
    state = _load_state()
    fresh = [r for r in crit if state.get(r["name"]) != today]
    if fresh:
        body = "; ".join(f"{r['name']}: {r['detail']}" for r in fresh[:4])
        _push(f"⚠️ Cheetah health: {len(crit)} critical", body)
        for r in crit:
            state[r["name"]] = today
        _save_state(state)
    elif digest:
        _push("🩺 Cheetah health digest",
              f"{audit['status'].upper()} · {audit['n_critical']} critical / "
              f"{audit['n_warn']} warn / {audit['n_checks']} checks")


# ── the audit ────────────────────────────────────────────────────────────────
def run_audit(alert: bool = True, digest: bool = False) -> dict:
    """Run the full check battery (the loop), aggregate, log, persist, alert."""
    install_file_handler()
    install_redaction()
    t0 = time.time()
    results: list = []
    for chk in CHECKS:
        try:
            results.append(chk())
        except Exception as exc:                       # a crashing check never sinks the audit
            results.append(_fail(getattr(chk, "__name__", "check"), "infra", WARN,
                                 f"check crashed: {exc}"))

    crit = [r for r in results if not r["ok"] and r["severity"] == CRITICAL]
    warns = [r for r in results if not r["ok"] and r["severity"] == WARN]
    status = "critical" if crit else ("degraded" if warns else "ok")

    audit = {
        "generated_at": int(time.time()),
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_sec": round(time.time() - t0, 2),
        "status": status,
        "n_checks": len(results),
        "n_critical": len(crit),
        "n_warn": len(warns),
        "checks": results,
    }

    summary = (f"HEALTH {status.upper()} — {len(crit)} critical, {len(warns)} warn "
               f"({len(results)} checks) :: "
               + "; ".join(f"{r['name']}={'ok' if r['ok'] else r['severity']}" for r in results))
    (log.error if crit else (log.warning if warns else log.info))(summary)

    _persist(audit)
    _ping_healthchecks(status)
    _post_webhook(audit)
    if alert:
        _maybe_alert(audit, crit, digest)
    return audit


def load_latest_audit() -> Optional[dict]:
    try:
        if AUDIT_PATH.exists():
            return json.loads(AUDIT_PATH.read_text())
    except Exception as exc:
        log.debug("load audit failed: %s", exc)
    return None
