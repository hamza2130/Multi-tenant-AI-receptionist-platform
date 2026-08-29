"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type LeadItem = { id: string; name: string; phone: string; intent: string; category: "lead" | "message" | "escalation" };

export default function LeadsPage() {
  const [leads, setLeads] = useState<LeadItem[] | null>(null);
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  useEffect(() => {
    if (!token) {
      window.location.href = "/login";
      return;
    }
    fetch("http://localhost:8000/console/leads", { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => res.json())
      .then(setLeads)
      .catch(() => setLeads([]));
  }, [token]);

  return (
    <div className="flex min-h-screen">
      <aside className="w-64 bg-teal-deep text-paper flex flex-col p-6">
        <div className="flex items-center gap-3 mb-10">
          <BellMark />
          <span className="font-display text-lg">Front Desk</span>
        </div>
        <nav className="flex flex-col gap-1 text-sm">
          <Link href="/dashboard" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">Overview</Link>
          <Link href="/dashboard/knowledge-base" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">Knowledge Base</Link>
          <Link href="/dashboard/test-sandbox" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">Test Sandbox</Link>
          <Link href="/dashboard/bookings" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">Bookings</Link>
          <div className="px-3 py-2 rounded-md bg-white/10 text-paper">Leads & Messages</div>
          <Link href="/dashboard/settings" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">Settings</Link>
          <Link href="/dashboard/publish" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">
            Publish
          </Link>
        </nav>
      </aside>

      <main className="flex-1 p-10 max-w-2xl">
        <h1 className="font-display text-3xl text-ink mb-1">Leads &amp; Messages</h1>
        <p className="text-ink-soft text-sm mb-8">
          Anything your receptionist couldn&apos;t fully resolve itself — interested callers, messages, and things flagged for a human.
        </p>

        {!leads ? (
          <p className="text-sm text-ink-soft">Loading…</p>
        ) : leads.length === 0 ? (
          <p className="text-sm text-ink-soft">Nothing here yet.</p>
        ) : (
          <div className="bg-white border border-line rounded-xl divide-y divide-line">
            {leads.map((l) => (
              <div key={l.id} className="px-5 py-4 text-sm">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-ink font-medium">{l.name}{l.phone && <span className="text-ink-soft font-normal"> · {l.phone}</span>}</p>
                  <CategoryBadge category={l.category} />
                </div>
                <p className="text-ink-soft">{l.intent}</p>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function CategoryBadge({ category }: { category: LeadItem["category"] }) {
  const config = {
    lead: { label: "Interested", color: "text-teal-deep bg-teal-deep/10" },
    message: { label: "Message", color: "text-brass bg-brass/10" },
    escalation: { label: "Needs follow-up", color: "text-danger bg-danger/10" },
  }[category];
  return <span className={`text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded-full ${config.color}`}>{config.label}</span>;
}

function BellMark() {
  return (
    <svg width="24" height="24" viewBox="0 0 28 28" fill="none">
      <path d="M14 4C9.6 4 6 7.6 6 12v4l-2 4h20l-2-4v-4c0-4.4-3.6-8-8-8z" stroke="#E9D3AC" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M11 21a3 3 0 0 0 6 0" stroke="#E9D3AC" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
