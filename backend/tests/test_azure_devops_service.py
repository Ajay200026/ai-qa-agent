"""Tests for Azure DevOps URL parsing."""

import pytest

from app.services.azure_devops_service import parse_organization_url, safe_branch_dirname


def test_parse_dev_azure_url():
    base, org = parse_organization_url("https://dev.azure.com/my-org")
    assert org == "my-org"
    assert base == "https://dev.azure.com/my-org"


def test_parse_visualstudio_url():
    base, org = parse_organization_url("https://contoso.visualstudio.com")
    assert org == "contoso"
    assert "dev.azure.com/contoso" in base


def test_safe_branch_dirname():
    assert safe_branch_dirname("feature/bugfix-3") == "feature_bugfix-3"
