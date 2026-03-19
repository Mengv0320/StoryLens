import { Link } from "react-router-dom";
import { Card } from "./primitives";

/** Shown on deep_analysis-only pages when current mode is fast_scan. */
export default function FastScanNotice() {
  return (
    <Card>
      <div className="py-6 text-center space-y-3">
        <p className="text-txt-soft text-sm">
          当前为快速扫书模式，此页面仅在深度分析模式下可用。
        </p>
        <p className="text-txt-soft text-sm">快速扫书结果请查看：</p>
        <div className="flex justify-center gap-3">
          <Link to="/overview" className="text-sm px-3 py-1.5 rounded bg-accent text-white hover:bg-accent/80">总览</Link>
          <Link to="/segments" className="text-sm px-3 py-1.5 rounded bg-accent text-white hover:bg-accent/80">分段</Link>
          <Link to="/key-chapters" className="text-sm px-3 py-1.5 rounded bg-accent text-white hover:bg-accent/80">关键章节</Link>
        </div>
      </div>
    </Card>
  );
}
