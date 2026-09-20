"""
Unit and integration tests for Event endpoints.
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


def test_organizer_create_event(client: TestClient):
    token = get_token(client, "org1@example.com", "organizer")
    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=2)).isoformat()
    end = (now + timedelta(days=2, hours=3)).isoformat()

    response = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Tech Conference 2026",
            "description": "Annual tech conference",
            "location": "Convention Center, Hall A",
            "starts_at": start,
            "ends_at": end,
            "total_tickets": 100,
            "price_cents": 5000,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Tech Conference 2026"
    assert data["available_tickets"] == 100
    assert data["price_cents"] == 5000
    assert data["is_published"] is False


def test_customer_cannot_create_event(client: TestClient):
    token = get_token(client, "cust1@example.com", "customer")
    now = datetime.now(timezone.utc)

    response = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Unauthorized Event",
            "starts_at": (now + timedelta(days=1)).isoformat(),
            "ends_at": (now + timedelta(days=1, hours=2)).isoformat(),
            "total_tickets": 50,
            "price_cents": 1000,
        },
    )
    assert response.status_code == 403
    assert "organizer access required" in response.json()["detail"].lower()


def test_list_published_events_excludes_drafts(client: TestClient):
    org_token = get_token(client, "org2@example.com", "organizer")
    now = datetime.now(timezone.utc)

    # 1. Create draft event
    draft_res = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "Draft Secret Event",
            "starts_at": (now + timedelta(days=5)).isoformat(),
            "ends_at": (now + timedelta(days=5, hours=2)).isoformat(),
            "total_tickets": 50,
            "price_cents": 2000,
        },
    )
    draft_id = draft_res.json()["id"]

    # 2. Public list should be empty
    list_res1 = client.get("/api/v1/events/")
    assert list_res1.status_code == 200
    assert list_res1.json()["total"] == 0

    # 3. Publish event
    pub_res = client.patch(
        f"/api/v1/events/{draft_id}/publish?is_published=true",
        headers={"Authorization": f"Bearer {org_token}"},
    )
    assert pub_res.status_code == 200
    assert pub_res.json()["is_published"] is True

    # 4. Public list should now include it
    list_res2 = client.get("/api/v1/events/")
    assert list_res2.status_code == 200
    assert list_res2.json()["total"] == 1
    assert list_res2.json()["items"][0]["title"] == "Draft Secret Event"


def test_organizer_update_event(client: TestClient):
    token = get_token(client, "org3@example.com", "organizer")
    other_org_token = get_token(client, "org4@example.com", "organizer")
    now = datetime.now(timezone.utc)

    create_res = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Original Title",
            "starts_at": (now + timedelta(days=1)).isoformat(),
            "ends_at": (now + timedelta(days=1, hours=2)).isoformat(),
            "total_tickets": 50,
            "price_cents": 1000,
        },
    )
    event_id = create_res.json()["id"]

    # Other organizer cannot update
    fail_update = client.put(
        f"/api/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {other_org_token}"},
        json={
            "title": "Hijacked Title",
            "starts_at": (now + timedelta(days=1)).isoformat(),
            "ends_at": (now + timedelta(days=1, hours=2)).isoformat(),
            "total_tickets": 50,
            "price_cents": 1000,
        },
    )
    assert fail_update.status_code == 403

    # Owner can update
    success_update = client.put(
        f"/api/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Updated Title",
            "location": "Updated Hall B",
            "starts_at": (now + timedelta(days=1)).isoformat(),
            "ends_at": (now + timedelta(days=1, hours=2)).isoformat(),
            "total_tickets": 75,
            "price_cents": 1500,
        },
    )
    assert success_update.status_code == 200
    assert success_update.json()["title"] == "Updated Title"
    assert success_update.json()["available_tickets"] == 75


def test_delete_event(client: TestClient):
    token = get_token(client, "org5@example.com", "organizer")
    now = datetime.now(timezone.utc)

    create_res = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Event to delete",
            "starts_at": (now + timedelta(days=1)).isoformat(),
            "ends_at": (now + timedelta(days=1, hours=2)).isoformat(),
            "total_tickets": 50,
            "price_cents": 1000,
        },
    )
    event_id = create_res.json()["id"]

    del_res = client.delete(
        f"/api/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 204

    get_res = client.get(f"/api/v1/events/{event_id}")
    assert get_res.status_code == 404


def test_organizer_patch_event(client: TestClient):
    token = get_token(client, "org_patch@example.com", "organizer")
    now = datetime.now(timezone.utc)

    create_res = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Patch Original",
            "starts_at": (now + timedelta(days=1)).isoformat(),
            "ends_at": (now + timedelta(days=1, hours=2)).isoformat(),
            "total_tickets": 50,
            "price_cents": 1000,
        },
    )
    event_id = create_res.json()["id"]

    patch_res = client.patch(
        f"/api/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Patched Title", "location": "New Location"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Patched Title"
    assert patch_res.json()["location"] == "New Location"
    assert patch_res.json()["total_tickets"] == 50


def test_list_events_filtering_and_pagination(client: TestClient):
    token = get_token(client, "org_filter@example.com", "organizer")
    now = datetime.now(timezone.utc)

    # Create 3 published events with distinct titles and locations
    for i, (title, loc, offset_days) in enumerate([
        ("Python Summit", "San Francisco", 2),
        ("AI Conference", "New York", 4),
        ("Database Workshop", "San Francisco", 6),
    ]):
        res = client.post(
            "/api/v1/events/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": title,
                "location": loc,
                "starts_at": (now + timedelta(days=offset_days)).isoformat(),
                "ends_at": (now + timedelta(days=offset_days, hours=2)).isoformat(),
                "total_tickets": 100,
                "price_cents": 2000,
            },
        )
        e_id = res.json()["id"]
        client.patch(f"/api/v1/events/{e_id}/publish?is_published=true", headers={"Authorization": f"Bearer {token}"})

    # Test search query
    search_res = client.get("/api/v1/events/?search=Python")
    assert search_res.status_code == 200
    assert search_res.json()["total"] == 1
    assert search_res.json()["items"][0]["title"] == "Python Summit"

    # Test location filter
    loc_res = client.get("/api/v1/events/?location=San Francisco")
    assert loc_res.status_code == 200
    assert loc_res.json()["total"] == 2

    # Test date_from filter
    date_str = (now + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_from_res = client.get(f"/api/v1/events/?date_from={date_str}")
    assert date_from_res.status_code == 200
    assert date_from_res.json()["total"] == 2

    # Test pagination size limit
    page_res = client.get("/api/v1/events/?page=1&size=1")
    assert page_res.status_code == 200
    assert len(page_res.json()["items"]) == 1
    assert page_res.json()["total"] == 3
    assert page_res.json()["pages"] == 3


def test_cannot_reduce_total_tickets_below_booked_count(client: TestClient):
    org_token = get_token(client, "org_reduce@example.com", "organizer")
    cust_token = get_token(client, "cust_reduce@example.com", "customer")
    now = datetime.now(timezone.utc)

    create_res = client.post(
        "/api/v1/events/",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "Popular Show",
            "starts_at": (now + timedelta(days=2)).isoformat(),
            "ends_at": (now + timedelta(days=2, hours=2)).isoformat(),
            "total_tickets": 10,
            "price_cents": 1000,
        },
    )
    event_id = create_res.json()["id"]
    client.patch(f"/api/v1/events/{event_id}/publish?is_published=true", headers={"Authorization": f"Bearer {org_token}"})

    # Customer books 6 tickets
    client.post(
        "/api/v1/bookings/",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"event_id": event_id, "quantity": 6},
    )

    # Organizer attempts to reduce total_tickets to 4 (below 6 booked tickets)
    reduce_res = client.put(
        f"/api/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "Popular Show",
            "starts_at": (now + timedelta(days=2)).isoformat(),
            "ends_at": (now + timedelta(days=2, hours=2)).isoformat(),
            "total_tickets": 4,
            "price_cents": 1000,
        },
    )
    assert reduce_res.status_code == 400
    assert "cannot reduce" in reduce_res.json()["detail"].lower()

