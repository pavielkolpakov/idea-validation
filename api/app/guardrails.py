"""Input guardrails: the pre-check client handle.

Held as a module-level singleton set during lifespan, matching how the graph,
embedder and verifier are wired — the real client constructs eagerly and needs a
provider key, so a setter is what lets the test suite inject a fake.
"""

_precheck = None


def set_precheck(precheck) -> None:
    global _precheck
    _precheck = precheck


def get_precheck():
    if _precheck is None:
        raise RuntimeError("precheck not initialised; app lifespan did not run")
    return _precheck
