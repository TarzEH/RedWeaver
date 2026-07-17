interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  compact?: boolean;
}

export function EmptyState({ icon, title, description, action, compact }: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center text-center ${compact ? "py-6" : "py-12"}`}>
      <div className={`${compact ? "mb-2" : "mb-3"} text-rw-dim`}>
        {icon}
      </div>
      <p className={`font-medium text-rw-muted ${compact ? "text-xs" : "text-sm"}`}>{title}</p>
      {description && (
        <p className={`text-rw-dim max-w-sm mt-1 ${compact ? "text-[10px]" : "text-xs"}`}>
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
