import { api } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { Card, SectionHeader, KeyValue } from "../components/primitives";

export default function SettingsPage() {
  const { data: settings } = usePolling(() => api.getSettings(), 30_000);

  const model = settings?.model ?? "gpt-4o";
  const baseUrl = settings?.baseUrl ?? "https://api.openai.com/v1";
  const apiKeyStatus = settings?.apiKeyStatus ?? "已配置";
  const chaptersPerEpisode = settings?.chaptersPerEpisode ?? 10;
  const splitStrategy = settings?.splitStrategy ?? "dynamic";
  const useCache = settings?.useCache ?? true;
  const skipQuality = settings?.skipQuality ?? false;
  const outputDir = settings?.outputDir ?? "./output";
  const lastRunId = settings?.lastRunId ?? "—";
  const lastRunStatus = settings?.lastRunStatus ?? "—";

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">设置</h1>

      <Card>
        <SectionHeader title="模型配置" />
        <div className="space-y-0.5">
          <KeyValue label="默认模型" value={String(model)} />
          <KeyValue label="Base URL" value={String(baseUrl)} />
          <KeyValue label="API Key 状态" value={<span className="text-success">{String(apiKeyStatus)}</span>} />
        </div>
      </Card>

      <Card>
        <SectionHeader title="运行设置" />
        <div className="space-y-0.5">
          <KeyValue label="每集目标章节数" value={String(chaptersPerEpisode)} />
          <KeyValue label="分集策略" value={String(splitStrategy)} />
          <KeyValue label="缓存" value={useCache ? "启用" : "禁用"} />
          <KeyValue label="跳过质量检查" value={skipQuality ? "是" : "否"} />
        </div>
      </Card>

      <Card>
        <SectionHeader title="输出设置" />
        <div className="space-y-0.5">
          <KeyValue label="输出目录" value={String(outputDir)} />
          <KeyValue label="最近运行 ID" value={String(lastRunId)} />
          <KeyValue label="最近运行状态" value={String(lastRunStatus)} />
        </div>
      </Card>
    </div>
  );
}
