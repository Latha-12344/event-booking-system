"""
Celery tasks for sending transactional and notification emails.
"""
import logging
import uuid
from typing import Any

from sqlalchemy import select

from app.database import SessionLocal
from app.models.booking import Booking
from app.models.event import Event
from app.models.user import User
from app.services.email_service import (
    send_booking_confirmation_email,
    send_event_update_email,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)
NOTIFICATION_BATCH_SIZE = 100


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.tasks.email_tasks.send_booking_confirmation",
)
def send_booking_confirmation(
    self,
    booking_id: str,
    customer_email: str,
    customer_name: str,
    event_title: str,
    starts_at: str,
    location: str | None,
    quantity: int,
    total_cents: int,
) -> None:
    """Send booking confirmation email to customer after DB commit."""
    try:
        logger.info("Sending booking confirmation for booking %s to %s", booking_id, customer_email)
        send_booking_confirmation_email(
            to=customer_email,
            customer_name=customer_name,
            event_title=event_title,
            starts_at=starts_at,
            location=location,
            quantity=quantity,
            total_cents=total_cents,
            booking_id=booking_id,
        )
    except Exception as exc:
        logger.error("Error sending booking confirmation: %s. Retrying...", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.tasks.email_tasks.send_event_update_notifications",
)
def send_event_update_notifications(
    self,
    event_id: str,
    changes: dict[str, Any],
) -> None:
    """
    Send notification emails to all customers with confirmed bookings for this event.
    Deduplicates by customer_id so customers with multiple bookings receive exactly 1 email.
    """
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        logger.error("Invalid event_id provided to task: %s", event_id)
        return

    db = SessionLocal()
    try:
        event = db.get(Event, event_uuid)
        if not event:
            logger.warning("Event %s not found. Skipping notifications.", event_id)
            return

        event_title = event.title

        # Query all confirmed bookings with customer details
        query = (
            select(Booking.customer_id, User.email, User.full_name)
            .join(User, Booking.customer_id == User.id)
            .where(
                Booking.event_id == event_uuid,
                Booking.status == "confirmed",
            )
        )
        results = db.execute(query).all()

        # Deduplicate by customer_id
        seen_customer_ids = set()
        recipients: list[tuple[str, str]] = []  # (email, full_name)
        for row in results:
            if row.customer_id not in seen_customer_ids:
                seen_customer_ids.add(row.customer_id)
                recipients.append((row.email, row.full_name))

        logger.info(
            "Found %d unique recipient(s) for event %s update notifications",
            len(recipients),
            event_id,
        )

        # Process large recipient sets in bounded batches. A failure is raised
        # after the batch so Celery can retry the task instead of silently
        # losing notifications.
        for batch_start in range(0, len(recipients), NOTIFICATION_BATCH_SIZE):
            batch = recipients[batch_start : batch_start + NOTIFICATION_BATCH_SIZE]
            batch_errors: list[Exception] = []
            for email, full_name in batch:
                try:
                    send_event_update_email(
                        to=email,
                        customer_name=full_name,
                        event_title=event_title,
                        changes=changes,
                    )
                except Exception as exc:
                    logger.error("Failed sending update email to %s: %s", email, exc)
                    batch_errors.append(exc)
            if batch_errors:
                raise RuntimeError(
                    f"Failed to send {len(batch_errors)} event update notification(s)"
                ) from batch_errors[0]
    except Exception as exc:
        logger.error("Error during event update notification task: %s. Retrying...", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()
