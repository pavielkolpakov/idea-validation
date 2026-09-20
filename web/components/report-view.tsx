"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Binoculars,
  Check,
  CheckCircle,
  Copy,
  DownloadSimple,
  GlobeHemisphereWest,
  LinkSimple,
  WarningCircle,
} from "@phosphor-icons/react";
import {
  errorMessage,
  getReport,
  safeUrl,
  TERMINAL,
  type Report,
  type ReportBody,
} from "@/lib/api";
import { useHistory } from "./providers";
import { dateLabel, ErrorNotice, Loading, Status } from "./ui";
const dimensions = [
  {
    key: "market_size",
    label: "Market size",
    description: "How large and reachable is the opportunity?",
    weight: "25%",
  },
  {
    key: "novelty",
    label: "Novelty",
    description: "How original is the approach?",
    weight: "20%",
  },
  {
    key: "competitive_headroom",
    label: "Competitive headroom",
    description: "How much room is there to stand out?",
    weight: "20%",
  },
  {
    key: "feasibility",
    label: "Feasibility",
    description: "Can a small team realistically build it?",
    weight: "20%",
  },
  {
    key: "timing",
    label: "Timing",
    description: "Does the moment favor this idea?",
    weight: "15%",
  },
] as const;
function Sources({
  indices,
  citations,
}: {
  indices: number[];
  citations: string[];
}) {
  return (
    <span className="inline-citations">
      {[...new Set(indices)]
        .filter((i) => citations[i] !== undefined)
        .map((i) => (
          <a href={`#source-${i}`} key={i} aria-label={`Read source ${i + 1}`}>
            {i + 1}
          </a>
        ))}
    </span>
  );
}
function CitedList({
  entries,
  citations,
}: {
  entries: NonNullable<ReportBody["risks"]>;
  citations: string[];
}) {
  return entries.length ? (
    <ol className="findings-list">
      {entries.map((item, i) => (
        <li key={i}>
          <span className="finding-number">
            {String(i + 1).padStart(2, "0")}
          </span>
          <p>
            {item.text}
            <Sources indices={item.sources ?? []} citations={citations} />
          </p>
        </li>
      ))}
    </ol>
  ) : (
    <p className="muted section-empty">
      No findings were included in this report.
    </p>
  );
}
export function ReportView({ slug }: { slug: string }) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [copied, setCopied] = useState(false);
  const [shareError, setShareError] = useState("");
  const { reports, refresh } = useHistory();
  const idea = reports.find((r) => r.public_slug === slug)?.idea;
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      setError("");
      try {
        const data = await getReport(slug, controller.signal);
        if (controller.signal.aborted) return;
        setReport(data);
        if (!TERMINAL.includes(data.status)) timer = setTimeout(poll, 1500);
        else refresh();
      } catch (e) {
        if (!controller.signal.aborted) setError(errorMessage(e));
      }
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [slug, retry, refresh]);
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 2500);
    return () => clearTimeout(timer);
  }, [copied]);
  async function copy() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setShareError("");
    } catch {
      setShareError(
        "Couldn’t copy the link. Copy this page’s address from your browser to share it.",
      );
    }
  }
  function download() {
    if (!report) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `ideacheck-${slug}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    // Keep the blob alive until the browser has started consuming the download.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const body = report?.report;
  const citations = body?.citations ?? [];
  const pending = report && !TERMINAL.includes(report.status);
  const completedResearch = Number(
    report?.step?.match(/\((\d+)\/4\)/)?.[1] ?? 0,
  );
  const judging =
    report?.step?.includes("judg") || report?.step?.includes("synthes");
  return (
    <>
      <Link className="back-link" href="/reports">
        <ArrowLeft size={16} />
        All reports
      </Link>
      <div className="page-title report-title">
        <div>
          <span className="eyebrow">THE EVIDENCE BEHIND YOUR IDEA</span>
          <h1>Validation report</h1>
          {idea && <p className="report-idea">{idea}</p>}
          <div className="report-meta">
            {report && (
              <>
                <Status status={report.status} />
                <span>{dateLabel(report.created_at)}</span>
              </>
            )}
          </div>
        </div>
        <div className="inline-actions">
          <button className="button secondary" onClick={() => void copy()}>
            {copied ? <Check size={17} /> : <Copy size={17} />}
            {copied ? "Link copied" : "Share report"}
          </button>
          {body && (
            <button
              className="icon-button bordered"
              aria-label="Download report as JSON"
              title="Download report as JSON"
              onClick={download}
            >
              <DownloadSimple size={20} />
            </button>
          )}
        </div>
      </div>
      <p className="sharing-note">
        <LinkSimple size={14} />
        Anyone with this report’s link can view it.
      </p>
      {shareError && <ErrorNotice message={shareError} />}
      {error && (
        <ErrorNotice message={error} retry={() => setRetry((n) => n + 1)} />
      )}
      {!report && !error && <Loading label="Loading validation report" />}
      {pending && (
        <section className="panel progress-panel" aria-live="polite">
          <span className="progress-icon">
            <Binoculars size={38} weight="light" />
          </span>
          <span className="eyebrow">A CLOSER LOOK IS UNDERWAY</span>
          <h2>
            {report.status === "queued"
              ? "Your idea is in the queue."
              : judging
                ? "Connecting the dots."
                : "Following the evidence."}
          </h2>
          <p>
            {report.status === "queued"
              ? "Research will begin when a slot is available."
              : "We’re exploring your market, competitors, and opportunities."}
            <br />
            You can leave this page and return to your report later.
          </p>
          <div className="progress-stages">
            <div className="done">
              <CheckCircle size={21} />
              <span>Idea received</span>
            </div>
            <div
              className={
                judging ? "done" : report.status === "running" ? "current" : ""
              }
            >
              <GlobeHemisphereWest size={21} />
              <span>
                Research{" "}
                {report.status === "running" && !judging
                  ? `${completedResearch}/4`
                  : ""}
              </span>
            </div>
            <div className={judging ? "current" : ""}>
              <CheckCircle size={21} />
              <span>Assessment</span>
            </div>
          </div>
          {report.step && (
            <span className="progress-detail">Current step: {report.step}</span>
          )}
        </section>
      )}
      {report?.status === "failed" && (
        <section className="panel empty-state">
          <WarningCircle size={40} />
          <h2>This research didn’t finish.</h2>
          <p>
            We couldn’t complete the report. You can return to your idea and try
            another run.
          </p>
          {report.error && (
            <details className="failure-details">
              <summary>View error details</summary>
              <p>{report.error}</p>
            </details>
          )}
          <Link className="button primary" href="/">
            Start a new validation <ArrowRight size={17} />
          </Link>
        </section>
      )}
      {report?.status === "succeeded" && !body && (
        <ErrorNotice
          message="This report finished, but its research content is unavailable."
          retry={() => setRetry((n) => n + 1)}
        />
      )}
      {report?.status === "succeeded" && body && (
        <>
          {!!body.degraded_agents?.length && (
            <div className="notice" role="status">
              <WarningCircle size={21} />
              <div>
                <strong>A partial view of the evidence</strong>
                <p>
                  Some research could not be completed:{" "}
                  {body.degraded_agents.join(", ")}. Treat this assessment as
                  provisional.
                </p>
              </div>
            </div>
          )}
          <div className="verdict-grid">
            <section className="score-panel">
              <span className="eyebrow">OVERALL ASSESSMENT</span>
              <div className="big-score">
                {report.score ?? "–"}
                <span>/100</span>
              </div>
              <span className="score-caption">Evidence, weighed together.</span>
              <p>
                A weighted assessment across five dimensions. Higher scores
                indicate stronger potential.
              </p>
            </section>
            <section className="panel verdict-panel">
              <div className="heading-with-icon">
                <Binoculars size={23} />
                <h2>The verdict</h2>
              </div>
              <p>{body.verdict || "No written verdict was included."}</p>
              <span className="verdict-footer">
                A starting point for your own due diligence.
              </span>
            </section>
          </div>
          <section className="panel report-section">
            <div className="section-heading">
              <h2>Breaking down the opportunity</h2>
              <span className="muted">Higher is stronger</span>
            </div>
            <div className="dimension-grid">
              {dimensions.map(({ key, label, description, weight }) => (
                <div className="dimension" key={key}>
                  <h3>{label}</h3>
                  <div className="dimension-score">
                    {body.subscores?.[key] ?? 0}
                    <small>/100</small>
                  </div>
                  <p>{description}</p>
                  <span>{weight} of overall score</span>
                </div>
              ))}
            </div>
          </section>
          <section className="panel report-section">
            <div className="section-heading">
              <h2>The competitive landscape</h2>
              <span className="subtle-tag">
                {body.competitors?.length ?? 0} companies
              </span>
            </div>
            {body.competitors?.length ? (
              <div className="competitor-list">
                {body.competitors.map((competitor, index) => {
                  const url = competitor.domain
                    ? safeUrl(
                        competitor.domain.includes("://")
                          ? competitor.domain
                          : `https://${competitor.domain}`,
                      )
                    : null;
                  return (
                    <article
                      className="competitor"
                      key={`${competitor.name}-${index}`}
                    >
                      <div className="company-initial">
                        {competitor.name.slice(0, 1).toUpperCase() || "?"}
                      </div>
                      <div>
                        <h3>
                          {url ? (
                            <a
                              href={url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {competitor.name}
                              <ArrowUpRight size={16} />
                            </a>
                          ) : (
                            competitor.name
                          )}
                        </h3>
                        <p>
                          {competitor.what_they_do}
                          <Sources
                            indices={competitor.sources ?? []}
                            citations={citations}
                          />
                        </p>
                        {competitor.funding_stage && (
                          <p className="funding-note">
                            {competitor.funding_stage}
                          </p>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <p className="muted section-empty">
                No competitors were identified in this report.
              </p>
            )}
          </section>
          <div className="findings-grid">
            <section className="panel report-section">
              <div className="section-heading">
                <h2>What to watch out for</h2>
                <WarningCircle size={22} />
              </div>
              <CitedList entries={body.risks ?? []} citations={citations} />
            </section>
            <section className="panel report-section differentiation">
              <div className="section-heading">
                <h2>Where you could stand out</h2>
                <ArrowUpRight size={22} />
              </div>
              <CitedList
                entries={body.differentiation ?? []}
                citations={citations}
              />
            </section>
          </div>
          <section className="panel report-section sources-section">
            <div className="section-heading">
              <h2>Follow the sources</h2>
              <span className="subtle-tag">{citations.length} references</span>
            </div>
            <p className="muted">
              Explore the evidence behind this assessment.
            </p>
            {citations.length ? (
              <ol className="sources-list">
                {citations.map((citation, i) => {
                  const url = safeUrl(citation);
                  return (
                    <li id={`source-${i}`} key={`${citation}-${i}`}>
                      <span>{String(i + 1).padStart(2, "0")}</span>
                      {url ? (
                        <a href={url} target="_blank" rel="noopener noreferrer">
                          <span>{citation}</span>
                          <ArrowUpRight size={17} />
                        </a>
                      ) : (
                        <span>{citation}</span>
                      )}
                    </li>
                  );
                })}
              </ol>
            ) : (
              <p className="section-empty muted">
                No sources were attached to this report.
              </p>
            )}
          </section>
        </>
      )}
    </>
  );
}
