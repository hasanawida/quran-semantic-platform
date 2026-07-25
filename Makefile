.PHONY: dev down test api-test web-build

dev:
	docker compose up --build

down:
	docker compose down

test:
	docker compose exec api pytest

api-test:
	cd apps/api && pytest

web-build:
	cd apps/web && npm run build
