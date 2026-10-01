"""
app/ai/rag/context_builder.py
==============================
ContextBuilder -- assembles retrieved memories into prompt-ready context.

Architecture (per review):
    ContextBlock (dataclass)        -- typed, named block of context text
    ContextBuilder                  -- filter → compress → deduplicate → budget → blocks
    PromptContextAssembler          -- ContextBlocks → formatted string for SystemPromptBuilder

ContextBlock types (extensible):
    conversation, market, portfolio, strategy, learning, system

Token budget:
    Entries are injected in descending relevance order (highest first).
    Injection stops when the token budget is exhausted.
    Token count estimated as len(content) // 4 (fast, conservative).
    Default budget: 800 tokens (ADR-003).

Retrieval metrics passthrough:
    ContextBuilder.build() accepts a RetrievalResult and attaches its
    metrics to the assembled context for debugging and XAI.

Resilience (Rule 11b):
    build() never raises. Returns empty ContextAssembly on any failure.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.ai.memory.short_term import MemoryEntry

logger = logging.getLogger(__name__)

# Tokens per character estimate (conservative)
_CHARS_PER_TOKEN = 4
_DEFAULT_BUDGET  = 800   # tokens (ADR-003)


# ── ContextBlock ──────────────────────────────────────────────────────────────

@dataclass
class ContextBlock:
    """
    One typed, named block of context text.

    block_type maps to a semantic category so Brain can compose contexts
    selectively (e.g. TraderAgent requests market + strategy only).
    """
    block_type:  str    # "conversation" | "market" | "portfolio" | "strategy" | "learning" | "system"
    content:     str
    token_count: int    = 0
    source_id:   str    = ""   # MemoryEntry.id that produced this block
    importance:  float  = 0.5

    def __post_init__(self):
        if self.token_count == 0:
            self.token_count = max(1, len(self.content) // _CHARS_PER_TOKEN)


# ── ContextAssembly ───────────────────────────────────────────────────────────

@dataclass
class ContextAssembly:
    """
    Complete assembled context for one request.

    blocks:          ordered list of ContextBlocks (highest relevance first)
    total_tokens:    sum of block token counts
    entries_used:    how many MemoryEntries were included
    entries_dropped: how many were dropped due to budget
    prompt_text:     formatted string ready for SystemPromptBuilder injection
    metrics:         retrieval pipeline metrics (from RetrievalResult)
    """
    blocks:           List[ContextBlock]  = field(default_factory=list)
    total_tokens:     int                 = 0
    entries_used:     int                 = 0
    entries_dropped:  int                 = 0
    prompt_text:      str                 = ""
    metrics:          Dict                = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return len(self.blocks) == 0


# ── ContextBuilder ────────────────────────────────────────────────────────────

class ContextBuilder:
    """
    Transforms a list of MemoryEntries into a token-budgeted ContextAssembly.

    Pipeline:
        entries → filter duplicates → map to ContextBlocks →
        sort by importance → apply token budget → assemble prompt text

    Usage
    -----
        builder  = ContextBuilder(max_tokens=800)
        assembly = builder.build(entries, query="RELIANCE breakout")
        # assembly.prompt_text ready for SystemPromptBuilder
        # assembly.metrics contains retrieval pipeline counts
    """

    # Maps MemoryEntry metadata entry_type to ContextBlock block_type
    _TYPE_MAP = {
        "conversation":    "conversation",
        "market_snapshot": "market",
        "news":            "market",
        "analysis_result": "strategy",
        "portfolio":       "portfolio",
        "learning":        "learning",
    }

    def __init__(self, max_tokens: int = _DEFAULT_BUDGET) -> None:
        self._max_tokens = max_tokens

    def build(
        self,
        entries:  List[MemoryEntry],
        query:    str = "",
        metrics:  Optional[dict] = None,
    ) -> ContextAssembly:
        """
        Build a ContextAssembly from entries. Never raises (Rule 11b).
        entries should already be relevance-ordered (highest first).
        """
        try:
            return self._build(entries, query, metrics or {})
        except Exception as exc:
            logger.warning("ContextBuilder.build failed: %s", exc)
            return ContextAssembly(metrics=metrics or {})

    def _build(self, entries: List[MemoryEntry], query: str, metrics: dict) -> ContextAssembly:
        seen_ids:    set  = set()
        blocks:      List[ContextBlock] = []
        total_tokens = 0
        dropped      = 0

        for entry in entries:
            # Skip non-MemoryEntry objects (malformed memory — Rule 11b)
            if not isinstance(entry, MemoryEntry):
                dropped += 1
                continue

            # Deduplicate by id
            if entry.id in seen_ids:
                dropped += 1
                continue
            seen_ids.add(entry.id)

            content = entry.content.strip()
            if not content:
                dropped += 1
                continue

            block = ContextBlock(
                block_type=self._classify(entry),
                content=content,
                source_id=entry.id,
                importance=entry.importance,
            )

            # Token budget check
            if total_tokens + block.token_count > self._max_tokens:
                dropped += 1
                continue

            blocks.append(block)
            total_tokens += block.token_count

        prompt_text = _format_blocks(blocks)

        return ContextAssembly(
            blocks=blocks,
            total_tokens=total_tokens,
            entries_used=len(blocks),
            entries_dropped=dropped,
            prompt_text=prompt_text,
            metrics=metrics,
        )

    def _classify(self, entry: MemoryEntry) -> str:
        """Map entry_type metadata to a ContextBlock block_type."""
        entry_type = entry.metadata.get("entry_type", "")
        return self._TYPE_MAP.get(entry_type, "conversation")


# ── PromptContextAssembler ────────────────────────────────────────────────────

class PromptContextAssembler:
    """
    Formats a ContextAssembly into a string for SystemPromptBuilder injection.

    Supports selective block_type filtering so agents can request only
    the context categories they need (e.g. TraderAgent: market + strategy).

    Usage
    -----
        assembler = PromptContextAssembler()
        text = assembler.format(assembly, include_types=["market", "strategy"])
    """

    def format(
        self,
        assembly:      ContextAssembly,
        include_types: Optional[List[str]] = None,
    ) -> str:
        """Format assembly into a prompt string. Returns '' if empty."""
        blocks = assembly.blocks
        if include_types:
            blocks = [b for b in blocks if b.block_type in include_types]
        if not blocks:
            return ""
        return _format_blocks(blocks)

    def metrics_summary(self, assembly: ContextAssembly) -> str:
        """One-line metrics string for logging and XAI."""
        m = assembly.metrics
        return (
            f"retrieved={m.get('dense_count', 0)+m.get('keyword_count', 0)} "
            f"merged={m.get('merged_count', 0)} "
            f"used={assembly.entries_used} "
            f"dropped={assembly.entries_dropped} "
            f"tokens={assembly.total_tokens} "
            f"cache_hit={m.get('cache_hit', False)}"
        )


# ── Formatting ────────────────────────────────────────────────────────────────

def _format_blocks(blocks: List[ContextBlock]) -> str:
    if not blocks:
        return ""
    lines = []
    for b in blocks:
        prefix = f"[{b.block_type}]"
        lines.append(f"{prefix} {b.content}")
    return "\n".join(lines)
