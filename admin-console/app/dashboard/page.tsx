"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type TenantInfo = {
  email: string;
  tenant_id: string;
  business_name: string;
  vertical: string;
  api_key: string;
  phone_number: string | null;
};

export default function DashboardPage() {
  const [info, setInfo] = useState<TenantInfo | null>(null);
  const [error, setError] = useState("");
  const [stats, setStats] = useState<{ bookings: number; leads: number; conversations: number } | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      window.location.href = "/login";
      return;
    }
    fetch("http://localhost:8000/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Session expired — please sign in again.");
        return res.json();
      })
      .then(setInfo)
      .catch((err) => {
        setError(err.message);
        localStorage.removeItem("access_token");
      });

    fetch("http://localhost:8000/console/stats", { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => res.json())
      .then(setStats)
      .catch(() => {});
  }, []);

  function signOut() {
    localStorage.removeItem("access_token");
    window.location.href = "/login";
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-64 bg-teal-deep text-paper flex flex-col p-6">
        <div className="flex items-center gap-3 mb-10">
          <BellMark />
          <span className="font-display text-lg">Front Desk</span>
        </div>
        <nav className="flex flex-col gap-1 text-sm">
          <NavItem label="Overview" active />
          <Link href="/dashboard/knowledge-base" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">
            Knowledge Base
          </Link>
          <Link href="/dashboard/test-sandbox" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">
            Test Sandbox
          </Link>
          <Link href="/dashboard/bookings" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">
            Bookings
          </Link>
          <Link href="/dashboard/leads" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">
            Leads &amp; Messages
          </Link>
          <Link href="/dashboard/settings" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">
            Settings
          </Link>
          <Link href="/dashboard/publish" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">
            Publish
          </Link>
        </nav>
        <button
          onClick={signOut}
          className="mt-auto text-sm text-paper/50 hover:text-paper transition-colors text-left"
        >
          Sign out
        </button>
      </aside>

      {/* Main */}
      <main className="flex-1 p-10">
        {error && (
          <p className="text-sm text-danger mb-6">{error} <a href="/login" className="underline">Sign in</a></p>
        )}

        {!info && !error && (
          <p className="text-ink-soft text-sm">Loading your business…</p>
        )}

        {info && (
          <>
            {/* Nameplate — the signature element */}
            <div className="bg-white border border-line rounded-xl px-8 py-6 mb-8 flex items-center justify-between shadow-sm">
              <div>
                <p className="text-xs uppercase tracking-widest text-brass font-medium mb-1">
                  {info.vertical.replace("_", " ")}
                </p>
                <h1 className="font-display text-3xl text-ink">{info.business_name}</h1>
              </div>
              <div className="text-right">
                <p className="text-xs text-ink-soft uppercase tracking-wide mb-1">Status</p>
                <span className="inline-flex items-center gap-1.5 text-sm font-medium text-teal-deep">
                  <span className="w-1.5 h-1.5 rounded-full bg-teal-mid" />
                  Sandbox
                </span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-8">
              <StatCard label="Bookings" value={stats ? String(stats.bookings) : "…"} />
              <StatCard label="Leads captured" value={stats ? String(stats.leads) : "…"} />
              <StatCard label="Conversations" value={stats ? String(stats.conversations) : "…"} />
            </div>

            <div className="bg-white border border-line rounded-xl p-8">
              <h2 className="font-display text-xl text-ink mb-2">Get your receptionist ready</h2>
              <p className="text-sm text-ink-soft mb-6 max-w-md">
                Upload what your business does — services, hours, policies — so it can start
                answering questions correctly.
              </p>
              <Link
                href="/dashboard/knowledge-base"
                className="inline-block bg-brass hover:bg-brass/90 text-teal-deep font-semibold text-sm px-5 py-2.5 rounded-md transition-colors"
              >
                Upload your business info
              </Link>
              <p className="text-xs text-ink-soft/60 mt-4 font-mono">
                API key: {info.api_key.slice(0, 18)}···
              </p>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function NavItem({ label, active, comingSoon }: { label: string; active?: boolean; comingSoon?: boolean }) {
  return (
    <div
      className={`px-3 py-2 rounded-md flex items-center justify-between ${
        active ? "bg-white/10 text-paper" : "text-paper/60"
      } ${comingSoon ? "cursor-not-allowed" : "cursor-pointer hover:text-paper"}`}
    >
      <span>{label}</span>
      {comingSoon && <span className="text-[10px] uppercase tracking-wide text-brass-light/70">Soon</span>}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white border border-line rounded-xl px-6 py-5">
      <p className="text-xs uppercase tracking-wide text-ink-soft mb-1">{label}</p>
      <p className="font-display text-3xl text-ink">{value}</p>
    </div>
  );
}

function BellMark() {
  return (
    <svg width="24" height="24" viewBox="0 0 28 28" fill="none">
      <path
        d="M14 4C9.6 4 6 7.6 6 12v4l-2 4h20l-2-4v-4c0-4.4-3.6-8-8-8z"
        stroke="#E9D3AC"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path d="M11 21a3 3 0 0 0 6 0" stroke="#E9D3AC" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
