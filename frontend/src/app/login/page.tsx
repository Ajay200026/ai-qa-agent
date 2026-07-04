"use client";

import { useState } from "react";
import { Brain } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PremiumCard } from "@/components/ui/premium-card";
import { ThemeToggle } from "@/components/theme/theme-toggle";

export default function LoginPage() {
  const { login, register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (isRegister) {
        await register(email, password);
      } else {
        await login(email, password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      <div className="relative hidden flex-1 flex-col justify-between bg-gradient-to-br from-primary/20 via-background to-background p-10 lg:flex">
        <div className="flex items-center gap-2">
          <Brain className="h-8 w-8 text-primary" />
          <span className="text-xl font-bold">AI QA Agent</span>
        </div>
        <div>
          <h1 className="text-4xl font-bold tracking-tight">
            Salesforce QA &<br />
            Knowledge Platform
          </h1>
          <p className="mt-4 max-w-md text-muted-foreground">
            Connect Azure DevOps, build knowledge graphs, and run AI-powered Salesforce testing.
          </p>
        </div>
        <p className="text-xs text-muted-foreground">Premium testing automation</p>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center p-6">
        <div className="absolute right-4 top-4">
          <ThemeToggle />
        </div>
        <PremiumCard className="w-full max-w-md" title="AI QA Agent" description={isRegister ? "Create your account" : "Sign in to your account"}>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Please wait..." : isRegister ? "Register" : "Sign In"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="w-full"
              onClick={() => setIsRegister(!isRegister)}
            >
              {isRegister ? "Already have an account? Sign in" : "Need an account? Register"}
            </Button>
          </form>
        </PremiumCard>
      </div>
    </div>
  );
}
