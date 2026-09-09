from pydantic import BaseModel, EmailStr, Field
from models.user import UserRole


class UserSignup(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    # Only used if you want to allow admin self-signup with an invite code;
    # otherwise the first admin is auto-created and future admins are
    # promoted via the /admin/users/{id}/promote endpoint.
    role: UserRole = UserRole.user


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole


class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True
