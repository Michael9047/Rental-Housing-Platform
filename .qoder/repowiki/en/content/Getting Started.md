# Getting Started

<cite>
**Referenced Files in This Document**
- [README.md](file://README.md)
- [docker-compose.yml](file://docker-compose.yml)
- [00-enable-vector.sql](file://docker/pg-init/00-enable-vector.sql)
- [backend/requirements.txt](file://backend/requirements.txt)
- [backend/app/core/config.py](file://backend/app/core/config.py)
- [backend/app/main.py](file://backend/app/main.py)
- [backend/alembic.ini](file://backend/alembic.ini)
- [frontend/package.json](file://frontend/package.json)
- [frontend/vite.config.ts](file://frontend/vite.config.ts)
- [wechat-miniprogram/project.config.json](file://wechat-miniprogram/project.config.json)
- [wechat-miniprogram/app.config.js](file://wechat-miniprogram/app.config.js)
- [wechat-miniprogram/utils/api.js](file://wechat-miniprogram/utils/api.js)
</cite>

## Table of Contents
1. Introduction
2. Prerequisites
3. Quick Start with Docker Compose
4. Backend Local Development Setup
5. Frontend Local Development Setup
6. WeChat Mini Program Development Setup
7. Environment Variables Configuration
8. Access URLs and Verification
9. Troubleshooting Guide
10. Conclusion

## Introduction
This guide helps you set up the Rental Housing Structure platform locally for development. It covers prerequisites, a quick start using Docker Compose, backend and frontend setup, WeChat Mini Program configuration, environment variables, verification steps, and troubleshooting tips.

## Prerequisites
Ensure your machine meets these requirements before proceeding:
- Python 3.13+
- Node.js 22+
- Docker & Docker Compose

These are required to run PostgreSQL (with pgvector), Redis, the FastAPI backend, and the Vue 3 + TypeScript frontend.

**Section sources**
- [README.md:66-70](file://README.md#L66-L70)

## Quick Start with Docker Compose
Start the core services (PostgreSQL with pgvector and Redis) using Docker Compose:
- Run: docker compose up -d
- The stack includes:
  - PostgreSQL image with pgvector extension enabled via an init script
  - Redis with persistence and memory policies suitable for development

After starting services, verify they are healthy by checking logs or running health checks defined in the compose file.

**Section sources**
- [README.md:72-76](file://README.md#L72-L76)
- [docker-compose.yml:9-27](file://docker-compose.yml#L9-L27)
- [docker-compose.yml:29-46](file://docker-compose.yml#L29-L46)
- [00-enable-vector.sql:1-3](file://docker/pg-init/00-enable-vector.sql#L1-L3)

## Backend Local Development Setup
Follow these steps to run the backend locally:
1. Create and activate a virtual environment:
   - python -m venv .venv
   - Windows: .venv\Scripts\activate
   - macOS/Linux: source .venv/bin/activate
2. Install dependencies from requirements.txt
3. Copy the environment template to .env and edit as needed
4. Apply database migrations using Alembic
5. Start the development server with auto-reload

Key notes:
- The backend uses asyncpg for async DB access and psycopg for Alembic migrations.
- The dev server is started with uvicorn in reload mode.
- Ensure the .env file contains DATABASE_URL and other required settings.

**Section sources**
- [README.md:77-86](file://README.md#L77-L86)
- [backend/requirements.txt:1-23](file://backend/requirements.txt#L1-L23)
- [backend/app/core/config.py:15-24](file://backend/app/core/config.py#L15-L24)
- [backend/app/core/config.py:26-38](file://backend/app/core/config.py#L26-L38)
- [backend/app/core/config.py:40-44](file://backend/app/core/config.py#L40-L44)
- [backend/app/main.py:17-39](file://backend/app/main.py#L17-L39)
- [backend/app/main.py:41-60](file://backend/app/main.py#L41-L60)
- [backend/app/main.py:65-77](file://backend/app/main.py#L65-L77)

## Frontend Local Development Setup
Run the Vue 3 + TypeScript frontend locally:
1. Navigate to the frontend directory
2. Install dependencies using npm
3. Start the development server

The Vite dev server runs on port 5173 and proxies API requests to the backend at localhost:8000.

**Section sources**
- [README.md:87-91](file://README.md#L87-L91)
- [frontend/package.json:6-12](file://frontend/package.json#L6-L12)
- [frontend/vite.config.ts:12-21](file://frontend/vite.config.ts#L12-L21)

## WeChat Mini Program Development Setup
To develop the WeChat Mini Program:
1. Open the wechat-miniprogram folder in WeChat DevTools
2. Set your AppID in project.config.json
3. Configure the backend baseUrl in app.config.js to point to your local backend
4. Start debugging in DevTools

Notes:
- The default development baseUrl points to http://localhost:8000/api/v1
- The api utility attaches Authorization headers when tokens are present

**Section sources**
- [README.md:98-103](file://README.md#L98-L103)
- [wechat-miniprogram/project.config.json:33](file://wechat-miniprogram/project.config.json#L33)
- [wechat-miniprogram/app.config.js:3-6](file://wechat-miniprogram/app.config.js#L3-6)
- [wechat-miniprogram/utils/api.js:6-12](file://wechat-miniprogram/utils/api.js#L6-12)

## Environment Variables Configuration
Use the provided environment template to configure your local environment:
- Copy the template to .env and fill in required values
- Key variables include:
  - DATABASE_URL: Async PostgreSQL connection string
  - REDIS_URL: Redis connection string
  - AUTH_SECRET_KEY: JWT signing secret
  - OPENAI_API_KEY: For embeddings and chat features
  - CORS_ORIGINS: Allowed origins (JSON array)
  - WECHAT_APPID / WECHAT_SECRET: Mini Program credentials (optional)

Backend settings are loaded from .env using pydantic-settings. Defaults are provided for development; override them via .env.

**Section sources**
- [README.md:196-208](file://README.md#L196-L208)
- [backend/app/core/config.py:7-8](file://backend/app/core/config.py#L7-8)
- [backend/app/core/config.py:15-24](file://backend/app/core/config.py#L15-L24)
- [backend/app/core/config.py:26-38](file://backend/app/core/config.py#L26-L38)
- [backend/app/core/config.py:40-44](file://backend/app/core/config.py#L40-L44)
- [backend/app/core/config.py:46-57](file://backend/app/core/config.py#L46-L57)
- [backend/app/core/config.py:107-119](file://backend/app/core/config.py#L107-L119)

## Access URLs and Verification
After starting all services:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

Verification steps:
- Check the health endpoint: GET http://localhost:8000/api/v1/health
- Confirm the frontend loads and can proxy API calls to the backend
- Ensure Alembic migrations have been applied successfully

**Section sources**
- [README.md:92-96](file://README.md#L92-L96)
- [backend/app/main.py:65-66](file://backend/app/main.py#L65-L66)

## Troubleshooting Guide
Common issues and resolutions:
- Database connection errors:
  - Verify DATABASE_URL matches your local PostgreSQL instance
  - Ensure the database exists and credentials are correct
  - Confirm Alembic migration has been applied
- Redis connectivity issues:
  - Check REDIS_URL and ensure Redis is running on localhost:6379
- CORS errors from the frontend:
  - Ensure CORS_ORIGINS includes http://localhost:5173
  - In development, the backend allows all origins; confirm production settings if applicable
- WeChat Mini Program cannot reach the backend:
  - Confirm baseUrl in app.config.js points to http://localhost:8000/api/v1
  - Ensure the backend is running and accessible from DevTools
- Port conflicts:
  - If ports 5173, 8000, 5432, or 6379 are in use, stop conflicting processes or adjust configurations

**Section sources**
- [backend/app/core/config.py:40-44](file://backend/app/core/config.py#L40-L44)
- [backend/app/main.py:27-39](file://backend/app/main.py#L27-L39)
- [wechat-miniprogram/app.config.js:3-6](file://wechat-miniprogram/app.config.js#L3-6)

## Conclusion
You now have the full development environment ready: Docker-backed PostgreSQL and Redis, a FastAPI backend with Alembic migrations, a Vue 3 + TypeScript frontend with hot reload, and a WeChat Mini Program configured for local development. Use the verification steps to confirm everything works, and refer to the troubleshooting section if you encounter common setup issues.