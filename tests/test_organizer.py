"""
Unit and integration tests for Organizer Dashboard endpoints.
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


def test_organizer_list_my_events(client: TestClient):
    org_token = get_token(client, "org_dash1@example.com", "organizer")
    now = datetime.now(timezone.utc)

    # Create 2 events: 1 draft, 1 published
    res1 = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "Organizer Event 1",
            "starts_at": (now + timedelta(days=1)).isoformat(),
            "ends_at": (now + timedelta(days=1, hours=2)).isoformat(),
            "total_tickets": 20,
            "price_cents": 1500,
        },
    )
    res2 = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "Organizer Event 2",
            "starts_at": (now + timedelta(days=2)).isoformat(),
            "ends_at": (now + timedelta(days=2, hours=2)).isoformat(),
            "total_tickets": 30,
            "price_cents": 2500,
        },
    )
    # Publish event 1
    client.patch(
        f"/api/v1/events/{res1.json()['id']}/publish?is_published=true",
        headers={"Authorization": f"Bearer {org_token}"},
    )

    # Organizer dashboard should show both
    dashboard_res = client.get(
        "/api/v1/organizer/events",
        headers={"Authorization": f"Bearer {org_token}"},
    )
    assert dashboard_res.status_code == 200
    data = dashboard_res.json()
    assert data["total"] == 2
    titles = [item["title"] for item in data["items"]]
    assert "Organizer Event 1" in titles
    assert "Organizer Event 2" in titles


def test_organizer_view_event_bookings(client: TestClient):
    org_token = get_token(client, "org_dash2@example.com", "organizer")
    other_org_token = get_token(client, "org_dash_other@example.com", "organizer")
    cust_token = get_token(client, "cust_dash@example.com", "customer")
    now = datetime.now(timezone.utc)

    # Create & publish event
    res = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "Festival 2026",
            "starts_at": (now + timedelta(days=4)).isoformat(),
            "ends_at": (now + timedelta(days=4, hours=6)).isoformat(),
            "total_tickets": 50,
            "price_cents": 3000,
        },
    )
    event_id = res.json()["id"]
    client.patch(
        f"/api/v1/events/{event_id}/publish?is_published=true",
        headers={"Authorization": f"Bearer {org_token}"},
    )

    # Customer books 2 tickets
    client.post(
        "/api/v1/bookings/",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"event_id": event_id, "quantity": 2},
    )

    # Organizer sees the booking
    bookings_res = client.get(
        f"/api/v1/organizer/events/{event_id}/bookings",
        headers={"Authorization": f"Bearer {org_token}"},
    )
    assert bookings_res.status_code == 200
    b_data = bookings_res.json()
    assert b_data["total"] == 1
    assert b_data["items"][0]["quantity"] == 2

    # Other organizer cannot view bookings
    unauth_res = client.get(
        f"/api/v1/organizer/events/{event_id}/bookings",
        headers={"Authorization": f"Bearer {other_org_token}"},
    )
    assert unauth_res.status_code == 403


def test_customer_cannot_access_organizer_endpoints(client: TestClient):
    cust_token = get_token(client, "cust_forbidden@example.com", "customer")
    res = client.get(
        "/api/v1/organizer/events",
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert res.status_code == 403
    assert "organizer access required" in res.json()["detail"].lower()
