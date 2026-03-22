import { useState, useEffect, useRef, useCallback } from "react";
import { ChevronUp, ChevronDown } from "lucide-react";
import { api } from "../../lib/api";
import { usePolling } from "../../lib/usePolling";

export default function RunLogDrawer() {
  const [open, setOpen] = useState(false);
  const { data: logs } = usePolling(() => api.getLogs(), 3_000, open);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const isNearBottom = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 60;
  }, []);

  useEffect(() => {
    if (open && bottomRef.current && isNearBottom()) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, open, isNearBottom]);

  const items = logs ?? [];

  return (
    <div className={`flex-shrink-0 border-t border-border bg-panel transition-all ${open ? "h-60" : "h-10"}`}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full h-10 flex items-center justify-between px-5 text-sm text-txt-soft hover:bg-panel-muted"
      >
        <span>运行日志 ({items.length})</span>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && (
        <div ref={scrollContainerRef} className="overflow-y-auto h-[200px] px-5 pb-3 font-mono text-xs">
          {items.length === 0 ? (
            <div className="py-4 text-center text-txt-faint">暂无日志</div>
          ) : items.map((log, i) => (
            <div key={`${log.timestamp}-${log.event}-${i}`} className={`py-1 border-b border-border/50 flex gap-4 ${log.errorType ? "text-danger" : "text-txt-soft"}`}>
              <span className="w-44 flex-shrink-0">{log.timestamp}</span>
              <span className="w-28 flex-shrink-0">{log.event}</span>
              <span>{log.stage}{log.chapterId ? ` / ${log.chapterId}` : ""}{log.error ? ` - ${log.error}` : ""}</span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}
