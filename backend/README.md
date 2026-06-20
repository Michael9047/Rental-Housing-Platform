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

## Phase 4: pgvector + Search

The backend now supports hybrid semantic search via pgvector:

1. Run the pgvector migration:

```powershell
alembic upgrade head
```

This enables the `vector` extension and adds an `embedding` column to the `properties` table with an IVFFlat index.

2. Start the Celery worker (for async embedding generation):

```powershell
celery -A app.celery_app worker -Q embedding --loglevel=info
```

3. The new search endpoint is at `GET /api/v1/properties/search`:

- `q` ¡ª natural language query (generates embedding for semantic search)
- `district`, `price_min`, `price_max`, `bedrooms`, `property_type` ¡ª structured filters
- Results include a `similarity` score when `q` is provided

Embedding generation is dispatched to Celery automatically on property create/update. Without a running Celery worker, properties will be saved without embeddings and will not appear in semantic search results.

To reindex all properties without embeddings, use the Celery task:

```powershell
celery -A app.celery_app call app.tasks.embedding_tasks.reindex_all_properties
```

## Previous Scope

The backend currently implements:

- Health check
- User CRUD
- Auth registration, login, JWT verification, and current-user lookup
- Role-based dependencies for landlord/admin access
- Public property reads and authenticated landlord/admin property writes
- PostgreSQL connection
- Alembic initial migration

Future modules such as WeChat login, booking, payment, embeddings, refresh token rotation, and AI recommendations are intentionally left out of the current implementation pass.

## Phase 6: Property Images & Media Upload

### Image Storage
- Images are stored locally in `backend/uploads/` (configurable via `UPLOAD_DIR`)
- Max file size: 5MB (configurable via `MAX_UPLOAD_SIZE`)
- Allowed types: JPEG, PNG, WebP (configurable via `ALLOWED_IMAGE_TYPES`)
- Max 10 images per property (configurable via `MAX_IMAGES_PER_PROPERTY`)
- Filenames use UUID to prevent collisions

### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/properties/{id}/images` | Upload images (multipart) |
| GET | `/api/v1/properties/{id}/images` | List images for a property |
| DELETE | `/api/v1/properties/{id}/images/{img_id}` | Delete an image |
| PATCH | `/api/v1/properties/{id}/images/{img_id}/primary` | Set primary image |
| GET | `/api/v1/uploads/{filename}` | Serve static image files |

### Model
- `PropertyImage`: id, property_id (FK), filename, original_name, mime_type, file_size, sort_order, is_primary, created_at, updated_at

### Testing
```bash
pytest tests/test_images.py -v
```
