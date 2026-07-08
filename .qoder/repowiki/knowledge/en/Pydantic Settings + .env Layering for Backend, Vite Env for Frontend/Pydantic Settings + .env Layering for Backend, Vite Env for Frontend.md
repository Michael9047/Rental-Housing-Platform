---
kind: configuration_system
name: Pydantic Settings + .env Layering for Backend, Vite Env for Frontend
category: configuration_system
scope:
    - '**'
source_files:
    - backend/app/core/config.py
    - backend/.env.example
    - backend/.env
    - backend/app/main.py
    - backend/alembic/env.py
    - backend/alembic.ini
    - docker-compose.yml
    - docker-compose.prod.yml
    - frontend/.env
---

The monorepo uses a two-tier configuration system: the FastAPI backend relies on `pydantic-settings` with `.env` file loading and environment-variable overrides, while the Vue frontend consumes Vite's `VITE_*` env variables. Docker Compose composes both layers at runtime.

### Backend configuration (FastAPI)
- **Single source of truth**: `backend/app/core/config.py` defines one `Settings(BaseSettings)` class that declares every runtime parameter as a typed field with defaults and `validation_alias="ENV_VAR_NAME"`. A module-level `@lru_cache` wrapper `get_settings()` returns a singleton instance so settings are loaded once per process.
- **File precedence**: `model_config = SettingsConfigDict(env_file=".env", ...)` makes the local `backend/.env` the first loader; any matching OS environment variable then shadows it. The example template lives in `backend/.env.example`.
- **Consumption pattern**: Any module that needs config imports `from app.core.config import get_settings` and calls `get_settings()` — this is used across `main.py`, `db/session.py`, `core/security.py`, `core/logging.py`, `celery_app.py`, Alembic `env.py`, and many route/service files.
- **Environment-driven behavior**: `main.py` reads `settings.environment` to relax CORS (`["*"]` in dev) vs. lock it down (production list), and toggles `debug`/logging accordingly.
- **Secrets & third-party keys**: Auth JWT key, OpenAI/DeepSeek API keys, WeChat AppID/Secret, Alibaba SMS credentials, SMTP credentials, and AMap keys are all declared as string fields with empty-string defaults — they must be supplied via `.env` or container env.
- **Alembic**: `alembic.ini` has a hardcoded default URL but `alembic/env.py` re-imports `get_settings()` and builds the SQLAlchemy URL from `settings.database_url`, so migrations follow the same env layering.

### Docker / deployment configuration
- **Development**: `docker-compose.yml` runs PostgreSQL (pgvector) and Redis locally; service env vars use `${VAR:-default}` substitution so `backend/.env` values can be overridden by compose env.
- **Production**: `docker-compose.prod.yml` references a top-level `.env.prod` via `env_file:` and injects service-specific overrides (e.g. `DATABASE_URL` pointing at the `postgres` container hostname). It also sets `ENVIRONMENT=production` and `DEBUG=false` at the container level.
- **Network isolation**: Three networks (`frontend`, `backend`, `data`) separate Nginx, the FastAPI/Celery stack, and persistent data stores.

### Frontend configuration (Vue 3 + Vite)
- **Build-time only**: `frontend/.env` holds `VITE_AMAP_KEY`; Vite exposes these as `import.meta.env.VITE_*` at build time. There is no runtime config loader in the SPA — the backend serves the AMap JS key through an API endpoint when needed.
- **Nginx reverse proxy** in `frontend/nginx/nginx.conf` proxies `/api/v1/*` to the backend container, keeping the frontend and backend URLs unified behind port 80.

### Conventions developers should follow
1. **Add new settings in one place**: declare them as fields on `app.core.config.Settings` with a `validation_alias` matching the uppercase env var name; provide a sensible default.
2. **Never hard-code secrets**: if a value is secret (keys, passwords), leave the default empty and require it via `.env` / container env.
3. **Use `get_settings()` everywhere**: import the cached accessor rather than instantiating `Settings()` directly, ensuring a single load per process.
4. **Keep `.env` out of version control**: commit `*.example` files only; real `.env` and `.env.prod` are mounted into containers.
5. **Docker env overrides win**: remember that `docker-compose.*.yml` `environment:` entries override both `.env` files and host env vars.