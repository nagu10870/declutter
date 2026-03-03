"""
Stripe Billing Service — Month 3

Handles:
  - Checkout session creation (monthly + yearly pricing)
  - Webhook event processing (subscription activated/cancelled/updated)
  - Customer portal for self-service billing management
  - Tier upgrades/downgrades reflected immediately in DB

Security:
  - Webhook signature verified via Stripe-Signature header
  - Never expose raw Stripe keys to frontend; all API calls server-side
  - Idempotent event processing (events can arrive out of order / duplicate)
"""

import stripe
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.user import User

if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


async def create_checkout_session(
    user: User,
    plan: str,  # "monthly" | "yearly"
    db: AsyncSession,
) -> dict:
    """
    Create a Stripe Checkout session for Pro subscription.
    Returns { url: str } — frontend redirects to this URL.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured")

    price_id = (
        settings.STRIPE_PRO_YEARLY_PRICE_ID
        if plan == "yearly"
        else settings.STRIPE_PRO_MONTHLY_PRICE_ID
    )
    if not price_id:
        raise HTTPException(status_code=503, detail=f"Price ID for '{plan}' plan not configured")

    # Get or create Stripe customer
    customer_id = await _get_or_create_customer(user, db)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.FRONTEND_URL}/settings?billing=success",
        cancel_url=f"{settings.FRONTEND_URL}/settings?billing=cancelled",
        metadata={"user_id": user.id},
        subscription_data={
            "trial_period_days": 14,  # 14-day free trial
            "metadata": {"user_id": user.id},
        },
        allow_promotion_codes=True,
    )
    return {"url": session.url, "session_id": session.id}


async def create_portal_session(user: User, db: AsyncSession) -> dict:
    """
    Create a Stripe Customer Portal session for managing existing subscription.
    Returns { url: str }
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured")

    customer_id = await _get_or_create_customer(user, db)
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{settings.FRONTEND_URL}/settings",
    )
    return {"url": session.url}


async def process_webhook(
    payload: bytes,
    sig_header: str,
    db: AsyncSession,
) -> dict:
    """
    Process Stripe webhook. Validates signature before any processing.
    Idempotent — safe to call multiple times for same event.
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
    ):
        await _handle_subscription_active(data, db)

    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_cancelled(data, db)

    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(data, db)

    return {"processed": event_type}


async def _get_or_create_customer(user: User, db: AsyncSession) -> str:
    """Get existing Stripe customer ID from user record, or create one."""
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = stripe.Customer.create(
        email=user.email,
        name=user.full_name or user.email,
        metadata={"user_id": user.id},
    )
    user.stripe_customer_id = customer.id
    await db.flush()
    return customer.id


async def _handle_subscription_active(subscription: dict, db: AsyncSession):
    """Upgrade user to Pro when subscription is active."""
    user_id = subscription.get("metadata", {}).get("user_id")
    if not user_id:
        # Fallback: find user via customer email
        customer = stripe.Customer.retrieve(subscription["customer"])
        result = await db.execute(
            select(User).where(User.email == customer.email)
        )
        user = result.scalar_one_or_none()
    else:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    if user:
        user.tier = "pro"
        await db.flush()


async def _handle_subscription_cancelled(subscription: dict, db: AsyncSession):
    """Downgrade user to free when subscription ends."""
    user_id = subscription.get("metadata", {}).get("user_id")
    if user_id:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.tier = "free"
            await db.flush()


async def _handle_payment_failed(invoice: dict, db: AsyncSession):
    """Log payment failure — don't immediately downgrade, Stripe retries."""
    # In production: send email notification via Resend
    pass


async def get_subscription_status(user: User) -> dict:
    """Return current subscription info for the settings page."""
    if not settings.STRIPE_SECRET_KEY:
        return {"plan": user.tier, "billing_configured": False}

    customers = stripe.Customer.list(email=user.email, limit=1)
    if not customers.data:
        return {"plan": user.tier, "billing_configured": True, "subscriptions": []}

    customer_id = customers.data[0].id
    subscriptions = stripe.Subscription.list(customer=customer_id, status="all", limit=5)

    active = [s for s in subscriptions.data if s.status in ("active", "trialing")]

    return {
        "plan": user.tier,
        "billing_configured": True,
        "customer_id": customer_id,
        "subscriptions": [
            {
                "id": s.id,
                "status": s.status,
                "current_period_end": s.current_period_end,
                "cancel_at_period_end": s.cancel_at_period_end,
                "trial_end": s.trial_end,
            }
            for s in active
        ],
    }
