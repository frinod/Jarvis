"""
app/ai/skills/__init__.py
==========================
Skills package -- BaseSkill ABC and SkillResult.

Architecture §5 defines the Skill interface:
  - Pure computation: no async, no I/O, no LLM calls, no side effects
  - Accept raw data as input, return a structured SkillResult
  - Independently unit-testable with no mocks required

Domain-specific skills live in app/ai/skills/<domain>/ (Phase 6D+).
This file provides the base contract only.

Domain agnosticism
-------------------
  BaseSkill contains zero domain knowledge.
  Domain logic lives in concrete skill subclasses.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── SkillResult ───────────────────────────────────────────────────────────────

@dataclass
class SkillResult:
    """
    Output of one skill execution.
    success=False means the skill ran but produced no useful output.
    error is set when an exception occurred.
    output carries the domain-specific result (always in metadata-style dict).
    """
    skill_name: str
    success:    bool
    output:     Any
    confidence: float          = 0.5
    error:      Optional[str]  = None
    elapsed_ms: float          = 0.0
    metadata:   Dict[str, Any] = field(default_factory=dict)


# ── BaseSkill ABC ─────────────────────────────────────────────────────────────

class BaseSkill(ABC):
    """
    Base contract for all JARVIS skills.

    Skills are pure computation modules:
      - No async (synchronous only)
      - No I/O, no network calls
      - No LLM calls
      - No side effects
      - Independently testable

    Usage
    -----
        class MySkill(BaseSkill):
            name    = "my_skill"
            version = "1.0.0"

            def run(self, data: dict) -> SkillResult:
                value = data.get("input", "")
                return SkillResult(skill_name=self.name, success=True, output=value)
    """

    name:    str = "base_skill"
    version: str = "1.0.0"

    @abstractmethod
    def run(self, data: dict) -> SkillResult:
        """
        Pure computation. No async. No I/O.
        data is a plain dict -- domain data lives here, not as first-class fields.
        """

    def describe(self) -> str:
        """Human-readable description of what this skill does."""
        return f"{self.name} v{self.version}"

    def can_run(self, data: dict) -> bool:
        """
        Return True if this skill can process the given data.
        Default: always True. Override for input validation.
        """
        return True


# ── SkillRegistry ─────────────────────────────────────────────────────────────

class SkillRegistry:
    """
    Holds named BaseSkill instances.
    Agents use this to discover and invoke skills.
    """

    def __init__(self) -> None:
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> BaseSkill:
        if name not in self._skills:
            raise KeyError(f"Skill '{name}' not registered")
        return self._skills[name]

    def has(self, name: str) -> bool:
        return name in self._skills

    def names(self) -> List[str]:
        return list(self._skills.keys())

    def run(self, name: str, data: dict) -> SkillResult:
        """Run a named skill. Returns a failed SkillResult if not found."""
        if name not in self._skills:
            return SkillResult(skill_name=name, success=False, output=None, error=f"Skill '{name}' not found")
        skill = self._skills[name]
        try:
            return skill.run(data)
        except Exception as exc:
            return SkillResult(skill_name=name, success=False, output=None, error=str(exc))

    def __len__(self) -> int:
        return len(self._skills)


__all__ = ["BaseSkill", "SkillResult", "SkillRegistry"]
