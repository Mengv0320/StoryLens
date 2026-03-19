import type { LucideIcon } from "lucide-react";

type Props = {
  label: string;
  value: number;
  icon: LucideIcon;
};

export default function StatCard({ label, value, icon: Icon }: Props) {
  return (
    <div className="rounded-md border border-border bg-panel shadow-sm p-5 flex items-center gap-4">
      <div className="rounded-lg bg-accent-soft p-2.5 text-accent">
        <Icon size={22} />
      </div>
      <div>
        <p className="text-3xl font-bold text-txt">{value.toLocaleString()}</p>
        <p className="text-sm text-txt-soft">{label}</p>
      </div>
    </div>
  );
}
