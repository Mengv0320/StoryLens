/** Map legacy English event_type values to Chinese labels for display. */
const EVENT_TYPE_MAP: Record<string, string> = {
  conflict: "冲突",
  turning_point: "转折",
  relationship_change: "关系变化",
  status_change: "身份变化",
  foreshadowing: "伏笔",
  payoff: "伏笔回收",
};

export function displayEventType(raw: string): string {
  return EVENT_TYPE_MAP[raw] || raw;
}
