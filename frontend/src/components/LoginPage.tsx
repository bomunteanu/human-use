import { useState } from "react";
import { useAuth } from "../hooks/useAuth";

export function LoginPage() {
  const { login } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const endpoint = mode === "login" ? "/auth/login" : "/auth/register";
      const res = await fetch(`http://localhost:8000${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail ?? "Something went wrong");
        return;
      }

      login(data.access_token);
    } catch {
      setError("Connection failed. Is the server running?");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0d1117] flex items-center justify-center">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <span className="text-[22px] font-semibold text-[#e6edf3]">human-use</span>
          <p className="text-[13px] text-[#7d8590] mt-1">Research powered by human intelligence</p>
        </div>

        {/* Card */}
        <div className="bg-[#161b22] border border-[#30363d] rounded-[12px] p-6">
          {/* Tab toggle */}
          <div className="flex bg-[#0d1117] rounded-[8px] p-1 mb-5">
            <button
              type="button"
              onClick={() => { setMode("login"); setError(null); }}
              className={`flex-1 py-1.5 text-[13px] rounded-[6px] font-medium transition-colors ${
                mode === "login"
                  ? "bg-[#21262d] text-[#e6edf3]"
                  : "text-[#7d8590] hover:text-[#e6edf3]"
              }`}
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => { setMode("register"); setError(null); }}
              className={`flex-1 py-1.5 text-[13px] rounded-[6px] font-medium transition-colors ${
                mode === "register"
                  ? "bg-[#21262d] text-[#e6edf3]"
                  : "text-[#7d8590] hover:text-[#e6edf3]"
              }`}
            >
              Create account
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[12px] text-[#7d8590] mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="w-full bg-[#0d1117] border border-[#30363d] rounded-[8px] px-3 py-2 text-[13px] text-[#e6edf3] placeholder-[#7d8590] focus:outline-none focus:border-[#58a6ff] focus:ring-1 focus:ring-[#58a6ff]"
              />
            </div>
            <div>
              <label className="block text-[12px] text-[#7d8590] mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                placeholder={mode === "register" ? "At least 8 characters" : ""}
                className="w-full bg-[#0d1117] border border-[#30363d] rounded-[8px] px-3 py-2 text-[13px] text-[#e6edf3] placeholder-[#7d8590] focus:outline-none focus:border-[#58a6ff] focus:ring-1 focus:ring-[#58a6ff]"
              />
            </div>

            {error && (
              <p className="text-[12px] text-[#f85149] bg-[#f8514918] border border-[#f8514933] rounded-[6px] px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2 text-[13px] font-medium bg-[#238636] hover:bg-[#2ea043] disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-[8px] transition-colors"
            >
              {isLoading
                ? "Please wait…"
                : mode === "login"
                ? "Sign in"
                : "Create account"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
