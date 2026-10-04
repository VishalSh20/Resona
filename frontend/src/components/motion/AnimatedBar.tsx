import { motion } from "framer-motion";

import { cn } from "@/lib/utils";

const EASE = [0.22, 1, 0.36, 1] as const;

interface AnimatedBarProps {
  /** 0 → 1. */
  fill: number;
  delay?: number;
  duration?: number;
  className?: string;
  barClassName?: string;
  trackClassName?: string;
}

/** A thin technical progress bar that grows from 0 → fill on scroll-in. */
export function AnimatedBar({
  fill,
  delay = 0,
  duration = 0.9,
  className,
  barClassName,
  trackClassName,
}: AnimatedBarProps) {
  return (
    <div
      className={cn(
        "h-1.5 w-full overflow-hidden rounded-full bg-border",
        trackClassName,
        className,
      )}
    >
      <motion.div
        className={cn("h-full rounded-full bg-foreground", barClassName)}
        initial={{ width: 0 }}
        whileInView={{ width: `${Math.max(0, Math.min(1, fill)) * 100}%` }}
        viewport={{ once: true }}
        transition={{ duration, delay, ease: EASE }}
      />
    </div>
  );
}
