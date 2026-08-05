from collections.abc import Iterator
from pathlib import Path

import pytest

import main
import music_ai.localization.resolver as resolver_module
from music_ai.localization import (
    SupportedLocale,
    UnsupportedLocaleError,
    resolve_locale,
)


class Inputs:
    def __init__(self, values: list[str | BaseException]) -> None:
        self._values: Iterator[str | BaseException] = iter(values)
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        value = next(self._values)
        if isinstance(value, BaseException):
            raise value
        return value


def _resolve(
    argv: tuple[str, ...] = (),
    environment: dict[str, str] | None = None,
    *,
    is_tty: bool = False,
    inputs: Inputs | None = None,
    output: list[str] | None = None,
) -> SupportedLocale:
    reader = inputs or Inputs([])
    messages = output if output is not None else []
    return resolve_locale(
        argv,
        environment or {},
        is_tty=is_tty,
        read_input=reader,
        write_output=messages.append,
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [("zh-CN", SupportedLocale.ZH_CN), (" en-US ", SupportedLocale.EN_US)],
)
def test_cli_selects_supported_locale(value: str, expected: SupportedLocale) -> None:
    assert _resolve(("--locale", value)) is expected


def test_valid_cli_overrides_conflicting_or_invalid_environment() -> None:
    assert _resolve(
        ("--locale", "zh-CN"), {"MUSICMIND_LOCALE": "fr-FR"}
    ) is SupportedLocale.ZH_CN


def test_valid_environment_bypasses_interactive_input() -> None:
    inputs = Inputs(["1"])
    assert _resolve(
        environment={"MUSICMIND_LOCALE": "en-US"},
        is_tty=True,
        inputs=inputs,
    ) is SupportedLocale.EN_US
    assert inputs.calls == 0


@pytest.mark.parametrize("value", ["fr-FR", "", "   ", "EN-US", "zh-cn"])
def test_invalid_explicit_cli_or_environment_value_fails(value: str) -> None:
    with pytest.raises(UnsupportedLocaleError) as cli_error:
        _resolve(("--locale", value))
    assert str(cli_error.value).endswith("Supported locales: zh-CN, en-US")

    with pytest.raises(UnsupportedLocaleError):
        _resolve(environment={"MUSICMIND_LOCALE": value})


@pytest.mark.parametrize(
    ("selection", "expected"),
    [("1", SupportedLocale.ZH_CN), ("2", SupportedLocale.EN_US), ("  ", SupportedLocale.ZH_CN)],
)
def test_interactive_selection(selection: str, expected: SupportedLocale) -> None:
    output: list[str] = []
    assert _resolve(
        is_tty=True,
        inputs=Inputs([selection]),
        output=output,
    ) is expected
    assert output[0].startswith("请选择报告语言 / Choose report language:")


def test_invalid_interactive_input_retries() -> None:
    output: list[str] = []
    inputs = Inputs(["x", " 3 ", "2"])
    assert _resolve(is_tty=True, inputs=inputs, output=output) is SupportedLocale.EN_US
    assert sum(message.startswith("请选择报告语言") for message in output) == 1
    assert output.count("请输入 1 或 2 / Please enter 1 or 2.") == 2
    assert inputs.calls == 3


def test_eof_and_non_interactive_execution_default_without_blocking() -> None:
    output: list[str] = []
    eof = Inputs([EOFError()])
    assert _resolve(is_tty=True, inputs=eof, output=output) is SupportedLocale.ZH_CN
    assert sum(message.startswith("请选择报告语言") for message in output) == 1

    unused = Inputs([AssertionError("stdin must not be read")])
    non_tty_output: list[str] = []
    assert _resolve(
        is_tty=False,
        inputs=unused,
        output=non_tty_output,
    ) is SupportedLocale.ZH_CN
    assert unused.calls == 0
    assert non_tty_output == []


def test_eof_after_invalid_interactive_input_defaults_to_chinese() -> None:
    output: list[str] = []
    inputs = Inputs(["invalid", EOFError()])

    assert _resolve(is_tty=True, inputs=inputs, output=output) is SupportedLocale.ZH_CN
    assert sum(message.startswith("请选择报告语言") for message in output) == 1
    assert output.count("请输入 1 或 2 / Please enter 1 or 2.") == 1
    assert inputs.calls == 2


def test_cli_help_is_fixed_bilingual_bootstrap_copy(capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        _resolve(("--help",))

    assert exit_info.value.code == 0
    assert "报告语言 / Report language: zh-CN or en-US" in capsys.readouterr().out


def test_resolver_has_no_catalog_or_ui_message_key_dependency() -> None:
    source = Path(resolver_module.__file__).read_text(encoding="utf-8")

    assert "localization.catalog" not in source
    assert "ui_text" not in source
    assert "UiMessageKey" not in source


def test_main_reports_invalid_locale_before_settings_or_authentication(
    monkeypatch, capsys
) -> None:
    events: list[str] = []
    monkeypatch.setattr(main, "load_environment", lambda: events.append("dotenv"))
    monkeypatch.setattr(
        main,
        "load_spotify_settings",
        lambda: (_ for _ in ()).throw(AssertionError("settings must not load")),
    )
    result = main.main(("--locale", "fr-FR"))
    assert result == 2
    assert events == ["dotenv"]
    assert capsys.readouterr().err == (
        "Unsupported locale: fr-FR\nSupported locales: zh-CN, en-US\n"
    )


def test_main_validates_catalogs_before_remaining_settings(monkeypatch) -> None:
    events: list[str] = []
    monkeypatch.setattr(main, "load_environment", lambda: events.append("dotenv"))
    monkeypatch.setattr(
        main,
        "resolve_locale",
        lambda *_args, **_kwargs: events.append("locale") or SupportedLocale.ZH_CN,
    )
    monkeypatch.setattr(
        main,
        "validate_localization_catalogs",
        lambda: events.append("catalogs"),
    )
    monkeypatch.setattr(
        main,
        "load_spotify_settings",
        lambda: events.append("settings")
        or (_ for _ in ()).throw(RuntimeError("stop")),
    )
    with pytest.raises(RuntimeError, match="stop"):
        main.main(())
    assert events == ["dotenv", "locale", "catalogs", "settings"]


def test_programmatic_main_does_not_consume_global_argv(monkeypatch) -> None:
    observed: list[tuple[str, ...]] = []
    monkeypatch.setattr(main, "load_environment", lambda: None)
    monkeypatch.setattr(
        main,
        "resolve_locale",
        lambda argv, *_args, **_kwargs: observed.append(tuple(argv))
        or SupportedLocale.ZH_CN,
    )
    monkeypatch.setattr(
        main,
        "validate_localization_catalogs",
        lambda: (_ for _ in ()).throw(RuntimeError("stop")),
    )
    monkeypatch.setattr(main.sys, "argv", ["pytest", "--unrelated"])
    with pytest.raises(RuntimeError, match="stop"):
        main.main()
    assert observed == [()]
