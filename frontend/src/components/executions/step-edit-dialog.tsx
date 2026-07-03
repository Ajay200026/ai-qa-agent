"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ExecutionStep } from "@/lib/types";

interface Props {
  executionId: string;
  step: ExecutionStep;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

const QUICK_FIELDS: Array<{ key: string; label: string }> = [
  { key: "customer_number", label: "Customer Number" },
  { key: "account_group", label: "Account Group" },
  { key: "distribution_channel", label: "Distribution Channel" },
  { key: "sales_office", label: "Sales Office" },
  { key: "primary_group", label: "Primary Group" },
  { key: "value", label: "Value" },
];

export function StepEditDialog({
  executionId,
  step,
  open,
  onClose,
  onSaved,
}: Props) {
  const initialParams =
    (step.action_params as Record<string, string> | null) || {};
  const [fields, setFields] = useState<Record<string, string>>({});
  const [json, setJson] = useState("");
  const [notes, setNotes] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [rerunChoice, setRerunChoice] = useState<"this" | "no">("this");

  useEffect(() => {
    if (open) {
      setError("");
      setFields(initialParams as Record<string, string>);
      setJson(JSON.stringify(initialParams, null, 2));
      setNotes(step.notes || "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, step.id]);

  if (!open) return null;

  const setField = (key: string, value: string) => {
    setFields((prev) => {
      const next = { ...prev };
      if (value) next[key] = value;
      else delete next[key];
      setJson(JSON.stringify(next, null, 2));
      return next;
    });
  };

  const handleJsonChange = (text: string) => {
    setJson(text);
    try {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed === "object") {
        setFields(parsed as Record<string, string>);
      }
    } catch {
      /* allow typing */
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      let parsed: Record<string, unknown>;
      try {
        parsed = json.trim() ? JSON.parse(json) : fields;
      } catch {
        setError("Params must be valid JSON");
        setSaving(false);
        return;
      }
      await api.patchExecutionStep(executionId, step.seq, parsed);
      if (notes !== (step.notes || "")) {
        await api.putExecutionStepNotes(executionId, step.seq, notes || null);
      }
      if (rerunChoice === "this") {
        await api.rerunExecution(executionId, { from_step_seq: step.seq });
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-lg border bg-background p-5 shadow-xl">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold">Edit Step #{step.seq}</h2>
            <p className="text-xs text-muted-foreground">
              {step.name} <span className="font-mono">({step.action})</span>
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            ✕
          </Button>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            {QUICK_FIELDS.map((f) => (
              <div key={f.key} className="space-y-1">
                <Label className="text-xs">{f.label}</Label>
                <Input
                  className="h-9"
                  value={fields[f.key] || ""}
                  onChange={(e) => setField(f.key, e.target.value)}
                />
              </div>
            ))}
          </div>

          <div className="space-y-1">
            <Label className="text-xs">Params (JSON)</Label>
            <Textarea
              rows={5}
              className="font-mono text-xs"
              value={json}
              onChange={(e) => handleJsonChange(e.target.value)}
            />
          </div>

          <div className="space-y-1">
            <Label className="text-xs">Notes (failure annotation)</Label>
            <Textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Why did this fail? What did you change?"
            />
          </div>

          <div className="space-y-1">
            <Label className="text-xs">After Save</Label>
            <select
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={rerunChoice}
              onChange={(e) =>
                setRerunChoice(e.target.value as "this" | "no")
              }
            >
              <option value="this">Re-run from this step</option>
              <option value="no">Save only (no re-run)</option>
            </select>
          </div>

          {error && <p className="text-xs text-destructive">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Saving…" : "Save & Continue"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
