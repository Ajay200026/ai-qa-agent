"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { LoginAsProfile, MatchHints } from "@/lib/types";
import { TableSkeleton } from "@/components/loading/table-skeleton";

const MAX_PROFILES = 5;
const COMMON_ROLES = ["Requestor", "Finance", "GM", "Approver", "Manager"];

export default function LoginAsPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<LoginAsProfile | null>(null);
  const [name, setName] = useState("");
  const [bottlerId, setBottlerId] = useState("");
  const [role, setRole] = useState("");
  const [hints, setHints] = useState<MatchHints>({});
  const [enabled, setEnabled] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => {
      const p = await api.getProjects();
      if (p.length === 0) {
        return [await api.createProject("Default Project", "Salesforce QA testing project")];
      }
      return p;
    },
  });
  const projectId = projects[0]?.id;

  const { data: profiles = [], isLoading } = useQuery({
    queryKey: ["login-as-profiles", projectId],
    queryFn: () => api.listLoginAsProfiles(projectId!),
    enabled: !!projectId,
    staleTime: 2 * 60_000,
  });

  const resetForm = () => {
    setEditing(null);
    setName("");
    setBottlerId("");
    setRole("");
    setHints({});
    setEnabled(true);
    setError("");
  };

  const startEdit = (p: LoginAsProfile) => {
    setEditing(p);
    setName(p.name);
    setBottlerId(p.bottler_id);
    setRole(p.onboarding_role);
    setHints(p.match_hints || {});
    setEnabled(p.enabled);
  };

  const handleSave = async () => {
    if (!projectId || !name.trim() || !bottlerId.trim() || !role.trim()) {
      setError("Name, bottler, and role are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (editing) {
        await api.updateLoginAsProfile(editing.id, {
          name: name.trim(),
          bottler_id: bottlerId.trim(),
          onboarding_role: role.trim(),
          match_hints: hints,
          enabled,
        });
      } else {
        if (profiles.length >= MAX_PROFILES) {
          setError(`Maximum ${MAX_PROFILES} profiles per project.`);
          return;
        }
        await api.createLoginAsProfile({
          project_id: projectId,
          name: name.trim(),
          bottler_id: bottlerId.trim(),
          onboarding_role: role.trim(),
          match_hints: hints,
          enabled,
          sort_order: profiles.length,
        });
      }
      await queryClient.invalidateQueries({ queryKey: ["login-as-profiles", projectId] });
      resetForm();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this login-as profile?")) return;
    await api.deleteLoginAsProfile(id);
    await queryClient.invalidateQueries({ queryKey: ["login-as-profiles", projectId] });
    if (editing?.id === id) resetForm();
  };

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold sm:text-3xl">Login As</h1>
        <p className="text-sm text-muted-foreground">
          Save up to {MAX_PROFILES} impersonation profiles per project. Runs after admin login;
          pick a profile when starting a new execution.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{editing ? "Edit Profile" : "Add Profile"}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Label</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Requestor @ 5000" />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Bottler ID</Label>
              <Input value={bottlerId} onChange={(e) => setBottlerId(e.target.value)} placeholder="5000" />
            </div>
            <div className="space-y-2">
              <Label>Onboarding Role</Label>
              <Input
                list="roles-list"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="Requestor"
              />
              <datalist id="roles-list">
                {COMMON_ROLES.map((r) => (
                  <option key={r} value={r} />
                ))}
              </datalist>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Match role (auto-pick from test pack)</Label>
              <Input
                value={hints.role || ""}
                onChange={(e) => setHints({ ...hints, role: e.target.value || null })}
              />
            </div>
            <div className="space-y-2">
              <Label>Match bottler</Label>
              <Input
                value={hints.bottler || ""}
                onChange={(e) => setHints({ ...hints, bottler: e.target.value || null })}
              />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="h-4 w-4 rounded border"
            />
            Enabled
          </label>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex gap-2">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Saving…" : editing ? "Update" : "Add Profile"}
            </Button>
            {editing && (
              <Button variant="outline" onClick={resetForm}>
                Cancel
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Saved Profiles ({profiles.length}/{MAX_PROFILES})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            <TableSkeleton rows={4} columns={2} />
          ) : profiles.length === 0 ? (
            <p className="text-sm text-muted-foreground">No profiles yet.</p>
          ) : null}
          {!isLoading && profiles.map((p) => (
            <div key={p.id} className="flex items-center justify-between gap-2 rounded-md border p-3">
              <div>
                <p className="font-medium">{p.name}</p>
                <p className="text-xs text-muted-foreground">
                  {p.onboarding_role} @ {p.bottler_id}
                </p>
                {!p.enabled && <Badge variant="outline">Disabled</Badge>}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => startEdit(p)}>
                  Edit
                </Button>
                <Button variant="destructive" size="sm" onClick={() => handleDelete(p.id)}>
                  Delete
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
