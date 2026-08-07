# ADR-006 — Prediction Engine

**Date**: 2026-08-07
**Status**: Proposed
**Research**: [docs/research/7.5-prediction-research.md](../research/7.5-prediction-research.md)

---

## Context

`MockForecastingEngine` is the only implementation. 13 trained XGBoost
models exist in `backend/models/` but are never called. `FeatureStore`
extracts only raw numeric values — not the TA indicators the models require.

## Decision

1. **`XGBoostForecastingEngine`**: loads `.meta` (feature list) and `.pkl`
   (model) at startup. `predict()` calls `model.predict_proba()`.

2. **`TechnicalFeatureExtractor`**: maps `compute_technical_analysis()`
   output to model feature names from `.meta`. Added to `FeatureStore`.

3. **TA-only fallback**: `is_model_available()` returns `False` for
   uncovered symbols. `ConfidenceScorer` uses TA-dominant weights (70/30).

4. **Feature vector cache**: `dict[symbol → (timestamp, FeatureVector)]`
   in `XGBoostForecastingEngine`. Avoids re-extraction within same session.

5. **No new model training**: existing `.pkl` models only. New training
   deferred to Phase 8.

## Consequences

**Positive**: `TraderAgent` produces real ML-backed predictions for 12 symbols;
SHAP explanations become available (7.8).

**Negative**: `xgboost` package required; model load adds ~200 ms at startup
(one-time); feature name mismatch risk at startup.

## Alternatives Rejected

- **LightGBM / LSTM**: no trained models available; training out of scope.
- **Use nearest model for uncovered symbols**: feature distribution mismatch
  risk; TA-only fallback is safer.

## Rollback

If `.meta` feature names don't match TA output: `XGBoostForecastingEngine`
logs the mismatch and falls back to `MockForecastingEngine`. No crash.
