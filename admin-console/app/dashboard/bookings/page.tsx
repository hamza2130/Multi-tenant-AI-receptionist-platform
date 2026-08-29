"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type BookingItem = { id: string; datetime: string; name: string; phone: string };

export default function BookingsPage() {
  const [bookings, setBookings] = useState<BookingItem[] | null>(null);
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  useEffect(() => {
  if (!token) {
    window.location.href = "/login";
    return;
  }

  fetch("http://localhost:8000/console/bookings", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
    .then((res) => {
      if (res.status === 401) {
        localStorage.removeItem("access_token");
        window.location.href = "/login";
        return null;
      }

      if (!res.ok) {
        throw new Error(`Request failed: ${res.status}`);
      }

      return res.json();
    })
    .then((data) => {
      if (data) {
        setBookings(data);
      }
    })
    .catch(() => setBookings([]));
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
          <div className="px-3 py-2 rounded-md bg-white/10 text-paper">Bookings</div>
          <Link href="/dashboard/leads" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">Leads & Messages</Link>
          <Link href="/dashboard/settings" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">Settings</Link>
          <Link href="/dashboard/publish" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">
            Publish
          </Link>
        </nav>
      </aside>

      <main className="flex-1 p-10 max-w-2xl">
        <h1 className="font-display text-3xl text-ink mb-1">Bookings</h1>
        <p className="text-ink-soft text-sm mb-8">
          Every appointment your receptionist has booked. There&apos;s no calendar sync yet — this is your source of truth for now.
        </p>

        {!bookings ? (
          <p className="text-sm text-ink-soft">Loading…</p>
        ) : bookings.length === 0 ? (
          <p className="text-sm text-ink-soft">No bookings yet — they&apos;ll show up here as your receptionist takes them.</p>
        ) : (
          <div className="bg-white border border-line rounded-xl divide-y divide-line">
            {bookings.map((b) => (
              <div key={b.id} className="px-5 py-4 flex items-center justify-between text-sm">
                <div>
                  <p className="text-ink font-medium">{b.name}</p>
                  <p className="text-ink-soft text-xs">{b.phone || "No phone provided"}</p>
                </div>
                <p className="font-mono text-xs text-ink-soft">
                  {new Date(b.datetime).toLocaleString(undefined, {
                    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
                  })}
                </p>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function BellMark() {
  return (
    <svg width="24" height="24" viewBox="0 0 28 28" fill="none">
      <path d="M14 4C9.6 4 6 7.6 6 12v4l-2 4h20l-2-4v-4c0-4.4-3.6-8-8-8z" stroke="#E9D3AC" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M11 21a3 3 0 0 0 6 0" stroke="#E9D3AC" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
