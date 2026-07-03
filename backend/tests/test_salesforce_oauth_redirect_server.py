import asyncio
from urllib.parse import parse_qs, urlparse

from app.services.salesforce_oauth_redirect import (
    SF_CLI_OAUTH_PORT,
    SF_CLI_REDIRECT_PATH,
    oauth_redirect_server,
)


async def _run_redirect_test() -> None:
    oauth_redirect_server.configure(frontend_origin="http://localhost:3000")
    await oauth_redirect_server.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", SF_CLI_OAUTH_PORT)
        request = (
            f"GET {SF_CLI_REDIRECT_PATH}?code=test-code&state=test-state HTTP/1.1\r\n"
            "Host: localhost:1717\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        writer.write(request.encode())
        await writer.drain()
        writer.write_eof()

        response = await reader.read(4096)
        text = response.decode("utf-8", errors="replace")
        assert "302 Found" in text
        assert "Location: http://localhost:3000/salesforce-orgs/oauth/callback" in text

        location_line = next(line for line in text.split("\r\n") if line.startswith("Location: "))
        location = location_line.split("Location: ", 1)[1]
        query = parse_qs(urlparse(location).query)
        assert query["code"] == ["test-code"]
        assert query["state"] == ["test-state"]
    finally:
        await oauth_redirect_server.stop()


def test_oauth_redirect_server_returns_302_to_frontend():
    asyncio.run(_run_redirect_test())
