"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, File, Folder } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useTheme } from "next-themes";

import { api } from "@/lib/api";
import type { RepoFileEntry } from "@/lib/types";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

interface CodeExplorerProps {
  repoId: string;
  scopePath: string;
}

const LANG_MAP: Record<string, string> = {
  apex: "java",
  javascript: "javascript",
  html: "html",
  xml: "xml",
  json: "json",
  css: "css",
  text: "text",
};

export function CodeExplorer({ repoId, scopePath }: CodeExplorerProps) {
  const { theme } = useTheme();
  const [currentPath, setCurrentPath] = useState("");
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  const listPath = currentPath;

  const { data: files = [], isLoading } = useQuery({
    queryKey: ["repo-files", repoId, listPath, scopePath],
    queryFn: () => api.listRepoFiles(repoId, listPath, scopePath),
    enabled: !!repoId && !!scopePath,
  });

  const { data: fileContent, isLoading: contentLoading } = useQuery({
    queryKey: ["repo-file-content", repoId, selectedFile],
    queryFn: () => api.getRepoFileContent(repoId, selectedFile!),
    enabled: !!selectedFile,
  });

  const handleEntryClick = (entry: RepoFileEntry) => {
    if (entry.is_directory) {
      const rel = entry.path.startsWith(scopePath)
        ? entry.path.slice(scopePath.length).replace(/^\//, "")
        : entry.path;
      setCurrentPath(rel);
      setSelectedFile(null);
    } else {
      setSelectedFile(entry.path);
    }
  };

  const style = theme === "dark" ? oneDark : oneLight;
  const highlightLang = LANG_MAP[fileContent?.language || "text"] || "text";

  return (
    <div className="grid h-[400px] grid-cols-[200px_1fr] overflow-hidden rounded-lg border">
      <ScrollArea className="border-r bg-muted/20 p-2">
        {isLoading ? (
          <p className="p-2 text-xs text-muted-foreground">Loading…</p>
        ) : (
          <div className="space-y-0.5">
            {currentPath && (
              <button
                type="button"
                onClick={() => {
                  const parts = currentPath.split("/").filter(Boolean);
                  parts.pop();
                  setCurrentPath(parts.join("/"));
                  setSelectedFile(null);
                }}
                className="flex w-full items-center gap-1 rounded px-2 py-1 text-xs text-muted-foreground hover:bg-accent"
              >
                .. up
              </button>
            )}
            {files.map((entry) => (
              <button
                key={entry.path}
                type="button"
                onClick={() => handleEntryClick(entry)}
                className={cn(
                  "flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-xs hover:bg-accent",
                  selectedFile === entry.path && "bg-primary/10 text-primary"
                )}
              >
                {entry.is_directory ? (
                  <Folder className="h-3.5 w-3.5 shrink-0 text-amber-500" />
                ) : (
                  <File className="h-3.5 w-3.5 shrink-0 text-blue-500" />
                )}
                <span className="truncate">{entry.name}</span>
                {!entry.is_directory && (
                  <ChevronRight className="ml-auto h-3 w-3 opacity-0" />
                )}
              </button>
            ))}
          </div>
        )}
      </ScrollArea>

      <ScrollArea className="bg-background">
        {!selectedFile ? (
          <p className="p-4 text-sm text-muted-foreground">Select a file to view source code.</p>
        ) : contentLoading ? (
          <p className="p-4 text-sm text-muted-foreground">Loading file…</p>
        ) : fileContent ? (
          <div>
            <div className="border-b bg-muted/30 px-3 py-1.5 font-mono text-xs text-muted-foreground">
              {fileContent.path}
              {fileContent.truncated && " (truncated)"}
            </div>
            <SyntaxHighlighter
              language={highlightLang}
              style={style}
              customStyle={{ margin: 0, borderRadius: 0, fontSize: "12px", background: "transparent" }}
              showLineNumbers
            >
              {fileContent.content}
            </SyntaxHighlighter>
          </div>
        ) : null}
      </ScrollArea>
    </div>
  );
}
