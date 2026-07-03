"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ORG_TYPES, loginUrlForOrgType } from "@/lib/salesforce-org";
import type { SalesforceOrg } from "@/lib/types";

type AuthTab = "web" | "credentials";

interface OrgConnectPanelProps {
  projectId: string;
  onConnected: (org: SalesforceOrg) => void;
}

export function OrgConnectPanel({ projectId, onConnected }: OrgConnectPanelProps) {
  const [tab, setTab] = useState<AuthTab>("web");
  const [name, setName] = useState("");
  const [orgType, setOrgType] = useState("sandbox");
  const [customLoginUrl, setCustomLoginUrl] = useState("");
  const [role, setRole] = useState("");
  const [bottler, setBottler] = useState("");
  const [isDefault, setIsDefault] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [securityToken, setSecurityToken] = useState("");
  const [instanceUrl, setInstanceUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleWebAuthorize = async () => {
    if (!name.trim()) {
      setError("Display name is required");
      return;
    }
    const loginUrl =
      orgType === "custom" ? loginUrlForOrgType(orgType, customLoginUrl) : loginUrlForOrgType(orgType, "");
    if (!loginUrl) {
      setError("Custom org type requires a login URL");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const { authorization_url, state } = await api.startSalesforceOAuth({
        project_id: projectId,
        name: name.trim(),
        org_type: orgType,
        login_url: orgType === "custom" ? loginUrl : undefined,
        role: role || undefined,
        bottler: bottler || undefined,
        is_default: isDefault,
      });
      localStorage.setItem("sf_oauth_state", state);
      window.location.replace(authorization_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start OAuth");
      setLoading(false);
    }
  };

  const handleCredentialsSave = async () => {
    if (!name.trim() || !username || !password) {
      setError("Name, username, and password are required");
      return;
    }
    const loginUrl =
      orgType === "custom" ? loginUrlForOrgType(orgType, customLoginUrl) : loginUrlForOrgType(orgType, "");
    setLoading(true);
    setError("");
    try {
      const org = await api.createOrg({
        project_id: projectId,
        name: name.trim(),
        org_type: orgType,
        login_url: loginUrl,
        auth_method: "credentials",
        username,
        password,
        security_token: securityToken || undefined,
        instance_url: instanceUrl || undefined,
        role: role || undefined,
        bottler: bottler || undefined,
        is_default: isDefault,
      });
      await api.validateOrg(org.id);
      onConnected(org);
      setName("");
      setUsername("");
      setPassword("");
      setSecurityToken("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save org");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Connect Salesforce Org</CardTitle>
        <p className="text-sm text-muted-foreground">
          Sign in once via Salesforce — we store your org and session. You do not need to enter a
          password again for test runs.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Button
            type="button"
            variant={tab === "web" ? "default" : "outline"}
            size="sm"
            onClick={() => setTab("web")}
          >
            Authorize via Web
          </Button>
          <Button
            type="button"
            variant={tab === "credentials" ? "default" : "outline"}
            size="sm"
            onClick={() => setTab("credentials")}
          >
            Username & Password
          </Button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2 sm:col-span-2">
            <Label>Display name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="UAT Sandbox" />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label>Org type</Label>
            <div className="flex flex-wrap gap-2">
              {ORG_TYPES.map((t) => (
                <Button
                  key={t.value}
                  type="button"
                  size="sm"
                  variant={orgType === t.value ? "default" : "outline"}
                  onClick={() => setOrgType(t.value)}
                >
                  {t.label}
                </Button>
              ))}
            </div>
          </div>
          {orgType === "custom" && (
            <div className="space-y-2 sm:col-span-2">
              <Label>Login URL</Label>
              <Input
                value={customLoginUrl}
                onChange={(e) => setCustomLoginUrl(e.target.value)}
                placeholder="https://test.salesforce.com"
              />
            </div>
          )}
          <div className="space-y-2">
            <Label>Role (optional)</Label>
            <Input value={role} onChange={(e) => setRole(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>Bottler (optional)</Label>
            <Input value={bottler} onChange={(e) => setBottler(e.target.value)} placeholder="4900" />
          </div>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input
              type="checkbox"
              checked={isDefault}
              onChange={(e) => setIsDefault(e.target.checked)}
            />
            Set as default org for new executions
          </label>
        </div>

        {tab === "web" ? (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              You sign in to Salesforce once. We save the org, instance URL, and your Salesforce
              username — no password or security token is stored. Test runs open the org using that
              session automatically.
            </p>
            <Button type="button" onClick={handleWebAuthorize} disabled={loading}>
              {loading ? "Opening Salesforce…" : "Authorize Org"}
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Alternative if you cannot use browser OAuth. Requires username, password, and usually
              a security token for API access.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Username</Label>
              <Input value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Password</Label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Security token</Label>
              <Input
                type="password"
                value={securityToken}
                onChange={(e) => setSecurityToken(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Instance URL</Label>
              <Input value={instanceUrl} onChange={(e) => setInstanceUrl(e.target.value)} />
            </div>
            <div className="sm:col-span-2">
              <Button onClick={handleCredentialsSave} disabled={loading}>
                {loading ? "Saving…" : "Save & Validate"}
              </Button>
            </div>
          </div>
          </div>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}
