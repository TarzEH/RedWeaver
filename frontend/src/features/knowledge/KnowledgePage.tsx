import { useEffect, useState } from "react";
import { BookOpen, Search } from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Input, Select } from "../../components/ui/Input";
import { EmptyState } from "../../components/ui/EmptyState";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge } from "../../components/ui/Badge";
import { api } from "../../services/api";

const CATEGORIES = [
  { value: "", label: "All categories" },
  { value: "privilege_escalation", label: "Privilege Escalation" },
  { value: "tunneling", label: "Tunneling" },
  { value: "flag_hunting", label: "Flag Hunting" },
  { value: "web_attacks", label: "Web Attacks" },
  { value: "active_directory", label: "Active Directory" },
  { value: "reconnaissance", label: "Reconnaissance" },
  { value: "exploitation", label: "Exploitation" },
  { value: "password_attacks", label: "Password Attacks" },
  { value: "reporting", label: "Reporting" },
  { value: "c2_frameworks", label: "C2 Frameworks" },
  { value: "av_evasion", label: "AV Evasion" },
  { value: "cloud_security", label: "Cloud Security" },
];

type KnowledgeResult = {
  content: string;
  file: string;
  category: string;
  relevance_score: number;
};

export function KnowledgePage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [results, setResults] = useState<KnowledgeResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<{ status: string; documents_indexed: number; files_indexed: number } | null>(null);

  useEffect(() => {
    api.knowledge.health().then(setHealth).catch(() => {});
  }, []);

  const search = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    try {
      const body: { query: string; top_k: number; category?: string } = { query: query.trim(), top_k: 10 };
      if (category) body.category = category;
      const data = await api.knowledge.query(body);
      setResults(data.results || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 animate-fade-in">
      <PageHeader
        title="Knowledge Base"
        subtitle={
          health && health.status !== "unavailable"
            ? `${health.documents_indexed} chunks from ${health.files_indexed} files indexed`
            : undefined
        }
        actions={
          health?.status === "unavailable" ? (
            <Badge variant="danger">Service unavailable</Badge>
          ) : undefined
        }
      />

      {/* Search */}
      <form onSubmit={search} className="flex gap-2 mb-6">
        <Input
          icon={<Search size={14} />}
          placeholder="Search techniques, commands, methodologies..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1"
        />
        <Select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          options={CATEGORIES}
        />
        <Button type="submit" loading={loading}>
          Search
        </Button>
      </form>

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs text-rw-dim">{results.length} results</p>
          {results.map((r, i) => (
            <Card key={i}>
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="accent">{r.category}</Badge>
                <span className="text-[10px] text-rw-dim font-mono">{r.file}</span>
                <span className="text-[10px] text-rw-dim ml-auto">
                  {(r.relevance_score * 100).toFixed(0)}% match
                </span>
              </div>
              <pre className="text-xs text-rw-muted whitespace-pre-wrap font-mono leading-relaxed max-h-40 overflow-y-auto">
                {r.content}
              </pre>
            </Card>
          ))}
        </div>
      )}

      {results.length === 0 && query && !loading && (
        <EmptyState
          icon={<BookOpen size={32} />}
          title="No results found"
          description="Try a different query or category."
        />
      )}

      {!query && results.length === 0 && (
        <EmptyState
          icon={<BookOpen size={32} />}
          title="Search the knowledge base"
          description="Query techniques, commands, methodologies, and patterns from the ingested knowledge files."
        />
      )}
    </div>
  );
}
