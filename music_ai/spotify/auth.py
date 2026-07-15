from dataclasses import dataclass
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
DEFAULT_SCOPES = ("user-read-private",)


@dataclass(frozen=True)
class SpotifyToken:
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str | None = None
    scope: str | None = None


class SpotifyAuth:
    def __init__(self, settings: SpotifySettings, scopes: tuple[str, ...] = DEFAULT_SCOPES):
        self._settings = settings
        self._scopes = scopes

    def authenticate(self) -> SpotifyToken:
        state = token_urlsafe(32)
        callback_server = _CallbackServer(self._settings.redirect_uri, expected_state=state)
        authorization_url = self._build_authorization_url(state)

        print("Open this URL in your browser to authenticate with Spotify:")
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
    def __init__(self, redirect_uri: str, expected_state: str):
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

    def wait_for_authorization_code(self) -> str:
        callback_result: dict[str, str] = {}
        expected_path = self._path
        expected_state = self._expected_state

        class SpotifyCallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed_request = urlparse(self.path)
                query_params = parse_qs(parsed_request.query)

                if parsed_request.path != expected_path:
                    self._send_response(404, "Unknown callback path.")
                    return

                error = _first_value(query_params, "error")
                if error:
                    callback_result["error"] = error
                    self._send_response(400, f"Spotify authorization failed: {error}")
                    return

                state = _first_value(query_params, "state")
                if state != expected_state:
                    callback_result["error"] = "Invalid authorization state."
                    self._send_response(400, "Invalid authorization state.")
                    return

                code = _first_value(query_params, "code")
                if not code:
                    callback_result["error"] = "Missing authorization code."
                    self._send_response(400, "Missing authorization code.")
                    return

                callback_result["code"] = code
                self._send_response(
                    200,
                    "Spotify authentication received. You can return to the terminal.",
                )

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _send_response(self, status_code: int, message: str) -> None:
                body = f"<html><body><p>{message}</p></body></html>".encode("utf-8")
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
