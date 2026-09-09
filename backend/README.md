# Support Simulator — Backend (Member 1: Backend + Database)

FastAPI + MySQL backend implementing:
- Login/signup with **admin** and **user** roles (JWT auth)
- Admin: upload FAQ / policy documents, view customer conversation history & summaries, manage users
- User: create and hold conversations (sessions), send messages
- Tables Member 2 (agents) and Member 4 (RAG) plug straight into: `sessions`, `messages`, `session_results`, `documents`

## 1. Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
- `DATABASE_URL` — point it at your MySQL instance. Create the database first:
  ```sql
  CREATE DATABASE support_simulator CHARACTER SET utf8mb4;
  ```
- `SECRET_KEY` — set a real random string (`python -c "import secrets; print(secrets.token_hex(32))"`)
- `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` — credentials for the admin account that's auto-created on first run

## 2. Run

```bash
uvicorn main:app --reload
```

Tables are created automatically on startup (`Base.metadata.create_all`), and a first admin user is seeded if none exists. Swap this for Alembic migrations before going to production.

API docs: http://localhost:8000/docs

## 3. Roles

| Role  | Can do |
|-------|--------|
| admin | Upload/delete FAQ & policy documents, view all conversations + summaries, list/promote users |
| user  | Sign up, log in, create sessions (conversations), send messages, view own history |

The **first admin** is seeded from `.env`. To make another user an admin, log in as an existing admin and call `POST /api/admin/users/{user_id}/promote`.

## 4. API Contract (for the whole team)

### Auth
```
POST /api/auth/signup          { name, email, password }              -> creates a "user" role account
POST /api/auth/login            (form: username=email, password)      -> { access_token, role }
GET  /api/auth/me               (auth required)                       -> current user profile
```
Send the token as `Authorization: Bearer <token>` on every other request.

### User — Conversations
```
POST /api/sessions                        { mode, product, scenario, customer_mood, difficulty }
GET  /api/sessions                         -> list of my sessions
GET  /api/sessions/{id}                    -> session + messages + result
POST /api/sessions/{id}/messages           { sender, content }        -> sender: customer|support|coach|system
POST /api/sessions/{id}/complete           -> marks session completed
POST /api/sessions/{id}/result             { summary, score, feedback } -> saved by orchestrator/coach agent
```

### Admin — Documents (FAQ / policy)
```
POST   /api/admin/documents/upload   (multipart: file, category, description)
GET    /api/admin/documents          -> list all uploaded documents (+ ingestion_status for Member 4's RAG job)
DELETE /api/admin/documents/{id}
```

### Admin — Dashboard
```
GET /api/admin/dashboard/conversations   -> all users' conversations with summary + score
GET /api/admin/users                     -> all users
POST /api/admin/users/{id}/promote       -> make a user an admin
```

## 5. Where this plugs into the rest of the team

- **Member 2 (Agents/Orchestrator)** calls `POST /api/sessions/{id}/messages` to log each agent turn, and `POST /api/sessions/{id}/result` after the coach agent scores the conversation.
- **Member 4 (RAG)** reads `GET /api/admin/documents` (or the `documents` table directly) to know which files to ingest/chunk/embed, and can update `ingestion_status` once processed.
- **Member 3 (Session config UI)** calls `POST /api/sessions` when the user clicks "Start Session".
- **Member 5 (Frontend/Integration)** wires the chat UI to the messages endpoints and the admin dashboard UI to `/api/admin/dashboard/conversations`.

## 6. Project structure

```
backend/
├── main.py                 # FastAPI app, CORS, startup DB init + admin seed
├── core/
│   ├── config.py            # env-based settings
│   ├── security.py          # password hashing + JWT
│   └── deps.py               # get_current_user / get_current_admin
├── database/
│   └── session.py            # SQLAlchemy engine/session/Base
├── models/                  # SQLAlchemy ORM models (users, sessions, messages, session_results, documents)
├── schemas/                 # Pydantic request/response models
└── routes/
    ├── auth.py               # signup/login/me
    ├── admin.py               # document upload, dashboard, user management
    └── sessions.py            # create session, messages, results
```
