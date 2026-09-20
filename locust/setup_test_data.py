"""
Setup script to initialize test data for Locust stress testing:
1. Creates or verifies a high-capacity test event (500,000 tickets).
2. Pre-creates a pool of customer users and generates valid JWT tokens.
3. Saves the event ID and tokens to locust/test_config.json.
"""
import json
import os
import sys
import uuid
from os import environ
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.auth.jwt import create_access_token
from app.auth.hashing import get_password_hash
from app.database import SessionLocal
from app.models.event import Event
from app.models.user import User

def setup():
    ticket_capacity = int(environ.get("LOAD_TEST_TICKET_CAPACITY", "1000"))
    db = SessionLocal()
    try:
        # 1. Ensure organizer user exists
        organizer = db.execute(
            select(User).where(User.email == "loadtest_organizer@example.com")
        ).scalar_one_or_none()
        if not organizer:
            organizer = User(
                email="loadtest_organizer@example.com",
                hashed_password=get_password_hash("password123"),
                full_name="Load Test Organizer",
                role="organizer",
                is_active=True,
            )
            db.add(organizer)
            db.commit()
            db.refresh(organizer)

        # 2. Ensure high-capacity published test event exists
        now = datetime.now(timezone.utc)
        event = db.execute(
            select(Event).where(Event.title == "Mega Stadium Concert 2026")
        ).scalar_one_or_none()

        if not event:
            event = Event(
                organizer_id=organizer.id,
                title="Mega Stadium Concert 2026",
                description="High concurrency load test event",
                location="Grand Arena",
                starts_at=now + timedelta(days=10),
                ends_at=now + timedelta(days=10, hours=4),
                price_cents=2500,
                total_tickets=ticket_capacity,
                available_tickets=ticket_capacity,
                is_published=True,
            )
            db.add(event)
            db.commit()
            db.refresh(event)
        else:
            # Reset tickets
            event.total_tickets = ticket_capacity
            event.available_tickets = ticket_capacity
            event.is_published = True
            db.commit()
            db.refresh(event)

        print(f"Target Event ID: {event.id}, Available tickets: {event.available_tickets}")

        # 3. Create pool of 500 customer users and tokens
        customer_tokens = []
        pw_hash = get_password_hash("password123")
        existing_users = {
            u.email: u for u in db.execute(
                select(User).where(User.email.like("perf_customer_%@example.com"))
            ).scalars().all()
        }

        users_to_add = []
        for i in range(1, 501):
            email = f"perf_customer_{i}@example.com"
            if email in existing_users:
                user = existing_users[email]
            else:
                user = User(
                    email=email,
                    hashed_password=pw_hash,
                    full_name=f"Perf Customer {i}",
                    role="customer",
                    is_active=True,
                )
                users_to_add.append(user)

        if users_to_add:
            db.add_all(users_to_add)
            db.commit()
            for u in users_to_add:
                existing_users[u.email] = u

        for i in range(1, 501):
            email = f"perf_customer_{i}@example.com"
            user = existing_users[email]
            token = create_access_token(subject=str(user.id), role="customer")
            customer_tokens.append(token)

        config = {
            "event_id": str(event.id),
            "organizer_email": "loadtest_organizer@example.com",
            "organizer_password": "password123",
            "customer_email": "perf_customer_1@example.com",
            "customer_password": "password123",
            "customer_tokens": customer_tokens,
        }

        with open("locust/test_config.json", "w") as f:
            json.dump(config, f)

        print(f"Successfully configured test data: 1 event, {len(customer_tokens)} customer tokens.")
    finally:
        db.close()

if __name__ == "__main__":
    setup()
