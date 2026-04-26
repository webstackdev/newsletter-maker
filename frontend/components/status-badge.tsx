import type { ReactNode } from "react"

type StatusBadgeProps = {
  tone: "positive" | "warning" | "negative" | "neutral"
  children: ReactNode
}

export function StatusBadge({ tone, children }: StatusBadgeProps) {
  const toneClasses = {
    positive: "bg-[#156f68]/15 text-[#156f68]",
    warning: "bg-[#c27a2c]/16 text-[#c27a2c]",
    negative: "bg-[#c55f4d]/15 text-[#c55f4d]",
    neutral: "bg-[#1f2b27]/8 text-[#5d6d67]",
  }

  return (
    <span
      data-tone={tone}
      className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ${toneClasses[tone]}`}
    >
      {children}
    </span>
  )
}
