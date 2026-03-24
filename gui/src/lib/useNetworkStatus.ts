import { useSyncExternalStore } from "react";

let failCount = 0;
const listeners = new Set<() => void>();

function getSnapshot(): boolean {
  return failCount >= 2;
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => { listeners.delete(cb); };
}

function notify() {
  for (const cb of listeners) cb();
}

export function reportFetchResult(ok: boolean) {
  const prev = getSnapshot();
  if (ok) {
    failCount = 0;
  } else {
    failCount++;
  }
  if (prev !== getSnapshot()) notify();
}

export function useNetworkStatus(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot);
}
