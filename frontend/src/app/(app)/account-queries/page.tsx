"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { AccountQuery, MatchHints } from "@/lib/types";
import { TableSkeleton } from "@/components/loading/table-skeleton";

const MAX_QUERIES = 5;

export default function AccountQueriesPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<AccountQuery | null>(null);
  const [name, setName] = useState("");
  const [soql, setSoql] = useState("");
  const [hints, setHints] = useState<MatchHints>({});
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

  const { data: orgs = [] } = useQuery({
    queryKey: ["orgs", projectId],
    queryFn: () => api.getOrgs(projectId!),
    enabled: !!projectId,
  });

  const { data: queries = [], isLoading } = useQuery({
    queryKey: ["account-queries", projectId],
    queryFn: () => api.listAccountQueries(projectId!),
    enabled: !!projectId,
    staleTime: 2 * 60_000,
  });

  const resetForm = () => {
    setEditing(null);
    setName("");
    setSoql("");
    setHints({});
    setError("");
  };

  const startEdit = (q: AccountQuery) => {
    setEditing(q);
    setName(q.name);
    setSoql(q.soql_text);
    setHints(q.match_hints || {});
  };

  const insertTemplate = async () => {
    const org = orgs.find((o) => o.bottler) || orgs[0];
    if (!org) return;
    try {
      const opts = await api.getCustomerSearchOptions(org.id);
      if (opts.default_soql) setSoql(opts.default_soql);
    } catch {
      setError("Connect an org with a bottler to load a template.");
    }
  };

  const handleSave = async () => {
    if (!projectId || !name.trim() || !soql.trim()) {
      setError("Name and SOQL are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (editing) {
        await api.updateAccountQuery(editing.id, {
          name: name.trim(),
          soql_text: soql.trim(),
          match_hints: hints,
        });
      } else {
        if (queries.length >= MAX_QUERIES) {
          setError(`Maximum ${MAX_QUERIES} queries per project.`);
          return;
        }
        await api.createAccountQuery({
          project_id: projectId,
          name: name.trim(),
          soql_text: soql.trim(),
          match_hints: hints,
          sort_order: queries.length,
        });
      }
      await queryClient.invalidateQueries({ queryKey: ["account-queries", projectId] });
      resetForm();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this account query?")) return;
    await api.deleteAccountQuery(id);
    await queryClient.invalidateQueries({ queryKey: ["account-queries", projectId] });
    if (editing?.id === id) resetForm();
  };

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold sm:text-3xl">Account Queries</h1>
        <p className="text-sm text-muted-foreground">
          Save up to {MAX_QUERIES} labeled SOQL queries per project. At run time the agent
          runs the query via the Salesforce REST API and picks an account.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{editing ? "Edit Query" : "Add Query"}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Label</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. AR Payer accounts" />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <Label>SOQL (Account SELECT)</Label>
              <Button type="button" variant="outline" size="sm" onClick={insertTemplate}>
                Insert template
              </Button>
            </div>
            <Textarea
              rows={8}
              className="font-mono text-xs"
              value={soql}
              onChange={(e) => setSoql(e.target.value)}
              placeholder="SELECT Id, AccountNumber, Name FROM Account WHERE ..."
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Match bottler (auto-pick)</Label>
              <Input
                value={hints.bottler || ""}
                onChange={(e) => setHints({ ...hints, bottler: e.target.value || null })}
                placeholder="5000"
              />
            </div>
            <div className="space-y-2">
              <Label>Match account group</Label>
              <Input
                value={hints.account_group || ""}
                onChange={(e) => setHints({ ...hints, account_group: e.target.value || null })}
              />
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex gap-2">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Saving…" : editing ? "Update" : "Add Query"}
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
          <CardTitle>Saved Queries ({queries.length}/{MAX_QUERIES})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            <TableSkeleton rows={4} columns={2} />
          ) : queries.length === 0 ? (
            <p className="text-sm text-muted-foreground">No queries yet.</p>
          ) : null}
          {!isLoading && queries.map((q) => (
            <div key={q.id} className="rounded-md border p-3 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{q.name}</p>
                  {q.match_hints?.bottler && (
                    <Badge variant="secondary" className="mt-1">
                      bottler {q.match_hints.bottler}
                    </Badge>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => startEdit(q)}>
                    Edit
                  </Button>
                  <Button variant="destructive" size="sm" onClick={() => handleDelete(q.id)}>
                    Delete
                  </Button>
                </div>
              </div>
              <pre className="max-h-24 overflow-auto rounded bg-muted p-2 text-xs">{q.soql_text}</pre>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
