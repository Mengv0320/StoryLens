import type { ReactNode } from "react";

type Props = { children: ReactNode; className?: string; onClick?: () => void };

export function Card({ children, className = "", onClick }: Props) {
  const interactive = !!onClick;
  return (
    <div
      className={`glass-card p-6 ${interactive ? "cursor-pointer hover:border-accent/40" : ""} ${className}`}
      onClick={onClick}
      {...(interactive ? {
        role: "button" as const,
        tabIndex: 0,
        onKeyDown: (e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick?.(); } },
      } : {})}
    >
      {children}
    </div>
  );
}

export function SectionHeader({ title, extra }: { title: string; extra?: ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-lg font-semibold text-txt">{title}</h2>
      {extra}
    </div>
  );
}

export function Badge({ label, variant = "default" }: { label: string; variant?: "default" | "success" | "warning" | "danger" | "info" | "accent" }) {
  const cls: Record<string, string> = {
    default: "bg-panel-muted text-txt-soft",
    success: "bg-success-soft text-success",
    warning: "bg-warning-soft text-warning",
    danger: "bg-danger-soft text-danger",
    info: "bg-info-soft text-info",
    accent: "bg-accent-soft text-accent",
  };
  return <span className={`inline-block text-xs px-3 py-1 rounded-full font-medium tracking-wide shadow-sm border border-transparent ${cls[variant]}`}>{label}</span>;
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center py-16 text-txt-faint text-sm">
      {message}
    </div>
  );
}

export function KeyValue({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between py-1.5 border-b border-border/50 text-sm">
      <span className="text-txt-soft">{label}</span>
      <span className="text-txt font-medium">{value}</span>
    </div>
  );
}
