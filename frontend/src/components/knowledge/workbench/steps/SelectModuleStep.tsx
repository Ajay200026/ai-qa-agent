"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { DiscoveredModule, KnowledgeModule } from "@/lib/types";
import { ModuleFolderPicker } from "@/components/knowledge/ModuleFolderPicker";
import { CodeExplorer } from "@/components/knowledge/CodeExplorer";
import { PremiumCard } from "@/components/ui/premium-card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface SelectModuleStepProps {
  repoId: string;
  modules: KnowledgeModule[];
  selectedModuleId: string | null;
  onSelect: (moduleId: string) => void;
  onContinue: () => void;
}

export function SelectModuleStep({
  repoId,
  modules,
  selectedModuleId,
  onSelect,
  onContinue,
}: SelectModuleStepProps) {
  const queryClient = useQueryClient();

  const { data: discovered = [] } = useQuery({
    queryKey: ["discover-modules", repoId],
    queryFn: () => api.discoverModules(repoId),
    enabled: !!repoId,
  });

  const selectedModule = modules.find((m) => m.id === selectedModuleId);

  const handleDiscoverClick = async (d: DiscoveredModule) => {
    if (!d.scope_path) {
      toast.error("No scope path for this module");
      return;
    }
    const existing = modules.find((m) => m.scope_path === d.scope_path);
    if (existing) {
      onSelect(existing.id);
      toast.success(`Module "${existing.name}" selected`);
      return;
    }
    try {
      const validation = await api.validateScope(repoId, d.scope_path);
      if (!validation.valid) {
        toast.error(validation.message || "Invalid scope");
        return;
      }
      const scopePath = validation.normalized_path || d.scope_path;
      const created = await api.createKnowledgeModule(repoId, d.name, scopePath);
      await queryClient.invalidateQueries({ queryKey: ["knowledge-modules", repoId] });
      onSelect(created.id);
      toast.success(`Module "${created.name}" created from suggestion`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to create module");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Select Module</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Browse folders and pick a feature scope to scan. Referenced dependencies are included automatically.
        </p>
      </div>

      {discovered.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <span className="self-center text-xs text-muted-foreground">Suggested:</span>
          {discovered.slice(0, 8).map((d) => (
            <button key={d.scope_path || d.name} type="button" onClick={() => handleDiscoverClick(d)}>
              <Badge variant="secondary" className="cursor-pointer text-xs hover:bg-primary/20">
                {d.name} ({d.file_count} files)
              </Badge>
            </button>
          ))}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <PremiumCard title="Folder Browser" description="Select a feature folder">
          <ModuleFolderPicker
            repoId={repoId}
            modules={modules}
            selectedModuleId={selectedModuleId}
            onSelect={onSelect}
            onError={() => {}}
          />
        </PremiumCard>

        <PremiumCard
          title="Code Explorer"
          description={selectedModule?.scope_path || "Select a module to browse code"}
          noPadding
        >
          {selectedModuleId && selectedModule?.scope_path ? (
            <Tabs defaultValue="code" className="p-4">
              <TabsList>
                <TabsTrigger value="code">Source Files</TabsTrigger>
              </TabsList>
              <TabsContent value="code" className="mt-4">
                <CodeExplorer repoId={repoId} scopePath={selectedModule.scope_path} />
              </TabsContent>
            </Tabs>
          ) : (
            <p className="p-6 text-sm text-muted-foreground">
              Select a module folder to preview source code.
            </p>
          )}
        </PremiumCard>
      </div>

      {selectedModuleId && (
        <Button onClick={onContinue}>Continue to Scan & Explore</Button>
      )}
    </div>
  );
}
