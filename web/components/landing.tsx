"use client";
import {
  ArrowUpRight,
  CaretDown,
  CheckCircle,
  GlobeHemisphereWest,
  Lightbulb,
  MagnifyingGlass,
  Plant,
  Target,
  TrendUp,
} from "@phosphor-icons/react";
import { AccountAction } from "./providers";

/** Illustrative figures only — these mock the report UI, they are not live data. */
const marketSignals = ["$4.2B market", "18% CAGR", "3 adjacent segments"];
const marketBars = [38, 54, 47, 72, 65, 88];
const competitors = [
  { initial: "D", name: "Design review platform", tag: "Bootstrapped" },
  { initial: "S", name: "Studio project suite", tag: "Series A" },
  { initial: "F", name: "Feedback & approvals", tag: "Seed" },
];
const dimensions = [
  { label: "Market size", score: 78 },
  { label: "Novelty", score: 54 },
  { label: "Headroom", score: 48 },
  { label: "Feasibility", score: 86 },
  { label: "Timing", score: 72 },
];
const sources = ["industry-report.com", "techcrunch.com", "producthunt.com"];
const steps = [
  {
    n: "01",
    icon: Lightbulb,
    title: "Plant your idea",
    body: "Describe what you want to build and who it is for. Two sentences is enough to start.",
  },
  {
    n: "02",
    icon: MagnifyingGlass,
    title: "Put down roots",
    body: "Four researchers work in parallel on the market, the competition, past attempts and the opening.",
  },
  {
    n: "03",
    icon: Plant,
    title: "Choose where to grow",
    body: "Read a scored assessment with every claim traced back to a source you can open yourself.",
  },
];
const faqs = [
  {
    q: "How long does a validation take?",
    a: "About two minutes. Four researchers run in parallel, then a judge weighs what they found into a single scored report.",
  },
  {
    q: "Where does the research come from?",
    a: "Live web research, not a model's memory. Every claim in the report carries a numbered citation you can open and read yourself.",
  },
  {
    q: "What does the score actually mean?",
    a: "It is a weighted read across five dimensions — market size, novelty, competitive headroom, feasibility and timing. It is a starting point for your own diligence, not a verdict.",
  },
  {
    q: "What if my idea is already taken?",
    a: "That is useful to know early, and it is rarely fatal. The report names who is already building and where the room to stand out is.",
  },
];

export function Landing() {
  return (
    <>
      <section className="landing-section" id="what-you-get">
        <div className="landing-head">
          <div className="eyebrow">
            <span className="eyebrow-line" />
            WHAT YOU GET
          </div>
          <h2>Four angles on one idea.</h2>
          <p>
            Every report is researched live, weighed against what already
            exists, and traced back to sources you can open yourself.
          </p>
        </div>
        <div className="feature-grid">
          <article className="feature-card wash-green">
            <div className="feature-art">
              <div className="mock-chips">
                {marketSignals.map((chip) => (
                  <span key={chip}>{chip}</span>
                ))}
              </div>
              <div className="mock-bars" aria-hidden="true">
                {marketBars.map((h, i) => (
                  <span
                    key={i}
                    style={{ "--h": `${h}%`, "--i": i } as React.CSSProperties}
                  />
                ))}
              </div>
            </div>
            <div className="feature-body">
              <GlobeHemisphereWest size={22} weight="light" />
              <h3>The market landscape</h3>
              <p>
                How large the opportunity really is, how fast it is moving, and
                which adjacent segments it touches.
              </p>
            </div>
          </article>

          <article className="feature-card wash-blue">
            <div className="feature-art">
              <div className="mock-rows">
                {competitors.map((c, i) => (
                  <div key={c.name} style={{ "--i": i } as React.CSSProperties}>
                    <span className="mock-initial">{c.initial}</span>
                    <span className="mock-name">{c.name}</span>
                    <span className="mock-tag">{c.tag}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="feature-body">
              <MagnifyingGlass size={22} weight="light" />
              <h3>Who&rsquo;s already building</h3>
              <p>
                The companies working on this today, how they position, and what
                that leaves open for you.
              </p>
            </div>
          </article>

          <article className="feature-card wash-sand">
            <div className="feature-art">
              <div className="mock-score">
                <div className="mock-score-value">
                  68<small>/100</small>
                </div>
                <div className="mock-dimensions">
                  {dimensions.map((d, i) => (
                    <div
                      key={d.label}
                      style={
                        {
                          "--w": `${d.score}%`,
                          "--i": i,
                        } as React.CSSProperties
                      }
                    >
                      <span>{d.label}</span>
                      <span className="mock-track">
                        <span className="mock-fill" />
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="feature-body">
              <TrendUp size={22} weight="light" />
              <h3>A score you can argue with</h3>
              <p>
                Five weighted dimensions, each with the reasoning behind it, so
                you can disagree with the parts you know better.
              </p>
            </div>
          </article>

          <article className="feature-card wash-mint">
            <div className="feature-art">
              <div className="mock-sources">
                {sources.map((src, i) => (
                  <div key={src} style={{ "--i": i } as React.CSSProperties}>
                    <span className="mock-index">0{i + 1}</span>
                    <span className="mock-url">{src}</span>
                    <ArrowUpRight size={14} />
                  </div>
                ))}
              </div>
            </div>
            <div className="feature-body">
              <Target size={22} weight="light" />
              <h3>Sources you can follow</h3>
              <p>
                Nothing is asserted without a citation. Open the evidence and
                judge it for yourself.
              </p>
            </div>
          </article>
        </div>
      </section>

      <section className="landing-section" id="how-it-works">
        <div className="landing-head">
          <div className="eyebrow">
            <span className="eyebrow-line" />
            HOW IT WORKS
          </div>
          <h2>Give your idea room to grow.</h2>
          <p>
            Three steps from a sentence you have been turning over to a report
            you can act on.
          </p>
        </div>
        <ol className="step-grid">
          {steps.map(({ n, icon: Icon, title, body }, i) => (
            <li
              className="step-card"
              key={n}
              style={{ "--i": i } as React.CSSProperties}
            >
              <div className="step-top">
                <span className="step-number">{n}</span>
                <span className="step-icon">
                  <Icon size={20} weight="light" />
                </span>
              </div>
              <h3>{title}</h3>
              <p>{body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="landing-section" id="faq">
        <div className="landing-head">
          <div className="eyebrow">
            <span className="eyebrow-line" />
            QUESTIONS
          </div>
          <h2>Before you start.</h2>
        </div>
        <div className="faq-list">
          {faqs.map(({ q, a }) => (
            <details key={q}>
              <summary>
                {q}
                <CaretDown size={18} />
              </summary>
              <p>{a}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="signin-cta">
        <div className="signin-cta-wash" aria-hidden="true" />
        <div>
          <h2>Ready to plant the seed?</h2>
          <p>Sign in to open your workspace and validate your first idea.</p>
          <div className="signin-cta-note">
            <CheckCircle size={15} />
            Takes about two minutes. No card needed.
          </div>
        </div>
        <AccountAction className="button primary" label="Sign in to start" />
      </section>
    </>
  );
}
