"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Brain, FolderGit2, GitBranch, MessageSquare, Scan, Sparkles } from "lucide-react";

import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/layout/page-header";
import { StatsCardsSkeleton } from "@/components/loading/stats-cards-skeleton";
import type { DiscoveredModule } from "@/lib/types";

const MODULE_STORAGE_KEY = "knowledge_selected_module";

function statusBadge(status: string) {
  const variant =
    status === "completed" ? "default" : status === "scanning" ? "secondary" : status === "failed" ? "destructive" : "outline";
  return <Badge variant={variant}>{status}</Badge>;
}

export default function KnowledgePage() {
  const queryClient = useQueryClient();
  const [repoName, setRepoName] = useState("");
  const [repoPath, setRepoPath] = useState("");
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null);
  const [selectedModuleId, setSelectedModuleId] = useState<string | null>(null);
  const [scanLog, setScanLog] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [scanning, setScanning] = useState(false);

  const { data: llmConfig } = useQuery({
    queryKey: ["llm-config"],
    queryFn: () => api.getLlmConfig(),
  });

  const { data: repos = [], isLoading: reposLoading } = useQuery({
    queryKey: ["knowledge-repos"],
    queryFn: () => api.listKnowledgeRepos(),
  });

  const { data: discovered = [] } = useQuery({
    queryKey: ["discovered-modules", selectedRepoId],
    queryFn: () => api.discoverModules(selectedRepoId!),
    enabled: !!selectedRepoId,
  });

  const { data: modules = [] } = useQuery({
    queryKey: ["knowledge-modules", selectedRepoId],
    queryFn: () => api.listKnowledgeModules(selectedRepoId!),
    enabled: !!selectedRepoId,
  });

  const { data: moduleStatus, refetch: refetchStatus } = useQuery({
    queryKey: ["module-status", selectedModuleId],
    queryFn: () => api.getModuleStatus(selectedModuleId!),
    enabled: !!selectedModuleId,
    refetchInterval: scanning ? 3000 : false,
  });

  useEffect(() => {
    const stored = localStorage.getItem(MODULE_STORAGE_KEY);
    if (stored) setSelectedModuleId(stored);
  }, []);

  useEffect(() => {
    if (repos.length > 0 && !selectedRepoId) {
      setSelectedRepoId(repos[0].id);
    }
  }, [repos, selectedRepoId]);

  useEffect(() => {
    if (selectedModuleId) {
      localStorage.setItem(MODULE_STORAGE_KEY, selectedModuleId);
    }
  }, [selectedModuleId]);

  const handleRegisterRepo = async () => {
    if (!repoName.trim() || !repoPath.trim()) {
      setError("Repository name and path are required.");
      return;
    }
    setError("");
    try {
      const repo = await api.createKnowledgeRepo(repoName.trim(), repoPath.trim());
      await queryClient.invalidateQueries({ queryKey: ["knowledge-repos"] });
      setSelectedRepoId(repo.id);
      setRepoName("");
      setRepoPath("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to register repository");
    }
  };

  const handleSelectModule = async (mod: DiscoveredModule) => {
    if (!selectedRepoId) return;
    setError("");
    try {
      const existing = modules.find((m) => m.name === mod.name);
      if (existing) {
        setSelectedModuleId(existing.id);
        return;
      }
      const created = await api.createKnowledgeModule(selectedRepoId, mod.name);
      await queryClient.invalidateQueries({ queryKey: ["knowledge-modules", selectedRepoId] });
      setSelectedModuleId(created.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to select module");
    }
  };

  const handleScan = async () => {
    if (!selectedModuleId) return;
    setScanning(true);
    setScanLog([]);
    setError("");
    try {
      await api.startModuleScan(selectedModuleId);

      const poll = setInterval(async () => {
        const status = await api.getModuleStatus(selectedModuleId);
        if (status.stats) {
          setScanLog((prev) => [...prev, `Indexed ${status.stats?.entities ?? 0} entities`]);
        }
        if (status.scan_status === "completed" || status.scan_status === "failed") {
          clearInterval(poll);
          setScanning(false);
          refetchStatus();
          queryClient.invalidateQueries({ queryKey: ["knowledge-modules", selectedRepoId] });
        }
      }, 2000);
    } catch (e) {
      setScanning(false);
      setError(e instanceof Error ? e.message : "Scan failed");
    }
  };

  const stats = moduleStatus?.stats || {};
  const selectedModule = modules.find((m) => m.id === selectedModuleId);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Knowledge Platform"
        description="Index Salesforce modules, build dependency graphs, and ask AI about your application."
      />

      <div className="flex flex-wrap gap-2">
        <Badge variant={llmConfig?.is_local ? "default" : "secondary"}>
          LLM: {llmConfig?.provider || "unknown"} {llmConfig?.model ? `(${llmConfig.model})` : ""}
        </Badge>
        <Badge variant={llmConfig?.enabled ? "default" : "destructive"}>
          AI {llmConfig?.enabled ? "Ready" : "Not configured"}
        </Badge>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <FolderGit2 className="h-5 w-5" />
              Repository
            </CardTitle>
            <CardDescription>Register a local Salesforce project path on your machine.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {reposLoading ? (
              <StatsCardsSkeleton />
            ) : repos.length > 0 ? (
              <div className="space-y-2">
                <Label>Registered repositories</Label>
                <div className="flex flex-wrap gap-2">
                  {repos.map((repo) => (
                    <Button
                      key={repo.id}
                      variant={selectedRepoId === repo.id ? "default" : "outline"}
                      size="sm"
                      onClick={() => setSelectedRepoId(repo.id)}
                    >
                      {repo.name}
                    </Button>
                  ))}
                </div>
                {selectedRepoId && (
                  <p className="text-xs text-muted-foreground">
                    {repos.find((r) => r.id === selectedRepoId)?.path}
                  </p>
                )}
              </div>
            ) : null}
            <div className="space-y-2">
              <Label htmlFor="repo-name">Name</Label>
              <Input id="repo-name" value={repoName} onChange={(e) => setRepoName(e.target.value)} placeholder="CONA Salesforce" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="repo-path">Local path</Label>
              <Input id="repo-path" value={repoPath} onChange={(e) => setRepoPath(e.target.value)} placeholder="/Users/you/projects/salesforce-repo" />
            </div>
            <Button onClick={handleRegisterRepo}>Register Repository</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Brain className="h-5 w-5" />
              Select Module
            </CardTitle>
            <CardDescription>Choose a module to scan. Only the module and its dependencies are indexed.</CardDescription>
          </CardHeader>
          <CardContent>
            {!selectedRepoId ? (
              <p className="text-sm text-muted-foreground">Register a repository first.</p>
            ) : discovered.length === 0 ? (
              <p className="text-sm text-muted-foreground">No modules discovered. Check the repository path.</p>
            ) : (
              <div className="max-h-64 space-y-2 overflow-y-auto">
                {discovered.map((mod) => {
                  const registered = modules.find((m) => m.name === mod.name);
                  const isSelected = registered?.id === selectedModuleId;
                  return (
                    <button
                      key={mod.name}
                      type="button"
                      onClick={() => handleSelectModule(mod)}
                      className={`flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors hover:bg-accent ${
                        isSelected ? "border-primary bg-accent" : ""
                      }`}
                    >
                      <span className="font-medium">{mod.name}</span>
                      <span className="text-xs text-muted-foreground">{mod.file_count} files</span>
                    </button>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {selectedModuleId && (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <CardTitle className="text-lg">{selectedModule?.name || "Module"}</CardTitle>
                <CardDescription className="mt-1 flex items-center gap-2">
                  Scan status: {statusBadge(moduleStatus?.scan_status || selectedModule?.scan_status || "pending")}
                </CardDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={handleScan} disabled={scanning}>
                  <Scan className="mr-2 h-4 w-4" />
                  {scanning ? "Scanning..." : "Scan Module"}
                </Button>
                <Button variant="outline" asChild>
                  <Link href={`/knowledge/graph?module=${selectedModuleId}`}>
                    <GitBranch className="mr-2 h-4 w-4" />
                    View Graph
                  </Link>
                </Button>
                <Button variant="outline" asChild>
                  <Link href={`/knowledge/ask?module=${selectedModuleId}`}>
                    <MessageSquare className="mr-2 h-4 w-4" />
                    Ask AI
                  </Link>
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Indexed Files" value={stats.indexed_files} />
              <StatCard label="Entities" value={stats.entities} />
              <StatCard label="Objects" value={stats.objects} />
              <StatCard label="Fields" value={stats.fields} />
              <StatCard label="Apex Classes" value={stats.apex_classes} />
              <StatCard label="LWC Components" value={stats.lwc_components} />
              <StatCard label="Flows" value={stats.flows} />
              <StatCard label="Business Rules" value={stats.business_rules} />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Badge variant="outline">Graph: {moduleStatus?.graph_status || "pending"}</Badge>
              <Badge variant="outline">Vector: {moduleStatus?.vector_status || "pending"}</Badge>
              <Badge variant="outline">AI: {moduleStatus?.ai_status || "pending"}</Badge>
            </div>
            {moduleStatus?.scan_error && (
              <p className="mt-4 text-sm text-destructive">{moduleStatus.scan_error}</p>
            )}
            {scanLog.length > 0 && (
              <div className="mt-4 rounded-md bg-muted p-3 text-xs">
                {scanLog.map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Sparkles className="h-5 w-5" />
            Workflow
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="list-inside list-decimal space-y-1 text-sm text-muted-foreground">
            <li>Register your local Salesforce repository path</li>
            <li>Select a module (e.g. Data Change, Onboarding)</li>
            <li>Scan to extract knowledge and build the dependency graph</li>
            <li>Explore the graph or ask AI questions about the application</li>
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value?: number | string }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold">{value ?? "—"}</p>
    </div>
  );
}
