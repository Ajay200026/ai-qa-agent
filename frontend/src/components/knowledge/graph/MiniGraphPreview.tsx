"use client";

import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ReactFlow,
  Background,
  useEdgesState,
  useNodesState,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import Link from "next/link";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

const NODE_COLORS: Record<string, string> = {
  Module: "#8b5cf6",
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

const NODE_WIDTH = 120;
const NODE_HEIGHT = 36;

function layoutGraph(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 50 });
  nodes.forEach((node) => g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
  edges.forEach((edge) => g.setEdge(edge.source, edge.target));
  dagre.layout(g);
  return nodes.map((node) => {
    const pos = g.node(node.id);
    return { ...node, position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 } };
  });
}

interface MiniGraphPreviewProps {
  moduleId: string;
  height?: number;
  showLabels?: boolean;
}

export function MiniGraphPreview({ moduleId, height = 300, showLabels = false }: MiniGraphPreviewProps) {
  const { data: graph, isLoading, error } = useQuery({
    queryKey: ["knowledge-graph", moduleId],
    queryFn: () => api.getModuleGraph(moduleId),
    enabled: !!moduleId,
  });

  const initialNodes: Node[] = useMemo(
    () =>
      (graph?.nodes || []).slice(0, 40).map((n) => ({
        id: n.id,
        data: { label: n.label || n.name },
        position: { x: 0, y: 0 },
        style: {
          background: NODE_COLORS[n.type] || "#6366f1",
          color: "#fff",
          border: "none",
          borderRadius: 6,
          fontSize: showLabels ? 9 : 10,
          padding: "4px 8px",
          width: showLabels ? 140 : NODE_WIDTH,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        },
      })),
    [graph]
  );

  const initialEdges: Edge[] = useMemo(
    () =>
      (graph?.edges || [])
        .filter((e) => initialNodes.some((n) => n.id === e.source) && initialNodes.some((n) => n.id === e.target))
        .map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          animated: true,
          style: { stroke: "hsl(var(--primary))", strokeWidth: 1 },
        })),
    [graph, initialNodes]
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center text-sm text-muted-foreground" style={{ height }}>
        Loading graph…
      </div>
    );
  }

  if (error || !graph?.nodes.length) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 p-6 text-center" style={{ height }}>
        <p className="text-sm text-muted-foreground">Run a scan to generate the dependency graph.</p>
      </div>
    );
  }

  return (
    <div className="relative" style={{ height }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
        minZoom={0.3}
        maxZoom={1}
      >
        <Background gap={16} size={1} className="opacity-30" />
      </ReactFlow>
      <div className="absolute bottom-2 right-2">
        <Button variant="secondary" size="sm" asChild>
          <Link href={`/knowledge/graph?module=${moduleId}`}>Open full graph</Link>
        </Button>
      </div>
    </div>
  );
}
