"""
Outbound Webhooks — Month 5

Allows Pro users to configure webhooks that fire on Declutter events.

POST   /api/v1/webhooks          → Register webhook endpoint
GET    /api/v1/webhooks          → List webhooks
DELETE /api/v1/webhooks/{id}     → Delete webhook
POST   /api/v1/webhooks/{id}/test → Send a test event

Events fired:
  - scan.completed   → after a scan job finishes
  - duplicate.found  → after new duplicate groups are detected
  - suggestion.new   → when new cleanup suggestions are generated
  - file.deleted     → when user deletes a file

Each webhook is signed with HMAC-SHA256 using the endpoint's secret.
"""

import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.extended import WebhookEndpoint

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

VALID_EVENTS = {
    "scan.completed",
    "duplicate.found",
    "suggestion.new",
    "file.deleted",
    "subscription.activated",
}


class CreateWebhookRequest(BaseModel):
    url: str
    events: list[str]
    label: Optional[str] = None


@router.post("")
async def create_webhook(
    req: CreateWebhookRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="Webhooks require Pro plan")

    invalid = set(req.events) - VALID_EVENTS
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid events: {invalid}")

    # Max 5 webhooks
    existing = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.user_id == current_user.id,
            WebhookEndpoint.is_active == True,
        )
    )
    if len(existing.scalars().all()) >= 5:
        raise HTTPException(status_code=400, detail="Maximum 5 webhooks per account")

    signing_secret = f"whsec_{secrets.token_urlsafe(32)}"

    endpoint = WebhookEndpoint(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        url=req.url,
        secret=signing_secret,
        events=req.events,
    )
    db.add(endpoint)
    await db.commit()

    return {
        "id": endpoint.id,
        "url": endpoint.url,
        "events": req.events,
        "signing_secret": signing_secret,  # Only shown on creation
        "warning": "Save the signing_secret — it will not be shown again.",
    }


@router.get("")
async def list_webhooks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.user_id == current_user.id,
            WebhookEndpoint.is_active == True,
        )
    )
    endpoints = result.scalars().all()
    return [
        {
            "id": e.id,
            "url": e.url,
            "events": e.events,
            "last_triggered_at": e.last_triggered_at,
            "failure_count": e.failure_count,
        }
        for e in endpoints
    ]


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == webhook_id,
            WebhookEndpoint.user_id == current_user.id,
        )
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook not found")
    endpoint.is_active = False
    await db.commit()
    return {"deleted": True}


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == webhook_id,
            WebhookEndpoint.user_id == current_user.id,
        )
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook not found")

    test_payload = {
        "event": "test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": current_user.id,
        "data": {"message": "This is a test webhook from Declutter"},
    }

    success, status_code = await _deliver_webhook(endpoint, test_payload)
    return {"success": success, "status_code": status_code}


# ── Delivery ──────────────────────────────────────────────────────────────

async def deliver_event(
    db: AsyncSession,
    user_id: str,
    event: str,
    data: dict,
):
    """Fire an event to all matching webhook endpoints for a user."""
    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.user_id == user_id,
            WebhookEndpoint.is_active == True,
        )
    )
    endpoints = result.scalars().all()

    payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "data": data,
    }

    for endpoint in endpoints:
        if event not in endpoint.events and "*" not in endpoint.events:
            continue
        success, _ = await _deliver_webhook(endpoint, payload)
        endpoint.last_triggered_at = datetime.now(timezone.utc)
        if not success:
            endpoint.failure_count += 1
            # Auto-disable after 10 consecutive failures
            if endpoint.failure_count >= 10:
                endpoint.is_active = False
        else:
            endpoint.failure_count = 0


async def _deliver_webhook(endpoint: WebhookEndpoint, payload: dict) -> tuple[bool, int]:
    """Actually POST the webhook payload with HMAC signature."""
    body = json.dumps(payload)
    signature = hmac.new(
        endpoint.secret.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                endpoint.url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Declutter-Signature": f"sha256={signature}",
                    "X-Declutter-Event": payload.get("event", "unknown"),
                    "User-Agent": "Declutter-Webhooks/1.0",
                },
            )
            return resp.status_code < 400, resp.status_code
    except Exception:
        return False, 0
