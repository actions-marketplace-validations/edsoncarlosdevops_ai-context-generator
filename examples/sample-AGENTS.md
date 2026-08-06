# 🤖 Governance Guidelines for Backend Services

This document provides context and rules for AI assistants working on this project.

## 1. FastAPI Architecture (Python)
- **Dependency Injection**: Always use FastAPI's `Depends` for database sessions and authentication contexts. Do not instantiate global service singletons.
- **Pydantic Validation**: Define strict Pydantic v2 models for all request and response schemas. Enable `extra = "forbid"` on input schemas to prevent unknown fields.
- **Async DB Calls**: Use SQLAlchemy 2.0 async sessions exclusively. Never block the event loop with synchronous ORM calls.

## 2. PostgreSQL Database Design
- **UUID Primary Keys**: Use `UUID` (gen_random_uuid()) for all primary keys to ensure safe distributed generation.
- **Migration Consistency**: All schema changes must be accompanied by an Alembic migration script. Do not write raw `ALTER TABLE` statements in application code.

## 3. Docker Containerization
- **Multi-stage Builds**: Use multi-stage Dockerfiles. The final image must use `python:3.12-slim` and not contain build dependencies like `gcc` or `make`.
- **Non-root User**: The final container must run under a non-root user (`appuser`). Never run the application as root.
