"""Audit silent scan failures — group WARNING/ERROR/Traceback log lines by
message template and rank by frequency.

Most scanner code paths swallow exceptions into log.warning/log.debug and
return None for the offending symbol. The symbol then silently drops out
of the candidate list. Over a Russell-1000 universe this is invisible at
the UI level — a scan with 200 silently-failing symbols looks identical
to one with 0.

This script pulls the last N minutes of docker compose logs for the
relevant services, normalizes message templates (so 'AAPL failed' and
'NVDA failed' bucket together), and prints:
  - top error templates with counts + a sample line
  - any Python tracebacks (and the modules they originate from)
  - which symbols failed most often (so you can spot-check them)

READ-ONLY. Run from the host (NOT inside the api container — needs
access to the docker socket / compose CLI):

    python backend/sepa/audit_scan_errors.py --since 20m

The Mac mini already has docker on PATH; this just shells out to it.

Optional flags:
    --since 1h            # log window (default 20m)
    --services api,cron   # which compose services to read (default both)
    --level WARNING       # minimum level (default WARNING; also accepts ERROR, INFO)
    --max-templates 30    # how many top buckets to show
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter, defaultdict


# Heuristic level ordering for filtering.
LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "WARN": 30, "ERROR": 40, "CRITICAL": 50}

# Patterns we use to normalize variable bits of log messages so different
# symbols/numbers/tickers bucket into the same template.
# Order matters — more specific patterns first.
NORMALIZERS = [
    (re.compile(r"\b[A-Z]{1,5}(?:\.[A-Z]{1,3})?\b(?=\s|:|$|\)|,)"), "<SYM>"),   # tickers
    (re.compile(r"\b\d{4}-\d{2}-\d{2}T?[\d:.]*Z?\b"), "<TS>"),                    # ISO timestamps
    (re.compile(r"\b\d{10,}\b"), "<EPOCH>"),                                      # unix ms / large ints
    (re.compile(r"\bhttps?://\S+"), "<URL>"),
    (re.compile(r"\b\d+\.\d+\b"), "<FLOAT>"),
    (re.compile(r"\b\d+\b"), "<INT>"),
    (re.compile(r"0x[0-9a-fA-F]+"), "<HEX>"),
]


def normalize(msg: str) -> str:
    out = msg
    for pat, repl in NORMALIZERS:
        out = pat.sub(repl, out)
    # Collapse repeated whitespace
    out = re.sub(r"\s+", " ", out).strip()
    return out


# Logging line shape (best-effort):
#   2026-05-27 21:34:01,123 LEVEL module.path message ...
# uvicorn/fastapi also emits non-stdlib lines; we try a couple regexes.
_LINE_PAT = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s+"
    r"(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL)\s+"
    r"(?P<logger>\S+)\s+"
    r"(?P<msg>.*)$"
)
_TRACEBACK_START = re.compile(r"^Traceback \(most recent call last\):")
_TRACEBACK_FILE  = re.compile(r'^\s+File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<fn>\S+)')


def fetch_logs(services: list[str], since: str) -> str:
    cmd = ["docker", "compose", "logs", "--since", since, "--no-color", "--tail=all", *services]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        print("ERROR: `docker` not found on PATH. Run from the host, not inside a container.", file=sys.stderr)
        sys.exit(2)
    except subprocess.TimeoutExpired:
        print("ERROR: docker compose logs timed out after 60s.", file=sys.stderr)
        sys.exit(2)
    if r.returncode != 0:
        print(f"docker stderr: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(r.returncode)
    return r.stdout


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--since", default="20m", help="Log window, e.g. 20m / 1h / 24h (default 20m)")
    p.add_argument("--services", default="api,cron", help="Compose services, comma-sep (default api,cron)")
    p.add_argument("--level", default="WARNING", help="Minimum level: WARNING/ERROR (default WARNING)")
    p.add_argument("--max-templates", type=int, default=30)
    args = p.parse_args()

    min_level = LEVELS.get(args.level.upper(), 30)
    services = [s.strip() for s in args.services.split(",") if s.strip()]

    print(f"Reading docker compose logs --since {args.since} for {services} …")
    raw = fetch_logs(services, args.since)
    lines = raw.splitlines()
    print(f"  {len(lines)} log lines retrieved\n")

    # Pass 1: structured log lines (level + logger + message).
    bucket_counts: Counter[str] = Counter()
    bucket_samples: dict[str, str] = {}
    bucket_loggers: defaultdict[str, Counter] = defaultdict(Counter)
    bucket_symbols: defaultdict[str, Counter] = defaultdict(Counter)
    bucket_originals: defaultdict[str, list[str]] = defaultdict(list)

    # Pass 2: standalone tracebacks (their context lines lack the level prefix).
    traceback_count = 0
    traceback_files: Counter[str] = Counter()
    traceback_samples: list[str] = []

    in_traceback = False
    current_tb: list[str] = []

    sym_pat = re.compile(r"\b([A-Z]{1,5})\b")

    for line in lines:
        # Strip docker compose's "service-N | " prefix
        compose_prefix = re.match(r"^[a-z0-9_.-]+-\d+\s*\|\s*", line)
        if compose_prefix:
            line = line[compose_prefix.end():]

        # Traceback accumulation
        if _TRACEBACK_START.match(line):
            if current_tb:
                # Save the previous traceback
                _record_tb(current_tb, traceback_files, traceback_samples)
                traceback_count += 1
            current_tb = [line]
            in_traceback = True
            continue
        if in_traceback:
            if line.startswith((" ", "\t")) or _TRACEBACK_FILE.match(line):
                current_tb.append(line)
                continue
            elif current_tb:
                # Last line is usually "ExceptionType: message" — capture it.
                current_tb.append(line)
                _record_tb(current_tb, traceback_files, traceback_samples)
                traceback_count += 1
                current_tb = []
                in_traceback = False
                # Fall through to also try matching this line as a normal log line

        # Structured line match
        m = _LINE_PAT.match(line)
        if not m:
            continue
        level = m.group("level").upper()
        if LEVELS.get(level, 0) < min_level:
            continue
        logger = m.group("logger")
        msg = m.group("msg")
        tmpl = normalize(msg)
        bucket_counts[tmpl] += 1
        bucket_loggers[tmpl][logger] += 1
        if tmpl not in bucket_samples:
            bucket_samples[tmpl] = msg
        if len(bucket_originals[tmpl]) < 3:
            bucket_originals[tmpl].append(msg)
        for sym in sym_pat.findall(msg):
            # Filter junk that looks ticker-shaped
            if sym not in {"WARN", "INFO", "ERROR", "DEBUG", "HTTP", "JSON", "API", "TTL", "OHLCV", "TZ", "ET", "UTC", "MA", "RS", "SEPA"}:
                bucket_symbols[tmpl][sym] += 1

    # Flush any in-progress traceback
    if current_tb:
        _record_tb(current_tb, traceback_files, traceback_samples)
        traceback_count += 1

    # ── Report ────────────────────────────────────────────────────────
    total_buckets = sum(bucket_counts.values())
    print(f"── {args.level}+ log lines bucketed: {total_buckets} across {len(bucket_counts)} unique templates ──\n")

    for tmpl, count in bucket_counts.most_common(args.max_templates):
        top_loggers = ", ".join(f"{lg} ({n})" for lg, n in bucket_loggers[tmpl].most_common(3))
        top_syms = ", ".join(f"{s}×{n}" for s, n in bucket_symbols[tmpl].most_common(5))
        print(f"[{count:>5}]  {tmpl[:120]}")
        print(f"         loggers: {top_loggers}")
        if top_syms:
            print(f"         symbols: {top_syms}")
        print(f"         example: {bucket_samples[tmpl][:160]}")
        print()

    print(f"\n── Python tracebacks: {traceback_count} captured ──\n")
    if traceback_files:
        print("Top originating files (by traceback count):")
        for path, n in traceback_files.most_common(10):
            print(f"  [{n:>3}] {path}")
        print()
        print("Up to 3 sample tracebacks (truncated to 12 lines each):")
        for i, tb in enumerate(traceback_samples[:3], 1):
            print(f"\n--- Sample traceback #{i} ---")
            for ln in tb.splitlines()[:12]:
                print(ln)
            print(f"--- end sample #{i} ---")
    else:
        print("No tracebacks in window.")

    # Heuristic: if nothing showed up, the user probably ran before the scan
    # actually fired any logs. Help them debug.
    if total_buckets == 0 and traceback_count == 0:
        print()
        print("Nothing matched. Common causes:")
        print(f"  - Scan didn't run in the last {args.since} window (widen with --since 1h)")
        print(f"  - Compose service names don't match (current: {services})")
        print(f"  - Level threshold too high (try --level INFO to see warnings noise)")


def _record_tb(tb_lines: list[str], files_counter: Counter, samples: list[str]):
    """Record a captured traceback: bump file counters + keep up to 3 samples."""
    for ln in tb_lines:
        m = _TRACEBACK_FILE.match(ln)
        if m:
            # Just the basename for cleaner buckets
            path = m.group("file").rsplit("/", 1)[-1]
            files_counter[path] += 1
    if len(samples) < 3:
        samples.append("\n".join(tb_lines))


if __name__ == "__main__":
    main()
