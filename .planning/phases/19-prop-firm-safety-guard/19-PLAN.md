# Phase 19 Plan: Prop Firm Safety Guard

## Status: READY

## Goal
Implement daily loss limit enforcement in the NinjaTrader bridge to prevent MFFU account termination.

## Architecture
The guard is a simple P&L accumulator inside `NinjaBridge`:
1. Track cumulative realized P&L per trading day (resets at midnight ET)
2. Before dispatching any new signal, check if daily loss exceeds `MAX_DAILY_LOSS`
3. If limit hit → log a CRITICAL warning and suppress the signal (do NOT send to NT)

## Tasks

### Wave 1: Implementation

- [x] **T19.1: Add PropFirmGuard to NinjaBridge** (`live/ninja_bridge.py`)
  - Add `MAX_DAILY_LOSS` env var (default: -2000.0 USD)
  - Track `_daily_pnl_usd` accumulator, reset on date change
  - Gate `on_trade_opened()` — suppress signal if limit exceeded
  - Log CRITICAL message when guard triggers

- [x] **T19.2: Update .env with MAX_DAILY_LOSS** (`.env`)
  - Add `MAX_DAILY_LOSS=-2000` to the environment file

- [x] **T19.3: Update SETUP.md** (`live/NinjaScript/SETUP.md`)
  - Document the MAX_DAILY_LOSS parameter in the setup guide

## Verification Criteria (UAT)
1. When cumulative daily P&L drops below -$2,000, the bridge logs CRITICAL and refuses new signals.
2. Guard resets at midnight ET — new trading day allows fresh signals.
3. Winning trades offset losses — guard tracks NET daily P&L, not gross losses.
4. Default value is -$2,000 but is configurable via .env.
