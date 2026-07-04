"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

const ROUTE_LABELS: Record<string, string> = {
  knowledge: "Knowledge",
  dashboard: "Dashboard",
  "salesforce-orgs": "Salesforce Orgs",
  executions: "Executions",
  reports: "Reports",
  "account-queries": "Account Queries",
  "login-as": "Login As",
  graph: "Graph",
  globe: "Globe",
  ask: "Ask AI",
  new: "New",
  edit: "Edit",
};

function buildBreadcrumbs(pathname: string) {
  const segments = pathname.split("/").filter(Boolean);
  const crumbs: { label: string; href: string }[] = [];
  let href = "";
  for (const seg of segments) {
    href += `/${seg}`;
    crumbs.push({ label: ROUTE_LABELS[seg] || seg, href });
  }
  return crumbs;
}

export function TopBar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const crumbs = buildBreadcrumbs(pathname);

  return (
    <header className="sticky top-0 z-20 hidden border-b bg-card/80 backdrop-blur-md md:flex md:h-14 md:items-center md:justify-between md:px-6">
      <nav className="flex items-center gap-1 text-sm text-muted-foreground">
        <Link href="/dashboard" className="hover:text-foreground transition-colors">
          Home
        </Link>
        {crumbs.map((crumb, i) => (
          <span key={crumb.href} className="flex items-center gap-1">
            <ChevronRight className="h-3.5 w-3.5" />
            {i === crumbs.length - 1 ? (
              <span className="font-medium text-foreground">{crumb.label}</span>
            ) : (
              <Link href={crumb.href} className="hover:text-foreground transition-colors">
                {crumb.label}
              </Link>
            )}
          </span>
        ))}
      </nav>

      <div className="flex items-center gap-3">
        <ThemeToggle />
        {user?.email && (
          <div
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-full bg-primary/20 text-xs font-semibold text-primary"
            )}
            title={user.email}
          >
            {user.email.charAt(0).toUpperCase()}
          </div>
        )}
      </div>
    </header>
  );
}
