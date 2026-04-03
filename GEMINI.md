<!-- GSD:project-start source:PROJECT.md -->
## Project

**DodgysDD IFVG Strategy Automation**

An automated futures trading system based on a rule-based price action strategy known as the DodgysDD Inversion Fair Value Gap (IFVG) Strategy. Everything revolves around waiting for liquidity to be swept, finding a Fair Value Gap (FVG) that gets inverted, and entering in the direction of the inversion toward the next liquidity pool. V1 is fully deterministic, modular, and backtestable.

**Core Value:** The system must mechanize the DodgysDD IFVG trading strategy into fully explicit, rule-based logic to enable robust and deterministic backtesting, completely eliminating ambiguity and discretionary steps.

### Constraints

- **Execution Limit**: V1 must be fully deterministic and backtestable.
- **Data Dependency**: Only utilize 1-minute NQ OHLCV data.
- **Code Quality**: Production-quality Python code with comments and docstrings.
- **Dependency Scope**: Prefer pandas/numpy, matplotlib/plotly. Avoid unnecessary bloat.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
