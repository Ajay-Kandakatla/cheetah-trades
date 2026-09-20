"""Political disclosures — the curated list, the board endpoint and the
headline watch.

Ajay 2026-05-28 asked for a chip when "Trump or U.S. government investments go
into a stock"; 2026-09-20 he asked for the other half: *"Anytime POTUS does new
investments show me those"*.

ONE SOURCE. ``political/disclosures.json`` holds the rows; the TypeScript the
frontend imports (``frontend/src/lib/politicalDisclosures.ts``) is GENERATED
from it by ``backend/scripts/gen_political_ts.py``. Before this package the
list lived in TypeScript only, which a cron container cannot read — so the
watch could never have known which names were already on the list.

Nothing in here is a measured signal. ``watch.py`` is a regex over headlines;
it fills a CANDIDATE list a human reads. It never edits the JSON.
"""
