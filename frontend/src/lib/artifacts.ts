import { API_URL, api } from "./api";
import { getFirebaseIdToken } from "./firebase";

export function artifactFilename(screenshotPath: string): string {
  return screenshotPath.split(/[/\\]/).pop() || screenshotPath;
}

async function resolveToken(forceRefresh = false): Promise<string | null> {
  if (typeof window !== "undefined") {
    try {
      const fresh = await getFirebaseIdToken(forceRefresh);
      if (fresh) {
        localStorage.setItem("token", fresh);
        return fresh;
      }
    } catch {
      // Firebase unavailable
    }
  }
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

export async function fetchArtifactBlobUrl(
  executionId: string,
  screenshotPath: string,
  retried = false
): Promise<string> {
  const filename = artifactFilename(screenshotPath);
  const token = await resolveToken();
  const response = await fetch(
    `${API_URL}/reports/artifacts/${executionId}/${encodeURIComponent(filename)}`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }
  );

  if (!response.ok) {
    if (response.status === 401 && !retried) {
      const refreshed = await resolveToken(true);
      if (refreshed) {
        return fetchArtifactBlobUrl(executionId, screenshotPath, true);
      }
    }
    throw new Error("Screenshot not found");
  }

  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export async function downloadReportFile(
  reportId: string,
  format: "zip" | "pdf"
): Promise<void> {
  const blob = await api.downloadReport(reportId, format);
  downloadBlob(blob, `report-${reportId.slice(0, 8)}.${format}`);
}
