"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] as const;
type Day = (typeof DAYS)[number];
type DayHours = { open: string; close: string; closed: boolean };

type Settings = {
  hours: Record<Day, DayHours>;
  services: string[];
  booking_rules: { advance_days: number; min_notice_hours: number; appointment_minutes: number };
  persona: string;
  whatsapp_number: string | null;
  phone_number: string | null;
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [newService, setNewService] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  useEffect(() => {
    if (!token) {
      window.location.href = "/login";
      return;
    }
    fetch("http://localhost:8000/console/settings", { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => res.json())
      .then(setSettings)
      .catch(() => setMessage({ type: "error", text: "Couldn't load your settings." }));
  }, [token]);

  async function save() {
    if (!settings) return;
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch("http://localhost:8000/console/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(settings),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(typeof data.detail === "string" ? data.detail : "Couldn't save — try again.");
      }
      setSettings(await res.json()); // shows the phone number as stored, e.g. "+1 (415)…" becomes "+1415…"
      setMessage({ type: "success", text: "Saved. Your receptionist will use these details from now on." });
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Something went wrong." });
    } finally {
      setSaving(false);
    }
  }

  function updateDay(day: Day, field: keyof DayHours, value: string | boolean) {
    if (!settings) return;
    setSettings({ ...settings, hours: { ...settings.hours, [day]: { ...settings.hours[day], [field]: value } } });
  }

  function addService() {
    const value = newService.trim();
    if (!value || !settings) return;
    setSettings({ ...settings, services: [...settings.services, value] });
    setNewService("");
  }

  function removeService(index: number) {
    if (!settings) return;
    setSettings({ ...settings, services: settings.services.filter((_, i) => i !== index) });
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
            Leads &amp; Messages
          </Link>
          <div className="px-3 py-2 rounded-md bg-white/10 text-paper">Settings</div>
          <Link href="/dashboard/publish" className="px-3 py-2 rounded-md text-paper/60 hover:text-paper transition-colors">
            Publish
          </Link>
        </nav>
      </aside>

      <main className="flex-1 p-10 max-w-2xl">
        <h1 className="font-display text-3xl text-ink mb-1">Settings</h1>
        <p className="text-ink-soft text-sm mb-8">
          Exact details your receptionist relies on — these take priority over anything in your knowledge base.
        </p>

        {!settings ? (
          <p className="text-sm text-ink-soft">Loading…</p>
        ) : (
          <div className="space-y-8">
            {/* Hours */}
            <section className="bg-white border border-line rounded-xl p-6">
              <h2 className="font-display text-xl text-ink mb-4">Hours</h2>
              <div className="space-y-2">
                {DAYS.map((day) => (
                  <div key={day} className="flex items-center gap-3">
                    <span className="w-24 text-sm capitalize text-ink-soft">{day}</span>
                    <label className="flex items-center gap-1.5 text-xs text-ink-soft">
                      <input
                        type="checkbox"
                        checked={!settings.hours[day].closed}
                        onChange={(e) => updateDay(day, "closed", !e.target.checked)}
                      />
                      Open
                    </label>
                    {!settings.hours[day].closed && (
                      <>
                        <input
                          type="time"
                          value={settings.hours[day].open}
                          onChange={(e) => updateDay(day, "open", e.target.value)}
                          className="border border-line rounded px-2 py-1 text-sm"
                        />
                        <span className="text-ink-soft text-xs">to</span>
                        <input
                          type="time"
                          value={settings.hours[day].close}
                          onChange={(e) => updateDay(day, "close", e.target.value)}
                          className="border border-line rounded px-2 py-1 text-sm"
                        />
                      </>
                    )}
                  </div>
                ))}
              </div>
            </section>

            {/* Services */}
            <section className="bg-white border border-line rounded-xl p-6">
              <h2 className="font-display text-xl text-ink mb-4">Services</h2>
              <div className="flex flex-wrap gap-2 mb-3">
                {settings.services.map((s, i) => (
                  <span key={i} className="inline-flex items-center gap-1.5 bg-brass-light/30 text-teal-deep text-sm px-3 py-1 rounded-full">
                    {s}
                    <button onClick={() => removeService(i)} className="text-teal-deep/60 hover:text-teal-deep">×</button>
                  </span>
                ))}
                {settings.services.length === 0 && <p className="text-sm text-ink-soft/60">No services added yet.</p>}
              </div>
              <div className="flex gap-2">
                <input
                  value={newService}
                  onChange={(e) => setNewService(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addService())}
                  placeholder="e.g. Consultation"
                  className="flex-1 border border-line rounded-md px-3 py-2 text-sm"
                />
                <button onClick={addService} className="bg-brass hover:bg-brass/90 text-teal-deep font-semibold text-sm px-4 py-2 rounded-md">
                  Add
                </button>
              </div>
            </section>

            {/* Booking rules */}
            <section className="bg-white border border-line rounded-xl p-6">
              <h2 className="font-display text-xl text-ink mb-4">Booking Rules</h2>
              <div className="space-y-3">
                <label className="flex items-center justify-between">
                  <span className="text-sm text-ink-soft">How far ahead can someone book?</span>
                  <span className="flex items-center gap-2">
                    <input
                      type="number"
                      min={1}
                      value={settings.booking_rules.advance_days}
                      onChange={(e) => setSettings({ ...settings, booking_rules: { ...settings.booking_rules, advance_days: Number(e.target.value) } })}
                      className="w-20 border border-line rounded-md px-2 py-1 text-sm text-right"
                    />
                    <span className="text-sm text-ink-soft">days</span>
                  </span>
                </label>
                <label className="flex items-center justify-between">
                  <span className="text-sm text-ink-soft">Minimum notice before an appointment</span>
                  <span className="flex items-center gap-2">
                    <input
                      type="number"
                      min={0}
                      value={settings.booking_rules.min_notice_hours}
                      onChange={(e) => setSettings({ ...settings, booking_rules: { ...settings.booking_rules, min_notice_hours: Number(e.target.value) } })}
                      className="w-20 border border-line rounded-md px-2 py-1 text-sm text-right"
                    />
                    <span className="text-sm text-ink-soft">hours</span>
                  </span>
                </label>
                <label className="flex items-center justify-between">
                  <span className="text-sm text-ink-soft">
                    How long is one appointment?
                    <span className="block text-xs text-ink-soft/70">Two bookings this close together are treated as a clash.</span>
                  </span>
                  <span className="flex items-center gap-2">
                    <input
                      type="number"
                      min={5}
                      step={5}
                      value={settings.booking_rules.appointment_minutes ?? 30}
                      onChange={(e) => setSettings({ ...settings, booking_rules: { ...settings.booking_rules, appointment_minutes: Number(e.target.value) } })}
                      className="w-20 border border-line rounded-md px-2 py-1 text-sm text-right"
                    />
                    <span className="text-sm text-ink-soft">minutes</span>
                  </span>
                </label>
              </div>
            </section>

                       {/* Persona */}
            <section className="bg-white border border-line rounded-xl p-6">
              <h2 className="font-display text-xl text-ink mb-4">Personality</h2>
              <textarea
                value={settings.persona}
                onChange={(e) => setSettings({ ...settings, persona: e.target.value })}
                rows={3}
                className="w-full border border-line rounded-md px-3 py-2 text-sm resize-none"
                placeholder="e.g. A warm, reassuring receptionist for a family clinic."
              />
            </section>

            {/* Phone number */}
            <section className="bg-white border border-line rounded-xl p-6">
              <h2 className="font-display text-xl text-ink mb-4">Phone Number</h2>
              <p className="text-sm text-ink-soft mb-3">
                The Twilio number your customers call. Your receptionist answers every call to it, using
                everything on this page.
              </p>
              <input
                type="tel"
                value={settings.phone_number ?? ""}
                onChange={(e) => setSettings({ ...settings, phone_number: e.target.value })}
                placeholder="e.g. +14155551234"
                className="w-full border border-line rounded-md px-3 py-2 text-sm"
              />
              <p className="text-xs text-ink-soft/70 mt-1.5">
                Include the + and country code. No number yet? You can still test calls from the Test Sandbox.
              </p>
            </section>

            {/* WhatsApp alerts */}
            <section className="bg-white border border-line rounded-xl p-6">
              <h2 className="font-display text-xl text-ink mb-4">WhatsApp Alerts</h2>
              <p className="text-sm text-ink-soft mb-3">
                Get an instant WhatsApp message whenever your receptionist escalates something to you —
                pricing questions, complaints, or anything it can&apos;t handle itself.
              </p>
              <input
                type="tel"
                value={settings.whatsapp_number ?? ""}
                onChange={(e) => setSettings({ ...settings, whatsapp_number: e.target.value })}
                placeholder="e.g. +923001234567"
                className="w-full border border-line rounded-md px-3 py-2 text-sm"
              />
              <p className="text-xs text-ink-soft/70 mt-1.5">
                Include the country code. Leave blank to turn off WhatsApp alerts.
              </p>
            </section>

            {message && (
              <p className={`text-sm rounded-md px-3 py-2 border ${message.type === "success" ? "text-teal-deep bg-teal-deep/5 border-teal-deep/20" : "text-danger bg-danger/5 border-danger/20"}`}>
                {message.text}
              </p>
            )}

            <button
              onClick={save}
              disabled={saving}
              className="bg-brass hover:bg-brass/90 disabled:opacity-50 text-teal-deep font-semibold text-sm px-6 py-2.5 rounded-md transition-colors"
            >
              {saving ? "Saving…" : "Save Settings"}
            </button>
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
