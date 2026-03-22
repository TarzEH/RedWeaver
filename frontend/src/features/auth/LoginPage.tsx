import { useState } from "react";
import { Crosshair } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";

interface LoginPageProps {
  onSwitchToRegister: () => void;
}

export function LoginPage({ onSwitchToRegister }: LoginPageProps) {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(email, password);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-rw-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm animate-scale-in">
        <div className="flex items-center justify-center gap-3 mb-8">
          <Crosshair size={32} className="text-rw-accent" />
          <h1 className="text-2xl font-bold text-rw-text">RedWeaver</h1>
        </div>

        <div className="bg-rw-elevated border border-rw-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-rw-text mb-1">Welcome back</h2>
          <p className="text-xs text-rw-dim mb-4">Sign in to continue</p>
          <div className="bg-rw-surface/50 border border-rw-border rounded-lg px-3 py-2 mb-4">
            <p className="text-[10px] text-rw-dim uppercase tracking-wider mb-1">Default credentials</p>
            <p className="text-xs text-rw-muted font-mono">admin@redweaver.io / redweaver</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
            <Input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            {error && <p className="text-xs text-red-400">{error}</p>}
            <Button type="submit" loading={loading} className="w-full">
              Sign in
            </Button>
          </form>
        </div>

        <p className="text-center text-xs text-rw-dim mt-4">
          No account?{" "}
          <button onClick={onSwitchToRegister} className="text-rw-accent hover:text-rw-accent-hover transition-colors">
            Create one
          </button>
        </p>
      </div>
    </div>
  );
}
