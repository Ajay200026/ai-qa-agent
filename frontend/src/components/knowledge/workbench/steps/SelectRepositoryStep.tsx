"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { FolderGit2, GitBranch, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { AzureRepo, KnowledgeRepo } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { PremiumCard } from "@/components/ui/premium-card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface SelectRepositoryStepProps {
  selectedRepoId: string | null;
  onRepoSelect: (repoId: string | null) => void;
  onRegistered: () => void;
}

export function SelectRepositoryStep({
  selectedRepoId,
  onRepoSelect,
  onRegistered,
}: SelectRepositoryStepProps) {
  const queryClient = useQueryClient();
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null);
  const [selectedProject, setSelectedProject] = useState("");
  const [selectedRepo, setSelectedRepo] = useState<AzureRepo | null>(null);
  const [selectedBranch, setSelectedBranch] = useState("");
  const [repoDisplayName, setRepoDisplayName] = useState("");
  const [registering, setRegistering] = useState(false);
  const [syncProgress, setSyncProgress] = useState(0);
  const [deleteRepoId, setDeleteRepoId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data: connections = [] } = useQuery({
    queryKey: ["azure-connections"],
    queryFn: () => api.listAzureConnections(),
  });

  const { data: repos = [] } = useQuery({
    queryKey: ["knowledge-repos"],
    queryFn: () => api.listKnowledgeRepos(),
  });

  const { data: projects = [] } = useQuery({
    queryKey: ["azure-projects", selectedConnectionId],
    queryFn: () => api.listAzureProjects(selectedConnectionId!),
    enabled: !!selectedConnectionId,
  });

  const { data: azureRepos = [] } = useQuery({
    queryKey: ["azure-repos", selectedConnectionId, selectedProject],
    queryFn: () => api.listAzureRepos(selectedConnectionId!, selectedProject),
    enabled: !!selectedConnectionId && !!selectedProject,
  });

  const { data: branchData } = useQuery({
    queryKey: ["azure-branches", selectedConnectionId, selectedProject, selectedRepo?.id],
    queryFn: () =>
      api.listAzureBranches(selectedConnectionId!, selectedRepo!.id, selectedProject),
    enabled: !!selectedConnectionId && !!selectedProject && !!selectedRepo?.id,
  });

  const branches = branchData?.branches ?? [];

  useEffect(() => {
    if (connections.length > 0 && !selectedConnectionId) {
      setSelectedConnectionId(connections[0].id);
    }
  }, [connections, selectedConnectionId]);

  useEffect(() => {
    if (selectedRepo && !repoDisplayName) {
      setRepoDisplayName(selectedRepo.name);
    }
  }, [selectedRepo, repoDisplayName]);

  useEffect(() => {
    if (selectedRepo?.default_branch && !selectedBranch) {
      setSelectedBranch(selectedRepo.default_branch);
    }
  }, [selectedRepo, selectedBranch]);

  const handleRegister = async () => {
    if (!selectedConnectionId || !selectedProject || !selectedRepo || !selectedBranch) {
      toast.error("Select project, repository, and branch");
      return;
    }
    setRegistering(true);
    setSyncProgress(10);
    const interval = setInterval(() => {
      setSyncProgress((p) => Math.min(p + 8, 90));
    }, 400);
    try {
      const repo = await api.createKnowledgeRepo({
        name: repoDisplayName.trim() || selectedRepo.name,
        source_type: "azure",
        connection_id: selectedConnectionId,
        azure_project: selectedProject,
        azure_repo: selectedRepo.name,
        azure_repo_id: selectedRepo.id,
        branch: selectedBranch,
      });
      setSyncProgress(100);
      toast.success("Repository registered and synced");
      await queryClient.invalidateQueries({ queryKey: ["knowledge-repos"] });
      onRepoSelect(repo.id);
      onRegistered();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Registration failed");
    } finally {
      clearInterval(interval);
      setRegistering(false);
      setSyncProgress(0);
    }
  };

  const handleDeleteRepo = async () => {
    if (!deleteRepoId) return;
    setDeleting(true);
    try {
      await api.deleteKnowledgeRepo(deleteRepoId);
      toast.success("Repository deleted");
      if (selectedRepoId === deleteRepoId) {
        onRepoSelect(null);
      }
      await queryClient.invalidateQueries({ queryKey: ["knowledge-repos"] });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting(false);
      setDeleteRepoId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Select Repository</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Choose a project, repository, and branch from Azure DevOps.
        </p>
      </div>

      {repos.length > 0 && (
        <div>
          <Label className="mb-3 block">Registered Repositories</Label>
          <div className="grid gap-3 sm:grid-cols-2">
            {repos.map((repo: KnowledgeRepo, i) => (
              <motion.div
                key={repo.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                className={`relative rounded-xl border p-4 transition-all hover:shadow-md ${
                  selectedRepoId === repo.id
                    ? "border-primary bg-primary/5 ring-2 ring-primary/30"
                    : "hover:border-primary/30"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onRepoSelect(repo.id)}
                  className="w-full text-left"
                >
                  <div className="flex items-center gap-2">
                    {repo.source_type === "local" ? (
                      <Upload className="h-4 w-4 text-primary" />
                    ) : (
                      <FolderGit2 className="h-4 w-4 text-primary" />
                    )}
                    <span className="font-medium">{repo.name}</span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {repo.source_type === "local"
                      ? "Uploaded codebase"
                      : `${repo.azure_project} / ${repo.azure_repo}`}
                  </p>
                  {repo.branch && (
                    <Badge variant="outline" className="mt-2 gap-1">
                      <GitBranch className="h-3 w-3" />
                      {repo.branch}
                    </Badge>
                  )}
                </button>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className="absolute right-2 top-2 h-8 w-8"
                  onClick={() => setDeleteRepoId(repo.id)}
                >
                  <Trash2 className="h-3.5 w-3.5 text-destructive" />
                </Button>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      <PremiumCard title="Register New Repository">
        <div className="space-y-4">
          {connections.length > 1 && (
            <div className="space-y-2">
              <Label>Connection</Label>
              <Select
                value={selectedConnectionId ?? ""}
                onValueChange={(v) => {
                  setSelectedConnectionId(v);
                  setSelectedProject("");
                  setSelectedRepo(null);
                  setSelectedBranch("");
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select connection" />
                </SelectTrigger>
                <SelectContent>
                  {connections.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name} ({c.organization_name})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {selectedConnectionId && (
            <div className="space-y-2">
              <Label>Project</Label>
              <Select
                value={selectedProject}
                onValueChange={(v) => {
                  setSelectedProject(v);
                  setSelectedRepo(null);
                  setSelectedBranch("");
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select project" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map((p) => (
                    <SelectItem key={p.id} value={p.name}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {selectedProject && (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Repository</Label>
                <Select
                  value={selectedRepo?.id ?? ""}
                  onValueChange={(v) => {
                    const repo = azureRepos.find((r) => r.id === v) ?? null;
                    setSelectedRepo(repo);
                    setSelectedBranch(repo?.default_branch ?? "");
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select repository" />
                  </SelectTrigger>
                  <SelectContent>
                    {azureRepos.map((r) => (
                      <SelectItem key={r.id} value={r.id}>
                        {r.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {selectedRepo && (
                <div className="space-y-2">
                  <Label>Branch</Label>
                  <Select value={selectedBranch} onValueChange={setSelectedBranch}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select branch" />
                    </SelectTrigger>
                    <SelectContent>
                      {branches.map((b) => (
                        <SelectItem key={b} value={b}>
                          {b}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          )}

          {selectedRepo && selectedBranch && (
            <div className="space-y-3 border-t pt-4">
              <div className="space-y-2">
                <Label htmlFor="display-name">Display Name</Label>
                <Input
                  id="display-name"
                  value={repoDisplayName}
                  onChange={(e) => setRepoDisplayName(e.target.value)}
                  placeholder={selectedRepo.name}
                />
              </div>
              {registering && (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground">Syncing repository…</p>
                  <Progress value={syncProgress} />
                </div>
              )}
              <Button onClick={handleRegister} disabled={registering} loading={registering}>
                Register & Sync Repository
              </Button>
            </div>
          )}
        </div>
      </PremiumCard>

      {selectedRepoId && (
        <Button onClick={onRegistered}>Continue to Module Selection</Button>
      )}

      <Dialog open={!!deleteRepoId} onOpenChange={() => setDeleteRepoId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete repository?</DialogTitle>
            <DialogDescription>
              This removes the repository, all modules, scan data, and workspace files.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteRepoId(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteRepo} loading={deleting}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
