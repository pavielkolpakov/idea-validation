"use client";
import Link from "next/link";
import { useState } from "react";
import {
  ArrowUpRight,
  Files,
  MagnifyingGlass,
  Plus,
} from "@phosphor-icons/react";
import { useHistory } from "@/components/providers";
import { dateLabel, ErrorNotice, Loading, Status } from "@/components/ui";
export default function ReportsPage() {
  const { reports, loading, error, refresh } = useHistory();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const filtered = reports.filter(
    (r) =>
      r.idea.toLowerCase().includes(query.toLowerCase()) &&
      (status === "all" || r.status === status),
  );
  return (
    <>
      <div className="page-title">
        <div>
          <span className="eyebrow">YOUR THINKING, IN ONE PLACE</span>
          <h1>
            My reports<span className="title-count">{reports.length}</span>
          </h1>
          <p>A record of the ideas you’ve put to the test.</p>
        </div>
        <Link className="button primary" href="/">
          <Plus size={18} />
          New validation
        </Link>
      </div>
      <div className="list-toolbar">
        <div className="input-with-icon search-input">
          <MagnifyingGlass size={18} />
          <input
            aria-label="Search your reports"
            placeholder="Find an idea…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <select
          aria-label="Filter reports by status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="all">All statuses</option>
          <option value="succeeded">Completed</option>
          <option value="running">Researching</option>
          <option value="queued">Queued</option>
          <option value="failed">Failed</option>
        </select>
        <button
          className="button secondary"
          onClick={refresh}
          disabled={loading}
        >
          Refresh
        </button>
      </div>
      {loading ? (
        <Loading label="Loading reports" />
      ) : error ? (
        <ErrorNotice message={error} retry={refresh} />
      ) : !filtered.length ? (
        <div className="empty-state panel">
          <Files size={38} weight="light" />
          <h2>
            {reports.length
              ? "No ideas match that search."
              : "Your next idea starts here."}
          </h2>
          <p>
            {reports.length
              ? "Try a different phrase or change the status filter."
              : "Validate an idea and come back here to revisit the research."}
          </p>
          {reports.length ? (
            <button
              className="button secondary"
              onClick={() => {
                setQuery("");
                setStatus("all");
              }}
            >
              Clear filters
            </button>
          ) : (
            <Link className="button primary" href="/">
              Explore an idea <Plus size={16} />
            </Link>
          )}
        </div>
      ) : (
        <div className="panel history-table">
          <div className="history-head">
            <span>Idea</span>
            <span>Status</span>
            <span>Score</span>
            <span>Created</span>
            <span />
          </div>
          {filtered.map((r) => (
            <Link
              className="history-row"
              key={r.public_slug}
              href={`/reports/${r.public_slug}`}
            >
              <h3>{r.idea}</h3>
              <Status status={r.status} />
              <span className="row-score">
                {r.score ?? "–"}
                {r.score != null && <small>/100</small>}
              </span>
              <time dateTime={r.created_at}>{dateLabel(r.created_at)}</time>
              <ArrowUpRight size={18} />
            </Link>
          ))}
        </div>
      )}
      <p className="table-footnote">
        Showing up to the 100 most recent reports in this workspace.
      </p>
    </>
  );
}
