# TaskFlow — Task Management API

TaskFlow is a multi-user task management backend built with FastAPI. It provides secure account registration and JWT authentication, personal task lists, project organization, due dates, tags, priority and status workflows, searchable and sortable pagination, and dashboard statistics. The API is documented through OpenAPI and can run on SQLite locally or PostgreSQL with Docker Compose.

## Why this is a portfolio project

This project demonstrates API design, authentication, relational data modeling, ownership-based access control, input validation, database migrations, pagination and filtering, containerization, and operational health checks. Each user's tasks and projects are scoped to their account. Passwords are hashed with Argon2; API access tokens are signed JWTs with configurable expiration.

## Features

- **Accounts:** register, log in, inspect the current account; Argon2 password hashing and expiring JWT bearer tokens
- **Tasks:** create, read, update, complete, and delete; statuses `todo`, `in_progress`, `done`; priorities `low`, `medium`, `high`, `urgent`
- **Organization:** projects with descriptions and colors; task tags, due dates, and optional project assignment
- **Discovery:** filter tasks by status, priority, project, tag, or due date; search title and description; sort and paginate results
- **Dashboard:** counts by workflow status and overdue tasks
- **Data and operations:** SQLAlchemy 2 ORM, Alembic migrations, SQLite development database, PostgreSQL deployment profile, Docker Compose, and `/healthz`
- **API docs:** interactive Swagger UI at `/docs` and ReDoc at `/redoc`

## Run locally

Requires Python 3.10 or newer.

```bash
py -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
Copy-Item .env.example .env   # Windows PowerShell; on macOS/Linux use: cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

The local default is SQLite in `taskflow.db`. Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) to explore the API. The original interactive CLI remains available with `python todo.py` and uses its own local data store.

## Run with Docker and PostgreSQL

```bash
Copy-Item .env.example .env   # or cp .env.example .env
# Replace SECRET_KEY in .env with a unique random value of at least 32 characters.
docker compose up --build
```

Compose starts PostgreSQL, waits for its health check, applies migrations, then starts the API. The database is stored in a named volume. `.env.example` contains local-only sample credentials; replace both `SECRET_KEY` and `POSTGRES_PASSWORD` before use, and configure secrets through the hosting provider for a public deployment.

## API walkthrough

Register and log in. The login response's `access_token` is used as a Bearer token for protected routes.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alex@example.com","full_name":"Alex Morgan","password":"change-this-password"}'

curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alex@example.com","password":"change-this-password"}'
```

Create a project, then create a task in that project:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/projects \
  -H "Authorization: Bearer YOUR_TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Job Search","description":"Applications and interview prep","color":"#4f46e5"}'

curl -X POST http://127.0.0.1:8000/api/v1/tasks \
  -H "Authorization: Bearer YOUR_TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Update portfolio","priority":"high","status":"todo","tags":["career","website"],"due_at":"2026-11-01T17:00:00Z","project_id":1}'
```

Useful endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/auth/register` | Create an account |
| `POST` | `/api/v1/auth/login` | Get a JWT access token |
| `GET` | `/api/v1/auth/me` | Get the signed-in account |
| `GET`, `POST` | `/api/v1/tasks` | List or create tasks |
| `GET`, `PATCH`, `DELETE` | `/api/v1/tasks/{task_id}` | Read, edit, or delete a task |
| `POST` | `/api/v1/tasks/{task_id}/complete` | Complete a task |
| `GET` | `/api/v1/tasks/stats` | Get the user's task summary |
| `GET`, `POST` | `/api/v1/projects` | List or create projects |
| `GET`, `PATCH`, `DELETE` | `/api/v1/projects/{project_id}` | Read, edit, or delete a project |
| `GET` | `/healthz` | Check API and database connectivity |

Task list query parameters include `status`, `priority`, `project_id`, `tag`, `search`, `due_before`, `sort`, `direction`, `limit` (maximum 100), and `offset`. Example: `GET /api/v1/tasks?status=todo&priority=high&sort=due&direction=asc&limit=20`.

## Configuration

Copy `.env.example` to `.env`. Settings can also be supplied through environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `APP_NAME` | API title | `TaskFlow API` |
| `ENVIRONMENT` | Runtime mode | `development` |
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///./taskflow.db` |
| `SECRET_KEY` | JWT signing key | Development-only key; set your own |
| `ACCESS_TOKEN_MINUTES` | Token lifetime | `30` |

Use `alembic upgrade head` after checkout and after pulling schema changes. Create a new migration with `alembic revision --autogenerate -m "describe change"`, review it, then commit it.

## Project structure

```text
app/
  config.py          environment configuration
  database.py        SQLAlchemy engine and sessions
  dependencies.py    authenticated-user dependency
  main.py            FastAPI application and health endpoint
  models.py          user, project, and task models
  schemas.py         request and response validation
  security.py        password hashing and JWT creation
  routers/           authentication, project, and task endpoints
migrations/          Alembic environment and initial schema
todo.py              original interactive CLI
```

## Resume description

**TaskFlow — Multi-user Task Management API | Python, FastAPI, SQLAlchemy, PostgreSQL, Docker**

Built a REST API for personal task and project management with JWT authentication, Argon2 password hashing, ownership-scoped CRUD, due dates, tags, priority workflows, search, filtering, and paginated results. Modeled relational data with SQLAlchemy and Alembic, added PostgreSQL container orchestration and health checks, and published interactive OpenAPI documentation.

Only list skills and deployment experience you can explain in an interview. A strong next step is to add automated endpoint tests and deploy a live demo with a small frontend client.
