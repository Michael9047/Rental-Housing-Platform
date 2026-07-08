---
kind: dependency_management
name: Per-Service Pinning with Lockfiles and Multi-Stage Docker Builds
category: dependency_management
scope:
    - '**'
source_files:
    - backend/requirements.txt
    - backend/requirements-dev.txt
    - backend/Dockerfile
    - frontend/package.json
    - frontend/package-lock.json
    - wechat-miniprogram/project.config.json
---

This monorepo manages dependencies independently per service using language-native package managers, with no cross-service shared dependency graph.

**Python (backend)**
- Dependencies are pinned to exact versions in `backend/requirements.txt` (e.g. fastapi==0.112.2, celery==5.4.0, openai==1.82.0). There is no pipenv.lock or poetry.lock; the text file itself is the lockfile.
- A separate `backend/requirements-dev.txt` includes `-r requirements.txt` plus dev-only packages (pytest, aiosqlite, pytest-asyncio).
- The backend `Dockerfile` uses a two-stage build: a python:3.13-slim builder stage runs `pip install --no-cache-dir --prefix=/install -r requirements.txt`, then copies only /usr/local into a slim runtime image — ensuring production images contain exactly the pinned set.
- No private PyPI registry or --index-url is configured; all packages resolve from the default PyPI.

**TypeScript/Vue (frontend)**
- `frontend/package.json` declares runtime deps (vue, pinia, axios, element-plus, leaflet) and dev deps (vite, typescript, vue-tsc).
- `frontend/package-lock.json` (lockfileVersion 3) pins every transitive dependency with integrity hashes, so npm ci produces deterministic installs across machines.
- No custom npm registry or .npmrc is present; resolution goes to the public npm registry.

**WeChat Miniprogram**
- `wechat-miniprogram/project.config.json` sets nodeModules to false, meaning the miniprogram does not use npm at all — third-party code is vendored inline as JS/WXML/WXSS files under components/. There is no package.json for this subproject.

**Orchestration**
- `docker-compose.yml` provisions infrastructure dependencies (PostgreSQL with pgvector, Redis) via official images; application services pull their Python/Node dependencies through the mechanisms above.
- No top-level lockfile or workspace tool (pnpm workspaces, pip-tools, etc.) ties the three subprojects together.

**Conventions developers should follow**
- Backend: add new Python packages to `backend/requirements.txt` with an explicit == version pin; keep dev-only extras in `requirements-dev.txt` via `-r requirements.txt`.
- Frontend: update `frontend/package.json` and commit the regenerated `frontend/package-lock.json`; avoid manual edits to the lockfile.
- Miniprogram: do not introduce npm dependencies — bundle any library source directly under `wechat-miniprogram/`.
- Do not configure private registries or proxy settings unless required by your environment; none are currently declared.