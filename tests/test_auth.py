"""
Unit and integration tests for Authentication endpoints.
"""
from fastapi.testclient import TestClient


def test_register_customer_success(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "customer@example.com",
            "password": "password123",
            "full_name": "Alice Customer",
            "role": "customer",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "customer@example.com"
    assert data["full_name"] == "Alice Customer"
    assert data["role"] == "customer"
    assert "hashed_password" not in data


def test_register_organizer_success(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "organizer@example.com",
            "password": "password123",
            "full_name": "Bob Organizer",
            "role": "organizer",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "organizer"


def test_register_duplicate_email_fails(client: TestClient):
    payload = {
        "email": "dup@example.com",
        "password": "password123",
        "full_name": "Dup User",
        "role": "customer",
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already registered" in res2.json()["detail"].lower()


def test_login_success(client: TestClient):
    # Register first
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "password": "mypassword123",
            "full_name": "Login User",
            "role": "customer",
        },
    )

    # Login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@example.com",
            "password": "mypassword123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password(client: TestClient):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpwd@example.com",
            "password": "mypassword123",
            "full_name": "Login User",
            "role": "customer",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "wrongpwd@example.com",
            "password": "incorrectpassword",
        },
    )
    assert response.status_code == 401


def test_get_current_user_profile(client: TestClient):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "me@example.com",
            "password": "password123",
            "full_name": "Me User",
            "role": "customer",
        },
    )

    token_res = client.post(
        "/api/v1/auth/login",
        json={"email": "me@example.com", "password": "password123"},
    )
    token = token_res.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


def test_get_current_user_unauthorized(client: TestClient):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_get_current_user_invalid_jwt(client: TestClient):
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.fake.token"},
    )
    assert response.status_code == 401


def test_get_current_user_expired_jwt(client: TestClient):
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    from app.config import settings

    # Create expired token
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "role": "customer",
        "iat": past,
        "exp": past + timedelta(minutes=10),
    }
    expired_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401

