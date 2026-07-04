"""Tests for Salesforce knowledge engine extractors and scanner."""

from pathlib import Path

from app.knowledge_engine.extractors.apex_extractor import extract_apex
from app.knowledge_engine.extractors.lwc_extractor import extract_lwc
from app.knowledge_engine.extractors.router import extract_file
from app.knowledge_engine.scanner.repo_scanner import (
    _module_matches,
    discover_modules,
    enumerate_all_files,
    filter_module_files,
    list_repo_children,
    normalize_scope_path,
    preflight_scope_files,
    summarize_folder,
)
from app.knowledge_engine.types import SalesforceFileType, ScannedFile


SAMPLE_APEX = """
public with sharing class CustomerController {
    public List<Account> getAccounts() {
        return [SELECT Id, Name, Finance_Type__c FROM Account WHERE Active__c = true];
    }

    public void saveAccount(Account acc) {
        AccountService.validate(acc);
        update acc;
    }
}
"""


def test_extract_apex_class():
    result = extract_apex(SAMPLE_APEX, "force-app/main/default/classes/CustomerController.cls")
    assert result.name == "CustomerController"
    assert result.entity_type == "ApexClass"
    assert "Account" in result.data["soql_objects"]
    assert "Finance_Type__c" in result.data["fields_read"]
    assert "AccountService" in result.data["called_classes"]
    assert any(m["name"] == "getAccounts" for m in result.data["methods"])


def test_discover_modules_on_fixture(tmp_path: Path):
    base = tmp_path / "force-app" / "main" / "default"
    lwc = base / "lwc" / "customerDetails"
    lwc.mkdir(parents=True)
    (lwc / "customerDetails.html").write_text("<template></template>")
    (lwc / "customerDetails.js").write_text("export default class {}")
    cls = base / "classes"
    cls.mkdir(parents=True)
    (cls / "CustomerController.cls").write_text(SAMPLE_APEX)

    all_files = enumerate_all_files(tmp_path)
    assert len(all_files) >= 2
    modules = discover_modules(tmp_path)
    names = [m["name"] for m in modules]
    names_lower = [n.lower() for n in names]
    assert any("customerdetails" in n or "customercontroller" in n for n in names_lower)

    filtered = filter_module_files(all_files, "customerDetails")
    assert len(filtered) >= 1


def _build_fixture_repo(tmp_path: Path) -> Path:
    base = tmp_path / "force-app" / "main" / "default"
    for name in ("customerDetails", "customerList"):
        lwc = base / "lwc" / name
        lwc.mkdir(parents=True)
        (lwc / f"{name}.html").write_text("<template></template>")
        (lwc / f"{name}.js").write_text("export default class {}")
    cls = base / "classes"
    cls.mkdir(parents=True)
    (cls / "CustomerController.cls").write_text(SAMPLE_APEX)
    return tmp_path


def test_list_repo_children_at_package_root(tmp_path: Path):
    repo = _build_fixture_repo(tmp_path)
    roots = list_repo_children(repo, "")
    paths = [str(e["path"]) for e in roots]
    assert "force-app/main/default" in paths


def test_list_repo_children_under_lwc(tmp_path: Path):
    repo = _build_fixture_repo(tmp_path)
    children = list_repo_children(repo, "force-app/main/default/lwc")
    names = {str(e["name"]) for e in children}
    assert names == {"customerDetails", "customerList"}


def test_list_repo_children_leaf_lwc_bundle(tmp_path: Path):
    repo = _build_fixture_repo(tmp_path)
    bundle_path = "force-app/main/default/lwc/customerDetails"
    children = list_repo_children(repo, bundle_path)
    assert len(children) == 1
    entry = children[0]
    assert entry["path"] == bundle_path
    assert entry.get("is_selectable") is True
    assert entry.get("is_current") is True
    assert entry["file_count"] >= 2


def test_summarize_folder_counts_lwc(tmp_path: Path):
    repo = _build_fixture_repo(tmp_path)
    breakdown = summarize_folder(repo, "force-app/main/default/lwc")
    assert breakdown.get("lwc", 0) >= 4


def test_filter_module_files_with_scope_path(tmp_path: Path):
    repo = _build_fixture_repo(tmp_path)
    all_files = enumerate_all_files(repo)
    scoped = filter_module_files(
        all_files,
        "ignored",
        scope_path="force-app/main/default/lwc",
        repo_path=repo,
    )
    assert len(scoped) >= 4
    assert all("lwc" in f.relative_path.replace("\\", "/") for f in scoped)


def test_normalize_scope_path_strips_project_prefix(tmp_path: Path):
    repo = _build_fixture_repo(tmp_path)
    scope = "CoreFlex Onboarding/force-app/main/default/lwc"
    assert normalize_scope_path(repo, scope) == "force-app/main/default/lwc"


def test_module_matches_spaced_folder_names():
    path = "force-app/main/default/lwc/Data Change/lwc/foo.js"
    assert _module_matches(path, "Data Change")
    assert _module_matches(path, "data change")


def test_preflight_scope_files_with_legacy_prefix(tmp_path: Path):
    repo = _build_fixture_repo(tmp_path)
    feature = repo / "force-app" / "main" / "default" / "lwc" / "Data Change"
    feature.mkdir(parents=True)
    bundle = feature / "lwc" / "myComponent"
    bundle.mkdir(parents=True)
    (bundle / "myComponent.html").write_text("<template></template>")
    (bundle / "myComponent.js").write_text("export default class {}")

    legacy_scope = "CoreFlex Onboarding/force-app/main/default/lwc/Data Change"
    matched, repaired = preflight_scope_files(repo, "Data Change", legacy_scope)
    assert repaired == "force-app/main/default/lwc/Data Change"
    assert len(matched) >= 2


def test_preflight_scope_files_empty_scope_fails(tmp_path: Path):
    repo = _build_fixture_repo(tmp_path)
    matched, _ = preflight_scope_files(repo, "missing", "force-app/main/default/nope")
    assert matched == []


def test_nested_clone_layout_scope_matching(tmp_path: Path):
    """Azure clones may nest SFDX under a named folder below the git workspace root."""
    workspace = tmp_path / "azure_clone"
    project = workspace / "CoreFlex Onboarding"
    bundle = (
        project
        / "force-app"
        / "main"
        / "default"
        / "lwc"
        / "Northeast Modules"
        / "lwc"
        / "Data Change"
        / "lwc"
        / "conaDatachangeParent"
    )
    bundle.mkdir(parents=True)
    (bundle / "conaDatachangeParent.js").write_text("export default class {}")
    (bundle / "conaDatachangeParent.html").write_text("<template></template>")
    (bundle / "conaDatachangeParent.js-meta.xml").write_text("<LightningComponentBundle/>")

    scope = (
        "CoreFlex Onboarding/force-app/main/default/lwc/Northeast Modules/lwc/"
        "Data Change/lwc/conaDatachangeParent"
    )
    matched, repaired = preflight_scope_files(workspace, "conaDatachangeParent", scope)
    assert repaired == (
        "force-app/main/default/lwc/Northeast Modules/lwc/Data Change/lwc/conaDatachangeParent"
    )
    assert len(matched) >= 2


def test_find_salesforce_project_root_nested(tmp_path: Path):
    from app.knowledge_engine.repo_path_resolver import find_salesforce_project_root

    workspace = tmp_path / "clone"
    project = workspace / "CoreFlex Onboarding"
    (project / "force-app" / "main" / "default").mkdir(parents=True)
    (project / "sfdx-project.json").write_text('{"packageDirectories":[{"path":"force-app"}]}')

    assert find_salesforce_project_root(workspace) == project.resolve()


def test_lwc_extract_dedupes_bundle(tmp_path: Path):
    bundle = tmp_path / "force-app" / "main" / "default" / "lwc" / "cmp"
    bundle.mkdir(parents=True)
    (bundle / "cmp.html").write_text("<template></template>")
    (bundle / "cmp.js").write_text("export default class {}")

    html_file = ScannedFile(
        path=bundle / "cmp.html",
        relative_path="force-app/main/default/lwc/cmp/cmp.html",
        file_type=SalesforceFileType.LWC,
    )
    js_file = ScannedFile(
        path=bundle / "cmp.js",
        relative_path="force-app/main/default/lwc/cmp/cmp.js",
        file_type=SalesforceFileType.LWC,
    )
    processed: set[str] = set()
    first = extract_file(html_file, processed)
    second = extract_file(js_file, processed)
    assert len(first) == 1
    assert second == []


def test_extract_lwc(tmp_path: Path):
    bundle = tmp_path / "customerDetails"
    bundle.mkdir()
    (bundle / "customerDetails.html").write_text(
        '<template><lightning-input field-name="Finance_Type__c"></lightning-input><c-child-comp></c-child-comp></template>'
    )
    (bundle / "customerDetails.js").write_text(
        """
        import getData from '@salesforce/apex/CustomerController.getAccounts';
        import FINANCE_FIELD from '@salesforce/schema/Account.Finance_Type__c';
        export default class CustomerDetails extends NavigationMixin(LightningElement) {
            @wire(getRecord, { recordId: '$recordId' }) record;
            handleSave() { this.dispatchEvent(new CustomEvent('save')); }
        }
        """
    )
    results = extract_lwc(bundle, "force-app/main/default/lwc/customerDetails/customerDetails.html")
    assert len(results) == 1
    assert results[0].name == "customerDetails"
    assert "CustomerController" in results[0].references
    assert "Finance_Type__c" in results[0].data["fields"]


def test_normalize_partial_lwc_folder_upload(tmp_path):
    from app.knowledge_engine.upload_normalizer import normalize_salesforce_upload

    feature = tmp_path / "Data Change" / "myCmp"
    feature.mkdir(parents=True)
    (feature / "myCmp.html").write_text("<template></template>", encoding="utf-8")
    (feature / "myCmp.js").write_text("export default class {}", encoding="utf-8")
    (feature / "myCmp.js-meta.xml").write_text("<LightningComponentBundle/>", encoding="utf-8")

    root = normalize_salesforce_upload(tmp_path)
    assert (root / "force-app" / "main" / "default" / "lwc" / "Data Change" / "myCmp" / "myCmp.js").is_file()


def test_normalize_partial_apex_folder_upload(tmp_path):
    from app.knowledge_engine.upload_normalizer import normalize_salesforce_upload

    classes = tmp_path / "classes"
    classes.mkdir()
    (classes / "Foo.cls").write_text("public class Foo {}", encoding="utf-8")
    (classes / "Foo.cls-meta.xml").write_text("<ApexClass/>", encoding="utf-8")

    root = normalize_salesforce_upload(tmp_path)
    assert (root / "force-app" / "main" / "default" / "classes" / "Foo.cls").is_file()

