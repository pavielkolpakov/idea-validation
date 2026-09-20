"use client";
import { ArrowClockwise, WarningCircle } from "@phosphor-icons/react";
import type { ReportStatus } from "@/lib/api";
export const statusLabels: Record<ReportStatus, string> = {
  queued: "Queued",
  running: "Researching",
  succeeded: "Completed",
  failed: "Failed",
};
export function Status({ status }: { status: ReportStatus }) {
  return (
    <span className={`status ${status}`}>
      <span />
      {statusLabels[status]}
    </span>
  );
}
export function ErrorNotice({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="notice error" role="alert">
      <WarningCircle size={20} />
      <div>{message}</div>
      {retry && (
        <button type="button" className="text-button" onClick={retry}>
          <ArrowClockwise size={16} />
          Retry
        </button>
      )}
    </div>
  );
}
export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="loading" role="status" aria-label={label}>
      <div className="skeleton" />
      <div className="skeleton" />
      <div className="skeleton" />
      <span className="sr-only">{label}</span>
    </div>
  );
}
export function dateLabel(date: string) {
  return new Date(date).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
