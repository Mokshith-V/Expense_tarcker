"""CRUD for the current user's categories."""
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..deps import CurrentUser, DbSession
from ..models import Category, User
from ..schemas import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])

CategoryId = Annotated[int, Path(gt=0)]


def get_owned_category(db: Session, user: User, category_id: int) -> Category:
    """Return the category if it exists AND belongs to this user, else 404.

    Another user's category gets the same 404 as a missing one,
    so nobody can probe which ids exist.
    """
    category = db.query(Category).filter(
        Category.id == category_id, Category.owner_id == user.id
    ).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


def ensure_name_free(db: Session, user: User, name: str, exclude_id: int | None = None) -> None:
    query = db.query(Category).filter(
        Category.owner_id == user.id, func.lower(Category.name) == name.lower()
    )
    if exclude_id is not None:
        query = query.filter(Category.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"You already have a category named '{name}'")


@router.get("", response_model=list[CategoryOut])
def list_categories(user: CurrentUser, db: DbSession):
    return db.query(Category).filter(Category.owner_id == user.id).order_by(Category.name).all()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CategoryOut)
def create_category(body: CategoryCreate, user: CurrentUser, db: DbSession):
    ensure_name_free(db, user, body.name)
    category = Category(**body.model_dump(), owner_id=user.id)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/{category_id}", response_model=CategoryOut)
def read_category(category_id: CategoryId, user: CurrentUser, db: DbSession):
    return get_owned_category(db, user, category_id)


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(category_id: CategoryId, body: CategoryUpdate, user: CurrentUser, db: DbSession):
    category = get_owned_category(db, user, category_id)
    changes = body.model_dump(exclude_unset=True)  # only the fields the client sent
    if "name" in changes:
        ensure_name_free(db, user, changes["name"], exclude_id=category.id)
    for field, value in changes.items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: CategoryId, user: CurrentUser, db: DbSession):
    category = get_owned_category(db, user, category_id)
    db.delete(category)  # its expenses stay, with category_id set to NULL
    db.commit()
