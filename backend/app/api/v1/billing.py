"""
Billing Routes — Month 3

POST /api/v1/billing/checkout          → Create Stripe Checkout session
POST /api/v1/billing/portal            → Create Stripe Customer Portal session
POST /api/v1/billing/webhook           → Stripe webhook handler
GET  /api/v1/billing/status            → Current subscription status
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.billing.stripe_service import (
    create_checkout_session,
    create_portal_session,
    process_webhook,
    get_subscription_status,
)

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    plan: str = "monthly"  # "monthly" | "yearly"


@router.post("/checkout")
async def billing_checkout(
    req: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Checkout session. Returns { url } to redirect the user.
    """
    if current_user.tier == "pro":
        raise HTTPException(status_code=400, detail="Already subscribed to Pro")

    if req.plan not in ("monthly", "yearly"):
        raise HTTPException(status_code=400, detail="Plan must be 'monthly' or 'yearly'")

    result = await create_checkout_session(current_user, req.plan, db)
    return result


@router.post("/portal")
async def billing_portal(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Open Stripe Customer Portal for billing management (cancel, update card, etc).
    """
    result = await create_portal_session(current_user, db)
    return result


@router.post("/webhook")
async def billing_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(default=None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    Stripe webhook endpoint. Must be called with raw body (no JSON parsing).
    Register this URL in Stripe Dashboard: https://yourdomain.com/api/v1/billing/webhook
    """
    payload = await request.body()

    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    result = await process_webhook(payload, stripe_signature, db)
    await db.commit()
    return result


@router.get("/status")
async def billing_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return current subscription status for the settings page.
    """
    return await get_subscription_status(current_user)
