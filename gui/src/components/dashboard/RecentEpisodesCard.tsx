import type { EpisodeListItem } from "../../lib/types";
import { Card, SectionHeader, Badge } from "../primitives";

const statusVariant: Record<EpisodeListItem["status"], "success" | "danger" | "warning"> = {
  completed: "success",
  failed: "danger",
  warning: "warning",
};

type Props = { episodes: EpisodeListItem[] };

export default function RecentEpisodesCard({ episodes }: Props) {
  return (
    <Card>
      <SectionHeader title="最近分集" />
      {episodes.length === 0 ? (
        <p className="text-sm text-txt-faint">暂无分集数据</p>
      ) : (
        <ul className="space-y-3">
          {episodes.map((ep) => (
            <li key={ep.id} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span className="text-txt-soft font-mono">{ep.indexLabel}</span>
                <span className="text-txt">{ep.title}</span>
                <span className="text-txt-faint">{ep.chapterRangeLabel}</span>
              </div>
              <Badge label={ep.status} variant={statusVariant[ep.status]} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
