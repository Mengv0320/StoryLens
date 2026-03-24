import { useState, useEffect, useMemo } from "react";
import { api } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { useActiveBook } from "../lib/useActiveBook";
import { Card, SectionHeader, Badge, EmptyState, KeyValue, SkeletonLine } from "../components/primitives";
import { displayEventType } from "../lib/eventTypes";
import { useShowMore } from "../hooks/useShowMore";
import { ChevronDown, X } from "lucide-react";

export default function TimelinePage() {
  const { activeBook } = useActiveBook();
  const { data: items } = usePolling(
    () => activeBook ? api.getBookTimeline(activeBook.bookId) : api.getTimeline(),
    10_000,
  );
  const [filter, setFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [groupSearch, setGroupSearch] = useState("");
  const [groupsExpanded, setGroupsExpanded] = useState(false);

  const filtered = items?.filter(i => !filter || i.eventGroup === filter) ?? [];
  const groups = [...new Set(items?.map(i => i.eventGroup) ?? [])];
  const compactMode = groups.length > 10;
  const matchedGroups = useMemo(() => {
    if (!groupSearch.trim()) return groups;
    const q = groupSearch.trim().toLowerCase();
    return groups.filter(g => g.toLowerCase().includes(q));
  }, [groups, groupSearch]);

  const { visible: visibleItems, hasMore, showMore, reset, total } = useShowMore(filtered, 30);
  useEffect(() => { reset(); }, [activeBook?.bookId, filter, reset]);
  const selected = filtered.find(i => i.id === selectedId) ?? null;

  return (
    <div className="p-4 md:p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">时间线</h1>

      {/* Filter section */}
      {!compactMode ? (
        /* Few groups: simple button row */
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setFilter("")}
            className={`text-xs px-3 py-1 rounded-md transition-colors ${!filter ? "bg-accent text-txt-inverse" : "bg-panel-muted text-txt-soft hover:bg-border"}`}
          >
            全部
          </button>
          {groups.map(g => (
            <button
              key={g}
              onClick={() => setFilter(g)}
              className={`text-xs px-3 py-1 rounded-md transition-colors ${filter === g ? "bg-accent text-txt-inverse" : "bg-panel-muted text-txt-soft hover:bg-border"}`}
            >
              {g}
            </button>
          ))}
        </div>
      ) : (
        /* Many groups: compact filter with search */
        <Card className="!p-4">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => { setFilter(""); setGroupsExpanded(false); }}
              className={`text-xs px-3 py-1.5 rounded-md transition-colors ${!filter ? "bg-accent text-txt-inverse" : "bg-panel-muted text-txt-soft hover:bg-border"}`}
            >
              全部
            </button>
            {filter && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-soft border border-accent/30 text-xs text-accent">
                <span className="truncate max-w-[200px]">{filter}</span>
                <button type="button" onClick={() => setFilter("")} className="hover:text-danger transition-colors">
                  <X size={12} />
                </button>
              </div>
            )}
            <div className="flex-1 min-w-[160px] max-w-xs">
              <input
                value={groupSearch}
                onChange={(e) => { setGroupSearch(e.target.value); setGroupsExpanded(true); }}
                onFocus={() => setGroupsExpanded(true)}
                placeholder={`搜索 ${groups.length} 个分组...`}
                className="w-full h-8 rounded-md border border-border bg-panel px-3 text-xs text-txt placeholder:text-txt-faint outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20"
              />
            </div>
            <button
              type="button"
              onClick={() => setGroupsExpanded(!groupsExpanded)}
              className="flex items-center gap-1 text-xs text-txt-soft hover:text-txt transition-colors"
            >
              {groupsExpanded ? "收起" : "展开"}
              <ChevronDown size={14} className={`transition-transform duration-200 ${groupsExpanded ? "rotate-180" : ""}`} />
            </button>
          </div>
          {groupsExpanded && (
            <div className="mt-3 max-h-32 overflow-y-auto flex flex-wrap gap-1.5 pr-1">
              {matchedGroups.length === 0 ? (
                <span className="text-xs text-txt-faint py-2">无匹配分组</span>
              ) : matchedGroups.map(g => (
                <button
                  key={g}
                  onClick={() => { setFilter(g); setGroupsExpanded(false); setGroupSearch(""); }}
                  className={`text-xs px-2.5 py-1 rounded-md transition-colors truncate max-w-[240px] ${
                    filter === g ? "bg-accent text-txt-inverse" : "bg-panel-soft text-txt-soft hover:bg-panel-muted hover:text-txt border border-border/50"
                  }`}
                  title={g}
                >
                  {g}
                </button>
              ))}
            </div>
          )}
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="md:col-span-2">
          <Card>
            <SectionHeader title="事件列表" />
            {!items ? (
              <div className="space-y-2 py-2">{Array.from({ length: 6 }, (_, i) => <SkeletonLine key={i} />)}</div>
            ) : !filtered.length ? (
              <EmptyState message="暂无时间线数据" />
            ) : (
              <div className="space-y-1 max-h-[60vh] overflow-y-auto">
                {visibleItems.map(item => (
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
                {hasMore && (
                  <button type="button" onClick={showMore} className="w-full py-2 text-sm text-accent hover:underline">
                    加载更多（已显示 {visibleItems.length}/{total}）
                  </button>
                )}
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
                <KeyValue label="事件类型" value={displayEventType(selected.eventType)} />
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
