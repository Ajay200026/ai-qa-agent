"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";

export default function ReportDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  const { data: report } = useQuery({
    queryKey: ["report", id],
    queryFn: () => api.getReport(id),
  });

  if (!report) {
    return <p className="text-muted-foreground">Loading report...</p>;
  }

  const passed = report.failed_count === 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Report</h1>
          <p className="font-mono text-sm text-muted-foreground">{report.id}</p>
        </div>
        <Badge variant={passed ? "success" : "destructive"} className="text-lg px-4 py-1">
          {passed ? "PASSED" : "FAILED"}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Passed Tests</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold text-green-600">
            {report.passed_count}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Failed Tests</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold text-red-600">
            {report.failed_count}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Created</CardTitle>
          </CardHeader>
          <CardContent>{formatDate(report.created_at)}</CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Execution Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="whitespace-pre-wrap rounded-lg bg-muted p-4 text-sm">
            {report.summary}
          </pre>
        </CardContent>
      </Card>

      {report.llm_analysis && (
        <Card>
          <CardHeader>
            <CardTitle>LLM Analysis</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap rounded-lg bg-muted p-4 text-sm">
              {report.llm_analysis}
            </pre>
          </CardContent>
        </Card>
      )}

      {report.artifacts_path && (
        <Card>
          <CardHeader>
            <CardTitle>Screenshots & Artifacts</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Artifacts stored at: {report.artifacts_path}
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Screenshots are captured per step during execution. Access via the execution detail page.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
