"""
tests/phase6/test_6d_skills.py
================================
Unit tests for Skills package (Task 6D.6).

Covers: SkillResult, BaseSkill contract, SkillRegistry.
"""
import pytest

from app.ai.skills import BaseSkill, SkillResult, SkillRegistry


# ── Concrete skill for testing ────────────────────────────────────────────────

class _UpperSkill(BaseSkill):
    name    = "upper"
    version = "1.0.0"

    def run(self, data: dict) -> SkillResult:
        text = data.get("text", "")
        return SkillResult(skill_name=self.name, success=True, output=text.upper(), confidence=0.9)


class _FailingSkill(BaseSkill):
    name    = "failing"
    version = "1.0.0"

    def run(self, data: dict) -> SkillResult:
        raise ValueError("skill error")


class _ConditionalSkill(BaseSkill):
    name    = "conditional"
    version = "1.0.0"

    def can_run(self, data: dict) -> bool:
        return "required_key" in data

    def run(self, data: dict) -> SkillResult:
        return SkillResult(skill_name=self.name, success=True, output=data["required_key"])


# ── TestSkillResult ───────────────────────────────────────────────────────────

class TestSkillResult:

    def test_construction(self):
        r = SkillResult(skill_name="test", success=True, output="result")
        assert r.skill_name == "test"
        assert r.success    is True
        assert r.output     == "result"

    def test_default_confidence(self):
        r = SkillResult(skill_name="t", success=True, output=None)
        assert r.confidence == 0.5

    def test_error_field(self):
        r = SkillResult(skill_name="t", success=False, output=None, error="timeout")
        assert r.error == "timeout"

    def test_elapsed_ms_default(self):
        r = SkillResult(skill_name="t", success=True, output=None)
        assert r.elapsed_ms == 0.0

    def test_metadata_default_empty(self):
        r = SkillResult(skill_name="t", success=True, output=None)
        assert r.metadata == {}


# ── TestBaseSkill ─────────────────────────────────────────────────────────────

class TestBaseSkill:

    def test_abstract_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            BaseSkill()

    def test_concrete_skill_instantiates(self):
        skill = _UpperSkill()
        assert skill is not None

    def test_run_returns_skill_result(self):
        skill  = _UpperSkill()
        result = skill.run({"text": "hello"})
        assert isinstance(result, SkillResult)

    def test_run_produces_correct_output(self):
        skill  = _UpperSkill()
        result = skill.run({"text": "hello"})
        assert result.output  == "HELLO"
        assert result.success is True

    def test_describe_returns_string(self):
        skill = _UpperSkill()
        desc  = skill.describe()
        assert "upper" in desc
        assert "1.0.0" in desc

    def test_can_run_default_true(self):
        skill = _UpperSkill()
        assert skill.can_run({}) is True

    def test_can_run_conditional(self):
        skill = _ConditionalSkill()
        assert skill.can_run({"required_key": "x"}) is True
        assert skill.can_run({}) is False

    def test_skill_is_synchronous(self):
        """Skills must be synchronous -- no async."""
        import inspect
        skill = _UpperSkill()
        assert not inspect.iscoroutinefunction(skill.run)


# ── TestSkillRegistry ─────────────────────────────────────────────────────────

class TestSkillRegistry:

    def test_register_and_get(self):
        registry = SkillRegistry()
        skill    = _UpperSkill()
        registry.register(skill)
        assert registry.get("upper") is skill

    def test_get_missing_raises(self):
        registry = SkillRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_has_returns_bool(self):
        registry = SkillRegistry()
        registry.register(_UpperSkill())
        assert registry.has("upper")   is True
        assert registry.has("missing") is False

    def test_names_returns_list(self):
        registry = SkillRegistry()
        registry.register(_UpperSkill())
        assert "upper" in registry.names()

    def test_len(self):
        registry = SkillRegistry()
        registry.register(_UpperSkill())
        assert len(registry) == 1

    def test_run_success(self):
        registry = SkillRegistry()
        registry.register(_UpperSkill())
        result = registry.run("upper", {"text": "hello"})
        assert result.success is True
        assert result.output  == "HELLO"

    def test_run_missing_skill_returns_failed_result(self):
        registry = SkillRegistry()
        result   = registry.run("nonexistent", {})
        assert result.success is False
        assert "not found" in result.error

    def test_run_exception_returns_failed_result(self):
        registry = SkillRegistry()
        registry.register(_FailingSkill())
        result = registry.run("failing", {})
        assert result.success is False
        assert result.error   == "skill error"

    def test_multiple_skills_registered(self):
        registry = SkillRegistry()
        registry.register(_UpperSkill())
        registry.register(_ConditionalSkill())
        assert len(registry) == 2
        assert registry.has("upper")
        assert registry.has("conditional")
