# Landing Optimizer — infra convenience targets.
# Requires Docker + Docker Compose. On Windows use Git Bash or WSL, or run the
# underlying `docker compose` commands directly.

COMPOSE = docker compose -f docker/docker-compose.yml
COMPOSE_WATCH = docker compose -f docker/docker-compose.yml -f docker/docker-compose.watch.yml

.PHONY: up watch down logs ps build migrate seed clean env

env: ## Create docker/.env file from .env.example if it doesn't exist yet
	@test -f docker/.env || (cp docker/.env.example docker/.env && echo "Created docker/.env from .env.example. Please edit it to set your secrets.")

up: env ## Start the full local stack
	$(COMPOSE) up -d

watch: env ## Start API, AI, and dashboard with live source sync/reload
	$(COMPOSE_WATCH) up --build --watch

down: ## Stop the stack
	$(COMPOSE) down

logs: ## Tail logs
	$(COMPOSE) logs -f --tail=100

ps: ## Show running services
	$(COMPOSE) ps

build: ## Rebuild service images
	$(COMPOSE) build

migrate: env ## Run Postgres + ClickHouse migrations in the build-stage tool image
	$(COMPOSE) run --rm --build migrate

seed: ## Seed a demo tenant + site via the API
	node scripts/seed.mjs

clean: ## Stop and remove volumes (DESTROYS local data)
	$(COMPOSE) down -v
