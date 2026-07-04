"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useEdgesState,
  useNodesState,
  type Node,
  type Edge,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";

import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { AgentModeToggle } from "@/components/knowledge/AgentModeToggle";
import { Button } from "@/components/ui/button";
import { PageLoading } from "@/components/loading/page-loading";
import type { EntityDetail, GraphNode } from "@/lib/types";

const NODE_COLORS: Record<string, string> = {
  Module: "#6366f1",
  LwcComponent: "#22c55e",
  ApexClass: "#3b82f6",
  ApexTrigger: "#2563eb",
  SObject: "#f59e0b",
  Field: "#eab308",
  Flow: "#a855f7",
  ValidationRule: "#ef4444",
  Layout: "#64748b",
  PermissionSet: "#14b8a6",
  Reference: "#94a3b8",
};

const NODE_WIDTH = 180;
const NODE_HEIGHT = 48;

function layoutGraph(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 80 });

  nodes.forEach((node) => {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });
  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  return nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
    };
  });
}

export default function KnowledgeGraphPage() {
  const searchParams = useSearchParams();
  const moduleId = searchParams.get("module") || localStorage.getItem("knowledge_selected_module");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [entityDetail, setEntityDetail] = useState<EntityDetail | null>(null);

  const { data: graph, isLoading, error } = useQuery({
    queryKey: ["knowledge-graph", moduleId],
    queryFn: () => api.getModuleGraph(moduleId!),
    enabled: !!moduleId,
  });

  const initialNodes: Node[] = useMemo(
    () =>
      (graph?.nodes || []).map((n) => ({
        id: n.id,
        data: { label: n.label || n.name, type: n.type, node: n },
        position: { x: 0, y: 0 },
        style: {
          background: NODE_COLORS[n.type] || "#e2e8f0",
          color: "#fff",
          border: "none",
          borderRadius: 8,
          fontSize: 12,
          padding: "8px 12px",
          width: NODE_WIDTH,
        },
      })),
    [graph]
  );

  const initialEdges: Edge[] = useMemo(
    () =>
      (graph?.edges || []).map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.relationship,
        animated: e.relationship === "CALLS",
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { strokeWidth: 1.5 },
        labelStyle: { fontSize: 10 },
      })),
    [graph]
  );

  const layoutedNodes = useMemo(
    () => layoutGraph(initialNodes, initialEdges),
    [initialNodes, initialEdges]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(layoutedNodes);
    setEdges(initialEdges);
  }, [layoutedNodes, initialEdges, setNodes, setEdges]);

  const onNodeClick = useCallback(async (_: React.MouseEvent, node: Node) => {
    const graphNode = node.data?.node as GraphNode;
    setSelectedNode(graphNode);
    setEntityDetail(null);
    const entityId = graphNode.entity_id;
    if (entityId) {
      try {
        const detail = await api.getKnowledgeEntity(entityId);
        setEntityDetail(detail);
      } catch {
        // entity detail optional
      }
    }
  }, []);

  if (!moduleId) {
    return (
      <div className="space-y-4">
        <PageHeader title="Dependency Graph" description="Select and scan a module from the Knowledge overview first." />
      </div>
    );
  }

  if (isLoading) return <PageLoading label="Loading graph..." />;
  if (error) {
    return (
      <div className="space-y-4">
        <PageHeader title="Dependency Graph" />
        <p className="text-destructive">Failed to load graph. Run a scan first.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Dependency Graph"
        description={`${graph?.nodes.length ?? 0} nodes, ${graph?.edges.length ?? 0} relationships`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <AgentModeToggle />
            <Button variant="outline" size="sm" asChild>
              <Link href={`/knowledge/globe?module=${moduleId}`}>3D Globe</Link>
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            <div className="h-[70vh] w-full">
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                fitView
                minZoom={0.1}
                maxZoom={2}
              >
                <Background />
                <Controls />
                <MiniMap nodeColor={(n) => NODE_COLORS[(n.data as { type?: string })?.type || ""] || "#ccc"} />
              </ReactFlow>
            </div>
          </CardContent>
        </Card>

        <Card className="h-[70vh] overflow-y-auto">
          <CardHeader>
            <CardTitle className="text-base">
              {selectedNode ? selectedNode.name : "Node Details"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            {!selectedNode ? (
              <p className="text-muted-foreground">Click a node to view details, dependencies, and navigation path.</p>
            ) : (
              <>
                <div className="flex flex-wrap gap-2">
                  <Badge>{selectedNode.type}</Badge>
                  {selectedNode.file_path && (
                    <Badge variant="outline" className="max-w-full truncate">
                      {selectedNode.file_path}
                    </Badge>
                  )}
                </div>
                {entityDetail?.summary && (
                  <div>
                    <p className="mb-1 font-medium">Summary</p>
                    <p className="text-muted-foreground">{entityDetail.summary}</p>
                  </div>
                )}
                {entityDetail?.business_rules && entityDetail.business_rules.length > 0 && (
                  <div>
                    <p className="mb-1 font-medium">Business Rules</p>
                    <ul className="list-inside list-disc text-muted-foreground">
                      {entityDetail.business_rules.map((rule, i) => (
                        <li key={i}>{rule}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {entityDetail?.dependencies && entityDetail.dependencies.length > 0 && (
                  <div>
                    <p className="mb-1 font-medium">Dependencies</p>
                    <ul className="space-y-1">
                      {entityDetail.dependencies.map((dep, i) => (
                        <li key={i} className="text-muted-foreground">
                          {dep.name} <span className="text-xs">({dep.type})</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {entityDetail?.navigation_path && entityDetail.navigation_path.length > 0 && (
                  <div>
                    <p className="mb-1 font-medium">Navigation Path</p>
                    <ol className="list-inside list-decimal text-muted-foreground">
                      {entityDetail.navigation_path.map((step, i) => (
                        <li key={i}>{step}</li>
                      ))}
                    </ol>
                  </div>
                )}
                {entityDetail?.related_files && entityDetail.related_files.length > 0 && (
                  <div>
                    <p className="mb-1 font-medium">Related Files</p>
                    <ul className="text-xs text-muted-foreground">
                      {entityDetail.related_files.map((f, i) => (
                        <li key={i} className="break-all">{f}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
