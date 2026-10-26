"""Spending summaries, calculated by MySQL with GROUP BY."""
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import extract, func

from ..deps import CurrentUser, DbSession
from ..models import Category, Expense
from ..schemas import CategoryTotal, MonthlyReport, MonthTotal, YearlyReport

router = APIRouter(prefix="/reports", tags=["reports"])

ZERO = Decimal("0.00")
Year = Annotated[int | None, Query(ge=2000, le=2100, description="Defaults to the current year")]
Month = Annotated[int | None, Query(ge=1, le=12, description="Defaults to the current month")]


def month_range(year: int, month: int) -> tuple[date, date]:
    """First day of the month, and first day of the NEXT month (exclusive end)."""
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


@router.get("/monthly", response_model=MonthlyReport)
def monthly_report(user: CurrentUser, db: DbSession, year: Year = None, month: Month = None):
    today = date.today()
    year = year or today.year
    month = month or today.month
    start, end = month_range(year, month)

    total_spent = func.sum(Expense.amount)
    # SQL: SELECT category, SUM(amount), COUNT(*) ... GROUP BY category
    # LEFT OUTER JOIN so uncategorised expenses (category_id NULL) are included.
    rows = (
        db.query(
            Expense.category_id,
            Category.name.label("category_name"),
            Category.monthly_budget,
            total_spent.label("total"),
            func.count(Expense.id).label("n"),  # not "count": Row already has a .count() method
        )
        .outerjoin(Category, Expense.category_id == Category.id)
        .filter(Expense.owner_id == user.id, Expense.spent_on >= start, Expense.spent_on < end)
        .group_by(Expense.category_id, Category.name, Category.monthly_budget)
        .order_by(total_spent.desc())
        .all()
    )

    by_category = []
    for row in rows:
        total = row.total or ZERO
        budget = row.monthly_budget
        remaining = budget - total if budget is not None else None
        by_category.append(CategoryTotal(
            category_id=row.category_id,
            category_name=row.category_name or "Uncategorised",
            total=total,
            count=row.n,
            monthly_budget=budget,
            remaining=remaining,
            over_budget=remaining is not None and remaining < 0,
        ))

    return MonthlyReport(
        year=year,
        month=month,
        total=sum((c.total for c in by_category), ZERO),
        count=sum(c.count for c in by_category),
        by_category=by_category,
    )


@router.get("/yearly", response_model=YearlyReport)
def yearly_report(user: CurrentUser, db: DbSession, year: Year = None):
    year = year or date.today().year
    month_of = extract("month", Expense.spent_on)

    rows = (
        db.query(
            month_of.label("month"),
            func.sum(Expense.amount).label("total"),
            func.count(Expense.id).label("n"),
        )
        .filter(
            Expense.owner_id == user.id,
            Expense.spent_on >= date(year, 1, 1),
            Expense.spent_on < date(year + 1, 1, 1),
        )
        .group_by(month_of)
        .all()
    )
    found = {int(row.month): row for row in rows}

    # Always return all 12 months, with zeros where nothing was spent.
    months = [
        MonthTotal(
            month=m,
            total=(found[m].total or ZERO) if m in found else ZERO,
            count=found[m].n if m in found else 0,
        )
        for m in range(1, 13)
    ]
    return YearlyReport(
        year=year,
        total=sum((m.total for m in months), ZERO),
        count=sum(m.count for m in months),
        months=months,
    )
