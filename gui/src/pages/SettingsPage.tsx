import { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { Card, SectionHeader, KeyValue, Badge } from "../components/primitives";
import { Save, Eye, EyeOff, RotateCcw, ChevronDown } from "lucide-react";

type ApiType = "openai" | "anthropic";

export default function SettingsPage() {
  const fetcher = useCallback(() => api.getSettings(), []);
  const { data: settings } = usePolling(fetcher, 30_000);

  // Editable fields
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiType, setApiType] = useState<ApiType>("openai");
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [genreModel, setGenreModel] = useState("");
  const [extractModel, setExtractModel] = useState("");
  const [analysisModel, setAnalysisModel] = useState("");
  const [summaryModel, setSummaryModel] = useState("");

  // Load settings into form once
  useEffect(() => {
    if (settings && !loaded) {
      setApiKey(String(settings.apiKey ?? ""));
      setBaseUrl(String(settings.baseUrl ?? ""));
      setModel(String(settings.model ?? ""));
      setApiType((settings.apiType as ApiType) ?? "openai");
      setGenreModel(String(settings.genreModel ?? ""));
      setExtractModel(String(settings.extractModel ?? ""));
      setAnalysisModel(String(settings.analysisModel ?? ""));
      setSummaryModel(String(settings.summaryModel ?? ""));
      setLoaded(true);
    }
  }, [settings, loaded]);

  const handleSave = async () => {
    setSaving(true);
    setMsg(null);
    try {
      // Don't send masked key back — only send if user edited it
      const payload: Record<string, string> = { baseUrl, model, apiType };
      if (apiKey && !apiKey.includes("****")) {
        payload.apiKey = apiKey;
      }
      if (genreModel) payload.genreModel = genreModel;
      if (extractModel) payload.extractModel = extractModel;
      if (analysisModel) payload.analysisModel = analysisModel;
      if (summaryModel) payload.summaryModel = summaryModel;
      await api.updateSettings(payload);
      setMsg({ type: "ok", text: "配置已保存，下次运行管线时生效" });
    } catch (e: any) {
      setMsg({ type: "err", text: e.message || "保存失败" });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setLoaded(false);
  };


  const chaptersPerEpisode = settings?.chaptersPerEpisode ?? 10;
  const splitStrategy = settings?.splitStrategy ?? "dynamic";
  const useCache = settings?.useCache ?? true;
  const skipQuality = settings?.skipQuality ?? false;
  const outputDir = settings?.outputDir ?? "./output";
  const lastRunId = settings?.lastRunId ?? "—";
  const lastRunStatus = settings?.lastRunStatus ?? "—";

  return (
    <div className="p-4 md:p-6 space-y-5">
      <h1 className="text-2xl font-semibold text-txt">设置</h1>

      {/* API Configuration Card */}
      <Card>
        <SectionHeader
          title="API 配置"
          extra={
            <div className="flex items-center gap-2">
              <Badge
                label={apiKey ? "已配置" : "未配置"}
                variant={apiKey ? "success" : "danger"}
              />
            </div>
          }
        />
        <div className="space-y-4 mt-2">
          {/* API Type */}
          <div>
            <label className="block text-sm text-txt-soft mb-1">提供商类型</label>
            <div className="flex gap-2">
              {(["openai", "anthropic"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setApiType(t)}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    apiType === t
                      ? "bg-accent text-white"
                      : "bg-panel-muted text-txt-soft hover:bg-panel-soft"
                  }`}
                >
                  {t === "openai" ? "OpenAI 兼容" : "Anthropic"}
                </button>
              ))}
            </div>
            <p className="text-xs text-txt-faint mt-1">
              SiliconFlow、DeepSeek、OpenRouter 等第三方 API 选择 "OpenAI 兼容"
            </p>
          </div>

          {/* Base URL */}
          <div>
            <label className="block text-sm text-txt-soft mb-1">Base URL</label>
            <input
              type="url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.siliconflow.cn/v1"
              className="w-full rounded-md border border-border bg-panel px-3 py-2 text-sm text-txt placeholder:text-txt-faint focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
          </div>

          {/* Model */}
          <div>
            <label className="block text-sm text-txt-soft mb-1">模型名称</label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="Pro/zai-org/GLM-4.7"
              className="w-full rounded-md border border-border bg-panel px-3 py-2 text-sm text-txt placeholder:text-txt-faint focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
          </div>

          {/* API Key */}
          <div>
            <label className="block text-sm text-txt-soft mb-1">API Key</label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type={showKey ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="w-full rounded-md border border-border bg-panel px-3 py-2 pr-10 text-sm text-txt placeholder:text-txt-faint focus:outline-none focus:ring-2 focus:ring-accent/40 font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-txt-soft hover:text-txt"
                >
                  {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-3 pt-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 rounded-md bg-accent text-white text-sm font-medium shadow-sm hover:bg-accent/90 disabled:opacity-50 transition-colors"
            >
              <Save size={14} />
              {saving ? "保存中..." : "保存配置"}
            </button>
            <button
              type="button"
              onClick={handleReset}
              className="flex items-center gap-2 px-4 py-2 rounded-md border border-border bg-panel text-txt-soft text-sm hover:bg-panel-soft transition-colors"
            >
              <RotateCcw size={14} />
              重新加载
            </button>
          </div>

          {/* Status message */}
          {msg && (
            <div
              className={`text-sm px-3 py-2 rounded-md ${
                msg.type === "ok"
                  ? "bg-success/10 text-success border border-success/20"
                  : "bg-danger-soft/30 text-danger border border-danger/20"
              }`}
            >
              {msg.text}
            </div>
          )}
        </div>
      </Card>

      {/* Advanced Model Config */}
      <Card>
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="w-full flex items-center justify-between py-1"
        >
          <span className="text-sm font-semibold text-txt">高级模型配置</span>
          <ChevronDown size={16} className={`text-txt-soft transition-transform duration-200 ${showAdvanced ? "rotate-180" : ""}`} />
        </button>
        {showAdvanced && (
          <div className="mt-3 space-y-4">
            <p className="text-xs text-txt-faint">留空则使用上方全局模型。可按阶段指定不同模型以优化成本或质量。</p>
            {([
              { label: "类型识别模型", value: genreModel, set: setGenreModel, placeholder: "用于判断小说类型/题材" },
              { label: "信息提取模型", value: extractModel, set: setExtractModel, placeholder: "用于逐章提取关键事件" },
              { label: "分析模型", value: analysisModel, set: setAnalysisModel, placeholder: "用于角色关系与因果分析" },
              { label: "总结模型", value: summaryModel, set: setSummaryModel, placeholder: "用于生成摘要与阅读指南" },
            ] as const).map((field) => (
              <label key={field.label} className="flex flex-col gap-1.5">
                <span className="text-sm text-txt-soft">{field.label}</span>
                <input
                  type="text"
                  value={field.value}
                  onChange={(e) => field.set(e.target.value)}
                  placeholder={field.placeholder}
                  className="w-full rounded-md border border-border bg-panel px-3 py-2 text-sm text-txt placeholder:text-txt-faint focus:outline-none focus:ring-2 focus:ring-accent/40"
                />
              </label>
            ))}
          </div>
        )}
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
