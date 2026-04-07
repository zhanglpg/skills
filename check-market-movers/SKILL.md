---
name: checking-market-movers
description: "Monitors portfolio holdings (GOOG, NVDA, TSMC, BABA, SPY, FXI, KWEB) hourly for significant price moves using Yahoo Finance data. Only interrupts for portfolio-relevant events exceeding configurable thresholds. Use when setting up automated portfolio alerts, hourly market checks, or significant move notifications."
---

# Check Market Movers Skill

Hourly portfolio monitoring that checks for significant price moves in tracked holdings. Only interrupts when events exceed configured thresholds.

## Quick Start

```bash
# Run manually
python3 ~/.openclaw/workspace/skills/custom/check-market-movers/scripts/check-market-movers.py

# Run via cron job (configured)
openclaw cron run hourly-market-movers
```

## Portfolio Tracked

| Ticker | Name | Sector | Interrupt Threshold |
|--------|------|--------|---------------------|
| GOOG | Alphabet | Tech | >5% |
| NVDA | NVIDIA | Semiconductors | >5% |
| TSMC | Taiwan Semiconductor | Semiconductors | >5% |
| BABA | Alibaba | China Internet | >5% |
| SPY | S&P 500 ETF | US Broad Market | >3% |
| FXI | China Large-Cap ETF | China Indices | >4% |
| KWEB | China Internet ETF | China Indices | >4% |

## How It Works

1. **Fetch Data** — Calls Yahoo Finance API (yfinance) for real-time prices
2. **Calculate Changes** — Computes intraday % change from open/close
3. **Check Thresholds** — Compares moves against portfolio-specific thresholds
4. **Report Events** — Only saves report and sends message if significant events detected

**Design principle:** Silent by default. No spam on normal days.

## Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| **Python 3** | Script runtime | Built-in on macOS |
| **yfinance** | Yahoo Finance API | `pip install yfinance` |
| **pandas** | Data handling | `pip install pandas` (auto-installed with yfinance) |

## Configuration

Edit `scripts/check-market-movers.py` to customize:

```python
# Portfolio holdings
PORTFOLIO = {
    "GOOG": {"name": "Alphabet", "sector": "Tech"},
    "NVDA": {"name": "NVIDIA", "sector": "Semiconductors"},
    "TSM": {"name": "Taiwan Semiconductor", "sector": "Semiconductors"},
    "BABA": {"name": "Alibaba", "sector": "China Internet"},
    "SPY": {"name": "S&P 500 ETF", "sector": "US Broad Market"},
    "FXI": {"name": "China Large-Cap ETF", "sector": "China Indices"},
    "KWEB": {"name": "China Internet ETF", "sector": "China Indices"},
}

# Interrupt thresholds
THRESHOLDS = {
    "portfolio_stock": 5.0,  # Individual stocks
    "portfolio_etf": 3.0,    # Broad market ETFs
    "china_exposure": 4.0,   # China-specific ETFs
}
```

## Output

### When No Events (Silent)
```
✓ No portfolio events (checked 7 holdings) - no report saved
```

### When Events Detected
```
⚠️ PORTFOLIO EVENTS DETECTED (2):
  - NVDA: +6.50%
  - GOOG: -5.20%
Report saved to: ~/.openclaw/workspace/briefs/investment/hourly-checks/2026-03-06-11-check.md
```

### Report Format
```markdown
# Portfolio Check - 2026-03-06 11:15

## Summary
- Check Time: 2026-03-06T11:15:49
- Events Found: 2
- Interrupt Required: **Yes**

## 🚨 Portfolio Events
- **NVDA** (NVIDIA): +6.50%
  - Sector: Semiconductors | Severity: high
- **GOOG** (Alphabet): -5.20%
  - Sector: Tech | Severity: medium

## Portfolio Holdings
| Ticker | Name | Sector | Price | Change |
|--------|------|--------|-------|--------|
| GOOG | Alphabet | Tech | $300.91 | 🔴 -0.72% |
| NVDA | NVIDIA | Semiconductors | $183.34 | 🟢 +1.20% |
...
```

## Scheduling

**Cron Expression:** `0 22-23 * * 1-5` and `0 0-7 * * 1-6` (Asia/Shanghai)

This runs every hour during US market hours:
- **Shanghai Time:** 10:00 PM - 7:00 AM (Mon-Sat)
- **US Eastern Time:** 9:30 AM - 4:00 PM (Mon-Fri)

## State Tracking

**Location:** `~/.openclaw/workspace-finance/memory/heartbeat-state.json`

Tracks:
- Last check time
- Last significant event
- Check count
- Current portfolio and thresholds

## Testing

```bash
cd ~/.openclaw/workspace/skills/custom/check-market-movers

# Test run
python3 scripts/check-market-movers.py

# Check output
ls -la ~/.openclaw/workspace/briefs/investment/hourly-checks/

# View state
cat ~/.openclaw/workspace-finance/memory/heartbeat-state.json
```

## Troubleshooting

### yfinance not installed
```bash
pip3 install yfinance
```

### Market data fetch fails
- Check internet connection
- Yahoo Finance may be rate-limiting (wait and retry)
- Markets may be closed (script handles this gracefully)

### Cron job not running
```bash
openclaw cron status
openclaw cron runs --id hourly-market-movers --limit 5
```

## Files

| File | Purpose |
|------|---------|
| `scripts/check-market-movers.py` | Main script |
| `SKILL.md` | This documentation |

## Related

- **Daily Investment Brief** — Comprehensive daily portfolio summary using `briefs` skill
- **Morning Briefing** — Daily overview including market data, reminders, and news

---

**Data Source:** Yahoo Finance (yfinance)
