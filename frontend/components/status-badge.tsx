import type { ReactNode } from "react";

type StatusBadgeProps = {
  tone: "positive" | "warning" | "negative" | "neutral";
  children: ReactNode;
};

export function StatusBadge({ tone, children }: StatusBadgeProps) {
  return <span className={`status-badge status-badge--${tone}`}>{children}</span>;
}