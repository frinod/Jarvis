"""
tests/phase7/test_7d_xai_learning.py
======================================
Phase 7D — XAI & Learning Engine tests.

Built incrementally:
  Part 1 (this file): XAI — ShapExplainer, ExplanationFormatter, XaiCache
  Part 2 (append):    LearningEvent, ExperienceRecord, FeedbackCollector
  Part 3 (append):    ModelEvaluator, RetrainingTrigger, ModelRegistry
  Part 4 (append):    Integration + domain agnosticism
"""
import asyncio
import time
import pytest

from app.ai.prediction.feature_store import FeatureVector
from app.ai.runtime.context import ExecutionContext
from app.ai.xai.shap_explainer import (
    FeatureImportance, BaseExplainer, FallbackExplainer, ShapExplainer,
)
from app.ai.xai.explanation_formatter import (
    Explanation, ExplanationFormatter, PipelineExplanationWriter,
)
from app.ai.xai.xai_cache import XaiCache


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fv(n: int = 4) -> FeatureVector:
    features = {f"f{i}": float(i + 1) for i in range(n)}
    return FeatureVector(features=features, source_keys=list(features.keys()))


def _ctx(**kwargs) -> ExecutionContext:
    ctx = ExecutionContext(user_input="test", session_id="s1")
    for k, v in kwargs.items():
        setattr(ctx, k, v)
    return ctx


# ═══════════════════════════════════════════════════════════════════════════════
# TestFeatureImportance
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeatureImportance:

    def test_top_returns_n_items(self):
        fi = FeatureImportance(scores=[("a", 0.5), ("b", 0.3), ("c", 0.2)])
        assert len(fi.top(2)) == 2

    def test_top_preserves_order(self):
        fi = FeatureImportance(scores=[("a", 0.5), ("b", 0.3), ("c", 0.2)])
        assert fi.top(2)[0] == ("a", 0.5)

    def test_top_clamps_to_available(self):
        fi = FeatureImportance(scores=[("a", 0.5)])
        assert len(fi.top(10)) == 1

    def test_as_dict(self):
        fi = FeatureImportance(scores=[("a", 0.5), ("b", 0.3)])
        d  = fi.as_dict()
        assert d["a"] == 0.5
        assert d["b"] == 0.3

    def test_empty_scores(self):
        fi = FeatureImportance(scores=[])
        assert fi.top(5) == []
        assert fi.as_dict() == {}

    def test_method_field(self):
        fi = FeatureImportance(scores=[], method="shap")
        assert fi.method == "shap"


# ═══════════════════════════════════════════════════════════════════════════════
# TestFallbackExplainer
# ═══════════════════════════════════════════════════════════════════════════════

class TestFallbackExplainer:

    def test_is_available(self):
        assert FallbackExplainer().is_available() is True

    def test_uniform_scores_sum_to_one(self):
        fv = _fv(4)
        fi = FallbackExplainer().explain(fv)
        total = sum(s for _, s in fi.scores)
        assert abs(total - 1.0) < 1e-5

    def test_all_features_present(self):
        fv = _fv(4)
        fi = FallbackExplainer().explain(fv)
        assert len(fi.scores) == 4

    def test_method_is_uniform(self):
        fi = FallbackExplainer().explain(_fv(2))
        assert fi.method == "uniform"

    def test_empty_features(self):
        fv = FeatureVector(features={})
        fi = FallbackExplainer().explain(fv)
        assert fi.scores == []

    def test_model_name_propagated(self):
        fi = FallbackExplainer().explain(_fv(2), model_name="xgb_v1")
        assert fi.model_name == "xgb_v1"

    def test_never_raises_on_bad_input(self):
        # Should not raise even with unusual input
        fi = FallbackExplainer().explain(FeatureVector(features={"x": float("nan")}))
        assert isinstance(fi, FeatureImportance)


# ═══════════════════════════════════════════════════════════════════════════════
# TestShapExplainer
# ═══════════════════════════════════════════════════════════════════════════════

class TestShapExplainer:

    def test_is_base_explainer(self):
        assert isinstance(ShapExplainer(), BaseExplainer)

    def test_fallback_when_no_model(self):
        """explain() with model=None must fall back gracefully."""
        fi = ShapExplainer().explain(_fv(3), model=None)
        assert isinstance(fi, FeatureImportance)
        assert fi.method == "uniform_fallback"

    def test_fallback_method_label(self):
        fi = ShapExplainer().explain(_fv(3))
        assert "fallback" in fi.method or fi.method == "shap"

    def test_returns_feature_importance(self):
        fi = ShapExplainer().explain(_fv(3))
        assert isinstance(fi, FeatureImportance)

    def test_never_raises(self):
        """explain() must never raise regardless of input."""
        explainer = ShapExplainer()
        try:
            explainer.explain(FeatureVector(features={}))
            explainer.explain(_fv(0))
        except Exception as exc:
            pytest.fail(f"ShapExplainer.explain raised: {exc}")

    def test_is_available_returns_bool(self):
        result = ShapExplainer().is_available()
        assert isinstance(result, bool)

    def test_fallback_explainer_is_base_explainer(self):
        assert isinstance(FallbackExplainer(), BaseExplainer)


# ═══════════════════════════════════════════════════════════════════════════════
# TestExplanation
# ═══════════════════════════════════════════════════════════════════════════════

class TestExplanation:

    def test_from_context_basic(self):
        ctx = _ctx(response="BUY", confidence=0.82, selected_agent="TraderAgent")
        exp = Explanation.from_context(ctx)
        assert exp.confidence == 0.82
        assert exp.agent_used == "TraderAgent"

    def test_from_context_with_importance(self):
        ctx = _ctx(confidence=0.75)
        fi  = FeatureImportance(scores=[("rsi", 0.6), ("macd", 0.4)], method="shap")
        exp = Explanation.from_context(ctx, importance=fi)
        assert len(exp.top_features) == 2

    def test_from_context_fallback_flag(self):
        ctx = _ctx(confidence=0.5)
        ctx.metadata["_decision_tree_fired"] = True
        exp = Explanation.from_context(ctx)
        assert exp.fallback_triggered is True

    def test_from_context_learning_flag(self):
        ctx = _ctx(confidence=0.7)
        ctx.metadata["_learning_applied"] = True
        exp = Explanation.from_context(ctx)
        assert exp.learning_applied is True

    def test_to_dict_contains_required_keys(self):
        exp = Explanation(confidence=0.8, agent_used="AnalystAgent")
        d   = exp.to_dict()
        assert "confidence" in d
        assert "agent_used" in d

    def test_prediction_truncated_to_200(self):
        ctx = _ctx(response="X" * 300, confidence=0.5)
        exp = Explanation.from_context(ctx)
        assert len(exp.prediction) <= 200

    def test_memory_used_populated(self):
        from app.ai.memory.short_term import MemoryEntry
        ctx = _ctx(confidence=0.6)
        ctx.memory_context = [MemoryEntry(content="past trade context")]
        exp = Explanation.from_context(ctx)
        assert len(exp.memory_used) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# TestExplanationFormatter
# ═══════════════════════════════════════════════════════════════════════════════

class TestExplanationFormatter:

    def _exp(self, **kwargs) -> Explanation:
        defaults = dict(
            prediction="BUY", confidence=0.82, agent_used="TraderAgent",
            top_features=[("rsi", 0.6), ("macd", 0.4)],
            decision_path=["step 1", "step 2"],
        )
        defaults.update(kwargs)
        return Explanation(**defaults)

    def test_format_text_contains_confidence(self):
        text = ExplanationFormatter().format_text(self._exp())
        assert "82%" in text

    def test_format_text_contains_agent(self):
        text = ExplanationFormatter().format_text(self._exp())
        assert "TraderAgent" in text

    def test_format_text_contains_features(self):
        text = ExplanationFormatter().format_text(self._exp())
        assert "rsi" in text

    def test_format_text_fallback_note(self):
        text = ExplanationFormatter().format_text(self._exp(fallback_triggered=True))
        assert "fallback" in text.lower()

    def test_format_text_learning_note(self):
        text = ExplanationFormatter().format_text(self._exp(learning_applied=True))
        assert "learning" in text.lower()

    def test_format_markdown_contains_bold_confidence(self):
        md = ExplanationFormatter().format_markdown(self._exp())
        assert "**Confidence**" in md

    def test_format_markdown_contains_features_section(self):
        md = ExplanationFormatter().format_markdown(self._exp())
        assert "Top Features" in md

    def test_format_json_is_valid_json(self):
        import json
        js = ExplanationFormatter().format_json(self._exp())
        d  = json.loads(js)
        assert "confidence" in d

    def test_format_text_never_raises(self):
        try:
            ExplanationFormatter().format_text(Explanation())
        except Exception as exc:
            pytest.fail(f"format_text raised: {exc}")

    def test_format_markdown_never_raises(self):
        try:
            ExplanationFormatter().format_markdown(Explanation())
        except Exception as exc:
            pytest.fail(f"format_markdown raised: {exc}")

    def test_format_json_never_raises(self):
        try:
            ExplanationFormatter().format_json(Explanation())
        except Exception as exc:
            pytest.fail(f"format_json raised: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# TestPipelineExplanationWriter
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineExplanationWriter:

    def test_writes_to_ctx_explanation(self):
        ctx = _ctx(confidence=0.75, selected_agent="TraderAgent")
        PipelineExplanationWriter().write(ctx)
        assert ctx.explanation != ""

    def test_writes_explanation_metadata(self):
        ctx = _ctx(confidence=0.75)
        PipelineExplanationWriter().write(ctx)
        assert "_explanation" in ctx.metadata

    def test_returns_explanation_object(self):
        ctx = _ctx(confidence=0.75)
        exp = PipelineExplanationWriter().write(ctx)
        assert isinstance(exp, Explanation)

    def test_with_feature_importance(self):
        ctx = _ctx(confidence=0.8)
        fi  = FeatureImportance(scores=[("rsi", 0.7), ("vol", 0.3)], method="shap")
        exp = PipelineExplanationWriter().write(ctx, importance=fi)
        assert len(exp.top_features) > 0

    def test_never_raises(self):
        try:
            PipelineExplanationWriter().write(ExecutionContext())
        except Exception as exc:
            pytest.fail(f"PipelineExplanationWriter.write raised: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# TestXaiCache
# ═══════════════════════════════════════════════════════════════════════════════

class TestXaiCache:

    def _fi(self, method: str = "shap") -> FeatureImportance:
        return FeatureImportance(scores=[("rsi", 0.6)], method=method)

    def test_miss_returns_none(self):
        cache = XaiCache()
        assert cache.get("nonexistent") is None

    def test_put_and_get(self):
        cache = XaiCache()
        fi    = self._fi()
        cache.put("k1", fi)
        assert cache.get("k1") is fi

    def test_expired_entry_returns_none(self):
        cache = XaiCache(ttl_seconds=0.01)
        fi    = self._fi()
        cache.put("k1", fi)
        time.sleep(0.05)
        assert cache.get("k1") is None

    def test_lru_eviction(self):
        cache = XaiCache(capacity=2)
        cache.put("k1", self._fi("a"))
        cache.put("k2", self._fi("b"))
        cache.put("k3", self._fi("c"))   # evicts k1 (LRU)
        assert cache.get("k1") is None
        assert cache.get("k2") is not None
        assert cache.get("k3") is not None

    def test_make_key_deterministic(self):
        cache = XaiCache()
        fv    = _fv(3)
        k1    = cache.make_key("v1.0", fv)
        k2    = cache.make_key("v1.0", fv)
        assert k1 == k2

    def test_make_key_differs_by_version(self):
        cache = XaiCache()
        fv    = _fv(3)
        assert cache.make_key("v1.0", fv) != cache.make_key("v1.1", fv)

    def test_make_key_differs_by_features(self):
        cache = XaiCache()
        fv1   = FeatureVector(features={"a": 1.0})
        fv2   = FeatureVector(features={"a": 2.0})
        assert cache.make_key("v1", fv1) != cache.make_key("v1", fv2)

    def test_invalidate(self):
        cache = XaiCache()
        cache.put("k1", self._fi())
        assert cache.invalidate("k1") is True
        assert cache.get("k1") is None

    def test_invalidate_missing_returns_false(self):
        assert XaiCache().invalidate("missing") is False

    def test_clear(self):
        cache = XaiCache()
        cache.put("k1", self._fi())
        cache.put("k2", self._fi())
        cache.clear()
        assert cache.size == 0

    def test_stats(self):
        cache = XaiCache(capacity=10)
        cache.put("k1", self._fi())
        s = cache.stats()
        assert s["size"] == 1
        assert s["capacity"] == 10

    def test_get_never_raises(self):
        try:
            XaiCache().get(None)  # type: ignore
        except Exception as exc:
            pytest.fail(f"XaiCache.get raised: {exc}")

    def test_put_never_raises(self):
        try:
            XaiCache().put(None, None)  # type: ignore
        except Exception as exc:
            pytest.fail(f"XaiCache.put raised: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# Part 2 — LearningEvent, ExperienceRecord, FeedbackCollector
# ═══════════════════════════════════════════════════════════════════════════════

from app.ai.learning.learning_event import LearningEvent, ExperienceRecord
from app.ai.learning.feedback_collector import (
    FeedbackRecord, FeedbackCollector, FeedbackReader,
)
from app.ai.memory.long_term import InMemoryLongTermMemory


def _ltm() -> InMemoryLongTermMemory:
    return InMemoryLongTermMemory(importance_threshold=0.0)


def _trace_stub(
    outcome: str = "success",
    confidence: float = 0.8,
    agent: str = "TraderAgent",
) -> object:
    """Minimal object that mimics a ReasoningTrace for LearningEvent.from_trace()."""
    class _Stub:
        session_id   = "s1"
        request_id   = "r1"
        agent_name   = agent
        intent_type  = "trade"
        goal         = "BUY AAPL"
        step_summary = "2 steps, final confidence 80%: buy signal"
        retry_count  = 0
        metadata     = {"market_regime": "trending"}
    _Stub.outcome    = outcome
    _Stub.confidence = confidence
    return _Stub()


# ── TestLearningEvent ─────────────────────────────────────────────────────────

class TestLearningEvent:

    def test_default_event_type(self):
        ev = LearningEvent()
        assert ev.event_type == "prediction_outcome"

    def test_from_trace_copies_fields(self):
        stub = _trace_stub(outcome="failure", confidence=0.4, agent="AnalystAgent")
        ev   = LearningEvent.from_trace(stub, model_version="v1.2")
        assert ev.outcome       == "failure"
        assert ev.confidence    == 0.4
        assert ev.agent_name    == "AnalystAgent"
        assert ev.model_version == "v1.2"

    def test_from_trace_market_regime(self):
        stub = _trace_stub()
        ev   = LearningEvent.from_trace(stub)
        assert ev.market_regime == "trending"

    def test_from_trace_reasoning_path(self):
        stub = _trace_stub()
        ev   = LearningEvent.from_trace(stub)
        assert "steps" in ev.reasoning_path

    def test_to_dict_contains_all_keys(self):
        ev = LearningEvent(event_type="retrain_requested", agent_name="TraderAgent")
        d  = ev.to_dict()
        for key in ("event_id", "event_type", "agent_name", "outcome", "confidence"):
            assert key in d

    def test_event_id_is_unique(self):
        ids = {LearningEvent().event_id for _ in range(10)}
        assert len(ids) == 10

    def test_from_trace_with_missing_attrs(self):
        """from_trace() must not raise when stub has no attributes."""
        ev = LearningEvent.from_trace(object())
        assert isinstance(ev, LearningEvent)

    def test_retrain_event_type(self):
        ev = LearningEvent(event_type="retrain_requested")
        assert ev.event_type == "retrain_requested"


# ── TestExperienceRecord ──────────────────────────────────────────────────────

class TestExperienceRecord:

    def test_from_event_copies_fields(self):
        ev  = LearningEvent(agent_name="TraderAgent", outcome="failure", market_regime="sideways")
        rec = ExperienceRecord.from_event(ev, lesson="Momentum underperformed", confidence_adjustment=-0.08)
        assert rec.agent_name            == "TraderAgent"
        assert rec.outcome               == "failure"
        assert rec.market_regime         == "sideways"
        assert rec.lesson                == "Momentum underperformed"
        assert rec.confidence_adjustment == -0.08

    def test_from_event_links_source(self):
        ev  = LearningEvent()
        rec = ExperienceRecord.from_event(ev, lesson="test")
        assert rec.source_event_id == ev.event_id

    def test_to_dict_contains_lesson(self):
        rec = ExperienceRecord(lesson="test lesson")
        d   = rec.to_dict()
        assert d["lesson"] == "test lesson"

    def test_record_id_unique(self):
        ids = {ExperienceRecord().record_id for _ in range(10)}
        assert len(ids) == 10

    def test_confidence_adjustment_default_zero(self):
        rec = ExperienceRecord()
        assert rec.confidence_adjustment == 0.0

    def test_to_dict_contains_confidence_adjustment(self):
        rec = ExperienceRecord(confidence_adjustment=-0.05)
        assert rec.to_dict()["confidence_adjustment"] == -0.05


# ── TestFeedbackRecord ────────────────────────────────────────────────────────

class TestFeedbackRecord:

    def test_round_trip(self):
        fb = FeedbackRecord(
            prediction="BUY", actual="profit", correct=True,
            confidence=0.82, model_version="v1.3",
            agent_name="TraderAgent", market_regime="trending",
        )
        d    = fb.to_dict()
        fb2  = FeedbackRecord.from_dict(d)
        assert fb2.prediction    == "BUY"
        assert fb2.correct       is True
        assert fb2.confidence    == 0.82
        assert fb2.model_version == "v1.3"

    def test_from_dict_extra_keys_go_to_metadata(self):
        d  = {"prediction": "SELL", "actual": "loss", "correct": False, "extra_key": "val"}
        fb = FeedbackRecord.from_dict(d)
        assert fb.metadata.get("extra_key") == "val"

    def test_trade_id_unique(self):
        ids = {FeedbackRecord().trade_id for _ in range(10)}
        assert len(ids) == 10

    def test_correct_field_bool(self):
        fb = FeedbackRecord.from_dict({"correct": 1})
        assert isinstance(fb.correct, bool)


# ── TestFeedbackCollector ─────────────────────────────────────────────────────

class TestFeedbackCollector:

    def test_record_returns_feedback_record(self):
        ltm = _ltm()
        col = FeedbackCollector(ltm=ltm)
        fb  = asyncio.get_event_loop().run_until_complete(
            col.record("BUY", "profit", correct=True, confidence=0.82)
        )
        assert isinstance(fb, FeedbackRecord)
        assert fb.prediction == "BUY"

    def test_record_stores_to_ltm(self):
        ltm = _ltm()
        col = FeedbackCollector(ltm=ltm)
        asyncio.get_event_loop().run_until_complete(
            col.record("SELL", "loss", correct=False, confidence=0.55)
        )
        assert ltm.size() == 1

    def test_record_without_ltm_returns_none(self):
        col = FeedbackCollector(ltm=None)
        fb  = asyncio.get_event_loop().run_until_complete(
            col.record("BUY", "profit", correct=True)
        )
        assert fb is None

    def test_record_feedback_prebuilt(self):
        ltm = _ltm()
        col = FeedbackCollector(ltm=ltm)
        fb  = FeedbackRecord(prediction="HOLD", actual="neutral", correct=True)
        ok  = asyncio.get_event_loop().run_until_complete(col.record_feedback(fb))
        assert ok is True

    def test_record_feedback_without_ltm_returns_false(self):
        col = FeedbackCollector(ltm=None)
        ok  = asyncio.get_event_loop().run_until_complete(
            col.record_feedback(FeedbackRecord())
        )
        assert ok is False

    def test_record_stores_all_rich_fields(self):
        ltm = _ltm()
        col = FeedbackCollector(ltm=ltm)
        asyncio.get_event_loop().run_until_complete(
            col.record(
                "BUY", "profit", correct=True,
                confidence=0.9, model_version="v2.0",
                agent_name="TraderAgent", market_regime="trending",
                reasoning_path="2 steps",
            )
        )
        reader  = FeedbackReader(ltm=ltm)
        records = asyncio.get_event_loop().run_until_complete(reader.recent(n=5))
        assert records[0].model_version  == "v2.0"
        assert records[0].market_regime  == "trending"
        assert records[0].reasoning_path == "2 steps"


# ── TestFeedbackReader ────────────────────────────────────────────────────────

class TestFeedbackReader:

    def _populate(self, ltm, n: int = 5):
        col = FeedbackCollector(ltm=ltm)
        loop = asyncio.get_event_loop()
        for i in range(n):
            loop.run_until_complete(
                col.record(
                    prediction="BUY" if i % 2 == 0 else "SELL",
                    actual="profit",
                    correct=True,
                    model_version="v1.0",
                    agent_name="TraderAgent",
                )
            )

    def test_recent_returns_records(self):
        ltm = _ltm()
        self._populate(ltm, 5)
        reader  = FeedbackReader(ltm=ltm)
        records = asyncio.get_event_loop().run_until_complete(reader.recent(n=10))
        assert len(records) == 5

    def test_recent_respects_n(self):
        ltm = _ltm()
        self._populate(ltm, 5)
        reader  = FeedbackReader(ltm=ltm)
        records = asyncio.get_event_loop().run_until_complete(reader.recent(n=3))
        assert len(records) == 3

    def test_recent_without_ltm_returns_empty(self):
        reader  = FeedbackReader(ltm=None)
        records = asyncio.get_event_loop().run_until_complete(reader.recent())
        assert records == []

    def test_by_model_filters(self):
        ltm = _ltm()
        col = FeedbackCollector(ltm=ltm)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(col.record("BUY", "profit", True, model_version="v1.0"))
        loop.run_until_complete(col.record("SELL", "loss",  False, model_version="v2.0"))
        reader  = FeedbackReader(ltm=ltm)
        records = loop.run_until_complete(reader.by_model("v1.0"))
        assert all(r.model_version == "v1.0" for r in records)

    def test_by_agent_filters(self):
        ltm = _ltm()
        col = FeedbackCollector(ltm=ltm)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(col.record("BUY", "profit", True, agent_name="TraderAgent"))
        loop.run_until_complete(col.record("SELL", "loss",  False, agent_name="AnalystAgent"))
        reader  = FeedbackReader(ltm=ltm)
        records = loop.run_until_complete(reader.by_agent("TraderAgent"))
        assert all(r.agent_name == "TraderAgent" for r in records)


# ═══════════════════════════════════════════════════════════════════════════════
# Part 3 — ModelEvaluator, RetrainingTrigger, ModelRegistry
# ═══════════════════════════════════════════════════════════════════════════════

from app.ai.learning.model_evaluator import EvaluationResult, ModelEvaluator
from app.ai.learning.retraining_trigger import TriggerConfig, TriggerResult, RetrainingTrigger
from app.ai.learning.model_registry import ModelRecord, ModelRegistry


def _records(n: int, correct_ratio: float = 0.7, confidence: float = 0.75) -> list:
    """Build n FeedbackRecords with the given correct ratio."""
    records = []
    for i in range(n):
        correct = i < int(n * correct_ratio)
        records.append(FeedbackRecord(
            prediction="BUY" if correct else "SELL",
            actual="profit" if correct else "loss",
            correct=correct,
            confidence=confidence,
            model_version="v1.0",
        ))
    return records


# ── TestEvaluationResult ──────────────────────────────────────────────────────

class TestEvaluationResult:

    def test_is_degraded_below_threshold(self):
        r = EvaluationResult(sample_count=20, accuracy=0.50)
        assert r.is_degraded(accuracy_threshold=0.60) is True

    def test_is_degraded_above_threshold(self):
        r = EvaluationResult(sample_count=20, accuracy=0.75)
        assert r.is_degraded(accuracy_threshold=0.60) is False

    def test_is_degraded_insufficient_samples(self):
        r = EvaluationResult(sample_count=5, accuracy=0.30)
        assert r.is_degraded() is False   # < 10 samples

    def test_to_dict_contains_all_metrics(self):
        r = EvaluationResult(sample_count=10, accuracy=0.7, f1=0.65, ece=0.05)
        d = r.to_dict()
        for key in ("accuracy", "precision", "recall", "f1", "ece",
                    "false_positive_rate", "false_negative_rate", "avg_confidence"):
            assert key in d


# ── TestModelEvaluator ────────────────────────────────────────────────────────

class TestModelEvaluator:

    def test_empty_records_returns_zero_result(self):
        r = ModelEvaluator().evaluate([])
        assert r.sample_count == 0
        assert r.accuracy     == 0.0

    def test_accuracy_calculation(self):
        records = _records(10, correct_ratio=0.8)
        r       = ModelEvaluator().evaluate(records)
        assert abs(r.accuracy - 0.8) < 0.01

    def test_sample_count(self):
        records = _records(15)
        r       = ModelEvaluator().evaluate(records)
        assert r.sample_count == 15

    def test_avg_confidence(self):
        records = _records(10, confidence=0.75)
        r       = ModelEvaluator().evaluate(records)
        assert abs(r.avg_confidence - 0.75) < 0.01

    def test_ece_is_non_negative(self):
        records = _records(20, correct_ratio=0.6, confidence=0.8)
        r       = ModelEvaluator().evaluate(records)
        assert r.ece >= 0.0

    def test_f1_between_zero_and_one(self):
        records = _records(20, correct_ratio=0.7)
        r       = ModelEvaluator().evaluate(records)
        assert 0.0 <= r.f1 <= 1.0

    def test_fpr_between_zero_and_one(self):
        records = _records(20, correct_ratio=0.5)
        r       = ModelEvaluator().evaluate(records)
        assert 0.0 <= r.false_positive_rate <= 1.0

    def test_fnr_between_zero_and_one(self):
        records = _records(20, correct_ratio=0.5)
        r       = ModelEvaluator().evaluate(records)
        assert 0.0 <= r.false_negative_rate <= 1.0

    def test_perfect_accuracy(self):
        records = _records(10, correct_ratio=1.0)
        r       = ModelEvaluator().evaluate(records)
        assert r.accuracy == 1.0

    def test_zero_accuracy(self):
        records = _records(10, correct_ratio=0.0)
        r       = ModelEvaluator().evaluate(records)
        assert r.accuracy == 0.0

    def test_never_raises_on_unusual_input(self):
        try:
            ModelEvaluator().evaluate([FeedbackRecord(confidence=float("nan"))])
        except Exception as exc:
            pytest.fail(f"ModelEvaluator.evaluate raised: {exc}")


# ── TestRetrainingTrigger ─────────────────────────────────────────────────────

class TestRetrainingTrigger:

    def _degraded_result(self, n: int = 20) -> EvaluationResult:
        return EvaluationResult(sample_count=n, accuracy=0.45, f1=0.40, ece=0.15)

    def _good_result(self, n: int = 20) -> EvaluationResult:
        return EvaluationResult(sample_count=n, accuracy=0.80, f1=0.78, ece=0.05)

    def test_fires_when_all_conditions_met(self):
        cfg     = TriggerConfig(accuracy_threshold=0.60, min_samples=10, cooldown_seconds=0)
        trigger = RetrainingTrigger(config=cfg)
        # Build declining history
        for _ in range(3):
            trigger.check(self._degraded_result(), model_version="v1.0")
        trigger.reset_cooldown()
        result = trigger.check(self._degraded_result(), model_version="v1.0")
        assert result.fired is True

    def test_does_not_fire_when_accuracy_ok(self):
        cfg     = TriggerConfig(accuracy_threshold=0.60, min_samples=10, cooldown_seconds=0)
        trigger = RetrainingTrigger(config=cfg)
        result  = trigger.check(self._good_result())
        assert result.fired is False

    def test_does_not_fire_insufficient_samples(self):
        cfg     = TriggerConfig(accuracy_threshold=0.60, min_samples=50, cooldown_seconds=0)
        trigger = RetrainingTrigger(config=cfg)
        result  = trigger.check(EvaluationResult(sample_count=5, accuracy=0.30))
        assert result.fired is False

    def test_does_not_fire_during_cooldown(self):
        cfg     = TriggerConfig(accuracy_threshold=0.60, min_samples=10, cooldown_seconds=9999)
        trigger = RetrainingTrigger(config=cfg)
        # Force first trigger
        trigger.reset_cooldown()
        for _ in range(3):
            trigger.check(self._degraded_result())
        # Second check should be blocked by cooldown
        result = trigger.check(self._degraded_result())
        assert result.fired is False

    def test_fired_event_is_retrain_requested(self):
        cfg     = TriggerConfig(accuracy_threshold=0.60, min_samples=10, cooldown_seconds=0)
        trigger = RetrainingTrigger(config=cfg)
        for _ in range(3):
            trigger.check(self._degraded_result())
        trigger.reset_cooldown()
        result = trigger.check(self._degraded_result(), model_version="v1.3")
        if result.fired:
            assert result.event.event_type    == "retrain_requested"
            assert result.event.model_version == "v1.3"

    def test_conditions_met_dict_present(self):
        trigger = RetrainingTrigger()
        result  = trigger.check(self._good_result())
        assert isinstance(result.conditions_met, dict)
        assert "accuracy_below_threshold" in result.conditions_met

    def test_reset_cooldown(self):
        trigger = RetrainingTrigger()
        trigger._last_trigger_at = time.time()
        trigger.reset_cooldown()
        assert trigger._last_trigger_at == 0.0

    def test_reset_history(self):
        trigger = RetrainingTrigger()
        trigger.check(self._degraded_result())
        trigger.reset_history()
        assert trigger._history == []

    def test_never_raises(self):
        try:
            RetrainingTrigger().check(EvaluationResult())
        except Exception as exc:
            pytest.fail(f"RetrainingTrigger.check raised: {exc}")

    def test_improving_trend_does_not_fire(self):
        cfg     = TriggerConfig(accuracy_threshold=0.60, min_samples=10, cooldown_seconds=0)
        trigger = RetrainingTrigger(config=cfg)
        # Feed improving accuracy — trend should block trigger
        for acc in [0.40, 0.45, 0.50]:
            trigger.check(EvaluationResult(sample_count=20, accuracy=acc))
        trigger.reset_cooldown()
        # Last value (0.50) > first in window (0.40) → improving → should NOT fire
        result = trigger.check(EvaluationResult(sample_count=20, accuracy=0.55))
        # trend_window=3: recent=[0.45, 0.50, 0.55], last > first → not declining
        assert result.conditions_met.get("trend_flat_or_declining") is False


# ── TestModelRegistry ─────────────────────────────────────────────────────────

class TestModelRegistry:

    def test_register_and_get(self):
        reg = ModelRegistry()
        reg.register("v1.0", model="model_a")
        assert reg.get("v1.0") == "model_a"

    def test_first_registered_is_active(self):
        reg = ModelRegistry()
        reg.register("v1.0", model="model_a")
        assert reg.get_active_version() == "v1.0"

    def test_set_active(self):
        reg = ModelRegistry()
        reg.register("v1.0", model="model_a")
        reg.register("v1.1", model="model_b")
        reg.set_active("v1.1")
        assert reg.get_active_version() == "v1.1"
        assert reg.get_active()         == "model_b"

    def test_set_active_unknown_version_returns_false(self):
        reg = ModelRegistry()
        assert reg.set_active("nonexistent") is False

    def test_rollback(self):
        reg = ModelRegistry()
        reg.register("v1.0", model="model_a")
        reg.register("v1.1", model="model_b")
        reg.set_active("v1.1")
        prev = reg.rollback()
        assert prev                     == "v1.0"
        assert reg.get_active_version() == "v1.0"

    def test_rollback_at_oldest_returns_none(self):
        reg = ModelRegistry()
        reg.register("v1.0", model="model_a")
        assert reg.rollback() is None

    def test_rollback_no_models_returns_none(self):
        assert ModelRegistry().rollback() is None

    def test_unregister(self):
        reg = ModelRegistry()
        reg.register("v1.0", model="model_a")
        assert reg.unregister("v1.0") is True
        assert reg.get("v1.0")        is None

    def test_unregister_missing_returns_false(self):
        assert ModelRegistry().unregister("nonexistent") is False

    def test_list_versions_ordered(self):
        reg = ModelRegistry()
        reg.register("v1.0", model="a")
        reg.register("v1.1", model="b")
        reg.register("v1.2", model="c")
        assert reg.list_versions() == ["v1.0", "v1.1", "v1.2"]

    def test_size(self):
        reg = ModelRegistry()
        reg.register("v1.0", model="a")
        reg.register("v1.1", model="b")
        assert reg.size == 2

    def test_stats(self):
        reg = ModelRegistry()
        reg.register("v1.0", model="a")
        s   = reg.stats()
        assert s["active_version"] == "v1.0"
        assert s["size"]           == 1

    def test_get_record(self):
        reg = ModelRegistry()
        reg.register("v1.0", model="a", description="initial", metrics={"accuracy": 0.8})
        rec = reg.get_record("v1.0")
        assert isinstance(rec, ModelRecord)
        assert rec.description        == "initial"
        assert rec.metrics["accuracy"] == 0.8

    def test_overwrite_existing_version(self):
        reg = ModelRegistry()
        reg.register("v1.0", model="old")
        reg.register("v1.0", model="new")
        assert reg.get("v1.0") == "new"
        assert reg.size        == 1

    def test_unregister_active_falls_back(self):
        reg = ModelRegistry()
        reg.register("v1.0", model="a")
        reg.register("v1.1", model="b")
        reg.set_active("v1.1")
        reg.unregister("v1.1")
        # Active should fall back to last remaining version
        assert reg.get_active_version() == "v1.0"


# ═══════════════════════════════════════════════════════════════════════════════
# Part 4 — Integration + Domain Agnosticism
# ═══════════════════════════════════════════════════════════════════════════════

from app.ai.reasoning.reasoning_log import ReasoningTrace, ReasoningLogger, ReasoningLogReader
from app.ai.runtime.context import ThoughtStep


# ── TestReasoningTraceToBoundary ──────────────────────────────────────────────

class TestReasoningTraceToBoundary:
    """
    Verifies the ReasoningTrace → LearningEvent boundary.
    LearningEvent.from_trace() must work with a real ReasoningTrace
    without importing ReasoningTrace in the learning package.
    """

    def _make_trace(self, outcome: str = "success", confidence: float = 0.8) -> ReasoningTrace:
        return ReasoningTrace(
            request_id="r1", session_id="s1",
            goal="BUY AAPL", intent_type="trade",
            agent_name="TraderAgent",
            confidence=confidence, retry_count=0, step_count=2,
            step_summary="2 steps, final confidence 80%: buy signal",
            outcome=outcome,
            metadata={"market_regime": "trending"},
        )

    def test_from_trace_with_real_reasoning_trace(self):
        trace = self._make_trace()
        ev    = LearningEvent.from_trace(trace, model_version="v1.0")
        assert ev.agent_name    == "TraderAgent"
        assert ev.outcome       == "success"
        assert ev.confidence    == 0.8
        assert ev.model_version == "v1.0"

    def test_from_trace_failure_outcome(self):
        trace = self._make_trace(outcome="failure", confidence=0.35)
        ev    = LearningEvent.from_trace(trace)
        assert ev.outcome    == "failure"
        assert ev.confidence == 0.35

    def test_from_trace_market_regime_from_metadata(self):
        trace = self._make_trace()
        ev    = LearningEvent.from_trace(trace)
        assert ev.market_regime == "trending"

    def test_experience_record_from_failure_event(self):
        trace = self._make_trace(outcome="failure", confidence=0.35)
        ev    = LearningEvent.from_trace(trace)
        rec   = ExperienceRecord.from_event(
            ev,
            lesson="Momentum strategy underperformed during sideways regime.",
            confidence_adjustment=-0.08,
        )
        assert rec.outcome               == "failure"
        assert rec.confidence_adjustment == -0.08
        assert "underperformed" in rec.lesson

    def test_learning_event_does_not_import_reasoning_trace(self):
        """
        The learning package must not import from the reasoning package.
        Verify by checking learning_event module's imports.
        """
        import app.ai.learning.learning_event as le_module
        import sys
        # reasoning_log should NOT be in learning_event's module dependencies
        assert "app.ai.reasoning" not in (
            getattr(le_module, "__file__", "") or ""
        )
        # The module itself should not have reasoning imports at module level
        source_path = le_module.__file__
        with open(source_path, encoding="utf-8") as f:
            source = f.read()
        assert "from app.ai.reasoning" not in source
        assert "import app.ai.reasoning" not in source


# ── TestFullFeedbackLoop ──────────────────────────────────────────────────────

class TestFullFeedbackLoop:
    """
    End-to-end: prediction → feedback → evaluate → trigger check.
    Validates the complete learning pipeline on synthetic data.
    """

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_feedback_loop_on_synthetic_data(self):
        ltm       = _ltm()
        collector = FeedbackCollector(ltm=ltm)
        reader    = FeedbackReader(ltm=ltm)
        evaluator = ModelEvaluator()
        cfg       = TriggerConfig(accuracy_threshold=0.60, min_samples=10, cooldown_seconds=0)
        trigger   = RetrainingTrigger(config=cfg)

        # Simulate 20 predictions with 40% accuracy (degraded)
        for i in range(20):
            correct = i < 8   # 8/20 = 40%
            self._run(collector.record(
                prediction="BUY", actual="profit" if correct else "loss",
                correct=correct, confidence=0.75, model_version="v1.0",
            ))

        records = self._run(reader.recent(n=50))
        assert len(records) == 20

        result = evaluator.evaluate(records)
        assert result.sample_count == 20
        assert abs(result.accuracy - 0.40) < 0.01

        # Trigger should fire (accuracy < 0.60, samples >= 10, trend declining)
        for _ in range(3):
            trigger.check(result)
        trigger.reset_cooldown()
        tr = trigger.check(result, model_version="v1.0")
        assert tr.fired is True
        assert tr.event.event_type == "retrain_requested"

    def test_feedback_loop_healthy_model_no_trigger(self):
        ltm       = _ltm()
        collector = FeedbackCollector(ltm=ltm)
        reader    = FeedbackReader(ltm=ltm)
        evaluator = ModelEvaluator()
        trigger   = RetrainingTrigger()

        for i in range(20):
            self._run(collector.record(
                prediction="BUY", actual="profit",
                correct=True, confidence=0.85, model_version="v2.0",
            ))

        records = self._run(reader.recent(n=50))
        result  = evaluator.evaluate(records)
        tr      = trigger.check(result)
        assert tr.fired is False

    def test_model_registry_rollback_after_retrain(self):
        reg = ModelRegistry()
        reg.register("v1.0", model="old_model", metrics={"accuracy": 0.72})
        reg.register("v1.1", model="new_model", metrics={"accuracy": 0.55})
        reg.set_active("v1.1")

        # New model is worse — rollback
        prev = reg.rollback()
        assert prev                     == "v1.0"
        assert reg.get_active()         == "old_model"
        assert reg.get_active_version() == "v1.0"


# ── TestXaiPipeline ───────────────────────────────────────────────────────────

class TestXaiPipeline:
    """
    End-to-end XAI: FeatureVector → ShapExplainer → XaiCache → ExplanationFormatter → ctx.
    """

    def test_full_xai_pipeline(self):
        fv        = _fv(5)
        explainer = ShapExplainer()
        cache     = XaiCache()
        writer    = PipelineExplanationWriter()
        ctx       = _ctx(confidence=0.78, selected_agent="TraderAgent")

        key = cache.make_key("v1.0", fv)
        fi  = cache.get(key)
        if fi is None:
            fi = explainer.explain(fv, model_name="v1.0")
            cache.put(key, fi)

        exp = writer.write(ctx, importance=fi)
        assert ctx.explanation != ""
        assert isinstance(exp, Explanation)
        assert len(exp.top_features) > 0

    def test_cache_hit_returns_same_object(self):
        fv    = _fv(3)
        cache = XaiCache()
        fi    = FallbackExplainer().explain(fv)
        key   = cache.make_key("v1.0", fv)
        cache.put(key, fi)
        assert cache.get(key) is fi

    def test_explanation_written_to_ctx_metadata(self):
        ctx = _ctx(confidence=0.65)
        fi  = FallbackExplainer().explain(_fv(4))
        PipelineExplanationWriter().write(ctx, importance=fi)
        assert "_explanation" in ctx.metadata
        assert "top_features" in ctx.metadata["_explanation"]

    def test_xai_pipeline_without_shap_installed(self):
        """Pipeline must work even when shap is not installed."""
        fv  = _fv(4)
        fi  = ShapExplainer().explain(fv, model=None)   # forces fallback
        ctx = _ctx(confidence=0.70)
        exp = PipelineExplanationWriter().write(ctx, importance=fi)
        assert isinstance(exp, Explanation)
        assert ctx.explanation != ""


# ── TestReasoningLogIntegration ───────────────────────────────────────────────

class TestReasoningLogIntegration:
    """
    Verifies ReasoningLogger → LTM → ReasoningLogReader → LearningEvent pipeline.
    """

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def _make_ctx(self, outcome_confidence: float = 0.8) -> ExecutionContext:
        ctx = ExecutionContext(
            user_input="analyse AAPL",
            session_id="s1",
            selected_agent="TraderAgent",
            intent_type="trade",
            confidence=outcome_confidence,
        )
        ctx.thought_chain = [
            ThoughtStep(content="Checking RSI", confidence=0.7, step_index=0),
            ThoughtStep(content="Signal confirmed", confidence=outcome_confidence, step_index=1),
        ]
        return ctx

    def test_log_and_read_trace(self):
        ltm    = _ltm()
        logger = ReasoningLogger(ltm=ltm)
        reader = ReasoningLogReader(ltm=ltm)

        ctx   = self._make_ctx(0.82)
        trace = self._run(logger.log(ctx, outcome="success"))
        assert trace is not None

        traces = self._run(reader.recent(n=5))
        assert len(traces) == 1
        assert traces[0].outcome    == "success"
        assert traces[0].confidence == 0.82

    def test_failure_trace_stored_with_importance_1(self):
        """Failure traces must not be dropped by LTM importance threshold."""
        ltm    = InMemoryLongTermMemory(importance_threshold=0.9)
        logger = ReasoningLogger(ltm=ltm)
        reader = ReasoningLogReader(ltm=ltm)

        ctx = self._make_ctx(0.20)   # very low confidence
        self._run(logger.log(ctx, outcome="failure"))

        traces = self._run(reader.recent(n=5))
        assert len(traces) == 1   # must be stored despite low confidence

    def test_trace_to_learning_event_pipeline(self):
        ltm    = _ltm()
        logger = ReasoningLogger(ltm=ltm)
        reader = ReasoningLogReader(ltm=ltm)

        ctx = self._make_ctx(0.45)
        ctx.metadata["market_regime"] = "sideways"
        self._run(logger.log(ctx, outcome="failure"))

        traces = self._run(reader.recent(n=5))
        trace  = traces[0]

        ev  = LearningEvent.from_trace(trace, model_version="v1.1")
        rec = ExperienceRecord.from_event(
            ev,
            lesson="Low confidence in sideways regime — reduce position size.",
            confidence_adjustment=-0.10,
        )
        assert ev.outcome               == "failure"
        assert rec.confidence_adjustment == -0.10
        assert "sideways" in rec.lesson


# ── TestAdvisoryOnlyConstraint ────────────────────────────────────────────────

class TestAdvisoryOnlyConstraint:
    """
    Verifies that the learning package is strictly advisory.
    No learning component modifies Brain, DecisionTree, or frozen engine.
    """

    def test_learning_event_does_not_modify_context(self):
        ctx = _ctx(confidence=0.75, response="BUY")
        ev  = LearningEvent(event_type="prediction_outcome", confidence=0.75)
        # LearningEvent construction must not touch ctx
        assert ctx.response    == "BUY"
        assert ctx.confidence  == 0.75

    def test_experience_record_does_not_modify_context(self):
        ctx = _ctx(confidence=0.75)
        ev  = LearningEvent()
        rec = ExperienceRecord.from_event(ev, lesson="test", confidence_adjustment=-0.05)
        assert ctx.confidence == 0.75   # unchanged

    def test_model_evaluator_is_pure(self):
        """ModelEvaluator must not have side effects."""
        records = _records(10, correct_ratio=0.5)
        ev      = ModelEvaluator()
        r1      = ev.evaluate(records)
        r2      = ev.evaluate(records)
        assert r1.accuracy == r2.accuracy   # deterministic

    def test_retraining_trigger_does_not_modify_registry(self):
        reg     = ModelRegistry()
        reg.register("v1.0", model="model_a")
        trigger = RetrainingTrigger(TriggerConfig(cooldown_seconds=0, min_samples=1))
        result  = EvaluationResult(sample_count=5, accuracy=0.30)
        trigger.check(result, model_version="v1.0")
        # Registry must be unchanged
        assert reg.get_active_version() == "v1.0"
        assert reg.get("v1.0")          == "model_a"

    def test_feedback_collector_does_not_touch_frozen_modules(self):
        """FeedbackCollector must not import from frozen trading engine."""
        import app.ai.learning.feedback_collector as fc_module
        with open(fc_module.__file__, encoding="utf-8") as f:
            source = f.read()
        assert "from app.trading" not in source
        assert "import app.trading" not in source


# ── TestDomainAgnosticism ─────────────────────────────────────────────────────

class TestDomainAgnosticism:
    """
    All Phase 7D components must work with non-trading domain data.
    """

    def test_feedback_collector_with_medical_domain(self):
        ltm = _ltm()
        col = FeedbackCollector(ltm=ltm)
        fb  = asyncio.get_event_loop().run_until_complete(
            col.record(
                prediction="HIGH_RISK", actual="confirmed",
                correct=True, confidence=0.91,
                agent_name="MedicalAgent", market_regime="",
            )
        )
        assert fb.prediction == "HIGH_RISK"
        assert fb.agent_name == "MedicalAgent"

    def test_model_evaluator_with_non_trading_records(self):
        records = [
            FeedbackRecord(prediction="APPROVE", actual="approved", correct=True,  confidence=0.88),
            FeedbackRecord(prediction="REJECT",  actual="rejected", correct=True,  confidence=0.72),
            FeedbackRecord(prediction="APPROVE", actual="rejected", correct=False, confidence=0.60),
        ]
        r = ModelEvaluator().evaluate(records)
        assert r.sample_count == 3
        assert abs(r.accuracy - 2/3) < 0.01

    def test_learning_event_with_generic_intent(self):
        ev = LearningEvent(
            event_type="prediction_outcome",
            intent_type="document_classification",
            agent_name="ClassifierAgent",
            outcome="success",
        )
        assert ev.intent_type == "document_classification"

    def test_explanation_formatter_with_generic_prediction(self):
        exp = Explanation(
            prediction="CATEGORY_A",
            confidence=0.91,
            agent_used="ClassifierAgent",
            top_features=[("word_count", 0.4), ("sentiment", 0.3)],
        )
        text = ExplanationFormatter().format_text(exp)
        assert "91%" in text
        assert "ClassifierAgent" in text

    def test_xai_cache_domain_agnostic(self):
        cache = XaiCache()
        fv    = FeatureVector(features={"word_count": 150.0, "sentiment": 0.3})
        fi    = FallbackExplainer().explain(fv)
        key   = cache.make_key("nlp_v1", fv)
        cache.put(key, fi)
        assert cache.get(key) is fi

    def test_model_registry_stores_any_model_type(self):
        reg = ModelRegistry()
        reg.register("sklearn_v1", model={"type": "sklearn", "params": {}})
        reg.register("torch_v1",   model={"type": "torch",   "params": {}})
        assert reg.get("sklearn_v1")["type"] == "sklearn"
        assert reg.get("torch_v1")["type"]   == "torch"
