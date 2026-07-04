"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import ForceGraph3D, { type ForceGraphMethods } from "react-force-graph-3d";
import type { GraphEdge, GraphNode } from "@/lib/types";

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
  Component: "#3b82f6",
  File: "#64748b",
  Function: "#14b8a6",
  BusinessLogic: "#f97316",
};

interface ForceNode {
  id: string;
  name: string;
  label: string;
  type: string;
  val: number;
}

interface ForceLink {
  id: string;
  source: string;
  target: string;
  relationship: string;
}

interface KnowledgeGlobeProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId?: string | null;
  onSelect?: (node: GraphNode | null) => void;
}

export function KnowledgeGlobe({ nodes, edges, selectedId, onSelect }: KnowledgeGlobeProps) {
  const graphRef = useRef<ForceGraphMethods<ForceNode, ForceLink> | undefined>(undefined);

  const graphData = useMemo(() => {
    const forceNodes: ForceNode[] = nodes.map((n) => ({
      id: n.id,
      name: n.name,
      label: n.label || n.name,
      type: n.type,
      val: n.type === "Module" ? 8 : 4,
    }));
    const forceLinks: ForceLink[] = edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      relationship: e.relationship,
    }));
    return { nodes: forceNodes, links: forceLinks };
  }, [nodes, edges]);

  const nodeById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  const handleNodeClick = useCallback(
    (node: ForceNode) => {
      const original = nodeById.get(node.id) ?? null;
      onSelect?.(original);
    },
    [nodeById, onSelect]
  );

  useEffect(() => {
    const fg = graphRef.current;
    if (!fg) return;
    fg.d3Force("charge")?.strength(-120);
    fg.d3Force("link")?.distance(40);
  }, [graphData]);

  if (graphData.nodes.length === 0) {
    return (
      <div className="flex h-[600px] items-center justify-center rounded-lg border bg-slate-950 text-sm text-slate-400">
        No graph data — run a module scan first.
      </div>
    );
  }

  return (
    <div className="h-[600px] w-full overflow-hidden rounded-lg border bg-slate-950">
      <ForceGraph3D
        ref={graphRef}
        graphData={graphData}
        backgroundColor="#020617"
        nodeLabel={(node) => `${node.label} (${node.type})`}
        linkLabel={(link) => link.relationship}
        nodeColor={(node) => NODE_COLORS[node.type] ?? "#94a3b8"}
        nodeVal={(node) => (node.id === selectedId ? node.val * 1.5 : node.val)}
        linkColor={(link) => (link.relationship === "CALLS" ? "#60a5fa" : "#475569")}
        linkOpacity={0.6}
        linkWidth={(link) => (link.relationship === "CALLS" ? 1.5 : 0.5)}
        linkDirectionalParticles={(link) => (link.relationship === "CALLS" ? 2 : 0)}
        linkDirectionalParticleWidth={2}
        onNodeClick={handleNodeClick}
        onBackgroundClick={() => onSelect?.(null)}
        showNavInfo={false}
      />
    </div>
  );
}
