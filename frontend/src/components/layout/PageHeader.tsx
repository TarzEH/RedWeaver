interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-6">
      <div>
        {/*
          tabIndex={-1} makes the heading programmatically focusable without
          putting it in the tab order. On every route change the shell's
          RouteAnnouncer moves focus here, which is what tells a screen-reader
          user the screen changed — React Router, unlike a real page load, does
          not reset focus on its own. The outline only appears for keyboard
          users, since :focus-visible does not match programmatic focus that
          follows a pointer interaction.
        */}
        <h1 tabIndex={-1} className="text-xl font-semibold text-rw-text">
          {title}
        </h1>
        {subtitle && <p className="text-xs text-rw-dim mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
