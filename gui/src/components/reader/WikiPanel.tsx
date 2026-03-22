import { Users, Clock } from "lucide-react";

type Props = {
  characters: string[];
  timeline: any[];
};

export default function WikiPanel({ characters, timeline }: Props) {
  return (
    <div className="h-full overflow-y-auto p-4 space-y-6">
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-txt font-medium border-b border-border pb-2">
          <Users size={16} className="text-accent" />
          <h3>出场角色档案</h3>
        </div>
        {characters.length === 0 ? (
          <p className="text-xs text-txt-faint">暂无登场角色</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {characters.map((c) => (
              <span key={c} className="px-2 py-1 text-xs rounded-md bg-accent-soft text-accent border border-accent/20">
                {c}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-3">
        <div className="flex items-center gap-2 text-txt font-medium border-b border-border pb-2">
          <Clock size={16} className="text-warning" />
          <h3>前情纪要 (Timeline)</h3>
        </div>
        {timeline.length === 0 ? (
          <p className="text-xs text-txt-faint">暂无事件纪要</p>
        ) : (
          <div className="space-y-4">
            {timeline.map((ev, i) => (
              <div key={i} className="relative pl-4 border-l-2 border-border/50">
                <div className="absolute w-2 h-2 rounded-full bg-warning -left-[5px] top-1.5"></div>
                <div className="text-[10px] text-txt-soft mb-0.5">{ev.chapterTitle}</div>
                <p className="text-xs text-txt leading-relaxed">{ev.description}</p>
                {ev.characters && ev.characters.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {ev.characters.map((c: string) => (
                      <span key={c} className="text-[10px] text-accent/80">@{c}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
