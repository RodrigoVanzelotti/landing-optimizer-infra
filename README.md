# Landing Optimizer — Infrastructure & Docs

Cross-cutting home for design docs, local dev stack, edge worker, IaC, and CI.

## Design docs
See [docs/](docs/):
- [PRODUCT_REQUIREMENTS.md](docs/PRODUCT_REQUIREMENTS.md)
- [ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md)
- [EVENT_SCHEMA.md](docs/EVENT_SCHEMA.md)
- [API_CONTRACTS.md](docs/API_CONTRACTS.md)
- [SECURITY.md](docs/SECURITY.md)
- [DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [ROADMAP.md](docs/ROADMAP.md)
- [IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) ← honest, living status

## Local development
Check out all five repos side by side, then:
```bash
cd docker
docker compose up -d           # postgres, clickhouse, redis, redpanda, api, ai, dashboard
# first run: apply migrations
docker compose exec api npx prisma migrate deploy
docker compose exec api npm run clickhouse:migrate
# seed a demo tenant + site
node ../scripts/seed.mjs
```
Dashboard: http://localhost:3000 · API: http://localhost:3001 · AI: http://localhost:8000

> Windows/corporate networks: if `prisma generate` fails TLS, run Node with the
> system trust store: `NODE_OPTIONS=--use-system-ca`.

## Layout
| Path | Purpose |
| --- | --- |
| `docs/` | Product/architecture/security/deployment docs. |
| `docker/` | Local dev Docker Compose stack. |
| `edge/` | Cloudflare Worker for public ingestion + config caching. |
| `terraform/` | IaC skeleton (AWS) for staging/production. |
| `k8s/base/` | Kubernetes manifests (Deployments, Services, HPA, Ingress). |
| `scripts/` | Operational scripts (seed, etc.). |
| `.github/workflows/` | Infra CI (compose/terraform/manifest validation). |

## Deployment
See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for environments, CI/CD, migrations,
blue/green, backups, observability, and rollback strategy.
