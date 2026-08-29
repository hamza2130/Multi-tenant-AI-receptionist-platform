"use client";

import { useState } from "react";
import Link from "next/link";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Couldn't sign you in. Check your details and try again.");
      }
      const data = await res.json();
      localStorage.setItem("access_token", data.access_token);
      window.location.href = "/dashboard";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen w-full">
      {/* Left — brand panel */}
      <div className="hidden lg:flex lg:w-[42%] flex-col justify-between bg-teal-deep text-paper p-12 relative overflow-hidden">
        <div className="absolute inset-0 opacity-[0.06]" style={{
          backgroundImage: "radial-gradient(circle, #FAF6EF 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }} />
        <div className="relative">
          <div className="flex items-center gap-3">
            <BellMark />
            <span className="font-display text-lg tracking-wide">Front Desk</span>
          </div>
        </div>

        <div className="relative">
          <p className="font-display italic text-3xl leading-snug text-brass-light">
            &ldquo;Every call answered.
            <br />
            Every business, its own voice.&rdquo;
          </p>
          <div className="mt-8 h-px w-16 bg-brass" />
          <p className="mt-6 text-sm text-paper/60 max-w-xs leading-relaxed">
            Train an AI receptionist on your business, in minutes — no code, no waiting room.
          </p>
        </div>
      </div>

      {/* Right — form panel */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <BellMark dark />
            <span className="font-display text-lg text-ink">Front Desk</span>
          </div>

          <h1 className="font-display text-3xl text-ink mb-1">Welcome back</h1>
          <p className="text-ink-soft text-sm mb-8">Sign in to manage your receptionist.</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Field label="Email">
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@business.com"
                className={inputClass}
              />
            </Field>
            <Field label="Password">
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className={inputClass}
              />
            </Field>

            {error && (
              <p className="text-sm text-danger bg-danger/5 border border-danger/20 rounded-md px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-brass hover:bg-brass/90 disabled:opacity-60 text-teal-deep font-semibold text-sm py-2.5 rounded-md transition-colors mt-2"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="text-sm text-ink-soft mt-8">
            New here?{" "}
            <Link href="/signup" className="text-teal-deep font-medium hover:text-brass transition-colors">
              Create an account
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

const inputClass =
  "w-full rounded-md border border-line bg-white px-3 py-2.5 text-sm text-ink placeholder:text-ink-soft/50 focus:outline-none focus:ring-2 focus:ring-brass/40 focus:border-brass transition-shadow";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-ink-soft mb-1.5 uppercase tracking-wide">
        {label}
      </span>
      {children}
    </label>
  );
}

function BellMark({ dark }: { dark?: boolean }) {
  const color = dark ? "#1F4B43" : "#E9D3AC";
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
      <path
        d="M14 4C9.6 4 6 7.6 6 12v4l-2 4h20l-2-4v-4c0-4.4-3.6-8-8-8z"
        stroke={color}
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path d="M11 21a3 3 0 0 0 6 0" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
