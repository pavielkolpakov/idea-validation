import operator
from typing import Annotated

from typing_extensions import TypedDict


class ReportState(TypedDict, total=False):
    """Shared state for a single report run.

    `dossiers` carries the `operator.add` reducer from day one even though Phase 1
    has a single node: in Phase 2 four research nodes write to it concurrently, and
    without the reducer the last one to finish silently overwrites the other three.
    """

    report_id: int
    idea: str
    target_user: str | None

    dossiers: Annotated[list[dict], operator.add]
    report: dict
    score: int
