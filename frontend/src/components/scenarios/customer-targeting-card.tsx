"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { CustomerTarget, SoqlAccountRow } from "@/lib/types";

type Source = "manual" | "soql";

interface Props {
  orgId: string | null;
  bottler: string | null;
  value: CustomerTarget | null;
  onChange: (target: CustomerTarget | null) => void;
}

const EMPTY: CustomerTarget = {
  account_number: "",
  account_name: "",
  sales_office: "",
  account_group: "",
  distribution_channel: "",
  search_strategy: "by_number",
  soql_query: "",
};

export function CustomerTargetingCard({ orgId, bottler, value, onChange }: Props) {
  const [enabled, setEnabled] = useState<boolean>(!!value);
  const [source, setSource] = useState<Source>(
    value?.soql_query ? "soql" : "manual"
  );
  const [draft, setDraft] = useState<CustomerTarget>({ ...EMPTY, ...(value || {}) });
  const [soql, setSoql] = useState<string>(value?.soql_query || "");
  const [rows, setRows] = useState<SoqlAccountRow[]>([]);
  const [queryError, setQueryError] = useState<string>("");
  const [queryLoading, setQueryLoading] = useState(false);
  const [selectedRowIdx, setSelectedRowIdx] = useState<number | null>(null);

  const optionsQuery = useQuery({
    queryKey: ["customer-search-options", orgId, draft.sales_office],
    queryFn: () =>
      api.getCustomerSearchOptions(orgId!, draft.sales_office || undefined),
    enabled: !!orgId && enabled,
    staleTime: 60_000,
  });

  // Preload a default SOQL when bottler info first arrives.
  useEffect(() => {
    if (source === "soql" && !soql && optionsQuery.data?.default_soql) {
      setSoql(optionsQuery.data.default_soql);
    }
  }, [optionsQuery.data?.default_soql, source, soql]);

  const accountGroups = useMemo(() => {
    const combos = optionsQuery.data?.combinations || [];
    const set = new Set<string>();
    combos.forEach((c) => c.account_group && set.add(c.account_group));
    return Array.from(set);
  }, [optionsQuery.data]);

  const distributionChannels = useMemo(() => {
    const combos = optionsQuery.data?.combinations || [];
    const set = new Set<string>();
    combos
      .filter((c) => !draft.account_group || c.account_group === draft.account_group)
      .forEach((c) => c.distribution_channel && set.add(c.distribution_channel));
    return Array.from(set);
  }, [optionsQuery.data, draft.account_group]);

  // Emit changes upward.
  useEffect(() => {
    if (!enabled) {
      onChange(null);
      return;
    }
    const payload: CustomerTarget = {
      ...draft,
      search_strategy: source === "soql" ? "by_soql" : "by_number",
      soql_query: source === "soql" ? soql : null,
      bottler: bottler || null,
    };
    onChange(payload);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, draft, soql, source, bottler]);

  const runQuery = async () => {
    if (!orgId || !soql.trim()) return;
    setQueryError("");
    setRows([]);
    setSelectedRowIdx(null);
    setQueryLoading(true);
    try {
      const result = await api.querySalesforce(orgId, soql.trim());
      setRows(result.records);
      if (result.records.length === 0) {
        setQueryError("Query returned no rows");
      }
    } catch (err) {
      setQueryError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setQueryLoading(false);
    }
  };

  const pickRow = (idx: number) => {
    const row = rows[idx];
    if (!row) return;
    setSelectedRowIdx(idx);
    setDraft((prev) => ({
      ...prev,
      account_number: row.account_number || "",
      account_name: row.account_name || "",
      sales_office: row.sales_office || prev.sales_office || "",
      account_group: row.account_group || prev.account_group || "",
      distribution_channel:
        row.distribution_channel || prev.distribution_channel || "",
    }));
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-2">
        <div>
          <CardTitle>Customer Targeting</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            Target a specific Salesforce Account. {bottler ? `Bottler: ${bottler}.` : "Connect an org with a bottler to filter options."}
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          Enable
        </label>
      </CardHeader>
      {enabled && (
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Button
              type="button"
              variant={source === "manual" ? "default" : "outline"}
              size="sm"
              onClick={() => setSource("manual")}
            >
              Manual
            </Button>
            <Button
              type="button"
              variant={source === "soql" ? "default" : "outline"}
              size="sm"
              onClick={() => setSource("soql")}
            >
              SOQL Query
            </Button>
          </div>

          {source === "soql" && (
            <div className="space-y-2">
              <Label htmlFor="soql">SOQL Query (Account only, LIMIT ≤ 50)</Label>
              <Textarea
                id="soql"
                rows={5}
                className="font-mono text-xs"
                value={soql}
                onChange={(e) => setSoql(e.target.value)}
                placeholder="SELECT AccountNumber, Name, ... FROM Account WHERE ... LIMIT 5"
              />
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={runQuery}
                  disabled={!orgId || queryLoading}
                >
                  {queryLoading ? "Running…" : "Run Query"}
                </Button>
                {queryError && (
                  <span className="text-xs text-destructive">{queryError}</span>
                )}
              </div>
              {rows.length > 0 && (
                <div className="overflow-x-auto rounded-md border">
                  <table className="w-full text-xs">
                    <thead className="bg-muted">
                      <tr>
                        <th className="p-2 text-left">Pick</th>
                        <th className="p-2 text-left">Account #</th>
                        <th className="p-2 text-left">Name</th>
                        <th className="p-2 text-left">Office</th>
                        <th className="p-2 text-left">Group</th>
                        <th className="p-2 text-left">Channel</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, idx) => (
                        <tr key={idx} className="border-t">
                          <td className="p-2">
                            <input
                              type="radio"
                              name="soql-row"
                              checked={selectedRowIdx === idx}
                              onChange={() => pickRow(idx)}
                            />
                          </td>
                          <td className="p-2 font-mono">{row.account_number}</td>
                          <td className="p-2">{row.account_name}</td>
                          <td className="p-2">{row.sales_office}</td>
                          <td className="p-2">{row.account_group}</td>
                          <td className="p-2">{row.distribution_channel}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label>Account Number</Label>
              <Input
                value={draft.account_number || ""}
                onChange={(e) =>
                  setDraft((p) => ({ ...p, account_number: e.target.value }))
                }
                placeholder="0605467903"
              />
            </div>
            <div className="space-y-1">
              <Label>Account Name (optional)</Label>
              <Input
                value={draft.account_name || ""}
                onChange={(e) =>
                  setDraft((p) => ({ ...p, account_name: e.target.value }))
                }
              />
            </div>
            <div className="space-y-1">
              <Label>Sales Office</Label>
              <Input
                value={draft.sales_office || ""}
                onChange={(e) =>
                  setDraft((p) => ({ ...p, sales_office: e.target.value }))
                }
                placeholder="K045"
              />
            </div>
            <div className="space-y-1">
              <Label>Account Group</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={draft.account_group || ""}
                onChange={(e) =>
                  setDraft((p) => ({
                    ...p,
                    account_group: e.target.value,
                    distribution_channel: "",
                  }))
                }
              >
                <option value="">Select</option>
                {accountGroups.map((ag) => (
                  <option key={ag} value={ag}>
                    {ag}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label>Distribution Channel</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={draft.distribution_channel || ""}
                onChange={(e) =>
                  setDraft((p) => ({ ...p, distribution_channel: e.target.value }))
                }
              >
                <option value="">{distributionChannels.length ? "Select" : "(any)"}</option>
                {distributionChannels.map((dc) => (
                  <option key={dc} value={dc}>
                    {dc}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {optionsQuery.data && optionsQuery.data.combinations.length === 0 && bottler && (
            <p className="text-xs text-muted-foreground">
              No combinations registered for bottler {bottler} / office {draft.sales_office || "(any)"}.
            </p>
          )}
        </CardContent>
      )}
    </Card>
  );
}
