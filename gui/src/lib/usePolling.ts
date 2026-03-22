import { useState, useEffect, useCallback, useRef } from "react";

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  enabled: boolean = true,
): { data: T | null; error: string | null; loading: boolean; refresh: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const fetcherRef = useRef(fetcher);
  const dataRef = useRef(data);
  const seqRef = useRef(0);
  fetcherRef.current = fetcher;
  dataRef.current = data;

  const doFetch = useCallback(async (signal?: AbortSignal) => {
    const seq = ++seqRef.current;
    if (dataRef.current === null) setLoading(true);
    try {
      const result = await fetcherRef.current();
      if (signal?.aborted || seq !== seqRef.current) return;
      setData(result);
      setError(null);
    } catch (err) {
      if (signal?.aborted || seq !== seqRef.current) return;
      setError(err instanceof Error ? err.message : "请求失败");
    } finally {
      if (seq === seqRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      // P1-3: 停止轮询但保留已有数据，不清除 data/error
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      if (abortRef.current) {
        abortRef.current.abort();
        abortRef.current = null;
      }
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;

    // P1-1: 递归 setTimeout，上一个请求完成后才调度下一次
    const poll = async () => {
      await doFetch(controller.signal);
      if (!controller.signal.aborted) {
        timeoutRef.current = setTimeout(poll, intervalMs);
      }
    };

    poll();

    // P1-2: unmount 时 clearTimeout + abort 进行中请求
    return () => {
      controller.abort();
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [enabled, intervalMs, doFetch]);

  const refresh = useCallback(() => {
    doFetch();
  }, [doFetch]);

  return { data, error, loading, refresh };
}
