"use client";

/**
 * Phase 1 UI: deliberately unstyled.
 *
 * Its only jobs are to prove the 202-plus-poll contract works from a browser
 * and to surface CORS problems on day one. Report rendering waits for Phase 2,
 * when the judge schema stops changing daily.
 */

import { useEffect, useRef, useState } from "react";
import { createReport, getReport, TERMINAL, type Report } from "@/lib/api";

const POLL_MS = 1500;

export default function Home() {
  const [idea, setIdea] = useState("");
  const [slug, setSlug] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;

    const tick = async () => {
      try {
        const r = await getReport(slug);
        if (cancelled) return;
        setReport(r);
        if (!TERMINAL.includes(r.status)) {
          timer.current = setTimeout(tick, POLL_MS);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    };
    void tick();

    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [slug]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setReport(null);
    setSlug(null);
    setSubmitting(true);
    try {
      const created = await createReport(idea);
      setSlug(created.public_slug);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const pending = report !== null && !TERMINAL.includes(report.status);

  return (
    <main className="mx-auto max-w-3xl p-6 font-mono">
      <h1 className="text-xl font-bold">IdeaCheck — Phase 1</h1>
      <p className="mb-4 text-sm">Stub pipeline. No research is performed yet.</p>

      <form onSubmit={submit} className="mb-4">
        <textarea
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          rows={5}
          className="w-full border p-2"
          placeholder="Describe your idea (min 20 characters)…"
        />
        <button
          type="submit"
          disabled={submitting || idea.trim().length < 20}
          className="mt-2 border px-3 py-1 disabled:opacity-40"
        >
          {submitting ? "submitting…" : "Validate idea"}
        </button>
      </form>

      {error && <pre className="text-red-600">{error}</pre>}

      {slug && (
        <p className="mb-2 text-sm">
          slug: <code>{slug}</code>
          {report && (
            <>
              {" — "}
              <strong>{report.status}</strong>
              {report.step ? ` (${report.step})` : ""}
              {pending ? " …" : ""}
            </>
          )}
        </p>
      )}

      {report && (
        <pre className="overflow-x-auto border bg-zinc-50 p-3 text-xs dark:bg-zinc-900">
          {JSON.stringify(report, null, 2)}
        </pre>
      )}
    </main>
  );
}
