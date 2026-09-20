"""
Unit and integration tests for Booking endpoints.
"""
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient


def get_token(client: TestClient, email: str, role: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
            "full_name": f"{role.title()} User",
            "role": role,
        },
    )
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    return res.json()["access_token"]


def create_published_event(client: TestClient, org_token: str, total_tickets: int = 10, price_cents: int = 2500) -> str:
    now = datetime.now(timezone.utc)
    res = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "Live Rock Concert",
            "starts_at": (now + timedelta(days=3)).isoformat(),
            "ends_at": (now + timedelta(days=3, hours=4)).isoformat(),
            "total_tickets": total_tickets,
            "price_cents": price_cents,
        },
    )
    event_id = res.json()["id"]
    client.patch(
        f"/api/v1/events/{event_id}/publish?is_published=true",
        headers={"Authorization": f"Bearer {org_token}"},
    )
    return event_id


def test_customer_book_tickets_success(client: TestClient):
    org_token = get_token(client, "org_b1@example.com", "organizer")
    cust_token = get_token(client, "cust_b1@example.com", "customer")
    event_id = create_published_event(client, org_token, total_tickets=10, price_cents=2500)

    # Book 3 tickets
    response = client.post(
        "/api/v1/bookings/",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"event_id": event_id, "quantity": 3},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["quantity"] == 3
    assert data["total_cents"] == 7500  # 3 * 2500
    assert data["status"] == "confirmed"

    # Verify event available_tickets was decremented from 10 to 7
    event_res = client.get(f"/api/v1/events/{event_id}")
    assert event_res.json()["available_tickets"] == 7


def test_organizer_cannot_book_tickets(client: TestClient):
    org_token = get_token(client, "org_b2@example.com", "organizer")
    event_id = create_published_event(client, org_token)

    response = client.post(
        "/api/v1/bookings/",
        headers={"Authorization": f"Bearer {org_token}"},
        json={"event_id": event_id, "quantity": 1},
    )
    assert response.status_code == 403
    assert "customer access required" in response.json()["detail"].lower()


def test_cannot_book_unpublished_event(client: TestClient):
    org_token = get_token(client, "org_b3@example.com", "organizer")
    cust_token = get_token(client, "cust_b3@example.com", "customer")
    now = datetime.now(timezone.utc)

    res = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "Unpublished Draft",
            "starts_at": (now + timedelta(days=2)).isoformat(),
            "ends_at": (now + timedelta(days=2, hours=1)).isoformat(),
            "total_tickets": 20,
            "price_cents": 1000,
        },
    )
    event_id = res.json()["id"]

    response = client.post(
        "/api/v1/bookings/",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"event_id": event_id, "quantity": 1},
    )
    assert response.status_code == 400
    assert "unpublished" in response.json()["detail"].lower()


def test_overbooking_fails_with_409_conflict(client: TestClient):
    org_token = get_token(client, "org_b4@example.com", "organizer")
    cust_token = get_token(client, "cust_b4@example.com", "customer")
    event_id = create_published_event(client, org_token, total_tickets=2)

    # Requesting 3 tickets when only 2 exist
    response = client.post(
        "/api/v1/bookings/",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"event_id": event_id, "quantity": 3},
    )
    assert response.status_code == 409
    assert "not enough tickets" in response.json()["detail"].lower()


def test_cancel_booking_releases_tickets(client: TestClient):
    org_token = get_token(client, "org_b5@example.com", "organizer")
    cust_token = get_token(client, "cust_b5@example.com", "customer")
    event_id = create_published_event(client, org_token, total_tickets=5)

    # Book 2 tickets
    book_res = client.post(
        "/api/v1/bookings/",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"event_id": event_id, "quantity": 2},
    )
    booking_id = book_res.json()["id"]

    # Verify 3 remaining
    assert client.get(f"/api/v1/events/{event_id}").json()["available_tickets"] == 3

    # Cancel booking
    cancel_res = client.delete(
        f"/api/v1/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    # Verify tickets are restored back to 5
    assert client.get(f"/api/v1/events/{event_id}").json()["available_tickets"] == 5


def test_multiple_bookings_per_customer_allowed(client: TestClient):
    """Verifies intentional design decision: customers can make multiple separate bookings for one event."""
    org_token = get_token(client, "org_b6@example.com", "organizer")
    cust_token = get_token(client, "cust_b6@example.com", "customer")
    event_id = create_published_event(client, org_token, total_tickets=10)

    # First booking: 2 tickets
    res1 = client.post(
        "/api/v1/bookings/",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"event_id": event_id, "quantity": 2},
    )
    assert res1.status_code == 201

    # Second booking by same customer: 3 tickets
    res2 = client.post(
        "/api/v1/bookings/",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"event_id": event_id, "quantity": 3},
    )
    assert res2.status_code == 201
    assert res1.json()["id"] != res2.json()["id"]

    # Total booked = 5, available = 5
    assert client.get(f"/api/v1/events/{event_id}").json()["available_tickets"] == 5


def test_other_customer_cannot_cancel_booking(client: TestClient):
    org_token = get_token(client, "org_b7@example.com", "organizer")
    cust1_token = get_token(client, "cust_b7_1@example.com", "customer")
    cust2_token = get_token(client, "cust_b7_2@example.com", "customer")
    event_id = create_published_event(client, org_token, total_tickets=10)

    # Customer 1 books
    res = client.post(
        "/api/v1/bookings/",
        headers={"Authorization": f"Bearer {cust1_token}"},
        json={"event_id": event_id, "quantity": 2},
    )
    booking_id = res.json()["id"]

    # Customer 2 attempts to cancel Customer 1's booking
    fail_cancel = client.delete(
        f"/api/v1/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {cust2_token}"},
    )
    assert fail_cancel.status_code == 403


def test_customer_cannot_view_another_customer_booking(client: TestClient):
    org_token = get_token(client, "org_b8@example.com", "organizer")
    cust1_token = get_token(client, "cust_b8_1@example.com", "customer")
    cust2_token = get_token(client, "cust_b8_2@example.com", "customer")
    event_id = create_published_event(client, org_token, total_tickets=10)

    res = client.post(
        "/api/v1/bookings/",
        headers={"Authorization": f"Bearer {cust1_token}"},
        json={"event_id": event_id, "quantity": 1},
    )
    booking_id = res.json()["id"]

    # Owner can view
    ok_res = client.get(
        f"/api/v1/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {cust1_token}"},
    )
    assert ok_res.status_code == 200

    # Non-owner cannot view
    fail_res = client.get(
        f"/api/v1/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {cust2_token}"},
    )
    assert fail_res.status_code == 403


def test_booking_concurrency_pessimistic_locking(client: TestClient):
    """
    Verifies pessimistic locking: multiple concurrent requests competing for limited tickets
    cannot oversell.
    """
    import concurrent.futures

    org_token = get_token(client, "org_concur@example.com", "organizer")
    event_id = create_published_event(client, org_token, total_tickets=3)

    # Register 6 distinct customers
    customer_tokens = []
    for i in range(6):
        tok = get_token(client, f"cust_concur_{i}@example.com", "customer")
        customer_tokens.append(tok)

    def attempt_booking(token):
        return client.post(
            "/api/v1/bookings/",
            headers={"Authorization": f"Bearer {token}"},
            json={"event_id": event_id, "quantity": 1},
        )

    # Execute 6 concurrent booking requests for 3 total tickets
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        responses = list(executor.map(attempt_booking, customer_tokens))

    status_codes = [r.status_code for r in responses]
    success_count = status_codes.count(201)
    conflict_count = status_codes.count(409)

    # Exactly 3 succeed, 3 receive 409 Conflict
    assert success_count == 3
    assert conflict_count == 3

    # Available tickets must be exactly 0, never negative
    event_res = client.get(f"/api/v1/events/{event_id}")
    assert event_res.json()["available_tickets"] == 0


def test_celery_task_queued_after_commit(client: TestClient):
    """Verifies that send_booking_confirmation.delay is invoked with correct payload."""
    from unittest.mock import patch

    org_token = get_token(client, "org_task@example.com", "organizer")
    cust_token = get_token(client, "cust_task@example.com", "customer")
    event_id = create_published_event(client, org_token, total_tickets=5, price_cents=1200)

    with patch("app.services.booking_service.send_booking_confirmation.delay") as mock_delay:
        res = client.post(
            "/api/v1/bookings/",
            headers={"Authorization": f"Bearer {cust_token}"},
            json={"event_id": event_id, "quantity": 2},
        )
        assert res.status_code == 201
        booking_id = res.json()["id"]

        # Ensure task was queued
        assert mock_delay.called
        kwargs = mock_delay.call_args.kwargs
        assert kwargs["booking_id"] == booking_id
        assert kwargs["customer_email"] == "cust_task@example.com"
        assert kwargs["quantity"] == 2
        assert kwargs["total_cents"] == 2400


def test_event_update_notification_deduplication(client: TestClient):
    """
    Verifies that when an event changes, customers with multiple bookings
    are deduplicated by customer_id and receive only ONE notification.
    """
    from unittest.mock import patch

    org_token = get_token(client, "org_dedup@example.com", "organizer")
    cust1_token = get_token(client, "cust_dedup1@example.com", "customer")
    cust2_token = get_token(client, "cust_dedup2@example.com", "customer")
    event_id = create_published_event(client, org_token, total_tickets=20)

    # Customer 1 makes 2 separate bookings
    client.post("/api/v1/bookings/", headers={"Authorization": f"Bearer {cust1_token}"}, json={"event_id": event_id, "quantity": 1})
    client.post("/api/v1/bookings/", headers={"Authorization": f"Bearer {cust1_token}"}, json={"event_id": event_id, "quantity": 2})

    # Customer 2 makes 1 booking
    client.post("/api/v1/bookings/", headers={"Authorization": f"Bearer {cust2_token}"}, json={"event_id": event_id, "quantity": 1})

    # Total bookings = 3, but unique customers = 2
    with patch("app.tasks.email_tasks.send_event_update_email") as mock_email:
        # Organizer updates event (triggers send_event_update_notifications)
        client.patch(
            f"/api/v1/events/{event_id}",
            headers={"Authorization": f"Bearer {org_token}"},
            json={"location": "Brand New Auditorium"},
        )

        # send_event_update_email should be called exactly twice (for cust1 and cust2)
        assert mock_email.call_count == 2
        called_emails = [call.kwargs["to"] for call in mock_email.call_args_list]
        assert "cust_dedup1@example.com" in called_emails
        assert "cust_dedup2@example.com" in called_emails

