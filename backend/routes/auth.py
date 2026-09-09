from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from core.deps import get_current_user
from core.security import hash_password, verify_password, create_access_token
from database.session import get_db
from models.user import User, UserRole
from schemas.auth import UserSignup, UserLogin, Token, UserOut

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(payload: UserSignup, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Public signup always creates a normal "user" account.
    # Admin accounts are created via the seeded first-admin or promoted
    # by an existing admin (see routes/admin.py) — never self-assigned here.
    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # form_data.username is used as the email field (OAuth2 password flow standard)
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token(data={"sub": user.id, "role": user.role.value})
    return Token(access_token=token, role=user.role)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
