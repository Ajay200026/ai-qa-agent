"""Local OAuth redirect listener on port 1717 (same as Salesforce CLI)."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import parse_qs, urlencode, urlparse

logger = logging.getLogger(__name__)

SF_CLI_OAUTH_PORT = 1717
SF_CLI_REDIRECT_PATH = "/OauthRedirect"
_FRONTEND_CALLBACK_PATH = "/salesforce-orgs/oauth/callback"


class SalesforceOAuthRedirectServer:
    def __init__(self) -> None:
        self._server: asyncio.Server | None = None
        self._frontend_origin = "http://localhost:3000"

    def configure(self, *, frontend_origin: str) -> None:
        self._frontend_origin = frontend_origin.rstrip("/")

    async def start(self) -> None:
        if self._server is not None:
            return
        try:
            self._server = await asyncio.start_server(
                self._handle_connection,
                host="127.0.0.1",
                port=SF_CLI_OAUTH_PORT,
            )
            logger.info("Salesforce OAuth redirect server listening on 127.0.0.1:%s", SF_CLI_OAUTH_PORT)
        except OSError as exc:
            raise RuntimeError(
                f"Port {SF_CLI_OAUTH_PORT} is in use (another SF CLI login may be running). "
                "Stop it or set SALESFORCE_OAUTH_REDIRECT_URI to your own Connected App callback."
            ) from exc

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    def _frontend_callback_url(self, *, code: str, state: str, error: str) -> str:
        params: dict[str, str] = {}
        if error:
            params["error"] = error
        if code:
            params["code"] = code
        if state:
            params["state"] = state
        query = urlencode(params)
        base = f"{self._frontend_origin}{_FRONTEND_CALLBACK_PATH}"
        return f"{base}?{query}" if query else base

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            request_line = (await reader.readline()).decode("utf-8", errors="replace").strip()
            if not request_line:
                return

            parts = request_line.split()
            if len(parts) < 2 or parts[0] != "GET":
                await self._send_text_response(writer, 405, "Method not allowed")
                return

            parsed = urlparse(parts[1])
            if parsed.path != SF_CLI_REDIRECT_PATH:
                await self._send_text_response(writer, 404, "Not found")
                return

            # Drain remaining headers
            while True:
                line = await reader.readline()
                if line in (b"\r\n", b"\n", b""):
                    break

            query = parse_qs(parsed.query)
            code = (query.get("code") or [""])[0]
            state = (query.get("state") or [""])[0]
            error = (query.get("error") or [""])[0]
            location = self._frontend_callback_url(code=code, state=state, error=error)
            await self._send_redirect(writer, location)
        except Exception:
            logger.exception("oauth_redirect.handle_failed")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _send_redirect(self, writer: asyncio.StreamWriter, location: str) -> None:
        body = f"Redirecting to {location}"
        encoded = body.encode("utf-8")
        headers = (
            "HTTP/1.1 302 Found\r\n"
            f"Location: {location}\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            f"Content-Length: {len(encoded)}\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        writer.write(headers.encode("utf-8") + encoded)
        await writer.drain()

    async def _send_text_response(
        self,
        writer: asyncio.StreamWriter,
        status: int,
        body: str,
    ) -> None:
        reason = {200: "OK", 404: "Not Found", 405: "Method Not Allowed"}.get(status, "OK")
        encoded = body.encode("utf-8")
        headers = (
            f"HTTP/1.1 {status} {reason}\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            f"Content-Length: {len(encoded)}\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        writer.write(headers.encode("utf-8") + encoded)
        await writer.drain()


oauth_redirect_server = SalesforceOAuthRedirectServer()
