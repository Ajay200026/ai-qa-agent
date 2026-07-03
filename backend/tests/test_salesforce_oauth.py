from app.services.salesforce_oauth import (
    SF_CLI_CLIENT_ID,
    SF_CLI_REDIRECT_URI,
    _oauth_settings,
    uses_sf_cli_redirect,
)


def test_oauth_defaults_match_sf_cli():
    client_id, client_secret, redirect_uri = _oauth_settings()
    assert client_id == SF_CLI_CLIENT_ID
    assert client_secret == ""
    assert redirect_uri == SF_CLI_REDIRECT_URI
    assert uses_sf_cli_redirect(redirect_uri)


def test_public_client_omits_secret_from_token_request():
    from app.services.salesforce_oauth import _token_request_data

    data = _token_request_data(
        client_id=SF_CLI_CLIENT_ID,
        client_secret="",
        grant_type="authorization_code",
        code="abc",
        redirect_uri=SF_CLI_REDIRECT_URI,
        code_verifier="verifier",
    )
    assert "client_secret" not in data
    assert data["code_verifier"] == "verifier"


def test_confidential_client_includes_secret():
    from app.services.salesforce_oauth import _token_request_data

    data = _token_request_data(
        client_id="custom-app-id",
        client_secret="super-secret",
        grant_type="refresh_token",
        refresh_token="rt",
    )
    assert data["client_secret"] == "super-secret"


def test_redirect_session_roundtrip():
    from app.services.salesforce_oauth import (
        consume_authorize_redirect_session,
        create_authorize_redirect_session,
    )

    url = "https://test.salesforce.com/services/oauth2/authorize?client_id=PlatformCLI"
    session_id = create_authorize_redirect_session(url)
    assert consume_authorize_redirect_session(session_id) == url


def test_start_oauth_flow_builds_authorize_url(monkeypatch):
    import asyncio
    from uuid import uuid4

    from app.services import salesforce_oauth as oauth_mod

    async def noop() -> None:
        return None

    monkeypatch.setattr(oauth_mod, "ensure_oauth_redirect_server", noop)

    url, state, redirect_session = asyncio.run(
        oauth_mod.start_oauth_flow(
            project_id=uuid4(),
            name="UAT",
            org_type="sandbox",
        )
    )
    assert state
    assert redirect_session
    assert SF_CLI_CLIENT_ID in url
    assert "test.salesforce.com/services/oauth2/authorize" in url
    assert "code_challenge=" in url
    assert "scope=refresh_token+api+web" in url or "scope=refresh_token%20api%20web" in url
