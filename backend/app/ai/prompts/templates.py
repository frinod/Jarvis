"""
app/ai/prompts/templates.py
============================
PromptTemplate -- named, reusable prompt templates with variable substitution.

Design
------
  - PromptTemplate is a simple dataclass: name, template string, variables.
  - render() substitutes variables using Python str.format_map().
  - TemplateRegistry holds named templates; get() raises if not found.
  - Built-in templates cover the standard pipeline stages.
  - All templates are domain-agnostic -- no trading or market content.

Domain agnosticism
-------------------
  Templates contain no domain knowledge. Domain data is injected via
  variables at render time, always through metadata dicts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ── PromptTemplate ────────────────────────────────────────────────────────────

@dataclass
class PromptTemplate:
    """
    A named prompt template with variable substitution.

    Variables are referenced as {variable_name} in the template string.
    render() raises KeyError if a required variable is missing.

    Usage
    -----
        t = PromptTemplate(
            name="greeting",
            template="Hello, {name}! How can I help with {topic}?",
            variables=["name", "topic"],
        )
        text = t.render(name="Alice", topic="research")
    """
    name:        str
    template:    str
    variables:   List[str]      = field(default_factory=list)
    description: str            = ""
    metadata:    Dict[str, str] = field(default_factory=dict)

    def render(self, **kwargs) -> str:
        """
        Substitute variables and return the rendered string.
        Raises KeyError if a required variable is not provided.
        Extra kwargs are silently ignored.
        """
        try:
            return self.template.format_map(kwargs)
        except KeyError as exc:
            raise KeyError(
                f"Template '{self.name}' missing variable: {exc}"
            ) from exc

    def render_safe(self, **kwargs) -> str:
        """
        Like render() but missing variables are left as {variable_name}.
        Never raises.
        """
        class _SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"
        return self.template.format_map(_SafeDict(kwargs))

    def required_variables(self) -> List[str]:
        """Return the declared variable list."""
        return list(self.variables)


# ── TemplateRegistry ──────────────────────────────────────────────────────────

class TemplateRegistry:
    """
    Holds named PromptTemplates. Thread-safe for reads (no writes after init).

    Usage
    -----
        registry = TemplateRegistry.default()
        t = registry.get("system_base")
        text = t.render(agent_name="Kiro", objective="help the user")
    """

    def __init__(self) -> None:
        self._templates: Dict[str, PromptTemplate] = {}

    def register(self, template: PromptTemplate) -> None:
        self._templates[template.name] = template

    def get(self, name: str) -> PromptTemplate:
        if name not in self._templates:
            raise KeyError(f"Template '{name}' not found in registry")
        return self._templates[name]

    def has(self, name: str) -> bool:
        return name in self._templates

    def names(self) -> List[str]:
        return list(self._templates.keys())

    def __len__(self) -> int:
        return len(self._templates)

    # ── Built-in templates ────────────────────────────────────────────

    @classmethod
    def default(cls) -> "TemplateRegistry":
        """Return a registry pre-loaded with all built-in templates."""
        registry = cls()
        for t in _BUILTIN_TEMPLATES:
            registry.register(t)
        return registry


# ── Built-in templates ────────────────────────────────────────────────────────

_BUILTIN_TEMPLATES: List[PromptTemplate] = [

    PromptTemplate(
        name="system_base",
        description="Base system prompt injected at the start of every request.",
        variables=["agent_name", "objective"],
        template=(
            "You are {agent_name}, an intelligent AI assistant.\n"
            "Your current objective: {objective}\n"
            "Be concise, accurate, and helpful."
        ),
    ),

    PromptTemplate(
        name="system_with_memory",
        description="System prompt with memory context injected.",
        variables=["agent_name", "objective", "memory_context"],
        template=(
            "You are {agent_name}, an intelligent AI assistant.\n"
            "Your current objective: {objective}\n\n"
            "Relevant context from memory:\n{memory_context}\n\n"
            "Use the above context to inform your response."
        ),
    ),

    PromptTemplate(
        name="reasoning_chain",
        description="Prompt that includes the reasoning chain for transparency.",
        variables=["objective", "thought_chain"],
        template=(
            "Objective: {objective}\n\n"
            "Reasoning:\n{thought_chain}\n\n"
            "Based on the above reasoning, provide a clear and accurate response."
        ),
    ),

    PromptTemplate(
        name="retry_with_critique",
        description="Prompt for a reasoning retry, injecting the previous critique.",
        variables=["objective", "critique"],
        template=(
            "Objective: {objective}\n\n"
            "Previous reasoning had issues: {critique}\n\n"
            "Please reason again, addressing the issues above."
        ),
    ),

    PromptTemplate(
        name="verification",
        description="Prompt asking the model to verify its own reasoning.",
        variables=["objective", "response"],
        template=(
            "Objective: {objective}\n\n"
            "Proposed response: {response}\n\n"
            "Is this response accurate, complete, and appropriate? "
            "If not, explain what is wrong."
        ),
    ),

    PromptTemplate(
        name="summarise_memory",
        description="Prompt to summarise a list of memory entries.",
        variables=["entries"],
        template=(
            "Summarise the following memory entries into a concise context paragraph:\n\n"
            "{entries}"
        ),
    ),
]
