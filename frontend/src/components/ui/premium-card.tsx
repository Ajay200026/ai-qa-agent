import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface PremiumCardProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  description?: string;
  headerAction?: React.ReactNode;
  noPadding?: boolean;
}

const PremiumCard = React.forwardRef<HTMLDivElement, PremiumCardProps>(
  ({ className, title, description, headerAction, noPadding, children, ...props }, ref) => (
    <Card
      ref={ref}
      className={cn(
        "rounded-xl border bg-card/80 shadow-sm backdrop-blur-sm transition-shadow hover:shadow-md",
        className
      )}
      {...props}
    >
      {(title || description || headerAction) && (
        <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-4">
          <div className="space-y-1">
            {title && <CardTitle className="text-lg">{title}</CardTitle>}
            {description && <CardDescription>{description}</CardDescription>}
          </div>
          {headerAction}
        </CardHeader>
      )}
      {noPadding ? children : <CardContent>{children}</CardContent>}
    </Card>
  )
);
PremiumCard.displayName = "PremiumCard";

export { PremiumCard };
