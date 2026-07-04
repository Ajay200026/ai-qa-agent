"use client";

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { FolderUp, Upload } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { PremiumCard } from "@/components/ui/premium-card";

interface UploadCodebaseStepProps {
  onUploaded: (repoId: string) => void;
}

export function UploadCodebaseStep({ onUploaded }: UploadCodebaseStepProps) {
  const queryClient = useQueryClient();
  const folderInputRef = useRef<HTMLInputElement>(null);
  const zipInputRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const runUpload = async (
    fn: (onProgress?: (percent: number) => void) => Promise<{ id: string }>
  ) => {
    if (!name.trim()) {
      toast.error("Enter a display name for this codebase");
      return;
    }
    setUploading(true);
    setProgress(5);
    try {
      const repo = await fn((percent) => setProgress(percent));
      setProgress(100);
      toast.success("Codebase uploaded");
      await queryClient.invalidateQueries({ queryKey: ["knowledge-repos"] });
      onUploaded(repo.id);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
      setProgress(0);
    }
  };

  const handleZip = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".zip")) {
      toast.error("Please select a .zip file");
      return;
    }
    await runUpload(() => api.uploadRepoZip(name.trim(), file));
  };

  const handleFolder = async (files: FileList) => {
    if (files.length === 0) {
      toast.error("No files selected");
      return;
    }
    await runUpload((onProgress) => api.uploadRepoFolder(name.trim(), files, onProgress));
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Upload Codebase</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Upload a full Salesforce project (ZIP or folder), or select a code folder directly — LWC
          bundles (.js, .html, .css), Apex classes (.cls), triggers, flows, and metadata are
          supported.
        </p>
      </div>

      <PremiumCard title="Codebase Details">
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="upload-name">Display Name</Label>
            <Input
              id="upload-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Salesforce Project"
              disabled={uploading}
            />
          </div>

          {uploading && (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">Uploading and validating…</p>
              <Progress value={progress} />
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div
              className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed p-6 text-center"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const file = e.dataTransfer.files[0];
                if (file) void handleZip(file);
              }}
            >
              <Upload className="h-8 w-8 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">ZIP Archive</p>
                <p className="text-xs text-muted-foreground">Drop a .zip file or browse</p>
              </div>
              <input
                ref={zipInputRef}
                type="file"
                accept=".zip"
                className="hidden"
                disabled={uploading}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleZip(file);
                  e.target.value = "";
                }}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={uploading}
                onClick={() => zipInputRef.current?.click()}
              >
                Choose ZIP
              </Button>
            </div>

            <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed p-6 text-center">
              <FolderUp className="h-8 w-8 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Local Folder</p>
                <p className="text-xs text-muted-foreground">
                  Select any folder with Salesforce code (feature folder, lwc, classes, etc.)
                </p>
              </div>
              <input
                ref={folderInputRef}
                type="file"
                className="hidden"
                disabled={uploading}
                // @ts-expect-error webkitdirectory is non-standard but supported in Chromium
                webkitdirectory=""
                multiple
                onChange={(e) => {
                  const files = e.target.files;
                  if (files) void handleFolder(files);
                  e.target.value = "";
                }}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={uploading}
                onClick={() => folderInputRef.current?.click()}
              >
                Choose Folder
              </Button>
            </div>
          </div>
        </div>
      </PremiumCard>
    </div>
  );
}
