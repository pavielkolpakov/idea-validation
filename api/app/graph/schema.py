"""The judge's output contract.

Two things are load-bearing here:

1. **Every subscore is higher-is-better.** `competitive_intensity` was renamed to
   `competitive_headroom` because a weighted mean over a mixed-direction field is
   silently wrong, and a prompt sentence is not strong enough to hold that line.

2. **Citations are integers, not URLs.** The judge sees dossiers annotated with
   `[n]` markers and can only emit indices into a citation table built in code.
   An LLM asked to write URLs writes plausible ones that do not exist — attached
   to specific factual claims about real companies. Here it physically cannot,
   and an out-of-range index fails validation instead of shipping.
"""

from pydantic import BaseModel, Field, model_validator

# Weights for the overall score. The judge does NOT emit an overall score: LLM
# holistic scores drift with prompt wording, cluster in the 60-75 band, and can
# contradict their own subscores with nothing to catch it. A weighted mean makes
# the 0-100 scale comparable across runs, and makes retuning free — historical
# reports can be re-scored from stored subscores without re-running the judge.
SCORE_WEIGHTS: dict[str, float] = {
    "market_size": 0.25,
    "novelty": 0.20,
    "competitive_headroom": 0.20,
    "feasibility": 0.20,
    "timing": 0.15,
}


class Subscores(BaseModel):
    market_size: int = Field(ge=0, le=100, description="How large and reachable the market is.")
    novelty: int = Field(ge=0, le=100, description="How genuinely new the approach is.")
    competitive_headroom: int = Field(
        ge=0,
        le=100,
        description=(
            "How much room is left in the market. HIGH means few or weak "
            "competitors; LOW means crowded and fiercely contested."
        ),
    )
    feasibility: int = Field(ge=0, le=100, description="How buildable this is by a small team.")
    timing: int = Field(ge=0, le=100, description="How well the timing fits current conditions.")

    def weighted_score(self) -> int:
        return round(sum(getattr(self, field) * w for field, w in SCORE_WEIGHTS.items()))


class Competitor(BaseModel):
    name: str
    domain: str | None = Field(default=None, description="Bare domain, e.g. 'example.com'.")
    what_they_do: str
    funding_stage: str | None = None
    sources: list[int] = Field(default_factory=list, description="Citation indices.")


class Risk(BaseModel):
    text: str
    sources: list[int] = Field(default_factory=list)


class DifferentiationAngle(BaseModel):
    text: str
    sources: list[int] = Field(default_factory=list)


class JudgeReport(BaseModel):
    verdict: str = Field(description="A written verdict on whether this idea is worth building.")
    subscores: Subscores
    competitors: list[Competitor] = Field(default_factory=list)
    risks: list[Risk] = Field(min_length=1, max_length=8)
    differentiation: list[DifferentiationAngle] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def _verdict_is_substantive(self) -> JudgeReport:
        # `.with_structured_output` guarantees shape, not substance: a
        # structurally valid report with an empty verdict validates fine and is
        # worthless. Fail loudly rather than shipping it.
        if len(self.verdict.strip()) < 20:
            raise ValueError("verdict is empty or too short to be a real verdict")
        return self

    def all_source_indices(self) -> list[int]:
        indices = [i for c in self.competitors for i in c.sources]
        indices += [i for r in self.risks for i in r.sources]
        indices += [i for d in self.differentiation for i in d.sources]
        return indices


def validate_citation_indices(report: JudgeReport, citation_count: int) -> None:
    """Reject indices that don't resolve to a real citation.

    This is the backstop that makes integer citations safe: a hallucinated index
    fails the run instead of rendering as a broken source link.
    """
    bad = sorted({i for i in report.all_source_indices() if i < 0 or i >= citation_count})
    if bad:
        raise ValueError(
            f"judge cited citation indices {bad}, but only {citation_count} citations exist"
        )
