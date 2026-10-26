"""Pydantic schemas: the JSON shapes clients send (…Create / …Update) and receive (…Out)."""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

# A reusable "money" type: positive, at most 12 digits, at most 2 after the point.
Money = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Budget = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class PaymentMethod(str, Enum):
    cash = "cash"
    card = "card"
    upi = "upi"
    netbanking = "netbanking"
    other = "other"


def _reject_nulls(model: BaseModel, fields: tuple[str, ...]) -> None:
    """For PATCH bodies: a field may be left out, but not sent as null."""
    for name in fields:
        if name in model.model_fields_set and getattr(model, name) is None:
            raise ValueError(f"{name} cannot be null")


# ---------- Users & auth ----------

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=100)
    # bcrypt only looks at the first 72 bytes of a password.
    password: str = Field(min_length=8, max_length=72)

    model_config = ConfigDict(json_schema_extra={"example": {
        "username": "mokshith",
        "email": "mokshith@example.com",
        "full_name": "Mokshith Vooka",
        "password": "a-strong-password",
    }})


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Categories ----------

class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    monthly_budget: Budget | None = None

    model_config = ConfigDict(str_strip_whitespace=True)  # "  Food " -> "Food"


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    monthly_budget: Budget | None = None  # send null to remove the budget

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def _check_nulls(self):
        _reject_nulls(self, ("name",))
        return self


class CategoryOut(BaseModel):
    id: int
    name: str
    monthly_budget: Decimal | None

    model_config = ConfigDict(from_attributes=True)


class CategoryBrief(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


# ---------- Expenses ----------

class ExpenseCreate(BaseModel):
    amount: Money
    description: str = Field(min_length=1, max_length=255)
    spent_on: date = Field(default_factory=date.today)
    payment_method: PaymentMethod = PaymentMethod.cash
    category_id: int | None = Field(default=None, gt=0)

    # Store the enum's plain value ("upi"), not the Enum object.
    model_config = ConfigDict(use_enum_values=True, json_schema_extra={"example": {
        "amount": "249.50",
        "description": "Lunch with team",
        "spent_on": "2026-10-26",
        "payment_method": "upi",
        "category_id": 1,
    }})


class ExpenseUpdate(BaseModel):
    """PATCH body: send only the fields you want to change."""
    amount: Money | None = None
    description: str | None = Field(default=None, min_length=1, max_length=255)
    spent_on: date | None = None
    payment_method: PaymentMethod | None = None
    category_id: int | None = Field(default=None, gt=0)  # send null to uncategorise

    model_config = ConfigDict(use_enum_values=True)

    @model_validator(mode="after")
    def _check_nulls(self):
        _reject_nulls(self, ("amount", "description", "spent_on", "payment_method"))
        return self


class ExpenseOut(BaseModel):
    id: int
    amount: Decimal
    description: str
    spent_on: date
    payment_method: str
    category: CategoryBrief | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExpensePage(BaseModel):
    total: int          # how many expenses match the filters, across all pages
    limit: int
    offset: int
    items: list[ExpenseOut]


class SortOrder(str, Enum):
    newest = "newest"
    oldest = "oldest"
    highest = "highest"
    lowest = "lowest"


# ---------- Reports ----------

class CategoryTotal(BaseModel):
    category_id: int | None
    category_name: str
    total: Decimal
    count: int
    monthly_budget: Decimal | None
    remaining: Decimal | None   # budget - total (negative = over budget)
    over_budget: bool


class MonthlyReport(BaseModel):
    year: int
    month: int
    total: Decimal
    count: int
    by_category: list[CategoryTotal]


class MonthTotal(BaseModel):
    month: int
    total: Decimal
    count: int


class YearlyReport(BaseModel):
    year: int
    total: Decimal
    count: int
    months: list[MonthTotal]
