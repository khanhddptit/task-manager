import re
import smtplib
from datetime import datetime, timedelta
from urllib.parse import parse_qs

from app.db import get_db
from app.services.auth_service import register_user


def csrf_headers(client):
    token = client.get("/auth/csrf").json["csrf_token"]
    return {"X-CSRFToken": token}


def configure_smtp(monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_URL", "https://kairo.example")
    monkeypatch.setenv("SMTP_HOST", "smtp.example")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_FROM", "Kairo <no-reply@example.com>")
    monkeypatch.setenv("SMTP_USERNAME", "mailer")
    monkeypatch.setenv("SMTP_PASSWORD", "test-password")
    monkeypatch.setenv("SMTP_USE_TLS", "false")
    monkeypatch.setenv("SMTP_USE_SSL", "false")


def request_reset(client, email):
    return client.post(
        "/auth/password-reset/request",
        json={"email": email},
        headers=csrf_headers(client),
    )


def complete_reset(client, token, password="new-password-123"):
    return client.post(
        "/auth/password-reset/complete",
        json={
            "token": token,
            "new_password": password,
            "confirm_password": password,
        },
        headers=csrf_headers(client),
    )


def captured_token(message):
    match = re.search(r"/password-reset#token=([^\s]+)", message)
    assert match
    return parse_qs("token=" + match.group(1))["token"][0]


def create_local_user(app, username="reset-user", email="reset@example.com"):
    with app.app_context():
        return register_user(username, "old-password-123", email, username)


def login(client, username, password):
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    return {"X-CSRFToken": response.json["csrf_token"]}


def test_request_is_generic_and_rate_limited_by_email(
    app, monkeypatch
):
    configure_smtp(monkeypatch)
    create_local_user(app)
    sent_messages = []
    monkeypatch.setattr(
        "app.services.auth_service._send_email",
        lambda message: sent_messages.append(message.get_content()) or "sent",
    )
    client = app.test_client()

    known = request_reset(client, "reset@example.com")
    unknown = request_reset(client, "unknown@example.com")
    repeated = request_reset(client, "reset@example.com")

    assert known.status_code == unknown.status_code == repeated.status_code == 202
    assert known.json == unknown.json == repeated.json
    assert len(sent_messages) == 1
    assert "token" not in str(known.json).lower()
    assert "https://kairo.example/password-reset" not in str(known.json)

    token = captured_token(sent_messages[0])
    with app.app_context():
        stored = get_db().execute(
            "SELECT token_hash, expires_at FROM password_reset_token"
        ).fetchone()
        assert stored["token_hash"] != token
        assert len(stored["token_hash"]) == 64
        remaining = datetime.strptime(
            stored["expires_at"], "%Y-%m-%d %H:%M:%S"
        ) - datetime.utcnow()
        assert timedelta(minutes=29, seconds=50) < remaining <= timedelta(minutes=30)


def test_expired_reset_token_is_rejected(app, monkeypatch):
    configure_smtp(monkeypatch)
    create_local_user(app)
    sent_messages = []
    monkeypatch.setattr(
        "app.services.auth_service._send_email",
        lambda message: sent_messages.append(message.get_content()) or "sent",
    )
    client = app.test_client()
    assert request_reset(client, "reset@example.com").status_code == 202
    token = captured_token(sent_messages[0])
    with app.app_context():
        get_db().execute(
            "UPDATE password_reset_token SET expires_at = '2000-01-01 00:00:00'"
        )
        get_db().commit()

    response = complete_reset(client, token)
    assert response.status_code == 400
    assert response.json["error"]["code"] == "reset_token_invalid"


def test_reset_token_is_one_time_and_invalidates_existing_sessions(app, monkeypatch):
    configure_smtp(monkeypatch)
    user_id = create_local_user(app)
    sent_messages = []
    monkeypatch.setattr(
        "app.services.auth_service._send_email",
        lambda message: sent_messages.append(message.get_content()) or "sent",
    )
    first_session = app.test_client()
    second_session = app.test_client()
    login(first_session, "reset-user", "old-password-123")
    login(second_session, "reset-user", "old-password-123")

    reset_client = app.test_client()
    assert request_reset(reset_client, "reset@example.com").status_code == 202
    token = captured_token(sent_messages[0])
    completed = complete_reset(reset_client, token)
    assert completed.status_code == 200
    assert complete_reset(reset_client, token).status_code == 400
    assert first_session.get("/auth/me").status_code == 401
    assert second_session.get("/auth/me").status_code == 401

    new_login = app.test_client()
    assert login(new_login, "reset-user", "new-password-123")
    with app.app_context():
        user = get_db().execute(
            "SELECT auth_version, password_login_enabled FROM user WHERE id = ?",
            (user_id,),
        ).fetchone()
        assert user["auth_version"] == 1
        assert user["password_login_enabled"] == 1


def test_smtp_failure_is_generic_and_does_not_leave_a_token(app, monkeypatch):
    configure_smtp(monkeypatch)
    create_local_user(app)

    class BrokenSMTP:
        def __init__(self, *args, **kwargs):
            raise smtplib.SMTPException("delivery failed")

    monkeypatch.setattr(
        "app.services.email_service.smtplib.SMTP", BrokenSMTP
    )
    response = request_reset(app.test_client(), "reset@example.com")
    assert response.status_code == 202
    assert "delivery failed" not in str(response.json)
    with app.app_context():
        assert get_db().execute(
            "SELECT COUNT(*) FROM password_reset_token"
        ).fetchone()[0] == 0


def test_google_only_account_does_not_gain_password_login(app, monkeypatch):
    configure_smtp(monkeypatch)
    with app.app_context():
        user_id = register_user("google-only", "placeholder-password", "google@example.com")
        get_db().execute(
            "UPDATE user SET password_login_enabled = 0 WHERE id = ?", (user_id,)
        )
        get_db().commit()
    sent_messages = []
    monkeypatch.setattr(
        "app.services.auth_service._send_email",
        lambda message: sent_messages.append(message.as_string()) or "sent",
    )

    response = request_reset(app.test_client(), "google@example.com")
    assert response.status_code == 202
    assert sent_messages == []
    with app.app_context():
        user = get_db().execute(
            "SELECT password_login_enabled FROM user WHERE id = ?", (user_id,)
        ).fetchone()
        assert user["password_login_enabled"] == 0
        assert get_db().execute(
            "SELECT COUNT(*) FROM password_reset_token"
        ).fetchone()[0] == 0


def test_reset_page_does_not_cache_or_refer_reset_token(app):
    response = app.test_client().get("/password-reset#token=not-for-logs")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert b"not-for-logs" not in response.data
