"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";

type Source = {
  id: string;
  type: string;
  status: string;
  created_at: string;
};

type TabKey = "text" | "file" | "url";

export default function KnowledgeBasePage() {
  const [tab, setTab] = useState<TabKey>("text");
  const [sources, setSources] = useState<Source[]>([]);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [viewingId, setViewingId] = useState<string | null>(null);
  const [viewContent, setViewContent] = useState<{ full_text: string; chunk_count: number } | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  
  // form state
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  const loadSources = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch("http://localhost:8000/console/knowledge-sources", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setSources(await res.json());
    } catch {
      // silent — the page still works without the history list loading
    }
  }, [token]);

  useEffect(() => {
    if (!token) {
      window.location.href = "/login";
      return;
    }
    loadSources();
  }, [token, loadSources]);

  async function viewSource(sourceId: string) {
    if (viewingId === sourceId) {
      // toggle closed if clicking the same one again
      setViewingId(null);
      setViewContent(null);
      return;
    }
    setViewingId(sourceId);
    setViewLoading(true);
    setViewContent(null);
    try {
      const res = await fetch(`http://localhost:8000/console/knowledge-sources/${sourceId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Couldn't load that content.");
      const data = await res.json();
      setViewContent({ full_text: data.full_text, chunk_count: data.chunk_count });
    } catch {
      setViewContent({ full_text: "Couldn't load this content — try again.", chunk_count: 0 });
    } finally {
      setViewLoading(false);
    }
  }

  async function deleteSource(sourceId: string) {
    if (!confirm("Remove this from your knowledge base? Your receptionist will stop using this information right away.")) return;
    setDeletingId(sourceId);
    try {
      const res = await fetch(`http://localhost:8000/console/knowledge-sources/${sourceId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Couldn't remove that — try again.");
      setSources((prev) => prev.filter((s) => s.id !== sourceId));
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Something went wrong." });
    } finally {
      setDeletingId(null);
    }
  }

  async function startEditing(sourceId: string) {
    // reuse the existing view-content fetch so we don't duplicate loading logic
    setEditingId(sourceId);
    setViewingId(null);
    setViewLoading(true);
    setEditText("");
    try {
      const res = await fetch(`http://localhost:8000/console/knowledge-sources/${sourceId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Couldn't load that content.");
      const data = await res.json();
      setEditText(data.full_text);
    } catch {
      setMessage({ type: "error", text: "Couldn't load this content for editing — try again." });
      setEditingId(null);
    } finally {
      setViewLoading(false);
    }
  }

  function cancelEditing() {
    setEditingId(null);
    setEditText("");
  }

  async function saveEdit(sourceId: string) {
    setSavingEdit(true);
    try {
      const res = await fetch(`http://localhost:8000/console/knowledge-sources/${sourceId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ text: editText }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Couldn't save your changes.");
      setMessage({ type: "success", text: "Updated! Your receptionist will use the new version." });
      setEditingId(null);
      setEditText("");
      loadSources(); // refreshes the list — the edited entry now has a new id under the hood
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Something went wrong." });
    } finally {
      setSavingEdit(false);
    }
  }

  async function submitText(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/console/ingest/text", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Something went wrong.");
      setMessage({ type: "success", text: "Added! Your receptionist can now answer from this." });
      setText("");
      loadSources();
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Something went wrong." });
    } finally {
      setLoading(false);
    }
  }

  async function submitUrl(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/console/ingest/url", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ url }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Something went wrong.");
      setMessage({ type: "success", text: "Page added! Your receptionist can now answer from it." });
      setUrl("");
      loadSources();
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Something went wrong." });
    } finally {
      setLoading(false);
    }
  }

  async function submitFile(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setMessage(null);
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("http://localhost:8000/console/ingest/file", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Something went wrong.");
      setMessage({ type: "success", text: "Document added! Your receptionist can now answer from it." });
      setFile(null);
      loadSources();
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Something went wrong." });
    } finally {
      setLoading(false);
    }
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
          <div className="px-3 py-2 rounded-md bg-white/10 text-paper">Knowledge Base</div>
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
      </aside>

      <main className="flex-1 p-10 max-w-3xl">
        <h1 className="font-display text-3xl text-ink mb-1">Knowledge Base</h1>
        <p className="text-ink-soft text-sm mb-8">
          Add anything your receptionist should know — services, hours, policies, FAQs.
        </p>

        <div className="bg-white border border-line rounded-xl overflow-hidden mb-8">
          <div className="flex border-b border-line">
            <TabButton label="Paste text" active={tab === "text"} onClick={() => setTab("text")} />
            <TabButton label="Upload PDF" active={tab === "file"} onClick={() => setTab("file")} />
            <TabButton label="From a webpage" active={tab === "url"} onClick={() => setTab("url")} />
          </div>

          <div className="p-6">
            {tab === "text" && (
              <form onSubmit={submitText} className="space-y-4">
                <textarea
                  required
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="e.g. We are open Monday to Saturday, 9am to 6pm. We offer general consultations, follow-ups, and vaccinations…"
                  rows={6}
                  className={`${inputClass} resize-none`}
                />
                <SubmitButton loading={loading} label="Add to knowledge base" />
              </form>
            )}

            {tab === "file" && (
              <form onSubmit={submitFile} className="space-y-4">
                <label className="block border-2 border-dashed border-line rounded-lg p-8 text-center cursor-pointer hover:border-brass transition-colors">
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    className="hidden"
                  />
                  <p className="text-sm text-ink-soft">
                    {file ? (
                      <span className="text-ink font-medium">{file.name}</span>
                    ) : (
                      <>Click to choose a PDF <span className="text-ink-soft/60">(menus, brochures, service lists…)</span></>
                    )}
                  </p>
                </label>
                <SubmitButton loading={loading} disabled={!file} label="Upload PDF" />
              </form>
            )}

            {tab === "url" && (
              <form onSubmit={submitUrl} className="space-y-4">
                <input
                  type="url"
                  required
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://yourbusiness.com/about"
                  className={inputClass}
                />
                <p className="text-xs text-ink-soft">We&apos;ll read the page and pull out what your receptionist needs.</p>
                <SubmitButton loading={loading} label="Add from webpage" />
              </form>
            )}

            {message && (
              <p
                className={`mt-4 text-sm rounded-md px-3 py-2 border ${
                  message.type === "success"
                    ? "text-teal-deep bg-teal-deep/5 border-teal-deep/20"
                    : "text-danger bg-danger/5 border-danger/20"
                }`}
              >
                {message.text}
              </p>
            )}
          </div>
        </div>

        <h2 className="font-display text-xl text-ink mb-3">What&apos;s been added</h2>
        {sources.length === 0 ? (
          <p className="text-sm text-ink-soft">Nothing added yet — use the form above to get started.</p>
        ) : (
          <div className="bg-white border border-line rounded-xl divide-y divide-line">
            {sources.map((s) => (
              <div key={s.id}>
                <div className="px-5 py-3 flex items-center justify-between text-sm">
                  <span className="capitalize text-ink">{s.type === "url" ? "Webpage" : s.type === "doc" ? "Document" : s.type}</span>
                  <span className="text-ink-soft font-mono text-xs">{new Date(s.created_at).toLocaleDateString()}</span>
                  <StatusBadge status={s.status} />
                  <div className="flex items-center gap-3 ml-4">
                    <button
                      onClick={() => viewSource(s.id)}
                      className="text-teal-deep/70 hover:text-teal-deep text-xs font-medium"
                    >
                      {viewingId === s.id ? "Hide" : "View"}
                    </button>
                    <button
                      onClick={() => startEditing(s.id)}
                      className="text-brass/80 hover:text-brass text-xs font-medium"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => deleteSource(s.id)}
                      disabled={deletingId === s.id}
                      className="text-danger/70 hover:text-danger text-xs font-medium disabled:opacity-40"
                    >
                      {deletingId === s.id ? "Removing…" : "Remove"}
                    </button>
                  </div>
                </div>
                {viewingId === s.id && (
                  <div className="px-5 pb-4 bg-paper/60">
                    {viewLoading ? (
                      <p className="text-xs text-ink-soft py-3">Loading…</p>
                    ) : (
                      <div className="bg-white border border-line rounded-lg p-4 mt-1">
                        <p className="text-xs text-ink-soft mb-2">
                          {viewContent?.chunk_count} chunk{viewContent?.chunk_count !== 1 ? "s" : ""} — this is exactly
                          what your receptionist can answer from:
                        </p>
                        <p className="text-sm text-ink whitespace-pre-wrap leading-relaxed">
                          {viewContent?.full_text}
                        </p>
                      </div>
                    )}
                  </div>
                )}
                {editingId === s.id && (
                  <div className="px-5 pb-4 bg-paper/60">
                    {viewLoading ? (
                      <p className="text-xs text-ink-soft py-3">Loading…</p>
                    ) : (
                      <div className="bg-white border border-line rounded-lg p-4 mt-1 space-y-3">
                        <textarea
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          rows={8}
                          className={`${inputClass} resize-none`}
                        />
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => saveEdit(s.id)}
                            disabled={savingEdit || !editText.trim()}
                            className="bg-brass hover:bg-brass/90 disabled:opacity-50 text-teal-deep font-semibold text-xs px-4 py-2 rounded-md transition-colors"
                          >
                            {savingEdit ? "Saving…" : "Save changes"}
                          </button>
                          <button
                            onClick={cancelEditing}
                            disabled={savingEdit}
                            className="text-ink-soft hover:text-ink text-xs font-medium disabled:opacity-40"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

const inputClass =
  "w-full rounded-md border border-line bg-white px-3 py-2.5 text-sm text-ink placeholder:text-ink-soft/50 focus:outline-none focus:ring-2 focus:ring-brass/40 focus:border-brass transition-shadow";

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

function SubmitButton({ loading, disabled, label }: { loading: boolean; disabled?: boolean; label: string }) {
  return (
    <button
      type="submit"
      disabled={loading || disabled}
      className="bg-brass hover:bg-brass/90 disabled:opacity-50 text-teal-deep font-semibold text-sm px-5 py-2.5 rounded-md transition-colors"
    >
      {loading ? "Adding…" : label}
    </button>
  );
}

function StatusBadge({ status }: { status: string }) {
  const isReady = status === "ready";
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${isReady ? "text-teal-deep" : "text-brass"}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${isReady ? "bg-teal-mid" : "bg-brass"}`} />
      {isReady ? "Ready" : status}
    </span>
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
