"""
Outbound email.

Two delivery backends, chosen by whether SMTP_HOST is configured:

  - SMTP: stdlib smtplib run in a worker thread. Deliberately no new
    dependency -- an async SMTP client buys nothing here, because sending is
    already off the request path (the route schedules it as a background
    task) and the volume is one message per password-reset request.

  - Log: writes the full message, link included, to the server log. This is
    what makes the reset flow genuinely usable in development without
    inventing mail credentials -- the same thing Django's console email
    backend does. It REFUSES to run under ENV=production, so a deployment
    that forgot to configure SMTP fails loudly on the first reset request
    instead of silently swallowing every email.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger("nexus.email")


class EmailError(RuntimeError):
    """Delivery failed. Never surfaced to an unauthenticated caller verbatim
    -- see auth_service.request_password_reset for why the reset route stays
    silent about it."""


def _build(to: str, subject: str, body: str) -> EmailMessage:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    return message


def _send_smtp_blocking(message: EmailMessage) -> None:
    settings = get_settings()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_starttls:
            server.starttls()
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


async def send_email(*, to: str, subject: str, body: str) -> None:
    settings = get_settings()

    if not settings.smtp_host:
        if settings.env == "production":
            raise EmailError(
                "No SMTP server is configured, so this message cannot be sent. "
                "Set SMTP_HOST (and credentials) for this deployment."
            )
        logger.warning(
            "SMTP is not configured -- logging this email instead of sending it.\n"
            "--- EMAIL (dev fallback) ---\nTo: %s\nSubject: %s\n\n%s\n--- END EMAIL ---",
            to, subject, body,
        )
        return

    try:
        await asyncio.to_thread(_send_smtp_blocking, _build(to, subject, body))
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailError(f"Could not send email via {settings.smtp_host}: {exc}") from exc


async def send_password_reset(*, to: str, link: str, ttl_minutes: int) -> None:
    body = (
        "Someone (hopefully you) asked to reset the password for your Nexus account.\n\n"
        f"Use this link to choose a new one -- it expires in {ttl_minutes} minutes "
        "and can only be used once:\n\n"
        f"{link}\n\n"
        "If you didn't ask for this, you can ignore this email. Your password stays as it is, "
        "and the link above does nothing until it's opened.\n\n"
        "-- Nexus Coder"
    )
    await send_email(to=to, subject="Reset your Nexus password", body=body)
