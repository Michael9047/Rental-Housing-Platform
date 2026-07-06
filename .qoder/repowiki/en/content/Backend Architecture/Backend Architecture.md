# Backend Architecture

<cite>
**Referenced Files in This Document**
- [main.py](file://backend/app/main.py)
- [router.py](file://backend/app/api/v1/router.py)
- [config.py](file://backend/app/core/config.py)
- [session.py](file://backend/app/db/session.py)
- [base.py](file://backend/app/db/base.py)
- [deps.py](file://backend/app/api/deps.py)
- [security.py](file://backend/app/core/security.py)
- [logging.py](file://backend/app/core/logging.py)
- [security_audit.py](file://backend/app/core/security_audit.py)
- [monitoring.py](file://backend/app/core/monitoring.py)
- [celery_app.py](file://backend/app/celery_app.py)
- [embedding_tasks.py](file://backend/app/tasks/embedding_tasks.py)
- [auth_service.py](file://backend/app/services/auth_service.py)
- [user.py](file://backend/app/models/user.py)
- [auth.py](file://backend/app/schemas/auth.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)
10. [Appendices](#appendices)

## Introduction
This document describes the architecture of the FastAPI backend for a rental housing system. It explains the layered design separating API routes, service layer, data models, and business logic; the application factory pattern; middleware pipeline (CORS, rate limiting, logging, security); database session management with SQLAlchemy 2.0 async patterns; API versioning under /api/v1/; dependency injection across services; Celery task queue integration; request/response validation with Pydantic; error handling strategies; infrastructure requirements; scalability considerations; and deployment topology.

## Project Structure
The backend follows a feature-oriented layout with clear separation:
- API layer: v1 routers grouped by feature modules
- Services layer: business logic encapsulated per domain
- Data access: SQLAlchemy 2.0 async engine and sessions
- Models: ORM entities and enums
- Schemas: Pydantic request/response models
- Core: configuration, security utilities, logging, monitoring, and audit helpers
- Tasks: Celery background jobs
- App entrypoint: application factory and middleware wiring

```mermaid
graph TB
subgraph "App Entry"
Main["FastAPI app factory<br/>create_app()"]
end
subgraph "API Layer"
Router["v1 Router Aggregator"]
Routes["Feature Routers<br/>auth, users, properties, bookings, ..."]
end
subgraph "Services Layer"
AuthSvc["AuthService"]
UserSvc["UserService"]
EmbeddingSvc["EmbeddingService"]
end
subgraph "Data Access"
DBSession["Async Session Maker"]
Base["SQLAlchemy DeclarativeBase"]
Models["ORM Models"]
end
subgraph "Core"
Config["Settings (Pydantic Settings)"]
Security["JWT & Password Utils"]
Logging["Request Logging & Exception Handlers"]
Monitoring["Prometheus Middleware"]
Audit["Rate Limiting & JWT Refresh"]
end
subgraph "Background Jobs"
CeleryApp["Celery App"]
EmbedTasks["Embedding Tasks"]
end
Main --> Router
Router --> Routes
Routes --> AuthSvc
AuthSvc --> UserSvc
AuthSvc --> Security
AuthSvc --> DBSession
EmbedTasks --> EmbeddingSvc
EmbedTasks --> DBSession
Main --> Logging
Main --> Monitoring
Main --> Audit
Main --> Config
DBSession --> Base
Base --> Models
CeleryApp --> EmbedTasks
```

**Diagram sources**
- [main.py:17-78](file://backend/app/main.py#L17-L78)
- [router.py:1-23](file://backend/app/api/v1/router.py#L1-L23)
- [auth_service.py:14-77](file://backend/app/services/auth_service.py#L14-L77)
- [session.py:1-14](file://backend/app/db/session.py#L1-L14)
- [base.py:1-35](file://backend/app/db/base.py#L1-L35)
- [config.py:7-167](file://backend/app/core/config.py#L7-L167)
- [security.py:1-34](file://backend/app/core/security.py#L1-L34)
- [logging.py:124-231](file://backend/app/core/logging.py#L124-L231)
- [monitoring.py:126-176](file://backend/app/core/monitoring.py#L126-L176)
- [security_audit.py:49-95](file://backend/app/core/security_audit.py#L49-L95)
- [celery_app.py:9-31](file://backend/app/celery_app.py#L9-L31)
- [embedding_tasks.py:16-81](file://backend/app/tasks/embedding_tasks.py#L16-L81)

**Section sources**
- [main.py:17-78](file://backend/app/main.py#L17-L78)
- [router.py:1-23](file://backend/app/api/v1/router.py#L1-L23)
- [config.py:7-167](file://backend/app/core/config.py#L7-L167)
- [session.py:1-14](file://backend/app/db/session.py#L1-L14)
- [base.py:1-35](file://backend/app/db/base.py#L1-L35)

## Core Components
- Application Factory: create_app initializes settings, logging, CORS, metrics, rate limiting, exception handlers, mounts uploads, and includes v1 router.
- API Versioning: All endpoints are mounted under /api/v1 via a central router that aggregates feature-specific routers.
- Dependency Injection: FastAPI Depends provide AsyncSession, current user, and role-based guards to route handlers.
- Database Sessions: SQLAlchemy 2.0 async engine and sessionmaker configured from settings; Base class used by all models.
- Security: bcrypt password hashing, JWT creation/verification, refresh token support, and OWASP checklist utilities.
- Validation: Pydantic schemas define strict input/output contracts.
- Background Processing: Celery app configured with Redis broker/backend and task routing; tasks use asyncio + async engines.
- Observability: Prometheus middleware and signals collect HTTP and Celery metrics; structured JSON logging with sensitive field masking.

**Section sources**
- [main.py:17-78](file://backend/app/main.py#L17-L78)
- [router.py:1-23](file://backend/app/api/v1/router.py#L1-L23)
- [deps.py:14-57](file://backend/app/api/deps.py#L14-L57)
- [session.py:1-14](file://backend/app/db/session.py#L1-L14)
- [security.py:12-34](file://backend/app/core/security.py#L12-L34)
- [security_audit.py:49-149](file://backend/app/core/security_audit.py#L49-L149)
- [auth.py:8-63](file://backend/app/schemas/auth.py#L8-L63)
- [celery_app.py:9-31](file://backend/app/celery_app.py#L9-L31)
- [embedding_tasks.py:16-112](file://backend/app/tasks/embedding_tasks.py#L16-L112)
- [logging.py:77-122](file://backend/app/core/logging.py#L77-L122)
- [monitoring.py:126-176](file://backend/app/core/monitoring.py#L126-L176)

## Architecture Overview
High-level component interactions and data flows:

```mermaid
sequenceDiagram
participant Client as "Client"
participant FastAPI as "FastAPI App"
participant MW as "Middleware Chain"
participant Router as "v1 Router"
participant Deps as "Deps (DB, Auth)"
participant Service as "Service Layer"
participant DB as "Async Session/Engine"
participant Celery as "Celery Worker"
participant Redis as "Redis Broker"
Client->>FastAPI : HTTP Request
FastAPI->>MW : Apply CORS, RateLimit, Logging, Metrics
MW-->>Router : Forwarded Request
Router->>Deps : Inject AsyncSession, CurrentUser
Deps->>DB : Create/Use AsyncSession
Router->>Service : Call business method
Service->>DB : Query/Update via ORM
Service-->>Router : Domain result
Router-->>MW : Response
MW-->>Client : HTTP Response
Note over Service,Celery : Long-running work enqueued
Service->>Celery : Enqueue task
Celery->>Redis : Publish job
Redis-->>Celery : Deliver job
Celery->>DB : Async Session in worker
Celery-->>Service : Task completes
```

**Diagram sources**
- [main.py:17-78](file://backend/app/main.py#L17-L78)
- [router.py:1-23](file://backend/app/api/v1/router.py#L1-L23)
- [deps.py:14-57](file://backend/app/api/deps.py#L14-L57)
- [session.py:1-14](file://backend/app/db/session.py#L1-L14)
- [celery_app.py:9-31](file://backend/app/celery_app.py#L9-L31)
- [embedding_tasks.py:16-112](file://backend/app/tasks/embedding_tasks.py#L16-L112)

## Detailed Component Analysis

### Application Factory and Middleware Pipeline
- create_app loads settings, sets up logging, configures CORS based on environment, installs Prometheus middleware, conditionally adds Redis-backed rate limiter, registers global exception handlers, mounts /metrics, installs Celery metrics signals, includes v1 router, and mounts static uploads.
- Middleware order matters: logging wraps all requests; rate limiting is applied before request processing; metrics capture latency and counts.

```mermaid
flowchart TD
Start(["create_app"]) --> LoadCfg["Load Settings"]
LoadCfg --> SetupLogging["Setup Logging"]
SetupLogging --> BuildApp["Create FastAPI Instance"]
BuildApp --> AddCORS["Add CORS Middleware"]
AddCORS --> AddMetrics["Add Prometheus Middleware"]
AddMetrics --> TryRateLimit{"Redis Available?"}
TryRateLimit --> |Yes| AddRL["Add RateLimitMiddleware"]
TryRateLimit --> |No| SkipRL["Skip Rate Limiting"]
AddRL --> AddLogging["Add RequestLoggingMiddleware"]
SkipRL --> AddLogging
AddLogging --> RegisterHandlers["Register Exception Handlers"]
RegisterHandlers --> MountMetrics["Mount /metrics Endpoint"]
MountMetrics --> InstallCeleryMetrics["Install Celery Metrics Signals"]
InstallCeleryMetrics --> IncludeV1["Include /api/v1 Router"]
IncludeV1 --> MountUploads["Mount Static Uploads"]
MountUploads --> End(["Return App"])
```

**Diagram sources**
- [main.py:17-78](file://backend/app/main.py#L17-L78)
- [monitoring.py:167-176](file://backend/app/core/monitoring.py#L167-L176)
- [security_audit.py:49-95](file://backend/app/core/security_audit.py#L49-L95)
- [logging.py:226-231](file://backend/app/core/logging.py#L226-L231)

**Section sources**
- [main.py:17-78](file://backend/app/main.py#L17-L78)
- [monitoring.py:126-176](file://backend/app/core/monitoring.py#L126-L176)
- [security_audit.py:49-95](file://backend/app/core/security_audit.py#L49-L95)
- [logging.py:124-231](file://backend/app/core/logging.py#L124-L231)

### API Versioning and Route Organization
- Central v1 router aggregates feature routers under consistent prefixes: auth, users, properties, images, bookings, notifications, chat, admin, import, wechat, ai-search, geo, contracts, payments, pois, map.
- Tags group endpoints for documentation and navigation.

```mermaid
graph LR
V1["/api/v1"] --> Health["health"]
V1 --> Auth["/auth"]
V1 --> Users["/users"]
V1 --> Props["/properties"]
V1 --> Images["/properties/images"]
V1 --> Bookings["/bookings"]
V1 --> Notifications["/notifications"]
V1 --> Chat["/chat"]
V1 --> Admin["/admin"]
V1 --> Import["/import"]
V1 --> Wechat["/wechat"]
V1 --> AISearch["/ai-search"]
V1 --> Geo["/geo"]
V1 --> Contracts["/contracts"]
V1 --> Payments["/payments"]
V1 --> POIs["/pois"]
V1 --> Map["/map"]
```

**Diagram sources**
- [router.py:1-23](file://backend/app/api/v1/router.py#L1-L23)

**Section sources**
- [router.py:1-23](file://backend/app/api/v1/router.py#L1-L23)

### Dependency Injection Pattern
- get_db_session provides an AsyncSession per request using async_session_maker.
- get_current_user validates bearer tokens and returns authenticated User.
- Role guards require_landlord, require_tenant, require_admin enforce authorization at route level.

```mermaid
classDiagram
class Deps {
+get_db_session() AsyncSession
+get_current_user(token, session) User
+require_landlord(user) User
+require_tenant(user) User
+require_admin(user) User
}
class AuthService {
+__init__(session)
+register_user(in) User
+authenticate(identifier, password) User?
+create_access_token(user) str
+get_current_user_from_token(token) User?
+wechat_login(code) tuple[User,bool]
}
Deps --> AuthService : "uses"
```

**Diagram sources**
- [deps.py:14-57](file://backend/app/api/deps.py#L14-L57)
- [auth_service.py:14-77](file://backend/app/services/auth_service.py#L14-L77)

**Section sources**
- [deps.py:14-57](file://backend/app/api/deps.py#L14-L57)
- [auth_service.py:14-77](file://backend/app/services/auth_service.py#L14-L77)

### Database Session Management (SQLAlchemy 2.0 Async)
- Engine created with async driver and echo controlled by debug flag.
- async_sessionmaker configured with expire_on_commit=False for predictable state after commits.
- Base class extends AsyncAttrs and DeclarativeBase; models inherit Base and TimestampMixin.

```mermaid
classDiagram
class Session {
+engine
+async_session_maker
+Base
}
class Model_User {
+id
+username
+password_hash
+phone
+email
+role
+status
}
Session --> Model_User : "declared via Base"
```

**Diagram sources**
- [session.py:1-14](file://backend/app/db/session.py#L1-L14)
- [base.py:1-35](file://backend/app/db/base.py#L1-L35)
- [user.py:24-48](file://backend/app/models/user.py#L24-L48)

**Section sources**
- [session.py:1-14](file://backend/app/db/session.py#L1-L14)
- [base.py:1-35](file://backend/app/db/base.py#L1-L35)
- [user.py:24-48](file://backend/app/models/user.py#L24-L48)

### Security Middleware and Authentication Flow
- Password hashing and verification via bcrypt.
- JWT access tokens with configurable expiry; refresh token flow supported.
- Rate limiting uses Redis sorted sets per client IP and endpoint prefix; development can bypass when debug enabled.
- Global exception handlers normalize errors and log with request context.

```mermaid
sequenceDiagram
participant Client as "Client"
participant FastAPI as "FastAPI"
participant RL as "RateLimitMiddleware"
participant Auth as "Auth Service"
participant Sec as "Security Utils"
participant DB as "Async Session"
Client->>FastAPI : POST /api/v1/auth/login
FastAPI->>RL : check(request)
RL-->>FastAPI : allow or 429
FastAPI->>Auth : authenticate(identifier, password)
Auth->>Sec : verify_password(...)
Auth->>DB : find user by username/email
DB-->>Auth : User
Auth->>Sec : create_access_token(subject)
Auth-->>FastAPI : User + token
FastAPI-->>Client : TokenResponse
```

**Diagram sources**
- [security_audit.py:49-95](file://backend/app/core/security_audit.py#L49-L95)
- [auth_service.py:29-38](file://backend/app/services/auth_service.py#L29-L38)
- [security.py:12-34](file://backend/app/core/security.py#L12-L34)
- [deps.py:19-30](file://backend/app/api/deps.py#L19-L30)
- [logging.py:193-231](file://backend/app/core/logging.py#L193-L231)

**Section sources**
- [security.py:12-34](file://backend/app/core/security.py#L12-L34)
- [security_audit.py:49-149](file://backend/app/core/security_audit.py#L49-L149)
- [auth_service.py:29-51](file://backend/app/services/auth_service.py#L29-L51)
- [logging.py:193-231](file://backend/app/core/logging.py#L193-L231)

### Request/Response Validation with Pydantic
- Schemas define strict inputs (e.g., RegisterRequest, LoginRequest) and outputs (CurrentUserResponse).
- Validators include min/max lengths, email format, enum constraints, and computed fields.
- Validation errors are normalized by global handler into a consistent error envelope.

```mermaid
flowchart TD
In["Request Body"] --> Validate["Pydantic Schema Validation"]
Validate --> Valid{"Valid?"}
Valid --> |No| ErrResp["422 Validation Error"]
Valid --> |Yes| Next["Proceed to Handler"]
```

**Diagram sources**
- [auth.py:8-63](file://backend/app/schemas/auth.py#L8-L63)
- [logging.py:193-202](file://backend/app/core/logging.py#L193-L202)

**Section sources**
- [auth.py:8-63](file://backend/app/schemas/auth.py#L8-L63)
- [logging.py:193-202](file://backend/app/core/logging.py#L193-L202)

### Celery Task Queue Integration
- Celery app configured with Redis broker/backend and task serialization.
- Task routing assigns specific queues (e.g., embedding, import).
- Tasks manage their own async engines and sessions; they track job status and handle retries/backoff.

```mermaid
sequenceDiagram
participant Service as "Service"
participant Celery as "Celery App"
participant Redis as "Redis Broker"
participant Worker as "Worker Process"
participant Task as "generate_property_embedding"
participant DB as "Async Session"
Service->>Celery : delay(task, args)
Celery->>Redis : enqueue job
Redis-->>Worker : deliver job
Worker->>Task : execute
Task->>DB : create pending job record
Task->>DB : update processing/completed/failed
Task-->>Worker : done
```

**Diagram sources**
- [celery_app.py:9-31](file://backend/app/celery_app.py#L9-L31)
- [embedding_tasks.py:16-112](file://backend/app/tasks/embedding_tasks.py#L16-L112)

**Section sources**
- [celery_app.py:9-31](file://backend/app/celery_app.py#L9-L31)
- [embedding_tasks.py:16-112](file://backend/app/tasks/embedding_tasks.py#L16-L112)

### Error Handling Strategy
- Global handlers for validation, HTTP exceptions, and unhandled exceptions produce a uniform JSON error structure.
- Structured logging captures request_id, method, path, status_code, duration_ms, and optional user_id.
- Sensitive fields are masked in logs to prevent leakage.

```mermaid
flowchart TD
Start(["Exception Occurs"]) --> Type{"Type?"}
Type --> |Validation| HandleVal["Build 422 Response"]
Type --> |HTTP| HandleHTTP["Build HTTP Response"]
Type --> |Generic| HandleGen["Build 500 Response"]
HandleVal --> Log["Log with Context"]
HandleHTTP --> Log
HandleGen --> Log
Log --> End(["Return Normalized Error"])
```

**Diagram sources**
- [logging.py:170-231](file://backend/app/core/logging.py#L170-L231)

**Section sources**
- [logging.py:170-231](file://backend/app/core/logging.py#L170-L231)

## Dependency Analysis
Key dependencies and relationships:

```mermaid
graph TB
Main["main.py"] --> Router["api/v1/router.py"]
Main --> Config["core/config.py"]
Main --> Logging["core/logging.py"]
Main --> Monitoring["core/monitoring.py"]
Main --> Audit["core/security_audit.py"]
Router --> Routes["routes/*"]
Routes --> Deps["api/deps.py"]
Deps --> Session["db/session.py"]
Deps --> AuthService["services/auth_service.py"]
AuthService --> Security["core/security.py"]
AuthService --> UserModel["models/user.py"]
AuthService --> Schemas["schemas/auth.py"]
Celery["celery_app.py"] --> Tasks["tasks/embedding_tasks.py"]
Tasks --> Session
```

**Diagram sources**
- [main.py:17-78](file://backend/app/main.py#L17-L78)
- [router.py:1-23](file://backend/app/api/v1/router.py#L1-L23)
- [deps.py:14-57](file://backend/app/api/deps.py#L14-L57)
- [session.py:1-14](file://backend/app/db/session.py#L1-L14)
- [auth_service.py:14-77](file://backend/app/services/auth_service.py#L14-L77)
- [security.py:12-34](file://backend/app/core/security.py#L12-L34)
- [user.py:24-48](file://backend/app/models/user.py#L24-L48)
- [auth.py:8-63](file://backend/app/schemas/auth.py#L8-L63)
- [celery_app.py:9-31](file://backend/app/celery_app.py#L9-L31)
- [embedding_tasks.py:16-112](file://backend/app/tasks/embedding_tasks.py#L16-L112)

**Section sources**
- [main.py:17-78](file://backend/app/main.py#L17-L78)
- [router.py:1-23](file://backend/app/api/v1/router.py#L1-L23)
- [deps.py:14-57](file://backend/app/api/deps.py#L14-L57)
- [session.py:1-14](file://backend/app/db/session.py#L1-L14)
- [auth_service.py:14-77](file://backend/app/services/auth_service.py#L14-L77)
- [security.py:12-34](file://backend/app/core/security.py#L12-L34)
- [user.py:24-48](file://backend/app/models/user.py#L24-L48)
- [auth.py:8-63](file://backend/app/schemas/auth.py#L8-L63)
- [celery_app.py:9-31](file://backend/app/celery_app.py#L9-L31)
- [embedding_tasks.py:16-112](file://backend/app/tasks/embedding_tasks.py#L16-L112)

## Performance Considerations
- Connection Pooling: Use appropriate pool size and overflow limits for asyncpg; monitor pool gauges exposed by Prometheus middleware.
- Asynchronous I/O: Keep DB calls non-blocking; avoid blocking operations in request handlers.
- Rate Limiting: Tune window and max_requests based on expected traffic; consider per-endpoint policies if needed.
- Background Jobs: Offload long-running tasks (embeddings, imports) to Celery workers; scale workers horizontally.
- Caching: Consider caching frequent reads (e.g., property listings) behind Redis where appropriate.
- Metrics: Track request latency histograms and Celery task durations to identify bottlenecks.

## Troubleshooting Guide
- Authentication Failures: Check JWT secret and algorithm settings; ensure tokens are not expired; verify user status is active.
- Rate Limit Errors: Inspect Redis connectivity and keys; confirm environment/debug flags; adjust limits if necessary.
- Validation Errors: Review Pydantic schema constraints and request payloads; consult normalized error responses.
- Database Issues: Verify connection string, pool metrics, and migrations; ensure models are imported via base module.
- Celery Problems: Confirm broker/backend URLs, task routing, and worker logs; inspect job status records.

**Section sources**
- [security.py:22-34](file://backend/app/core/security.py#L22-L34)
- [security_audit.py:49-95](file://backend/app/core/security_audit.py#L49-L95)
- [logging.py:193-231](file://backend/app/core/logging.py#L193-L231)
- [session.py:1-14](file://backend/app/db/session.py#L1-L14)
- [celery_app.py:9-31](file://backend/app/celery_app.py#L9-L31)
- [embedding_tasks.py:16-112](file://backend/app/tasks/embedding_tasks.py#L16-L112)

## Conclusion
The backend employs a clean layered architecture with explicit separation between API routes, services, models, and core utilities. The application factory centralizes middleware and configuration, while dependency injection ensures testable and composable components. SQLAlchemy 2.0 async patterns and Redis-backed rate limiting and Celery integration enable scalable, observable operations. Strong validation and standardized error handling improve reliability and developer experience.

## Appendices

### Infrastructure Requirements
- Python runtime and virtual environment
- PostgreSQL with async driver (asyncpg)
- Redis for rate limiting, Celery broker/backend, and optional caching
- Optional: prometheus-client for metrics collection

### Scalability Considerations
- Horizontal scaling of FastAPI instances behind a reverse proxy/load balancer
- Multiple Celery workers per queue for heavy workloads
- Database read replicas for query-heavy features
- External object storage for uploads instead of local filesystem

### Deployment Topology
```mermaid
graph TB
LB["Reverse Proxy / Load Balancer"]
subgraph "Application Pods"
API1["FastAPI Instance 1"]
API2["FastAPI Instance 2"]
end
subgraph "Workers"
W1["Celery Worker - embedding"]
W2["Celery Worker - import"]
end
Redis[(Redis)]
DB[(PostgreSQL)]
LB --> API1
LB --> API2
API1 --> Redis
API2 --> Redis
API1 --> DB
API2 --> DB
W1 --> Redis
W2 --> Redis
W1 --> DB
W2 --> DB
```