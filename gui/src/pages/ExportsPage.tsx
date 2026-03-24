import { useState } from "react";
import { api, getAuthHeaders } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { Card, Badge, EmptyState, toast } from "../components/primitives";
import { Copy, Check, Download } from "lucide-react";

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

function DownloadButton({ fileId, filename }: { fileId: string; filename: string }) {
  const [loading, setLoading] = useState(false);

  const handleDownload = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/results/exports/${encodeURIComponent(fileId)}/download`, {
        headers: { ...getAuthHeaders() },
      });
      if (!res.ok) {
        toast("下载失败", "error");
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      toast("下载完成", "success");
    } catch {
      toast("下载失败", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleDownload}
      disabled={loading}
      className="flex items-center gap-1 rounded px-2 py-1 text-xs text-txt-soft hover:text-accent hover:bg-panel-soft disabled:opacity-50 transition-colors"
      title="下载文件"
    >
      <Download size={12} />
      {loading ? "下载中..." : "下载"}
    </button>
  );
}

export default function ExportsPage() {
  const { data: exports } = usePolling(() => api.getExports(), 15_000);

  return (
    <div className="p-4 md:p-6 space-y-5">
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
                  <div className="flex items-center gap-1">
                    <DownloadButton fileId={item.id} filename={item.path.replace(/\\/g, '/').split('/').pop() ?? item.id} />
                    <CopyButton text={item.path} />
                  </div>
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
