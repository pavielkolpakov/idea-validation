.PHONY: up down logs migrate revision api web test fmt reset

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

test:
	cd api && uv run pytest -q

fmt:
	cd api && uv run ruff check --fix . && uv run ruff format .
