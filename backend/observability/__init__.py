"""Observability — fail-safe app logging + a health-audit battery.

- logsetup.install_file_handler() persists ALL app logs to a rotating file on
  the shared volume so silent failures leave a trail (and any external agent —
  Datadog / Splunk / Vector / Promtail — can tail it).
- health_audit.run_audit() runs a battery of in-process checks for critical data
  that silently failed to fire, pushes the owner on a CRITICAL miss, and feeds
  optional external sinks (Healthchecks.io dead-man's-switch + a generic webhook).
"""
