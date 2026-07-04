import type { GraphNode } from "@/lib/types";

const ORBIT_RADIUS: Record<number, number> = {
  0: 0,
  1: 4,
  2: 6,
  3: 8,
  4: 10,
  5: 12,
};

export function layoutGlobeNodes(nodes: GraphNode[]): Map<string, [number, number, number]> {
  const positions = new Map<string, [number, number, number]>();
  const byLevel = new Map<number, GraphNode[]>();

  for (const node of nodes) {
    const level = node.orbit_level ?? orbitLevelForType(node.type);
    if (!byLevel.has(level)) byLevel.set(level, []);
    byLevel.get(level)!.push(node);
  }

  for (const [level, group] of byLevel) {
    const radius = ORBIT_RADIUS[level] ?? 8;
    group.forEach((node, i) => {
      const phi = Math.acos(1 - (2 * (i + 0.5)) / Math.max(group.length, 1));
      const theta = Math.PI * (1 + Math.sqrt(5)) * i;
      const x = radius * Math.sin(phi) * Math.cos(theta);
      const y = radius * Math.sin(phi) * Math.sin(theta);
      const z = radius * Math.cos(phi);
      positions.set(node.id, [x, y, z]);
    });
  }

  return positions;
}

function orbitLevelForType(type: string): number {
  const map: Record<string, number> = {
    Repository: 0,
    Module: 1,
    Component: 2,
    File: 2,
    LwcComponent: 3,
    ApexClass: 3,
    Flow: 3,
    Function: 3,
    BusinessLogic: 4,
    Field: 4,
    Scenario: 5,
    Defect: 5,
    VisionMemory: 5,
  };
  return map[type] ?? 3;
}

export const NODE_COLORS: Record<string, string> = {
  Repository: "#6366f1",
  Module: "#8b5cf6",
  Component: "#3b82f6",
  LwcComponent: "#06b6d4",
  ApexClass: "#10b981",
  Flow: "#f59e0b",
  Function: "#14b8a6",
  File: "#64748b",
  Field: "#ec4899",
  BusinessLogic: "#f97316",
  Scenario: "#a855f7",
  Defect: "#ef4444",
  VisionMemory: "#84cc16",
};
