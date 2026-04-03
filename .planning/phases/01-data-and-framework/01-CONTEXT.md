# Phase 1: Data & Framework - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Setting up the foundational Python architecture and building the 1-minute NQ OHLCV data pipeline. This establishes the structural container that the trading logic will plug into.

</domain>

<decisions>
## Implementation Decisions

### Data Management
- **D-01 Data Ingestion:** Use Parquet files to load the historical 1-minute NQ OHLCV data.
- **D-02 Configuration:** Use a strongly-typed Python Dataclass config object to manage and pass strategy parameters.

### Architecture
- **D-03 Code Structure:** Use Object-Oriented classes (e.g., `DataLoader`, `Engine`) to enforce modularity and ensure components can be cleanly swapped out (e.g., for V2 ML integration).

### Agent's Discretion
The exact names of the classes and internal dataframe indexing approaches are left to the agent's discretion, provided they remain performant and modular.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Definitions
- `.planning/PROJECT.md` — Core context and V1 vs V2 separation boundaries.
- `.planning/REQUIREMENTS.md` — Specifically DATA-01 and DATA-02 requirements.
- `.planning/ROADMAP.md` — Overall 5-phase structure to respect limits of Phase 1.
</canonical_refs>
