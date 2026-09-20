"use client";
import Link from "next/link";
import { useState } from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  GitBranch,
  Plant,
  Buildings,
} from "@phosphor-icons/react";
import {
  SeedMotion,
  motionDirections,
  type MotionDirection,
} from "@/components/seed-motion";
const icons = [GitBranch, Plant, Buildings];
export default function MotionDirectionsPage() {
  const [direction, setDirection] = useState<MotionDirection>("engine");
  const selected = motionDirections.find((item) => item.id === direction)!;
  return (
    <div className="motion-review">
      <Link href="/" className="back-link">
        <ArrowLeft size={16} />
        Back to workspace
      </Link>
      <div className="motion-review-heading">
        <span className="eyebrow">IDEACHECK / MOTION DIRECTIONS</span>
        <h1>
          One little seed.
          <br />
          <span>Three ways to tell its story.</span>
        </h1>
        <p>
          Inspired by Monad’s flowing paths and quiet, living diagrams. Made for
          IdeaCheck.
        </p>
      </div>
      <div
        className="direction-tabs"
        role="tablist"
        aria-label="Animation directions"
      >
        {motionDirections.map((item, i) => {
          const Icon = icons[i];
          return (
            <button
              type="button"
              role="tab"
              aria-selected={item.id === direction}
              aria-controls="motion-preview"
              key={item.id}
              id={`tab-${item.id}`}
              onClick={() => setDirection(item.id)}
              onKeyDown={(event) => {
                if (
                  ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)
                ) {
                  event.preventDefault();
                  const next =
                    event.key === "Home"
                      ? 0
                      : event.key === "End"
                        ? 2
                        : (i + (event.key === "ArrowRight" ? 1 : 2)) % 3;
                  setDirection(motionDirections[next].id);
                  document
                    .getElementById(`tab-${motionDirections[next].id}`)
                    ?.focus();
                }
              }}
              tabIndex={item.id === direction ? 0 : -1}
            >
              <span className="direction-number">0{i + 1}</span>
              <Icon size={19} weight="light" />
              {item.name}
            </button>
          );
        })}
      </div>
      <section
        className="motion-review-stage"
        id="motion-preview"
        role="tabpanel"
        aria-labelledby={`tab-${direction}`}
      >
        <div className="direction-intro">
          <div>
            <span className="eyebrow">{selected.name}</span>
            <h2>{selected.subtitle}</h2>
          </div>
          <span className="motion-format">SVG · continuous loop</span>
        </div>
        <SeedMotion key={direction} direction={direction} />
        <div className="direction-footer">
          <p>{selected.description}</p>
          <Link className="button primary" href={`/?motion=${direction}#hero`}>
            Preview in workspace <ArrowUpRight size={17} />
          </Link>
        </div>
      </section>
      <div className="motion-review-note">
        <Plant size={21} weight="light" />
        <p>
          The seed is your idea. The roots are research. What grows next is
          yours to build.
          <br />
          All three directions include pause, replay, and a still composition
          for reduced motion.
        </p>
      </div>
    </div>
  );
}
