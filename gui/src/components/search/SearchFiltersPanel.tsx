import { SlidersHorizontal } from "lucide-react";
import type { SearchFilters } from "../../hooks/useSearchState";

interface SearchFiltersPanelProps {
  filters: SearchFilters;
  onChange: (f: Partial<SearchFilters>) => void;
  className?: string;
}

const EVENT_TYPES = [
  { value: "", label: "全部类型" },
  { value: "conflict", label: "冲突" },
  { value: "turning_point", label: "转折点" },
  { value: "relationship_change", label: "关系变化" },
  { value: "status_change", label: "状态变化" },
  { value: "foreshadowing", label: "伏笔" },
  { value: "payoff", label: "伏笔回收" },
];

const FLAG_OPTIONS: { key: string; label: string }[] = [
  { key: "involves_protagonist", label: "涉及主角" },
  { key: "involves_identity_reveal", label: "身份揭露" },
  { key: "involves_faction_change", label: "阵营变化" },
  { key: "involves_death_or_breakthrough", label: "死亡/突破" },
  { key: "involves_relationship_change", label: "关系变动" },
];

export function SearchFiltersPanel({
  filters,
  onChange,
  className = "",
}: SearchFiltersPanelProps) {
  const currentFlags = filters.flags || {};

  const toggleFlag = (key: string) => {
    const next = { ...currentFlags };
    if (next[key]) {
      delete next[key];
    } else {
      next[key] = true;
    }
    onChange({ flags: Object.keys(next).length > 0 ? next : undefined });
  };

  return (
    <div className={`bg-panel border border-border rounded-card p-3 ${className}`}>
      <div className="flex items-center gap-1.5 mb-3">
        <SlidersHorizontal size={14} className="text-txt-secondary" />
        <span className="text-xs font-medium text-txt-secondary">高级筛选</span>
      </div>

      <div className="mb-3">
        <label className="text-xs text-txt-secondary mb-1 block">事件类型</label>
        <select
          value={filters.event_type || ""}
          onChange={(e) =>
            onChange({ event_type: e.target.value || undefined })
          }
          className="w-full bg-bg border border-border rounded px-2 py-1 text-xs text-txt outline-none focus:border-accent"
        >
          {EVENT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      <div className="mb-3">
        <label className="text-xs text-txt-secondary mb-1 block">
          重要度范围: {filters.min_importance ?? 1} - {filters.max_importance ?? 5}
        </label>
        <div className="flex items-center gap-2">
          <input
            type="range"
            min={1}
            max={5}
            value={filters.min_importance ?? 1}
            onChange={(e) =>
              onChange({ min_importance: Number(e.target.value) })
            }
            className="flex-1 accent-accent"
          />
          <span className="text-xs text-txt-secondary">至</span>
          <input
            type="range"
            min={1}
            max={5}
            value={filters.max_importance ?? 5}
            onChange={(e) =>
              onChange({ max_importance: Number(e.target.value) })
            }
            className="flex-1 accent-accent"
          />
        </div>
      </div>

      <div>
        <label className="text-xs text-txt-secondary mb-1.5 block">事件标记</label>
        <div className="flex flex-wrap gap-1.5">
          {FLAG_OPTIONS.map((opt) => {
            const active = !!currentFlags[opt.key];
            return (
              <button
                key={opt.key}
                onClick={() => toggleFlag(opt.key)}
                className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${
                  active
                    ? "bg-accent/10 text-accent border-accent/30"
                    : "bg-bg text-txt-secondary border-border hover:border-accent/20"
                }`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
