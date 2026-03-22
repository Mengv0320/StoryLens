import type { Chapter } from "../../features/reader/types";

type Props = {
  chapters: Chapter[];
  selectedId: string;
  onSelect: (id: string) => void;
};

export default function ChapterSidebar({ chapters, selectedId, onSelect }: Props) {
  return (
    <div className="w-56 shrink-0 border-r border-border overflow-y-auto">
      <div className="p-3 text-xs font-medium text-txt-soft uppercase tracking-wide">章节目录</div>
      <div className="space-y-0.5 pb-4">
        {chapters.map((ch) => {
          const active = ch.id === selectedId;
          return (
            <button
              key={ch.id}
              onClick={() => onSelect(ch.id)}
              className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 transition-colors ${
                active
                  ? "bg-accent-soft text-accent border-l-2 border-accent"
                  : "text-txt-soft hover:bg-panel-soft border-l-2 border-transparent"
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${ch.analyzed ? "bg-success" : "bg-panel-muted"}`} />
              <span className="truncate">
                {ch.index}. {ch.title}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
