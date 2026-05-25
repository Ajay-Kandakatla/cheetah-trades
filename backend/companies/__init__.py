"""Company info — cached snapshot of yfinance Ticker.info per symbol.

Pulls longBusinessSummary, sector, industry, website, employees, etc.
Cached in Mongo for 30 days (descriptions don't change often).
"""
from companies import store  # noqa: F401
