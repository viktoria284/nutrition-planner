from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.schemas.user import UserCreate, UserOut, UserUpdateMe
from app.services.security import create_access_token, hash_password, verify_password
from app.services.users import (
    create_user,
    get_user_by_email,
    get_user_by_identifier,
    get_user_by_username,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if get_user_by_email(db, payload.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    if get_user_by_username(db, payload.username):
        raise HTTPException(status_code=409, detail="Username already taken")

    user = create_user(
        db=db,
        email=payload.email,
        username=payload.username,
        display_name=payload.display_name,
        hashed_password=hash_password(payload.password),
    )
    return user


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # form.username = identifier (email OR username)
    identifier = (form.username or "").strip().lower()

    user = get_user_by_identifier(db, identifier)
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(subject=str(user.id))
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
def update_me(payload: UserUpdateMe, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    update_data = payload.model_dump(exclude_unset=True)

    next_email = update_data.get("email")
    if next_email is not None and next_email != current_user.email:
        existing = get_user_by_email(db, next_email)
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=409, detail="Email already registered")
        current_user.email = next_email

    next_username = update_data.get("username")
    if next_username is not None and next_username != current_user.username:
        existing = get_user_by_username(db, next_username)
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=409, detail="Username already taken")
        current_user.username = next_username

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user
