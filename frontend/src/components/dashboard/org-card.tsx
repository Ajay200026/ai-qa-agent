"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PremiumCard } from "@/components/ui/premium-card";
import type { SalesforceOrg } from "@/lib/types";
import { formatDate } from "@/lib/utils";

interface OrgCardProps {
  org: SalesforceOrg;
}

export function OrgCard({ org }: OrgCardProps) {
  const statusVariant =
    org.status === "connected" ? "default" : org.status === "error" ? "destructive" : "secondary";

  return (
    <motion.div whileHover={{ y: -2 }} transition={{ duration: 0.2 }}>
      <PremiumCard className="h-full transition-shadow hover:shadow-md">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-base font-semibold">{org.name}</h3>
          <div className="flex shrink-0 gap-1">
            {org.is_default && <Badge variant="outline">Default</Badge>}
            <Badge variant={statusVariant}>{org.status}</Badge>
          </div>
        </div>
        <div className="mt-3 space-y-1.5 text-sm text-muted-foreground">
          <p>Type: {org.org_type}</p>
          <p>Auth: {org.auth_method}</p>
          <p>Validated: {formatDate(org.last_validated_at)}</p>
        </div>
        <Link href={`/salesforce-orgs/${org.id}`} className="mt-4 inline-block">
          <Button variant="outline" size="sm">
            View details
          </Button>
        </Link>
      </PremiumCard>
    </motion.div>
  );
}
