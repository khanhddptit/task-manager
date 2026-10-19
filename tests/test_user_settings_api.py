from io import BytesIO

from app.db import get_db
from app.services.auth_service import register_user


def csrf_token(client):
    return client.get("/auth/csrf").json["csrf_token"]


def login(client, username="demo", password="correct-password"):
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password},
        headers={"X-CSRFToken": csrf_token(client)},
    )
    assert response.status_code == 200
    return response.json["csrf_token"]


def test_registration_requires_unique_email_and_sets_profile_defaults(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "new_user",
            "email": "NEW@example.test",
            "password": "correct-password",
            "confirm_password": "correct-password",
        },
        headers={"X-CSRFToken": csrf_token(client)},
    )
    assert response.status_code == 201
    assert response.json["user"]["email"] == "new@example.test"
    assert response.json["user"]["display_name"] == "new_user"

    duplicate = client.post(
        "/auth/register",
        json={
            "username": "another_user",
            "email": "new@example.test",
            "password": "correct-password",
            "confirm_password": "correct-password",
        },
        headers={"X-CSRFToken": csrf_token(client)},
    )
    assert duplicate.status_code == 409
    assert duplicate.json["error"]["code"] == "email_taken"


def test_profile_update_requires_email_and_rejects_duplicate(app, client, user_id):
    token = login(client)
    current = client.get("/auth/me")
    assert current.status_code == 200
    assert current.json["user"]["email"] is None

    missing_email = client.patch(
        "/auth/me",
        json={"display_name": "Demo Person"},
        headers={"X-CSRFToken": token},
    )
    assert missing_email.status_code == 400
    assert "email" in missing_email.json["error"]["fields"]

    with app.app_context():
        register_user("other-user", "correct-password", "taken@example.test")

    duplicate = client.patch(
        "/auth/me",
        json={"display_name": "Demo Person", "email": "TAKEN@example.test"},
        headers={"X-CSRFToken": token},
    )
    assert duplicate.status_code == 409
    assert duplicate.json["error"]["code"] == "email_taken"

    updated = client.patch(
        "/auth/me",
        json={"display_name": "  Demo Person  ", "email": "DEMO@example.test"},
        headers={"X-CSRFToken": token},
    )
    assert updated.status_code == 200
    assert updated.json["user"]["display_name"] == "Demo Person"
    assert updated.json["user"]["email"] == "demo@example.test"
    assert updated.json["user"]["username"] == "demo"
    with app.app_context():
        stored = get_db().execute(
            "SELECT display_name, email FROM user WHERE id = ?", (user_id,)
        ).fetchone()
    assert tuple(stored) == ("Demo Person", "demo@example.test")


def test_password_change_revokes_other_sessions(app, client, user_id):
    client_token = login(client)
    other_client = app.test_client()
    login(other_client)

    changed = client.post(
        "/auth/password",
        json={
            "current_password": "correct-password",
            "new_password": "new-correct-password",
            "confirm_password": "new-correct-password",
        },
        headers={"X-CSRFToken": client_token},
    )
    assert changed.status_code == 200
    assert client.get("/auth/me").status_code == 200
    assert other_client.get("/auth/me").status_code == 401

    old_password_client = app.test_client()
    old_password = old_password_client.post(
        "/auth/login",
        json={"username": "demo", "password": "correct-password"},
        headers={"X-CSRFToken": csrf_token(old_password_client)},
    )
    assert old_password.status_code == 401

    new_client = app.test_client()
    assert login(new_client, password="new-correct-password")


def test_password_change_requires_current_password_and_csrf(client, user_id):
    token = login(client)
    wrong_password = client.post(
        "/auth/password",
        json={
            "current_password": "wrong-password",
            "new_password": "new-correct-password",
            "confirm_password": "new-correct-password",
        },
        headers={"X-CSRFToken": token},
    )
    assert wrong_password.status_code == 400
    assert wrong_password.json["error"]["code"] == "current_password_invalid"

    missing_token = client.post(
        "/auth/password",
        json={
            "current_password": "correct-password",
            "new_password": "new-correct-password",
            "confirm_password": "new-correct-password",
        },
    )
    assert missing_token.status_code == 400
    assert missing_token.json["error"]["code"] == "csrf_failed"


def test_avatar_upload_is_private_validated_and_replaced(app, client, tmp_path, user_id):
    app.config["AVATAR_STORAGE"] = str(tmp_path / "avatars")
    token = login(client)
    missing = client.get("/auth/me/avatar")
    assert missing.status_code == 404

    png = bytes.fromhex("89504e470d0a1a0a") + b"demo-image-data"
    uploaded = client.post(
        "/auth/me/avatar",
        data={"avatar": (BytesIO(png), "../../avatar.png")},
        headers={"X-CSRFToken": token},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 200
    assert uploaded.json["user"]["avatar_url"] == "/auth/me/avatar"
    avatar_path = next((tmp_path / "avatars").iterdir())
    assert avatar_path.name != "avatar.png"
    assert client.get("/auth/me/avatar").mimetype == "image/png"

    replaced = client.post(
        "/auth/me/avatar",
        data={"avatar": (BytesIO(bytes.fromhex("ffd8ff6a706567ffd9")), "photo.jpg")},
        headers={"X-CSRFToken": token},
        content_type="multipart/form-data",
    )
    assert replaced.status_code == 200
    files = list((tmp_path / "avatars").iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".jpg"
    assert client.get("/auth/me/avatar").mimetype == "image/jpeg"

    deleted = client.delete(
        "/auth/me/avatar", headers={"X-CSRFToken": token}
    )
    assert deleted.status_code == 200
    assert deleted.json["user"]["avatar_url"] is None
    assert list((tmp_path / "avatars").iterdir()) == []
    assert client.get("/auth/me/avatar").status_code == 404

    invalid = client.post(
        "/auth/me/avatar",
        data={"avatar": (BytesIO(b"not an image"), "photo.svg")},
        headers={"X-CSRFToken": token},
        content_type="multipart/form-data",
    )
    assert invalid.status_code == 400
    assert "avatar" in invalid.json["error"]["fields"]


def test_avatar_upload_rejects_oversized_file(app, client, tmp_path, user_id):
    app.config["AVATAR_STORAGE"] = str(tmp_path / "avatars")
    token = login(client)
    too_large = bytes.fromhex("89504e470d0a1a0a") + b"x" * (2 * 1024 * 1024)
    response = client.post(
        "/auth/me/avatar",
        data={"avatar": (BytesIO(too_large), "large.png")},
        headers={"X-CSRFToken": token},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.json["error"]["code"] == "validation_error"
