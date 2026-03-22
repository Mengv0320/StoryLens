import { useState } from "react";
import { api } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { useActiveBook } from "../lib/useActiveBook";
import { Card, SectionHeader, Badge, EmptyState, KeyValue } from "../components/primitives";

export default function TimelinePage() {
  const { activeBook } = useActiveBook();
  const { data: items } = usePolling(
    () => activeBook ? api.getBookTimeline(activeBook.bookId) : api.getTimeline(),
    10_000,
  );
  const [filter, setFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const filtered = items?.filter(i => !filter || i.eventGroup === filter) ?? [];
  const groups = [...new Set(items?.map(i => i.eventGroup) ?? [])];
  const selected = filtered.find(i => i.id === selectedId) ?? null;

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">时间线</h1>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setFilter("")}
          className={`text-xs px-3 py-1 rounded ${!filter ? "bg-accent text-white" : "bg-panel-muted text-txt-soft hover:bg-border"}`}
        >
          全部
        </button>
        {groups.map(g => (
          <button
            key={g}
            onClick={() => setFilter(g)}
            className={`text-xs px-3 py-1 rounded ${filter === g ? "bg-accent text-white" : "bg-panel-muted text-txt-soft hover:bg-border"}`}
          >
            {g}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="md:col-span-2">
          <Card>
            <SectionHeader title="事件列表" />
            {!filtered.length ? (
              <EmptyState message="暂无时间线数据" />
            ) : (
              <div className="space-y-1 max-h-[60vh] overflow-y-auto">
                {filtered.map(item => (
                  <button
                    key={item.id}
                    onClick={() => setSelectedId(item.id)}
                    className={`w-full text-left p-2 rounded text-sm flex items-center justify-between gap-2 ${
                      selectedId === item.id ? "bg-accent-soft border border-accent" : "hover:bg-panel-muted border border-transparent"
                    }`}
                  >
                    <div className="min-w-0">
                      <span className="text-txt font-medium">{item.title}</span>
                      <div className="text-xs text-txt-soft">{item.chapterRangeLabel}</div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <Badge label={item.eventGroup} variant="info" />
                      <span className="text-xs text-txt-soft">重要度 {item.importance}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="md:col-span-1">
          <Card>
            <SectionHeader title="事件详情" />
            {!selected ? (
              <EmptyState message="选择事件查看详情" />
            ) : (
              <div className="space-y-0.5">
                <KeyValue label="标题" value={selected.title} />
                <KeyValue label="章节范围" value={selected.chapterRangeLabel} />
                <KeyValue label="事件类型" value={selected.eventType} />
                <KeyValue label="事件分组" value={<Badge label={selected.eventGroup} variant="info" />} />
                <KeyValue label="重要度" value={selected.importance} />
                <KeyValue label="相关角色" value={selected.characters.join("、") || "—"} />
                <KeyValue label="摘要" value={selected.summary} />
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
