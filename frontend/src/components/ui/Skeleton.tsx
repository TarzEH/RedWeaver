import { cn } from "../../lib/cn";

interface SkeletonProps {
  /** Extra classes — set width/height/shape here (e.g. "h-4 w-32 rounded"). */
  className?: string;
}

/**
 * Shimmer placeholder for loading content. Uses the rw-surface base with an
 * animated highlight sweep (see `.rw-skeleton` in index.css). Compose size and
 * shape via `className`; respects prefers-reduced-motion.
 */
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      aria-hidden
      className={cn("rw-skeleton rounded-md", className)}
    />
  );
}
