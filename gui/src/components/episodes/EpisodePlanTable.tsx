import type { EpisodePlanItem } from "../../lib/types";

type Props = { items: EpisodePlanItem[] };

export default function EpisodePlanTable({ items }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-panel-muted text-txt-soft font-medium text-left">
            <th className="px-4 py-3 w-16">集号</th>
            <th className="px-4 py-3">标题</th>
            <th className="px-4 py-3">覆盖章节</th>
            <th className="px-4 py-3">核心冲突</th>
            <th className="px-4 py-3">集尾钩子</th>
          </tr>
        </thead>
        <tbody>
          {items.map((ep, i) => (
            <tr key={ep.id} className={`border-b border-border/50 ${i % 2 === 1 ? "bg-panel-soft" : ""}`}>
              <td className="px-4 py-3 font-mono text-txt-soft">{String(i + 1).padStart(2, "0")}</td>
              <td className="px-4 py-3 text-txt font-medium">{ep.title}</td>
              <td className="px-4 py-3 text-txt-soft">{ep.chapterRangeLabel}</td>
              <td className="px-4 py-3 text-txt">{ep.mainConflict}</td>
              <td className="px-4 py-3 text-txt">{ep.endingHook}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
