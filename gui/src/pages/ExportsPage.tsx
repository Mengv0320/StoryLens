import { api } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { Card, Badge, EmptyState } from "../components/primitives";

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
                <p className="text-xs text-success truncate">{item.path.replace(/\\/g, '/').split('/').pop()}</p>
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
