from datetime import timedelta

from app.security import create_access_token


def test_register_returns_user_without_password(client):
    response = client.post("/auth/register", json={
        "username": "mokshith",
        "email": "mokshith@example.com",
        "full_name": "Mokshith Vooka",
        "password": "password123",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "mokshith"
    assert data["full_name"] == "Mokshith Vooka"
    assert "password" not in data
    assert "hashed_password" not in data


def test_register_creates_default_categories(client, auth_headers):
    response = client.get("/categories", headers=auth_headers)
    names = {c["name"] for c in response.json()}
    assert names == {"Food", "Transport", "Bills", "Shopping", "Entertainment", "Health", "Other"}


def test_register_duplicate_username_is_409(client, auth_headers):
    response = client.post("/auth/register", json={
        "username": "mokshith",
        "email": "someone-else@example.com",
        "password": "password123",
    })
    assert response.status_code == 409


def test_register_validates_input(client):
    response = client.post("/auth/register", json={
        "username": "ab",              # too short
        "email": "not-an-email",
        "password": "short",           # too short
    })
    assert response.status_code == 422
    bad_fields = {error["loc"][-1] for error in response.json()["detail"]}
    assert bad_fields == {"username", "email", "password"}


def test_login_wrong_password_is_401(client, auth_headers):
    response = client.post("/auth/token", data={"username": "mokshith", "password": "wrong-password"})
    assert response.status_code == 401


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_with_token(client, auth_headers):
    response = client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "mokshith"


def test_tampered_token_is_rejected(client, auth_headers):
    token = auth_headers["Authorization"].removeprefix("Bearer ")
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert response.status_code == 401


def test_expired_token_is_rejected(client, auth_headers):
    token = create_access_token(1, "mokshith", expires_delta=timedelta(minutes=-1))
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
