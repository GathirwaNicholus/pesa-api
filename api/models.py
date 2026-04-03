"""
models.py — SQLAlchemy ORM Models (the "M" in MVC)
===================================================

WHY ORM Models?
---------------
ORM (Object-Relational Mapping) lets us work with Python objects instead of
raw SQL strings. SQLAlchemy translates Python operations into SQL automatically:
    session.add(transaction)  →  INSERT INTO transactions ...
    await session.get(User, id)  →  SELECT * FROM users WHERE id = ...

This has three benefits:
1. Type safety — your IDE knows the shape of User, Transaction, etc.
2. Composability — build queries programmatically without string concatenation.
3. Database agnosticism — swap Postgres for SQLite in tests by changing the URL.

The models here mirror the SQL schema in 001_init.sql exactly.
"""

import uuid
from datetime import datetime, date
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey,
    Numeric, String, Text, Enum as SAEnum, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from api.database import Base


# ---------------------------------------------------------------------------
# Python Enums — these feed SQLAlchemy's SAEnum which generates Postgres ENUMs
# ---------------------------------------------------------------------------
class TransactionType(str, PyEnum):
    income  = "income"
    expense = "expense"


class BudgetPeriod(str, PyEnum):
    weekly  = "weekly"
    monthly = "monthly"


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),            # as_uuid=True: Python gets a uuid.UUID, not a string
        primary_key=True,
        default=uuid.uuid4,            # generate UUID in Python (no DB round-trip needed)
    )
    email: str       = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password: str = Column(Text, nullable=False)
    full_name: str   = Column(String(255), nullable=True)
    is_active: bool  = Column(Boolean, default=True, nullable=False)
    created_at: datetime = Column(
        DateTime(timezone=True),       # timezone=True → TIMESTAMPTZ in Postgres
        server_default=func.now(),
        # server_default=func.now(): the DB generates this value, not Python.
        # This means the timestamp is always consistent, even if clocks drift.
    )

    # Relationships — these let us do user.transactions in Python without
    # writing a JOIN. SQLAlchemy issues a SELECT automatically.
    transactions = relationship("Transaction", back_populates="user", lazy="select")
    budgets      = relationship("Budget",      back_populates="user", lazy="select")
    # lazy="select": load related objects when first accessed (not eagerly upfront).
    # In async code we use selectinload() explicitly instead, but this default
    # is safe as a fallback.


# ---------------------------------------------------------------------------
# Transaction model
# ---------------------------------------------------------------------------
class Transaction(Base):
    __tablename__ = "transactions"

    id: uuid.UUID   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: float    = Column(Numeric(12, 2), nullable=False)
    currency: str    = Column(String(3), nullable=False, default="KES")
    category: str    = Column(String(100), nullable=False, index=True)
    description: str = Column(Text, nullable=True)
    type: TransactionType = Column(
        SAEnum(TransactionType, name="transaction_type", create_type=False),
        # create_type=False: the ENUM type already exists in Postgres (from migration).
        # If True, SQLAlchemy would try to CREATE TYPE again → error.
        nullable=False,
    )
    created_at: datetime = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    user = relationship("User", back_populates="transactions")


# ---------------------------------------------------------------------------
# Budget model
# ---------------------------------------------------------------------------
class Budget(Base):
    __tablename__ = "budgets"

    id: uuid.UUID      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: str      = Column(String(100), nullable=False)
    limit_amount: float = Column(Numeric(12, 2), nullable=False)
    period: BudgetPeriod = Column(
        SAEnum(BudgetPeriod, name="budget_period", create_type=False),
        nullable=False,
        default=BudgetPeriod.monthly,
    )
    start_date: date   = Column(Date, nullable=False)
    is_active: bool    = Column(Boolean, default=True, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="budgets")
