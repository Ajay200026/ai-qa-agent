import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

interface PageLoadingProps {
  label?: string;
  className?: string;
  fullScreen?: boolean;
}

export function PageLoading({
  label = "Loading…",
  className,
  fullScreen = false,
}: PageLoadingProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 text-sm text-muted-foreground",
        fullScreen && "min-h-screen",
        !fullScreen && "py-16",
        className
      )}
    >
      <Spinner size="lg" />
      {label && <p>{label}</p>}
    </div>
  );
}
