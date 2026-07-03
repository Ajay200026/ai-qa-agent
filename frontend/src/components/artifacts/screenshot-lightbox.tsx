"use client";

import { useEffect, useState } from "react";
import { AuthenticatedImage } from "@/components/artifacts/authenticated-image";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";

interface ScreenshotLightboxProps {
  executionId: string;
  screenshotPath: string;
  alt?: string;
  open: boolean;
  onClose: () => void;
}

export function ScreenshotLightbox({
  executionId,
  screenshotPath,
  alt,
  open,
  onClose,
}: ScreenshotLightboxProps) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <button
        type="button"
        className="absolute right-4 top-4 rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
        onClick={onClose}
        aria-label="Close"
      >
        <X className="h-5 w-5" />
      </button>
      <div
        className="max-h-[90vh] max-w-[95vw] overflow-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <AuthenticatedImage
          executionId={executionId}
          screenshotPath={screenshotPath}
          alt={alt}
          className="max-h-[90vh] w-auto max-w-full rounded object-contain"
        />
      </div>
    </div>
  );
}

interface ScreenshotThumbnailProps {
  executionId: string;
  screenshotPath: string;
  alt?: string;
  className?: string;
}

export function ScreenshotThumbnail({
  executionId,
  screenshotPath,
  alt,
  className,
}: ScreenshotThumbnailProps) {
  const [lightboxOpen, setLightboxOpen] = useState(false);

  return (
    <>
      <AuthenticatedImage
        executionId={executionId}
        screenshotPath={screenshotPath}
        alt={alt}
        className={cn("max-h-24 rounded border", className)}
        onClick={() => setLightboxOpen(true)}
      />
      <ScreenshotLightbox
        executionId={executionId}
        screenshotPath={screenshotPath}
        alt={alt}
        open={lightboxOpen}
        onClose={() => setLightboxOpen(false)}
      />
    </>
  );
}
