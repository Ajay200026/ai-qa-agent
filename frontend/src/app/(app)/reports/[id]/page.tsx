"use client";

import { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { downloadReportFile, artifactFilename } from "@/lib/artifacts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScreenshotThumbnail } from "@/components/artifacts/screenshot-lightbox";
import { formatDate } from "@/lib/utils";
import { ReportSkeleton } from "@/components/loading/report-skeleton";
import { Download, FileText } from "lucide-react";
import { Spinner } from "@/components/ui/spinner";

export default function ReportDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [downloading, setDownloading] = useState<"zip" | "pdf" | null>(null);
  const [downloadError, setDownloadError] = useState("");

  const { data: report, isLoading } = useQuery({
    queryKey: ["report", id],
    queryFn: () => api.getReport(id),
  });

  const { data: execution } = useQuery({
    queryKey: ["execution", report?.execution_id],
    queryFn: () => api.getExecution(report!.execution_id),
    enabled: !!report?.execution_id,
  });

  const { data: artifactList } = useQuery({
    queryKey: ["artifacts", report?.execution_id],
    queryFn: () => api.listArtifacts(report!.execution_id),
    enabled: !!report?.execution_id,
  });

  const handleDownload = async (format: "zip" | "pdf") => {
    setDownloading(format);
    setDownloadError("");
    try {
      await downloadReportFile(id, format);
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDownloading(null);
    }
  };

  if (isLoading || !report) {
    return <ReportSkeleton />;
  }

  const passed = report.failed_count === 0;
  const executionId = report.execution_id;
  const stepsWithScreenshots = (execution?.steps ?? []).filter((s) => s.screenshot_path);
  const stepFilenames = new Set(
    stepsWithScreenshots.map((s) => artifactFilename(s.screenshot_path!))
  );
  const extraArtifacts = (artifactList?.files ?? []).filter((f) => !stepFilenames.has(f));

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold sm:text-3xl">Report</h1>
          <p className="break-all font-mono text-xs text-muted-foreground sm:text-sm">{report.id}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={passed ? "success" : "destructive"} className="w-fit px-4 py-1 text-base sm:text-lg">
            {passed ? "PASSED" : "FAILED"}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            disabled={!!downloading}
            onClick={() => handleDownload("zip")}
          >
            {downloading === "zip" ? (
              <Spinner size="sm" className="mr-2" />
            ) : (
              <Download className="mr-2 h-4 w-4" />
            )}
            Download ZIP
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!!downloading}
            onClick={() => handleDownload("pdf")}
          >
            {downloading === "pdf" ? (
              <Spinner size="sm" className="mr-2" />
            ) : (
              <FileText className="mr-2 h-4 w-4" />
            )}
            Download PDF
          </Button>
        </div>
      </div>

      {downloadError && (
        <p className="text-sm text-destructive">{downloadError}</p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
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

      {stepsWithScreenshots.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Step Screenshots</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {stepsWithScreenshots.map((step) => (
                <div key={step.id} className="space-y-2 rounded-lg border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium">
                      {step.seq}. {step.name}
                    </p>
                    <Badge
                      variant={
                        step.status === "passed"
                          ? "success"
                          : step.status === "failed"
                            ? "destructive"
                            : "secondary"
                      }
                      className="capitalize"
                    >
                      {step.status}
                    </Badge>
                  </div>
                  <ScreenshotThumbnail
                    executionId={executionId}
                    screenshotPath={step.screenshot_path!}
                    alt={`Step ${step.seq} screenshot`}
                    className="w-full max-h-40 object-contain"
                  />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {extraArtifacts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>All Artifacts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {extraArtifacts.map((filename) => (
                <div key={filename} className="space-y-2 rounded-lg border p-3">
                  <p className="truncate text-xs font-mono text-muted-foreground">{filename}</p>
                  <ScreenshotThumbnail
                    executionId={executionId}
                    screenshotPath={filename}
                    alt={filename}
                    className="w-full max-h-40 object-contain"
                  />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
