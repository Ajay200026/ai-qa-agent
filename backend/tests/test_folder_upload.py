"""Tests for batched folder upload and upload normalizer."""

from pathlib import Path
from uuid import uuid4

from app.knowledge_engine.upload_normalizer import normalize_salesforce_upload
from app.services.upload_session import create_session, get_session, pop_session


SAMPLE_APEX = "public class Foo {}"


def test_normalize_preserves_full_sfdx_tree(tmp_path: Path):
    base = tmp_path / "force-app" / "main" / "default"
    cls = base / "classes"
    cls.mkdir(parents=True)
    (cls / "AccountController.cls").write_text(SAMPLE_APEX)
    lwc = base / "lwc" / "customerSearch"
    lwc.mkdir(parents=True)
    (lwc / "customerSearch.js").write_text("export default class {}")
    (lwc / "customerSearch.html").write_text("<template></template>")

    root = normalize_salesforce_upload(tmp_path, preserve_existing=True)
    assert (root / "force-app" / "main" / "default" / "classes" / "AccountController.cls").is_file()
    assert (root / "force-app" / "main" / "default" / "lwc" / "customerSearch" / "customerSearch.js").is_file()


def test_normalize_wraps_main_default(tmp_path: Path):
    default = tmp_path / "main" / "default" / "classes"
    default.mkdir(parents=True)
    (default / "Bar.cls").write_text(SAMPLE_APEX)

    root = normalize_salesforce_upload(tmp_path, preserve_existing=True)
    assert (root / "force-app" / "main" / "default" / "classes" / "Bar.cls").is_file()


def test_normalize_partial_lwc_still_relocates(tmp_path: Path):
    bundle = tmp_path / "myComponent"
    bundle.mkdir()
    (bundle / "myComponent.js").write_text("export default class {}")
    (bundle / "myComponent.html").write_text("<template></template>")
    (bundle / "myComponent.js-meta.xml").write_text("<LightningComponentBundle/>")

    root = normalize_salesforce_upload(tmp_path)
    assert (root / "force-app" / "main" / "default" / "lwc" / "myComponent" / "myComponent.js").is_file()


def test_upload_session_lifecycle(tmp_path: Path):
    repo_id = uuid4()
    owner_id = uuid4()
    workspace = tmp_path / str(repo_id)
    workspace.mkdir()
    session = create_session(repo_id, workspace, "Test Project", owner_id)
    assert get_session(session.session_id) is session
    popped = pop_session(session.session_id)
    assert popped is session
    assert get_session(session.session_id) is None
