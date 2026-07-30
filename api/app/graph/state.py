import operator
from typing import Annotated

from typing_extensions import TypedDict


class ReportState(TypedDict, total=False):
    """Shared state for a single report run.

    `dossiers` and `degraded_agents` both carry `operator.add`: four research
    nodes write to them concurrently, and without the reducer the last one to
    finish silently overwrites the other three.
    """

    report_id: int
    idea: str
    target_user: str | None

    dossiers: Annotated[list[dict], operator.add]
    degraded_agents: Annotated[list[str], operator.add]

    citations: list[str]
    report: dict
    score: int
