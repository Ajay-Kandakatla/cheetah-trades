# Cheetah-market-app — top-level convenience targets.
#
# Most of these are thin wrappers that run inside the api container so
# you don't have to remember the docker-compose-exec incantation.
#
# The only target that's mandatory for safety is `make contracts` —
# anyone touching backend/sepa/, backend/options/, or backend/setups/
# code is expected to run this BEFORE committing. The pre-commit hook
# at scripts/pre-commit-hook installs a guard that runs it
# automatically when those paths are touched.

# Default target: print available commands.
.DEFAULT_GOAL := help

.PHONY: help contracts contracts-sepa contracts-vcp contracts-phantom contracts-breakout contracts-kell contracts-trading contracts-frontend contracts-realtime install-hooks lint

help:                          ## Show this help.
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

contracts: contracts-sepa contracts-kell contracts-trading contracts-frontend  ## Run ALL contracts regression tests. MANDATORY before any sepa/options/setups change.

contracts-sepa:                ## Run the SEPA contracts regression test (docs/SEPA_CONTRACTS.md).
	@echo "→ SEPA contracts (docs/SEPA_CONTRACTS.md)"
	@docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests/test_sepa_contracts.py -v --tb=short

contracts-vcp:                 ## VCP behavioral contracts (docs/sepa/vcp_methodology.md). Fold into `contracts-sepa` after the api image is rebuilt with test_vcp.py.
	@echo "→ VCP behavioral contracts (docs/sepa/vcp_methodology.md)"
	@docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests/test_vcp.py -v --tb=short

contracts-gauge:               ## Market Gauge behavioral contracts incl. weekly + outlook (docs/sepa/market_gauge_methodology.md). Fold into `contracts-sepa` after the api image is rebuilt with test_market_gauge.py.
	@echo "→ Market Gauge behavioral contracts (backend/sepa/market_gauge.py, daily + weekly + outlook)"
	@docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests/test_market_gauge.py -v --tb=short

contracts-phantom:             ## prices.py data-hygiene: phantom trailing-bar guard + delisted/stale-symbol floor. Fold into `contracts-sepa` after the api image is rebuilt with test_phantom_bar.py.
	@echo "→ prices.py data-hygiene contracts (phantom-bar + staleness, backend/sepa/prices.py)"
	@docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests/test_phantom_bar.py -v --tb=short

contracts-breakout:            ## Breakout-recency (volume.days_since_breakout) + setup_ready gate. Fold into `contracts-sepa` after the api image is rebuilt with test_breakout_window.py.
	@echo "→ Breakout-window contracts (backend/sepa/volume.py + scanner._is_setup_ready)"
	@docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests/test_breakout_window.py -v --tb=short

contracts-sales:               ## Sales Confidence score contracts (docs/sepa/sales_confidence_methodology.md). Fold into `contracts-sepa` after the api image is rebuilt with test_sales.py.
	@echo "→ Sales Confidence contracts (backend/sepa/sales.py)"
	@docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests/test_sales.py -v --tb=short

contracts-trading:             ## Auto-Pilot risk contracts (docs/sepa/risk_management_methodology.md + SEPA_CONTRACTS.md 11f). Stdlib-only — runs on the HOST python, no docker.
	@echo "→ Auto-Pilot risk contracts (backend/trading/risk_rules.py + engine)"
	@cd backend && (test -x .venv/bin/python && .venv/bin/python -m pytest tests/test_risk_rules.py tests/test_trading_contracts.py tests/test_trading_engine.py -q --tb=short || python3 -m pytest tests/test_risk_rules.py tests/test_trading_contracts.py tests/test_trading_engine.py -q --tb=short)

contracts-kell:                ## Run the Kell scanner contracts regression test (docs/KELL_CONTRACTS.md).
	@echo "→ Kell contracts (docs/KELL_CONTRACTS.md)"
	@docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests/test_kell_contracts.py -v --tb=short

contracts-realtime:            ## Massive key-routing + WS live-feed contracts. Fold into `contracts` after the api image is rebuilt with live_feed.py.
	@echo "→ Real-time contracts (massive_keys + live_feed + accumulation + short_interest)"
	@docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests/test_massive_keys.py tests/test_live_feed.py tests/test_accumulation.py tests/test_short_interest.py -v --tb=short

contracts-frontend:            ## Frontend source contracts (alert-banner cap, etc.) — pure Node, no docker.
	@echo "→ Frontend contracts (frontend/scripts/contracts.mjs)"
	@node frontend/scripts/contracts.mjs

install-hooks:                 ## Install the pre-commit guard at .git/hooks/pre-commit.
	@cp scripts/pre-commit-hook .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "✓ Pre-commit hook installed. It will run `make contracts` automatically"
	@echo "  on any commit that touches backend/sepa/, backend/options/, or backend/setups/."

lint:                          ## Lint frontend (tsc --noEmit).
	cd frontend && npx tsc --noEmit -p .
