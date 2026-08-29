"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Script from "next/script";

type TenantInfo = {
  tenant_id: string;
  business_name: string;
  api_key: string;
};

declare global {
  interface Window {
    Twilio: any;
  }
}

export default function TestSandboxPage() {
  const [tab, setTab] = useState<"chat" | "call">("chat");
  const [info, setInfo] = useState<TenantInfo | null>(null);
  const [error, setError] = useState("");

  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  useEffect(() => {
    if (!token) {
      window.location.href = "/login";
      return;
    }
    fetch("http://localhost:8000/auth/me", { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => {
        if (!res.ok) throw new Error("Session expired.");
        return res.json();
      })
      .then((data) =>
        setInfo({ tenant_id: data.tenant_id, business_name: data.business_name, api_key: data.api_key })
      )
      .catch((err) => setError(err.message));
  }, [token]);

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
          <div className="px-3 py-2 rounded-md bg-white/10 text-paper">Test Sandbox</div>
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
      </aside>

      <main className="flex-1 p-10">
        <h1 className="font-display text-3xl text-ink mb-1">Test Sandbox</h1>
        <p className="text-ink-soft text-sm mb-8">
          Try out {info ? info.business_name + "'s" : "your"} receptionist — exactly how a real caller or
          website visitor would experience it.
        </p>

        {error && <p className="text-sm text-danger">{error} <a href="/login" className="underline">Sign in</a></p>}
        {!info && !error && <p className="text-sm text-ink-soft">Loading…</p>}

        {info && (
          <div className="bg-white border border-line rounded-xl overflow-hidden max-w-md">
            <div className="flex border-b border-line">
              <TabButton label="💬 Chat" active={tab === "chat"} onClick={() => setTab("chat")} />
              <TabButton label="📞 Call" active={tab === "call"} onClick={() => setTab("call")} />
            </div>
            {tab === "chat" ? <ChatPanel apiKey={info.api_key} /> : <CallPanel tenantId={info.tenant_id} />}
          </div>
        )}
      </main>
    </div>
  );
}

function ChatPanel({ apiKey }: { apiKey: string }) {
  const [messages, setMessages] = useState<{ text: string; sender: "user" | "bot" }[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages]);

  async function send() {
    const text = input.trim();
    if (!text) return;
    setMessages((m) => [...m, { text, sender: "user" }]);
    setInput("");
    try {
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
        body: JSON.stringify({ message: text, conversation_id: conversationId }),
      });
      const data = await res.json();
      setConversationId(data.conversation_id);
      setMessages((m) => [...m, { text: data.answer, sender: "bot" }]);
    } catch {
      setMessages((m) => [...m, { text: "Sorry, something went wrong.", sender: "bot" }]);
    }
  }

  return (
    <div className="p-4">
      <div ref={scrollRef} className="h-72 overflow-y-auto mb-3 space-y-2">
        {messages.length === 0 && (
          <p className="text-sm text-ink-soft/60 text-center mt-16">Ask it something a customer might ask.</p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`text-sm px-3 py-2 rounded-lg max-w-[80%] ${
              m.sender === "user" ? "bg-teal-deep text-paper ml-auto" : "bg-paper text-ink"
            }`}
          >
            {m.text}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Type a message…"
          className="flex-1 rounded-md border border-line px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brass/40"
        />
        <button onClick={send} className="bg-brass hover:bg-brass/90 text-teal-deep font-semibold text-sm px-4 py-2 rounded-md">
          Send
        </button>
      </div>
    </div>
  );
}

function CallPanel({ tenantId }: { tenantId: string }) {
  const [status, setStatus] = useState("Loading…");
  const [connected, setConnected] = useState(false);
  const deviceRef = useRef<any>(null);
  const callRef = useRef<any>(null);
  const [sdkReady, setSdkReady] = useState(false);

  useEffect(() => {
    if (!sdkReady) return;
    (async () => {
      try {
        const res = await fetch("http://localhost:8000/token");
        const data = await res.json();
        const device = new window.Twilio.Device(data.token, { logLevel: 1 });
        device.on("registered", () => setStatus("Ready to call."));
        device.on("error", (err: any) => setStatus("Error: " + err.message));
        await device.register();
        deviceRef.current = device;
      } catch (err) {
        setStatus("Setup failed: " + (err instanceof Error ? err.message : "unknown error"));
      }
    })();
  }, [sdkReady]);

  async function call() {
    setStatus("Calling…");
    // Passing tenant_id as a custom param — this is what lets the sandbox
    // test THIS specific business, instead of always connecting to
    // whichever tenant happens to have a phone number configured.
    const activeCall = await deviceRef.current.connect({ params: { tenant_id: tenantId } });
    callRef.current = activeCall;
    activeCall.on("accept", () => {
      setStatus("Connected — say something!");
      setConnected(true);
    });
    activeCall.on("disconnect", () => {
      setStatus("Call ended.");
      setConnected(false);
    });
  }

  function hangup() {
    callRef.current?.disconnect();
  }

  return (
    <div className="p-8 text-center">
      <Script src="https://cdn.jsdelivr.net/npm/@twilio/voice-sdk@2.18.3/dist/twilio.min.js" onLoad={() => setSdkReady(true)} />
      <p className="text-sm text-ink-soft mb-6">Talk to it directly through your microphone.</p>
      {!connected ? (
        <button
          onClick={call}
          disabled={status !== "Ready to call."}
          className="bg-teal-deep disabled:opacity-50 hover:bg-teal-mid text-paper font-semibold text-sm px-6 py-3 rounded-full transition-colors"
        >
          📞 Call Receptionist
        </button>
      ) : (
        <button
          onClick={hangup}
          className="bg-danger hover:bg-danger/90 text-paper font-semibold text-sm px-6 py-3 rounded-full transition-colors"
        >
          Hang Up
        </button>
      )}
      <p className="text-xs text-ink-soft mt-4">{status}</p>
    </div>
  );
}

function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
        active ? "text-teal-deep border-b-2 border-brass -mb-px" : "text-ink-soft hover:text-ink"
      }`}
    >
      {label}
    </button>
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
