from io import BytesIO
from urllib.parse import urlencode

import pytest

import music_ai.spotify.auth as auth_module
from music_ai.spotify.auth import OAuthUserMessages, _CallbackServer


_ZH_MESSAGES = OAuthUserMessages(
    open_url="请在浏览器中打开以下网址以登录 Spotify：",
    unknown_callback_path="未知的回调路径。",
    authorization_failed="Spotify 授权失败：{error}",
    invalid_state="授权状态无效。",
    missing_code="缺少授权代码。",
    success="Spotify 登录已完成。你可以返回终端。",
)


def _run_callback_request(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    messages: OAuthUserMessages,
) -> tuple[int, str, str, str | None, BaseException | None]:
    response_values: dict[str, object] = {}

    class FakeHTTPServer:
        def __init__(self, address, handler_class) -> None:
            response_values["address"] = address
            self._handler_class = handler_class
            self.timeout: int | None = None

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def handle_request(self) -> None:
            handler = object.__new__(self._handler_class)
            handler.path = path
            handler.wfile = BytesIO()
            handler.send_response = lambda status: response_values.update(
                status=status
            )
            handler.send_header = lambda name, value: response_values.update(
                {name: value}
            )
            handler.end_headers = lambda: None
            handler.do_GET()
            response_values["body"] = handler.wfile.getvalue()

    monkeypatch.setattr(auth_module, "HTTPServer", FakeHTTPServer)
    server = _CallbackServer(
        "http://127.0.0.1:8765/callback",
        expected_state="expected-state",
        messages=messages,
    )
    code: str | None = None
    error: BaseException | None = None
    try:
        code = server.wait_for_authorization_code()
    except Exception as caught:
        error = caught
    return (
        int(response_values["status"]),
        str(response_values["Content-Type"]),
        bytes(response_values["body"]).decode("utf-8"),
        code,
        error,
    )


@pytest.mark.parametrize(
    ("messages", "path", "expected"),
    [
        (
            _ZH_MESSAGES,
            "/callback?code=code&state=wrong-state",
            "授权状态无效。",
        ),
        (_ZH_MESSAGES, "/callback?state=expected-state", "缺少授权代码。"),
        (
            OAuthUserMessages(),
            "/callback?code=code&state=wrong-state",
            "Invalid authorization state.",
        ),
        (
            OAuthUserMessages(),
            "/callback?state=expected-state",
            "Missing authorization code.",
        ),
    ],
)
def test_callback_validation_raises_the_same_localized_message_shown_in_browser(
    monkeypatch: pytest.MonkeyPatch,
    messages: OAuthUserMessages,
    path: str,
    expected: str,
) -> None:
    status, content_type, body, code, error = _run_callback_request(
        monkeypatch,
        path,
        messages,
    )

    assert status == 400
    assert content_type == "text/html; charset=utf-8"
    assert expected in body
    assert code is None
    assert isinstance(error, RuntimeError)
    assert str(error) == expected


def test_callback_query_error_is_localized_and_html_escaped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_error = "<script>alert(1)</script>"
    query = urlencode({"error": raw_error, "state": "expected-state"})

    status, content_type, body, code, error = _run_callback_request(
        monkeypatch,
        f"/callback?{query}",
        _ZH_MESSAGES,
    )

    assert status == 400
    assert content_type == "text/html; charset=utf-8"
    assert "Spotify 授权失败：&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert raw_error not in body
    assert code is None
    assert isinstance(error, RuntimeError)
    assert str(error) == f"Spotify 授权失败：{raw_error}"


@pytest.mark.parametrize("messages", [OAuthUserMessages(), _ZH_MESSAGES])
def test_successful_callback_preserves_code_and_readable_localized_html(
    monkeypatch: pytest.MonkeyPatch,
    messages: OAuthUserMessages,
) -> None:
    status, content_type, body, code, error = _run_callback_request(
        monkeypatch,
        "/callback?code=authorization-code&state=expected-state",
        messages,
    )

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert messages.success in body
    assert code == "authorization-code"
    assert error is None
