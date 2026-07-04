"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { RotateCcw, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { StepIndicator, type WorkbenchStep } from "@/components/knowledge/workbench/StepIndicator";
import { ConnectAzureStep } from "@/components/knowledge/workbench/steps/ConnectAzureStep";
import { UploadCodebaseStep } from "@/components/knowledge/workbench/steps/UploadCodebaseStep";
import { SelectRepositoryStep } from "@/components/knowledge/workbench/steps/SelectRepositoryStep";
import { SelectModuleStep } from "@/components/knowledge/workbench/steps/SelectModuleStep";
import { ScanExploreStep } from "@/components/knowledge/workbench/steps/ScanExploreStep";

const MODULE_STORAGE_KEY = "knowledge_selected_module";

function deriveStep(
  reposCount: number,
  selectedRepoId: string | null,
  selectedModuleId: string | null
): WorkbenchStep {
  if (reposCount === 0) return "connect";
  if (!selectedRepoId) return "repository";
  if (!selectedModuleId) return "module";
  return "scan";
}

export function KnowledgeWorkbench() {
  const queryClient = useQueryClient();
  const [currentStep, setCurrentStep] = useState<WorkbenchStep>("connect");
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null);
  const [selectedModuleId, setSelectedModuleId] = useState<string | null>(null);
  const [sourceTab, setSourceTab] = useState<"azure" | "upload">("azure");
  const [showReset, setShowReset] = useState(false);
  const [resetting, setResetting] = useState(false);

  const { data: llmConfig } = useQuery({
    queryKey: ["llm-config"],
    queryFn: () => api.getLlmConfig(),
  });

  const { data: connections = [] } = useQuery({
    queryKey: ["azure-connections"],
    queryFn: () => api.listAzureConnections(),
  });

  const { data: repos = [] } = useQuery({
    queryKey: ["knowledge-repos"],
    queryFn: () => api.listKnowledgeRepos(),
  });

  const { data: modules = [] } = useQuery({
    queryKey: ["knowledge-modules", selectedRepoId],
    queryFn: () => api.listKnowledgeModules(selectedRepoId!),
    enabled: !!selectedRepoId,
  });

  const { data: moduleStatus } = useQuery({
    queryKey: ["module-status", selectedModuleId],
    queryFn: () => api.getModuleStatus(selectedModuleId!),
    enabled: !!selectedModuleId,
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

  useEffect(() => {
    setCurrentStep(deriveStep(repos.length, selectedRepoId, selectedModuleId));
  }, [repos.length, selectedRepoId, selectedModuleId]);

  const completedSteps = useMemo((): WorkbenchStep[] => {
    const done: WorkbenchStep[] = [];
    if (repos.length > 0 || connections.length > 0) done.push("connect");
    if (repos.length > 0 && selectedRepoId) done.push("repository");
    if (selectedModuleId) done.push("module");
    if (moduleStatus?.scan_status === "completed") done.push("scan");
    return done;
  }, [connections.length, repos.length, selectedRepoId, selectedModuleId, moduleStatus]);

  const handleStartFresh = async () => {
    setResetting(true);
    try {
      const result = await api.resetKnowledge();
      toast.success(
        `Reset complete: ${result.repos_deleted} repos, ${result.connections_deleted} connections removed`
      );
      setSelectedRepoId(null);
      setSelectedModuleId(null);
      localStorage.removeItem(MODULE_STORAGE_KEY);
      setCurrentStep("connect");
      await queryClient.invalidateQueries();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Reset failed");
    } finally {
      setResetting(false);
      setShowReset(false);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="Knowledge Platform"
        description="Connect Azure DevOps or upload code, select a module, and build your knowledge graph."
        actions={
          <Button variant="outline" size="sm" onClick={() => setShowReset(true)}>
            <RotateCcw className="mr-2 h-4 w-4" />
            Start Fresh
          </Button>
        }
      />

      <div className="flex flex-wrap gap-2">
        <Badge variant={llmConfig?.is_local ? "default" : "secondary"}>
          LLM: {llmConfig?.provider || "unknown"}
        </Badge>
        <Badge variant={llmConfig?.enabled ? "default" : "destructive"}>
          AI {llmConfig?.enabled ? "Ready" : "Not configured"}
        </Badge>
        <Badge variant="outline" className="gap-1">
          <Sparkles className="h-3 w-3" />
          Graphify Pipeline
        </Badge>
      </div>

      <div className="grid gap-8 lg:grid-cols-[240px_1fr]">
        <aside className="rounded-xl border bg-card/50 p-4">
          <StepIndicator
            currentStep={currentStep}
            completedSteps={completedSteps}
            onStepClick={setCurrentStep}
          />
        </aside>

        <div className="min-w-0">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentStep}
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -16 }}
              transition={{ duration: 0.25 }}
            >
              {currentStep === "connect" && (
                <div className="space-y-6">
                  <Tabs value={sourceTab} onValueChange={(v) => setSourceTab(v as "azure" | "upload")}>
                    <TabsList>
                      <TabsTrigger value="azure">Azure DevOps</TabsTrigger>
                      <TabsTrigger value="upload">Upload Code</TabsTrigger>
                    </TabsList>
                    <TabsContent value="azure" className="mt-6">
                      <ConnectAzureStep onConnected={() => setCurrentStep("repository")} />
                    </TabsContent>
                    <TabsContent value="upload" className="mt-6">
                      <UploadCodebaseStep
                        onUploaded={(repoId) => {
                          setSelectedRepoId(repoId);
                          setCurrentStep("module");
                        }}
                      />
                    </TabsContent>
                  </Tabs>
                  {repos.length > 0 && (
                    <Button variant="outline" onClick={() => setCurrentStep("repository")}>
                      Skip to registered repositories
                    </Button>
                  )}
                </div>
              )}
              {currentStep === "repository" && (
                <SelectRepositoryStep
                  selectedRepoId={selectedRepoId}
                  onRepoSelect={setSelectedRepoId}
                  onRegistered={() => setCurrentStep("module")}
                />
              )}
              {currentStep === "module" && selectedRepoId && (
                <SelectModuleStep
                  repoId={selectedRepoId}
                  modules={modules}
                  selectedModuleId={selectedModuleId}
                  onSelect={setSelectedModuleId}
                  onContinue={() => setCurrentStep("scan")}
                />
              )}
              {currentStep === "scan" && selectedModuleId && selectedRepoId && (
                <ScanExploreStep
                  selectedModuleId={selectedModuleId}
                  modules={modules}
                  repoId={selectedRepoId}
                  onFixScope={() => setCurrentStep("module")}
                  onModuleDeleted={() => {
                    setSelectedModuleId(null);
                    localStorage.removeItem(MODULE_STORAGE_KEY);
                    setCurrentStep("module");
                  }}
                />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      <Dialog open={showReset} onOpenChange={setShowReset}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Start fresh?</DialogTitle>
            <DialogDescription>
              This deletes all your knowledge repositories, modules, scan data, Azure connections, and
              workspace files. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowReset(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleStartFresh} loading={resetting}>
              Reset everything
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
