import { BookOpen, Film, Zap, Users, Layers, AlertTriangle } from "lucide-react";
import type { RunSummary } from "../../lib/types";
import StatCard from "./StatCard";

type Props = { summary: RunSummary };

export default function StatsRow({ summary }: Props) {
  const stats = [
    { label: "章节数", value: summary.chapterCount, icon: BookOpen },
    { label: "场景数", value: summary.sceneCount, icon: Film },
    { label: "事件数", value: summary.eventCount, icon: Zap },
    { label: "角色数", value: summary.characterCount, icon: Users },
    { label: "分集数", value: summary.episodeCount, icon: Layers },
    { label: "失败数", value: summary.failureCount, icon: AlertTriangle },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {stats.map((s) => (
        <StatCard key={s.label} label={s.label} value={s.value} icon={s.icon} />
      ))}
    </div>
  );
}
