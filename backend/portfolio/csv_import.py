"""Fidelity CSV import — manual positions ingestion fallback.

Why this exists
---------------
Plaid Investments in Trial tier returns balances-only for active Fidelity
brokerage sub-accounts (TOD, RSU, 401k), withholding per-position data
until you apply for Investments Production. While that approval is
pending — or as a permanent fallback — users can dump Fidelity's own
"Download positions" CSV into here and get the same heatmap + R-multiples
+ alerts treatment that Plaid-returned holdings get.

Source of CSV
-------------
Fidelity → Accounts & Trade → Positions → "Download" button at top right.
File is named ``Portfolio_Positions_<MMM-DD-YYYY>.csv`` by default.

Format quirks Fidelity ships
----------------------------
- Dollar-formatted numbers:        "$7,432.00", "-$45.00", "+$2,432.00"
- Percent-formatted numbers:       "48.64%", "-0.60%"
- Quoted account names with commas:"Individual - TOD"
- Pending Activity rows:           skip (no ticker, no shares)
- Cash rows (FCASH** / SPAXX):     allowed through (they're real cash MMF positions)
- Account-total summary rows:      blank Symbol column → skip
- Disclaimer block at EOF:         non-CSV plain text → skip when parsing fails
- Column order:                    Fidelity occasionally renumbers; match by header name not index

This parser is intentionally permissive — Fidelity has shipped 4 minor
format revisions since 2022. We match column headers case-insensitively
and tolerate extra/missing columns.
"""
from __future__ import annotations

import csv
import io
import logging
import re
from typing import Iterable, Optional

log = logging.getLogger("portfolio.csv_import")


# Columns we care about, mapped to canonical names. Right side is what
# we read from Fidelity's CSV; left side is what we hand back. Match is
# case-insensitive and whitespace-tolerant.
_COLUMN_MAP: dict[str, str] = {
    "account_name":   "Account Name",
    "account_number": "Account Number",
    "symbol":         "Symbol",
    "description":    "Description",
    "quantity":       "Quantity",
    "last_price":     "Last Price",
    "current_value":  "Current Value",
    "cost_basis":     "Cost Basis Total",
    "avg_cost":       "Average Cost Basis",
    "type":           "Type",
}

# Symbols that Fidelity uses for pending activity / cash sweeps that aren't
# real tradeable tickers. Skip these on import.
_SKIP_SYMBOLS = {
    "",
    "PENDING ACTIVITY",
    "PENDING_ACTIVITY",
}


def _norm_header(s: str) -> str:
    """Normalize a CSV header for fuzzy matching: strip, lower, collapse spaces."""
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _parse_money(s: str | None) -> Optional[float]:
    """Parse Fidelity's money strings: '$7,432.00', '-$45.00', '+$2,432.00', '--'.
    Returns None for blanks, dashes, or anything unparseable."""
    if s is None:
        return None
    t = str(s).strip()
    if not t or t in ("--", "—", "n/a", "N/A"):
        return None
    # Strip $ and commas. Handle leading + (Fidelity uses it for gainers).
    t = t.replace("$", "").replace(",", "").replace("+", "").strip()
    # Handle (123.45) accounting-style negatives just in case.
    if t.startswith("(") and t.endswith(")"):
        t = "-" + t[1:-1]
    try:
        return float(t)
    except ValueError:
        return None


def _parse_qty(s: str | None) -> Optional[float]:
    """Parse Fidelity's quantity field: usually plain '100' or '42.265', but
    can be empty for cash rows."""
    if s is None:
        return None
    t = str(s).strip().replace(",", "")
    if not t or t in ("--", "—"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _build_account_label(account_name: str, account_number: str) -> str:
    """Build the per-row ``account`` field. Combines name + last-4 of
    account number so the same ticker held in two accounts (e.g. TOD + HSA)
    stays as two separate rows in the manual store (composite unique key
    is user × ticker × account)."""
    name = (account_name or "").strip() or "Fidelity"
    num = (account_number or "").strip()
    last4 = num[-4:] if len(num) >= 4 else num
    return f"{name} ({last4})" if last4 else name


def parse_fidelity_csv(content: bytes | str) -> dict:
    """Parse a Fidelity positions CSV. Returns:

    .. code-block:: python

       {
         "rows":    [ { ticker, shares, cost_basis, account, ...meta }, ... ],
         "skipped": [ { reason, line_no, raw } ],   # for debugging
         "total_value":  214_335.07,
         "imported":     12,
         "format_ok":    True,
       }

    Never raises on malformed input — returns ``format_ok=False`` instead
    so the API route can show a friendly error rather than 500.
    """
    if isinstance(content, bytes):
        # Fidelity ships UTF-8 with BOM occasionally; tolerate.
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")
    else:
        text = content

    # Strip Fidelity's trailing disclaimer block. It starts with a blank
    # line followed by paragraph text — easy to detect by absence of commas.
    lines = text.splitlines()
    csv_lines: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            csv_lines.append("")
            continue
        # If the line has no comma AND no quote, it's probably disclaimer prose.
        # Keep CSV-ish lines (header / data) only.
        if "," in s or '"' in s:
            csv_lines.append(ln)

    if not csv_lines:
        return {"rows": [], "skipped": [], "total_value": 0.0, "imported": 0, "format_ok": False, "error": "empty file"}

    reader = csv.reader(io.StringIO("\n".join(csv_lines)))
    try:
        header = next(reader)
    except StopIteration:
        return {"rows": [], "skipped": [], "total_value": 0.0, "imported": 0, "format_ok": False, "error": "no header row"}

    # Map our canonical names → column index by fuzzy header match.
    norm_header_index: dict[str, int] = {}
    for i, raw_col in enumerate(header):
        nh = _norm_header(raw_col)
        if nh and nh not in norm_header_index:
            norm_header_index[nh] = i

    col_idx: dict[str, Optional[int]] = {}
    for canonical, csv_name in _COLUMN_MAP.items():
        col_idx[canonical] = norm_header_index.get(_norm_header(csv_name))

    if col_idx["symbol"] is None or col_idx["quantity"] is None:
        return {
            "rows": [], "skipped": [], "total_value": 0.0, "imported": 0,
            "format_ok": False,
            "error": "missing required columns (Symbol and Quantity). Is this a Fidelity Portfolio_Positions CSV?",
            "headers_seen": list(header),
        }

    def cell(row: list[str], canonical: str) -> str:
        i = col_idx.get(canonical)
        if i is None or i >= len(row):
            return ""
        return (row[i] or "").strip()

    rows: list[dict] = []
    skipped: list[dict] = []
    total_value = 0.0

    for line_no, raw_row in enumerate(reader, start=2):  # line 2 = first data row
        if not raw_row or not any(c.strip() for c in raw_row):
            continue

        symbol_raw = cell(raw_row, "symbol")
        symbol = symbol_raw.strip().upper()
        # Drop Fidelity's "**" suffix that marks money-market core positions
        # (e.g. "FCASH**", "SPAXX**"). The underlying ticker still works.
        clean_symbol = symbol.rstrip("*").strip()

        if clean_symbol in _SKIP_SYMBOLS:
            skipped.append({"line": line_no, "reason": "non-position row", "raw_symbol": symbol_raw})
            continue

        # Real US tickers START with a letter and are ≤ 8 chars (with
        # one optional . or - for class-share notation like BRK.A or BF-B).
        # Fidelity occasionally writes 9-char CUSIPs (e.g. "09260L455") into
        # the Symbol column for specialty securities — those start with
        # digits, so the leading-letter requirement filters them cleanly.
        if not re.match(r"^[A-Z][A-Z0-9]{0,5}([.\-][A-Z]{1,2})?$", clean_symbol):
            skipped.append({"line": line_no, "reason": "non-ticker symbol", "raw_symbol": symbol_raw})
            continue

        qty = _parse_qty(cell(raw_row, "quantity"))
        if qty is None or qty <= 0:
            skipped.append({"line": line_no, "reason": "no shares", "raw_symbol": symbol_raw})
            continue

        cost_basis = _parse_money(cell(raw_row, "cost_basis"))
        last_price = _parse_money(cell(raw_row, "last_price"))
        current_value = _parse_money(cell(raw_row, "current_value"))
        avg_cost = _parse_money(cell(raw_row, "avg_cost"))

        # Derive missing values when possible.
        if cost_basis is None and avg_cost is not None and qty:
            cost_basis = round(avg_cost * qty, 2)
        if current_value is None and last_price is not None and qty:
            current_value = round(last_price * qty, 2)

        account = _build_account_label(
            cell(raw_row, "account_name"),
            cell(raw_row, "account_number"),
        )

        rows.append({
            "ticker":        clean_symbol,
            "shares":        qty,
            "cost_basis":    cost_basis,
            "avg_cost":      avg_cost,
            "last_price":    last_price,
            "current_value": current_value,
            "account":       account,
            "description":   cell(raw_row, "description"),
        })
        if current_value is not None:
            total_value += current_value

    return {
        "rows":         rows,
        "skipped":      skipped,
        "total_value":  round(total_value, 2),
        "imported":     len(rows),
        "format_ok":    True,
    }


# --------------------------------------------------------------------------
# Disk-sync — pick up CSVs the user drops into ``backend/fidelity/``
# without needing a UI upload. Cheaper UX: export from Fidelity →
# save into a watched folder (or sync via iCloud Drive / Dropbox) →
# Pounce ingests on a cron schedule + on-demand button.
# --------------------------------------------------------------------------
import os
from pathlib import Path
from typing import Tuple


def _drop_dir() -> Path:
    """Where users drop Fidelity CSVs. Override via env for tests / alt mount.

    Default is ``backend/fidelity/`` (mounted into the api container at
    ``/app/fidelity/``). We pick paths in this order:
      1. ``PORTFOLIO_CSV_DROP_DIR`` env var if set
      2. ``/app/fidelity`` (container default — backend bind-mount)
      3. ``./fidelity`` (when running locally without Docker)
    """
    env = os.getenv("PORTFOLIO_CSV_DROP_DIR")
    if env:
        return Path(env)
    if Path("/app/fidelity").exists():
        return Path("/app/fidelity")
    return Path("fidelity")


def find_latest_csv() -> Optional[Path]:
    """Return the most recently modified .csv file in the drop dir, or None.

    "Most recently modified" beats lexicographic sort because Fidelity's
    filename format ``Portfolio_Positions_<MMM-DD-YYYY>.csv`` orders
    alphabetically by month name (Apr < Aug < Dec < ...), not by date.
    mtime sidesteps that entirely.
    """
    d = _drop_dir()
    if not d.exists() or not d.is_dir():
        return None
    csvs = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() == ".csv"]
    if not csvs:
        return None
    csvs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return csvs[0]


def list_csvs() -> list[dict]:
    """List every CSV in the drop dir, newest first. Used by the UI's
    "Sync from disk" button to show what's available before ingest."""
    d = _drop_dir()
    if not d.exists():
        return []
    out = []
    for p in d.iterdir():
        if not (p.is_file() and p.suffix.lower() == ".csv"):
            continue
        st = p.stat()
        out.append({
            "name":     p.name,
            "size":     st.st_size,
            "mtime":    int(st.st_mtime),
        })
    out.sort(key=lambda r: r["mtime"], reverse=True)
    return out


def sync_from_disk(user_email: str, *, archive: bool = False) -> dict:
    """Find the newest CSV in the drop dir and ingest it.

    Returns a dict suitable for returning straight from a FastAPI route:
    ``{"ok": True, "file": "...", "written": N, ...}`` on success, or
    ``{"ok": False, "reason": "..."}`` if no file or parse failed.

    Set ``archive=True`` to move the processed file to ``<dir>/archive/``
    after ingest. Useful for cron-driven sync where you only want each
    CSV processed once. For the manual button (idempotent re-ingest),
    keep ``archive=False`` so the user can re-trigger if needed.
    """
    latest = find_latest_csv()
    if latest is None:
        return {
            "ok":     False,
            "reason": f"no CSV files found in {_drop_dir()}",
            "hint":   "Drop a Fidelity 'Download Positions' CSV into this folder.",
        }

    try:
        content = latest.read_bytes()
    except OSError as exc:
        return {"ok": False, "reason": f"could not read {latest.name}: {exc}"}

    parsed = parse_fidelity_csv(content)
    if not parsed.get("format_ok"):
        return {
            "ok":      False,
            "reason":  parsed.get("error", "unrecognized CSV format"),
            "file":    latest.name,
            "headers": parsed.get("headers_seen") or [],
        }

    result = apply_to_store(user_email, parsed, replace_account=True)
    result["file"] = latest.name
    result["parsed_summary"] = {
        "imported_rows": parsed["imported"],
        "total_value":   parsed["total_value"],
        "skipped":       len(parsed.get("skipped") or []),
    }

    if archive and result.get("ok"):
        archive_dir = latest.parent / "archive"
        try:
            archive_dir.mkdir(exist_ok=True)
            target = archive_dir / latest.name
            # If a same-named file already archived (e.g. re-export on the
            # same day), append a timestamp suffix so we don't overwrite.
            if target.exists():
                target = archive_dir / f"{latest.stem}.{int(latest.stat().st_mtime)}{latest.suffix}"
            latest.rename(target)
            result["archived_to"] = str(target.relative_to(latest.parent.parent))
        except OSError as exc:
            log.warning("portfolio.csv_import: archive failed: %s", exc)
            result["archive_error"] = str(exc)

    return result


def apply_to_store(user_email: str, parsed: dict, *, replace_account: bool = True) -> dict:
    """Persist parsed rows to ``portfolio.store``. When ``replace_account``
    is True (default), delete all existing manual rows in the same account
    before re-inserting — this is the right semantics for "re-importing
    today's CSV" where the user expects yesterday's stale positions to be
    cleared. Set to False to merge instead (rare; useful for partial CSVs).
    """
    from portfolio import store

    if not parsed.get("format_ok"):
        return {"ok": False, "reason": parsed.get("error", "bad CSV")}

    rows = parsed["rows"]

    if replace_account:
        # Delete existing manual rows for each account that's about to be
        # rewritten. We can't do a blanket delete-all because the user
        # might have manually-typed positions in OTHER accounts we don't
        # want to wipe.
        accounts_in_csv = {r["account"] for r in rows}
        db = store._get_db()
        if db is not None:
            for acct in accounts_in_csv:
                db.portfolio_holdings.delete_many({
                    "user_email": user_email.lower(),
                    "account":    acct,
                })

    written = 0
    failed: list[dict] = []
    for r in rows:
        res = store.upsert_holding(
            user_email,
            r["ticker"],
            r["shares"],
            r["cost_basis"] or 0.0,
            account=r["account"],
            tags=["csv-import"],
            notes=(r.get("description") or "")[:200],
        )
        if res.get("ok"):
            written += 1
        else:
            failed.append({"ticker": r["ticker"], "reason": res.get("reason")})

    return {
        "ok":           True,
        "written":      written,
        "failed":       failed,
        "total_value":  parsed["total_value"],
        "skipped_csv":  len(parsed.get("skipped") or []),
    }
