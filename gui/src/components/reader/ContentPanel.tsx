import { useEffect, type RefObject } from "react";

type Highlight = {
  offset: number;
  length: number;
  eventId: string;
};

type Props = {
  title: string;
  content: string;
  highlights: Highlight[];
  activeEventId: string | null;
  contentRef: RefObject<HTMLDivElement | null>;
};

export default function ContentPanel({ title, content, highlights, activeEventId, contentRef }: Props) {
  // Scroll to active anchor when it changes
  useEffect(() => {
    if (!activeEventId) return;
    const el = document.getElementById(`anchor-${activeEventId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [activeEventId]);

  // Build segments by splitting text at highlight boundaries
  const segments = buildSegments(content, highlights, activeEventId);

  return (
    <div className="flex-1 overflow-y-auto border-r border-border" ref={contentRef}>
      <div className="p-5">
        <h2 className="text-lg font-semibold text-txt mb-4">{title}</h2>
        <div className="text-sm text-txt-soft leading-relaxed whitespace-pre-wrap">
          {segments.map((seg, i) =>
            seg.eventId ? (
              <mark
                key={i}
                id={`anchor-${seg.eventId}`}
                data-event-id={seg.eventId}
                className={`rounded px-0.5 ${
                  seg.eventId === activeEventId ? "bg-warning/40" : "bg-warning/20"
                }`}
              >
                {seg.text}
              </mark>
            ) : (
              <span key={i}>{seg.text}</span>
            )
          )}
        </div>
      </div>
    </div>
  );
}

type Segment = { text: string; eventId: string | null };

function buildSegments(
  content: string,
  highlights: Highlight[],
  _activeEventId: string | null
): Segment[] {
  if (highlights.length === 0) return [{ text: content, eventId: null }];

  // Sort highlights by offset
  const sorted = [...highlights].sort((a, b) => a.offset - b.offset);
  const result: Segment[] = [];
  let cursor = 0;

  for (const hl of sorted) {
    const start = Math.min(hl.offset, content.length);
    const end = Math.min(hl.offset + hl.length, content.length);

    if (start < cursor) continue; // overlapping, skip

    if (cursor < start) {
      result.push({ text: content.slice(cursor, start), eventId: null });
    }
    if (start < end) {
      result.push({ text: content.slice(start, end), eventId: hl.eventId });
    }
    cursor = end;
  }

  if (cursor < content.length) {
    result.push({ text: content.slice(cursor), eventId: null });
  }

  return result;
}
