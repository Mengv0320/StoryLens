import type { EpisodeListItem } from "../../lib/types";
import { Badge } from "../primitives";

const statusVariant: Record<EpisodeListItem["status"], "success" | "danger" | "warning"> = {
  completed: "success",
  failed: "danger",
  warning: "warning",
};

type Props = {
  items: EpisodeListItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

export default function EpisodeList({ items, selectedId, onSelect }: Props) {
  return (
    <div className="border-r border-border overflow-y-auto">
      {items.map((ep) => (
        <div
          key={ep.id}
          onClick={() => onSelect(ep.id)}
          className={`px-4 py-3 border-b border-border/50 cursor-pointer transition-colors ${
            ep.id === selectedId ? "bg-accent-soft" : "hover:bg-panel-muted"
          }`}
        >
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-mono text-txt-soft">{ep.indexLabel}</span>
            <Badge label={ep.status === "completed" ? "完成" : ep.status === "failed" ? "失败" : "警告"} variant={statusVariant[ep.status]} />
          </div>
          <p className="text-md text-txt font-medium">{ep.title}</p>
          <p className="text-xs text-txt-faint mt-0.5">{ep.chapterRangeLabel}</p>
        </div>
      ))}
    </div>
  );
}
