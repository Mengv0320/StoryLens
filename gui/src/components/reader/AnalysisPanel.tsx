import { Star, Users } from "lucide-react";
import { Badge } from "../../components/primitives";
import type { AnalysisResult } from "../../features/reader/types";

type Props = {
  analysis: AnalysisResult | null;
  activeEventId: string | null;
  onEventClick: (eventId: string) => void;
};

const scoreVariant = (score: number) => {
  if (score >= 4) return "success" as const;
  if (score >= 3) return "warning" as const;
  return "danger" as const;
};

export default function AnalysisPanel({ analysis, activeEventId, onEventClick }: Props) {
  if (!analysis) {
    return (
      <div className="h-full overflow-y-auto p-4">
        <p className="text-sm text-txt-faint text-center mt-10">该章节暂无分析结果</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {/* Score & Summary */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-txt-soft">重要性</span>
          <Badge label={`${analysis.importanceScore} / 5`} variant={scoreVariant(analysis.importanceScore)} />
        </div>
        <p className="text-xs text-txt-soft">{analysis.importanceReason}</p>
      </div>

      <div className="space-y-1">
        <div className="text-xs font-medium text-txt">章节摘要</div>
        <p className="text-sm text-txt-soft leading-relaxed">{analysis.summary}</p>
      </div>

      {/* Key Events */}
      <div className="space-y-2">
        <div className="text-xs font-medium text-txt">关键事件</div>
        {analysis.keyEvents.map((ev) => {
          const active = ev.id === activeEventId;
          return (
            <button
              key={ev.id}
              onClick={() => onEventClick(ev.id)}
              className={`w-full text-left rounded-md border p-2.5 transition-colors ${
                active
                  ? "border-accent bg-accent-soft"
                  : "border-border hover:border-accent/50 bg-panel"
              }`}
            >
              <p className="text-sm text-txt leading-snug mb-1.5">{ev.description}</p>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="flex items-center gap-0.5 text-xs text-warning">
                  <Star className="w-3 h-3" />
                  {ev.importance}
                </span>
                {ev.characters.map((c) => (
                  <span
                    key={c}
                    className="flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded bg-accent/10 text-accent"
                  >
                    <Users className="w-3 h-3" />
                    {c}
                  </span>
                ))}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
