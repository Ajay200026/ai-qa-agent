import { Suspense } from "react";
import SalesforceOAuthCallbackInner from "./callback-inner";

export default function SalesforceOAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <p className="mt-12 text-center text-sm text-muted-foreground">Loading…</p>
      }
    >
      <SalesforceOAuthCallbackInner />
    </Suspense>
  );
}
