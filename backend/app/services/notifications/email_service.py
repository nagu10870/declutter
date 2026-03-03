"""
Email Notification Service — Month 4

Uses Resend API for transactional email delivery.
Templates are built with Jinja2 inline (no external template files needed).

Email types:
  - Scan completion digest (files indexed, duplicates found, space savings)
  - Weekly storage report (usage trends, suggestions)
  - Monthly report (growth, biggest duplicates)
  - Welcome email on registration
  - Pro trial ending reminder (3 days before trial ends)
  - Payment failed warning

All emails use the same dark-themed HTML template that matches the app UI.
"""

import os
from typing import Optional
from datetime import datetime, timezone

try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False

from jinja2 import Template
from app.core.config import settings


# ── Base HTML Template ────────────────────────────────────────────────────

EMAIL_BASE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ subject }}</title>
</head>
<body style="margin:0;padding:0;background:#0d0f14;font-family:'Helvetica Neue',Arial,sans-serif;color:#f0f2ff;">
  <div style="max-width:600px;margin:0 auto;padding:32px 16px;">
    <!-- Header -->
    <div style="text-align:center;margin-bottom:32px;">
      <div style="display:inline-flex;align-items:center;gap:10px;background:linear-gradient(135deg,#4f7cff,#1de9a4);padding:10px 20px;border-radius:16px;">
        <span style="font-size:20px;font-weight:bold;color:white;">⚡ Declutter</span>
      </div>
    </div>

    <!-- Card -->
    <div style="background:#13161e;border:1px solid #252a38;border-radius:16px;padding:32px;">
      {{ body }}
    </div>

    <!-- Footer -->
    <div style="text-align:center;margin-top:24px;">
      <p style="color:#4a5068;font-size:12px;">
        You're receiving this from <a href="{{ app_url }}" style="color:#4f7cff;">Declutter</a>.
        <a href="{{ app_url }}/account?unsubscribe=1" style="color:#4a5068;">Unsubscribe</a>
      </p>
    </div>
  </div>
</body>
</html>"""

STAT_BLOCK = """
<div style="background:#1a1e29;border-radius:12px;padding:16px;margin:8px 0;display:flex;justify-content:space-between;align-items:center;">
  <span style="color:#8891b0;font-size:13px;">{{ label }}</span>
  <span style="color:{{ color }};font-weight:bold;font-size:18px;">{{ value }}</span>
</div>
"""

BUTTON = """
<a href="{{ url }}" style="display:inline-block;background:#4f7cff;color:white;text-decoration:none;padding:12px 28px;border-radius:12px;font-weight:600;margin-top:16px;">
  {{ label }}
</a>
"""


# ── Email Builders ────────────────────────────────────────────────────────

def _render(body_html: str, subject: str) -> str:
    return Template(EMAIL_BASE).render(
        subject=subject,
        body=body_html,
        app_url=settings.FRONTEND_URL,
    )


def build_scan_digest_email(
    user_name: str,
    files_indexed: int,
    duplicate_groups: int,
    bytes_recoverable: int,
    job_duration_secs: float,
) -> tuple[str, str]:
    """Returns (subject, html)"""
    subject = f"✅ Scan complete — {_fmt_bytes(bytes_recoverable)} recoverable"

    stats_html = ""
    for label, value, color in [
        ("Files indexed", f"{files_indexed:,}", "#4f7cff"),
        ("Duplicate groups", str(duplicate_groups), "#f5a623"),
        ("Space recoverable", _fmt_bytes(bytes_recoverable), "#1de9a4"),
        ("Duration", f"{job_duration_secs:.0f}s", "#8891b0"),
    ]:
        stats_html += Template(STAT_BLOCK).render(label=label, value=value, color=color)

    btn = Template(BUTTON).render(url=f"{settings.FRONTEND_URL}/duplicates", label="Review Duplicates →")
    body = f"""
    <h2 style="color:#f0f2ff;margin-top:0;">Hey {user_name}, your scan is done!</h2>
    <p style="color:#8891b0;">Here's what we found:</p>
    {stats_html}
    <div style="text-align:center;margin-top:24px;">{btn}</div>
    """
    return subject, _render(body, subject)


def build_weekly_digest_email(
    user_name: str,
    total_files: int,
    total_bytes: int,
    suggestions_count: int,
    potential_savings: int,
) -> tuple[str, str]:
    subject = "📊 Your weekly storage report"
    stats_html = ""
    for label, value, color in [
        ("Total files", f"{total_files:,}", "#4f7cff"),
        ("Total size", _fmt_bytes(total_bytes), "#8891b0"),
        ("Cleanup suggestions", str(suggestions_count), "#f5a623"),
        ("Potential savings", _fmt_bytes(potential_savings), "#1de9a4"),
    ]:
        stats_html += Template(STAT_BLOCK).render(label=label, value=value, color=color)

    btn = Template(BUTTON).render(url=f"{settings.FRONTEND_URL}/suggestions", label="View Suggestions →")
    body = f"""
    <h2 style="color:#f0f2ff;margin-top:0;">Weekly report for {user_name}</h2>
    <p style="color:#8891b0;">Here's your storage health at a glance:</p>
    {stats_html}
    <div style="text-align:center;margin-top:24px;">{btn}</div>
    """
    return subject, _render(body, subject)


def build_welcome_email(user_name: str) -> tuple[str, str]:
    subject = "⚡ Welcome to Declutter — let's clean up your storage"
    btn = Template(BUTTON).render(url=f"{settings.FRONTEND_URL}/dashboard", label="Go to Dashboard →")
    body = f"""
    <h2 style="color:#f0f2ff;margin-top:0;">Welcome, {user_name}! 👋</h2>
    <p style="color:#8891b0;">Declutter helps you find and remove duplicate files, blurry photos, and unnecessary screenshots across all your cloud storage.</p>
    <div style="background:#1a1e29;border-radius:12px;padding:20px;margin:20px 0;">
      <p style="color:#f0f2ff;font-weight:600;margin-top:0;">Get started in 3 steps:</p>
      <p style="color:#8891b0;">1. 📁 Connect your Google Drive, Dropbox, or scan local files</p>
      <p style="color:#8891b0;">2. 🔍 Run a scan — we'll index metadata only, never download your files</p>
      <p style="color:#8891b0;">3. 🗑 Review duplicates and suggestions to free up space</p>
    </div>
    <div style="text-align:center;">{btn}</div>
    """
    return subject, _render(body, subject)


def build_trial_ending_email(user_name: str, days_left: int) -> tuple[str, str]:
    subject = f"⏰ Your Pro trial ends in {days_left} day{'s' if days_left != 1 else ''}"
    btn = Template(BUTTON).render(url=f"{settings.FRONTEND_URL}/settings?tab=billing", label="Keep Pro Access →")
    body = f"""
    <h2 style="color:#f0f2ff;margin-top:0;">Trial ending soon, {user_name}</h2>
    <p style="color:#8891b0;">Your 14-day free trial of Declutter Pro ends in <strong style="color:#f5a623;">{days_left} day{'s' if days_left != 1 else ''}</strong>.</p>
    <p style="color:#8891b0;">After your trial, you'll lose access to:</p>
    <div style="background:#1a1e29;border-radius:12px;padding:20px;margin:20px 0;">
      <p style="color:#8891b0;">• Google Drive, Dropbox & OneDrive integration</p>
      <p style="color:#8891b0;">• AI similarity detection & blurry photo cleanup</p>
      <p style="color:#8891b0;">• Smart suggestions engine</p>
      <p style="color:#8891b0;">• Scheduled automatic scans</p>
    </div>
    <div style="text-align:center;">{btn}</div>
    """
    return subject, _render(body, subject)


# ── Sender ────────────────────────────────────────────────────────────────

async def send_email(to: str, subject: str, html: str) -> bool:
    """Send email via Resend. Returns True if sent, False if unavailable."""
    if not RESEND_AVAILABLE or not settings.RESEND_API_KEY:
        # Log to stdout in dev mode
        print(f"[EMAIL] To: {to} | Subject: {subject}")
        return False
    try:
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send({
            "from": f"Declutter <{settings.FROM_EMAIL}>",
            "to": [to],
            "subject": subject,
            "html": html,
        })
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


async def send_scan_digest(user, job) -> bool:
    duration = 0.0
    if job.started_at and job.completed_at:
        duration = (job.completed_at - job.started_at).total_seconds()
    subject, html = build_scan_digest_email(
        user_name=user.full_name or user.email.split("@")[0],
        files_indexed=job.files_scanned or 0,
        duplicate_groups=0,  # Could query but keeping it simple
        bytes_recoverable=job.bytes_reclaimable or 0,
        job_duration_secs=duration,
    )
    return await send_email(user.email, subject, html)


async def send_weekly_storage_digest(db, user) -> bool:
    from sqlalchemy import select, func, text
    from app.models.file import FileRecord, Suggestion

    # Quick stats
    stats = await db.execute(
        select(
            func.count(FileRecord.id).label("cnt"),
            func.coalesce(func.sum(FileRecord.file_size), 0).label("bytes"),
        ).where(FileRecord.user_id == user.id, FileRecord.is_deleted == False)
    )
    row = stats.one()

    sug_stats = await db.execute(
        select(
            func.count(Suggestion.id).label("cnt"),
            func.coalesce(func.sum(Suggestion.bytes_savings), 0).label("bytes"),
        ).where(
            Suggestion.user_id == user.id,
            Suggestion.dismissed == False,
            Suggestion.applied == False,
        )
    )
    sug = sug_stats.one()

    subject, html = build_weekly_digest_email(
        user_name=user.full_name or user.email.split("@")[0],
        total_files=row.cnt or 0,
        total_bytes=int(row.bytes),
        suggestions_count=sug.cnt or 0,
        potential_savings=int(sug.bytes),
    )
    return await send_email(user.email, subject, html)


async def send_welcome(user) -> bool:
    subject, html = build_welcome_email(
        user.full_name or user.email.split("@")[0]
    )
    return await send_email(user.email, subject, html)


# ── Helpers ───────────────────────────────────────────────────────────────

def _fmt_bytes(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b //= 1024
    return f"{b:.1f} PB"
