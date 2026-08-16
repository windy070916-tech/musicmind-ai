"""Static dependency ownership checks for Sprint 4A interpretation layers."""

import ast
from pathlib import Path
import subprocess
import sys


_ROOT = Path(__file__).resolve().parents[1]


def _python_files(relative_directory: str) -> tuple[Path, ...]:
    return tuple(sorted((_ROOT / relative_directory).rglob("*.py")))


def _imports(relative_directory: str) -> tuple[tuple[Path, str], ...]:
    imports: list[tuple[Path, str]] = []
    for path in _python_files(relative_directory):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend((path, alias.name) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.append((path, node.module))
    return tuple(imports)


def _assert_no_import_prefixes(
    relative_directory: str, forbidden_prefixes: tuple[str, ...]
) -> None:
    violations = tuple(
        (path.relative_to(_ROOT), module, prefix)
        for path, module in _imports(relative_directory)
        for prefix in forbidden_prefixes
        if module == prefix or module.startswith(f"{prefix}.")
    )
    assert violations == ()


def _defined_or_referenced_names(relative_directory: str) -> frozenset[str]:
    names: set[str] = set()
    for path in _python_files(relative_directory):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
    return frozenset(names)


def test_ai_cannot_import_raw_listening_infrastructure() -> None:
    _assert_no_import_prefixes(
        "music_ai/ai",
        (
            "music_ai.database",
            "music_ai.spotify",
            "music_ai.memory",
            "music_ai.repository",
            "music_ai.temporal",
            "music_ai.analytics",
            "music_ai.knowledge",
        ),
    )


def test_signal_depends_on_knowledge_not_infrastructure_or_downstream_layers() -> None:
    _assert_no_import_prefixes(
        "music_ai/signal",
        (
            "music_ai.database",
            "music_ai.spotify",
            "music_ai.memory",
            "music_ai.repository",
            "music_ai.analytics",
            "music_ai.temporal",
            "music_ai.localization",
            "music_ai.presentation",
            "music_ai.ai",
        ),
    )


def test_planner_cannot_import_raw_evidence_or_provider_layers() -> None:
    _assert_no_import_prefixes(
        "music_ai/planning",
        (
            "music_ai.database",
            "music_ai.spotify",
            "music_ai.memory",
            "music_ai.repository",
            "music_ai.analytics",
            "music_ai.temporal",
            "music_ai.ai",
        ),
    )


def test_provider_adapters_remain_transport_only() -> None:
    _assert_no_import_prefixes(
        "music_ai/ai/providers",
        (
            "music_ai.knowledge",
            "music_ai.signal",
            "music_ai.planning",
            "music_ai.narrative",
            "music_ai.visible_content",
            "music_ai.presentation",
        ),
    )
    names = _defined_or_referenced_names("music_ai/ai/providers")
    assert names.isdisjoint(
        {
            "EvidenceMaturity",
            "InterpretationRole",
            "SignalRelationship",
            "SignalType",
            "SignalProjector",
        }
    )


def test_narrative_remains_independent_of_interpretation_policy() -> None:
    _assert_no_import_prefixes(
        "music_ai/narrative",
        ("music_ai.signal", "music_ai.planning", "music_ai.ai"),
    )


def test_presentation_cannot_own_signal_ranking_or_relationships() -> None:
    _assert_no_import_prefixes(
        "music_ai/presentation",
        ("music_ai.signal", "music_ai.planning", "music_ai.ai.providers"),
    )
    names = _defined_or_referenced_names("music_ai/presentation")
    assert names.isdisjoint(
        {
            "EvidenceMaturity",
            "InterpretationPlanner",
            "SignalRelationship",
            "SignalRoleEligibility",
            "SignalType",
            "SignalProjector",
            "role_eligibility_for_maturity",
        }
    )


def test_fresh_imports_do_not_activate_forbidden_transitive_layers() -> None:
    cases = (
        (
            "music_ai.ai.providers.openai",
            (
                "music_ai.analytics",
                "music_ai.database",
                "music_ai.knowledge",
                "music_ai.memory",
                "music_ai.narrative",
                "music_ai.planning",
                "music_ai.signal",
                "music_ai.temporal",
                "music_ai.visible_content",
            ),
        ),
        (
            "music_ai.ai.interpretation_request",
            (
                "music_ai.analytics",
                "music_ai.database",
                "music_ai.knowledge",
                "music_ai.memory",
                "music_ai.narrative",
                "music_ai.repository",
                "music_ai.spotify",
                "music_ai.temporal",
            ),
        ),
        (
            "music_ai.signal.projection",
            (
                "music_ai.ai",
                "music_ai.analytics",
                "music_ai.database",
                "music_ai.localization",
                "music_ai.memory",
                "music_ai.presentation",
                "music_ai.repository",
                "music_ai.spotify",
                "music_ai.temporal",
            ),
        ),
        (
            "music_ai.planning.planner",
            (
                "music_ai.ai",
                "music_ai.analytics",
                "music_ai.database",
                "music_ai.memory",
                "music_ai.repository",
                "music_ai.spotify",
                "music_ai.temporal",
            ),
        ),
    )
    for module, forbidden in cases:
        script = (
            "import importlib,sys;"
            f"importlib.import_module({module!r});"
            f"forbidden={forbidden!r};"
            "violations=[name for name in sys.modules "
            "if any(name == prefix or name.startswith(prefix + '.') "
            "for prefix in forbidden)];"
            "raise SystemExit(1 if violations else 0)"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, (module, completed.stdout, completed.stderr)
