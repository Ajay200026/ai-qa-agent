"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { IdentityMap, IdentityMapEntry, IdentityPreviewItem } from "@/lib/types";

interface Props {
  testPackContent: string;
  value: IdentityMap | null;
  onChange: (map: IdentityMap | null) => void;
}

function entryKey(bottler: string | null, role: string | null): string {
  return `${(bottler || "").toLowerCase()}|${(role || "").toLowerCase()}`;
}

function statusFor(entry: IdentityMapEntry | undefined): "Default" | "Overridden" | "Disabled" {
  if (entry && entry.enabled === false) return "Disabled";
  if (
    entry &&
    ((entry.override_bottler && entry.override_bottler !== entry.bottler) ||
      (entry.override_role && entry.override_role !== entry.role))
  ) {
    return "Overridden";
  }
  return "Default";
}

export function IdentityMapCard({ testPackContent, value, onChange }: Props) {
  const [detected, setDetected] = useState<IdentityPreviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const entriesByKey = useMemo(() => {
    const map = new Map<string, IdentityMapEntry>();
    for (const entry of value?.entries || []) {
      map.set(entryKey(entry.bottler, entry.role), entry);
    }
    return map;
  }, [value]);

  const fetchIdentities = useCallback(async (content: string) => {
    if (!content.trim() || content.trim().length < 40) {
      setDetected([]);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await api.previewIdentities(content.trim());
      setDetected(result.identities);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to detect identities");
      setDetected([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchIdentities(testPackContent);
    }, 600);
    return () => clearTimeout(timer);
  }, [testPackContent, fetchIdentities]);

  const updateEntry = (item: IdentityPreviewItem, patch: Partial<IdentityMapEntry>) => {
    const bottler = item.bottler || "";
    const role = item.role || "";
    const key = entryKey(bottler, role);
    const existing = entriesByKey.get(key) || {
      bottler,
      role,
      enabled: true,
    };
    const updated: IdentityMapEntry = { ...existing, ...patch, bottler, role };
    const others = (value?.entries || []).filter(
      (e) => entryKey(e.bottler, e.role) !== key
    );
    onChange({ entries: [...others, updated] });
  };

  const resetToDetected = () => {
    const entries: IdentityMapEntry[] = detected.map((item) => ({
      bottler: item.bottler || "",
      role: item.role || "",
      enabled: true,
    }));
    onChange(entries.length ? { entries } : null);
  };

  if (!testPackContent.trim()) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base sm:text-lg">Identity Map</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Paste test pack content to detect identities.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <CardTitle className="text-base sm:text-lg">Identity Map</CardTitle>
        <Button type="button" variant="outline" size="sm" onClick={resetToDetected}>
          Reset to detected
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground sm:text-sm">
          Per-test-case impersonation overrides. Each row maps a (bottler, role)
          pair found in the test pack to a Salesforce user lookup.
        </p>
        {loading && (
          <p className="text-sm text-muted-foreground">Detecting identities…</p>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && detected.length === 0 && !error && (
          <p className="text-sm text-muted-foreground">
            No (bottler, role) pairs detected in the test pack.
          </p>
        )}
        {detected.length > 0 && (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="border-b bg-muted/50">
                <tr>
                  <th className="px-3 py-2 font-medium">Enabled</th>
                  <th className="px-3 py-2 font-medium">Bottler</th>
                  <th className="px-3 py-2 font-medium">Role</th>
                  <th className="px-3 py-2 font-medium">Override Bottler</th>
                  <th className="px-3 py-2 font-medium">Override Role</th>
                  <th className="px-3 py-2 font-medium">Test Cases</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {detected.map((item) => {
                  const key = entryKey(item.bottler, item.role);
                  const entry = entriesByKey.get(key);
                  const enabled = entry?.enabled !== false;
                  const status = statusFor(entry);
                  return (
                    <tr key={key} className="border-b last:border-0">
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={enabled}
                          onChange={(e) =>
                            updateEntry(item, { enabled: e.target.checked })
                          }
                          className="h-4 w-4 rounded border"
                        />
                      </td>
                      <td className="px-3 py-2">{item.bottler || "—"}</td>
                      <td className="px-3 py-2">{item.role || "—"}</td>
                      <td className="px-3 py-2">
                        <Input
                          className="h-8"
                          placeholder={item.bottler || ""}
                          value={entry?.override_bottler || ""}
                          onChange={(e) =>
                            updateEntry(item, {
                              override_bottler: e.target.value || null,
                            })
                          }
                        />
                      </td>
                      <td className="px-3 py-2">
                        <Input
                          className="h-8"
                          placeholder={item.role || ""}
                          value={entry?.override_role || ""}
                          onChange={(e) =>
                            updateEntry(item, {
                              override_role: e.target.value || null,
                            })
                          }
                        />
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">
                        {item.tc_ids.join(", ")}
                      </td>
                      <td className="px-3 py-2">
                        <Badge
                          variant={
                            status === "Disabled"
                              ? "outline"
                              : status === "Overridden"
                                ? "secondary"
                                : "default"
                          }
                        >
                          {status}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
