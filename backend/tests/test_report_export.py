"""Tests for artifact helpers and report export."""

from __future__ import annotations

import asyncio
import io
import zipfile
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.services.artifact_service import (
    artifact_basename,
    list_artifact_files,
    resolve_artifact_path,
)
from app.services.report_export_service import ReportExportService, _pdf_safe


def test_artifact_basename_extracts_filename():
    assert artifact_basename("/tmp/artifacts/exec-id/step_01_login.png") == "step_01_login.png"
    assert artifact_basename("step_02_foo.png") == "step_02_foo.png"
    assert artifact_basename(None) is None


def test_resolve_artifact_path_rejects_traversal(tmp_path, monkeypatch):
    execution_id = uuid4()
    artifacts_root = tmp_path / "artifacts"
    exec_dir = artifacts_root / str(execution_id)
    exec_dir.mkdir(parents=True)
    (exec_dir / "ok.png").write_bytes(b"png")

    monkeypatch.setattr(
        "app.services.artifact_service.get_settings",
        lambda: SimpleNamespace(artifacts_dir=artifacts_root),
    )

    path = resolve_artifact_path(execution_id, "ok.png")
    assert path.name == "ok.png"

    with pytest.raises(NotFoundError):
        resolve_artifact_path(execution_id, "../secrets.txt")

    with pytest.raises(NotFoundError):
        resolve_artifact_path(execution_id, "missing.png")


def test_list_artifact_files_sorted(tmp_path, monkeypatch):
    execution_id = uuid4()
    artifacts_root = tmp_path / "artifacts"
    exec_dir = artifacts_root / str(execution_id)
    exec_dir.mkdir(parents=True)
    (exec_dir / "b.png").write_bytes(b"1")
    (exec_dir / "a.png").write_bytes(b"2")
    (exec_dir / "notes.txt").write_text("skip")

    monkeypatch.setattr(
        "app.services.artifact_service.get_settings",
        lambda: SimpleNamespace(artifacts_dir=artifacts_root),
    )

    assert list_artifact_files(execution_id) == ["a.png", "b.png"]


def _png_bytes() -> bytes:
    # Minimal valid 1x1 PNG
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c6300010000050001b8b82f0a0000000049454e44ae426082"
    )


def test_build_zip_contains_summary_and_screenshots(tmp_path, monkeypatch):
    execution_id = uuid4()
    report_id = uuid4()
    artifacts_root = tmp_path / "artifacts"
    exec_dir = artifacts_root / str(execution_id)
    exec_dir.mkdir(parents=True)
    (exec_dir / "step_01_login.png").write_bytes(_png_bytes())

    monkeypatch.setattr(
        "app.services.artifact_service.get_settings",
        lambda: SimpleNamespace(artifacts_dir=artifacts_root),
    )

    report = SimpleNamespace(
        id=report_id,
        execution_id=execution_id,
        summary="Test passed",
        passed_count=1,
        failed_count=0,
        llm_analysis="All good",
        created_at=datetime.now(UTC),
    )
    step = SimpleNamespace(
        seq=1,
        name="Login",
        action="login",
        status="passed",
        error=None,
        screenshot_path="step_01_login.png",
    )
    execution = SimpleNamespace(steps=[step])

    service = ReportExportService(db=AsyncMock())
    service._load_report_context = AsyncMock(return_value=(report, execution))

    content, filename = asyncio.run(service.build_zip(report_id))
    assert filename.endswith(".zip")

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        names = zf.namelist()
        assert "report_summary.txt" in names
        assert "report.json" in names
        assert "screenshots/step_01_login.png" in names
        assert "Test passed" in zf.read("report_summary.txt").decode()


def test_pdf_safe_replaces_unicode():
    assert "?" in _pdf_safe("hello — world") or "-" in _pdf_safe("hello — world")
    assert _pdf_safe(None) == ""
    assert _pdf_safe("") == ""


def test_build_pdf_handles_unicode_summary(tmp_path, monkeypatch):
    execution_id = uuid4()
    report_id = uuid4()
    artifacts_root = tmp_path / "artifacts"
    exec_dir = artifacts_root / str(execution_id)
    exec_dir.mkdir(parents=True)
    (exec_dir / "step_01_login.png").write_bytes(_png_bytes())

    monkeypatch.setattr(
        "app.services.artifact_service.get_settings",
        lambda: SimpleNamespace(artifacts_dir=artifacts_root),
    )

    report = SimpleNamespace(
        id=report_id,
        execution_id=execution_id,
        summary="Summary with unicode — dash and “quotes”",
        passed_count=1,
        failed_count=0,
        llm_analysis=None,
        created_at=datetime.now(UTC),
    )
    step = SimpleNamespace(
        seq=1,
        name="Login",
        action="login",
        status="passed",
        error=None,
        screenshot_path="step_01_login.png",
    )
    execution = SimpleNamespace(steps=[step])

    service = ReportExportService(db=AsyncMock())
    service._load_report_context = AsyncMock(return_value=(report, execution))

    content, filename = asyncio.run(service.build_pdf(report_id))
    assert filename.endswith(".pdf")
    assert content[:4] == b"%PDF"
