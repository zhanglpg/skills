#!/usr/bin/env python3
"""
Fetch real-time portfolio prices for daily brief generation.
Outputs JSON with current prices and daily changes.

Usage:
    python3 scripts/fetch_prices.py [--tickers GOOG,NVDA,TSM,BABA,SPY,FXI,KWEB]
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

try:
    import yfinance as yf
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance", "-q"])
    import yfinance as yf

DEFAULT_TICKERS = ["GOOG", "NVDA", "TSM", "BABA", "SPY", "FXI", "KWEB", "QQQ"]

def main():
    tickers_str = None
    for i, arg in enumerate(sys.argv):
        if arg == "--tickers" and i + 1 < len(sys.argv):
            tickers_str = sys.argv[i + 1]

    tickers = tickers_str.split(",") if tickers_str else DEFAULT_TICKERS

    data = yf.download(tickers, period="2d", auto_adjust=True, progress=False)

    results = {}
    for ticker in tickers:
        try:
            close = data["Close"][ticker]
            latest = close.iloc[-1]
            prev = close.iloc[-2] if len(close) > 1 else latest
            change_pct = ((latest - prev) / prev) * 100 if prev != 0 else 0
            results[ticker] = {
                "price": round(float(latest), 2),
                "change_pct": round(float(change_pct), 2),
                "previous_close": round(float(prev), 2),
            }
        except Exception as e:
            results[ticker] = {"error": str(e)}

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tickers": results,
    }

    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
