import { useState, useMemo, useCallback } from "react";

export function useShowMore<T>(items: T[], pageSize = 30) {
  const [page, setPage] = useState(1);

  const visible = useMemo(() => items.slice(0, page * pageSize), [items, page, pageSize]);
  const hasMore = visible.length < items.length;
  const total = items.length;

  const showMore = useCallback(() => setPage((p) => p + 1), []);
  const reset = useCallback(() => setPage(1), []);

  return { visible, hasMore, showMore, reset, total };
}
