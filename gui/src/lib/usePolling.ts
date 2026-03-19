import { useState, useEffect, useCallback, useRef } from "react";

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  enabled: boolean = true,
): { data: T | null; error: string | null; loading: boolean; refresh: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fetcherRef = useRef(fetcher);
  const dataRef = useRef(data);
  fetcherRef.current = fetcher;
  dataRef.current = data;

  const doFetch = useCallback(async () => {
    // Only show loading spinner on initial fetch (when no data yet)
    if (dataRef.current === null) setLoading(true);
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      intervalRef.current = null;
      return;
    }
    doFetch();
    intervalRef.current = setInterval(doFetch, intervalMs);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [enabled, intervalMs, doFetch]);

  return { data, error, loading, refresh: doFetch };
}
