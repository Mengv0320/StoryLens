import { Card } from "../primitives";

export default function TaskActions() {
  return (
    <Card>
      <div className="flex gap-3">
        <button className="h-10 rounded-sm px-4 text-md font-medium bg-accent text-white">
          开始处理
        </button>
        <button className="h-10 rounded-sm px-4 text-md font-medium border border-accent text-accent">
          继续运行
        </button>
        <button className="h-10 rounded-sm px-4 text-md font-medium bg-danger-soft text-danger">
          停止任务
        </button>
      </div>
    </Card>
  );
}
