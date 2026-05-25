# Day-trading signal detectors. Each signal has:
#   detect(df, ...) -> list[dict] of triggered signals (entries with stop/target)
#   backtest(df, ...) -> stats for walk-forward over the input window
