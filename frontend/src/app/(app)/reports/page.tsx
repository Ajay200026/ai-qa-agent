"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";

export default function ReportsPage() {
  const { data: reports = [] } = useQuery({
    queryKey: ["reports"],
    queryFn: () => api.getReports(),
    refetchInterval: 15000,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Reports</h1>
        <p className="text-muted-foreground">Execution reports and test results</p>
      </div>

      <Card>
        <CardContent className="p-0">
          <table className="w-full">
            <thead>
              <tr className="border-b text-left text-sm text-muted-foreground">
                <th className="p-4">Report ID</th>
                <th className="p-4">Passed</th>
                <th className="p-4">Failed</th>
                <th className="p-4">Result</th>
                <th className="p-4">Created</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {reports.map((report) => (
                <tr key={report.id} className="border-b">
                  <td className="p-4 font-mono text-xs">{report.id.slice(0, 8)}...</td>
                  <td className="p-4">{report.passed_count}</td>
                  <td className="p-4">{report.failed_count}</td>
                  <td className="p-4">
                    <Badge variant={report.failed_count === 0 ? "success" : "destructive"}>
                      {report.failed_count === 0 ? "PASSED" : "FAILED"}
                    </Badge>
                  </td>
                  <td className="p-4">{formatDate(report.created_at)}</td>
                  <td className="p-4">
                    <Link href={`/reports/${report.id}`}>
                      <Button variant="ghost" size="sm">View</Button>
                    </Link>
                  </td>
                </tr>
              ))}
              {reports.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-muted-foreground">
                    No reports yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
