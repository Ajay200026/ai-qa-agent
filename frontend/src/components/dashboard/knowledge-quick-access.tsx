"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Brain, ChevronRight, FolderGit2 } from "lucide-react";
import { motion } from "framer-motion";

import { api } from "@/lib/api";
import { PremiumCard } from "@/components/ui/premium-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function KnowledgeQuickAccess() {
  const { data: repos = [] } = useQuery({
    queryKey: ["knowledge-repos"],
    queryFn: () => api.listKnowledgeRepos(),
  });

  const { data: connections = [] } = useQuery({
    queryKey: ["azure-connections"],
    queryFn: () => api.listAzureConnections(),
  });

  const firstRepo = repos[0];
  const { data: modules = [] } = useQuery({
    queryKey: ["knowledge-modules", firstRepo?.id],
    queryFn: () => api.listKnowledgeModules(firstRepo!.id),
    enabled: !!firstRepo?.id,
  });

  const scannedModule = modules.find((m) => m.scan_status === "completed");

  const pipelineStatus = [
    { label: "Azure", done: connections.length > 0 },
    { label: "Repo", done: repos.length > 0 },
    { label: "Module", done: modules.length > 0 },
    { label: "Scanned", done: !!scannedModule },
  ];

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
      <PremiumCard
        title="Knowledge Platform"
        description="Azure DevOps → Module → Graph pipeline"
        headerAction={
          <Button variant="outline" size="sm" asChild>
            <Link href="/knowledge">
              Open
              <ChevronRight className="ml-1 h-4 w-4" />
            </Link>
          </Button>
        }
      >
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary" />
            <div>
              <p className="text-2xl font-bold">{repos.length}</p>
              <p className="text-xs text-muted-foreground">Repositories</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <FolderGit2 className="h-5 w-5 text-primary" />
            <div>
              <p className="text-2xl font-bold">{modules.length}</p>
              <p className="text-xs text-muted-foreground">Modules</p>
            </div>
          </div>
          {scannedModule && (
            <Badge variant="default" className="ml-auto">
              Last scan: {scannedModule.name}
            </Badge>
          )}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {pipelineStatus.map((s) => (
            <Badge key={s.label} variant={s.done ? "default" : "outline"}>
              {s.label} {s.done ? "✓" : "—"}
            </Badge>
          ))}
        </div>
      </PremiumCard>
    </motion.div>
  );
}
