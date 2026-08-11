"""Static architecture checks for Sprint 3E dependency ownership."""

from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]


def _python_source(relative_directory: str) -> str:
    directory = _ROOT / relative_directory
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(directory.rglob("*.py"))
    )


def test_temporal_does_not_import_downstream_product_layers() -> None:
    source = _python_source("music_ai/temporal")
    for forbidden in (
        "music_ai.knowledge",
        "music_ai.narrative",
        "music_ai.presentation",
        "music_ai.localization",
    ):
        assert forbidden not in source


def test_knowledge_and_narrative_remain_localization_independent() -> None:
    knowledge_source = _python_source("music_ai/knowledge")
    narrative_source = _python_source("music_ai/narrative")

    assert "music_ai.localization" not in knowledge_source
    assert "music_ai.presentation" not in knowledge_source
    assert "music_ai.localization" not in narrative_source


def test_presentation_contains_no_sprint3e_selection_policy() -> None:
    source = _python_source("music_ai/presentation")

    assert "ARTIST_DURATION_SHARE_EVOLUTION" not in source
    assert "ARTIST_BREADTH_EVOLUTION" not in source
    assert "LISTENING_CONCENTRATION_EVOLUTION" not in source
    assert "suppress" not in source.casefold()
    assert "deduplic" not in source.casefold()


def test_provider_adapters_contain_no_temporal_product_branches() -> None:
    source = _python_source("music_ai/ai/providers")

    assert "long_term" not in source.casefold()
    assert "evolution" not in source.casefold()
