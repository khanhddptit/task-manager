from authlib.integrations.base_client.errors import MismatchingStateError, OAuthError
from flask import redirect
import pytest

from app.core.db import get_db
from app.services.auth_service import (
    GoogleLinkRequiredError,
    complete_google_signin,
    link_google_identity,
    register_user,
)


class InvalidGrantGoogleClient:
    def authorize_access_token(self):
        raise OAuthError("invalid_grant")


class InvalidStateGoogleClient:
    def authorize_access_token(self):
        raise MismatchingStateError("mismatching_state")


class FakeGoogleClient:
    def __init__(self, userinfo=None):
        self.userinfo_data = userinfo or {
            "sub": "google-subject-1",
            "email": "google-user@example.test",
            "email_verified": True,
            "name": "Google User",
        }

    def authorize_redirect(self, redirect_uri, **kwargs):
        return redirect("https://accounts.google.com/mock-authorize")

    def authorize_access_token(self):
        return {"userinfo": self.userinfo_data}


def enable_fake_google(app, userinfo=None):
    app.extensions["google_oauth_enabled"] = True
    fake_client = FakeGoogleClient(userinfo)
    app.extensions["google_oauth"].create_client = lambda name: fake_client
    return fake_client


def test_google_status_and_unconfigured_login(client):
    status = client.get("/auth/google/status")
    assert status.status_code == 200
    assert status.json == {"enabled": False}

    response = client.get("/auth/google")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/login?oauth_error=google_unconfigured"
    )


def test_google_login_starts_oauth_when_configured(app, client):
    enable_fake_google(app)
    response = client.get("/auth/google")
    assert response.status_code == 302
    assert response.headers["Location"] == "https://accounts.google.com/mock-authorize"


def test_google_oauth_errors_show_safe_callback_diagnostic(app, client):
    app.extensions["google_oauth_enabled"] = True
    app.extensions["google_oauth"].create_client = lambda name: InvalidGrantGoogleClient()
    response = client.get("/auth/google/callback")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/login?oauth_error=google_invalid_grant"
    )


def test_google_state_errors_have_safe_diagnostic(app, client):
    app.extensions["google_oauth_enabled"] = True
    app.extensions["google_oauth"].create_client = lambda name: InvalidStateGoogleClient()
    response = client.get("/auth/google/callback")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/login?oauth_error=google_state_mismatch"
    )


def test_google_signin_creates_account_only_for_verified_new_email(app):
    enable_fake_google(app)
    client = app.test_client()
    response = client.get("/auth/google/callback")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/tasks/")
    with client:
        user_response = client.get("/auth/me")
        assert user_response.status_code == 200
        user = user_response.json["user"]
        assert user["email"] == "google-user@example.test"
        assert user["display_name"] == "Google User"
        assert user["password_login_enabled"] is False
        assert user["google_connected"] is True
        username = user["username"]
        csrf = client.get("/auth/csrf").json["csrf_token"]
        set_password = client.post(
            "/auth/password",
            json={
                "new_password": "new-google-user-password",
                "confirm_password": "new-google-user-password",
            },
            headers={"X-CSRFToken": csrf},
        )
        assert set_password.status_code == 200
        assert client.get("/auth/me").json["user"]["password_login_enabled"] is True

    password_client = app.test_client()
    token = password_client.get("/auth/csrf").json["csrf_token"]
    password_login = password_client.post(
        "/auth/login",
        json={"username": username, "password": "not-a-real-password"},
        headers={"X-CSRFToken": token},
    )
    assert password_login.status_code == 401

    password_client = app.test_client()
    token = password_client.get("/auth/csrf").json["csrf_token"]
    enabled_login = password_client.post(
        "/auth/login",
        json={"username": username, "password": "new-google-user-password"},
        headers={"X-CSRFToken": token},
    )
    assert enabled_login.status_code == 200

    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM user").fetchone()[0] == 1
        assert get_db().execute("SELECT COUNT(*) FROM oauth_identity").fetchone()[0] == 1


def test_google_signin_requires_verified_email(app):
    enable_fake_google(app, {
        "sub": "unverified-subject",
        "email": "unverified@example.test",
        "email_verified": False,
        "name": "Unverified User",
    })
    client = app.test_client()
    response = client.get("/auth/google/callback")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/login?oauth_error=google_profile_unverified"
    )
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM user").fetchone()[0] == 0


def test_existing_email_requires_explicit_link_then_google_signin_uses_link(app):
    with app.app_context():
        user_id = register_user(
            "local-user", "correct-password", "local@example.test", "Local User"
        )
        with pytest.raises(GoogleLinkRequiredError):
            complete_google_signin(
                "linked-subject", "local@example.test", "Google Name"
            )
        linked_user = link_google_identity(
            user_id, "linked-subject", "local@example.test"
        )
        signed_in_user = complete_google_signin(
            "linked-subject", "local@example.test", "Google Name"
        )
        assert linked_user["id"] == user_id
        assert signed_in_user["id"] == user_id
        assert bool(signed_in_user["google_connected"]) is True
        assert bool(signed_in_user["password_login_enabled"]) is True


def test_google_link_requires_authenticated_user_and_matching_email(app, client, user_id):
    fake = enable_fake_google(app, {
        "sub": "link-subject",
        "email": "demo@example.test",
        "email_verified": True,
        "name": "Demo",
    })
    response = client.get("/auth/google/link")
    assert response.status_code == 401

    with app.app_context():
        get_db().execute(
            "UPDATE user SET email = 'demo@example.test' WHERE id = ?",
            (user_id,),
        )
        get_db().commit()
    with client.session_transaction() as stored:
        stored["user_id"] = user_id
        stored["auth_version"] = 0
        stored["google_link_user_id"] = user_id
    fake.userinfo_data["email"] = "different@example.test"
    response = client.get("/auth/google/callback")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/settings?oauth_error=google_email_mismatch"
    )
    assert client.get("/auth/me").json["user"]["google_connected"] is False
