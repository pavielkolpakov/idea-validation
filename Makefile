.PHONY: up down logs migrate revision api web backfill test test-live types fmt reset

up:
	docker compose up -d
	@echo "waiting for postgres..."
	@until docker compose exec -T db pg_isready -U ideacheck -d ideacheck >/dev/null 2>&1; do sleep 1; done
	@echo "postgres ready on :5433"

down:
	docker compose down

reset:
	docker compose down -v
	$(MAKE) up
	$(MAKE) migrate

logs:
	docker compose logs -f db

migrate:
	cd api && uv run alembic upgrade head

# usage: make revision m="add foo"
revision:
	cd api && uv run alembic revision --autogenerate -m "$(m)"

api:
	cd api && uv run uvicorn app.main:app --reload --port 8000

web:
	cd web && npm run dev

# Backfill corpus embeddings/entities for reports written before Phase 3.
backfill:
	cd api && uv run python -m app.scripts.backfill

# Regenerate the OpenAPI spec and the frontend types from it. Both outputs are
# committed: Vercel's build cannot reach the API to generate them, and a spec
# diff is the most readable review signal that an API contract moved.
types:
	cd api && uv run python -m app.scripts.dump_openapi
	cd web && npx openapi-typescript ../api/openapi.json -o lib/api.gen.ts

test:
	cd api && uv run pytest -q -m "not live"

# Hits the real Perplexity + Anthropic APIs and costs money. This is what
# verifies the citation shape the fakes only assume — run before shipping.
test-live:
	cd api && uv run pytest -q -m live -s

fmt:
	cd api && uv run ruff check --fix . && uv run ruff format .
