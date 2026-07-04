"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { BrainNodeDetail, GraphNode } from "@/lib/types";

interface NodeDetailPanelProps {
  node: GraphNode | null;
  detail?: BrainNodeDetail | null;
}

export function NodeDetailPanel({ node, detail }: NodeDetailPanelProps) {
  if (!node) {
    return (
      <Card className="h-full">
        <CardContent className="pt-6 text-sm text-muted-foreground">
          Click a node on the globe to see details, file paths, and flow connections.
        </CardContent>
      </Card>
    );
  }

  const neighbors = detail?.neighbors ?? [];

  return (
    <Card className="h-full overflow-auto">
      <CardHeader>
        <CardTitle className="text-base">{node.label || node.name}</CardTitle>
        <Badge variant="secondary">{node.type}</Badge>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {(detail?.description || detail?.summary || node.summary) && (
          <p>{detail?.description || detail?.summary || node.summary}</p>
        )}
        {node.file_path && (
          <div>
            <p className="font-medium">File</p>
            <code className="text-xs">
              {node.file_path}
              {node.line_start ? `:${node.line_start}` : ""}
            </code>
          </div>
        )}
        {neighbors.length > 0 && (
          <div>
            <p className="mb-2 font-medium">Flow / connections</p>
            <ul className="space-y-1">
              {neighbors.slice(0, 12).map((n, i) => (
                <li key={i} className="text-muted-foreground">
                  {n.rel} → {n.node} ({n.node_type})
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
