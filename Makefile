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

.PHONY: help contracts contracts-sepa contracts-kell contracts-frontend install-hooks lint

help:                          ## Show this help.
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

contracts: contracts-sepa contracts-kell contracts-frontend  ## Run ALL contracts regression tests. MANDATORY before any sepa/options/setups change.

contracts-sepa:                ## Run the SEPA contracts regression test (docs/SEPA_CONTRACTS.md).
	@echo "→ SEPA contracts (docs/SEPA_CONTRACTS.md)"
	@docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests/test_sepa_contracts.py -v --tb=short

contracts-kell:                ## Run the Kell scanner contracts regression test (docs/KELL_CONTRACTS.md).
	@echo "→ Kell contracts (docs/KELL_CONTRACTS.md)"
	@docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests/test_kell_contracts.py -v --tb=short

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
