"""Price-alert push delivery — regression (2026-06-02).

Bug: `price_alerts.check_alerts()` fired `notify.send_alert(kind="price_alert")`
with NO `user_email`. `price_alert` is in `notify.PRIVATE_KINDS`, and
`notify._send_push` REFUSES a private kind without a user_email (returns 0) — so
every price-alert push was silently dropped (never reached the phone). Same class
of bug as the portfolio-alert delivery fix.

Fix: alerts are scoped to their creator (`user_email` on the doc, set from the
authenticated request), and `check_alerts` passes that through to `send_alert`;
legacy alerts fall back to the house owner so they still deliver.
"""
import inspect

from sepa import price_alerts
from sepa import notify


def test_price_alert_is_a_private_kind():
    # The guard that makes user_email mandatory only matters because price_alert
    # is private. If this ever changes, the delivery contract changes too.
    assert "price_alert" in notify.PRIVATE_KINDS


def test_target_email_prefers_creator_then_owner():
    # Creator's own email wins.
    assert price_alerts._target_email({"user_email": "trader@x.com"}) == "trader@x.com"
    # Legacy alert (no user_email) must still resolve to SOMEONE (house owner),
    # otherwise the private-kind guard drops it.
    assert price_alerts._target_email({}) is not None
    assert price_alerts._target_email({"user_email": ""}) is not None


def test_create_accepts_and_stores_user_email():
    params = inspect.signature(price_alerts.create).parameters
    assert "user_email" in params, "create() must accept user_email to scope the alert"
    src = "\n".join(l.split("#", 1)[0] for l in inspect.getsource(price_alerts.create).splitlines())
    assert '"user_email"' in src, "create() must persist user_email on the alert doc"


def test_check_alerts_passes_user_email_to_send_alert():
    # The exact regression guard: the fire path MUST hand a user_email to
    # notify.send_alert, or the private-kind guard silently drops the push.
    src = "\n".join(l.split("#", 1)[0] for l in inspect.getsource(price_alerts.check_alerts).splitlines())
    assert "user_email=" in src, (
        "check_alerts must pass user_email= to notify.send_alert — "
        "price_alert is a PRIVATE kind and is dropped without it"
    )
    assert "_target_email" in src, "check_alerts must resolve the recipient via _target_email"
