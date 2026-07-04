"use client";

import { useState } from "react";
import { Menu } from "lucide-react";
import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/top-bar";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { Button } from "@/components/ui/button";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <header className="sticky top-0 z-30 flex items-center justify-between border-b bg-card/80 px-4 py-3 backdrop-blur-md md:hidden">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Open navigation menu"
          onClick={() => setMobileOpen(true)}
        >
          <Menu className="h-5 w-5" />
        </Button>
        <div className="text-center">
          <p className="text-sm font-semibold">AI QA Agent</p>
          <p className="text-xs text-muted-foreground">Salesforce Testing</p>
        </div>
        <ThemeToggle />
      </header>

      {mobileOpen && (
        <button
          type="button"
          aria-label="Close navigation menu"
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <Sidebar mobileOpen={mobileOpen} onNavigate={() => setMobileOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="min-w-0 flex-1 overflow-auto p-4 sm:p-6 lg:p-8">
          <div className="mx-auto max-w-7xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
