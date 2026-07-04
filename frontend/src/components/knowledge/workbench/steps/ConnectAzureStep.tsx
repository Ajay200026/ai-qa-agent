"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Cloud, Plus, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { api } from "@/lib/api";
import type { AzureConnection } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { PremiumCard } from "@/components/ui/premium-card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const connectSchema = z.object({
  organization_url: z.string().url("Enter a valid Azure DevOps URL"),
  connection_name: z.string().min(1, "Connection name is required"),
  pat: z.string().min(1, "PAT is required"),
});

type ConnectForm = z.infer<typeof connectSchema>;

interface ConnectAzureStepProps {
  onConnected: () => void;
}

export function ConnectAzureStep({ onConnected }: ConnectAzureStepProps) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [validating, setValidating] = useState<string | null>(null);

  const { data: connections = [], isLoading } = useQuery({
    queryKey: ["azure-connections"],
    queryFn: () => api.listAzureConnections(),
  });

  const form = useForm<ConnectForm>({
    resolver: zodResolver(connectSchema),
    defaultValues: {
      organization_url: "https://dev.azure.com/",
      connection_name: "",
      pat: "",
    },
  });

  const onSubmit = async (data: ConnectForm) => {
    try {
      await api.connectAzure({
        name: data.connection_name.trim(),
        organization_url: data.organization_url.trim(),
        pat: data.pat.trim(),
      });
      toast.success("Azure DevOps connected");
      form.reset({ organization_url: "https://dev.azure.com/", connection_name: "", pat: "" });
      setShowForm(false);
      await queryClient.invalidateQueries({ queryKey: ["azure-connections"] });
      onConnected();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Connection failed");
    }
  };

  const handleValidate = async (id: string) => {
    setValidating(id);
    try {
      await api.validateAzureConnection(id);
      toast.success("Connection validated");
      await queryClient.invalidateQueries({ queryKey: ["azure-connections"] });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Validation failed");
    } finally {
      setValidating(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await api.deleteAzureConnection(deleteId);
      toast.success("Connection removed");
      await queryClient.invalidateQueries({ queryKey: ["azure-connections"] });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleteId(null);
    }
  };

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading connections…</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Connect Azure DevOps</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Add your organization with a Personal Access Token (Code Read + Project Read).
        </p>
      </div>

      {connections.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {connections.map((c: AzureConnection, i) => (
            <motion.div
              key={c.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <PremiumCard className="relative">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Cloud className="h-5 w-5 text-primary" />
                    <div>
                      <p className="font-medium">{c.name}</p>
                      <p className="text-xs text-muted-foreground">{c.organization_name}</p>
                    </div>
                  </div>
                  <Badge variant={c.status === "connected" ? "default" : "destructive"}>
                    {c.status}
                  </Badge>
                </div>
                <div className="mt-4 flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleValidate(c.id)}
                    disabled={validating === c.id}
                  >
                    <RefreshCw className={`mr-1 h-3 w-3 ${validating === c.id ? "animate-spin" : ""}`} />
                    Validate
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setDeleteId(c.id)}>
                    <Trash2 className="h-3 w-3 text-destructive" />
                  </Button>
                </div>
              </PremiumCard>
            </motion.div>
          ))}
        </div>
      )}

      {!showForm ? (
        <Button variant="outline" onClick={() => setShowForm(true)}>
          <Plus className="mr-2 h-4 w-4" />
          {connections.length === 0 ? "Add Azure Connection" : "Add Another Connection"}
        </Button>
      ) : (
        <PremiumCard title="New Connection">
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="org-url">Organization URL</Label>
              <Input id="org-url" {...form.register("organization_url")} placeholder="https://dev.azure.com/your-org" />
              {form.formState.errors.organization_url && (
                <p className="text-xs text-destructive">{form.formState.errors.organization_url.message}</p>
              )}
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="conn-name">Connection Name</Label>
                <Input id="conn-name" {...form.register("connection_name")} placeholder="My Azure Org" />
                {form.formState.errors.connection_name && (
                  <p className="text-xs text-destructive">{form.formState.errors.connection_name.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="pat">Personal Access Token</Label>
                <Input id="pat" type="password" {...form.register("pat")} placeholder="PAT" />
                {form.formState.errors.pat && (
                  <p className="text-xs text-destructive">{form.formState.errors.pat.message}</p>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" loading={form.formState.isSubmitting}>
                Connect
              </Button>
              <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            </div>
          </form>
        </PremiumCard>
      )}

      {connections.length > 0 && (
        <Button onClick={onConnected}>Continue to Repository Selection</Button>
      )}

      <Dialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove connection?</DialogTitle>
            <DialogDescription>This will not delete registered repositories.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete}>Remove</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
