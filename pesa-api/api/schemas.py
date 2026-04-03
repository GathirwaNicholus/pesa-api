"""
schemas.py — Pydantic v2 Request/Response Schemas
===================================================

WHY separate schemas from ORM models?
--------------------------------------
ORM models (models.py) represent database rows.
Pydantic schemas represent the JSON that goes IN and OUT of your API.
They often differ:
  - Passwords come IN but never go OUT.
  - Computed fields (e.g. net_balance) go OUT but aren't stored.
  - Clients send subset fields on creation; full objects come back.

Keeping them separate is the "schema pattern" — it prevents accidentally
leaking sensitive DB fields (like hashed_password) in API responses.

Pydantic v2 improvements over v1:
  - 10–50x faster validation (Rust core)
  - model_config replaces class Config inner class
  - field_validator replaces @validator
  - model_validator replaces @root_validator
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator, field_validator

from api.models import BudgetPeriod, TransactionType


# ---------------------------------------------------------------------------
# Shared config mixin
# ---------------------------------------------------------------------------
class APIModel(BaseModel):
    """Base class for all schemas. Sets shared config once."""
    model_config = {
        "from_attributes": True,
        # from_attributes=True (was orm_mode=True in v1):
        # Allows Pydantic to read values from ORM objects via attribute access
        # (e.g. transaction.amount) instead of dict access (transaction["amount"]).
        # This is what makes response_model work seamlessly with SQLAlchemy objects.
    }


# ===========================================================================
# Auth schemas
# ===========================================================================

class UserCreate(APIModel):
    email: EmailStr                              # Pydantic validates email format
    password: str = Field(min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)


class UserResponse(APIModel):
    id: uuid.UUID
    email: EmailStr
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    # NOTE: hashed_password is intentionally absent — never expose it.


class Token(APIModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(APIModel):
    """Internal model for decoded JWT payload."""
    user_id: Optional[str] = None


class LoginRequest(APIModel):
    email: EmailStr
    password: str


# ===========================================================================
# Transaction schemas
# ===========================================================================

class TransactionCreate(APIModel):
    amount: Decimal = Field(gt=0, decimal_places=2)
    # Decimal for money — no floating-point precision errors.
    # gt=0 means strictly greater than zero.
    currency: str   = Field(default="KES", min_length=3, max_length=3)
    category: str   = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    type: TransactionType

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        """ISO 4217 codes are always uppercase."""
        return v.upper()


class TransactionUpdate(APIModel):
    """Partial update — all fields optional (PATCH semantics)."""
    amount:      Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    currency:    Optional[str]     = Field(None, min_length=3, max_length=3)
    category:    Optional[str]     = Field(None, min_length=1, max_length=100)
    description: Optional[str]     = None
    type:        Optional[TransactionType] = None


class TransactionResponse(APIModel):
    id:          uuid.UUID
    user_id:     uuid.UUID
    amount:      Decimal
    currency:    str
    category:    str
    description: Optional[str]
    type:        TransactionType
    created_at:  datetime


class TransactionList(APIModel):
    """Paginated list response."""
    items: list[TransactionResponse]
    total: int
    page:  int
    size:  int


# ===========================================================================
# Budget schemas
# ===========================================================================

class BudgetCreate(APIModel):
    category:     str     = Field(min_length=1, max_length=100)
    limit_amount: Decimal = Field(gt=0, decimal_places=2)
    period:       BudgetPeriod = BudgetPeriod.monthly
    start_date:   date


class BudgetUpdate(APIModel):
    limit_amount: Optional[Decimal] = Field(None, gt=0)
    period:       Optional[BudgetPeriod] = None
    is_active:    Optional[bool] = None


class BudgetResponse(APIModel):
    id:           uuid.UUID
    user_id:      uuid.UUID
    category:     str
    limit_amount: Decimal
    period:       BudgetPeriod
    start_date:   date
    is_active:    bool
    created_at:   datetime


class BudgetOverageAlert(APIModel):
    budget_id:    uuid.UUID
    category:     str
    limit_amount: Decimal
    total_spent:  Decimal
    overage:      Decimal
    is_over:      bool


# ===========================================================================
# Analytics schemas
# ===========================================================================

class CategorySpend(APIModel):
    category:    str
    total:       Decimal
    percentage:  float    # percentage of total expense


class MonthlyMovingAverage(APIModel):
    month:        str     # "2025-01", "2025-02", etc.
    total_expense: Decimal
    moving_avg:   Optional[float]  # None for months before window fills


class BurnRateForecast(APIModel):
    daily_rate:  float
    days_left:   float         # -1 means infinite (no spending)
    forecast_label: str        # human-readable: "Budget lasts ~14 more days"


class AnalyticsResponse(APIModel):
    period_start:        date
    period_end:          date
    total_income:        Decimal
    total_expense:       Decimal
    net:                 Decimal    # income - expense
    top_categories:      list[CategorySpend]
    monthly_moving_avg:  list[MonthlyMovingAverage]
    burn_rate:           Optional[BurnRateForecast]  # None if no active budget
    overage_alerts:      list[BudgetOverageAlert]


# ===========================================================================
# Health check
# ===========================================================================

class HealthResponse(APIModel):
    status:   str
    version:  str
    database: str    # "connected" | "error"
