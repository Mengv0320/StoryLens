import { usePolling } from "./usePolling";
import { api } from "./api";
import type { PipelineStatusResponse } from "./api";
import { useCallback } from "react";

/** Returns the current pipeline mode ("fast_scan" | "deep_analysis" | undefined). */
export function useRunMode() {
  const { data } = usePolling<PipelineStatusResponse>(
    useCallback(() => api.getPipelineStatus(), []),
    30_000,
  );
  return data?.mode as "fast_scan" | "deep_analysis" | "standard_analysis" | undefined;
}
