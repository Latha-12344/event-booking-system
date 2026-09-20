"""
Email service using Resend API.

Provides helpers to format HTML and send:
1. Booking confirmation emails.
2. Event update notification emails.
"""
import logging
from typing import Any

import resend

from app.config import settings

logger = logging.getLogger(__name__)


def render_booking_confirmation_html(
    customer_name: str,
    event_title: str,
    starts_at: str,
    location: str | None,
    quantity: int,
    total_cents: int,
    booking_id: str,
) -> str:
    total_dollars = f"${total_cents / 100:.2f}"
    loc_str = location or "Online / TBD"
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Booking Confirmation</title></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0; font-size: 24px;">Booking Confirmed!</h1>
    </div>
    <div style="border: 1px solid #E5E7EB; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
        <p>Hi <strong>{customer_name}</strong>,</p>
        <p>Thank you for booking with us! Your reservation is confirmed.</p>
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <tr><td style="padding: 8px 0; border-bottom: 1px solid #F3F4F6;"><strong>Event:</strong></td><td style="padding: 8px 0; border-bottom: 1px solid #F3F4F6;">{event_title}</td></tr>
            <tr><td style="padding: 8px 0; border-bottom: 1px solid #F3F4F6;"><strong>Date & Time:</strong></td><td style="padding: 8px 0; border-bottom: 1px solid #F3F4F6;">{starts_at}</td></tr>
            <tr><td style="padding: 8px 0; border-bottom: 1px solid #F3F4F6;"><strong>Location:</strong></td><td style="padding: 8px 0; border-bottom: 1px solid #F3F4F6;">{loc_str}</td></tr>
            <tr><td style="padding: 8px 0; border-bottom: 1px solid #F3F4F6;"><strong>Tickets:</strong></td><td style="padding: 8px 0; border-bottom: 1px solid #F3F4F6;">{quantity}</td></tr>
            <tr><td style="padding: 8px 0; border-bottom: 1px solid #F3F4F6;"><strong>Total Paid:</strong></td><td style="padding: 8px 0; border-bottom: 1px solid #F3F4F6;">{total_dollars}</td></tr>
            <tr><td style="padding: 8px 0;"><strong>Booking Reference:</strong></td><td style="padding: 8px 0;"><code>{booking_id}</code></td></tr>
        </table>
        <p style="color: #6B7280; font-size: 14px;">If you have any questions or need to manage your booking, visit our portal.</p>
    </div>
</body>
</html>"""


def render_event_update_html(
    customer_name: str,
    event_title: str,
    changes: dict[str, Any],
) -> str:
    change_rows = ""
    for field, val in changes.items():
        change_rows += f"<tr><td style='padding: 6px 0;'><strong>{field.replace('_', ' ').title()}:</strong></td><td style='padding: 6px 0;'>{val}</td></tr>"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Event Update</title></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #F59E0B; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0; font-size: 24px;">Event Details Updated</h1>
    </div>
    <div style="border: 1px solid #E5E7EB; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
        <p>Hi <strong>{customer_name}</strong>,</p>
        <p>There have been important updates to the event: <strong>{event_title}</strong>.</p>
        <h3 style="color: #374151;">Updated Information:</h3>
        <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
            {change_rows}
        </table>
        <p style="color: #6B7280; font-size: 14px;">Please review the updated details above. If you have questions, contact the event organizer.</p>
    </div>
</body>
</html>"""


def send_booking_confirmation_email(
    to: str,
    customer_name: str,
    event_title: str,
    starts_at: str,
    location: str | None,
    quantity: int,
    total_cents: int,
    booking_id: str,
) -> dict[str, Any] | None:
    """Send booking confirmation email via Resend API."""
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured. Skipping email to %s", to)
        return None

    resend.api_key = settings.RESEND_API_KEY
    html_content = render_booking_confirmation_html(
        customer_name=customer_name,
        event_title=event_title,
        starts_at=starts_at,
        location=location,
        quantity=quantity,
        total_cents=total_cents,
        booking_id=booking_id,
    )
    params: resend.Emails.SendParams = {
        "from": settings.EMAIL_FROM,
        "to": [to],
        "subject": f"Booking Confirmed: {event_title}",
        "html": html_content,
    }
    return resend.Emails.send(params)


def send_event_update_email(
    to: str,
    customer_name: str,
    event_title: str,
    changes: dict[str, Any],
) -> dict[str, Any] | None:
    """Send event update notification email via Resend API."""
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured. Skipping email to %s", to)
        return None

    resend.api_key = settings.RESEND_API_KEY
    html_content = render_event_update_html(
        customer_name=customer_name,
        event_title=event_title,
        changes=changes,
    )
    params: resend.Emails.SendParams = {
        "from": settings.EMAIL_FROM,
        "to": [to],
        "subject": f"Update: {event_title}",
        "html": html_content,
    }
    return resend.Emails.send(params)
