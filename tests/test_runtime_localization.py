from datetime import datetime, timezone

import main
import music_ai.spotify.auth as auth_module
from config import SpotifySettings
from music_ai.localization import SupportedLocale
from music_ai.spotify.auth import SpotifyAuth, SpotifyToken


class FakeClient:
    def __init__(self, tracks: list[dict[str, object]]) -> None:
        self._tracks = tracks
        self.calls: list[dict[str, int]] = []

    def recent_tracks(self, **values):
        self.calls.append(values)
        return self._tracks


def test_download_runtime_messages_follow_resolved_locale(capsys) -> None:
    first_client = FakeClient([])
    main._download_recent_tracks(
        first_client,
        None,
        locale=SupportedLocale.ZH_CN,
    )
    assert capsys.readouterr().out == "首次同步。\n正在下载最近播放记录……\n"

    current_client = FakeClient([{}])
    latest = datetime(2026, 8, 5, 8, tzinfo=timezone.utc)
    main._download_recent_tracks(
        current_client,
        latest,
        locale=SupportedLocale.EN_US,
    )
    assert capsys.readouterr().out == (
        "Last synchronized playback:\n"
        "2026-08-05T08:00:00+00:00\n"
        "Checking Spotify...\n"
        "Found 1 new playback records.\n"
    )


def test_ai_report_runtime_label_is_localized(capsys) -> None:
    main._print_ai_report("报告正文", locale=SupportedLocale.ZH_CN)
    output = capsys.readouterr().out
    assert "MusicMind AI" in output
    assert "报告正文" in output


def test_ai_no_signal_and_generation_failure_are_distinct_localized_states() -> None:
    from music_ai.localization.catalog import ui_text
    from music_ai.localization.models import UiMessageKey

    expected = {
        SupportedLocale.EN_US: (
            "There are no new listening changes worth a separate interpretation today."
        ),
        SupportedLocale.ZH_CN: "今天还没有出现值得单独解读的新变化。",
    }
    prohibited = {
        SupportedLocale.EN_US: ("signal", "qualified", "threshold", "eligible"),
        SupportedLocale.ZH_CN: ("信号", "呈现条件", "达到"),
    }
    for locale in SupportedLocale:
        no_signal = ui_text(locale, UiMessageKey.AI_NO_SIGNAL)
        failure = ui_text(locale, UiMessageKey.AI_GENERATION_FAILURE)
        assert no_signal == expected[locale]
        assert failure
        assert no_signal != failure
        assert all(term not in no_signal.lower() for term in prohibited[locale])


def test_spotify_auth_receives_prelocalized_copy_without_resolving_locale(
    monkeypatch, capsys
) -> None:
    captured: list[object] = []

    class FakeCallbackServer:
        def __init__(self, redirect_uri, expected_state, messages):
            captured.extend((redirect_uri, expected_state, messages))

        def wait_for_authorization_code(self):
            return "code"

    monkeypatch.setattr(auth_module, "_CallbackServer", FakeCallbackServer)
    monkeypatch.setattr(auth_module.webbrowser, "open", lambda url: captured.append(url))
    monkeypatch.setattr(
        SpotifyAuth,
        "_exchange_code_for_token",
        lambda self, code: SpotifyToken("token", "Bearer", 3600),
    )
    messages = main._oauth_user_messages(SupportedLocale.ZH_CN)
    spotify_auth = SpotifyAuth(
        SpotifySettings(
            "client",
            "secret",
            "http://127.0.0.1:8888/callback",
        ),
        messages=messages,
    )

    token = spotify_auth.authenticate()

    assert token.access_token == "token"
    assert captured[2] is messages
    assert "请在浏览器中打开以下网址以登录 Spotify：" in capsys.readouterr().out
    assert "resolve_locale" not in auth_module.__dict__
