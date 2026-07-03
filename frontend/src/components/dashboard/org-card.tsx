import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SalesforceOrg } from "@/lib/types";
import { formatDate } from "@/lib/utils";

interface OrgCardProps {
  org: SalesforceOrg;
}

export function OrgCard({ org }: OrgCardProps) {
  const statusVariant =
    org.status === "connected" ? "success" : org.status === "error" ? "destructive" : "secondary";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base">{org.name}</CardTitle>
        <div className="flex gap-1">
          {org.is_default && <Badge variant="outline">Default</Badge>}
          <Badge variant={statusVariant}>{org.status}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-muted-foreground">
        <p>Type: {org.org_type}</p>
        <p>Auth: {org.auth_method}</p>
        <p>Validated: {formatDate(org.last_validated_at)}</p>
        <Link href={`/salesforce-orgs/${org.id}`}>
          <Button variant="link" className="h-auto p-0 text-sm">
            View details
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}
