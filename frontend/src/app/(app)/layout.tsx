"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/hooks/useAuth";
import { PageLoading } from "@/components/loading/page-loading";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const isOAuthCallback = pathname?.startsWith("/salesforce-orgs/oauth/callback");

  useEffect(() => {
    if (isOAuthCallback) return;
    if (!loading && !isAuthenticated) {
      router.push("/login");
    }
  }, [loading, isAuthenticated, isOAuthCallback, router]);

  if (isOAuthCallback) {
    return <div className="min-h-screen bg-background">{children}</div>;
  }

  if (loading) {
    return <PageLoading label="Loading…" fullScreen />;
  }

  if (!isAuthenticated) return null;

  return <AppShell>{children}</AppShell>;
}
