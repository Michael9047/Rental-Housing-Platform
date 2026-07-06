---
kind: build_system
name: Docker-Compose Orchestration with Multi-Stage Builds
category: build_system
scope:
    - '**'
source_files:
    - docker-compose.yml
    - docker-compose.prod.yml
    - backend/Dockerfile
    - frontend/Dockerfile
    - backend/requirements.txt
    - frontend/package.json
    - backend/alembic.ini
    - DEPLOYMENT.md
---

The project uses a Docker-first build and deployment system centered on `docker-compose` for both development and production environments, with multi-stage Dockerfiles per service.

**Build & packaging**
- Backend (`backend/Dockerfile`): Python 3.13-slim multi-stage build — builder stage installs C deps (gcc, libpq-dev) and pins `requirements.txt`, runtime stage copies only the installed wheels plus application code under a non-root `appuser`. Gunicorn + Uvicorn workers are the production entrypoint.
- Frontend (`frontend/Dockerfile`): Node 22 Alpine builder runs `npm ci` then `vue-tsc && vite build`; the Nginx 1.27-alpine runtime serves the static `dist/` output via a custom `nginx/nginx.conf` that proxies `/api/v1/*` to the backend container.
- WeChat miniprogram has no build script in this repo; it is developed inside the WeChat DevTools and deployed directly from source.
- Dependency manifests: `backend/requirements.txt` (pinned versions), `frontend/package.json` (Vite 6 + Vue 3 + Vitest).

**Orchestration**
- `docker-compose.yml`: Development-only stack — PostgreSQL 16 with pgvector (auto-installed via `docker/pg-init/00-enable-vector.sql`), Redis 7 with AOF persistence, healthchecks, named volumes. No app containers — developers run FastAPI/Vite locally.
- `docker-compose.prod.yml`: Full production stack — `postgres`, `redis`, `backend` (Gunicorn), `celery-worker` (queues: celery, embedding, import), `celery-beat`, and `nginx` reverse proxy. Three-tier network isolation (`frontend` external, `backend` internal, `data` internal). Resource limits/reservations per service. `.env.prod` supplies secrets.
- `DEPLOYMENT.md` documents one-command deploy, Alembic migration, index creation, Let's Encrypt SSL, backup/restore, horizontal scaling (`--scale`), and troubleshooting.

**Database migrations**
- Alembic config at `backend/alembic.ini` with versioned migrations under `backend/alembic/versions/`. Production migrations are run via `docker compose exec backend alembic upgrade head`.

**Testing hooks**
- Backend: `pytest.ini` drives `pytest` against an isolated test DB; tests live in `backend/tests/`.
- Frontend: Vitest configured in `frontend/vitest.config.ts`, scripts exposed as `npm test` / `test:watch` / `test:coverage`.

**CI/CD**
- No GitHub Actions workflows were found under `.github/workflows/`; builds and deployments are intended to be triggered manually or by an external orchestrator using the Compose files.

**Conventions**
- Every service ships its own `Dockerfile` and is orchestrated exclusively through Compose — no ad-hoc `Makefile` or shell wrappers.
- Secrets flow via `env_file` (`.env.prod`) rather than inline environment variables.
- Health checks are declared in every Dockerfile so Compose `depends_on` can gate on `service_healthy`.