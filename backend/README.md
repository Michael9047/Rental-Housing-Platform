# Rental Housing Backend

FastAPI backend scaffold for the rental housing matching platform.

## Stack

- FastAPI
- SQLAlchemy 2.0 async ORM
- Alembic migrations
- PostgreSQL 16
- Pydantic v2

## Local Development

1. Copy environment variables:

```powershell
Copy-Item .env.example .env
```

2. Start PostgreSQL and Redis:

```powershell
docker compose up -d postgres redis
```

3. Install backend dependencies:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

4. Run migrations:

```powershell
alembic upgrade head
```

5. Start the API:

```powershell
uvicorn app.main:app --reload
```

The API docs will be available at `http://127.0.0.1:8000/docs`.

## Current Scope

The backend currently implements:

- Health check
- User CRUD
- Auth registration, login, JWT verification, and current-user lookup
- Role-based dependencies for landlord/admin access
- Public property reads and authenticated landlord/admin property writes
- PostgreSQL connection
- Alembic initial migration

Future modules such as WeChat login, booking, payment, embeddings, refresh token rotation, and AI recommendations are intentionally left out of the current implementation pass.
