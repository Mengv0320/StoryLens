import { useState, useEffect } from "react";
import { api } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { useActiveBook } from "../lib/useActiveBook";
import type { CharacterDetail } from "../lib/types";
import { Card, SectionHeader, Badge, EmptyState, KeyValue } from "../components/primitives";

const relVariant: Record<string, "danger" | "warning" | "success" | "info" | "accent" | "default"> = {
  hostile: "danger", suspicious: "warning", allied: "success",
  subordinate: "info", mentor: "accent", family: "accent",
  romantic: "accent", unknown: "default",
};

export default function CharactersPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CharacterDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const { activeBook } = useActiveBook();

  const { data: characters } = usePolling(
    () => activeBook ? api.getBookCharacters(activeBook.bookId) : api.getCharacters(),
    10_000,
  );

  useEffect(() => {
    if (!selectedId) { setDetail(null); return; }
    let cancelled = false;
    setDetailLoading(true);
    const req = activeBook
      ? api.getBookCharacterDetail(activeBook.bookId, selectedId)
      : api.getCharacterDetail(selectedId);
    req
      .then(d => { if (!cancelled) setDetail(d); })
      .catch(() => { if (!cancelled) setDetail(null); })
      .finally(() => { if (!cancelled) setDetailLoading(false); });
    return () => { cancelled = true; };
  }, [selectedId, activeBook?.bookId]);

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">角色</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="md:col-span-1">
          <Card>
            <SectionHeader title="角色列表" />
            <div className="space-y-1 max-h-[60vh] overflow-y-auto">
              {!characters?.length ? (
                <EmptyState message="暂无角色数据" />
              ) : characters.map(c => (
                <button
                  key={c.id}
                  onClick={() => setSelectedId(c.id)}
                  className={`w-full text-left p-2 rounded text-sm flex items-center justify-between gap-2 ${
                    selectedId === c.id ? "bg-accent-soft border border-accent" : "hover:bg-panel-muted border border-transparent"
                  }`}
                >
                  <div className="min-w-0">
                    <span className="text-txt font-medium">{c.name}</span>
                    {c.faction && <Badge label={c.faction} variant="info" />}
                    <div className="text-xs text-txt-soft">别名 {c.aliasCount} · 事件 {c.eventCount}</div>
                  </div>
                </button>
              ))}
            </div>
          </Card>
        </div>

        <div className="md:col-span-2">
          <Card>
            <SectionHeader title="角色详情" />
            {!selectedId ? (
              <EmptyState message="选择左侧角色查看详情" />
            ) : detailLoading ? (
              <div className="py-8 text-center text-txt-soft text-sm">加载中...</div>
            ) : !detail ? (
              <EmptyState message="无法加载详情" />
            ) : (
              <div className="space-y-4">
                <div className="space-y-0.5">
                  <KeyValue label="姓名" value={detail.name} />
                  {detail.identity && <KeyValue label="身份" value={detail.identity} />}
                  {detail.faction && <KeyValue label="阵营" value={detail.faction} />}
                  {detail.currentGoal && <KeyValue label="当前目标" value={detail.currentGoal} />}
                  {detail.aliases.length > 0 && (
                    <KeyValue label="别名" value={detail.aliases.join("、")} />
                  )}
                </div>

                {detail.relationships.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-txt mb-2">关系</h3>
                    <div className="space-y-1">
                      {detail.relationships.map((r, i) => (
                        <div key={i} className="flex items-center gap-2 text-sm py-1 border-b border-border/50">
                          <Badge label={r.relationType} variant={relVariant[r.relationType] ?? "default"} />
                          <span className="text-txt font-medium">{r.targetName}</span>
                          {r.note && <span className="text-txt-soft text-xs">— {r.note}</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {detail.recentEvents.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-txt mb-2">近期事件</h3>
                    <ul className="space-y-1 text-sm text-txt-soft">
                      {detail.recentEvents.map((e, i) => (
                        <li key={i} className="py-0.5">· {e}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
