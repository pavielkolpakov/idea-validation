"""Write the OpenAPI spec to a file.

Runs without a live server and without a database, so `make types` works on a
cold checkout and in CI. The spec is committed alongside the generated types:
a spec diff is the most readable signal a reviewer gets that an API contract
moved, which a diff of generated TypeScript is not.
"""

import json
import pathlib
import sys

OUT = pathlib.Path(__file__).resolve().parents[2] / "openapi.json"


def main() -> None:
    from app.main import app

    OUT.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
