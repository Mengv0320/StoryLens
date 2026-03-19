import type { ReactNode } from "react";

export default function RightInfoPanel({ children }: { children?: ReactNode }) {
  return (
    <aside className="w-[320px] flex-shrink-0 border-l border-border bg-panel-soft overflow-y-auto p-5">
      {children ?? <p className="text-sm text-txt-faint">暂无辅助信息</p>}
    </aside>
  );
}
