import { Card, SectionHeader } from "../primitives";

const stages = ["分类", "切分", "抽取", "归一", "分集"];

export default function StageStepper() {
  return (
    <Card>
      <SectionHeader title="阶段进度" />
      <div className="flex items-center gap-2">
        {stages.map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <span className="px-3 py-1.5 rounded-sm text-sm font-medium bg-panel-muted text-txt-faint">{s}</span>
            {i < stages.length - 1 && <span className="text-txt-faint">→</span>}
          </div>
        ))}
      </div>
    </Card>
  );
}
