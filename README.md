# Rental Housing Matching System

This repository is being built from the architecture plan in ental-housing-system-architecture.md.

## Current Phase

Phase 5 - Vue 3 Frontend scaffolded:

- FastAPI backend with PostgreSQL + pgvector
- JWT auth, role-based access control
- Property CRUD with hybrid semantic search
- Celery async embedding generation
- **Vue 3 + TypeScript frontend with Element Plus**
- **Vite dev server proxying to backend**
- **Pinia state management with auth & property stores**
- **Vue Router with navigation guards for role-based access**
- **All core pages: Home, Search, Detail, Login, Register, Profile, Create, Manage**

## Project Structure

- ackend/ - FastAPI backend application, tests, migrations, and backend setup notes
- rontend/ - Vue 3 + TypeScript SPA with Element Plus
- ental-housing-system-architecture.md - system architecture and staged product plan
- docker-compose.yml - local PostgreSQL and Redis services
- .env.example - example environment variables for local development

## Local Development

- Backend: see ackend/README.md
- Frontend: see rontend/README.md

### Quick Start (Frontend)

`ash
cd frontend
npm install
npm run dev
`

The Vite dev server runs on http://localhost:5173 and proxies /api to the backend at localhost:8000.

## Not Implemented Yet

The following modules are intentionally left for later phases:

- WeChat login
- Booking and viewing appointments
- Payment flows
- Property images and media uploads
- AI recommendation and embeddings (backend ready, frontend integration pending)
