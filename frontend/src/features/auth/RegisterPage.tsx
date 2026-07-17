import { useState } from "react";
import { Crosshair } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";

interface RegisterPageProps {
  onSwitchToLogin: () => void;
}

export function RegisterPage({ onSwitchToLogin }: RegisterPageProps) {
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await register(email, username, password);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed");
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
          <h2 className="text-lg font-semibold text-rw-text mb-1">Create account</h2>
          <p className="text-xs text-rw-dim mb-5">Get started with RedWeaver</p>

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
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
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
              Create account
            </Button>
          </form>
        </div>

        <p className="text-center text-xs text-rw-dim mt-4">
          Already have an account?{" "}
          <button onClick={onSwitchToLogin} className="text-rw-accent hover:text-rw-accent-hover transition-colors">
            Sign in
          </button>
        </p>
      </div>
    </div>
  );
}
