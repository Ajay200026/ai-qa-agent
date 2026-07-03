"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SalesforceOrg } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { Eye, RefreshCw, Star, Trash2 } from "lucide-react";

interface OrgListProps {
  orgs: SalesforceOrg[];
  onValidate: (orgId: string) => void;
  onSetDefault: (orgId: string) => void;
  onDelete: (orgId: string) => void;
  busyId?: string | null;
}

function statusVariant(status: string) {
  if (status === "connected") return "success" as const;
  if (status === "error") return "destructive" as const;
  return "secondary" as const;
}

export function OrgList({ orgs, onValidate, onSetDefault, onDelete, busyId }: OrgListProps) {
  if (orgs.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No Salesforce orgs yet. Authorize one below.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full min-w-[720px] text-sm">
        <thead className="border-b bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-4 py-3 font-medium">Name</th>
            <th className="px-4 py-3 font-medium">Connected as</th>
            <th className="px-4 py-3 font-medium">Type</th>
            <th className="px-4 py-3 font-medium">Auth</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Instance</th>
            <th className="px-4 py-3 font-medium">Validated</th>
            <th className="px-4 py-3 font-medium text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {orgs.map((org) => (
            <tr key={org.id} className="border-b last:border-0 hover:bg-muted/20">
              <td className="px-4 py-3 font-medium">
                <div className="flex items-center gap-2">
                  {org.name}
                  {org.is_default && (
                    <Badge variant="outline" className="text-xs">
                      Default
                    </Badge>
                  )}
                </div>
              </td>
              <td className="max-w-[200px] truncate px-4 py-3 text-muted-foreground">
                {org.salesforce_username || "—"}
              </td>
              <td className="px-4 py-3 capitalize text-muted-foreground">{org.org_type}</td>
              <td className="px-4 py-3 capitalize text-muted-foreground">{org.auth_method}</td>
              <td className="px-4 py-3">
                <Badge variant={statusVariant(org.status)}>{org.status}</Badge>
              </td>
              <td className="max-w-[180px] truncate px-4 py-3 text-muted-foreground">
                {org.instance_url || "—"}
              </td>
              <td className="px-4 py-3 text-muted-foreground">
                {formatDate(org.last_validated_at)}
              </td>
              <td className="px-4 py-3">
                <div className="flex justify-end gap-1">
                  <Link href={`/salesforce-orgs/${org.id}`}>
                    <Button variant="ghost" size="icon" title="View">
                      <Eye className="h-4 w-4" />
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    size="icon"
                    title="Re-validate"
                    disabled={busyId === org.id}
                    onClick={() => onValidate(org.id)}
                  >
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                  {!org.is_default && (
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Set as default"
                      disabled={busyId === org.id}
                      onClick={() => onSetDefault(org.id)}
                    >
                      <Star className="h-4 w-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    title="Delete"
                    disabled={busyId === org.id}
                    onClick={() => onDelete(org.id)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
