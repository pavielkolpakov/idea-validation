"use client";
import { ArrowDownRight, ArrowRight } from "@phosphor-icons/react";
import { AccountAction, useIdentity } from "./providers";
import { SeedMotion } from "./seed-motion";
export function SeedHero() {
  const { ready, signedIn } = useIdentity();
  return (
    <section className="seed-hero" id="hero">
      <div className="seed-hero-wash" aria-hidden="true" />
      <div className="seed-hero-copy">
        <div className="eyebrow">
          <span className="eyebrow-line" />
          YOUR IDEA IS THE SEED
        </div>
        <h1>
          Every big thing
          <br />
          <span>starts small.</span>
        </h1>
        <p>
          Plant your idea. Discover the market, understand the risks, and find
          the space to grow.
        </p>
        <div className="hero-actions">
          {ready && signedIn ? (
            <a className="button primary" href="#idea-composer">
              Validate an idea <ArrowDownRight size={18} />
            </a>
          ) : (
            <AccountAction
              className="button primary"
              label="Start validating"
            />
          )}
          <a className="button secondary" href="#how-it-works">
            See how it works <ArrowRight size={17} />
          </a>
        </div>
      </div>
      <SeedMotion direction="engine" />
    </section>
  );
}
