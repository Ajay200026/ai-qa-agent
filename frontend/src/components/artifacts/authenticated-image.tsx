"use client";

import { useEffect, useState } from "react";
import { fetchArtifactBlobUrl } from "@/lib/artifacts";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

interface AuthenticatedImageProps {
  executionId: string;
  screenshotPath: string;
  alt?: string;
  className?: string;
  onClick?: () => void;
}

export function AuthenticatedImage({
  executionId,
  screenshotPath,
  alt = "Screenshot",
  className,
  onClick,
}: AuthenticatedImageProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    setError(false);
    setSrc(null);

    fetchArtifactBlobUrl(executionId, screenshotPath)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setSrc(url);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [executionId, screenshotPath]);

  if (error) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded border bg-muted px-2 py-4 text-xs text-muted-foreground",
          className
        )}
      >
        Screenshot unavailable
      </div>
    );
  }

  if (!src) {
    return <Skeleton className={cn("rounded border", className)} />;
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      className={cn("object-cover", onClick && "cursor-pointer", className)}
      onClick={onClick}
    />
  );
}
