import type { ExportItem } from "../../lib/types";
import { Copy, FolderOpen, CheckCircle, XCircle } from "lucide-react";

type Props = { item: ExportItem };

export default function ExportCard({ item }: Props) {
  const handleCopy = () => {
    navigator.clipboard.writeText(item.path).catch(() => {});
  };

  return (
    <div className="rounded-md border border-border bg-panel shadow-sm p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-md font-semibold text-txt">{item.label}</h3>
        <span className="text-xs px-2 py-0.5 rounded-pill bg-panel-muted text-txt-soft font-mono">{item.format}</span>
      </div>
      <div className="flex items-center gap-2">
        {item.exists ? (
          <CheckCircle size={14} className="text-success flex-shrink-0" />
        ) : (
          <XCircle size={14} className="text-txt-faint flex-shrink-0" />
        )}
        <span className={`text-sm font-mono truncate ${item.exists ? "text-txt" : "text-txt-faint"}`}>
          {item.path}
        </span>
      </div>
      <p className="text-sm text-txt-soft">{item.description}</p>
      <div className="flex gap-2">
        <button onClick={handleCopy} className="h-8 px-3 rounded-sm border border-border text-xs text-txt-soft hover:bg-panel-muted flex items-center gap-1.5">
          <Copy size={14} /> 复制路径
        </button>
        <button className="h-8 px-3 rounded-sm border border-border text-xs text-txt-soft hover:bg-panel-muted flex items-center gap-1.5">
          <FolderOpen size={14} /> 打开目录
        </button>
      </div>
    </div>
  );
}
