from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.security import hash_password
from database.session import Base, engine, SessionLocal
from models.user import User, UserRole
from routes import auth, admin, sessions

app = FastAPI(
    title="Support Simulator - Backend",
    description=(
        "Auth (admin/user roles), FAQ/policy document upload, "
        "conversation creation, and admin dashboard summary APIs."
    ),
    version="1.0.0",
)

# Allow the frontend (Member 3 / Member 5) to call this API during development.
# Tighten this list before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(sessions.router)


@app.on_event("startup")
def on_startup():
    # Create tables if they don't exist yet.
    # For production, swap this for Alembic migrations (see alembic/ folder).
    Base.metadata.create_all(bind=engine)

    # Seed a first admin account so someone can log in and start uploading
    # documents / promoting other users, even on a brand new database.
    db = SessionLocal()
    try:
        existing_admin = db.query(User).filter(User.role == UserRole.admin).first()
        if not existing_admin:
            admin_user = User(
                name=settings.FIRST_ADMIN_NAME,
                email=settings.FIRST_ADMIN_EMAIL,
                hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
                role=UserRole.admin,
            )
            db.add(admin_user)
            db.commit()
            print(f"[startup] Seeded first admin: {settings.FIRST_ADMIN_EMAIL}")
    finally:
        db.close()


@app.get("/")
def root():
    return {"status": "ok", "service": "support-simulator-backend"}


@app.get("/health")
def health():
    return {"status": "healthy"}
