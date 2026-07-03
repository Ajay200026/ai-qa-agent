from urllib.parse import parse_qs, urlparse

from app.services.salesforce_oauth_redirect import (
    SF_CLI_REDIRECT_PATH,
    SalesforceOAuthRedirectServer,
)


def test_frontend_callback_url_includes_code_and_state():
    server = SalesforceOAuthRedirectServer()
    server.configure(frontend_origin="http://localhost:3000")
    url = server._frontend_callback_url(code="auth-code", state="state-123", error="")
    parsed = urlparse(url)
    assert parsed.path == "/salesforce-orgs/oauth/callback"
    query = parse_qs(parsed.query)
    assert query["code"] == ["auth-code"]
    assert query["state"] == ["state-123"]
    assert "error" not in query


def test_frontend_callback_url_includes_error():
    server = SalesforceOAuthRedirectServer()
    server.configure(frontend_origin="http://localhost:3000")
    url = server._frontend_callback_url(code="", state="", error="access_denied")
    query = parse_qs(urlparse(url).query)
    assert query["error"] == ["access_denied"]


def test_sf_cli_redirect_path_matches_cli():
    assert SF_CLI_REDIRECT_PATH == "/OauthRedirect"
