from dataclasses import dataclass
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
from secrets import token_urlsafe
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
import webbrowser

import requests
from requests.auth import HTTPBasicAuth

from config import SpotifySettings


AUTHORIZATION_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
DEFAULT_SCOPES = (
    "user-read-private",
    "user-library-read",
    "user-read-recently-played",
)


@dataclass(frozen=True)
class SpotifyToken:
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str | None = None
    scope: str | None = None


@dataclass(frozen=True)
class OAuthUserMessages:
    """Prelocalized user copy injected without making OAuth locale-aware."""

    open_url: str = "Open this URL in your browser to authenticate with Spotify:"
    unknown_callback_path: str = "Unknown callback path."
    authorization_failed: str = "Spotify authorization failed: {error}"
    invalid_state: str = "Invalid authorization state."
    missing_code: str = "Missing authorization code."
    success: str = "Spotify authentication received. You can return to the terminal."


class SpotifyAuth:
    """Handles Spotify OAuth authorization and token exchange."""

    def __init__(
        self,
        settings: SpotifySettings,
        scopes: tuple[str, ...] = DEFAULT_SCOPES,
        messages: OAuthUserMessages = OAuthUserMessages(),
    ) -> None:
        self._settings = settings
        self._scopes = scopes
        self._messages = messages

    def authenticate(self) -> SpotifyToken:
        """Run the browser-based OAuth flow and return a Spotify access token."""
        state = token_urlsafe(32)
        callback_server = _CallbackServer(
            self._settings.redirect_uri,
            expected_state=state,
            messages=self._messages,
        )
        authorization_url = self._build_authorization_url(state)

        print(self._messages.open_url)
        print(authorization_url)
        webbrowser.open(authorization_url)

        authorization_code = callback_server.wait_for_authorization_code()
        return self._exchange_code_for_token(authorization_code)

    def _build_authorization_url(self, state: str) -> str:
        query_params = {
            "response_type": "code",
            "client_id": self._settings.client_id,
            "scope": " ".join(self._scopes),
            "redirect_uri": self._settings.redirect_uri,
            "state": state,
        }
        return f"{AUTHORIZATION_URL}?{urlencode(query_params)}"

    def _exchange_code_for_token(self, authorization_code: str) -> SpotifyToken:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": authorization_code,
                "redirect_uri": self._settings.redirect_uri,
            },
            auth=HTTPBasicAuth(self._settings.client_id, self._settings.client_secret),
            timeout=20,
        )
        response.raise_for_status()
        token_data = response.json()

        return SpotifyToken(
            access_token=token_data["access_token"],
            token_type=token_data["token_type"],
            expires_in=token_data["expires_in"],
            refresh_token=token_data.get("refresh_token"),
            scope=token_data.get("scope"),
        )


class _CallbackServer:
    def __init__(
        self,
        redirect_uri: str,
        expected_state: str,
        messages: OAuthUserMessages = OAuthUserMessages(),
    ) -> None:
        parsed_uri = urlparse(redirect_uri)

        if parsed_uri.scheme != "http":
            raise ValueError("SPOTIPY_REDIRECT_URI must use http for the local callback server.")
        if parsed_uri.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError(
                "SPOTIPY_REDIRECT_URI must point to localhost or 127.0.0.1 for this app."
            )

        self._host = parsed_uri.hostname
        self._port = parsed_uri.port or 80
        self._path = parsed_uri.path or "/"
        self._expected_state = expected_state
        self._messages = messages

    def wait_for_authorization_code(self) -> str:
        callback_result: dict[str, str] = {}
        expected_path = self._path
        expected_state = self._expected_state
        messages = self._messages

        class SpotifyCallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed_request = urlparse(self.path)
                query_params = parse_qs(parsed_request.query)

                if parsed_request.path != expected_path:
                    self._send_response(404, messages.unknown_callback_path)
                    return

                error = _first_value(query_params, "error")
                if error:
                    localized_error = messages.authorization_failed.format(error=error)
                    callback_result["error"] = localized_error
                    self._send_response(
                        400,
                        localized_error,
                    )
                    return

                state = _first_value(query_params, "state")
                if state != expected_state:
                    callback_result["error"] = messages.invalid_state
                    self._send_response(400, messages.invalid_state)
                    return

                code = _first_value(query_params, "code")
                if not code:
                    callback_result["error"] = messages.missing_code
                    self._send_response(400, messages.missing_code)
                    return

                callback_result["code"] = code
                self._send_response(
                    200,
                    messages.success,
                )

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _send_response(self, status_code: int, message: str) -> None:
                body = (
                    f"<html><body><p>{html.escape(message)}</p></body></html>"
                ).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        with HTTPServer((self._host, self._port), SpotifyCallbackHandler) as server:
            server.timeout = 300
            server.handle_request()

        if "code" in callback_result:
            return callback_result["code"]

        if "error" in callback_result:
            raise RuntimeError(callback_result["error"])

        raise TimeoutError("Timed out waiting for Spotify authorization callback.")


def _first_value(query_params: dict[str, list[str]], key: str) -> str | None:
    values = query_params.get(key)
    return values[0] if values else None
