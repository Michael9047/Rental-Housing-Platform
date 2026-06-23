# Rental Housing Matching System

An intelligent rental housing platform with AI-powered semantic search, LLM chat assistant,
and WeChat Mini Program integration.

Built with FastAPI + PostgreSQL/pgvector (backend), Vue 3 + TypeScript (frontend),
and WeChat Mini Program (mobile).

## Current Phase

**Phase 10 — Polish & Deployment** ✓

All phases complete:
- Phase 1–3: Core backend (models, auth, CRUD)
- Phase 4–5: Semantic search with OpenAI embeddings
- Phase 6: AI Chat with RAG + SSE streaming
- Phase 7: Data import (CSV/Excel bulk upload)
- Phase 8: Admin dashboard + audit logging
- Phase 9: WeChat Mini Program
- **Phase 10: Production deployment, CI/CD, monitoring, security hardening**

## Project Structure

```
.
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/               # API v1 routes
│   │   ├── core/              # Config, security, logging, monitoring
│   │   ├── db/                # Database session, indexes
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic layer
│   │   └── tasks/             # Celery async tasks
│   ├── tests/                 # Backend test suite
│   ├── alembic/               # Database migrations
│   ├── Dockerfile             # Multi-stage production build
│   └── requirements.txt
├── frontend/                   # Vue 3 + TypeScript SPA
│   ├── src/
│   │   ├── components/        # Reusable Vue components
│   │   ├── layouts/           # Page layouts
│   │   ├── router/            # Vue Router config
│   │   ├── services/          # API client modules
│   │   ├── stores/            # Pinia state management
│   │   ├── types/             # TypeScript type definitions
│   │   └── views/             # Page components
│   ├── nginx/
│   │   └── nginx.conf         # Production Nginx config
│   └── Dockerfile             # Multi-stage (Node build + Nginx)
├── wechat-miniprogram/         # WeChat Mini Program
├── docker/                     # Docker initialization scripts
├── .github/workflows/         # CI/CD pipelines
│   ├── ci.yml                 # Lint, test, build, push images
│   └── deploy.yml             # Manual production deploy
├── docker-compose.yml          # Development services
├── docker-compose.prod.yml     # Full production stack
├── .env.example                # Development environment template
├── .env.prod                   # Production environment template
├── DEPLOYMENT.md               # Detailed deployment guide
└── README.md                   # This file
```

## Local Development

### Prerequisites
- Python 3.13+
- Node.js 22+
- Docker & Docker Compose

### Quick Start

```bash
# 1. Start PostgreSQL + Redis (dev)
docker compose up -d

# 2. Backend setup
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
cp ../.env.example .env   # Edit with your values
alembic upgrade head
uvicorn app.main:app --reload

# 3. Frontend setup
cd frontend
npm install
npm run dev

# 4. Access
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Mini Program Development

1. Open `wechat-miniprogram/` in WeChat DevTools
2. Set your AppID in `project.config.json`
3. Configure the backend baseUrl in `app.config.js`
4. Start debugging

## Production Deployment

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for complete deployment guide including:
- Server requirements
- Docker Compose quick start
- SSL/HTTPS setup with Let's Encrypt
- Database backup & restore
- Monitoring stack setup
- Common troubleshooting

### Quick Deploy

```bash
# 1. Copy and configure environment
cp .env.prod.example .env.prod
# Edit .env.prod with real secrets

# 2. Start the full stack
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 3. Run database migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# 4. Check health
curl http://localhost:80/api/v1/health
```

## API Endpoints

### Core
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/auth/login | Email + password login |
| POST | /api/v1/auth/register | User registration |
| POST | /api/v1/auth/refresh | Refresh JWT access token |
| GET | /api/v1/health | Health check |
| GET | /metrics | Prometheus metrics |

### Properties
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/properties | List properties (paginated) |
| GET | /api/v1/properties/search | Semantic + facet search |
| GET | /api/v1/properties/{id} | Property detail |
| POST | /api/v1/properties | Create property (landlord) |
| PUT | /api/v1/properties/{id} | Update property (owner) |
| DELETE | /api/v1/properties/{id} | Delete property (owner) |

### WeChat
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/auth/wechat/login | Mini Program login (code → JWT) |
| POST | /api/v1/auth/wechat/phone | Phone number binding |
| GET | /api/v1/wechat/config | Mini program configuration |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/chat/sessions | Create new chat session |
| GET | /api/v1/chat/sessions | List user sessions |
| GET | /api/v1/chat/sessions/{id}/messages | Session history |
| POST | /api/v1/chat/sessions/{id}/messages | Send message (SSE stream) |
| DELETE | /api/v1/chat/sessions/{id} | Delete session |

### Bookings & Notifications
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/bookings | Create booking |
| GET | /api/v1/bookings | List bookings (role-filtered) |
| PATCH | /api/v1/bookings/{id}/status | Approve/reject (landlord) |
| GET | /api/v1/notifications | List notifications |
| PATCH | /api/v1/notifications/{id}/read | Mark as read |
| GET | /api/v1/notifications/unread-count | Unread count |

### Admin
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/admin/stats | Dashboard statistics |
| GET | /api/v1/admin/logs | Audit logs |
| PATCH | /api/v1/admin/properties/{id}/status | Moderate property |
| PATCH | /api/v1/admin/users/{id}/role | Update user role |
| GET | /api/v1/admin/embeddings/stats | Embedding stats |
| POST | /api/v1/admin/embeddings/reindex | Trigger reindex |

### Import
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/import/upload | Upload CSV/Excel |
| GET | /api/v1/import/tasks | Import task list |
| POST | /api/v1/import/tasks/{id}/retry | Retry failed rows |

## Environment Variables

See [.env.example](.env.example) for development and [.env.prod](.env.prod) for production.

Key variables:
| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | Async PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `AUTH_SECRET_KEY` | JWT signing secret (64+ chars in prod) | Yes |
| `OPENAI_API_KEY` | OpenAI API key for embeddings + chat | Yes |
| `CORS_ORIGINS` | Allowed origins (comma-separated JSON array) | Prod only |
| `WECHAT_APPID` / `WECHAT_SECRET` | WeChat Mini Program credentials | Optional |

## Monitoring

- **Prometheus metrics** at `/metrics` (request count, latency, Celery tasks, DB pool)
- **Structured JSON logging** in production (file and stdout)
- **Health check** at `/api/v1/health`
- **Request/response logging middleware** with timing and user tracking

## Security

- Bcrypt password hashing (cost factor 12)
- JWT with configurable expiry + refresh token rotation
- Redis-backed rate limiting (configurable per endpoint)
- SQLAlchemy parameterized queries (SQL injection prevention)
- CORS tightened in production via `CORS_ORIGINS`
- Sensitive data masking in logs (phone, email, password)
- Security headers via Nginx (X-Content-Type-Options, X-Frame-Options, etc.)
- OWASP Top 10 compliance audit module
- Non-root container user

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy 2.0 (async), PostgreSQL 16, pgvector, Celery, Redis
- **Frontend**: Vue 3, TypeScript, Vite, Element Plus, Pinia, Vue Router
- **Mobile**: WeChat Mini Program (native WXML/WXSS/JS)
- **AI**: OpenAI text-embedding-3-small, GPT-4o, pgvector HNSW/IVFFlat
- **Infra**: Docker, Nginx, Prometheus, GitHub Actions CI/CD
