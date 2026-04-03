"""
routers/budgets.py — Budget CRUD Endpoints
==========================================

Routes:
  POST   /api/v1/budgets       → create budget
  GET    /api/v1/budgets       → list budgets
  PATCH  /api/v1/budgets/{id}  → update
  DELETE /api/v1/budgets/{id}  → delete
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api import models, schemas
from api.auth import get_current_active_user
from api.database import get_db

router = APIRouter(prefix="/budgets", tags=["Budgets"])


@router.post(
    "",
    response_model=schemas.BudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a budget for a category",
)
async def create_budget(
    budget_in: schemas.BudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    # Check for duplicate active budget in same category+period
    existing = await db.execute(
        select(models.Budget).where(
            models.Budget.user_id   == current_user.id,
            models.Budget.category  == budget_in.category,
            models.Budget.period    == budget_in.period,
            models.Budget.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Active {budget_in.period} budget for '{budget_in.category}' already exists. "
                   "Update or deactivate it first.",
        )

    budget = models.Budget(
        user_id=current_user.id,
        category=budget_in.category,
        limit_amount=budget_in.limit_amount,
        period=budget_in.period,
        start_date=budget_in.start_date,
    )
    db.add(budget)
    await db.flush()
    return budget


@router.get(
    "",
    response_model=list[schemas.BudgetResponse],
    summary="List all budgets for the current user",
)
async def list_budgets(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    q = select(models.Budget).where(models.Budget.user_id == current_user.id)
    if active_only:
        q = q.where(models.Budget.is_active == True)
    q = q.order_by(models.Budget.category)

    result = await db.execute(q)
    return result.scalars().all()


@router.patch(
    "/{budget_id}",
    response_model=schemas.BudgetResponse,
    summary="Update a budget",
)
async def update_budget(
    budget_id: uuid.UUID,
    budget_update: schemas.BudgetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    budget = await _get_budget_or_404(budget_id, current_user.id, db)
    update_data = budget_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(budget, field, value)
    await db.flush()
    return budget


@router.delete(
    "/{budget_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a budget",
)
async def delete_budget(
    budget_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    budget = await _get_budget_or_404(budget_id, current_user.id, db)
    await db.delete(budget)


async def _get_budget_or_404(
    budget_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> models.Budget:
    result = await db.execute(
        select(models.Budget).where(
            models.Budget.id      == budget_id,
            models.Budget.user_id == user_id,
        )
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found",
        )
    return budget
