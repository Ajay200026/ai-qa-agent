"use client";

import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { LoginAsTarget } from "@/lib/types";

const COMMON_ROLES = ["Requestor", "Finance", "GM", "Approver", "Manager"];

interface Props {
  bottler: string | null;
  value: LoginAsTarget | null;
  onChange: (target: LoginAsTarget | null) => void;
}

export function LoginAsCard({ bottler, value, onChange }: Props) {
  const [enabled, setEnabled] = useState(!!value?.enabled);
  const [bottlerId, setBottlerId] = useState(value?.bottler_id || bottler || "");
  const [role, setRole] = useState(value?.onboarding_role || "");

  useEffect(() => {
    if (!enabled) {
      onChange(null);
      return;
    }
    if (bottlerId.trim() && role.trim()) {
      onChange({
        bottler_id: bottlerId.trim(),
        onboarding_role: role.trim(),
        enabled: true,
      });
    } else {
      onChange(null);
    }
  }, [enabled, bottlerId, role, onChange]);

  useEffect(() => {
    if (bottler && !value?.bottler_id) {
      setBottlerId(bottler);
    }
  }, [bottler, value?.bottler_id]);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-base sm:text-lg">Login As (Impersonate User)</CardTitle>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            className="h-4 w-4 rounded border"
          />
          Enable
        </label>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground sm:text-sm">
          Runs after the admin login. Acts as the default identity for test cases
          that do not specify their own role/bottler.
        </p>
        {enabled && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="login-as-bottler">Bottler ID</Label>
              <Input
                id="login-as-bottler"
                value={bottlerId}
                onChange={(e) => setBottlerId(e.target.value)}
                placeholder="e.g. 5000"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="login-as-role">Onboarding Role</Label>
              <Input
                id="login-as-role"
                list="onboarding-roles"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="e.g. Requestor"
              />
              <datalist id="onboarding-roles">
                {COMMON_ROLES.map((r) => (
                  <option key={r} value={r} />
                ))}
              </datalist>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
