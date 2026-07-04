"use client";

import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import Link from "next/link";

import { PageHeader } from "@/components/layout/page-header";
import { AgentModeToggle } from "@/components/knowledge/AgentModeToggle";
import { NodeDetailPanel } from "@/components/knowledge/brain/NodeDetailPanel";
import type { GraphNode } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useModuleGraph } from "@/hooks/useModuleGraph";

const KnowledgeGlobe = dynamic(
  () => import("@/components/knowledge/brain/KnowledgeGlobe").then((m) => m.KnowledgeGlobe),
  { ssr: false, loading: () => <div className="h-[600px] animate-pulse rounded-lg bg-muted" /> }
);

export default function KnowledgeGlobePage() {
  const params = useSearchParams();
  const moduleId =
    params.get("module") ||
    (typeof window !== "undefined" ? localStorage.getItem("knowledge_selected_module") : null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [subgraphOnly, setSubgraphOnly] = useState(true);

  const { data: graph, isLoading } = useModuleGraph(moduleId, subgraphOnly);

  const { data: detail } = useQuery({
    queryKey: ["brain-node", selected?.id],
    queryFn: () => api.getBrainNode(selected!.id),
    enabled: !!selected?.id,
  });

  return (
    <div className="space-y-4">
      <PageHeader
        title="Module Dependency Graph (3D)"
        description="Force-directed 3D subgraph with labeled nodes and relationships"
        actions={
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <Button
                variant={subgraphOnly ? "default" : "outline"}
                size="sm"
                onClick={() => setSubgraphOnly(true)}
              >
                Scope + deps
              </Button>
              <Button
                variant={!subgraphOnly ? "default" : "outline"}
                size="sm"
                onClick={() => setSubgraphOnly(false)}
              >
                Full module
              </Button>
            </div>
            <AgentModeToggle />
            {moduleId && (
              <Button variant="outline" size="sm" asChild>
                <Link href={`/knowledge/graph?module=${moduleId}`}>2D Graph</Link>
              </Button>
            )}
          </div>
        }
      />
      {!moduleId ? (
        <p className="text-muted-foreground">Select a module from Knowledge Overview first.</p>
      ) : isLoading ? (
        <p>Loading dependency graph…</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <KnowledgeGlobe
              nodes={graph?.nodes ?? []}
              edges={graph?.edges ?? []}
              selectedId={selected?.id}
              onSelect={setSelected}
            />
          </div>
          <NodeDetailPanel node={selected} detail={detail} />
        </div>
      )}
    </div>
  );
}
