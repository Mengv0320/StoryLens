import type { ProgressSnapshot } from "../../lib/types";
import { Card, SectionHeader } from "../primitives";

const STAGES = ["分类", "切分", "抽取", "分集归纳"];

type Props = { progress: ProgressSnapshot };

export default function ProgressSection({ progress }: Props) {
  const pct = progress.totalChapters > 0
    ? Math.round((progress.completedChapters / progress.totalChapters) * 100)
    : 0;

  const currentIdx = STAGES.indexOf(progress.currentStage);

  return (
    <Card>
      <SectionHeader title="当前进度" />

      {/* stage flow */}
      <div className="flex items-center gap-2 mb-5 flex-wrap">
        {STAGES.map((stage, i) => {
          const done = i < currentIdx;
          const active = i === currentIdx;
          return (
            <div key={stage} className="flex items-center gap-2">
              {i > 0 && <span className="text-txt-faint">→</span>}
              <span
                className={`text-sm px-2.5 py-1 rounded-md ${
                  done
                    ? "bg-success-soft text-success"
                    : active
                      ? "bg-accent-soft text-accent font-semibold"
                      : "bg-panel-muted text-txt-faint"
                }`}
              >
                {stage}
              </span>
            </div>
          );
        })}
      </div>

      {/* progress bar */}
      <div className="w-full h-3 rounded-full bg-panel-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-accent transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex justify-between mt-2 text-sm text-txt-soft">
        <span>{progress.completedChapters} / {progress.totalChapters} 章</span>
        <span>{pct}%</span>
      </div>
    </Card>
  );
}
