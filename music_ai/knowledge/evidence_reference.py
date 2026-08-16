"""Deterministic, locale-neutral identities for qualified Knowledge evidence."""

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from enum import Enum
from hashlib import sha256
import json
from math import isfinite

from music_ai.knowledge.models import KnowledgeFact


def knowledge_evidence_id(fact: KnowledgeFact) -> str:
    """Return a stable run-scoped reference for one qualified fact.

    User-visible wording, display priority, and ``confidence`` are deliberately
    excluded.  The identity follows the canonical fact contract and its structured
    evidence so deterministic composition and Signal projection can refer to the
    same observation without depending on localized prose.
    """
    if not isinstance(fact, KnowledgeFact):
        raise TypeError("fact must be KnowledgeFact.")
    payload = {
        "category": _enum_value(fact.category),
        "source": _enum_value(fact.source),
        "time_horizon": _enum_value(fact.time_horizon),
        "date_range": _canonical_value(fact.date_range),
        "metadata": _canonical_value(fact.metadata),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"kf_{sha256(encoded).hexdigest()[:20]}"


def _enum_value(value: object) -> object:
    return value.value if isinstance(value, Enum) else value


def _canonical_value(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("Knowledge evidence cannot contain non-finite floats.")
        return value
    if isinstance(value, Enum):
        return _canonical_value(value.value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        canonical_items = (_canonical_value(item) for item in value)
        return sorted(
            canonical_items,
            key=lambda item: json.dumps(
                item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonical_value(item) for item in value]
    raise TypeError(
        "Knowledge evidence metadata must contain deterministic JSON-like values; "
        f"got {type(value).__name__}."
    )
