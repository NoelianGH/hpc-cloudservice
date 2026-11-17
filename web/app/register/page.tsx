"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import TerminalCode from "@/components/TerminalCode";
import { GitHubFactors } from "@/lib/types";

export default function RegisterPage() {
  const router = useRouter();

  // Form states
  const [formData, setFormData] = useState({
    firstName: "",
    lastName: "",
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
    githubUsername: "",
    workerName: "",
  });

  // Flow step: 1 = Form, 2 = OTP, 3 = Success
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Analysis result & Session details
  const [sessionId, setSessionId] = useState<string>("");
  const [githubScore, setGithubScore] = useState<number | null>(null);
  const [githubFactors, setGithubFactors] = useState<GitHubFactors | null>(null);

  // OTP input
  const [otpInput, setOtpInput] = useState("");
  const [resending, setResending] = useState(false);
  const [resendMsg, setResendMsg] = useState<string | null>(null);

  // Verified output credentials
  const [verifiedWorker, setVerifiedWorker] = useState<{
    worker_id: string;
    worker_name: string;
    github_username: string;
  } | null>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  // Step 1: Submit Form -> Check GitHub Anti-Fake -> Send OTP
  const handleSubmitRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!formData.githubUsername.trim()) {
      setErrorMsg("Username GitHub wajib diisi untuk verifikasi reputasi node.");
      return;
    }
    if (!formData.email.trim() || !formData.email.includes("@")) {
      setErrorMsg("Alamat email tidak valid.");
      return;
    }
    // Password = satu-satunya cara login WEBSITE (dashboard).
    if (formData.password.length < 8) {
      setErrorMsg("Password minimal 8 karakter (dipakai untuk login website).");
      return;
    }
    if (formData.password !== formData.confirmPassword) {
      setErrorMsg("Konfirmasi password tidak cocok.");
      return;
    }

    setLoading(true);

    try {
      const res = await fetch("/api/auth/register-request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          firstName: formData.firstName,
          lastName: formData.lastName,
          username: formData.username || formData.email.split("@")[0],
          email: formData.email,
          password: formData.password,
          githubUsername: formData.githubUsername.trim(),
          workerName: formData.workerName.trim() || `worker-${formData.githubUsername.trim().toLowerCase()}`,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        let errText = "Verifikasi registrasi gagal.";
        if (data.detail) {
          if (typeof data.detail === "string") {
            errText = data.detail;
          } else if (data.detail.message) {
            errText = data.detail.message;
            if (data.detail.reasons && data.detail.reasons.length > 0) {
              errText += `\nAlasan: ${data.detail.reasons.join(" | ")}`;
            }
          }
        }
        setErrorMsg(errText);
        setLoading(false);
        return;
      }

      setSessionId(data.session_id);
      setGithubScore(data.github_score ?? 100);
      setGithubFactors(data.factors ?? null);

      // Proceed to Step 2 (OTP)
      setStep(2);
    } catch (err: any) {
      setErrorMsg("Gagal menghubungi server verifikasi: " + (err.message || "Network Error"));
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Verify OTP
  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!otpInput.trim() || otpInput.trim().length < 6) {
      setErrorMsg("Masukkan 6 digit kode OTP yang valid.");
      return;
    }

    setLoading(true);

    try {
      const res = await fetch("/api/auth/verify-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          otp: otpInput.trim(),
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setErrorMsg(data.detail || "Kode OTP salah atau telah kadaluarsa.");
        setLoading(false);
        return;
      }

      // Success!
      setVerifiedWorker({
        worker_id: data.worker_id,
        worker_name: data.worker_name,
        github_username: data.github_username,
      });

      // Langsung login website dengan email + password yang baru dibuat. Server menyimpan
      // SESI web di cookie httpOnly.
      await fetch("/api/volunteer/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: formData.email.trim(), password: formData.password }),
      }).catch(() => undefined);

      setStep(3);
    } catch (err: any) {
      setErrorMsg("Gagal memverifikasi OTP: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Step 2b: Resend OTP
  const handleResendOtp = async () => {
    setResending(true);
    setResendMsg(null);
    try {
      const res = await fetch("/api/auth/resend-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
      await res.json();
      setResendMsg("Kode OTP baru telah dikirimkan ke email Anda.");
    } catch (err: any) {
      setResendMsg("Gagal mengirim ulang OTP: " + err.message);
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="relative py-12 px-4 sm:px-6 lg:px-8">
      {/* Background radial glow */}
      <div className="pointer-events-none absolute left-1/2 top-10 -translate-x-1/2 h-[350px] w-[600px] rounded-full bg-cyber-amber-deep/15 blur-[100px]" />

      <div className="mx-auto max-w-2xl">
        {/* Top Header Badge */}
        <div className="text-center">
          <span className="font-mono text-xs font-semibold uppercase tracking-wider text-cyber-amber-bright">
            Aktivasi Node Relawan IdleScale
          </span>
          <h1 className="mt-2 font-mono text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
            {step === 1 && "PENDAFTARAN WORKER NODE"}
            {step === 2 && "VERIFIKASI KODE KEAMANAN OTP"}
            {step === 3 && "AKTIVASI NODE BERHASIL"}
          </h1>
          <p className="mt-2 font-mono text-xs text-zinc-400">
            {step === 1 && "Gerbang validasi reputasi anti-fake memeriksa akun GitHub Anda sebelum memberikan izin akses worker."}
            {step === 2 && `Masukkan 6 digit kode OTP rahasia yang telah dikirim ke ${formData.email}`}
            {step === 3 && "Akun relawan Anda aktif. Ambil jobdesk di dashboard untuk mendapat akses compute node."}
          </p>
        </div>

        {/* Progress Pipeline Indicator */}
        <div className="mt-8 flex items-center justify-between font-mono text-xs">
          <div className={`flex items-center space-x-2 ${step >= 1 ? "text-cyber-amber-bright" : "text-zinc-600"}`}>
            <span className={`flex h-6 w-6 items-center justify-center rounded-full border ${step >= 1 ? "border-cyber-amber bg-cyber-amber/20" : "border-zinc-700 bg-cyber-surface"}`}>
              1
            </span>
            <span className="hidden sm:inline">IDENTITY & GITHUB</span>
          </div>

          <div className={`h-[1px] flex-1 mx-3 ${step >= 2 ? "bg-cyber-amber" : "bg-zinc-800"}`} />

          <div className={`flex items-center space-x-2 ${step >= 2 ? "text-cyber-amber-bright" : "text-zinc-600"}`}>
            <span className={`flex h-6 w-6 items-center justify-center rounded-full border ${step >= 2 ? "border-cyber-amber bg-cyber-amber/20" : "border-zinc-700 bg-cyber-surface"}`}>
              2
            </span>
            <span className="hidden sm:inline">EMAIL OTP</span>
          </div>

          <div className={`h-[1px] flex-1 mx-3 ${step === 3 ? "bg-cyber-amber" : "bg-zinc-800"}`} />

          <div className={`flex items-center space-x-2 ${step === 3 ? "text-emerald-400" : "text-zinc-600"}`}>
            <span className={`flex h-6 w-6 items-center justify-center rounded-full border ${step === 3 ? "border-emerald-500 bg-emerald-500/20 text-emerald-400" : "border-zinc-700 bg-cyber-surface"}`}>
              3
            </span>
            <span className="hidden sm:inline">AUTHORIZED</span>
          </div>
        </div>

        {/* Error Alert Banner */}
        {errorMsg && (
          <div className="mt-6 rounded border border-red-500/50 bg-red-950/40 p-4 font-mono text-xs text-red-200">
            <div className="flex items-start space-x-2">
              <span className="text-red-400 font-bold">Peringatan:</span>
              <div className="flex-1 whitespace-pre-line">{errorMsg}</div>
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* STEP 1: Registration Form */}
        {/* =================================================================== */}
        {step === 1 && (
          <div className="cyber-box mt-8 p-6 sm:p-8">
            <form onSubmit={handleSubmitRegister} className="space-y-4">
              <div className="border-b border-cyber-border pb-3">
                <h3 className="font-mono text-xs font-bold text-cyber-amber-bright uppercase tracking-wider">
                  [1] PERSONAL & CREDENTIALS
                </h3>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className="block font-mono text-[11px] text-zinc-300">
                    FIRST NAME <span className="text-cyber-amber-bright">*</span>
                  </label>
                  <input
                    type="text"
                    name="firstName"
                    required
                    value={formData.firstName}
                    onChange={handleInputChange}
                    placeholder="e.g. Noel"
                    className="mt-1 w-full rounded border border-cyber-border bg-cyber-black px-3 py-2 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                  />
                </div>

                <div>
                  <label className="block font-mono text-[11px] text-zinc-300">
                    LAST NAME <span className="font-sans text-[10px] text-zinc-500">(opsional)</span>
                  </label>
                  <input
                    type="text"
                    name="lastName"
                    value={formData.lastName}
                    onChange={handleInputChange}
                    placeholder="e.g. Pratama"
                    className="mt-1 w-full rounded border border-cyber-border bg-cyber-black px-3 py-2 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className="block font-mono text-[11px] text-zinc-300">
                    PREFERRED USERNAME <span className="text-cyber-amber-bright">*</span>
                  </label>
                  <input
                    type="text"
                    name="username"
                    required
                    value={formData.username}
                    onChange={handleInputChange}
                    placeholder="e.g. noel_hpc"
                    className="mt-1 w-full rounded border border-cyber-border bg-cyber-black px-3 py-2 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                  />
                </div>

                <div>
                  <label className="block font-mono text-[11px] text-zinc-300">
                    EMAIL ADDRESS (GMAIL / WORK) <span className="text-cyber-amber-bright">*</span>
                  </label>
                  <input
                    type="email"
                    name="email"
                    required
                    value={formData.email}
                    onChange={handleInputChange}
                    placeholder="noel@example.com"
                    className="mt-1 w-full rounded border border-cyber-border bg-cyber-black px-3 py-2 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                  />
                  <span className="text-[10px] text-zinc-500 font-mono">
                    Security OTP code will be sent to this email address.
                  </span>
                </div>
              </div>

              <div className="border-b border-cyber-border pt-4 pb-2">
                <h3 className="font-mono text-xs font-bold text-cyber-amber-bright uppercase tracking-wider">
                  [2] GITHUB VERIFICATION & NODE IDENTITY
                </h3>
              </div>

              <div>
                <label className="block font-mono text-[11px] text-zinc-300">
                  GITHUB USERNAME (ANTI-FAKE WORKER VERIFICATION) <span className="text-cyber-amber-bright">*</span>
                </label>
                <div className="relative mt-1">
                  <span className="absolute inset-y-0 left-0 flex items-center pl-3 font-mono text-xs text-zinc-500">
                    github.com/
                  </span>
                  <input
                    type="text"
                    name="githubUsername"
                    required
                    value={formData.githubUsername}
                    onChange={handleInputChange}
                    placeholder="username"
                    className="w-full rounded border border-cyber-border bg-cyber-black py-2 pl-24 pr-3 font-mono text-xs text-cyber-amber-bright placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                  />
                </div>
                <div className="mt-1.5 rounded border border-cyber-border bg-cyber-surface/60 p-2 text-[10px] text-zinc-400 font-mono">
                  <span className="text-cyber-amber-light font-semibold">[CRITERIA]:</span> Minimum 30 days account age and at least 2 public repositories to prevent Sybil/bot accounts.
                </div>
              </div>

              <div>
                <label className="block font-mono text-[11px] text-zinc-300">
                  WORKER NODE DISPLAY NAME (OPTIONAL)
                </label>
                <input
                  type="text"
                  name="workerName"
                  value={formData.workerName}
                  onChange={handleInputChange}
                  placeholder={`e.g. laptop-noel-node`}
                  className="mt-1 w-full rounded border border-cyber-border bg-cyber-black px-3 py-2 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 pt-2">
                <div>
                  <label className="block font-mono text-[11px] text-zinc-300">
                    PASSWORD LOGIN WEBSITE *
                  </label>
                  <div className="relative mt-1">
                    <input
                      type={showPassword ? "text" : "password"}
                      name="password"
                      required
                      minLength={8}
                      autoComplete="new-password"
                      value={formData.password}
                      onChange={handleInputChange}
                      placeholder="••••••••••••"
                      className="w-full rounded border border-cyber-border bg-cyber-black px-3 py-2 pr-10 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-cyber-amber-bright focus:outline-none p-1 transition-colors"
                      title={showPassword ? "Sembunyikan password" : "Lihat password"}
                      aria-label={showPassword ? "Sembunyikan password" : "Lihat password"}
                    >
                      {showPassword ? (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                        </svg>
                      ) : (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block font-mono text-[11px] text-zinc-300">
                    CONFIRM PASSWORD
                  </label>
                  <div className="relative mt-1">
                    <input
                      type={showConfirmPassword ? "text" : "password"}
                      name="confirmPassword"
                      required
                      autoComplete="new-password"
                      value={formData.confirmPassword}
                      onChange={handleInputChange}
                      placeholder="••••••••••••"
                      className="w-full rounded border border-cyber-border bg-cyber-black px-3 py-2 pr-10 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-cyber-amber-bright focus:outline-none p-1 transition-colors"
                      title={showConfirmPassword ? "Sembunyikan password" : "Lihat password"}
                      aria-label={showConfirmPassword ? "Sembunyikan password" : "Lihat password"}
                    >
                      {showConfirmPassword ? (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                        </svg>
                      ) : (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
              </div>

              <p className="font-mono text-[10px] leading-relaxed text-zinc-500">
                Email + password dipakai untuk masuk ke website (dashboard). Akses compute node (ssh) memakai{" "}
                <span className="text-zinc-300">token node</span> terpisah yang terbit tiap kali Anda mengambil jobdesk.
              </p>

              <button
                type="submit"
                disabled={loading}
                className="mt-6 flex w-full items-center justify-center space-x-2 rounded border border-cyber-amber bg-cyber-amber py-3 font-mono text-xs font-bold text-cyber-void shadow-amber-glow transition-all hover:bg-cyber-amber-bright hover:shadow-amber-glow-lg disabled:opacity-50"
              >
                {loading ? (
                  <span>RUNNING GITHUB REPUTATION SCAN & DISPATCHING OTP...</span>
                ) : (
                  <>
                    <span>VERIFY GITHUB & DISPATCH OTP CODE</span>
                    <span>&rarr;</span>
                  </>
                )}
              </button>
            </form>

            <div className="mt-6 text-center font-mono text-xs text-zinc-400">
              Sudah punya akun?{" "}
              <Link href="/login" className="text-cyber-amber-bright hover:underline">
                Sign in to Dashboard &rarr;
              </Link>
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* STEP 2: OTP Verification Form */}
        {/* =================================================================== */}
        {step === 2 && (
          <div className="cyber-box mt-8 p-6 sm:p-8">
            {/* GitHub Analysis Badge */}
            <div className="mb-6 rounded border border-emerald-500/40 bg-emerald-950/20 p-4 font-mono text-xs">
              <div className="flex items-center justify-between text-emerald-400 font-bold">
                <span>[✓] GITHUB REPUTATION VALIDATED</span>
                <span>SCORE: {githubScore}/100</span>
              </div>
              {githubFactors && (
                <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-zinc-300 border-t border-emerald-900/50 pt-2">
                  <div>Account Age: <span className="text-emerald-400 font-bold">{githubFactors.account_age_days} days</span></div>
                  <div>Public Repos: <span className="text-emerald-400 font-bold">{githubFactors.public_repos} repos</span></div>
                  <div>Followers: <span className="text-emerald-400 font-bold">{githubFactors.followers}</span></div>
                  <div>Profile: <span className="text-emerald-400 font-bold">{githubFactors.profile_complete ? "Complete" : "Valid"}</span></div>
                </div>
              )}
            </div>

            <form onSubmit={handleVerifyOtp} className="space-y-4">
              <div>
                <label className="block font-mono text-xs text-zinc-300 text-center">
                  ENTER 6-DIGIT VERIFICATION CODE (OTP)
                </label>
                <div className="mt-3 flex justify-center">
                  <input
                    type="text"
                    maxLength={6}
                    required
                    autoFocus
                    value={otpInput}
                    onChange={(e) => setOtpInput(e.target.value.replace(/[^0-9]/g, ""))}
                    placeholder="000000"
                    className="w-48 text-center font-mono text-2xl font-bold tracking-[0.3em] rounded border-2 border-cyber-amber bg-cyber-black py-3 text-cyber-amber-bright placeholder-zinc-700 focus:outline-none focus:shadow-amber-glow"
                  />
                </div>
                <p className="mt-2 text-center font-mono text-[10px] text-zinc-400">
                  Sent to <strong className="text-zinc-200">{formData.email}</strong> &bull; Valid for 10 minutes.
                </p>
              </div>

              {resendMsg && (
                <p className="text-center font-mono text-xs text-cyber-amber-light">
                  {resendMsg}
                </p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="mt-6 flex w-full items-center justify-center space-x-2 rounded border border-cyber-amber bg-cyber-amber py-3 font-mono text-xs font-bold text-cyber-void shadow-amber-glow transition-all hover:bg-cyber-amber-bright hover:shadow-amber-glow-lg disabled:opacity-50"
              >
                {loading ? (
                  <span>AUTHENTICATING SECURITY CODE...</span>
                ) : (
                  <>
                    <span>SUBMIT OTP & ACTIVATE WORKER</span>
                    <span>&gt;</span>
                  </>
                )}
              </button>
            </form>

            <div className="mt-6 flex items-center justify-between border-t border-cyber-border pt-4 font-mono text-xs">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="text-zinc-500 hover:text-zinc-300"
              >
                &larr; Back to Information
              </button>

              <button
                type="button"
                disabled={resending}
                onClick={handleResendOtp}
                className="text-cyber-amber-bright hover:underline disabled:opacity-50"
              >
                {resending ? "Dispatching..." : "Resend OTP Code"}
              </button>
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* STEP 3: Verification Successful & Activation Result */}
        {/* =================================================================== */}
        {step === 3 && verifiedWorker && (
          <div className="cyber-box mt-8 p-6 sm:p-8">
            <div className="flex items-center space-x-3 border-b border-cyber-border pb-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500">
                ✓
              </div>
              <div>
                <h3 className="font-mono text-sm font-bold text-white">
                  VERIFIKASI BERHASIL • NODE RESMI DIIZINKAN
                </h3>
                <p className="font-mono text-xs text-emerald-400">
                  Status relawan: AKTIF &bull; Login website dengan email + password
                </p>
              </div>
            </div>

            {/* Credentials Card */}
            <div className="mt-6 space-y-3 rounded border border-cyber-border bg-cyber-black p-4 font-mono text-xs">
              <div className="flex justify-between items-center border-b border-cyber-border/60 pb-2">
                <span className="text-zinc-400">WORKER ID:</span>
                <span className="text-cyber-amber-bright font-bold">{verifiedWorker.worker_id}</span>
              </div>
              <div className="flex justify-between items-center border-b border-cyber-border/60 pb-2">
                <span className="text-zinc-400">NODE NAME:</span>
                <span className="text-zinc-200">{verifiedWorker.worker_name}</span>
              </div>
              <div className="flex justify-between items-center border-b border-cyber-border/60 pb-2">
                <span className="text-zinc-400">GITHUB USERNAME:</span>
                <span className="text-emerald-400">@{verifiedWorker.github_username} (Terverifikasi)</span>
              </div>
            </div>

            {/* Langkah berikutnya: jobdesk + compute node */}
            <div className="mt-6">
              <h4 className="font-mono text-xs font-bold text-cyber-amber-bright uppercase tracking-wider">
                Langkah Berikutnya
              </h4>
              <ol className="mt-2 list-decimal space-y-1 pl-5 font-mono text-xs text-zinc-400">
                <li>Buka dashboard, tekan <span className="text-zinc-200">AMBIL JOBDESK</span> (jobdesk terlama di antrean).</li>
                <li>Kartu jobdesk menampilkan perintah <span className="text-zinc-200">ssh</span> dan <span className="text-zinc-200">token node</span> (password ssh).</li>
                <li>Login ke compute node dari Command Prompt, kerjakan branch jobdesk, lalu <span className="text-zinc-200">jobdesk ajukan</span>.</li>
                <li>Setelah admin menyetujui, token node mati; ambil jobdesk berikutnya di website.</li>
              </ol>
              <TerminalCode title="Command Prompt / terminal" code={"ssh -p 2222 jd<id>@<alamat compute node>   # password = token node"} />
            </div>

            {/* Action buttons */}
            <div className="mt-6 flex flex-col sm:flex-row gap-3">
              <Link
                href="/dashboard"
                className="flex flex-1 items-center justify-center space-x-2 rounded border border-cyber-amber bg-cyber-amber py-3 font-mono text-xs font-bold text-cyber-void shadow-amber-glow hover:bg-cyber-amber-bright hover:shadow-amber-glow-lg"
              >
                <span>OPEN COMMAND CENTER DASHBOARD</span>
                <span>&rarr;</span>
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
