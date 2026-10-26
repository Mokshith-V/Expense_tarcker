"""Register, log in, and "who am I"."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from ..deps import CurrentUser, DbSession
from ..models import Category, User
from ..schemas import Token, UserCreate, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Every new user starts with these categories.
DEFAULT_CATEGORIES = ["Food", "Transport", "Bills", "Shopping", "Entertainment", "Health", "Other"]


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def register(body: UserCreate, db: DbSession):
    taken = db.query(User).filter(
        or_(User.username == body.username, User.email == body.email)
    ).first()
    if taken:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Username or email is already registered")

    user = User(
        username=body.username,
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
    )
    # Thanks to the relationship, these are inserted together with the user
    # and get owner_id filled in automatically.
    user.categories = [Category(name=name) for name in DEFAULT_CATEGORIES]

    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two requests registering the same name at the same moment
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Username or email is already registered")
    db.refresh(user)
    return user


@router.post("/token", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    user = db.query(User).filter(User.username == form.username).first()
    # Same message for "no such user" and "wrong password",
    # so attackers can't find out which usernames exist.
    if user is None or not user.is_active or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id, user.username))


@router.get("/me", response_model=UserOut)
def read_me(user: CurrentUser):
    return user
