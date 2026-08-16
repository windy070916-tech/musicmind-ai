"""Structured knowledge derived from MusicMind analytics."""

from importlib import import_module

from music_ai.knowledge.evidence_reference import knowledge_evidence_id
from music_ai.knowledge.message_keys import FactMessageKey
from music_ai.knowledge.models import (
    FactCategory,
    FactSource,
    FactTimeHorizon,
    ImportanceLevel,
    InsightType,
    KnowledgeFact,
)


__all__ = [
    "ContextualKnowledgeEngine",
    "FactCategory",
    "FactMessageKey",
    "FactSource",
    "FactTimeHorizon",
    "ImportanceLevel",
    "InsightType",
    "KnowledgeEngine",
    "KnowledgeFact",
    "LongTermEvolutionKnowledgeEngine",
    "LongTermKnowledgeEngine",
    "RecentKnowledgeEngine",
    "knowledge_evidence_id",
]

_ENGINE_EXPORTS = {
    "ContextualKnowledgeEngine": ("music_ai.knowledge.contextual_knowledge_engine", "ContextualKnowledgeEngine"),
    "KnowledgeEngine": ("music_ai.knowledge.knowledge_engine", "KnowledgeEngine"),
    "LongTermEvolutionKnowledgeEngine": ("music_ai.knowledge.long_term_evolution_knowledge_engine", "LongTermEvolutionKnowledgeEngine"),
    "LongTermKnowledgeEngine": ("music_ai.knowledge.long_term_knowledge_engine", "LongTermKnowledgeEngine"),
    "RecentKnowledgeEngine": ("music_ai.knowledge.recent_knowledge_engine", "RecentKnowledgeEngine"),
}


def __getattr__(name: str):
    """Load engine implementations only when a consumer explicitly asks for one."""
    target = _ENGINE_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value
