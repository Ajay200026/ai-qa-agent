"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SalesforceOAuthCallbackInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const error = searchParams.get("error");
  const [callbackError, setCallbackError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const exchangedRef = useRef(false);

  useEffect(() => {
    if (error) return;
    if (!code || !state) return;
    if (exchangedRef.current) return;
    exchangedRef.current = true;

    const stored = localStorage.getItem("sf_oauth_state");
    if (stored && stored !== state) {
      setCallbackError("OAuth state mismatch — try again from Salesforce Orgs.");
      return;
    }

    (async () => {
      try {
        await api.completeSalesforceOAuth({ state, code });
        localStorage.removeItem("sf_oauth_state");
        setSuccess(true);
        router.replace("/salesforce-orgs?connected=1");
      } catch (err) {
        setCallbackError(err instanceof Error ? err.message : "Failed to complete OAuth");
      }
    })();
  }, [code, state, error, router]);

  if (error || callbackError) {
    return (
      <Card className="mx-auto mt-12 max-w-md">
        <CardHeader>
          <CardTitle>Authorization failed</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-destructive">{error || callbackError}</p>
          <Button asChild variant="outline">
            <Link href="/salesforce-orgs">Back to Salesforce Orgs</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (success) {
    return (
      <Card className="mx-auto mt-12 max-w-md">
        <CardHeader>
          <CardTitle>Org connected</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Redirecting to Salesforce Orgs…
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="mx-auto mt-12 max-w-md">
      <CardHeader>
        <CardTitle>Completing authorization…</CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">
        Finishing Salesforce sign-in. This usually takes a few seconds.
      </CardContent>
    </Card>
  );
}
