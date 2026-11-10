"use client";
import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [loginMode, setLoginMode] = useState<"credentials" | "token">("credentials");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [workerToken, setWorkerToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setLoading(true);

    try {
      if (loginMode === "token") {
        const token = workerToken.trim();
        if (!token.startsWith("hpc_w_") && token.length < 10) {
          setErrorMsg("Format WORKER_TOKEN tidak valid (biasanya diawali dengan hpc_w_...).");
          setLoading(false);
          return;
        }

        // Store session
        if (typeof window !== "undefined") {
          localStorage.setItem("hpc_worker_token", token);
          localStorage.setItem("hpc_worker_name", "Authorized-Worker");
          localStorage.setItem("hpc_worker_id", "w-verified");
        }

        router.push("/dashboard");
      } else {
        if (!identifier.trim()) {
          setErrorMsg("Username atau Email wajib diisi.");
          setLoading(false);
          return;
        }

        // Save session
        if (typeof window !== "undefined") {
          localStorage.setItem("hpc_username", identifier);
          localStorage.setItem("hpc_email", identifier.includes("@") ? identifier : `${identifier}@hpc.local`);
          localStorage.setItem("hpc_worker_token", "hpc_w_" + Math.random().toString(36).substring(2, 18));
          localStorage.setItem("hpc_worker_id", "w-" + Math.random().toString(36).substring(2, 8));
        }

        router.push("/dashboard");
      }
    } catch (err: any) {
      setErrorMsg("Gagal melakukan login: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative py-16 px-4 sm:px-6 lg:px-8">
      {/* Background radial glow */}
      <div className="pointer-events-none absolute left-1/2 top-10 -translate-x-1/2 h-[300px] w-[500px] rounded-full bg-cyber-amber-deep/15 blur-[90px]" />

      <div className="mx-auto max-w-md">
        <div className="text-center">
          <span className="font-mono text-xs font-semibold uppercase tracking-widest text-cyber-amber-bright">
            // ACCESS CONTROL
          </span>
          <h1 className="mt-2 font-mono text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
            SIGN IN TO HPC GRID
          </h1>
          <p className="mt-2 font-mono text-xs text-zinc-400">
            Authenticate to access your worker dashboard, task logs, and compute telemetry.
          </p>
        </div>

        {/* Tab switch: Credentials vs Worker Token */}
        <div className="mt-8 flex rounded border border-cyber-border bg-cyber-surface p-1 font-mono text-xs">
          <button
            type="button"
            onClick={() => { setLoginMode("credentials"); setErrorMsg(null); }}
            className={`flex-1 py-1.5 text-center font-semibold rounded transition-all ${
              loginMode === "credentials"
                ? "bg-cyber-amber text-cyber-void shadow-amber-glow-sm"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            ACCOUNT LOGIN
          </button>
          <button
            type="button"
            onClick={() => { setLoginMode("token"); setErrorMsg(null); }}
            className={`flex-1 py-1.5 text-center font-semibold rounded transition-all ${
              loginMode === "token"
                ? "bg-cyber-amber text-cyber-void shadow-amber-glow-sm"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            QUICK TOKEN ACCESS
          </button>
        </div>

        {errorMsg && (
          <div className="mt-4 rounded border border-red-500/50 bg-red-950/40 p-3 font-mono text-xs text-red-300">
            [ERROR]: {errorMsg}
          </div>
        )}

        <div className="cyber-box mt-4 p-6 sm:p-8">
          <form onSubmit={handleLogin} className="space-y-4">
            {loginMode === "credentials" ? (
              <>
                <div>
                  <label className="block font-mono text-[11px] text-zinc-300">
                    EMAIL OR USERNAME
                  </label>
                  <input
                    type="text"
                    required
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder="user@example.com / username"
                    className="mt-1 w-full rounded border border-cyber-border bg-cyber-black px-3 py-2 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                  />
                </div>

                <div>
                  <div className="flex justify-between items-center">
                    <label className="block font-mono text-[11px] text-zinc-300">
                      PASSWORD
                    </label>
                    <span className="font-mono text-[10px] text-zinc-500">OPTIONAL IN DEMO</span>
                  </div>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="mt-1 w-full rounded border border-cyber-border bg-cyber-black px-3 py-2 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                  />
                </div>
              </>
            ) : (
              <div>
                <label className="block font-mono text-[11px] text-zinc-300">
                  WORKER AUTHORIZATION TOKEN
                </label>
                <textarea
                  rows={3}
                  required
                  value={workerToken}
                  onChange={(e) => setWorkerToken(e.target.value)}
                  placeholder="hpc_w_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                  className="mt-1 w-full rounded border border-cyber-border bg-cyber-black px-3 py-2 font-mono text-xs text-cyber-amber-bright placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                />
                <p className="mt-1 font-mono text-[10px] text-zinc-500">
                  Direct token access issued from CLI authentication or email OTP verification.
                </p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="mt-6 flex w-full items-center justify-center space-x-2 rounded border border-cyber-amber bg-cyber-amber py-3 font-mono text-xs font-bold text-cyber-void shadow-amber-glow transition-all hover:bg-cyber-amber-bright hover:shadow-amber-glow-lg disabled:opacity-50"
            >
              <span>{loading ? "AUTHENTICATING..." : "ENTER COMMAND CENTER"}</span>
              <span>&rarr;</span>
            </button>
          </form>

          <div className="mt-6 border-t border-cyber-border pt-4 text-center font-mono text-xs text-zinc-400">
            Don&apos;t have an authorized worker node?{" "}
            <Link href="/register" className="text-cyber-amber-bright hover:underline">
              Register Node &rarr;
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

