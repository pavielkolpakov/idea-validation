"use client";
import { useEffect, useState } from "react";
import {
  ArrowClockwise,
  Books,
  Database,
  GlobeHemisphereWest,
  Lightbulb,
} from "@phosphor-icons/react";
import {
  errorMessage,
  getCorpusStats,
  getHealth,
  type CorpusStats,
} from "@/lib/api";
import { ErrorNotice, Loading } from "@/components/ui";
const categories = [
  {
    key: "ideas",
    label: "Ideas explored",
    detail: "Ideas submitted for validation.",
    icon: Lightbulb,
  },
  {
    key: "entities",
    label: "Companies discovered",
    detail: "Businesses identified in the research.",
    icon: GlobeHemisphereWest,
  },
  {
    key: "research_chunks",
    label: "Research passages",
    detail: "Evidence collected across research runs.",
    icon: Books,
  },
] as const;
export default function ResearchPage() {
  const [stats, setStats] = useState<CorpusStats | null>(null);
  const [health, setHealth] = useState("checking");
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setError("");
      setHealth("checking");
      const [corpus, service] = await Promise.allSettled([
        getCorpusStats(controller.signal),
        getHealth(controller.signal),
      ]);
      if (controller.signal.aborted) return;
      if (corpus.status === "fulfilled") setStats(corpus.value);
      else setError(errorMessage(corpus.reason));
      setHealth(
        service.status === "fulfilled" && service.value.status === "ok"
          ? "online"
          : "offline",
      );
      setLoading(false);
    }
    void load();
    return () => controller.abort();
  }, [revision]);
  return (
    <>
      <div className="page-title">
        <div>
          <span className="eyebrow">THE RESEARCH BEHIND THE REPORTS</span>
          <h1>
            A growing body
            <br />
            of knowledge.
          </h1>
          <p>A transparent look at the evidence collected across IdeaCheck.</p>
        </div>
        <button
          className="button secondary"
          disabled={loading}
          onClick={() => setRevision((n) => n + 1)}
        >
          <ArrowClockwise size={17} />
          Refresh
        </button>
      </div>
      <div className="library-banner">
        <Database size={34} weight="light" />
        <div>
          <h2>Every exploration leaves something useful.</h2>
          <p>
            Completed reports contribute ideas, companies, and research to the
            library. These are aggregate counts across all workspaces.
          </p>
        </div>
        <span className={`service-status ${health}`}>
          <span />
          {health === "checking"
            ? "Checking service"
            : health === "online"
              ? "Service online"
              : "Service unavailable"}
        </span>
      </div>
      {error && (
        <ErrorNotice message={error} retry={() => setRevision((n) => n + 1)} />
      )}
      {loading ? (
        <Loading label="Loading research statistics" />
      ) : (
        stats && (
          <div className="corpus-grid">
            {categories.map(({ key, label, detail, icon: Icon }) => (
              <section className="panel corpus-card" key={key}>
                <Icon size={25} weight="light" />
                <h2>{label}</h2>
                <strong>{stats[key].total.toLocaleString()}</strong>
                <p>{detail}</p>
                <div className="embedding-count">
                  <span>Indexed for retrieval</span>
                  <b>
                    {stats[key].embedded.toLocaleString()}
                    <small> / {stats[key].total.toLocaleString()}</small>
                  </b>
                </div>
              </section>
            ))}
          </div>
        )
      )}
      <div className="library-explainer">
        <h2>A library in the making.</h2>
        <p>
          This version collects and indexes research as reports finish. Browsing
          individual records and searching the library aren’t available yet.
        </p>
        <p>
          Indexing can finish after a report is ready. A difference between
          collected and indexed counts doesn’t affect your report.
        </p>
      </div>
    </>
  );
}
