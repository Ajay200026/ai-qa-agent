"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

export const WIZARD_STEPS = [
  { id: "org", label: "Salesforce Org", description: "Pick connected org" },
  { id: "scenario", label: "Scenario", description: "Template & test pack" },
  { id: "libraries", label: "Libraries", description: "Account query & Login As" },
  { id: "review", label: "Review & Run", description: "Confirm and start" },
] as const;

export type WizardStepId = (typeof WIZARD_STEPS)[number]["id"];

interface ExecutionWizardProps {
  currentStep: WizardStepId;
  onStepClick?: (step: WizardStepId) => void;
  children: React.ReactNode;
}

export function ExecutionWizard({ currentStep, onStepClick, children }: ExecutionWizardProps) {
  const currentIndex = WIZARD_STEPS.findIndex((s) => s.id === currentStep);

  return (
    <div className="grid gap-8 lg:grid-cols-[240px_1fr]">
      <nav className="space-y-1 lg:sticky lg:top-6 lg:self-start">
        {WIZARD_STEPS.map((step, index) => {
          const done = index < currentIndex;
          const active = step.id === currentStep;
          return (
            <motion.button
              key={step.id}
              type="button"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
              onClick={() => onStepClick?.(step.id)}
              className={cn(
                "flex w-full items-start gap-3 rounded-lg border px-3 py-3 text-left transition-colors",
                active && "border-primary bg-primary/5",
                done && !active && "border-muted bg-muted/30",
                !active && !done && "border-transparent hover:bg-muted/40"
              )}
            >
              <span
                className={cn(
                  "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                  active && "bg-primary text-primary-foreground",
                  done && "bg-green-600 text-white",
                  !active && !done && "bg-muted text-muted-foreground"
                )}
              >
                {done ? <Check className="h-3.5 w-3.5" /> : index + 1}
              </span>
              <span>
                <span className="block text-sm font-medium">{step.label}</span>
                <span className="block text-xs text-muted-foreground">{step.description}</span>
              </span>
            </motion.button>
          );
        })}
        <p className="px-3 pt-2 text-xs text-muted-foreground">
          Need a new org?{" "}
          <Link href="/salesforce-orgs" className="underline">
            Manage Salesforce Orgs
          </Link>
        </p>
      </nav>
      <div className="min-w-0 space-y-6">{children}</div>
    </div>
  );
}
