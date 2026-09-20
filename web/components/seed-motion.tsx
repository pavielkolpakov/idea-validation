"use client";

import { useEffect, useId, useRef, useState, type CSSProperties } from "react";
import {
  ArrowCounterClockwise,
  Buildings,
  ChartLineUp,
  Compass,
  Leaf,
  MagnifyingGlass,
  Pause,
  Plant,
  Play,
  ShieldCheck,
  SquaresFour,
  Storefront,
  type Icon,
} from "@phosphor-icons/react";
import "./seed-motion.css";

export type MotionDirection = "engine" | "roots" | "skyline";
export const motionDirections = [
  {
    id: "engine",
    name: "Growth engine",
    subtitle: "One seed. Many possibilities.",
    description:
      "An idea moves through a living research engine. Evidence travels in; a project, a business, and a company emerge as possible paths forward.",
  },
  {
    id: "roots",
    name: "Roots before growth",
    subtitle: "Strong ideas start below the surface.",
    description:
      "Research spreads into a root system. A seed takes hold, branches open, and different ventures grow from the same foundation.",
  },
  {
    id: "skyline",
    name: "Seed to skyline",
    subtitle: "Something small. Something that lasts.",
    description:
      "A single seed sends out a shoot, then a project, a storefront, and a company rise in sequence. A small ecosystem grows from a well-tested idea.",
  },
] as const;

const evidence: { label: string; icon: Icon }[] = [
  { label: "Market signals", icon: ChartLineUp },
  { label: "Competition", icon: MagnifyingGlass },
  { label: "Past attempts", icon: ShieldCheck },
  { label: "Opportunity", icon: Compass },
];
const ventures: { label: string; icon: Icon }[] = [
  { label: "A project", icon: SquaresFour },
  { label: "A business", icon: Storefront },
  { label: "A company", icon: Buildings },
];

function Seed({
  x,
  y,
  scale = 1,
  fill,
}: {
  x: number;
  y: number;
  scale?: number;
  fill: string;
}) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <ellipse className="seed-shadow" cx="0" cy="21" rx="20" ry="5" />
      <g className="seed-kernel">
        <path
          d="M -15 10 C -31 -8 -8 -32 17 -26 C 27 1 6 27 -15 10 Z"
          fill={fill}
          stroke="#386b48"
          strokeWidth="1"
        />
        <path
          d="M -12 7 Q 2 -2 12 -19"
          fill="none"
          stroke="#d4e7a6"
          strokeWidth="1.3"
          opacity=".8"
        />
      </g>
    </g>
  );
}
function Node({
  x,
  y,
  label,
  icon: Icon,
  width = 150,
  variant = "",
  delay = 0,
}: {
  x: number;
  y: number;
  label: string;
  icon: Icon;
  width?: number;
  variant?: string;
  delay?: number;
}) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <g
        className={`motion-node ${variant}`}
        style={{ "--node-delay": `${delay}s` } as CSSProperties}
      >
        <rect x={-width / 2} y={-21} width={width} height="42" rx="21" />
        <g transform={`translate(${-width / 2 + 15} -9)`}>
          <Icon size={18} weight="light" />
        </g>
        <text x={-width / 2 + 42} y="5">
          {label}
        </text>
      </g>
    </g>
  );
}
function Signal({
  path,
  delay = 0,
  duration = 4,
  id,
}: {
  path: string;
  delay?: number;
  duration?: number;
  id: string;
}) {
  return (
    <g className="moving-signal" opacity="0">
      <circle r="9" fill="#f8fcf6" stroke="#a2cba1" strokeWidth=".8" />
      <circle r="3" fill="#4c8b51" />
      <animate
        attributeName="opacity"
        values="0;1;1;0"
        keyTimes="0;0.08;0.9;1"
        dur={`${duration}s`}
        begin={`${delay}s`}
        repeatCount="indefinite"
      />
      <animateMotion
        id={id}
        dur={`${duration}s`}
        begin={`${delay}s`}
        repeatCount="indefinite"
        path={path}
        calcMode="spline"
        keyTimes="0;1"
        keySplines="0.4 0 0.2 1"
      />
    </g>
  );
}
function Engine({ prefix }: { prefix: string }) {
  const inputs = [
    "M 345 65 C 345 110 450 100 450 167",
    "M 555 65 C 555 110 450 100 450 167",
    "M 345 335 C 345 287 450 298 450 233",
    "M 555 335 C 555 287 450 298 450 233",
  ];
  const outputs = [
    "M 496 200 C 600 200 590 85 702 85",
    "M 496 200 H 702",
    "M 496 200 C 600 200 590 315 702 315",
  ];
  return (
    <>
      <ellipse
        cx="450"
        cy="200"
        rx="150"
        ry="125"
        fill={`url(#${prefix}-glow)`}
      />
      <path className="motion-wire" d="M 150 200 H 404" />
      <path className="motion-current seed-current" d="M 150 200 H 404" />
      {inputs.map((d, i) => (
        <g key={d}>
          <path className="motion-wire" d={d} />
          <Signal
            path={d}
            delay={i * 0.85}
            duration={4.4}
            id={`${prefix}-in-${i}`}
          />
        </g>
      ))}
      {outputs.map((d, i) => (
        <g key={d}>
          <path className="motion-wire" d={d} />
          <path className={`motion-current output-current output-${i}`} d={d} />
          <Signal
            path={d}
            delay={2 + i * 0.9}
            duration={5}
            id={`${prefix}-out-${i}`}
          />
        </g>
      ))}
      <Seed x={130} y={196} scale={1.08} fill={`url(#${prefix}-seed)`} />
      <text className="scene-label" x="130" y="250" textAnchor="middle">
        Your idea
      </text>
      <text className="scene-caption" x="130" y="270" textAnchor="middle">
        A seed of possibility
      </text>
      {evidence.map(({ label, icon }, i) => (
        <Node
          key={label}
          x={i % 2 === 0 ? 345 : 555}
          y={i < 2 ? 45 : 355}
          label={label}
          icon={icon}
          width={164}
        />
      ))}
      <g transform="translate(450 200)">
        <rect
          className="hub-orbit orbit-one"
          x="-61"
          y="-61"
          width="122"
          height="122"
          rx="28"
        />
        <rect
          className="hub-orbit orbit-two"
          x="-47"
          y="-47"
          width="94"
          height="94"
          rx="23"
        />
        <rect
          className="hub-core"
          x="-38"
          y="-38"
          width="76"
          height="76"
          rx="24"
        />
        <g className="hub-plant" transform="translate(-21 -24)">
          <Plant size={42} weight="light" />
        </g>
      </g>
      <text className="hub-label" x="450" y="282" textAnchor="middle">
        ideacheck
      </text>
      {ventures.map(({ label, icon }, i) => (
        <Node
          key={label}
          x={770}
          y={85 + i * 115}
          label={label}
          icon={icon}
          width={145}
          variant="venture-node"
          delay={i * 0.7}
        />
      ))}
      <text className="scene-caption" x="770" y="361" textAnchor="middle">
        Room to grow
      </text>
    </>
  );
}
function Roots({ prefix }: { prefix: string }) {
  const roots = [
    "M 450 242 C 450 294 152 271 152 342",
    "M 450 242 C 450 299 347 281 347 342",
    "M 450 242 C 450 296 552 281 552 342",
    "M 450 242 C 450 294 747 271 747 342",
  ];
  const branches = [
    "M 450 228 C 450 150 238 211 238 105",
    "M 450 228 C 450 190 450 101 450 72",
    "M 450 228 C 450 150 662 211 662 105",
  ];
  return (
    <>
      <ellipse
        cx="450"
        cy="206"
        rx="220"
        ry="145"
        fill={`url(#${prefix}-glow)`}
      />
      <path
        className="ground-line"
        d="M 65 246 C 190 242 277 250 386 245 S 654 247 835 243"
      />
      <text className="scene-caption" x="65" y="229">
        POSSIBILITY
      </text>
      <text className="scene-caption" x="65" y="270">
        EVIDENCE
      </text>
      {roots.map((d, i) => (
        <g key={d}>
          <path className="root-guide" d={d} />
          <path
            className="growing-root"
            d={d}
            pathLength="1"
            style={{ "--grow-delay": `${i * 0.3}s` } as CSSProperties}
          />
          <Signal
            path={d}
            delay={i * 0.6}
            duration={5.5}
            id={`${prefix}-root-${i}`}
          />
        </g>
      ))}
      {branches.map((d, i) => (
        <g key={d}>
          <path className="branch-guide" d={d} />
          <path
            className="growing-branch"
            d={d}
            pathLength="1"
            style={{ "--grow-delay": `${i * 0.4}s` } as CSSProperties}
          />
        </g>
      ))}
      <g
        className="root-leaf leaf-left"
        transform="translate(345 170) rotate(-28)"
      >
        <Leaf size={36} weight="duotone" />
      </g>
      <g
        className="root-leaf leaf-right"
        transform="translate(515 148) rotate(30)"
      >
        <Leaf size={32} weight="duotone" />
      </g>
      <g
        className="root-leaf leaf-top"
        transform="translate(427 108) rotate(-32)"
      >
        <Leaf size={30} weight="duotone" />
      </g>
      <Seed x={450} y={239} scale={0.85} fill={`url(#${prefix}-seed)`} />
      {ventures.map(({ label, icon }, i) => (
        <Node
          key={label}
          x={[238, 450, 662][i]}
          y={[84, 50, 84][i]}
          label={label}
          icon={icon}
          width={150}
          variant={`canopy-node canopy-${i}`}
        />
      ))}
      {evidence.map(({ label, icon }, i) => (
        <Node
          key={label}
          x={[152, 347, 552, 747][i]}
          y={361}
          label={label}
          icon={icon}
          width={166}
          variant="root-node"
        />
      ))}
      <text className="seed-underlabel" x="500" y="250">
        An idea takes root.
      </text>
    </>
  );
}
function Skyline({ prefix }: { prefix: string }) {
  const stems = [
    "M 160 273 C 210 273 230 276 274 276",
    "M 326 276 C 379 276 400 276 451 276",
    "M 536 276 C 585 276 615 276 658 276",
  ];
  return (
    <>
      <ellipse
        cx="500"
        cy="220"
        rx="325"
        ry="155"
        fill={`url(#${prefix}-glow)`}
        opacity=".6"
      />
      <path className="ground-line" d="M 70 282 H 835" />
      <path className="skyline-root" d="M 130 282 C 230 362 660 333 747 282" />
      <path className="skyline-root" d="M 300 282 C 370 338 508 313 508 282" />
      {stems.map((d, i) => (
        <Signal
          key={d}
          path={d}
          delay={i * 2}
          duration={4}
          id={`${prefix}-flow-${i}`}
        />
      ))}
      <Seed x={130} y={263} scale={0.9} fill={`url(#${prefix}-seed)`} />
      <text className="scene-label" x="130" y="324" textAnchor="middle">
        An idea
      </text>
      <g transform="translate(302 277)">
        <g className="skyline-grow grow-project">
          <path className="plant-stem" d="M 0 0 C 0 -22 -3 -36 3 -63" />
          <path
            className="plant-leaf"
            d="M 0 -31 C -34 -28 -44 -54 -42 -63 C -13 -66 2 -51 0 -31"
          />
          <path
            className="plant-leaf light-leaf"
            d="M 1 -51 C 29 -43 41 -66 36 -80 C 11 -79 -1 -66 1 -51"
          />
          <rect
            className="project-sheet"
            x="-38"
            y="-153"
            width="76"
            height="58"
            rx="9"
          />
          <path
            className="sheet-line"
            d="M -21 -135 H 13 M -21 -123 H 23 M -21 -111 H 1"
          />
          <circle cx="29" cy="-145" r="12" fill="#d9ecc9" />
          <g transform="translate(21 -153)">
            <Leaf size={16} />
          </g>
        </g>
      </g>
      <text className="scene-label" x="302" y="324" textAnchor="middle">
        A project
      </text>
      <g transform="translate(508 277)">
        <g className="skyline-grow grow-business">
          <rect
            className="building-face"
            x="-57"
            y="-110"
            width="114"
            height="110"
            rx="3"
          />
          <path
            className="shop-roof"
            d="M -65 -113 L -45 -139 H 45 L 65 -113 Z"
          />
          <path
            className="shop-awning"
            d="M -65 -113 H 65 V -99 Q 52 -84 39 -99 Q 26 -84 13 -99 Q 0 -84 -13 -99 Q -26 -84 -39 -99 Q -52 -84 -65 -99 Z"
          />
          <rect
            className="shop-window"
            x="-42"
            y="-75"
            width="45"
            height="42"
            rx="3"
          />
          <rect
            className="shop-door"
            x="15"
            y="-75"
            width="26"
            height="75"
            rx="3"
          />
          <path
            className="window-reflection"
            d="M -37 -65 L -12 -40 M -30 -68 L -7 -45"
          />
          <g transform="translate(-11 -163)">
            <Leaf size={22} weight="duotone" />
          </g>
        </g>
      </g>
      <text className="scene-label" x="508" y="324" textAnchor="middle">
        A business
      </text>
      <g transform="translate(732 277)">
        <g className="skyline-grow grow-company">
          <path className="tower-side" d="M 8 -207 L 51 -187 V 0 H 8 Z" />
          <rect
            className="tower-face"
            x="-43"
            y="-207"
            width="51"
            height="207"
            rx="3"
          />
          <rect
            className="tower-wing"
            x="-69"
            y="-99"
            width="43"
            height="99"
            rx="3"
          />
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <g key={i}>
              <path
                className="tower-window"
                d={`M -31 ${-189 + i * 27} H -7`}
              />
              <path
                className="tower-side-window"
                d={`M 20 ${-182 + i * 27} L 38 ${-173 + i * 27}`}
              />
            </g>
          ))}
          <path
            className="tower-window"
            d="M -58 -78 H -37 M -58 -55 H -37 M -58 -32 H -37"
          />
          <g transform="translate(-31 -239)">
            <Leaf size={25} weight="duotone" />
          </g>
        </g>
      </g>
      <text className="scene-label" x="732" y="324" textAnchor="middle">
        A company
      </text>
      <g className="skyline-soil">
        <rect x="325" y="355" width="254" height="31" rx="15.5" />
        <g transform="translate(344 363)">
          <Plant size={15} />
        </g>
        <text x="369" y="375">
          Rooted in research. Built by you.
        </text>
      </g>
    </>
  );
}

function MobileScene({
  direction,
  prefix,
}: {
  direction: MotionDirection;
  prefix: string;
}) {
  const botanical = direction === "roots";
  const paths = [65, 195, 325].map((x) =>
    botanical
      ? `M 195 220 C 195 140 ${x} 160 ${x} 83`
      : `M 195 186 C 195 244 ${x} 230 ${x} 271`,
  );
  return (
    <>
      <ellipse
        cx="195"
        cy="185"
        rx="175"
        ry="130"
        fill={`url(#${prefix}-glow)`}
      />
      {paths.map((d, i) => (
        <g key={d}>
          <path className="motion-wire" d={d} />
          <path
            className="motion-current"
            d={d}
            style={{ animationDelay: `${-i}s` }}
          />
          <Signal
            path={d}
            delay={i * 0.9}
            duration={5}
            id={`${prefix}-mobile-${i}`}
          />
        </g>
      ))}
      {!botanical && <path className="motion-wire" d="M 195 76 V 113" />}
      <Seed
        x={195}
        y={botanical ? 235 : 43}
        scale={0.8}
        fill={`url(#${prefix}-seed)`}
      />
      <text
        className="scene-label"
        x="195"
        y={botanical ? 279 : 87}
        textAnchor="middle"
      >
        Your idea
      </text>
      {botanical ? (
        <>
          <path className="ground-line" d="M 32 251 H 358" />
          <path
            className="skyline-root"
            d="M 195 255 C 195 314 83 295 83 330 M 195 255 C 195 314 305 295 305 330"
          />
          <g transform="translate(176 139)">
            <Plant size={38} weight="light" />
          </g>
          <text className="scene-caption" x="195" y="341" textAnchor="middle">
            Strong roots, grounded in research.
          </text>
        </>
      ) : (
        <>
          <rect
            className="hub-orbit orbit-mobile"
            x="146"
            y="102"
            width="98"
            height="96"
            rx="30"
          />
          <rect
            className="hub-core"
            x="158"
            y="114"
            width="74"
            height="72"
            rx="22"
          />
          <g className="hub-plant" transform="translate(174 126)">
            <Plant size={42} weight="light" />
          </g>
          <text className="scene-caption" x="195" y="214" textAnchor="middle">
            Research &amp; validation
          </text>
        </>
      )}
      {ventures.map(({ label, icon }, i) => (
        <Node
          key={label}
          x={[65, 195, 325][i]}
          y={botanical ? 63 : 292}
          label={label.slice(2, 3).toUpperCase() + label.slice(3)}
          icon={icon}
          width={114}
          variant="venture-node"
          delay={i * 0.7}
        />
      ))}
    </>
  );
}

export function SeedMotion({
  direction = "engine",
}: {
  direction?: MotionDirection;
}) {
  const id = useId().replace(/:/g, "");
  const svg = useRef<SVGSVGElement>(null);
  const container = useRef<HTMLElement>(null);
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [visible, setVisible] = useState(true);
  const [replay, setReplay] = useState(0);
  const stopped = paused || reduced || !visible;
  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduced(preference.matches);
    sync();
    const screen = window.matchMedia("(max-width: 700px)");
    const syncScreen = () => setMobile(screen.matches);
    syncScreen();
    screen.addEventListener("change", syncScreen);
    preference.addEventListener("change", sync);
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.08 },
    );
    if (container.current) observer.observe(container.current);
    return () => {
      preference.removeEventListener("change", sync);
      screen.removeEventListener("change", syncScreen);
      observer.disconnect();
    };
  }, []);
  useEffect(() => {
    if (!svg.current) return;
    if (stopped) svg.current.pauseAnimations();
    else svg.current.unpauseAnimations();
  }, [stopped, direction, replay]);
  const selected = motionDirections.find((d) => d.id === direction)!;
  return (
    <figure
      ref={container}
      className={`seed-motion ${stopped ? "motion-paused" : ""} ${reduced ? "motion-reduced" : ""}`}
    >
      <svg
        key={`${direction}-${replay}`}
        ref={svg}
        className={`seed-scene scene-${direction}`}
        viewBox={
          mobile && direction !== "skyline" ? "0 0 390 365" : "0 0 900 405"
        }
        role="img"
        aria-labelledby={`${id}-title ${id}-description`}
      >
        <title
          id={`${id}-title`}
        >{`${selected.name}: an idea grows with evidence`}</title>
        <desc
          id={`${id}-description`}
        >{`${selected.description} An illustration of the validation process, not a live report or a promise of business success.`}</desc>
        <defs>
          <radialGradient id={`${id}-glow`}>
            <stop offset="0%" stopColor="#cbe4a7" stopOpacity=".65" />
            <stop offset="48%" stopColor="#dcecc8" stopOpacity=".35" />
            <stop offset="100%" stopColor="#f8fbf6" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={`${id}-seed`} x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#b9d978" />
            <stop offset=".48" stopColor="#5d934c" />
            <stop offset="1" stopColor="#2d6041" />
          </linearGradient>
        </defs>
        {mobile && direction !== "skyline" ? (
          <MobileScene direction={direction} prefix={id} />
        ) : direction === "engine" ? (
          <Engine prefix={id} />
        ) : direction === "roots" ? (
          <Roots prefix={id} />
        ) : (
          <Skyline prefix={id} />
        )}
      </svg>
      <figcaption className="motion-caption">
        <span>
          {direction === "roots"
            ? "Better roots. Brighter possibilities."
            : direction === "skyline"
              ? "You bring the ambition. We help ground it."
              : "An idea, a little evidence, a world of possibility."}
        </span>
        <div className="motion-controls">
          <button
            type="button"
            onClick={() => setPaused(!paused)}
            disabled={reduced}
            aria-label={paused ? "Play animation" : "Pause animation"}
            title={
              reduced
                ? "Reduced motion is enabled"
                : paused
                  ? "Play animation"
                  : "Pause animation"
            }
          >
            {paused || reduced ? <Play size={13} /> : <Pause size={13} />}
          </button>
          <button
            type="button"
            onClick={() => {
              setPaused(false);
              setReplay((n) => n + 1);
            }}
            disabled={reduced}
            aria-label="Replay animation"
            title="Replay animation"
          >
            <ArrowCounterClockwise size={14} />
          </button>
        </div>
      </figcaption>
    </figure>
  );
}
