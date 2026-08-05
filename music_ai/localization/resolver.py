"""Resolve one supported locale from explicit runtime configuration."""

from argparse import ArgumentParser
from collections.abc import Callable, Mapping, Sequence

from music_ai.localization.models import (
    SupportedLocale,
    parse_supported_locale,
)


_INTERACTIVE_PROMPT = """请选择报告语言 / Choose report language:

1. 中文
2. English

请输入 1 或 2，直接回车默认中文："""
_INTERACTIVE_RETRY = "请输入 1 或 2 / Please enter 1 or 2."
_CLI_LOCALE_HELP = "报告语言 / Report language: zh-CN or en-US"


def resolve_locale(
    argv: Sequence[str],
    environment: Mapping[str, str],
    *,
    is_tty: bool,
    read_input: Callable[[], str],
    write_output: Callable[[str], None],
) -> SupportedLocale:
    """Resolve CLI, environment, interactive, then non-interactive locale."""
    cli_value = _parse_cli_locale(argv)
    if cli_value is not None:
        return parse_supported_locale(cli_value)

    if "MUSICMIND_LOCALE" in environment:
        return parse_supported_locale(environment["MUSICMIND_LOCALE"])

    if not is_tty:
        return SupportedLocale.ZH_CN

    write_output(_INTERACTIVE_PROMPT)
    while True:
        try:
            selection = read_input().strip()
        except EOFError:
            return SupportedLocale.ZH_CN
        if selection in {"", "1"}:
            return SupportedLocale.ZH_CN
        if selection == "2":
            return SupportedLocale.EN_US
        write_output(_INTERACTIVE_RETRY)


def _parse_cli_locale(argv: Sequence[str]) -> str | None:
    parser = ArgumentParser(description="MusicMind")
    parser.add_argument(
        "--locale",
        help=_CLI_LOCALE_HELP,
    )
    return parser.parse_args(list(argv)).locale
