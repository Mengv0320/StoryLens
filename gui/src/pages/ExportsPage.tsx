import { useState } from "react";
import { api } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { Card, Badge, EmptyState, toast } from "../components/primitives";
import { Copy, Check } from "lucide-react";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast("路径已复制", "success");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast("复制失败", "error");
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="flex items-center gap-1 rounded px-2 py-1 text-xs text-txt-soft hover:text-accent hover:bg-panel-soft transition-colors"
      title="复制路径"
    >
      {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
      {copied ? "已复制" : "复制路径"}
    </button>
  );
}

export default function ExportsPage() {
  const { data: exports } = usePolling(() => api.getExports(), 15_000);

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">导出</h1>
      {!exports?.length ? (
        <Card><EmptyState message="暂无导出文件。运行管线后将在此显示产出文件。" /></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {exports.map(item => (
            <Card key={item.id}>
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-txt">{item.label}</span>
                <Badge label={item.format} variant={item.exists ? "success" : "default"} />
              </div>
              <p className="text-sm text-txt-soft mb-2">{item.description}</p>
              {item.exists ? (
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs text-success truncate flex-1">{item.path.replace(/\\/g, '/').split('/').pop()}</p>
                  <CopyButton text={item.path} />
                </div>
              ) : (
                <p className="text-xs text-txt-soft">文件尚未生成</p>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
