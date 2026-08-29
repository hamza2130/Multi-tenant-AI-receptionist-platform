"use client";

import { useState } from "react";
import Link from "next/link";

export default function SignupPage() {
  const [businessName, setBusinessName] = useState("");
  const [vertical, setVertical] = useState("clinic");
  const [otherVertical, setOtherVertical] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    const finalVertical = vertical === "other" ? otherVertical.trim() : vertical;
    // Only "clinic", "restaurant", and "real_estate" are real templates —
    // "other" has no template, so template_key stays null and the
    // tenant starts from a blank Settings/Knowledge Base, same as before.
    const templateKey = vertical === "other" ? null : vertical;
    try {
      const res = await fetch("http://localhost:8000/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_name: businessName,
          vertical: finalVertical,
          email,
          password,
          template_key: templateKey,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Couldn't create your account. Try again.");
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
      <div className="hidden lg:flex lg:w-[42%] flex-col justify-between bg-teal-deep text-paper p-12 relative overflow-hidden">
        <div className="absolute inset-0 opacity-[0.06]" style={{
          backgroundImage: "radial-gradient(circle, #FAF6EF 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }} />
        <div className="relative flex items-center gap-3">
          <BellMark />
          <span className="font-display text-lg tracking-wide">Front Desk</span>
        </div>
        <div className="relative">
          <p className="font-display italic text-3xl leading-snug text-brass-light">
            Set up your receptionist
            <br />
            before your next call comes in.
          </p>
          <div className="mt-8 h-px w-16 bg-brass" />
          <ol className="mt-6 space-y-2 text-sm text-paper/70">
            <li>1. Tell us about your business</li>
            <li>2. Upload what it should know</li>
            <li>3. Test it, then go live</li>
          </ol>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-8 overflow-y-auto">
        <div className="w-full max-w-sm py-8">
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <BellMark dark />
            <span className="font-display text-lg text-ink">Front Desk</span>
          </div>

          <h1 className="font-display text-3xl text-ink mb-1">Create your account</h1>
          <p className="text-ink-soft text-sm mb-8">Takes about a minute.</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Field label="Business name">
              <input
                required
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                placeholder="Sunrise Clinic"
                className={inputClass}
              />
            </Field>

            <Field label="What kind of business">
              <select
                value={vertical}
                onChange={(e) => setVertical(e.target.value)}
                className={inputClass}
              >
                <option value="clinic">Clinic / Medical practice</option>
                <option value="restaurant">Restaurant</option>
                <option value="real_estate">Real estate</option>
                <option value="other">Something else</option>
              </select>
              {vertical !== "other" && (
                <p className="text-xs text-ink-soft/70 mt-1.5">
                  We'll pre-fill your hours, services, and starter info for this
                  business type — fully editable afterward.
                </p>
              )}
            </Field>
            {vertical === "other" && (
              <Field label="Tell us what kind">
                <input
                  required
                  value={otherVertical}
                  onChange={(e) => setOtherVertical(e.target.value)}
                  placeholder="e.g. salon, law firm, gym…"
                  className={inputClass}
                />
              </Field>
            )}

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
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
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
              {loading ? "Creating your account…" : "Create account"}
            </button>
          </form>

          <p className="text-sm text-ink-soft mt-8">
            Already set up?{" "}
            <Link href="/login" className="text-teal-deep font-medium hover:text-brass transition-colors">
              Sign in
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
