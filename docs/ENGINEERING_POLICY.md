# JARVIS Engineering Policy

**Version**: 1.0  
**Effective**: 2025-07-01  
**Status**: Active  
**Owner**: Project Lead

This document is the engineering constitution for JARVIS. All contributors and AI coding agents must follow these rules without exception.

---

## Version Policy

| Series | Scope |
|--------|-------|
| 0.7.x  | Verified trading engine (frozen) |
| 0.8.x  | Memory · RAG · Embeddings · Qdrant |
| 0.9.x  | Learning · Prediction · Optimisation |
| 1.0.0  | Production candidate |

A minor version bump (0.7 → 0.8) requires a new architecture baseline document. A patch bump (0.7.1 → 0.7.2) requires only a V&V entry and passing tests.

---

## Rule 1 — Frozen Component Changes

Components listed as **FROZEN** in the current baseline document may not be modified without all four of:

1. A new or amended ADR approved by the project lead.
2. A V&V entry documenting the mathematical or logical change.
3. All existing regression tests passing (currently 1517/1517 minimum).
4. A new architecture baseline document tagged in Git.

Frozen components as of v0.7.1:

- `backend/app/api/technical_analysis.py`
- `backend/app/api/forecaster.py`
- `backend/app/api/market_regime.py`
- `backend/app/api/mtf_analysis.py`
- `backend/app/api/backtesting.py`
- `backend/app/api/paper_trading.py`
- `backend/app/api/auto_trader.py`
- `backend/app/ai/prediction/confidence.py`
- `backend/app/ai/prediction/feature_store.py`

---

## Rule 2 — New AI Capability Workflow

Every new AI capability must follow this sequence in order. No step may be skipped.

```
Research document  →  ADR  →  Implementation  →  V&V  →  Baseline
```

Research documents live in `docs/research/`.  
ADRs live in `docs/adr/`.  
V&V entries live in `docs/vv/`.  
Baselines live in `docs/architecture_baselines/`.

---

## Rule 3 — Public API Stability

No breaking change to a public API endpoint (any route registered in a FastAPI router) without an ADR that explicitly documents the breaking change and the migration path.

A breaking change is defined as: removing a field, renaming a field, changing a field type, or changing HTTP method or path.

Adding new optional fields is not a breaking change and does not require an ADR.

---

## Rule 4 — Mathematical Algorithm Verification

Every function that implements a financial formula, statistical calculation, or ML inference pipeline must have:

1. An independent verification step (manual derivation or reference to a published formula in a research document or baseline).
2. At least one unit test with a known-correct expected value.
3. An integration test confirming the output flows correctly to its consumer.
4. A regression test that runs in CI on every commit.

If a formula is changed, the V&V entry must record the old formula, the new formula, and the reason for the change.

---

## Rule 5 — No Merge with Failing Tests

No code may be committed to `master` if any test in the suite is failing.

The minimum passing bar is the count recorded in the most recent baseline document. As of v0.7.1 that bar is **1517/1517**.

New features must add new tests. The total test count must never decrease between releases.

---

## Rule 6 — Package Structure Freeze

The top-level package structure is frozen. No new top-level folder under `backend/app/` may be created without an ADR.

Current approved top-level packages:

```
backend/app/
    config/
    core/
    ai/
    api/
    market_data/
```

New sub-packages within an existing top-level package (e.g. `app/ai/memory/`) are permitted without an ADR provided they do not introduce new external dependencies.

New external dependencies always require an ADR entry listing the package, version pin, and justification.

---

## Rule 7 — File Size Limit

No source file may exceed 300 lines. If a file approaches this limit, split it by responsibility before adding new code. The split itself does not require an ADR but must be noted in the commit message.

---

## Rule 8 — Two-Stream Architecture

The AI layer (Phase 7+) consumes outputs from the trading engine. It must never import from or call internal functions of frozen trading engine files directly. All communication goes through the defined public interfaces (FastAPI routes or explicitly exported helper functions).

Any proposed exception requires an ADR.

---

## Rule 9 — Kernel Freeze

The following packages are kernel-level and may not receive new files or new external dependencies without an Architecture Change Proposal (ACP) reviewed by the project lead:

- `backend/app/core/`
- `backend/app/config/`
- `backend/app/resilience/`

---

## Rule 10 — Secrets and Credentials

No API key, token, password, or credential of any kind may appear in source code or documentation. All secrets are loaded from environment variables or a secrets manager. Violations are grounds for immediate rollback regardless of test status.

---

## Approved Dependencies for Phase 7

The following packages are pre-approved for Phase 7 implementation. No further ADR is needed to install them.

| Package | Version Pin | Purpose |
|---------|-------------|---------|
| qdrant-client | ==1.7.x | Vector store |
| sentence-transformers | ==2.2.2 | Embeddings |
| transformers | ==4.30.x | LLM utilities |
| torch | ==1.13.x (CPU) | Model inference |
| xgboost | ==1.7.x | Prediction models |
| shap | ==0.41.x | Explainability |

Any package not in this table requires a new ADR entry before installation.

---

## Rule 11 — Intelligence Layer Resilience

The AI layer is allowed to degrade gracefully. The trading engine is never allowed to degrade unsafely.

This rule has three binding sub-rules:

**11a — Forbidden dependency direction.** No component inside the trading engine (frozen files listed in Rule 1) may import, call, or depend on any Phase 7+ component: Qdrant, sentence-transformers, embeddings, vector search, RAG, agents, reasoning, or learning. The dependency arrow points one way only: trading engine produces signals, AI layer consumes them.

**11b — Intelligence services must fail silently.** Any Phase 7+ service (memory, RAG, embeddings, agents, LLM) must catch its own exceptions, return a defined fallback result, and never propagate an error into the trading path. Fallback results are valid results, not error states.

**11c — Full intelligence failure must leave trading intact.** If every intelligence service fails simultaneously (Qdrant down, embeddings down, RAG down, learning down, LLM down), the system must still produce a safe, deterministic trading decision from market data and the verified algorithms alone. This is the fault-tolerance baseline and must be verified by `TestMemoryFailureIsolation` in Phase 7A and extended in each subsequent sub-phase.

The detailed resilience contract (health states, timeout budgets, write semantics) is specified in ADR-002.

---

## Change Log

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2025-07-01 | Initial policy — established after v0.7.1 baseline |
| 1.1 | 2025-07-01 | Rule 11 — Intelligence Layer Resilience (three sub-rules, references ADR-002) |
