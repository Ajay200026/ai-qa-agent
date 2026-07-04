"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, Cloud, Database, FileText, GitBranch, Globe, LayoutDashboard, LogOut, MessageSquare, Play, UserCircle, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";

const navItems = [
  { href: "/knowledge", label: "Knowledge", icon: Brain },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/salesforce-orgs", label: "Salesforce Orgs", icon: Cloud },
  { href: "/executions/new", label: "New Execution", icon: Play },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/account-queries", label: "Account Queries", icon: Database },
  { href: "/login-as", label: "Login As", icon: UserCircle },
];

const knowledgeSubItems = [
  { href: "/knowledge", label: "Overview", icon: Brain },
  { href: "/knowledge/graph", label: "Graph", icon: GitBranch },
  { href: "/knowledge/globe", label: "Globe", icon: Globe },
  { href: "/knowledge/ask", label: "Ask AI", icon: MessageSquare },
];

interface SidebarProps {
  mobileOpen?: boolean;
  onNavigate?: () => void;
}

export function Sidebar({ mobileOpen = false, onNavigate }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-50 flex h-screen w-64 flex-col border-r bg-card transition-transform duration-200 md:static md:translate-x-0",
        mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
      )}
    >
      <div className="flex items-start justify-between border-b p-4 md:p-6">
        <div>
          <h1 className="bg-gradient-to-r from-primary to-purple-400 bg-clip-text text-lg font-bold text-transparent">
            AI QA Agent
          </h1>
          <p className="text-xs text-muted-foreground">Salesforce Testing</p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          aria-label="Close navigation menu"
          onClick={onNavigate}
        >
          <X className="h-5 w-5" />
        </Button>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-4">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = pathname.startsWith(item.href);
          return (
            <div key={item.href}>
              <Link
                href={item.href}
                onClick={onNavigate}
                className={cn(
                  "relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all",
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                {active && (
                  <span className="absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full bg-primary" />
                )}
                <Icon className="h-4 w-4 shrink-0" />
                {item.label}
              </Link>
              {item.href === "/knowledge" && pathname.startsWith("/knowledge") && (
                <div className="ml-4 mt-1 space-y-1 border-l border-border pl-2">
                  {knowledgeSubItems.map((sub) => {
                    const SubIcon = sub.icon;
                    const subActive = pathname === sub.href;
                    return (
                      <Link
                        key={sub.href}
                        href={sub.href}
                        onClick={onNavigate}
                        className={cn(
                          "flex items-center gap-2 rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
                          subActive
                            ? "text-primary"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        <SubIcon className="h-3 w-3 shrink-0" />
                        {sub.label}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      <div className="border-t p-4">
        <p className="mb-2 truncate text-xs text-muted-foreground">{user?.email}</p>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start"
          onClick={() => {
            onNavigate?.();
            logout();
          }}
        >
          <LogOut className="mr-2 h-4 w-4" />
          Logout
        </Button>
      </div>
    </aside>
  );
}
