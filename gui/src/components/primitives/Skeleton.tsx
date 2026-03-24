export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse bg-panel-muted rounded ${className}`} />;
}

export function SkeletonCard({ className = "" }: { className?: string }) {
  return <Skeleton className={`h-32 rounded-md ${className}`} />;
}

export function SkeletonLine({ className = "" }: { className?: string }) {
  return <Skeleton className={`h-4 w-full ${className}`} />;
}
