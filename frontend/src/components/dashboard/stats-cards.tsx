"use client";

import { useEffect, useRef } from "react";
import { motion, useInView, useSpring, useTransform } from "framer-motion";
import { Activity, CheckCircle2, Cloud, XCircle } from "lucide-react";
import { PremiumCard } from "@/components/ui/premium-card";
import type { DashboardStats } from "@/lib/types";
import { cn } from "@/lib/utils";

interface StatsCardsProps {
  stats: DashboardStats;
}

function AnimatedNumber({ value }: { value: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const spring = useSpring(0, { stiffness: 80, damping: 20 });
  const display = useTransform(spring, (v) => Math.round(v).toString());

  useEffect(() => {
    if (inView) spring.set(value);
  }, [inView, value, spring]);

  useEffect(() => {
    const unsub = display.on("change", (v) => {
      if (ref.current) ref.current.textContent = v;
    });
    return unsub;
  }, [display]);

  return <span ref={ref}>0</span>;
}

export function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      title: "Total Executions",
      value: stats.total_executions,
      display: stats.total_executions,
      icon: Activity,
      accent: "from-violet-500/20 to-transparent",
      animate: true,
    },
    {
      title: "Success Rate",
      value: stats.success_rate,
      display: `${stats.success_rate}%`,
      icon: CheckCircle2,
      accent: "from-green-500/20 to-transparent",
      animate: false,
    },
    {
      title: "Failed Executions",
      value: stats.failed_executions,
      display: stats.failed_executions,
      icon: XCircle,
      accent: "from-red-500/20 to-transparent",
      animate: true,
    },
    {
      title: "Connected Orgs",
      value: stats.connected_orgs,
      display: stats.connected_orgs,
      icon: Cloud,
      accent: "from-blue-500/20 to-transparent",
      animate: true,
    },
  ];

  return (
    <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
      {cards.map((card, i) => {
        const Icon = card.icon;
        return (
          <motion.div
            key={card.title}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
          >
            <PremiumCard className="relative overflow-hidden">
              <div className={cn("absolute inset-x-0 top-0 h-1 bg-gradient-to-r", card.accent)} />
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">{card.title}</p>
                  <p className="mt-2 text-3xl font-bold tabular-nums">
                    {card.animate ? <AnimatedNumber value={card.value as number} /> : card.display}
                  </p>
                </div>
                <div className="rounded-lg bg-primary/10 p-2">
                  <Icon className="h-5 w-5 text-primary" />
                </div>
              </div>
            </PremiumCard>
          </motion.div>
        );
      })}
    </div>
  );
}
