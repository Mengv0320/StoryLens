import { Card, SectionHeader, KeyValue } from "../primitives";

export default function RuntimeMetrics() {
  return (
    <Card>
      <SectionHeader title="运行指标" />
      <div className="space-y-0.5">
        <KeyValue label="已完成章节" value="-" />
        <KeyValue label="分集数" value="-" />
        <KeyValue label="失败数" value="-" />
        <KeyValue label="缓存命中" value="-" />
        <KeyValue label="Token 用量" value="-" />
        <KeyValue label="平均耗时" value="-" />
      </div>
    </Card>
  );
}
