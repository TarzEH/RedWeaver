import { useEffect, useState, type ReactNode } from "react";
import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Crosshair,
  FolderOpen,
  BookOpen,
  Settings,
  Plus,
  Bug,
} from "lucide-react";
import { api } from "../../services/api";
import type { RunSummary } from "../../types/api";

function Item({
  children,
  onSelect,
  icon: Icon,
  value,
}: {
  children: ReactNode;
  onSelect: () => void;
  icon: typeof Crosshair;
  value?: string;
}) {
  return (
    <Command.Item
      value={value}
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-rw-text data-[selected=true]:bg-rw-surface"
    >
      <Icon size={15} className="text-rw-dim" />
      {children}
    </Command.Item>
  );
}

/** Global Cmd/Ctrl-K command palette: jump to pages, start a hunt, open runs. */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  useEffect(() => {
    if (open) api.runs.list().then(setRuns).catch(() => {});
  }, [open]);

  const go = (path: string) => {
    setOpen(false);
    navigate(path);
  };

  if (!open) return null;

  return (
    <div
      className="animate-fade-in fixed inset-0 z-[300] flex items-start justify-center bg-black/60 pt-[15vh] backdrop-blur-sm"
      onClick={() => setOpen(false)}
    >
      <Command
        label="Command Menu"
        className="animate-scale-in w-full max-w-xl overflow-hidden rounded-xl border border-rw-border bg-rw-elevated shadow-2xl [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-rw-dim"
        onClick={(e) => e.stopPropagation()}
      >
        <Command.Input
          autoFocus
          placeholder="Search or jump to…"
          className="w-full border-b border-rw-border bg-transparent px-4 py-3.5 text-sm text-rw-text outline-none placeholder:text-rw-dim"
        />
        <Command.List className="max-h-80 overflow-y-auto p-2">
          <Command.Empty className="px-3 py-6 text-center text-sm text-rw-dim">
            No results.
          </Command.Empty>
          <Command.Group heading="Navigate">
            <Item onSelect={() => go("/dashboard")} icon={LayoutDashboard}>Dashboard</Item>
            <Item onSelect={() => go("/hunt")} icon={Crosshair}>Hunt</Item>
            <Item onSelect={() => go("/sessions")} icon={FolderOpen}>Sessions &amp; Targets</Item>
            <Item onSelect={() => go("/knowledge")} icon={BookOpen}>Knowledge Base</Item>
            <Item onSelect={() => go("/settings")} icon={Settings}>Settings</Item>
          </Command.Group>
          <Command.Group heading="Actions">
            <Item value="new hunt scan" onSelect={() => go("/hunt")} icon={Plus}>New Hunt</Item>
          </Command.Group>
          {runs.length > 0 && (
            <Command.Group heading="Recent runs">
              {runs.slice(0, 8).map((r) => (
                <Item
                  key={r.run_id}
                  value={`run ${r.target} ${r.run_id}`}
                  onSelect={() => go(`/hunt/${r.run_id}`)}
                  icon={Bug}
                >
                  <span className="truncate">{r.target}</span>
                  <span className="ml-auto font-mono text-xs text-rw-dim">
                    {r.run_id.slice(0, 8)}
                  </span>
                </Item>
              ))}
            </Command.Group>
          )}
        </Command.List>
      </Command>
    </div>
  );
}
