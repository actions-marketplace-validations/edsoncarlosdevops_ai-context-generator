# FastAPI + PostgreSQL + Docker — Agent Governance Guidelines

This project is a REST API service built with FastAPI (Python) backed by PostgreSQL, containerised with Docker, and deployed via GitHub Actions CI/CD. It exposes HTTP endpoints with Pydantic-validated schemas, uses SQLAlchemy async ORM with Alembic migrations, and is designed for horizontal scalability behind a load balancer.

## 1. API Design & Input Validation

- **Pydantic Boundary Enforcement**: All route handler inputs MUST be declared as Pydantic `BaseModel` subclasses. Raw `dict` or `Request.json()` parsing at the handler level is a 🔴 Critical finding.
- **HTTP Status Codes**: `201` for resource creation, `204` for deletion, `422` for validation errors (automatic via FastAPI). Never return `200` for a created resource.
- **Response Schema Pinning**: Every endpoint MUST declare an explicit `response_model`. Returning raw `dict` bypasses serialisation validation and is a 🟠 High finding.
- **No Business Logic in Routers**: Route handlers must delegate to a service layer. Any database query or business computation directly in a router function is a 🟡 Medium finding.

## 2. Database & Migration Safety

- **Alembic Migrations Required**: Every schema change (column add/remove/rename, index creation, constraint change) MUST have a corresponding Alembic migration file. Direct `CREATE TABLE` or `ALTER TABLE` in code is a 🔴 Critical finding.
- **Reversible Migrations**: Every migration MUST implement `downgrade()`. An empty or `pass` downgrade body is a 🟠 High finding.
- **Async Sessions**: All database operations MUST use `AsyncSession` from `sqlalchemy.ext.asyncio`. Synchronous `Session` usage blocks the event loop and is a 🔴 Critical finding.
- **Index Strategy**: Foreign key columns and any column used in `WHERE` or `ORDER BY` clauses MUST have a database index declared in the migration.

## 3. Security

- **No Hardcoded Secrets**: API keys, database URLs, and JWT secrets MUST be loaded from environment variables via `pydantic-settings` (`BaseSettings`). Any literal secret string in source code is a 🔴 Critical finding.
- **JWT Expiry**: All issued JWT tokens MUST include an `exp` claim. Tokens without expiry are a 🔴 Critical security finding.
- **CORS Allowlist**: `CORSMiddleware` MUST specify explicit origins. Wildcard `allow_origins=["*"]` in production configuration is a 🟠 High finding.

## 4. Container & CI/CD Standards

- **Multi-Stage Dockerfile**: The production Docker image MUST use a multi-stage build. The final `FROM` MUST use `python:3.12-slim` or distroless. Installing dev dependencies in the final stage is a 🟡 Medium finding.
- **No Secrets in Layers**: `ENV` or `ARG` instructions must never carry secret values. Use Docker BuildKit secrets (`--mount=type=secret`) for sensitive build-time values.
- **Health Check Required**: Every service `Dockerfile` MUST define a `HEALTHCHECK` instruction pointing to a `/health` or `/ready` endpoint.

## 5. Testing Standards

- **Minimum Coverage**: All new service-layer functions and utility modules require at least one `pytest` test. PRs that add business logic without tests are a 🟡 Medium finding.
- **Test Database Isolation**: Tests MUST use a separate test database or `pytest-asyncio` transaction rollback fixtures. Tests that mutate the development database are a 🟠 High finding.
