# =============================================================================
# backend/routers/auth_router.py -- Register / Login / Me
# =============================================================================

from fastapi         import APIRouter, Depends, HTTPException
from pydantic        import BaseModel
from typing          import Optional
from sqlalchemy.orm  import Session

from database import get_db, User
from auth     import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    email:    Optional[str] = None
    phone:    Optional[str] = None
    password: str


class LoginRequest(BaseModel):
    email:    Optional[str] = None
    phone:    Optional[str] = None
    password: str


def user_dict(user: User) -> dict:
    return {"id": user.id, "email": user.email, "phone": user.phone}


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if not req.email and not req.phone:
        raise HTTPException(status_code=400, detail="Provide email or phone")

    if req.email and db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if req.phone and db.query(User).filter(User.phone == req.phone).first():
        raise HTTPException(status_code=400, detail="Phone already registered")

    user = User(
        email=req.email,
        phone=req.phone,
        hashed_password=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": user_dict(user)}


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = None
    if req.email:
        user = db.query(User).filter(User.email == req.email).first()
    elif req.phone:
        user = db.query(User).filter(User.phone == req.phone).first()
    else:
        raise HTTPException(status_code=400, detail="Provide email or phone")

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": user_dict(user)}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return user_dict(current_user)
