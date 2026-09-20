"use client";
import Link from "next/link";
import { SeedHero } from "@/components/seed-hero";
import { Landing } from "@/components/landing";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Binoculars,
  CheckCircle,
  Clock,
  GlobeHemisphereWest,
  Lightbulb,
  Plant,
  MagnifyingGlass,
  Plus,
  Target,
  TrendUp,
} from "@phosphor-icons/react";
import { ApiError, createReport, errorMessage } from "@/lib/api";
import { AccountAction, useHistory, useIdentity } from "@/components/providers";
import { dateLabel, ErrorNotice, Loading, Status } from "@/components/ui";
const examples = [
  {
    label: "A smarter way to hire",
    idea: "A skills-first hiring platform that helps small businesses find and assess freelance specialists through short paid trial projects instead of resumes.",
    target: "Small business owners hiring their first freelancers",
  },
  {
    label: "Less food waste",
    idea: "A neighborhood marketplace connecting independent bakeries and cafés with nearby residents who can reserve discounted surplus food before closing time.",
    target: "Independent cafés and cost-conscious city residents",
  },
  {
    label: "Tools for independent teams",
    idea: "A lightweight client portal for independent design studios that combines feedback, approvals, and project payments in one shared workspace.",
    target: "Independent design studios with 2–10 people",
  },
];
export default function Home() {
  const router = useRouter();
  const { ready, signedIn, getToken } = useIdentity();
  const { reports, loading, error: historyError, refresh } = useHistory();
  const [idea, setIdea] = useState("");
  const [target, setTarget] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState<unknown>(null);
  const form = useRef<HTMLFormElement>(null);
  const submittingRef = useRef(false);
  useEffect(() => {
    // Restore browser-only state after hydration; sessionStorage is an external store.
    try {
      const draft = JSON.parse(
        sessionStorage.getItem("ideacheck-draft") || "null",
      );
      if (draft) {
        // eslint-disable-next-line react-hooks/set-state-in-effect -- Hydrate from browser-only draft storage.
        setIdea(draft.idea || "");
        setTarget(draft.target || "");
      }
    } catch {
      /* A draft is optional. */
    }
  }, []);
  function saveDraft(nextIdea: string, nextTarget: string) {
    setIdea(nextIdea);
    setTarget(nextTarget);
    setFailure(null);
    try {
      sessionStorage.setItem(
        "ideacheck-draft",
        JSON.stringify({ idea: nextIdea, target: nextTarget }),
      );
    } catch {
      /* Form remains usable when storage is full. */
    }
  }
  async function submit(force = false) {
    if (submittingRef.current || !form.current?.reportValidity()) return;
    submittingRef.current = true;
    setSubmitting(true);
    setFailure(null);
    try {
      const token = await getToken();
      if (signedIn && !token) throw new ApiError(401, null);
      const created = await createReport(idea.trim(), target.trim(), force, {
        token,
      });
      try {
        sessionStorage.removeItem("ideacheck-draft");
      } catch {
        /* Nonessential cleanup. */
      }
      refresh();
      router.push(`/reports/${created.public_slug}`);
    } catch (e) {
      setFailure(e);
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  }
  const reason = failure instanceof ApiError ? failure.reason : null;
  const duplicate = failure instanceof ApiError ? failure.existingSlug : null;
  if (!ready || !signedIn)
    return (
      <>
        <SeedHero />
        <Landing />
      </>
    );
  return (
    <>
      <div className="intro">
        <div className="eyebrow">
          <span className="eyebrow-line" />
          YOUR WORKSPACE
        </div>
        <h1>What are we validating today?</h1>
        <p>Describe the idea and we&rsquo;ll go and research it.</p>
      </div>
      <div className="compose-grid">
        <section className="composer panel" id="idea-composer">
          <div className="section-heading">
            <div className="heading-with-icon">
              <Lightbulb size={23} weight="light" />
              <h2>Plant the seed.</h2>
            </div>
            <span className="subtle-tag">New validation</span>
          </div>
          <form
            ref={form}
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
          >
            <label htmlFor="idea">Your idea</label>
            <textarea
              id="idea"
              minLength={20}
              maxLength={1500}
              required
              rows={5}
              value={idea}
              onChange={(e) => saveDraft(e.target.value, target)}
              placeholder="I’m building a product that helps [who] solve [what], by doing [how]…"
              aria-describedby="idea-help"
            />
            <div className="field-meta" id="idea-help">
              <span>
                A little context goes a long way. Be as specific as you can.
              </span>
              <span>{idea.length.toLocaleString()} / 1,500</span>
            </div>
            <label htmlFor="target">
              Who is it for? <span className="optional">Optional</span>
            </label>
            <div className="input-with-icon">
              <Target size={18} />
              <input
                id="target"
                maxLength={280}
                value={target}
                onChange={(e) => saveDraft(idea, e.target.value)}
                placeholder="e.g. Independent designers running a small studio"
              />
            </div>
            {failure != null && (
              <div className="submission-error">
                {reason === "duplicate" ? (
                  <div className="notice" role="alert">
                    <div>
                      <strong>You’ve explored this idea before.</strong>
                      <p>
                        Open the existing report or use another run to research
                        it again.
                      </p>
                      <div className="inline-actions">
                        {duplicate && (
                          <Link
                            className="button secondary"
                            href={`/reports/${duplicate}`}
                          >
                            View existing report
                          </Link>
                        )}
                        <button
                          type="button"
                          className="text-button"
                          disabled={submitting}
                          onClick={() => void submit(true)}
                        >
                          Research again <ArrowRight size={16} />
                        </button>
                      </div>
                    </div>
                  </div>
                ) : reason === "anon_quota" || reason === "ip_rate" ? (
                  <div className="notice" role="alert">
                    <div>
                      <strong>
                        {reason === "anon_quota"
                          ? "Your guest report is ready to build on."
                          : "Guest research is temporarily limited."}
                      </strong>
                      <p>
                        {reason === "anon_quota"
                          ? "Sign in to keep your report and validate more ideas."
                          : "Too many guest requests came from this network. Sign in or try again later."}
                      </p>
                      <AccountAction label="Sign in to continue" />
                    </div>
                  </div>
                ) : reason === "user_quota" ? (
                  <ErrorNotice message="You’ve used your research allowance for this month. Your existing reports are still available. Come back next month for more." />
                ) : (
                  <ErrorNotice message={errorMessage(failure)} />
                )}
              </div>
            )}
            <div className="form-footer">
              <span>
                <CheckCircle size={16} />
                {signedIn
                  ? "Saved to your workspace"
                  : "One free validation. No card needed."}
              </span>
              <button
                className="button primary"
                disabled={!ready || submitting || idea.trim().length < 20}
                type="submit"
              >
                {submitting ? "Starting research…" : "Validate my idea"}
                <ArrowRight size={18} />
              </button>
            </div>
          </form>
        </section>
        <aside className="research-preview">
          <div className="preview-header">
            <Binoculars size={30} weight="light" />
            <span>GIVE YOUR IDEA GOOD GROUND</span>
          </div>
          <h2>
            Good roots.
            <br />
            Real potential.
          </h2>
          <p>
            A promising idea needs strong roots.
            <br />
            Research helps you find them.
          </p>
          <div className="research-angles">
            <div>
              <GlobeHemisphereWest size={20} />
              <span>The market landscape</span>
            </div>
            <div>
              <MagnifyingGlass size={20} />
              <span>Who’s already building</span>
            </div>
            <div>
              <TrendUp size={20} />
              <span>Risks & opportunities</span>
            </div>
            <div>
              <Target size={20} />
              <span>Your room to stand out</span>
            </div>
          </div>
          <div className="preview-foot">
            <span className="mini-mark">
              <CheckCircle size={16} />
            </span>
            Real sources. A considered verdict.
          </div>
        </aside>
      </div>
      <div className="examples">
        <span>Need a starting point?</span>
        {examples.map((example) => (
          <button
            key={example.label}
            onClick={() => {
              saveDraft(example.idea, example.target);
              document.getElementById("idea")?.focus();
            }}
          >
            <Plus size={14} />
            {example.label}
          </button>
        ))}
      </div>
      <section className="recent-section">
        <div className="section-heading">
          <h2>Pick up where you left off</h2>
          <Link className="text-link" href="/reports">
            All reports <ArrowUpRight size={16} />
          </Link>
        </div>
        {loading ? (
          <Loading label="Loading recent reports" />
        ) : historyError ? (
          <ErrorNotice message={historyError} retry={refresh} />
        ) : reports.length ? (
          <div className="report-list">
            {reports.slice(0, 3).map((r) => (
              <Link
                className="report-row"
                key={r.public_slug}
                href={`/reports/${r.public_slug}`}
              >
                <span className="report-icon">
                  <Lightbulb size={22} />
                </span>
                <div className="report-row-title">
                  <h3>{r.idea}</h3>
                  <span>{dateLabel(r.created_at)}</span>
                </div>
                <Status status={r.status} />
                <span className="row-score">
                  {r.score != null ? (
                    <>
                      {r.score}
                      <small>/100</small>
                    </>
                  ) : (
                    <Clock size={18} />
                  )}
                </span>
                <ArrowUpRight size={19} />
              </Link>
            ))}
          </div>
        ) : (
          <div className="empty-inline">
            <span className="empty-icon">
              <Plant size={26} weight="light" />
            </span>
            <div>
              <h3>Your first seed belongs here.</h3>
              <p>
                Your validation reports will live here. Start with the idea
                above.
              </p>
            </div>
            <span className="empty-line" />
          </div>
        )}
      </section>
    </>
  );
}
