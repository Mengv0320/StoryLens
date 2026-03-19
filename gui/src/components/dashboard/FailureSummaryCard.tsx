import { AlertTriangle } from "lucide-react";
import type { FailureItem } from "../../lib/types";
import { Card, SectionHeader, Badge } from "../primitives";

type Props = { failures: FailureItem[] };

export default function FailureSummaryCard({ failures }: Props) {
  return (
    <Card>
      <SectionHeader
        title="失败与警告"
        extra={
          failures.length > 0 ? (
            <Badge label={`${failures.length} 项`} variant="danger" />
          ) : undefined
        }
      />
      {failures.length === 0 ? (
        <p className="text-sm text-txt-faint">无失败记录</p>
      ) : (
        <ul className="space-y-3">
          {failures.map((f) => (
            <li key={f.id} className="flex items-start gap-3 text-sm">
              <AlertTriangle size={16} className="mt-0.5 shrink-0 text-danger" />
              <div>
                <p className="text-txt font-medium">
                  <span className="text-danger">[{f.errorType}]</span>{" "}
                  {f.title ?? f.id}
                </p>
                <p className="text-txt-soft">{f.error}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
