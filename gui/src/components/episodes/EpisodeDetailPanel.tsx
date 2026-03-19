import type { EpisodeDetail } from "../../lib/types";
import { EmptyState } from "../primitives";

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-sm font-medium text-txt-soft mb-1">{label}</p>
      <div className="text-md text-txt">{children}</div>
    </div>
  );
}

type Props = { detail: EpisodeDetail | null };

export default function EpisodeDetailPanel({ detail }: Props) {
  if (!detail) return <EmptyState message="请选择一集查看详情" />;
  return (
    <div className="p-5 space-y-4 overflow-y-auto">
      <h2 className="text-xl font-semibold text-txt">{detail.title}</h2>
      <p className="text-sm text-txt-faint">{detail.chapterRangeLabel}</p>
      <Section label="核心主题">{detail.coreTheme}</Section>
      <Section label="主冲突">{detail.mainConflict}</Section>
      <Section label="关键事件">
        <ul className="list-disc list-inside space-y-1">
          {detail.keyEvents.map((e, i) => <li key={i}>{e}</li>)}
        </ul>
      </Section>
      <Section label="高潮">{detail.climax}</Section>
      <Section label="集尾钩子">{detail.endingHook}</Section>
      <Section label="单集摘要">
        <p className="leading-relaxed">{detail.summary}</p>
      </Section>
    </div>
  );
}
