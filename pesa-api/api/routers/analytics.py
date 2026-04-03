"""
routers/analytics.py — Analytics Endpoint
==========================================

This is the most interesting route: it combines:
  1. Multiple async SQL queries (monthly spend, top categories)
  2. C++ moving average calculation via ctypes bridge
  3. C++ burn-rate forecast
  4. Budget overage detection

Route:
  GET /api/v1/analytics?months=3  → full analytics summary
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from api import models, schemas
from api.auth import get_current_active_user
from api.database import get_db
from api import engine_bridge

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "",
    response_model=schemas.AnalyticsResponse,
    summary="Get financial analytics summary",
)
async def get_analytics(
    months: int = Query(default=3, ge=1, le=12, description="Number of months to analyse"),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Returns a comprehensive analytics summary.

    Design note: we issue multiple targeted SQL queries rather than one
    giant JOIN. This is often faster in Postgres because:
      - Each query hits its optimal index
      - The planner doesn't have to handle a complex multi-join
      - Async allows issuing them concurrently (we could use asyncio.gather here)
    """
    now = datetime.now(timezone.utc)
    period_start = (now.replace(day=1) - timedelta(days=30 * (months - 1))).date()
    period_end   = now.date()

    # -------------------------------------------------------------------------
    # 1. Total income and expense for the period
    # -------------------------------------------------------------------------
    income_q = select(func.coalesce(func.sum(models.Transaction.amount), 0)).where(
        models.Transaction.user_id    == current_user.id,
        models.Transaction.type       == models.TransactionType.income,
        models.Transaction.created_at >= period_start,
    )
    expense_q = select(func.coalesce(func.sum(models.Transaction.amount), 0)).where(
        models.Transaction.user_id    == current_user.id,
        models.Transaction.type       == models.TransactionType.expense,
        models.Transaction.created_at >= period_start,
    )
    total_income  = Decimal((await db.execute(income_q)).scalar_one())
    total_expense = Decimal((await db.execute(expense_q)).scalar_one())
    net = total_income - total_expense

    # -------------------------------------------------------------------------
    # 2. Top spending categories
    # -------------------------------------------------------------------------
    cat_q = (
        select(
            models.Transaction.category,
            func.sum(models.Transaction.amount).label("total"),
        )
        .where(
            models.Transaction.user_id    == current_user.id,
            models.Transaction.type       == models.TransactionType.expense,
            models.Transaction.created_at >= period_start,
        )
        .group_by(models.Transaction.category)
        .order_by(func.sum(models.Transaction.amount).desc())
        .limit(3)
    )
    cat_rows = (await db.execute(cat_q)).all()

    top_categories = []
    for row in cat_rows:
        pct = float(row.total / total_expense * 100) if total_expense > 0 else 0.0
        top_categories.append(
            schemas.CategorySpend(
                category=row.category,
                total=Decimal(row.total),
                percentage=round(pct, 1),
            )
        )

    # -------------------------------------------------------------------------
    # 3. Monthly totals → feed into C++ moving average
    # -------------------------------------------------------------------------
    # This query groups transactions by month and sums expenses per month.
    # We use DATE_TRUNC via SQLAlchemy's text() for clarity.
    monthly_q = await db.execute(
        text("""
            SELECT
                TO_CHAR(DATE_TRUNC('month', created_at), 'YYYY-MM') AS month,
                SUM(amount) AS total
            FROM transactions
            WHERE
                user_id = :user_id
                AND type = 'expense'
                AND created_at >= :since
            GROUP BY DATE_TRUNC('month', created_at)
            ORDER BY DATE_TRUNC('month', created_at)
        """),
        {"user_id": str(current_user.id), "since": period_start},
    )
    monthly_rows = monthly_q.all()

    monthly_amounts = [float(r.total) for r in monthly_rows]
    monthly_labels  = [r.month for r in monthly_rows]

    # Call C++ moving average (window = min(3, available data))
    window = min(3, len(monthly_amounts))
    ma_values = engine_bridge.moving_average(monthly_amounts, window) if window >= 2 else None

    monthly_moving_avg = []
    for i, (label, amt) in enumerate(zip(monthly_labels, monthly_amounts)):
        # The moving average array is shorter than the input (length - window + 1).
        # Align: the first MA value corresponds to index (window - 1) in the input.
        ma_index = i - (window - 1)
        ma_val = ma_values[ma_index] if ma_values and ma_index >= 0 else None
        monthly_moving_avg.append(
            schemas.MonthlyMovingAverage(
                month=label,
                total_expense=Decimal(str(round(amt, 2))),
                moving_avg=round(ma_val, 2) if ma_val is not None else None,
            )
        )

    # -------------------------------------------------------------------------
    # 4. Burn-rate forecast — uses the most active budget
    # -------------------------------------------------------------------------
    burn_rate_forecast = None

    active_budget = await db.execute(
        select(models.Budget).where(
            models.Budget.user_id   == current_user.id,
            models.Budget.is_active == True,
        )
        .order_by(models.Budget.limit_amount.desc())
        .limit(1)
    )
    budget = active_budget.scalar_one_or_none()

    if budget:
        # Get daily expenses for this month so far
        daily_q = await db.execute(
            text("""
                SELECT
                    DATE(created_at AT TIME ZONE 'UTC') AS day,
                    SUM(amount) AS total
                FROM transactions
                WHERE
                    user_id    = :user_id
                    AND type   = 'expense'
                    AND category = :category
                    AND created_at >= DATE_TRUNC('month', NOW())
                GROUP BY DATE(created_at AT TIME ZONE 'UTC')
                ORDER BY day
            """),
            {"user_id": str(current_user.id), "category": budget.category},
        )
        daily_rows = daily_q.all()

        if daily_rows:
            daily_amounts = [float(r.total) for r in daily_rows]
            spent_so_far  = sum(daily_amounts)

            result = engine_bridge.burn_rate_forecast(
                daily_amounts,
                float(budget.limit_amount),
                spent_so_far,
            )
            if result:
                days_left = result["days_left"]
                if days_left == -1.0:
                    label = "No spending detected — budget intact"
                elif days_left <= 0:
                    label = "Budget exhausted"
                else:
                    label = f"Budget lasts ~{int(days_left)} more days at current rate"

                burn_rate_forecast = schemas.BurnRateForecast(
                    daily_rate=round(result["daily_rate"], 2),
                    days_left=round(days_left, 1),
                    forecast_label=label,
                )

    # -------------------------------------------------------------------------
    # 5. Budget overage alerts (from DB view)
    # -------------------------------------------------------------------------
    overages_q = await db.execute(
        text("""
            SELECT
                budget_id, category, limit_amount,
                total_spent, overage_amount, is_over_budget
            FROM v_budget_overages
            WHERE user_id = :user_id
        """),
        {"user_id": str(current_user.id)},
    )
    overage_rows = overages_q.all()
    overage_alerts = [
        schemas.BudgetOverageAlert(
            budget_id=row.budget_id,
            category=row.category,
            limit_amount=Decimal(str(row.limit_amount)),
            total_spent=Decimal(str(row.total_spent)),
            overage=Decimal(str(max(row.overage_amount, 0))),
            is_over=row.is_over_budget,
        )
        for row in overage_rows
    ]

    return schemas.AnalyticsResponse(
        period_start=period_start,
        period_end=period_end,
        total_income=total_income,
        total_expense=total_expense,
        net=net,
        top_categories=top_categories,
        monthly_moving_avg=monthly_moving_avg,
        burn_rate=burn_rate_forecast,
        overage_alerts=overage_alerts,
    )
