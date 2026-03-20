# Test Coverage Analysis

**Date:** 2026-03-20
**Tests passing:** 291/291
**Framework:** Python `unittest` (stdlib)

## Current Coverage Summary

| Module | File | Test Classes | Test Methods | Coverage |
|--------|------|-------------|--------------|----------|
| fetcher | `briefs/scripts/fetcher.py` | 14 | ~80 | High |
| summarizer | `briefs/scripts/summarizer.py` | 5 | ~20 | High |
| renderer | `briefs/scripts/renderer.py` | 8 | ~35 | High |
| generate_brief | `briefs/scripts/generate_brief.py` | 6 | ~25 | Medium |
| check-market-movers | `check-market-movers/scripts/check-market-movers.py` | 10 | 43 | High |
| paper-digest | `paper-digest/scripts/test_digest_paper.py` | — | 32 | Medium |
| openbb-integration | `briefs/scripts/test_openbb_integration.py` | — | 29 | Medium |

## Remaining Gaps

### 1. `generate_brief.py` — `_build_portfolio_context()` Untested (Medium)

The `_build_portfolio_context()` method (lines 127-150) has **no dedicated tests**. It builds a context block used in prompt generation for portfolio-type briefs.

**What to test:**
- Returns empty string when no holdings and no watchlist
- Formats holdings grouped by sector with ticker counts
- Formats watchlist tickers and themes
- Handles partial config (holdings but no watchlist, and vice versa)
- Correctly counts total positions across sectors

### 2. `generate_brief.py` — `generate_brief()` Pipeline Undertested (Medium)

`TestGenerateBriefContent` has only 2 tests for the main orchestration method (lines 154-277). This is the most critical code path — it wires together all modules.

**What to test:**
- Template variable substitution (portfolio vars like `holdings_count`, `sector_count`)
- Twitter block generation (with accounts vs without)
- Unavailable web sources block generation
- Failed RSS sources note generation
- Output path provided vs not (file save vs logger output)
- Validation failure path (warning logged but generation continues)

### 3. `generate_brief.py` — `main()` CLI Entry Point Untested (Low-Medium)

The `main()` function (lines 280-304) with argparse handling has no tests.

**What to test:**
- `--test` flag recognition
- `--output_dir` overrides config
- `--config` custom config file path
- Default behavior (no args)

### 4. `fetcher.py` — `fetch_web_source()` Trafilatura Path Untested (Low-Medium)

The trafilatura integration path (line 354-355) is never tested — all web extraction tests set `_HAS_TRAFILATURA = False`. If trafilatura is installed, this code path runs in production but is unverified.

**What to test:**
- Mock `trafilatura.extract()` returning content
- Mock `trafilatura.extract()` returning None/empty (falls through to None check)

### 5. Integration / End-to-End Tests (Strategic Gap)

The test suite is entirely unit tests with mocked dependencies. There are no integration tests that verify the modules work together correctly. Consider adding:

- A test that runs the full pipeline with all external calls mocked at the HTTP/subprocess boundary (not at module boundaries)
- A test that verifies config loading → fetcher → summarizer → renderer data flow
- A test using real config files (`config.ai-tech.json`, `config.portfolio.json`) to verify config schema compatibility

## Priority Recommendations

| Priority | Area | Effort | Impact |
|----------|------|--------|--------|
| **P1** | Test `_build_portfolio_context()` | ~30 min | Covers untested method in critical path |
| **P1** | Expand `generate_brief()` pipeline tests | ~1 hour | Better coverage of main orchestration logic |
| **P2** | Test trafilatura code path in fetcher | ~20 min | Covers production code path |
| **P2** | Test `main()` CLI entry point | ~30 min | Covers user-facing interface |
| **P3** | Add integration test for full pipeline | ~1 hour | Catches module boundary issues |
