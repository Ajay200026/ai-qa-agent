"use client";

import { motion } from "framer-motion";
import {
  Brain,
  CheckCircle2,
  Circle,
  Database,
  GitBranch,
  Loader2,
  Network,
  Sparkles,
} from "lucide-react";
import { PremiumCard } from "@/components/ui/premium-card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

const STAGES = [
  { key: "sync", label: "Sync Repository", icon: GitBranch },
  { key: "enumerate", label: "Enumerate Files", icon: Database },
  { key: "extract", label: "Extract Entities", icon: Brain },
  { key: "graph", label: "Build Graph", icon: Network },
  { key: "vector", label: "Index Vectors", icon: Sparkles },
  { key: "complete", label: "Complete", icon: CheckCircle2 },
];

interface ScanProgressPanelProps {
  scanning: boolean;
  scanLog: string[];
  entities: string[];
}

function inferStage(log: string[]): number {
  const text = log.join(" ").toLowerCase();
  if (text.includes("complete") || text.includes("scan_completed")) return 5;
  if (text.includes("vector") || text.includes("index") || text.includes("chroma")) return 4;
  if (text.includes("graph") || text.includes("neo4j")) return 3;
  if (text.includes("extract") || text.includes("entity")) return 2;
  if (text.includes("enumerat") || text.includes("file")) return 1;
  if (text.includes("sync") || text.includes("clone") || text.includes("fetch")) return 0;
  return Math.min(log.length, 5);
}

export function ScanProgressPanel({ scanning, scanLog, entities }: ScanProgressPanelProps) {
  const activeStage = scanning ? inferStage(scanLog) : scanLog.length > 0 ? 5 : -1;

  return (
    <PremiumCard title="Scan Progress" description={scanning ? "Processing module…" : "Ready to scan"}>
      <div className="space-y-4">
        <div className="space-y-2">
          {STAGES.map((stage, i) => {
            const Icon = stage.icon;
            const done = activeStage > i;
            const active = activeStage === i;
            return (
              <motion.div
                key={stage.key}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 transition-colors",
                  active && "bg-primary/10",
                  done && "text-green-600 dark:text-green-400"
                )}
              >
                {scanning && active ? (
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                ) : done ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <Circle className="h-4 w-4 text-muted-foreground/40" />
                )}
                <Icon className="h-4 w-4 shrink-0" />
                <span className="text-sm">{stage.label}</span>
              </motion.div>
            );
          })}
        </div>

        {entities.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">Recent entities</p>
            <ScrollArea className="h-24 rounded-md border bg-muted/20 p-2">
              {entities.map((e, i) => (
                <p key={i} className="truncate text-xs text-muted-foreground">
                  {e}
                </p>
              ))}
            </ScrollArea>
          </div>
        )}

        {scanLog.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">Log</p>
            <ScrollArea className="h-20 rounded-md border bg-muted/20 p-2">
              {scanLog.slice(-8).map((line, i) => (
                <p key={i} className="text-xs text-muted-foreground">
                  {line}
                </p>
              ))}
            </ScrollArea>
          </div>
        )}
      </div>
    </PremiumCard>
  );
}
