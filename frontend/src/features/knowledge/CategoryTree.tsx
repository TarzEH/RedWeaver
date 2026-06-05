import { useState } from "react";
import { ChevronRight, FileText, Folder, FolderOpen } from "lucide-react";
import { cn } from "../../lib/cn";
import { Spinner } from "../../components/ui/Spinner";
import { api, type KbFile } from "../../services/api";
import { categoryLabel } from "./kbUtils";

export interface CategoryNode {
  category: string;
  chunks: number;
  files: number;
}

interface CategoryTreeProps {
  categories: CategoryNode[];
  loading: boolean;
  selectedFile: string | null;
  onSelectFile: (file: KbFile) => void;
}

/** Left pane: collapsible category → files tree. Files are lazy-loaded on expand. */
export function CategoryTree({ categories, loading, selectedFile, onSelectFile }: CategoryTreeProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Spinner size="sm" label="Loading categories" />
      </div>
    );
  }

  if (categories.length === 0) {
    return (
      <p className="px-3 py-6 text-center text-xs text-rw-dim">No categories indexed.</p>
    );
  }

  return (
    <nav className="space-y-0.5">
      {categories.map((cat) => (
        <CategoryBranch
          key={cat.category}
          node={cat}
          selectedFile={selectedFile}
          onSelectFile={onSelectFile}
        />
      ))}
    </nav>
  );
}

function CategoryBranch({
  node,
  selectedFile,
  onSelectFile,
}: {
  node: CategoryNode;
  selectedFile: string | null;
  onSelectFile: (file: KbFile) => void;
}) {
  const [open, setOpen] = useState(false);
  const [files, setFiles] = useState<KbFile[] | null>(null);
  const [loading, setLoading] = useState(false);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && files === null && !loading) {
      setLoading(true);
      try {
        const data = await api.knowledge.files(node.category);
        setFiles(data.files || []);
      } catch {
        setFiles([]);
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <div>
      <button
        type="button"
        onClick={toggle}
        className={cn(
          "group flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm",
          "text-rw-muted transition-colors hover:bg-rw-surface hover:text-rw-text",
        )}
      >
        <ChevronRight
          size={14}
          className={cn(
            "shrink-0 text-rw-dim transition-transform duration-150",
            open && "rotate-90",
          )}
        />
        {open ? (
          <FolderOpen size={15} className="shrink-0 text-rw-accent" />
        ) : (
          <Folder size={15} className="shrink-0 text-rw-dim" />
        )}
        <span className="flex-1 truncate font-medium">{categoryLabel(node.category)}</span>
        <span className="shrink-0 rounded-full bg-rw-surface px-1.5 py-0.5 font-mono text-[10px] text-rw-dim group-hover:bg-rw-elevated">
          {node.files}
        </span>
      </button>

      {open && (
        <div className="ml-3 border-l border-rw-border-subtle pl-2">
          {loading && (
            <div className="px-2 py-2">
              <Spinner size="xs" />
            </div>
          )}
          {!loading && files && files.length === 0 && (
            <p className="px-2 py-2 text-[11px] text-rw-dim">No files.</p>
          )}
          {!loading &&
            files?.map((f) => {
              const active = selectedFile === f.file;
              return (
                <button
                  key={f.file}
                  type="button"
                  onClick={() => onSelectFile(f)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors",
                    active
                      ? "bg-rw-accent/15 text-rw-accent"
                      : "text-rw-dim hover:bg-rw-surface hover:text-rw-text",
                  )}
                >
                  <FileText size={13} className="shrink-0" />
                  <span className="truncate">{f.title || f.file}</span>
                </button>
              );
            })}
        </div>
      )}
    </div>
  );
}
