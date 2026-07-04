"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Folder, FolderOpen, Search } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { KnowledgeModule, RepoFolderEntry } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const GENERIC_FOLDERS = new Set([
  "lwc",
  "classes",
  "objects",
  "flows",
  "triggers",
  "aura",
  "main",
  "default",
  "force-app",
]);

const BREAKDOWN_LABELS: Record<string, string> = {
  lwc: "LWC",
  apex_class: "Apex",
  apex_trigger: "Trigger",
  object: "Object",
  flow: "Flow",
  field: "Field",
  validation_rule: "Validation",
  layout: "Layout",
  permission_set: "PermSet",
  label: "Label",
  custom_metadata: "Metadata",
  other: "Other",
};

interface ModuleFolderPickerProps {
  repoId: string;
  modules: KnowledgeModule[];
  selectedModuleId: string | null;
  onSelect: (moduleId: string) => void;
  onError: (message: string) => void;
}

function formatBreakdown(breakdown: Record<string, number>) {
  return Object.entries(breakdown)
    .filter(([, count]) => count > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([key, count]) => ({
      key,
      label: BREAKDOWN_LABELS[key] ?? key,
      count,
    }));
}

export function ModuleFolderPicker({
  repoId,
  modules,
  selectedModuleId,
  onSelect,
  onError,
}: ModuleFolderPickerProps) {
  const queryClient = useQueryClient();
  const [currentPath, setCurrentPath] = useState("");
  const [search, setSearch] = useState("");
  const [selecting, setSelecting] = useState<string | null>(null);

  const { data: folders = [], isLoading } = useQuery({
    queryKey: ["repo-tree", repoId, currentPath],
    queryFn: () => api.listRepoTree(repoId, currentPath),
    enabled: !!repoId,
  });

  const { data: leafScope } = useQuery({
    queryKey: ["validate-scope", repoId, currentPath],
    queryFn: () => api.validateScope(repoId, currentPath),
    enabled: !!repoId && !!currentPath && !isLoading && folders.length === 0,
  });

  const displayFolders = useMemo(() => {
    if (folders.length > 0) return folders;
    if (!currentPath || !leafScope?.valid || leafScope.file_count <= 0) return [];
    const parts = currentPath.split("/").filter(Boolean);
    const name = parts[parts.length - 1] || currentPath;
    return [
      {
        name,
        path: currentPath,
        file_count: leafScope.file_count,
        breakdown: leafScope.breakdown,
        is_selectable: true,
        is_current: true,
      } satisfies RepoFolderEntry,
    ];
  }, [folders, currentPath, leafScope]);

  const breadcrumbs = useMemo(() => {
    if (!currentPath) return [];
    const parts = currentPath.split("/").filter(Boolean);
    const crumbs: { label: string; path: string }[] = [];
    let acc = "";
    for (const part of parts) {
      acc = acc ? `${acc}/${part}` : part;
      crumbs.push({ label: part, path: acc });
    }
    return crumbs;
  }, [currentPath]);

  const filteredFolders = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return displayFolders;
    return displayFolders.filter(
      (f) => f.name.toLowerCase().includes(q) || f.path.toLowerCase().includes(q)
    );
  }, [displayFolders, search]);

  const handleSelectFolder = async (entry: RepoFolderEntry) => {
    const isGeneric = GENERIC_FOLDERS.has(entry.name.toLowerCase());
    if (isGeneric) {
      onError(`"${entry.name}" is a generic folder. Open it and select a named feature folder (e.g. Data Change).`);
      toast.error(`Select a feature folder inside "${entry.name}", not the container itself.`);
      return;
    }

    setSelecting(entry.path);
    onError("");
    try {
      const validation = await api.validateScope(repoId, entry.path);
      if (!validation.valid) {
        const msg = validation.message || "Invalid folder scope";
        if (validation.suggestion) {
          toast.error(`${msg} Suggested: ${validation.suggestion}`);
          onError(`${msg} Try: ${validation.suggestion}`);
        } else {
          toast.error(msg);
          onError(msg);
        }
        return;
      }

      const scopePath = validation.normalized_path || entry.path;
      const existing = modules.find((m) => m.scope_path === scopePath);
      if (existing) {
        onSelect(existing.id);
        toast.success(`Module "${existing.name}" selected`);
        return;
      }

      const created = await api.createKnowledgeModule(repoId, entry.name, scopePath);
      await queryClient.invalidateQueries({ queryKey: ["knowledge-modules", repoId] });
      onSelect(created.id);
      toast.success(`Module "${created.name}" created`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to select folder";
      toast.error(msg);
      onError(msg);
    } finally {
      setSelecting(null);
    }
  };

  const registeredForPath = (path: string) =>
    modules.find((m) => m.scope_path === path)?.id ?? null;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Select a <strong>feature folder</strong> (e.g. Data Change) — not generic containers like{" "}
        <code className="text-xs">lwc</code> or <code className="text-xs">classes</code>.
      </p>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search folders…"
          className="pl-9"
        />
      </div>

      <div className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
        <button
          type="button"
          onClick={() => setCurrentPath("")}
          className="inline-flex items-center gap-1 rounded px-1 hover:bg-accent hover:text-foreground"
        >
          <Folder className="h-3.5 w-3.5" />
          Repository
        </button>
        {breadcrumbs.map((crumb) => (
          <span key={crumb.path} className="inline-flex items-center gap-1">
            <ChevronRight className="h-3.5 w-3.5" />
            <button
              type="button"
              onClick={() => setCurrentPath(crumb.path)}
              className="rounded px-1 hover:bg-accent hover:text-foreground"
            >
              {crumb.label}
            </button>
          </span>
        ))}
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading folders…</p>
      ) : filteredFolders.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {search
            ? "No folders match your search."
            : currentPath && leafScope?.valid && leafScope.file_count > 0
              ? "This folder contains files but no subfolders. Select it as your module scope."
              : "No folders found at this level."}
        </p>
      ) : (
        <div className="max-h-80 space-y-2 overflow-y-auto">
          {filteredFolders.map((entry) => {
            const registeredId = registeredForPath(entry.path);
            const isSelected = registeredId === selectedModuleId;
            const badges = formatBreakdown(entry.breakdown);
            const isGeneric = GENERIC_FOLDERS.has(entry.name.toLowerCase());
            const canSelect =
              (entry.is_selectable || entry.is_current || !isGeneric) && entry.file_count > 0;

            return (
              <div
                key={entry.path}
                className={`flex items-start justify-between gap-3 rounded-md border px-3 py-2 transition-colors ${
                  isSelected ? "border-primary bg-accent" : "hover:bg-accent/50"
                }`}
              >
                <button
                  type="button"
                  onClick={() => {
                    if (entry.is_current || entry.is_selectable) return;
                    setCurrentPath(entry.path);
                  }}
                  className="min-w-0 flex-1 text-left"
                >
                  <div className="flex items-center gap-2">
                    <FolderOpen className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="truncate font-medium">{entry.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {entry.file_count} {entry.file_count === 1 ? "file" : "files"}
                    </span>
                  </div>
                  {badges.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {badges.map((b) => (
                        <Badge key={b.key} variant="secondary" className="text-xs font-normal">
                          {b.count} {b.label}
                        </Badge>
                      ))}
                    </div>
                  )}
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">{entry.path}</p>
                  {isGeneric && (
                    <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
                      Container folder — open and select a named feature inside.
                    </p>
                  )}
                </button>
                <Button
                  type="button"
                  size="sm"
                  variant={isSelected ? "default" : "outline"}
                  disabled={selecting === entry.path || !canSelect}
                  onClick={() => (isGeneric ? setCurrentPath(entry.path) : handleSelectFolder(entry))}
                >
                  {isGeneric
                    ? "Open"
                    : selecting === entry.path
                      ? "…"
                      : isSelected
                        ? "Selected"
                        : "Select"}
                </Button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
