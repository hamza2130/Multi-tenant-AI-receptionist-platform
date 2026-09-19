"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

type TenantInfo = {
  tenant_id: string;
  business_name: string;
  api_key: string;
};

// voice_server.py — test calls go straight to it over WebRTC.
const VOICE_API = "http://localhost:8001";

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
            {tab === "chat" ? <ChatPanel apiKey={info.api_key} /> : <CallPanel token={token ?? ""} />}
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

type CallState = "idle" | "connecting" | "live" | "ended" | "error";

const CALL_STATUS: Record<Exclude<CallState, "error">, string> = {
  idle: "Uses your browser's microphone — no phone number or Twilio account needed.",
  connecting: "Connecting to your receptionist…",
  live: "Connected — say something!",
  ended: "Call ended. Anything it booked or noted is in Bookings and Leads & Messages.",
};

// A test call over WebRTC, straight to voice_server.py — the same pipeline
// a real phone caller reaches, minus the phone network.
function CallPanel({ token }: { token: string }) {
  const [state, setState] = useState<CallState>("idle");
  const [error, setError] = useState("");
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const micRef = useRef<MediaStream | null>(null);
  const channelRef = useRef<RTCDataChannel | null>(null);
  const pingRef = useRef<number | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  // Safe to call more than once — hanging up, a dropped connection, and
  // leaving the page can all land here.
  const teardown = useCallback(() => {
    if (pingRef.current !== null) {
      window.clearInterval(pingRef.current);
      pingRef.current = null;
    }
    channelRef.current?.close();
    channelRef.current = null;
    pcRef.current?.close();
    pcRef.current = null;
    micRef.current?.getTracks().forEach((track) => track.stop());
    micRef.current = null;
    if (audioRef.current) audioRef.current.srcObject = null;
  }, []);

  const sendHangup = useCallback(() => {
    if (channelRef.current?.readyState === "open") {
      channelRef.current.send(JSON.stringify({ type: "hangup" }));
    }
  }, []);

  // Leaving the page mid-call hangs up rather than leaving the mic open.
  useEffect(
    () => () => {
      sendHangup();
      teardown();
    },
    [sendHangup, teardown],
  );

  function fail(message: string) {
    teardown();
    setError(message);
    setState("error");
  }

  function endCall() {
    teardown();
    setState("ended");
  }

  async function call() {
    setError("");
    setState("connecting");
    try {
      const mic = await navigator.mediaDevices.getUserMedia({ audio: true });
      micRef.current = mic;

      const pc = new RTCPeerConnection();
      pcRef.current = pc;

      // The voice server reads tracks by position — audio, then video, then
      // screen — so the audio transceiver has to be the first one created.
      pc.addTransceiver(mic.getAudioTracks()[0], { direction: "sendrecv" });

      // The server only sends audio while pings keep arriving (one a second);
      // the same channel carries our "hangup" and its "peerLeft".
      const channel = pc.createDataChannel("chat");
      channelRef.current = channel;
      channel.onopen = () => {
        pingRef.current = window.setInterval(() => {
          if (channel.readyState === "open") channel.send("ping");
        }, 1000);
      };
      channel.onmessage = (event) => {
        if (isPeerLeft(event.data)) endCall();
      };

      pc.ontrack = (event) => {
        if (audioRef.current) {
          audioRef.current.srcObject = event.streams[0] ?? new MediaStream([event.track]);
        }
      };
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "connected") setState("live");
        if (pc.connectionState === "failed") {
          fail("The audio connection dropped. Check the voice server is still running, then call again.");
        }
      };

      await pc.setLocalDescription(await pc.createOffer());
      await iceGatheringComplete(pc);
      const offer = pc.localDescription;
      if (!offer) throw new Error("Your browser couldn't prepare the call. Try again.");

      let res: Response;
      try {
        res = await fetch(`${VOICE_API}/webrtc/offer`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ sdp: offer.sdp, type: offer.type }),
        });
      } catch {
        throw new Error("Can't reach the voice server. Start it with: uvicorn voice_server:app --port 8001");
      }
      if (res.status === 401) throw new Error("Your session has expired. Sign in again to test calls.");
      if (!res.ok) throw new Error(`The voice server couldn't start the call (error ${res.status}).`);

      const answer = await res.json();
      await pc.setRemoteDescription({ sdp: answer.sdp, type: answer.type });
    } catch (err) {
      fail(describeCallError(err));
    }
  }

  function hangup() {
    sendHangup();
    // Give the hangup message a moment to leave before closing the connection.
    // The Hang Up button stays up until then, so a quick re-dial can't be
    // torn down by this timer.
    window.setTimeout(endCall, 250);
  }

  return (
    <div className="p-8 text-center">
      <p className="text-sm text-ink-soft mb-6">Talk to it directly through your microphone.</p>
      {state === "live" ? (
        <button
          onClick={hangup}
          className="bg-danger hover:bg-danger/90 text-paper font-semibold text-sm px-6 py-3 rounded-full transition-colors"
        >
          Hang Up
        </button>
      ) : (
        <button
          onClick={call}
          disabled={state === "connecting"}
          className="bg-teal-deep disabled:opacity-50 hover:bg-teal-mid text-paper font-semibold text-sm px-6 py-3 rounded-full transition-colors"
        >
          {state === "connecting" ? "Connecting…" : "📞 Call Receptionist"}
        </button>
      )}
      <p className={`text-xs mt-4 ${state === "error" ? "text-danger" : "text-ink-soft"}`}>
        {state === "error" ? error : CALL_STATUS[state]}
      </p>
      <audio ref={audioRef} autoPlay />
    </div>
  );
}

// The voice server doesn't take trickled candidates, so the offer has to
// carry all of them. Local candidates arrive almost at once; the timeout
// only stops a slow network adapter from stalling the call.
function iceGatheringComplete(pc: RTCPeerConnection, timeoutMs = 2000): Promise<void> {
  if (pc.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const finish = () => {
      pc.removeEventListener("icegatheringstatechange", check);
      window.clearTimeout(timer);
      resolve();
    };
    const check = () => {
      if (pc.iceGatheringState === "complete") finish();
    };
    const timer = window.setTimeout(finish, timeoutMs);
    pc.addEventListener("icegatheringstatechange", check);
  });
}

// The server sends this when it ends the call itself (e.g. after 5 idle minutes).
function isPeerLeft(data: unknown): boolean {
  if (typeof data !== "string") return false;
  try {
    const message = JSON.parse(data);
    return message?.type === "signalling" && message?.message?.type === "peerLeft";
  } catch {
    return false;
  }
}

function describeCallError(err: unknown): string {
  if (err instanceof DOMException && err.name === "NotAllowedError") {
    return "Microphone access is blocked. Allow it for this site in your browser, then call again.";
  }
  if (err instanceof DOMException && err.name === "NotFoundError") {
    return "No microphone found. Connect one, then call again.";
  }
  return err instanceof Error ? err.message : "The call couldn't start. Try again.";
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
