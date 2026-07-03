"""Tests for Salesforce knowledge engine extractors and scanner."""

from pathlib import Path

from app.knowledge_engine.extractors.apex_extractor import extract_apex
from app.knowledge_engine.extractors.lwc_extractor import extract_lwc
from app.knowledge_engine.scanner.repo_scanner import discover_modules, filter_module_files, enumerate_all_files


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
    assert "customerDetails" in names or "CustomerController" in names

    filtered = filter_module_files(all_files, "customerDetails")
    assert len(filtered) >= 1


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
