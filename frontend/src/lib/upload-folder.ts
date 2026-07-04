export const SKIP_DIR_SEGMENTS = new Set([
  ".git",
  "node_modules",
  ".sfdx",
  ".sf",
  "coverage",
  ".husky",
]);

export const UPLOAD_BATCH_SIZE = 150;

export interface UploadManifestEntry {
  fileName: string;
  relativePath: string;
  fullPath: string;
  extension: string;
  size: number;
}

export function getRelativePath(file: File): string {
  return (file.webkitRelativePath || file.name).replace(/\\/g, "/");
}

export function shouldUploadFile(file: File): boolean {
  if (file.size === 0) return false;
  const rel = getRelativePath(file);
  const segments = rel.split("/").filter(Boolean);
  if (segments.some((seg) => SKIP_DIR_SEGMENTS.has(seg))) return false;
  const base = segments[segments.length - 1] || file.name;
  if (base.startsWith(".")) return false;
  return true;
}

export function normalizeSfdxPaths(paths: string[]): string[] {
  if (paths.length === 0) return paths;
  const hasForceApp = paths.some(
    (p) => p.startsWith("force-app/") || p.includes("/force-app/")
  );
  if (hasForceApp) return paths;
  const hasMainDefault = paths.some(
    (p) => p.startsWith("main/default/") || p.startsWith("main\\default\\")
  );
  if (hasMainDefault) return paths.map((p) => `force-app/${p.replace(/\\/g, "/")}`);
  return paths;
}

export function prepareFolderUpload(files: FileList): {
  files: File[];
  paths: string[];
  manifest: UploadManifestEntry[];
} {
  const filtered = Array.from(files).filter(shouldUploadFile);
  const rawPaths = filtered.map(getRelativePath);
  const paths = normalizeSfdxPaths(rawPaths);
  const manifest = filtered.map((file, i) => {
    const relativePath = paths[i];
    const segments = relativePath.split("/");
    const fileName = segments[segments.length - 1] || file.name;
    const dot = fileName.lastIndexOf(".");
    return {
      fileName,
      relativePath,
      fullPath: relativePath,
      extension: dot >= 0 ? fileName.slice(dot) : "",
      size: file.size,
    };
  });
  return { files: filtered, paths, manifest };
}

export function chunkFiles<T>(items: T[], size = UPLOAD_BATCH_SIZE): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    chunks.push(items.slice(i, i + size));
  }
  return chunks;
}
