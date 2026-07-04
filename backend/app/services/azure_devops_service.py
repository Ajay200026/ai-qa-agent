"""Azure DevOps REST API client (PAT auth)."""

from __future__ import annotations

import base64
import re
from typing import Any
from urllib.parse import quote, urlparse

import httpx

API_VERSION = "7.1"


def parse_organization_url(organization_url: str) -> tuple[str, str]:
    """Return (normalized_base_url, organization_name)."""
    raw = organization_url.strip().rstrip("/")
    if not raw.startswith("http"):
        raw = f"https://{raw}"

    parsed = urlparse(raw)
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")

    if "dev.azure.com" in host:
        org = path.split("/")[0] if path else ""
        if not org:
            raise ValueError("Organization URL must be https://dev.azure.com/{organization}")
        base = f"https://dev.azure.com/{org}"
        return base, org

    if host.endswith("visualstudio.com"):
        org = host.split(".")[0]
        base = f"https://dev.azure.com/{org}"
        return base, org

    if path:
        org = path.split("/")[0]
        base = f"{parsed.scheme}://{host}/{org}"
        return base.rstrip("/"), org

    raise ValueError(
        "Unsupported organization URL. Use https://dev.azure.com/{organization}"
    )


def _auth_header(pat: str) -> dict[str, str]:
    token = base64.b64encode(f":{pat}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


class AzureDevOpsClient:
    def __init__(self, organization_url: str, pat: str):
        self.base_url, self.organization_name = parse_organization_url(organization_url)
        self.pat = pat
        self._headers = _auth_header(pat)

    async def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, headers=self._headers, params=params or {})
        if resp.status_code == 401:
            raise ValueError("Invalid or expired Azure DevOps PAT")
        if resp.status_code >= 400:
            raise ValueError(f"Azure DevOps API error ({resp.status_code}): {resp.text[:300]}")
        return resp.json()

    async def validate(self) -> None:
        await self.list_projects()

    async def list_projects(self) -> list[dict[str, str]]:
        data = await self._get("_apis/projects", {"api-version": API_VERSION, "$top": "100"})
        return [
            {"id": p["id"], "name": p["name"]}
            for p in data.get("value", [])
            if p.get("name")
        ]

    async def list_repositories(self, project: str) -> list[dict[str, str]]:
        encoded_project = quote(project, safe="")
        data = await self._get(
            f"{encoded_project}/_apis/git/repositories",
            {"api-version": API_VERSION},
        )
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "default_branch": (r.get("defaultBranch") or "refs/heads/main").replace(
                    "refs/heads/", ""
                ),
            }
            for r in data.get("value", [])
            if r.get("name")
        ]

    async def list_branches(self, project: str, repo_id: str) -> list[str]:
        encoded_project = quote(project, safe="")
        data = await self._get(
            f"{encoded_project}/_apis/git/repositories/{repo_id}/refs",
            {"api-version": API_VERSION, "filter": "heads/"},
        )
        branches: list[str] = []
        for ref in data.get("value", []):
            name = ref.get("name", "")
            if name.startswith("refs/heads/"):
                branches.append(name.replace("refs/heads/", "", 1))
        return sorted(branches)

    def build_clone_url(self, project: str, repo_name: str) -> str:
        encoded_project = quote(project, safe="")
        encoded_repo = quote(repo_name, safe="")
        safe_pat = quote(self.pat, safe="")
        return (
            f"https://{safe_pat}@dev.azure.com/{self.organization_name}/"
            f"{encoded_project}/_git/{encoded_repo}"
        )


def safe_branch_dirname(branch: str) -> str:
    return re.sub(r"[^\w\-.]+", "_", branch)
