"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type TenantInfo = {
  tenant_id: string;
  business_name: string;
  api_key: string;
};

const WIDGET_BASE_URL = "http://localhost:5500/widget_combined.html";

export default function PublishPage() {
  const [info, setInfo] = useState<TenantInfo | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  useEffect(() => {
    if (!token) {
      window.location.href = "/login";
      return;
    }
    fetch("http://localhost:8000/auth/me", { headers: { Authorization: "Bearer " + token } })
      .then(function (res) {
        if (!res.ok) throw new Error("Session expired.");
        return res.json();
      })
      .then(function (data) {
        setInfo({ tenant_id: data.tenant_id, business_name: data.business_name, api_key: data.api_key });
      })
      .catch(function (err) {
        setError(err.message);
      });
  }, [token]);

  const embedUrl = info ? WIDGET_BASE_URL + "?api_key=" + info.api_key : "";
  const iframeSnippet = "<iframe\n  src=\"" + embedUrl + "\"\n  width=\"380\"\n  height=\"560\"\n  style=\"border:none; border-radius:16px;\"\n></iframe>";

  function copySnippet() {
    navigator.clipboard.writeText(iframeSnippet);
    setCopied(true);
    setTimeout(function () {
      setCopied(false);
    }, 2000);
  }

  return (
    <div className="flex min-h-screen">
      <aside className="w-64 bg-teal-deep text-paper flex flex-col p-6">
        <div className="flex items-center gap-3 mb-10">
          <BellMark />
          <span className="font-display text-lg">Front Desk</span>
        </div>
        <nav className="flex flex-col gap-1 text-sm">
          <Link href="/dashboard" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">
            Overview
          </Link>
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
            Leads & Messages
          </Link>
          <Link href="/dashboard/settings" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">
            Settings
          </Link>
          <div className="px-3 py-2 rounded-md bg-white/10 text-paper">Publish</div>
        </nav>
      </aside>

      <main className="flex-1 p-10 max-w-2xl">
        <h1 className="font-display text-3xl text-ink mb-1">Publish</h1>
        <p className="text-ink-soft text-sm mb-8">
          Add your receptionist to your website. Copy the snippet below into your site's HTML, anywhere you would like the chat widget to appear.
        </p>

        {error && (
          <p className="text-sm text-danger">
            {error} <a href="/login" className="underline">Sign in</a>
          </p>
        )}
        {!info && !error && <p className="text-sm text-ink-soft">Loading...</p>}

        {info && (
          <div className="space-y-6">
            <div className="bg-white border border-line rounded-xl p-5">
              <p className="text-xs font-medium text-ink-soft uppercase tracking-wide mb-3">Embed code</p>
              <pre className="bg-paper border border-line rounded-md p-4 text-xs text-ink overflow-x-auto whitespace-pre-wrap">
                {iframeSnippet}
              </pre>
              <button
                onClick={copySnippet}
                className="mt-3 bg-brass hover:bg-brass/90 text-teal-deep font-semibold text-sm px-4 py-2 rounded-md transition-colors"
              >
                {copied ? "Copied!" : "Copy snippet"}
              </button>
            </div>

            <div className="bg-white border border-line rounded-xl p-5">
              <p className="text-xs font-medium text-ink-soft uppercase tracking-wide mb-2">Direct link</p>
              <p className="text-sm text-ink-soft mb-2">
                You can also share this link directly, or open it yourself to preview exactly what visitors will see:
              </p>
              
                <a href={embedUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-teal-deep underline break-all"
              >
                {embedUrl}
              </a>
            </div>

            <p className="text-xs text-ink-soft/70">
              This key is unique to {info.business_name}. Keep this page private. Anyone with this link can chat with your receptionist as if they were a website visitor.
            </p>
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