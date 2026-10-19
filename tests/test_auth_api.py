import sqlite3
from datetime import timedelta
from unittest.mock import patch

import pytest
from flask import g, jsonify
from itsdangerous import TimestampSigner
from werkzeug.security import check_password_hash

from app.auth.decorators import login_required
from app.db import get_db
from app.models.user import get_user_by_username
from app.services.auth_service import UsernameTakenError, register_user


PASSWORD = "correct-password"


def csrf_token(client):
    response = client.get("/auth/csrf")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    return response.json["csrf_token"]


def post_json(client, path, **data):
    if path == "/auth/register" and "username" in data and "email" not in data:
        data["email"] = f"{str(data['username']).strip()}@example.test"
    return client.post(path, json=data, headers={"X-CSRFToken": csrf_token(client)})


def login(client, username="demo", password=PASSWORD):
    return post_json(client, "/auth/login", username=username, password=password)


def assert_error(response, status, code):
    assert response.status_code == status
    assert response.is_json
    assert response.json["error"]["code"] == code
    assert "Location" not in response.headers
    assert response.headers["Cache-Control"] == "no-store"


def test_registration_hashes_password_and_requires_login(app, client):
    response = post_json(
        client, "/auth/register", username="  new_user  ",
        password=PASSWORD, confirm_password=PASSWORD,
    )
    assert response.status_code == 201
    assert "Location" not in response.headers
    assert response.json["user"]["username"] == "new_user"
    assert set(response.json["user"]) == {
        "id", "username", "display_name", "email", "avatar_url",
        "password_login_enabled", "google_connected", "created_at"
    }
    with app.app_context():
        user = get_user_by_username("new_user")
        assert user["password_hash"] != PASSWORD
        assert check_password_hash(user["password_hash"], PASSWORD)
    with client.session_transaction() as stored:
        assert "user_id" not in stored
        assert PASSWORD not in str(dict(stored))
    assert_error(client.get("/auth/me"), 401, "authentication_required")
    assert login(client, "new_user").status_code == 200


@pytest.mark.parametrize("changes,field", [
    ({"username": ""}, "username"),
    ({"username": "ab"}, "username"),
    ({"username": "a" * 33}, "username"),
    ({"username": "bad name"}, "username"),
    ({"username": "user'--"}, "username"),
    ({"username": None}, "username"),
    ({"username": 123}, "username"),
    ({"username": []}, "username"),
    ({"password": ""}, "password"),
    ({"password": "short"}, "password"),
    ({"password": "x" * 129}, "password"),
    ({"password": 123}, "password"),
    ({"password": None}, "password"),
    ({"password": {}}, "password"),
    ({"confirm_password": None}, "confirm_password"),
    ({"confirm_password": "wrong"}, "confirm_password"),
])
def test_registration_validation(app, client, changes, field):
    data = {"username": "valid", "password": PASSWORD, "confirm_password": PASSWORD}
    data.update(changes)
    response = post_json(client, "/auth/register", **data)
    assert_error(response, 400, "validation_error")
    assert field in response.json["error"]["fields"]
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM user").fetchone()[0] == 0


@pytest.mark.parametrize("path", ["/auth/register", "/auth/login"])
def test_missing_fields(client, path):
    response = post_json(client, path)
    assert_error(response, 400, "validation_error")
    expected = {"username", "password"}
    if path == "/auth/register":
        expected.update({"confirm_password", "email"})
    assert set(response.json["error"]["fields"]) == expected


def test_duplicate_username_does_not_replace_password(app, client, user_id):
    response = post_json(
        client, "/auth/register", username="demo",
        password="different-password", confirm_password="different-password",
    )
    assert_error(response, 409, "username_taken")
    assert "different-password" not in response.text
    with app.app_context():
        assert check_password_hash(get_user_by_username("demo")["password_hash"], PASSWORD)
        assert get_db().execute("SELECT COUNT(*) FROM user").fetchone()[0] == 1
        register_user("another", PASSWORD)
        assert get_db().execute("SELECT COUNT(*) FROM user").fetchone()[0] == 2


def test_service_handles_database_unique_constraint(app, user_id):
    with app.app_context():
        with pytest.raises(UsernameTakenError):
            register_user("demo", PASSWORD)


def test_unrelated_database_errors_are_not_reported_as_duplicate(app):
    with app.app_context():
        with patch("app.services.auth_service.create_user", side_effect=sqlite3.IntegrityError):
            with pytest.raises(sqlite3.IntegrityError):
                register_user("new_user", PASSWORD)


def test_password_is_not_trimmed(client):
    password = "  exact password  "
    post_json(client, "/auth/register", username="spaces",
              password=password, confirm_password=password)
    assert_error(login(client, "spaces", password.strip()), 401, "invalid_credentials")
    assert login(client, "spaces", password).status_code == 200


def test_login_rotates_session_and_returns_new_csrf_token(app, client, user_id):
    with client.session_transaction() as stored:
        stored["old_state"] = "remove-me"
    old_csrf = csrf_token(client)
    response = client.post("/auth/login", json={
        "username": " demo ", "password": PASSWORD,
    }, headers={"X-CSRFToken": old_csrf})
    assert response.status_code == 200
    assert response.json["user"]["id"] == user_id
    new_csrf = response.json["csrf_token"]
    assert new_csrf != old_csrf
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie and "Expires=" in cookie
    with client.session_transaction() as stored:
        assert set(stored) == {"user_id", "auth_version", "_permanent", "csrf_token"}
        assert stored["user_id"] == user_id
        assert stored.permanent is True
    with client:
        response = client.get("/auth/me")
        assert response.status_code == 200
        assert response.json["user"]["id"] == user_id
        assert set(response.json["user"]) == {
            "id", "username", "display_name", "email", "avatar_url",
            "password_login_enabled", "google_connected", "created_at"
        }
        assert "password_hash" not in g.user.keys()
    assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(hours=8)
    assert app.config["SESSION_REFRESH_EACH_REQUEST"] is True
    assert_error(client.post("/auth/logout", headers={"X-CSRFToken": old_csrf}), 400, "csrf_failed")
    response = client.post("/auth/logout", headers={"X-CSRFToken": new_csrf})
    assert response.status_code == 200
    with client.session_transaction() as stored:
        assert not stored
    assert_error(client.get("/auth/me"), 401, "authentication_required")
    assert login(client).status_code == 200


@pytest.mark.parametrize("username,password", [
    ("demo", "wrong-password"), ("missing", PASSWORD), ("' OR 1=1 --", PASSWORD),
])
def test_failed_login_has_generic_error(client, user_id, username, password):
    response = login(client, username, password)
    assert_error(response, 401, "invalid_credentials")
    assert response.json["error"]["message"] == "Tên đăng nhập hoặc mật khẩu không đúng."
    assert "wrong-password" not in response.text
    with client.session_transaction() as stored:
        assert "user_id" not in stored


@pytest.mark.parametrize("username,password", [
    (None, PASSWORD), ([], PASSWORD), (" ", PASSWORD), ("a" * 33, PASSWORD),
    ("demo", None), ("demo", {}), ("demo", ""), ("demo", "x" * 129),
])
def test_login_rejects_invalid_types_and_lengths(client, username, password):
    assert_error(login(client, username, password), 400, "validation_error")


def test_login_required_is_reusable_without_redirect(app, client, user_id):
    @app.get("/private-test")
    @login_required
    def private_test():
        return jsonify(user_id=g.user["id"])

    response = client.get("/private-test")
    assert response.status_code == 401
    assert response.json["error"]["code"] == "authentication_required"
    assert "Location" not in response.headers
    login(client)
    assert client.get("/private-test").json == {"user_id": user_id}


@pytest.mark.parametrize("path", ["/auth/login", "/auth/register"])
def test_authenticated_users_cannot_replace_current_account(client, user_id, path):
    login(client)
    assert_error(post_json(client, path), 409, "already_authenticated")
    assert client.get("/auth/me").json["user"]["id"] == user_id


@pytest.mark.parametrize("path", ["/auth/register", "/auth/login", "/auth/logout"])
def test_get_does_not_render_forms_or_logout(client, path):
    response = client.get(path)
    assert_error(response, 405, "method_not_allowed")
    assert "POST" in response.headers["Allow"]


def test_logout_requires_login(client):
    assert_error(post_json(client, "/auth/logout"), 401, "authentication_required")


@pytest.mark.parametrize("path", ["/auth/register", "/auth/login", "/auth/logout"])
@pytest.mark.parametrize("token", [None, "invalid-token"])
def test_csrf_rejects_missing_or_invalid_token(app, client, user_id, path, token):
    if path == "/auth/logout":
        login(client)
    headers = {} if token is None else {"X-CSRFToken": token}
    response = client.post(path, json={
        "username": "new_user", "password": PASSWORD, "confirm_password": PASSWORD,
    }, headers=headers)
    assert_error(response, 400, "csrf_failed")
    with app.app_context():
        assert get_user_by_username("new_user") is None
    with client.session_transaction() as stored:
        assert ("user_id" in stored) == (path == "/auth/logout")


def test_csrf_token_cannot_be_reused_by_another_client(app, client):
    token = csrf_token(client)
    other_client = app.test_client()
    assert_error(other_client.post("/auth/login", json={
        "username": "demo", "password": PASSWORD,
    }, headers={"X-CSRFToken": token}), 400, "csrf_failed")


def test_expired_csrf_token_rejected(client):
    with patch.object(TimestampSigner, "get_timestamp", return_value=1000):
        token = csrf_token(client)
    with patch.object(TimestampSigner, "get_timestamp", return_value=4601):
        response = client.post("/auth/login", json={
            "username": "demo", "password": PASSWORD,
        }, headers={"X-CSRFToken": token})
    assert_error(response, 400, "csrf_failed")


def test_deleted_user_is_logged_out(app, client, user_id):
    login(client)
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM user WHERE id = ?", (user_id,))
        db.commit()
    assert_error(client.get("/auth/me"), 401, "authentication_required")
    with client.session_transaction() as stored:
        assert "user_id" not in stored


@pytest.mark.parametrize("invalid_id", ["1", True, [], -1, 99999, 2**70])
def test_stale_or_invalid_session_user_is_rejected(client, invalid_id):
    with client.session_transaction() as stored:
        stored["user_id"] = invalid_id
    assert_error(client.get("/auth/me"), 401, "authentication_required")
    with client.session_transaction() as stored:
        assert "user_id" not in stored


def test_tampered_session_cookie_is_rejected(app, client, user_id):
    login(client)
    cookie_name = app.config["SESSION_COOKIE_NAME"]
    cookie = client.get_cookie(cookie_name)
    client.set_cookie(cookie_name, cookie.value + "tampered")
    assert_error(client.get("/auth/me"), 401, "authentication_required")


def test_session_expires_after_eight_hours(client, user_id):
    with patch.object(TimestampSigner, "get_timestamp", return_value=1000):
        login(client)
    with patch.object(TimestampSigner, "get_timestamp", return_value=1000 + 8 * 3600 + 1):
        assert_error(client.get("/auth/me"), 401, "authentication_required")


def test_activity_refreshes_session(client, user_id):
    with patch.object(TimestampSigner, "get_timestamp", return_value=1000):
        login(client)
    with patch.object(TimestampSigner, "get_timestamp", return_value=1000 + 7 * 3600):
        response = client.get("/auth/me")
        assert response.status_code == 200
        assert "Set-Cookie" in response.headers
    with patch.object(TimestampSigner, "get_timestamp", return_value=1000 + 9 * 3600):
        assert client.get("/auth/me").status_code == 200


def test_secure_cookie_in_https_mode(app, client, user_id):
    app.config["SESSION_COOKIE_SECURE"] = True
    assert "Secure" in login(client).headers["Set-Cookie"]


@pytest.mark.parametrize("path", ["/auth/login", "/auth/register"])
@pytest.mark.parametrize("body,content_type,status,code", [
    ("{", "application/json", 400, "bad_request"),
    ("[]", "application/json", 400, "bad_request"),
    ("null", "application/json", 400, "bad_request"),
    ('"text"', "application/json", 400, "bad_request"),
    ("123", "application/json", 400, "bad_request"),
    ("{}", "text/plain", 415, "unsupported_media_type"),
    ("username=demo", "application/x-www-form-urlencoded", 415, "unsupported_media_type"),
])
def test_invalid_request_bodies_return_json(client, path, body, content_type, status, code):
    response = client.post(path, data=body, content_type=content_type,
                           headers={"X-CSRFToken": csrf_token(client)})
    assert_error(response, status, code)


def test_unknown_auth_endpoint_returns_json(client):
    assert_error(client.get("/auth/missing"), 404, "not_found")


def test_oversized_auth_request_returns_json(app, client):
    token = csrf_token(client)
    app.config["MAX_CONTENT_LENGTH"] = 100
    response = client.post("/auth/register", json={"username": "a" * 101},
                           headers={"X-CSRFToken": token})
    assert_error(response, 413, "request_entity_too_large")


def test_internal_error_does_not_leak_details(app, client):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    token = csrf_token(client)
    with patch("app.auth.routes.authenticate_user", side_effect=RuntimeError("private-detail")):
        response = client.post("/auth/login", json={
            "username": "demo", "password": PASSWORD,
        }, headers={"X-CSRFToken": token})
    assert_error(response, 500, "internal_server_error")
    assert "private-detail" not in response.text


def test_no_redirect_for_next_parameter(client, user_id):
    response = client.post("/auth/login?next=https://example.com", json={
        "username": "demo", "password": PASSWORD,
    }, headers={"X-CSRFToken": csrf_token(client)})
    assert response.status_code == 200
    assert "Location" not in response.headers
