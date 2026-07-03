import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function OrgMetadataSkeleton() {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-6 w-20 rounded-full" />
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className={i >= 2 && i <= 3 ? "sm:col-span-2" : undefined}>
            <Skeleton className="mb-2 h-3 w-20" />
            <Skeleton className="h-5 w-full max-w-xs" />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
