"""CRUD for expenses, plus filtering, sorting and pagination."""
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from ..deps import CurrentUser, DbSession
from ..models import Category, Expense, User
from ..schemas import (
    ExpenseCreate,
    ExpenseOut,
    ExpensePage,
    ExpenseUpdate,
    PaymentMethod,
    SortOrder,
)

router = APIRouter(prefix="/expenses", tags=["expenses"])

ExpenseId = Annotated[int, Path(gt=0)]

# The id is a tie-breaker so the order is stable when dates or amounts are equal.
SORT_COLUMNS = {
    SortOrder.newest: (Expense.spent_on.desc(), Expense.id.desc()),
    SortOrder.oldest: (Expense.spent_on.asc(), Expense.id.asc()),
    SortOrder.highest: (Expense.amount.desc(), Expense.id.desc()),
    SortOrder.lowest: (Expense.amount.asc(), Expense.id.asc()),
}


def get_owned_expense(db: Session, user: User, expense_id: int) -> Expense:
    expense = db.query(Expense).filter(
        Expense.id == expense_id, Expense.owner_id == user.id
    ).first()
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    return expense


def ensure_own_category(db: Session, user: User, category_id: int | None) -> None:
    """Stop users from filing expenses under someone else's category."""
    if category_id is None:
        return
    exists = db.query(Category.id).filter(
        Category.id == category_id, Category.owner_id == user.id
    ).first()
    if exists is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="category_id does not match any of your categories")


@router.get("", response_model=ExpensePage)
def list_expenses(
    user: CurrentUser,
    db: DbSession,
    start_date: date | None = None,
    end_date: date | None = None,
    category_id: Annotated[int | None, Query(gt=0)] = None,
    uncategorised: bool = False,
    payment_method: PaymentMethod | None = None,
    min_amount: Annotated[Decimal | None, Query(ge=0)] = None,
    max_amount: Annotated[Decimal | None, Query(ge=0)] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    sort: SortOrder = SortOrder.newest,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="start_date must be on or before end_date")

    # Build the query step by step; nothing runs until .count() / .all().
    query = db.query(Expense).filter(Expense.owner_id == user.id)
    if start_date:
        query = query.filter(Expense.spent_on >= start_date)
    if end_date:
        query = query.filter(Expense.spent_on <= end_date)
    if uncategorised:
        query = query.filter(Expense.category_id.is_(None))
    elif category_id is not None:
        query = query.filter(Expense.category_id == category_id)
    if payment_method is not None:
        query = query.filter(Expense.payment_method == payment_method.value)
    if min_amount is not None:
        query = query.filter(Expense.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(Expense.amount <= max_amount)
    if search:
        query = query.filter(Expense.description.ilike(f"%{search}%"))

    total = query.count()  # matches across ALL pages
    rows = query.order_by(*SORT_COLUMNS[sort]).offset(offset).limit(limit).all()

    return ExpensePage(
        total=total,
        limit=limit,
        offset=offset,
        items=[ExpenseOut.model_validate(row) for row in rows],
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ExpenseOut)
def create_expense(body: ExpenseCreate, user: CurrentUser, db: DbSession):
    ensure_own_category(db, user, body.category_id)
    expense = Expense(**body.model_dump(), owner_id=user.id)
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.get("/{expense_id}", response_model=ExpenseOut)
def read_expense(expense_id: ExpenseId, user: CurrentUser, db: DbSession):
    return get_owned_expense(db, user, expense_id)


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(expense_id: ExpenseId, body: ExpenseUpdate, user: CurrentUser, db: DbSession):
    expense = get_owned_expense(db, user, expense_id)
    changes = body.model_dump(exclude_unset=True)  # only the fields the client sent
    if "category_id" in changes:
        ensure_own_category(db, user, changes["category_id"])
    for field, value in changes.items():
        setattr(expense, field, value)
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: ExpenseId, user: CurrentUser, db: DbSession):
    expense = get_owned_expense(db, user, expense_id)
    db.delete(expense)
    db.commit()
