"use client";

import { motion } from "framer-motion";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export type WorkbenchStep = "connect" | "repository" | "module" | "scan";

const STEPS: { id: WorkbenchStep; label: string; description: string }[] = [
  { id: "connect", label: "Connect / Upload", description: "Azure DevOps or ZIP" },
  { id: "repository", label: "Repository", description: "Project, repo, branch" },
  { id: "module", label: "Module", description: "Select feature scope" },
  { id: "scan", label: "Scan & Explore", description: "Build knowledge graph" },
];

interface StepIndicatorProps {
  currentStep: WorkbenchStep;
  completedSteps: WorkbenchStep[];
  onStepClick?: (step: WorkbenchStep) => void;
}

export function StepIndicator({ currentStep, completedSteps, onStepClick }: StepIndicatorProps) {
  const currentIndex = STEPS.findIndex((s) => s.id === currentStep);

  return (
    <nav className="space-y-1">
      {STEPS.map((step, i) => {
        const done = completedSteps.includes(step.id);
        const active = step.id === currentStep;
        const clickable = done || i <= currentIndex;

        return (
          <button
            key={step.id}
            type="button"
            disabled={!clickable || !onStepClick}
            onClick={() => onStepClick?.(step.id)}
            className={cn(
              "flex w-full items-start gap-3 rounded-lg px-3 py-3 text-left transition-all",
              active && "bg-primary/10",
              clickable && onStepClick && "hover:bg-accent cursor-pointer",
              !clickable && "opacity-50 cursor-default"
            )}
          >
            <div
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-xs font-semibold transition-colors",
                done && "border-green-500 bg-green-500/20 text-green-600 dark:text-green-400",
                active && !done && "border-primary bg-primary text-primary-foreground",
                !active && !done && "border-muted-foreground/30 text-muted-foreground"
              )}
            >
              {done ? <Check className="h-4 w-4" /> : i + 1}
            </div>
            <div className="min-w-0 pt-0.5">
              <p className={cn("text-sm font-medium", active && "text-primary")}>{step.label}</p>
              <p className="text-xs text-muted-foreground">{step.description}</p>
            </div>
            {active && (
              <motion.div
                layoutId="step-indicator"
                className="absolute left-0 hidden"
                transition={{ type: "spring", stiffness: 300, damping: 30 }}
              />
            )}
          </button>
        );
      })}
    </nav>
  );
}

export { STEPS };
