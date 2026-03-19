import type { TimelineItem } from "../../lib/types";
import { Badge } from "../primitives";

type Props = {
  items: TimelineItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

export default function TimelineView({ items, selectedId, onSelect }: Props) {
  return (
    <div className="relative pl-6">
      <div className="absolute left-[11px] top-0 bottom-0 w-0.5 bg-border" />
      {items.map((evt) => (
        <div
          key={evt.id}
          onClick={() => onSelect(evt.id)}
          className={`relative pl-6 pb-6 cursor-pointer group ${evt.id === selectedId ? "opacity-100" : "opacity-80 hover:opacity-100"}`}
        >
          <div className={`absolute left-0 top-1.5 w-3 h-3 rounded-full border-2 ${
            evt.id === selectedId ? "bg-accent border-accent" : "bg-panel border-border group-hover:border-accent"
          }`} />
          <div className={`rounded-md border p-4 transition-colors ${
            evt.id === selectedId ? "border-accent bg-accent-soft" : "border-border bg-panel hover:bg-panel-muted"
          }`}>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-md font-medium text-txt">{evt.title}</span>
              <Badge label={evt.eventType} variant={evt.eventGroup === "主线" ? "accent" : "default"} />
              {evt.importance >= 4 && <Badge label={`${evt.importance}`} variant="warning" />}
            </div>
            <p className="text-xs text-txt-faint mb-2">{evt.chapterRangeLabel}</p>
            <div className="flex gap-1.5 flex-wrap">
              {evt.characters.map((c) => (
                <span key={c} className="text-xs px-2 py-0.5 rounded-pill bg-panel-muted text-txt-soft">{c}</span>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
