import type { CharacterDetail } from "../../lib/types";
import { EmptyState, Badge } from "../primitives";

const relColors: Record<string, "danger" | "success" | "info" | "accent" | "warning" | "default"> = {
  hostile: "danger",
  suspicious: "warning",
  allied: "success",
  subordinate: "default",
  mentor: "info",
  family: "accent",
  romantic: "accent",
  unknown: "default",
};

const relLabels: Record<string, string> = {
  hostile: "敌对", suspicious: "怀疑", allied: "同盟", subordinate: "下属",
  mentor: "师徒", family: "亲属", romantic: "情感", unknown: "未知",
};

type Props = { detail: CharacterDetail | null };

export default function CharacterCard({ detail }: Props) {
  if (!detail) return <EmptyState message="请选择一个角色查看详情" />;

  return (
    <div className="p-5 space-y-4 overflow-y-auto">
      <h2 className="text-xl font-semibold text-txt">{detail.name}</h2>

      {detail.aliases.length > 0 && (
        <div>
          <p className="text-sm font-medium text-txt-soft mb-1">别名</p>
          <div className="flex gap-2 flex-wrap">
            {detail.aliases.map((a) => <Badge key={a} label={a} variant="default" />)}
          </div>
        </div>
      )}

      {detail.identity && (
        <div>
          <p className="text-sm font-medium text-txt-soft mb-1">身份</p>
          <p className="text-md text-txt">{detail.identity}</p>
        </div>
      )}

      {detail.faction && (
        <div>
          <p className="text-sm font-medium text-txt-soft mb-1">阵营</p>
          <p className="text-md text-txt">{detail.faction}</p>
        </div>
      )}

      {detail.currentGoal && (
        <div>
          <p className="text-sm font-medium text-txt-soft mb-1">当前目标</p>
          <p className="text-md text-txt">{detail.currentGoal}</p>
        </div>
      )}

      {detail.recentEvents.length > 0 && (
        <div>
          <p className="text-sm font-medium text-txt-soft mb-1">最近事件</p>
          <ul className="list-disc list-inside text-md text-txt space-y-1">
            {detail.recentEvents.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}

      {detail.relationships.length > 0 && (
        <div>
          <p className="text-sm font-medium text-txt-soft mb-2">关系</p>
          <div className="space-y-2">
            {detail.relationships.map((r, i) => (
              <div key={i} className="flex items-center gap-3 text-sm">
                <span className="text-txt font-medium w-20">{r.targetName}</span>
                <Badge label={relLabels[r.relationType] ?? r.relationType} variant={relColors[r.relationType] ?? "default"} />
                {r.note && <span className="text-txt-faint">{r.note}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
