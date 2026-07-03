"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import { downloadReportFile } from "@/lib/artifacts";
import { Download } from "lucide-react";

export default function ReportsPage() {
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const { data: reports = [] } = useQuery({
    queryKey: ["reports"],
    queryFn: () => api.getReports(),
    refetchInterval: 15000,
  });

  const handleDownload = async (reportId: string) => {
    setDownloadingId(reportId);
    try {
      await downloadReportFile(reportId, "zip");
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports"
        description="Execution reports and test results"
      />

      <Card>
        <CardContent className="p-0">
          {reports.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">No reports yet</p>
          ) : (
            <>
              <div className="space-y-3 p-4 md:hidden">
                {reports.map((report) => (
                  <div key={report.id} className="rounded-lg border p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-mono text-xs">{report.id}</p>
                        <p className="mt-2 text-sm text-muted-foreground">
                          Passed {report.passed_count} · Failed {report.failed_count}
                        </p>
                        <p className="text-sm text-muted-foreground">{formatDate(report.created_at)}</p>
                      </div>
                      <Badge variant={report.failed_count === 0 ? "success" : "destructive"}>
                        {report.failed_count === 0 ? "PASSED" : "FAILED"}
                      </Badge>
                    </div>
                    <div className="mt-3 flex gap-2">
                      <Link href={`/reports/${report.id}`} className="flex-1">
                        <Button variant="outline" size="sm" className="w-full">
                          View
                        </Button>
                      </Link>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={downloadingId === report.id}
                        onClick={() => handleDownload(report.id)}
                        aria-label="Download ZIP"
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="hidden overflow-x-auto md:block">
                <table className="w-full min-w-[720px]">
                  <thead>
                    <tr className="border-b text-left text-sm text-muted-foreground">
                      <th className="p-4">Report ID</th>
                      <th className="p-4">Passed</th>
                      <th className="p-4">Failed</th>
                      <th className="p-4">Result</th>
                      <th className="p-4">Created</th>
                      <th className="p-4" />
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
                          <div className="flex items-center gap-1">
                            <Link href={`/reports/${report.id}`}>
                              <Button variant="ghost" size="sm">
                                View
                              </Button>
                            </Link>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={downloadingId === report.id}
                              onClick={() => handleDownload(report.id)}
                              aria-label="Download ZIP"
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
