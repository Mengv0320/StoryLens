import { useState, useCallback } from "react";
import { api } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { useActiveBook } from "../lib/useActiveBook";
import type { NarrativeResult, GroupSummary, TensionPoint } from "../lib/types";
import { Card, SectionHeader, Badge, EmptyState, KeyValue } from "../components/primitives";

function TensionBar({ level }: { level: number }) {
  const pct = (level / 5) * 100;
  const color = level >= 4 ? "bg-danger" : level >= 3 ? "bg-warning" : "bg-accent";
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 rounded-full bg-panel-soft overflow-hidden">
        <div className={`h-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-txt-soft w-4 text-right">{level}</span>
    </div>
  );
}

function TensionCurve({ points }: { points: TensionPoint[] }) {
  if (!points.length) return null;
  const maxH = 80;
  const barW = Math.max(18, Math.min(40, 600 / points.length));
  return (
    <div className="flex items-end gap-1 overflow-x-auto py-2" style={{ minHeight: maxH + 28 }}>
      {points.map((p) => {
        const h = (p.level / 5) * maxH;
        const color = p.level >= 4 ? "bg-danger" : p.level >= 3 ? "bg-warning" : "bg-accent";
        return (
          <div key={p.groupId} className="flex flex-col items-center gap-1" title={p.reason}>
            <div className={`${color} rounded-t`} style={{ width: barW, height: h }} />
            <span className="text-[10px] text-txt-soft truncate" style={{ maxWidth: barW + 8 }}>
              {p.groupId.replace("grp_", "G")}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function GroupCard({ group, isOpen, onToggle }: { group: GroupSummary; isOpen: boolean; onToggle: () => void }) {
  return (
    <Card className="cursor-pointer" onClick={onToggle}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Badge label={group.groupId.replace("grp_", "G")} variant="accent" />
          <span className="text-sm text-txt-soft">{group.chapterRange}</span>
        </div>
        <div className="flex items-center gap-3">
          <TensionBar level={group.tensionLevel} />
          <span className="text-xs text-txt-soft">{isOpen ? "▲" : "▼"}</span>
        </div>
      </div>
      {isOpen && (
        <div className="mt-4 space-y-3 text-sm" onClick={(e) => e.stopPropagation()}>
          <div>
            <div className="font-medium text-txt mb-1">剧情推进</div>
            <p className="text-txt-soft leading-relaxed">{group.plotProgress}</p>
          </div>
          {group.newForeshadowing.length > 0 && (
            <div>
              <div className="font-medium text-txt mb-1">新伏笔</div>
              <ul className="list-disc list-inside text-txt-soft space-y-0.5">
                {group.newForeshadowing.map((f, i) => <li key={`foreshadow-new-${i}-${f.slice(0, 20)}`}>{f}</li>)}
              </ul>
            </div>
          )}
          {group.resolvedForeshadowing.length > 0 && (
            <div>
              <div className="font-medium text-txt mb-1">回收伏笔</div>
              <ul className="list-disc list-inside text-success space-y-0.5">
                {group.resolvedForeshadowing.map((f, i) => <li key={`foreshadow-resolved-${i}-${f.slice(0, 20)}`}>{f}</li>)}
              </ul>
            </div>
          )}
          {group.characterArcs.length > 0 && (
            <div>
              <div className="font-medium text-txt mb-1">角色弧线</div>
              <div className="space-y-1">
                {group.characterArcs.map((a) => (
                  <div key={`arc-${a.name}`} className="flex gap-2">
                    <Badge label={a.name} variant="info" />
                    <span className="text-txt-soft">{a.development}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {group.keyCausality.length > 0 && (
            <div>
              <div className="font-medium text-txt mb-1">因果链</div>
              <div className="space-y-1">
                {group.keyCausality.map((c, i) => (
                  <div key={`cause-${i}-${c.cause.slice(0, 15)}`} className="text-txt-soft">
                    <span className="text-warning">{c.cause}</span>
                    <span className="mx-1">→</span>
                    <span className="text-accent">{c.effect}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {group.subplotThreads.length > 0 && (
            <KeyValue label="活跃支线" value={group.subplotThreads.join("、")} />
          )}
          {group.openQuestions.length > 0 && (
            <KeyValue label="遗留悬念" value={group.openQuestions.join("、")} />
          )}
        </div>
      )}
    </Card>
  );
}

export default function NarrativePage() {
  const { activeBook } = useActiveBook();
  const fetcher = useCallback(
    () => activeBook
      ? api.getBookNarrative(activeBook.bookId)
      : api.getNarrative(),
    [activeBook?.bookId],
  );
  const { data, loading } = usePolling<NarrativeResult>(fetcher, 15_000);
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());

  const toggleGroup = (id: string) => {
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  if (loading && !data) {
    return (
      <div className="p-4 md:p-6 space-y-5">
        <h1 className="text-2xl font-semibold text-txt">叙事分析</h1>
        <EmptyState message="正在加载..." />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-4 md:p-6 space-y-5">
        <h1 className="text-2xl font-semibold text-txt">叙事分析</h1>
        <EmptyState message="暂无叙事分析数据，请先完成标准分析。" />
      </div>
    );
  }

  const syn = data.bookSynthesis;
  const groups = data.groupSummaries ?? [];

  return (
    <div className="p-4 md:p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">叙事分析</h1>

      {/* Book Synthesis */}
      {syn && (
        <>
          <Card>
            <SectionHeader title={syn.title || "全书综合"} extra={<Badge label={`${groups.length} 组`} variant="accent" />} />
            <div className="space-y-3 text-sm">
              <div>
                <div className="font-medium text-txt mb-1">主线剧情</div>
                <p className="text-txt-soft leading-relaxed">{syn.mainPlotline}</p>
              </div>
              {syn.themes.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {syn.themes.map((t) => <Badge key={`theme-${t}`} label={t} variant="info" />)}
                </div>
              )}
            </div>
          </Card>

          {/* Tension Curve */}
          {syn.tensionCurve.length > 0 && (
            <Card>
              <SectionHeader title="张力曲线" />
              <TensionCurve points={syn.tensionCurve} />
            </Card>
          )}

          {/* Character Arcs */}
          {syn.characterArcs.length > 0 && (
            <Card>
              <SectionHeader title="角色弧线" />
              <div className="space-y-3">
                {syn.characterArcs.map((a) => (
                  <div key={`char-${a.name}`} className="border-b border-border/50 pb-2 last:border-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge label={a.name} variant="accent" />
                    </div>
                    <p className="text-sm text-txt-soft">{a.arcSummary}</p>
                    {a.keyMoments.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {a.keyMoments.map((m, j) => (
                          <span key={`moment-${j}-${m.slice(0, 15)}`} className="text-xs bg-panel-muted px-1.5 py-0.5 rounded text-txt-soft">{m}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Foreshadowing Tracker */}
          {syn.foreshadowingTracker.length > 0 && (
            <Card>
              <SectionHeader title="伏笔追踪" />
              <div className="space-y-2 text-sm">
                {syn.foreshadowingTracker.map((f) => (
                  <div key={`ftrack-${f.setupGroup}-${f.setup.slice(0, 20)}`} className="flex items-start gap-2">
                    <Badge label={f.resolvedGroup ? "已回收" : "未回收"} variant={f.resolvedGroup ? "success" : "warning"} />
                    <div>
                      <span className="text-txt">{f.setup}</span>
                      <span className="text-txt-soft ml-2 text-xs">
                        埋设于 {f.setupGroup.replace("grp_", "G")}
                        {f.resolvedGroup && ` → 回收于 ${f.resolvedGroup.replace("grp_", "G")}`}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Subplot Summary */}
          {syn.subplotSummary.length > 0 && (
            <Card>
              <SectionHeader title="支线概要" />
              <div className="space-y-2 text-sm">
                {syn.subplotSummary.map((s) => (
                  <div key={`subplot-${s.thread}`} className="flex items-start gap-2">
                    <Badge label={s.status === "resolved" ? "已完结" : "进行中"} variant={s.status === "resolved" ? "success" : "accent"} />
                    <div>
                      <span className="font-medium text-txt">{s.thread}</span>
                      <span className="text-txt-soft ml-2">{s.summary}</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Open Questions */}
          {syn.openQuestions.length > 0 && (
            <Card>
              <SectionHeader title="未解悬念" />
              <ul className="list-disc list-inside text-sm text-txt-soft space-y-1">
                {syn.openQuestions.map((q, i) => <li key={`oq-${i}-${q.slice(0, 20)}`}>{q}</li>)}
              </ul>
            </Card>
          )}

          {/* Quality Notes */}
          {syn.qualityNotes.length > 0 && (
            <Card>
              <SectionHeader title="质量备注" />
              <ul className="list-disc list-inside text-sm text-txt-soft space-y-1">
                {syn.qualityNotes.map((n, i) => <li key={`qn-${i}-${n.slice(0, 20)}`}>{n}</li>)}
              </ul>
            </Card>
          )}
        </>
      )}

      {/* Group Summaries */}
      <SectionHeader title="分组摘要" extra={<span className="text-sm text-txt-soft">{groups.length} 组</span>} />
      <div className="space-y-3">
        {groups.length === 0 ? (
          <EmptyState message="暂无分组数据。" />
        ) : (
          groups.map((g) => (
            <GroupCard
              key={g.groupId}
              group={g}
              isOpen={openGroups.has(g.groupId)}
              onToggle={() => toggleGroup(g.groupId)}
            />
          ))
        )}
      </div>
    </div>
  );
}
