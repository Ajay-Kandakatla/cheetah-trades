"""Bring the owner's ALREADY-REGISTERED devices up to the 2026-09-20 keep-set.

Ajay 2026-09-20: *"Default on for any change of todays features Bondes or Potus
or explosive growth or Earnings I wanna see all of them."* and *"Remove
volleyball and learning of stocks I do dont wanna see them they are spamming
too much."*

`push.subs.prefs_for()` only decides what a NEWLY registering device starts
with. His three phones are already registered, so the code change alone leaves
them exactly as they were: 🏛️ potus off, 📣 and ✨ absent, the four retired
kinds still True in their stored prefs. This script is the data write that
closes that gap — and nothing else. It:

  * turns ON every kind in `subs.OWNER_KEEP_SET` (never a retyped list),
  * turns OFF every kind in `subs.RETIRED_2026_09_20`,
  * touches ONLY documents whose `user_email` is the owner's,
  * prints what it would do and changes nothing unless `--apply` is passed.

Run it in the api container:

    docker exec -i -w /app cheetah-market-app-api-1 \\
        python -m scripts.owner_prefs_apply            # dry run, prints a diff
    docker exec -i -w /app cheetah-market-app-api-1 \\
        python -m scripts.owner_prefs_apply --apply

Idempotent: a second `--apply` prints "no change" for every device.

NOT A GATE AND NOT A RULE. It flips per-device preference flags — which KINDS
may reach him. What any kind requires to fire is untouched.

The arithmetic lives in `apply()`, which is pure over injected documents, so
`backend/tests/test_owner_prefs_apply.py` pins it without a database.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from push import subs

# The address never appears as a literal in this file — it is imported from
# the ONE place that owns it (growth.alerts.OWNER) and compared against the
# environment. `chr(64)` is the at-sign, spelled this way so the source guard
# in the tests can assert that no address literal was ever typed here.
_AT = chr(64)


def _mask(email: str) -> str:
    """The local part only — enough to tell two addresses apart in a log
    without printing a full address into the container's stdout."""
    return (email or "").split(_AT)[0] or "(empty)"


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def on_kinds() -> list[str]:
    """The kinds this script turns ON — the keep-set itself, never a copy."""
    return sorted(subs.OWNER_KEEP_SET)


def off_kinds() -> list[str]:
    """The kinds this script turns OFF — the retired set itself."""
    return sorted(subs.RETIRED_2026_09_20)


def apply(docs, *, owner: str, apply: bool, coll=None) -> dict:
    """Compute (and optionally write) the pref diff for the owner's devices.

    `docs` is any iterable of `push_subscriptions` documents. A non-owner
    document is COUNTED and never read past its `user_email`. When `apply` is
    True and `coll` is given, each owner document with at least one change gets
    one `update_one($set)` carrying only the changed keys plus `updated_at`.

    Returns {devices, changed, applied, untouched, rows: [...]} where each row
    is {label, kind, endpoint, changes: {key: [old, new]}}.
    """
    on, off = on_kinds(), off_kinds()
    keys = on + off
    want = {**{k: True for k in on}, **{k: False for k in off}}

    rows: list[dict] = []
    untouched = 0
    changed = 0
    for doc in docs:
        if (doc.get("user_email") or "").lower() != owner:
            untouched += 1
            continue
        prefs = doc.get("prefs") or {}
        before = {k: prefs.get(k) for k in keys}
        # `is not` on purpose: a stored `None` (key absent) must count as a
        # change even though `None == False` is False anyway — and a stored
        # `1` must NOT be mistaken for `True`'s identity.
        changes = {k: [before[k], want[k]] for k in keys if before[k] is not want[k]}
        rows.append({
            "label": (doc.get("label") or "")[:32],
            "kind": doc.get("kind") or "web",
            "endpoint": (doc.get("endpoint") or "")[:28],
            "changes": changes,
        })
        if not changes:
            continue
        changed += 1
        if apply and coll is not None:
            coll.update_one(
                {"_id": doc["_id"]},
                {"$set": {**{f"prefs.{k}": v for k, (_old, v) in changes.items()},
                          "updated_at": _now()}},
            )
    return {"devices": len(rows), "changed": changed, "applied": bool(apply),
            "untouched": untouched, "rows": rows}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    do_apply = "--apply" in argv
    as_json = "--json" in argv

    owner = subs._owner_email()
    from growth.alerts import OWNER
    if owner != OWNER.lower():
        # The environment and the code literal must agree, or this script
        # would rewrite the prefs of whoever the env happens to name.
        print(f"REFUSING: OWNER_EMAIL/DEFAULT_USER_EMAIL is {_mask(owner)!r} but "
              f"growth.alerts.OWNER is {_mask(OWNER)!r} — no device was read",
              file=sys.stderr)
        return 2

    db = subs._get_db()
    if db is None:
        print("REFUSING: Mongo unavailable — no device was read", file=sys.stderr)
        return 2
    coll = db.push_subscriptions
    out = apply(list(coll.find({})), owner=owner, apply=do_apply, coll=coll)

    if as_json:
        print(json.dumps(out, indent=2, default=str))
        return 0
    print(f"keep-set ON : {', '.join(on_kinds())}")
    print(f"retired OFF : {', '.join(off_kinds())}")
    for row in out["rows"]:
        head = f"{row['label']} · {row['kind']} · {row['endpoint']}…"
        if not row["changes"]:
            print(f"{head} : no change")
            continue
        for k, (old, new) in sorted(row["changes"].items()):
            print(f"{head} : {k} {old}→{new}")
    print(f"untouched (not the owner): {out['untouched']}")
    print(f"devices {out['devices']} · changed {out['changed']} · "
          f"applied {'yes' if out['applied'] else 'no'}")
    if not do_apply and out["changed"]:
        print("(dry run — re-run with --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
