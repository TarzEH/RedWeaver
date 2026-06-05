import { useEffect, useRef, useState } from "react";
import { Search, Sparkles, FileText, Loader2, MessageSquareQuote } from "lucide-react";
import { cn } from "../../lib/cn";
import { Input } from "../../components/ui/Input";
import { Badge } from "../../components/ui/Badge";
import { EmptyState } from "../../components/ui/EmptyState";
import { MarkdownRenderer } from "../../components/domain/MarkdownRenderer";
import { api, type KbResult } from "../../services/api";
import { categoryLabel, fileBaseName } from "./kbUtils";

type Mode = "search" | "ask";

interface SearchPanelProps {
  /** Open a KB file (by its `file` key) in the center pane. */
  onOpenFile: (file: string) => void;
}

interface AskState {
  answer: string;
  sources: string[];
  question: string;
}

/** Right pane: search-as-you-type query + an Ask (grounded Q&A) toggle. */
export function SearchPanel({ onOpenFile }: SearchPanelProps) {
  const [mode, setMode] = useState<Mode>("search");
  const [query, setQuery] = useState("");

  // Search-as-you-type state
  const [results, setResults] = useState<KbResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);

  // Ask state
  const [ask, setAsk] = useState<AskState | null>(null);
  const [asking, setAsking] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reqIdRef = useRef(0);

  // Debounced search-as-you-type (only in search mode).
  useEffect(() => {
    if (mode !== "search") return;
    const term = query.trim();
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!term) {
      setResults([]);
      setSearched(false);
      setSearching(false);
      return;
    }

    setSearching(true);
    debounceRef.current = setTimeout(async () => {
      const reqId = ++reqIdRef.current;
      try {
        const data = await api.knowledge.query({ query: term, top_k: 8 });
        if (reqId === reqIdRef.current) setResults(data.results || []);
      } catch {
        if (reqId === reqIdRef.current) setResults([]);
      } finally {
        if (reqId === reqIdRef.current) {
          setSearching(false);
          setSearched(true);
        }
      }
    }, 350);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, mode]);

  const runAsk = async () => {
    const q = query.trim();
    if (!q || asking) return;
    setAsking(true);
    setAsk(null);
    try {
      const data = await api.knowledge.ask(q);
      setAsk({ answer: data.answer, sources: data.sources || [], question: data.question });
    } catch {
      setAsk({ answer: "_Sorry — the knowledge service could not answer that question right now._", sources: [], question: q });
    } finally {
      setAsking(false);
    }
  };

  const switchMode = (next: Mode) => {
    if (next === mode) return;
    setMode(next);
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === "ask") void runAsk();
  };

  return (
    <div className="flex h-full flex-col">
      {/* Mode toggle */}
      <div className="mb-3 flex gap-1 rounded-lg border border-rw-border bg-rw-elevated p-1">
        <ToggleButton active={mode === "search"} onClick={() => switchMode("search")} icon={<Search size={13} />}>
          Search
        </ToggleButton>
        <ToggleButton active={mode === "ask"} onClick={() => switchMode("ask")} icon={<Sparkles size={13} />}>
          Ask
        </ToggleButton>
      </div>

      {/* Query input */}
      <form onSubmit={onSubmit} className="mb-3">
        <Input
          icon={mode === "search" ? <Search size={14} /> : <Sparkles size={14} />}
          placeholder={
            mode === "search"
              ? "Search techniques, commands…"
              : "Ask a question about the KB…"
          }
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoComplete="off"
        />
        {mode === "ask" && (
          <p className="mt-1.5 text-[10px] text-rw-dim">
            Press Enter to get a grounded answer with cited sources.
          </p>
        )}
      </form>

      {/* Results / answer */}
      <div className="-mr-1 flex-1 overflow-y-auto pr-1">
        {mode === "search" ? (
          <SearchResults
            query={query}
            searching={searching}
            searched={searched}
            results={results}
            onOpenFile={onOpenFile}
          />
        ) : (
          <AskResult ask={ask} asking={asking} hasQuery={!!query.trim()} onOpenFile={onOpenFile} />
        )}
      </div>
    </div>
  );
}

function ToggleButton({
  active,
  onClick,
  icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
        active ? "bg-rw-accent text-white shadow-sm" : "text-rw-dim hover:bg-rw-surface hover:text-rw-text",
      )}
    >
      {icon}
      {children}
    </button>
  );
}

function SearchResults({
  query,
  searching,
  searched,
  results,
  onOpenFile,
}: {
  query: string;
  searching: boolean;
  searched: boolean;
  results: KbResult[];
  onOpenFile: (file: string) => void;
}) {
  if (!query.trim()) {
    return (
      <EmptyState
        compact
        icon={<Search size={26} />}
        title="Search the knowledge base"
        description="Results appear as you type."
      />
    );
  }

  if (searching && results.length === 0) {
    return (
      <div className="flex items-center gap-2 px-1 py-4 text-xs text-rw-dim">
        <Loader2 size={14} className="animate-spin" />
        Searching…
      </div>
    );
  }

  if (searched && results.length === 0) {
    return (
      <EmptyState compact icon={<Search size={26} />} title="No matches" description="Try different keywords." />
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between px-0.5">
        <p className="text-[10px] uppercase tracking-wide text-rw-dim">
          {results.length} result{results.length === 1 ? "" : "s"}
        </p>
        {searching && <Loader2 size={12} className="animate-spin text-rw-dim" />}
      </div>
      {results.map((r, i) => (
        <button
          key={`${r.file}-${i}`}
          type="button"
          onClick={() => onOpenFile(r.file)}
          className="block w-full rounded-lg border border-rw-border bg-rw-elevated p-3 text-left transition-colors hover:border-rw-accent/40 hover:bg-rw-surface"
        >
          <div className="mb-1.5 flex items-center gap-2">
            <Badge variant="accent">{categoryLabel(r.category)}</Badge>
            <span className="ml-auto shrink-0 font-mono text-[10px] text-rw-accent">
              {(r.relevance_score * 100).toFixed(0)}% match
            </span>
          </div>
          <p className="mb-1 truncate font-mono text-[11px] text-rw-muted">{fileBaseName(r.file)}</p>
          <p className="line-clamp-3 text-[11px] leading-relaxed text-rw-dim">{r.content}</p>
        </button>
      ))}
    </div>
  );
}

function AskResult({
  ask,
  asking,
  hasQuery,
  onOpenFile,
}: {
  ask: AskState | null;
  asking: boolean;
  hasQuery: boolean;
  onOpenFile: (file: string) => void;
}) {
  if (asking) {
    return (
      <div className="flex items-center gap-2 px-1 py-4 text-xs text-rw-dim">
        <Loader2 size={14} className="animate-spin" />
        Thinking…
      </div>
    );
  }

  if (!ask) {
    return (
      <EmptyState
        compact
        icon={<MessageSquareQuote size={26} />}
        title="Ask your knowledge base"
        description={hasQuery ? "Press Enter to get an answer." : "Type a question and press Enter."}
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-rw-border bg-rw-elevated p-3">
        <MarkdownRenderer content={ask.answer} variant="enhanced" />
      </div>
      {ask.sources.length > 0 && (
        <div>
          <p className="mb-1.5 text-[10px] uppercase tracking-wide text-rw-dim">Sources</p>
          <div className="flex flex-wrap gap-1.5">
            {ask.sources.map((src) => (
              <button
                key={src}
                type="button"
                onClick={() => onOpenFile(src)}
                className="inline-flex items-center gap-1.5 rounded-full border border-rw-border bg-rw-surface px-2.5 py-1 text-[11px] text-rw-muted transition-colors hover:border-rw-accent/40 hover:text-rw-accent"
              >
                <FileText size={11} />
                {fileBaseName(src)}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
