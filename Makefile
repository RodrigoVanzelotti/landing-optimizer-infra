# Landing Optimizer — infra convenience targets.
# Requires Docker + Docker Compose. On Windows use Git Bash or WSL, or run the
# underlying `docker compose` commands directly.

COMPOSE = docker compose -f docker/docker-compose.yml

.PHONY: up down logs ps build migrate seed clean

up: ## Start the full local stack
	$(COMPOSE) up -d

down: ## Stop the stack
	$(COMPOSE) down

logs: ## Tail logs
	$(COMPOSE) logs -f --tail=100

ps: ## Show running services
	$(COMPOSE) ps

build: ## Rebuild service images
	$(COMPOSE) build

migrate: ## Run Postgres + ClickHouse migrations inside the api container
	$(COMPOSE) exec api npx prisma migrate deploy
	$(COMPOSE) exec api npm run clickhouse:migrate

seed: ## Seed a demo tenant + site via the API
	node scripts/seed.mjs

clean: ## Stop and remove volumes (DESTROYS local data)
	$(COMPOSE) down -v
