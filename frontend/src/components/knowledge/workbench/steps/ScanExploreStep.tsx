"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { GitBranch, Globe, MessageSquare, Scan, Trash2, Wrench } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { KnowledgeModule } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PremiumCard } from "@/components/ui/premium-card";
import { ScanProgressPanel } from "@/components/knowledge/ScanProgressPanel";
import { MiniGraphPreview } from "@/components/knowledge/graph/MiniGraphPreview";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface ScanExploreStepProps {
  selectedModuleId: string;
  modules: KnowledgeModule[];
  repoId: string;
  onFixScope?: () => void;
  onModuleDeleted?: () => void;
}

function StatCard({ label, value }: { label: string; value?: number | string }) {
  return (
    <div className="rounded-lg border bg-muted/30 p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold tabular-nums">{value ?? "—"}</p>
    </div>
  );
}

export function ScanExploreStep({
  selectedModuleId,
  modules,
  repoId,
  onFixScope,
  onModuleDeleted,
}: ScanExploreStepProps) {
  const queryClient = useQueryClient();
  const [scanning, setScanning] = useState(false);
  const [scanLog, setScanLog] = useState<string[]>([]);
  const [entities, setEntities] = useState<string[]>([]);
  const [showDelete, setShowDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const selectedModule = modules.find((m) => m.id === selectedModuleId);

  const { data: moduleStatus, refetch: refetchStatus } = useQuery({
    queryKey: ["module-status", selectedModuleId],
    queryFn: () => api.getModuleStatus(selectedModuleId),
    refetchInterval: (query) => {
      const status = query.state.data?.scan_status;
      return scanning || status === "scanning" ? 3000 : false;
    },
  });

  const stats = moduleStatus?.stats || {};
  const scanComplete = moduleStatus?.scan_status === "completed";
  const scanFailed = moduleStatus?.scan_status === "failed";

  const scanFailureMessage = useMemo(() => {
    if (moduleStatus?.scan_status === "failed" && moduleStatus.scan_error) {
      return moduleStatus.scan_error;
    }
    if (selectedModule?.scan_status === "failed" && selectedModule.scan_error) {
      return selectedModule.scan_error;
    }
    const failedLog = [...scanLog]
      .reverse()
      .find((line) => line.toLowerCase().includes("failed") || line.toLowerCase().includes("error"));
    return failedLog ?? null;
  }, [moduleStatus, selectedModule, scanLog]);

  const finalizeScan = async (failedMessage?: string) => {
    setScanning(false);
    await refetchStatus();
    await queryClient.invalidateQueries({ queryKey: ["knowledge-modules", repoId] });
    if (failedMessage) {
      setScanLog((prev) => (prev.includes(failedMessage) ? prev : [...prev, failedMessage]));
      toast.error(failedMessage);
    }
  };

  useEffect(() => {
    if (!scanning) return;
    if (moduleStatus?.scan_status === "failed" && moduleStatus.scan_error) {
      void finalizeScan(moduleStatus.scan_error);
    }
  }, [scanning, moduleStatus?.scan_status, moduleStatus?.scan_error]);

  const handleScan = async () => {
    setScanning(true);
    setScanLog(["Starting scan…"]);
    setEntities([]);
    try {
      await api.startModuleScan(selectedModuleId);

      const consumeStream = async () => {
        try {
          for await (const event of api.streamModuleScan(selectedModuleId)) {
            if (event.event_type === "heartbeat") continue;
            const msg = event.message || event.event_type;
            if (msg) {
              setScanLog((prev) => (prev[prev.length - 1] === msg ? prev : [...prev, msg]));
              if (event.event_type.includes("entity") || event.event_type.includes("extract")) {
                setEntities((prev) => [...prev.slice(-19), msg]);
              }
            }
            if (event.event_type === "scan_completed") {
              await finalizeScan();
              toast.success("Scan completed");
              return;
            }
            if (event.event_type === "scan_failed") {
              await finalizeScan(event.message || "Scan failed");
              return;
            }
          }
        } catch (streamError) {
          const streamMsg =
            streamError instanceof Error ? streamError.message : "Scan stream disconnected";
          setScanLog((prev) => [...prev, streamMsg]);
        }

        const status = await api.getModuleStatus(selectedModuleId);
        if (status.scan_status === "completed") {
          await finalizeScan();
          toast.success("Scan completed");
        } else if (status.scan_status === "failed") {
          await finalizeScan(status.scan_error || "Scan failed");
        } else if (status.scan_status === "scanning") {
          setScanLog((prev) =>
            prev.includes("Scan still running…") ? prev : [...prev, "Scan still running…"]
          );
        } else {
          await finalizeScan("Scan ended before completion. Try again.");
        }
      };

      void consumeStream();
    } catch (e) {
      setScanning(false);
      toast.error(e instanceof Error ? e.message : "Scan failed");
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await api.deleteKnowledgeModule(selectedModuleId);
      toast.success("Module deleted");
      await queryClient.invalidateQueries({ queryKey: ["knowledge-modules", repoId] });
      setShowDelete(false);
      onModuleDeleted?.();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  };

  const statusBadge = useMemo(() => {
    const status = moduleStatus?.scan_status || selectedModule?.scan_status || "pending";
    const variant =
      status === "completed"
        ? "default"
        : status === "scanning"
          ? "secondary"
          : status === "failed"
            ? "destructive"
            : "outline";
    return <Badge variant={variant}>{status}</Badge>;
  }, [moduleStatus, selectedModule]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">{selectedModule?.name || "Module"}</h2>
          {selectedModule?.scope_path && (
            <p className="mt-1 font-mono text-xs text-muted-foreground">{selectedModule.scope_path}</p>
          )}
          <div className="mt-2 flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Status:</span>
            {statusBadge}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={handleScan} disabled={scanning}>
            <Scan className="mr-2 h-4 w-4" />
            {scanning ? "Scanning…" : "Scan Module"}
          </Button>
          <Button variant="outline" asChild disabled={!scanComplete}>
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
          <Button variant="outline" asChild>
            <Link href={`/knowledge/globe?module=${selectedModuleId}`}>
              <Globe className="mr-2 h-4 w-4" />
              3D Graph
            </Link>
          </Button>
          <Button variant="ghost" size="icon" onClick={() => setShowDelete(true)} title="Delete module">
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </div>

      {(scanFailed || scanFailureMessage) && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4">
          <p className="text-sm font-medium text-destructive">Scan failed</p>
          <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">
            {scanFailureMessage || "The scan could not complete. Check the scope path and try again."}
          </p>
          <div className="mt-3 flex gap-2">
            {onFixScope && (
              <Button size="sm" variant="outline" onClick={onFixScope}>
                <Wrench className="mr-2 h-3.5 w-3.5" />
                Fix scope
              </Button>
            )}
            <Button size="sm" variant="destructive" onClick={() => setShowDelete(true)}>
              <Trash2 className="mr-2 h-3.5 w-3.5" />
              Delete module
            </Button>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <ScanProgressPanel scanning={scanning} scanLog={scanLog} entities={entities} />
        <PremiumCard title="Knowledge Graph" noPadding>
          <MiniGraphPreview moduleId={selectedModuleId} height={320} showLabels />
        </PremiumCard>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Indexed Files" value={stats.indexed_files as number} />
        <StatCard label="Entities" value={stats.entities as number} />
        <StatCard label="Apex Classes" value={stats.apex_classes as number} />
        <StatCard label="LWC Components" value={stats.lwc_components as number} />
        <StatCard label="Objects" value={stats.objects as number} />
        <StatCard label="Flows" value={stats.flows as number} />
        <StatCard label="Fields" value={stats.fields as number} />
        <StatCard label="Business Rules" value={stats.business_rules as number} />
      </div>

      <div className="flex flex-wrap gap-2">
        <Badge variant="outline">Graph: {moduleStatus?.graph_status || "pending"}</Badge>
        <Badge variant="outline">Vector: {moduleStatus?.vector_status || "pending"}</Badge>
        <Badge variant="outline">AI: {moduleStatus?.ai_status || "pending"}</Badge>
      </div>

      <Dialog open={showDelete} onOpenChange={setShowDelete}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete module?</DialogTitle>
            <DialogDescription>
              This removes scan artifacts, graph data, and vectors for &quot;{selectedModule?.name}&quot;.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDelete(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} loading={deleting}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
