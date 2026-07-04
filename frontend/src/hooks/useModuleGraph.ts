"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { GraphEdge, GraphNode } from "@/lib/types";

const MAX_SUBGRAPH_NODES = 80;

function buildSubgraph(nodes: GraphNode[], edges: GraphEdge[]): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const moduleNode = nodes.find((n) => n.type === "Module");
  if (!moduleNode) {
    return { nodes: nodes.slice(0, MAX_SUBGRAPH_NODES), edges: edges.slice(0, 120) };
  }

  const keep = new Set<string>([moduleNode.id]);
  for (const edge of edges) {
    if (edge.source === moduleNode.id) keep.add(edge.target);
    if (edge.target === moduleNode.id) keep.add(edge.source);
  }

  const filteredNodes = nodes.filter((n) => keep.has(n.id)).slice(0, MAX_SUBGRAPH_NODES);
  const nodeIds = new Set(filteredNodes.map((n) => n.id));
  const filteredEdges = edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));

  return { nodes: filteredNodes, edges: filteredEdges };
}

export function useModuleGraph(moduleId: string | null | undefined, subgraphOnly = false) {
  const query = useQuery({
    queryKey: ["knowledge-graph", moduleId, subgraphOnly ? "subgraph" : "full"],
    queryFn: () => api.getModuleGraph(moduleId!),
    enabled: !!moduleId,
  });

  const graph = useMemo(() => {
    if (!query.data) return undefined;
    if (!subgraphOnly) return query.data;
    const { nodes, edges } = buildSubgraph(query.data.nodes, query.data.edges);
    return { ...query.data, nodes, edges };
  }, [query.data, subgraphOnly]);

  return { ...query, data: graph };
}
