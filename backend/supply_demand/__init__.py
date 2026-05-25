"""Supply/Demand module — sector-level and company-level dependency tracking.

Two parallel data structures:
  - dependencies.py: curated company-to-company graph (NVDA→TSM, AAPL→ASML, etc.)
  - sectors.py:      curated sector list (AI Chips, Lithium, Oil, etc.) + ETFs

Both feed into one /supply-demand page with two views (Graph + Sectors)
and surface on Morning + Overnight + per-ticker detail pages.
"""
