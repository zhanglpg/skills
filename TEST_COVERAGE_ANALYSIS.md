# Test Coverage Analysis

**Date:** 2026-03-06
**Tests passing:** 165/165
**Framework:** Python `unittest` (stdlib)

## Current Coverage Summary

| Module | File | Test Classes | Test Methods | Coverage |
|--------|------|-------------|--------------|----------|
| fetcher | `briefs/scripts/fetcher.py` | 14 | ~80 | High |
| summarizer | `briefs/scripts/summarizer.py` | 5 | ~20 | High |
| renderer | `briefs/scripts/renderer.py` | 8 | ~35 | High |
| generate_brief | `briefs/scripts/generate_brief.py` | 6 | ~25 | Medium |
| check-market-movers | `check-market-movers/scripts/check-market-movers.py` | 0 | 0 | **None** |

## Gap Analysis: Areas to Improve

### 1. `check-market-movers.py` — No Tests (Critical)

This entire module (313 lines, 6 functions) has **zero test coverage**. It handles real-time portfolio monitoring and has non-trivial logic that should be tested:

| Function | Lines | Risk | What to Test |
|----------|-------|------|-------------|
| `get_market_data()` | 56-100 | High | Mock `yf.download`, verify response structure, test missing/null ticker data, exception handling |
| `check_significant_events()` | 103-179 | High | Threshold logic for stocks vs ETFs, severity classification, China exposure detection, portfolio news filtering |
| `format_report()` | 182-241 | Medium | Report structure, ticker display (TSM→TSMC), price/change formatting, N/A handling, emoji indicators |
| `save_report()` | 244-250 | Low | Directory creation, filename format |
| `update_state()` | 253-273 | Low | State JSON structure, TSM→TSMC display mapping |
| `main()` | 276-312 | Medium | Exit codes (0 vs 1), test mode flag, conditional report saving |

**Recommended tests (~25-30 new test methods):**
- `TestCheckSignificantEvents`: ETF vs stock threshold differentiation, severity levels, edge cases (change exactly at threshold), China exposure double-counting prevention, empty holdings
- `TestFormatReport`: Output structure validation, TSM→TSMC display name, market-closed formatting, event type rendering
- `TestGetMarketData`: Mocked yfinance responses, error handling, null/missing data
- `TestSaveReport` and `TestUpdateState`: File I/O with mocks

### 2. `generate_brief.py` — `_build_portfolio_context()` Untested (Medium)

The `_build_portfolio_context()` method (lines 127-150) has **no dedicated tests**. It builds a context block used in prompt generation for portfolio-type briefs.

**What to test:**
- Returns empty string when no holdings and no watchlist
- Formats holdings grouped by sector with ticker counts
- Formats watchlist tickers and themes
- Handles partial config (holdings but no watchlist, and vice versa)
- Correctly counts total positions across sectors

### 3. `generate_brief.py` — `generate_brief()` Pipeline Undertested (Medium)

`TestGenerateBriefContent` has only 2 tests for the main orchestration method (lines 154-277). This is the most critical code path — it wires together all modules.

**What to test:**
- Template variable substitution (portfolio vars like `holdings_count`, `sector_count`)
- Twitter block generation (with accounts vs without)
- Unavailable web sources block generation
- Failed RSS sources note generation
- Output path provided vs not (file save vs logger output)
- Validation failure path (warning logged but generation continues)

### 4. `generate_brief.py` — `main()` CLI Entry Point Untested (Low-Medium)

The `main()` function (lines 280-304) with argparse handling has no tests.

**What to test:**
- `--test` flag recognition
- `--output_dir` overrides config
- `--config` custom config file path
- Default behavior (no args)

### 5. `generate_brief.py` — `_setup_logger()` Untested (Low)

The logger setup (lines 84-104) is always mocked in tests. While this is fine for unit testing, there's no test verifying:

- File handler creation with correct path
- Console handler with correct format
- Graceful fallback when log directory can't be created

### 6. `fetcher.py` — `fetch_web_source()` Trafilatura Path Untested (Low-Medium)

The trafilatura integration path (line 354-355) is never tested — all web extraction tests set `_HAS_TRAFILATURA = False`. If trafilatura is installed, this code path runs in production but is unverified.

**What to test:**
- Mock `trafilatura.extract()` returning content
- Mock `trafilatura.extract()` returning None/empty (falls through to None check)

### 7. `fetcher.py` — `fetch_web_sources_parallel()` Lightly Tested (Low)

`TestFetchWebSourcesParallel` has only 2 tests. Missing coverage:

**What to test:**
- Filtering by fetchable categories (only `newsletter`, `ai_lab`, `research_org`)
- Non-fetchable categories are skipped
- Mixed results (some succeed, some fail)
- Results stored in `fetched_content['web_pages']`

### 8. `renderer.py` — `validate_brief()` Edge Cases (Low)

**What to test:**
- `min_required` calculation: verify `max(3, total // 2)` logic with different template sizes
- Brief with exactly the minimum required sections
- Brief with all sections present
- Template with fewer than 6 sections (where `3 > total // 2`)

### 9. Integration / End-to-End Tests (Strategic Gap)

The test suite is entirely unit tests with mocked dependencies. There are no integration tests that verify the modules work together correctly. Consider adding:

- A test that runs the full pipeline with all external calls mocked at the HTTP/subprocess boundary (not at module boundaries)
- A test that verifies config loading → fetcher → summarizer → renderer data flow
- A test using real config files (`config.ai-tech.json`, `config.portfolio.json`) to verify config schema compatibility

## Priority Recommendations

| Priority | Area | Effort | Impact |
|----------|------|--------|--------|
| **P0** | Add tests for `check-market-movers.py` | ~3 hours | Covers entirely untested module with financial logic |
| **P1** | Test `_build_portfolio_context()` | ~30 min | Covers untested method in critical path |
| **P1** | Expand `generate_brief()` pipeline tests | ~1 hour | Better coverage of main orchestration logic |
| **P2** | Test trafilatura code path in fetcher | ~20 min | Covers production code path |
| **P2** | Test `main()` CLI entry point | ~30 min | Covers user-facing interface |
| **P3** | Add integration test for full pipeline | ~1 hour | Catches module boundary issues |
| **P3** | Expand `fetch_web_sources_parallel` tests | ~20 min | Better concurrency testing |
