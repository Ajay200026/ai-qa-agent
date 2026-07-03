from app.automation.playwright_paths import resolve_playwright_browsers_path


def test_ignores_cursor_sandbox_path(monkeypatch, tmp_path):
    sandbox = "/tmp/cursor-sandbox-cache/fake/playwright"
    real = tmp_path / "ms-playwright"
    (real / "chromium-1223").mkdir(parents=True)

    monkeypatch.setattr(
        "app.automation.playwright_paths._default_browser_paths",
        lambda: [real],
    )
    resolved = resolve_playwright_browsers_path(sandbox)
    assert resolved == str(real)


def test_prefers_valid_configured_path(monkeypatch, tmp_path):
    configured = tmp_path / "custom-browsers"
    (configured / "chromium-1200").mkdir(parents=True)

    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    resolved = resolve_playwright_browsers_path(str(configured))
    assert resolved == str(configured)
