"""🚩 Gajjala's tab on Chart Maps (2026-10-13) — Goverdhan Gajjala's five 5-minute setups over HIS scanner on the whole
US market, plus ☀️ Premarket, 🌙 Post-market and 📓 his Playbook.

One cron pass every 5 minutes (run.py) reads ONE whole-market Massive snapshot, scans it with his three numbers
(scanner.py), loads closed 5/15-minute bars for the listed names (bars.py), runs the pure detectors and stores every
read in Mongo (store.py). The endpoint only READS Mongo — nothing here scans or fetches on a page load. Every number
lives in constants.py. UNMEASURED: no study here says these setups win; nothing here trades or enters a lane.
"""
