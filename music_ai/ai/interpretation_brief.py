"""Strict dynamic response contract for MusicMind AI interpretation prose."""

from collections.abc import Mapping
from dataclasses import InitVar, dataclass
import re

from music_ai.ai.interpretation_request import InterpretationRequest
from music_ai.planning.models import InterpretationRole


# A short paragraph is deliberately bounded independently of provider token settings.
MAX_INTERPRETATION_TEXT_CHARACTERS = 500
_ITEM_KEYS = frozenset({"plan_item_id", "role", "text"})
_PAYLOAD_KEYS = frozenset({"items"})
_MARKDOWN_PATTERN = re.compile(
    r"```|`|\*\*|__|~~|!\[|\[[^\]]+\]\([^\)]+\)|"
    r"\[[^\]]+\]\[[^\]]*\]|\[[^\]]+\]:\s*\S+|<[^>]+>|"
    r"\*[^*]+\*|(?<!\w)_[^_]+_(?!\w)|"
    r"(^|\s)#{1,6}\s|(^|\s)>\s|^\s*[-+*]\s|^\s*-{3,}\s*$|"
    r"^\s*\d+[.)]\s"
)
_EMOJI_PATTERN = re.compile(
    "[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF]"
)


@dataclass(frozen=True, slots=True)
class InterpretationBriefItem:
    """One provider-realized paragraph tied to an approved plan item."""

    plan_item_id: str
    role: InterpretationRole
    text: str
    approved_opaque_labels: InitVar[tuple[str, ...]] = ()

    def __post_init__(self, approved_opaque_labels: tuple[str, ...]) -> None:
        if not isinstance(self.plan_item_id, str) or not self.plan_item_id.strip():
            raise ValueError("plan_item_id must be non-empty text.")
        if not isinstance(self.role, InterpretationRole):
            raise TypeError("role must be InterpretationRole.")
        object.__setattr__(
            self,
            "text",
            _plain_bounded_text(self.text, approved_opaque_labels),
        )


@dataclass(frozen=True, slots=True)
class InterpretationBrief:
    """Validated dynamic brief in deterministic plan order."""

    items: tuple[InterpretationBriefItem, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        if len(self.items) > 3:
            raise ValueError("Interpretation brief cannot contain more than three items.")
        if any(not isinstance(item, InterpretationBriefItem) for item in self.items):
            raise TypeError("Brief items must be InterpretationBriefItem values.")
        item_ids = tuple(item.plan_item_id for item in self.items)
        roles = tuple(item.role for item in self.items)
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Interpretation brief cannot duplicate a plan item.")
        if len(roles) != len(set(roles)):
            raise ValueError("Interpretation brief cannot duplicate a role.")
        if (
            InterpretationRole.SECONDARY in roles
            and InterpretationRole.PRIMARY not in roles
        ):
            raise ValueError("Secondary cannot exist without Primary.")
        role_order = {
            InterpretationRole.PRIMARY: 0,
            InterpretationRole.SECONDARY: 1,
            InterpretationRole.WATCH: 2,
        }
        if roles != tuple(sorted(roles, key=role_order.__getitem__)):
            raise ValueError("Brief items must follow Primary, Secondary, Watch order.")

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, object],
        request: InterpretationRequest,
    ) -> "InterpretationBrief":
        """Strictly validate provider structure and references against ``request``."""
        if not isinstance(payload, Mapping) or frozenset(payload) != _PAYLOAD_KEYS:
            raise ValueError("Interpretation response must contain only 'items'.")

        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            raise ValueError("Interpretation response 'items' must be a list.")

        planned_items = tuple(request.plan_items)
        if planned_items and not 1 <= len(raw_items) <= 3:
            raise ValueError("An invoked interpretation response requires 1-3 items.")
        if not planned_items and raw_items:
            raise ValueError("An empty plan cannot have response items.")
        if len(raw_items) != len(planned_items):
            raise ValueError("Interpretation response must realize every planned item.")

        expected = {item.plan_item_id: item for item in planned_items}
        parsed: dict[str, InterpretationBriefItem] = {}
        seen_roles: set[InterpretationRole] = set()
        for raw_item in raw_items:
            if not isinstance(raw_item, Mapping) or frozenset(raw_item) != _ITEM_KEYS:
                raise ValueError("Each interpretation item must use the exact item schema.")
            item_id = raw_item.get("plan_item_id")
            if not isinstance(item_id, str) or item_id not in expected:
                raise ValueError("Interpretation response references an unknown plan item.")
            if item_id in parsed:
                raise ValueError("Interpretation response contains a duplicate plan item.")

            role_value = raw_item.get("role")
            try:
                role = InterpretationRole(role_value)
            except (TypeError, ValueError) as error:
                raise ValueError("Interpretation response contains an unexpected role.") from error
            if role in seen_roles:
                raise ValueError("Interpretation response contains a duplicate role.")
            if role.value != expected[item_id].role:
                raise ValueError("Interpretation response role does not match the plan.")

            parsed[item_id] = InterpretationBriefItem(
                item_id,
                role,
                raw_item.get("text"),  # type: ignore[arg-type]
                request.approved_opaque_labels,
            )
            seen_roles.add(role)

        if frozenset(parsed) != frozenset(expected):
            raise ValueError("Interpretation response omitted a planned item.")
        return cls(tuple(parsed[item.plan_item_id] for item in planned_items))


def _plain_bounded_text(
    value: object,
    approved_opaque_labels: tuple[str, ...] = (),
) -> str:
    """Validate provider prose while preserving exact selected source labels."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Interpretation text must be a non-empty string.")
    text = value.strip()
    if len(text) > MAX_INTERPRETATION_TEXT_CHARACTERS:
        raise ValueError(
            "Interpretation text exceeds the 500-character paragraph limit."
        )
    approved_spans = _approved_label_spans(text, approved_opaque_labels)
    prohibited_matches = (
        *_MARKDOWN_PATTERN.finditer(text),
        *_EMOJI_PATTERN.finditer(text),
    )
    if "\n" in text or "\r" in text or any(
        not _inside_approved_span(match.span(), approved_spans)
        for match in prohibited_matches
    ):
        raise ValueError("Interpretation text must be one plain-text paragraph.")
    return text


def _approved_label_spans(
    text: str,
    approved_opaque_labels: tuple[str, ...],
) -> tuple[tuple[int, int], ...]:
    """Locate exact selected-label occurrences without changing provider text."""
    if not isinstance(approved_opaque_labels, tuple):
        raise TypeError("approved_opaque_labels must be a tuple.")
    if any(not isinstance(label, str) or not label for label in approved_opaque_labels):
        raise ValueError("approved_opaque_labels must contain non-empty strings.")

    spans: list[tuple[int, int]] = []
    for label in sorted(
        set(approved_opaque_labels),
        key=lambda value: (-len(value), value),
    ):
        start = 0
        while True:
            occurrence = text.find(label, start)
            if occurrence < 0:
                break
            spans.append((occurrence, occurrence + len(label)))
            start = occurrence + 1
    return tuple(spans)


def _inside_approved_span(
    match_span: tuple[int, int],
    approved_spans: tuple[tuple[int, int], ...],
) -> bool:
    """Return whether a prohibited token is wholly inside one exact source label."""
    start, end = match_span
    return any(
        start >= allowed_start and end <= allowed_end
        for allowed_start, allowed_end in approved_spans
    )
