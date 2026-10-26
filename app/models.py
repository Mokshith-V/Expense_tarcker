"""SQLAlchemy models: one class per MySQL table."""
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # One user has many categories and many expenses.
    # cascade="all, delete-orphan": deleting a user deletes their data too.
    categories = relationship("Category", back_populates="owner", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="owner", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"
    # The same user can't have two categories with the same name,
    # but two different users can both have "Food".
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_category_owner_name"),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    monthly_budget = Column(Numeric(12, 2), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    owner = relationship("User", back_populates="categories")
    # No delete cascade here: deleting a category keeps its expenses,
    # and SQLAlchemy sets their category_id to NULL ("uncategorised").
    expenses = relationship("Expense", back_populates="category")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    # Numeric(12, 2) = MySQL DECIMAL(12,2): exact money, never float rounding errors.
    amount = Column(Numeric(12, 2), nullable=False)
    description = Column(String(255), nullable=False)
    spent_on = Column(Date, nullable=False, index=True)
    payment_method = Column(String(20), nullable=False, default="cash")
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    owner = relationship("User", back_populates="expenses")
    category = relationship("Category", back_populates="expenses")
