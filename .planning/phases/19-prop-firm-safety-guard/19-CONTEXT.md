# Phase 19: Prop Firm Safety Guard - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Implement daily loss limit enforcement in the NinjaTrader bridge to prevent MFFU account termination. The bridge must track cumulative P&L per trading day and refuse new signals once the configurable `MAX_DAILY_LOSS` threshold is exceeded.

</domain>

<decisions>
## Implementation Decisions

### Agent's Discretion
All implementation choices are at the agent's discretion — pure infrastructure/safety phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key constraints:
- Must integrate into existing `NinjaBridge` class in `live/ninja_bridge.py`
- Must be configurable via `.env` (consistent with existing NINJA_HOST/PORT pattern)
- Must reset at midnight ET (new trading day)
- MFFU default max daily loss: $2,000 for most eval accounts

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `live/ninja_bridge.py` — NinjaBridge class with `on_trade_closed()` hook that receives `pnl_points`
- `live/engine.py` — `POINT_VALUE = 20.0` constant for NQ P&L calculation
- `.env` — existing pattern for configuration (NINJA_HOST, NINJA_PORT, RITHMIC_CONTRACTS)

### Established Patterns
- Environment variables loaded via `os.environ.get()` with sensible defaults
- Logging via `logging.getLogger(__name__)`
- AsyncIO event loop for all bridge operations

### Integration Points
- `NinjaBridge.on_trade_closed()` — accumulate P&L here
- `NinjaBridge.on_trade_opened()` — gate signal dispatch here
- `NinjaBridge.on_bar()` — potential reset check on day boundary

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure safety phase. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
