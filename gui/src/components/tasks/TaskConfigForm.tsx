import { Card, SectionHeader } from "../primitives";

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm text-txt-soft">{label}</span>
      <span className="text-md text-txt">{value}</span>
    </div>
  );
}

export default function TaskConfigForm() {
  return (
    <Card>
      <SectionHeader title="任务配置" />
      <div className="grid grid-cols-2 gap-x-8 gap-y-4">
        <Field label="输入文件" value="-" />
        <Field label="输出目录" value="-" />
        <Field label="模型" value="-" />
        <Field label="分集策略" value="-" />
        <Field label="目标章节数/集" value="-" />
      </div>
    </Card>
  );
}
