"""
routers/transactions.py — Transaction CRUD Endpoints
=====================================================

Routes:
  POST   /api/v1/transactions          → create transaction
  GET    /api/v1/transactions          → list (paginated, filterable)
  GET    /api/v1/transactions/{id}     → get single
  PATCH  /api/v1/transactions/{id}     → partial update
  DELETE /api/v1/transactions/{id}     → delete
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api import models, schemas
from api.auth import get_current_active_user
from api.database import get_db

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post(
    "",
    response_model=schemas.TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new transaction",
)
async def create_transaction(
    tx_in: schemas.TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    The user_id is taken from the JWT, not the request body.
    Users cannot create transactions for other users — enforced here,
    not just by UI convention.
    """
    tx = models.Transaction(
        user_id=current_user.id,
        amount=tx_in.amount,
        currency=tx_in.currency,
        category=tx_in.category,
        description=tx_in.description,
        type=tx_in.type,
    )
    db.add(tx)
    await db.flush()
    return tx


@router.get(
    "",
    response_model=schemas.TransactionList,
    summary="List transactions with pagination and filters",
)
async def list_transactions(
    # Query parameters with validation and defaults:
    page:     int = Query(default=1, ge=1, description="Page number (1-based)"),
    size:     int = Query(default=20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    type:     Optional[models.TransactionType] = Query(None, description="income or expense"),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Paginated list of the current user's transactions.

    WHY manual pagination (LIMIT/OFFSET) instead of a cursor?
    OFFSET pagination is simpler to implement and good enough for most use cases.
    Cursor-based pagination (WHERE id > last_seen_id) is better for large datasets
    or real-time feeds but requires more complex implementation.
    """
    # Build filters dynamically — only add conditions that have values
    conditions = [models.Transaction.user_id == current_user.id]
    if category:
        conditions.append(models.Transaction.category == category)
    if type:
        conditions.append(models.Transaction.type == type)

    # Count total (for pagination metadata)
    count_q = select(func.count()).select_from(models.Transaction).where(and_(*conditions))
    total = (await db.execute(count_q)).scalar_one()

    # Fetch the page
    offset = (page - 1) * size
    rows_q = (
        select(models.Transaction)
        .where(and_(*conditions))
        .order_by(models.Transaction.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(rows_q)
    items = result.scalars().all()
    # .scalars() unwraps the Row objects to give us Transaction ORM instances directly.

    return schemas.TransactionList(items=items, total=total, page=page, size=size)


@router.get(
    "/{transaction_id}",
    response_model=schemas.TransactionResponse,
    summary="Get a single transaction",
)
async def get_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    tx = await _get_tx_or_404(transaction_id, current_user.id, db)
    return tx


@router.patch(
    "/{transaction_id}",
    response_model=schemas.TransactionResponse,
    summary="Partially update a transaction",
)
async def update_transaction(
    transaction_id: uuid.UUID,
    tx_update: schemas.TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    PATCH (partial update) vs PUT (full replace):
    - PUT requires the client to send the entire object every time.
    - PATCH sends only the fields that changed.
    - We use model_dump(exclude_unset=True) to get only fields the client sent.
    """
    tx = await _get_tx_or_404(transaction_id, current_user.id, db)

    update_data = tx_update.model_dump(exclude_unset=True)
    # exclude_unset=True: skip fields that weren't included in the request.
    # This prevents overwriting existing values with None unintentionally.

    for field, value in update_data.items():
        setattr(tx, field, value)

    await db.flush()
    return tx


@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a transaction",
)
async def delete_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    204 No Content: successful DELETE returns no response body.
    This is the correct HTTP status for a successful delete.
    """
    tx = await _get_tx_or_404(transaction_id, current_user.id, db)
    await db.delete(tx)
    # db.delete() marks the object for deletion; actual DELETE SQL runs on flush/commit.


# ---------------------------------------------------------------------------
# Private helper
# ---------------------------------------------------------------------------
async def _get_tx_or_404(
    transaction_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> models.Transaction:
    """
    Fetch a transaction belonging to the user, or raise 404.

    WHY check user_id here?
    An attacker could guess another user's transaction UUID and try
    GET /transactions/<other-user-uuid>. Filtering by BOTH transaction_id
    AND user_id ensures users can only see their own data.
    This is called IDOR (Insecure Direct Object Reference) prevention.
    """
    result = await db.execute(
        select(models.Transaction).where(
            models.Transaction.id      == transaction_id,
            models.Transaction.user_id == user_id,
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    return tx
