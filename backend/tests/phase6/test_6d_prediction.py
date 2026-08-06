"""
tests/phase6/test_6d_prediction.py
=====================================
Unit tests for Prediction package (Tasks 6D.11–6D.13).

Covers: FeatureVector, FeatureStore, PredictionResult, MockForecastingEngine,
        ScorerConfig, ScoredResult, ConfidenceScorer.
"""
import pytest

from app.ai.prediction.feature_store import FeatureStore, FeatureVector
from app.ai.prediction.forecasting import (
    ForecastingEngine, MockForecastingEngine, PredictionResult, PredictionDirection,
)
from app.ai.prediction.confidence import ConfidenceScorer, ScorerConfig, ScoredResult
from app.ai.perception.market import InMemoryMarketPerception


# ── TestFeatureVector ─────────────────────────────────────────────────────────

class TestFeatureVector:

    def test_construction(self):
        fv = FeatureVector(features={"price": 100.0, "volume": 5000.0})
        assert fv.features["price"]  == 100.0
        assert fv.features["volume"] == 5000.0

    def test_to_list_all_values(self):
        fv     = FeatureVector(features={"a": 1.0, "b": 2.0})
        values = fv.to_list()
        assert set(values) == {1.0, 2.0}

    def test_to_list_with_keys(self):
        fv     = FeatureVector(features={"a": 1.0, "b": 2.0, "c": 3.0})
        values = fv.to_list(keys=["b", "a"])
        assert values == [2.0, 1.0]

    def test_to_list_missing_key_returns_zero(self):
        fv     = FeatureVector(features={"a": 1.0})
        values = fv.to_list(keys=["a", "missing"])
        assert values == [1.0, 0.0]

    def test_len(self):
        fv = FeatureVector(features={"a": 1.0, "b": 2.0})
        assert len(fv) == 2

    def test_source_keys_default_empty(self):
        fv = FeatureVector(features={})
        assert fv.source_keys == []


# ── TestFeatureStore ──────────────────────────────────────────────────────────

class TestFeatureStore:

    def test_build_numeric_values(self):
        store  = FeatureStore()
        fv     = store.build({"price": 100.0, "volume": 5000})
        assert fv.features["price"]  == 100.0
        assert fv.features["volume"] == 5000.0

    def test_build_skips_non_numeric(self):
        store = FeatureStore()
        fv    = store.build({"price": 100.0, "symbol": "TEST", "active": True})
        assert "symbol" not in fv.features
        assert "price"  in fv.features
        assert "active" in fv.features   # bool is converted

    def test_build_converts_bool_to_float(self):
        store = FeatureStore()
        fv    = store.build({"flag_true": True, "flag_false": False})
        assert fv.features["flag_true"]  == 1.0
        assert fv.features["flag_false"] == 0.0

    def test_build_empty_dict(self):
        store = FeatureStore()
        fv    = store.build({})
        assert len(fv) == 0

    def test_build_records_source_keys(self):
        store = FeatureStore()
        fv    = store.build({"price": 100.0, "volume": 5000})
        assert "price"  in fv.source_keys
        assert "volume" in fv.source_keys

    @pytest.mark.asyncio
    async def test_build_from_bundles(self):
        store = FeatureStore()
        p1    = InMemoryMarketPerception(mock_data={"price": 100.0})
        p2    = InMemoryMarketPerception(mock_data={"volume": 5000.0})
        b1    = await p1.fetch({})
        b2    = await p2.fetch({})
        fv    = store.build_from_bundles([b1, b2])
        assert "price"  in fv.features
        assert "volume" in fv.features

    def test_build_from_bundles_later_overrides_earlier(self):
        store = FeatureStore()

        class _FakeBundle:
            data = {"price": 100.0}

        class _FakeBundle2:
            data = {"price": 200.0}

        fv = store.build_from_bundles([_FakeBundle(), _FakeBundle2()])
        assert fv.features["price"] == 200.0


# ── TestPredictionResult ──────────────────────────────────────────────────────

class TestPredictionResult:

    def test_construction(self):
        r = PredictionResult(
            direction=PredictionDirection.UP,
            magnitude=0.7,
            confidence=0.8,
        )
        assert r.direction  == PredictionDirection.UP
        assert r.magnitude  == 0.7
        assert r.confidence == 0.8

    def test_direction_values(self):
        assert PredictionDirection.UP.value      == "up"
        assert PredictionDirection.DOWN.value    == "down"
        assert PredictionDirection.NEUTRAL.value == "neutral"

    def test_features_used_default_empty(self):
        r = PredictionResult(PredictionDirection.NEUTRAL, 0.5, 0.5)
        assert r.features_used == []


# ── TestMockForecastingEngine ─────────────────────────────────────────────────

class TestMockForecastingEngine:

    def test_predict_returns_prediction_result(self):
        engine = MockForecastingEngine()
        fv     = FeatureVector(features={"price": 100.0})
        result = engine.predict(fv)
        assert isinstance(result, PredictionResult)

    def test_predict_uses_configured_direction(self):
        engine = MockForecastingEngine(direction=PredictionDirection.UP)
        fv     = FeatureVector(features={})
        result = engine.predict(fv)
        assert result.direction == PredictionDirection.UP

    def test_predict_uses_configured_confidence(self):
        engine = MockForecastingEngine(confidence=0.9)
        fv     = FeatureVector(features={})
        result = engine.predict(fv)
        assert result.confidence == 0.9

    def test_predict_records_features_used(self):
        engine = MockForecastingEngine()
        fv     = FeatureVector(features={"a": 1.0}, source_keys=["a"])
        result = engine.predict(fv)
        assert "a" in result.features_used

    def test_is_model_available_always_true(self):
        engine = MockForecastingEngine()
        assert engine.is_model_available("any_model") is True

    def test_set_prediction(self):
        engine = MockForecastingEngine()
        engine.set_prediction(PredictionDirection.DOWN, 0.8, 0.75)
        fv     = FeatureVector(features={})
        result = engine.predict(fv)
        assert result.direction  == PredictionDirection.DOWN
        assert result.magnitude  == 0.8
        assert result.confidence == 0.75

    def test_is_abc_subclass(self):
        engine = MockForecastingEngine()
        assert isinstance(engine, ForecastingEngine)


# ── TestConfidenceScorer ──────────────────────────────────────────────────────

class TestConfidenceScorer:

    def _pred(self, confidence=0.7):
        return PredictionResult(PredictionDirection.UP, 0.5, confidence)

    def test_no_inputs_returns_neutral(self):
        scorer = ConfidenceScorer()
        result = scorer.score()
        assert result.confidence == 0.5
        assert "neutral" in result.reasoning.lower()

    def test_prediction_only(self):
        scorer = ConfidenceScorer()
        result = scorer.score(prediction=self._pred(0.8))
        assert result.confidence == 0.8

    def test_ta_signal_only(self):
        scorer = ConfidenceScorer()
        result = scorer.score(ta_signal=0.6)
        assert result.confidence == 0.6

    def test_sentiment_normalised_from_minus_one_to_one(self):
        scorer = ConfidenceScorer()
        # sentiment=1.0 → normalised=1.0
        result = scorer.score(sentiment=1.0)
        assert result.confidence == 1.0

    def test_sentiment_negative_normalised(self):
        scorer = ConfidenceScorer()
        # sentiment=-1.0 → normalised=0.0
        result = scorer.score(sentiment=-1.0)
        assert result.confidence == 0.0

    def test_all_sources_aggregated(self):
        scorer = ConfidenceScorer()
        result = scorer.score(
            prediction=self._pred(0.8),
            ta_signal=0.7,
            sentiment=0.6,   # normalised to 0.8
        )
        assert 0.0 < result.confidence < 1.0
        assert "prediction" in result.components
        assert "ta_signal"  in result.components
        assert "sentiment"  in result.components

    def test_reasoning_string_not_empty(self):
        scorer = ConfidenceScorer()
        result = scorer.score(prediction=self._pred(0.7))
        assert result.reasoning != ""

    def test_confidence_clamped_to_range(self):
        scorer = ConfidenceScorer()
        result = scorer.score(ta_signal=2.0)   # out of range
        assert 0.0 <= result.confidence <= 1.0

    def test_custom_weights(self):
        cfg    = ScorerConfig(weight_prediction=1.0, weight_ta_signal=0.0, weight_sentiment=0.0)
        scorer = ConfidenceScorer(config=cfg)
        result = scorer.score(prediction=self._pred(0.9), ta_signal=0.1)
        # Only prediction should matter
        assert result.confidence == 0.9

    def test_scored_result_construction(self):
        r = ScoredResult(confidence=0.75, reasoning="test", components={"a": 0.75})
        assert r.confidence == 0.75
        assert r.reasoning  == "test"
