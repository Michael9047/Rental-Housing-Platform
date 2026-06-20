# Rental Housing Matching System

This repository is being built from the architecture plan in `rental-housing-system-architecture.md`.

## Current Phase

The current implementation includes backend foundation, auth layer, and Phase 4 (pgvector search):

- FastAPI application
- PostgreSQL persistence
- SQLAlchemy 2.0 async ORM
- Alembic migrations
- User CRUD
- Property CRUD
- Password hashing with passlib/bcrypt
- JWT access token authentication
- Auth routes for register, login, and current-user lookup`n- Hybrid property search with pgvector semantic similarity`n- OpenAI text-embedding-3-small integration`n- Celery async task queue for embedding generation`n- IVFFlat index for fast vector search
- Role-based access control for landlord/admin operations
- Public property reads and authenticated property writes

## Project Structure

- `backend/` - FastAPI backend application, tests, migrations, and backend setup notes
- `rental-housing-system-architecture.md` - system architecture and staged product plan
- `docker-compose.yml` - local PostgreSQL and Redis services
- `.env.example` - example environment variables for local development

## Local Development

See `backend/README.md` for backend setup and run commands.

## Not Implemented Yet

The following modules are intentionally left for later phases (Phase 5+):

- WeChat login
- Booking and viewing appointments
- Payment flows
- Property images and media uploads
- AI recommendation and embeddings
- Frontend application
