"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  ArrowUpRight,
  ChartBar,
  Check,
  Plant,
  Files,
  Leaf,
  List,
  Plus,
  X,
} from "@phosphor-icons/react";
import { AccountAction, useHistory, useIdentity } from "./providers";
import { ErrorNotice } from "./ui";
const links = [
  { href: "/", label: "New validation", icon: Plus },
  { href: "/reports", label: "My reports", icon: Files },
  { href: "/research", label: "Research library", icon: ChartBar },
];
export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const { name, ready, signedIn } = useIdentity();
  const { reports, claimError, retryClaim } = useHistory();
  const title =
    path === "/"
      ? "New validation"
      : path === "/reports"
        ? "My reports"
        : path === "/research"
          ? "Research library"
          : path === "/design/seed-motion"
            ? "Motion directions"
            : "Validation report";
  const footer = (
    <footer className="page-footer">
      <span>Good ideas deserve good ground.</span>
      <span>
        IdeaCheck <span aria-hidden="true">↗</span>
      </span>
    </footer>
  );
  const brand = (
    <Link href="/" className="brand" onClick={() => setOpen(false)}>
      <span className="brand-mark">
        <Leaf size={25} weight="bold" />
      </span>
      ideacheck<span className="brand-period">.</span>
    </Link>
  );
  // No workspace until there is an account to own it: signed-out visitors get a
  // plain marketing frame, and the sidebar appears only once they sign in.
  if (!ready || !signedIn)
    return (
      <div className="app-shell marketing-shell">
        <div className="main-shell">
          <header className="topbar marketing-topbar">
            {brand}
            <div className="topbar-actions">
              <Link className="text-link" href="/#how-it-works">
                How it works
              </Link>
              <AccountAction className="button primary" label="Sign in" />
            </div>
          </header>
          <main id="main-content" className="content">
            {children}
          </main>
          {footer}
        </div>
      </div>
    );
  return (
    <div className="app-shell">
      {open && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <aside className={`sidebar ${open ? "is-open" : ""}`}>
        {brand}
        <button
          className="mobile-close icon-button"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        >
          <X size={20} />
        </button>
        <div className="workspace-label">
          <span className="workspace-avatar">{name[0]}</span>
          <span>
            {name}
            <small>Member workspace</small>
          </span>
        </div>
        <nav aria-label="Main navigation">
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className={`nav-link ${(href === "/" ? path === href : path.startsWith(href)) ? "active" : ""}`}
            >
              <Icon size={20} />
              {label}
              {href === "/reports" && reports.length > 0 && (
                <span className="nav-count">{reports.length}</span>
              )}
            </Link>
          ))}
        </nav>
        {reports.length > 0 && (
          <div className="sidebar-recent">
            <p>Recent reports</p>
            {reports.slice(0, 4).map((r) => (
              <Link
                onClick={() => setOpen(false)}
                key={r.public_slug}
                href={`/reports/${r.public_slug}`}
              >
                <span className={`recent-dot ${r.status}`} />
                <span>{r.idea}</span>
              </Link>
            ))}
          </div>
        )}
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <Plant size={26} weight="light" />
            <h3>
              Small beginnings.
              <br />
              Real possibilities.
            </h3>
            <p>Give your idea the research it needs to take root.</p>
            <Link href="/#how-it-works" onClick={() => setOpen(false)}>
              How it works <ArrowUpRight size={15} />
            </Link>
          </div>
          <div className="sidebar-footer">
            <span className="mini-mark">
              <Check size={12} weight="bold" />
            </span>
            Good things start with a seed
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="mobile-menu icon-button"
              aria-label="Open navigation"
              onClick={() => setOpen(true)}
            >
              <List size={23} />
            </button>
            <span className="breadcrumb-root">Workspace</span>
            <span className="breadcrumb-root slash">/</span>
            <span>{title}</span>
          </div>
          <div className="topbar-actions">
            <AccountAction />
          </div>
        </header>
        <main id="main-content" className="content">
          {claimError && (
            <ErrorNotice
              message={`Your guest reports haven’t been moved to this account yet. ${claimError}`}
              retry={retryClaim}
            />
          )}
          {children}
        </main>
        {footer}
      </div>
    </div>
  );
}
