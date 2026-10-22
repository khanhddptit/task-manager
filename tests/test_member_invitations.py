from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from app.core.db import get_db
from app.services.auth_service import register_user
from app.services.project_service import create_project
from app.services.workspace_service import create_workspace


def authenticate(client, username):
    csrf = client.get("/auth/csrf").json["csrf_token"]
    response = client.post(
        "/auth/login",
        json={"username": username, "password": "correct-password"},
        headers={"X-CSRFToken": csrf},
    )
    assert response.status_code == 200
    return {"X-CSRFToken": response.json["csrf_token"]}


@pytest.fixture()
def member_world(app):
    with app.app_context():
        users = {
            "owner": register_user(
                "invite-owner", "correct-password", "owner@example.com", "Workspace Owner"
            ),
            "member": register_user(
                "invite-member", "correct-password", "member@example.com", "Workspace Member"
            ),
            "invitee": register_user(
                "invitee", "correct-password", "guest@example.com", "Guest User"
            ),
            "wrong": register_user(
                "wrong-user", "correct-password", "wrong@example.com", "Wrong User"
            ),
        }
        workspace = create_workspace("Kairo Team", "", users["owner"])
        workspace_id = workspace["id"]
        get_db().execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) "
            "VALUES (?, ?, 'member')",
            (workspace_id, users["member"]),
        )
        get_db().commit()
        project = create_project(workspace_id, users["owner"], "Kairo Project", "")
    return {"users": users, "workspace_id": workspace_id, "project_id": project["id"]}


def workspace_url(world, suffix=""):
    return f"/workspaces/{world['workspace_id']}{suffix}"


def project_url(world, suffix=""):
    return (
        f"/workspaces/{world['workspace_id']}/projects/{world['project_id']}"
        f"{suffix}"
    )


def clear_smtp_environment(monkeypatch):
    for key in (
        "SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM",
        "SMTP_USE_TLS", "SMTP_USE_SSL", "PUBLIC_APP_URL", "INVITATION_TTL_HOURS",
    ):
        monkeypatch.delenv(key, raising=False)


def create_invite(client, url, headers, email="guest@example.com"):
    return client.post(url, json={"email": email}, headers=headers)


def invitation_token(response):
    return parse_qs(urlsplit(response.json["invitation"]["invite_url"]).query)["token"][0]


def test_workspace_and_project_member_lists_include_email_and_role(app, member_world):
    world = member_world
    with app.app_context():
        get_db().execute(
            "INSERT INTO project_member (project_id, workspace_id, user_id, role) "
            "VALUES (?, ?, ?, 'member')",
            (world["project_id"], world["workspace_id"], world["users"]["member"]),
        )
        get_db().commit()

    owner = app.test_client()
    headers = authenticate(owner, "invite-owner")
    workspace = owner.get(workspace_url(world, "/members"))
    assert workspace.status_code == 200
    assert workspace.json["can_manage"] is True
    listed_workspace_member = next(
        item for item in workspace.json["members"]
        if item["user_id"] == world["users"]["member"]
    )
    assert listed_workspace_member["display_name"] == "Workspace Member"
    assert listed_workspace_member["email"] == "member@example.com"

    project = owner.get(project_url(world, "/members"))
    assert project.status_code == 200
    listed_project_member = next(
        item for item in project.json["members"]
        if item["id"] == world["users"]["member"]
    )
    assert listed_project_member["email"] == "member@example.com"
    assert listed_project_member["role"] == "member"
    assert headers["X-CSRFToken"]


def test_workspace_member_cannot_invite_or_elevate_role(app, member_world, monkeypatch):
    clear_smtp_environment(monkeypatch)
    client = app.test_client()
    headers = authenticate(client, "invite-member")
    response = create_invite(
        client,
        workspace_url(member_world, "/members/invitations"),
        headers,
        "new@example.com",
    )
    assert response.status_code == 403, response.json


def test_project_member_cannot_issue_project_invites(app, member_world, monkeypatch):
    clear_smtp_environment(monkeypatch)
    world = member_world
    with app.app_context():
        get_db().execute(
            "INSERT INTO project_member (project_id, workspace_id, user_id, role) "
            "VALUES (?, ?, ?, 'member')",
            (world["project_id"], world["workspace_id"], world["users"]["member"]),
        )
        get_db().commit()
    client = app.test_client()
    headers = authenticate(client, "invite-member")
    response = create_invite(
        client,
        project_url(world, "/members/invitations"),
        headers,
        "new@example.com",
    )
    assert response.status_code == 403


def test_email_validation_and_invites_never_assign_admin(app, member_world, monkeypatch):
    clear_smtp_environment(monkeypatch)
    client = app.test_client()
    headers = authenticate(client, "invite-owner")
    url = project_url(member_world, "/members/invitations")

    invalid = create_invite(client, url, headers, "not-an-email")
    assert invalid.status_code == 400
    assert invalid.json["error"]["code"] == "invalid_email"

    elevated = client.post(
        url,
        json={"email": "guest@example.com", "role": "admin"},
        headers=headers,
    )
    assert elevated.status_code == 400

    issued = create_invite(client, url, headers)
    assert issued.status_code == 201
    invitation = issued.json["invitation"]
    assert invitation["role"] == "member"
    assert invitation["email_status"] == "not_configured"
    assert "SMTP_HOST" in invitation["email_message"]
    assert invitation["invite_url"].startswith("/invite/accept?")
    expires_at = datetime.strptime(invitation["expires_at"], "%Y-%m-%d %H:%M:%S")
    remaining = expires_at - datetime.utcnow()
    assert timedelta(hours=167, minutes=59) <= remaining <= timedelta(hours=168)
    token = invitation_token(issued)
    with app.app_context():
        saved = get_db().execute(
            "SELECT token_hash, role FROM member_invitation WHERE id = ?",
            (invitation["id"],),
        ).fetchone()
        assert saved["token_hash"] != token
        assert len(saved["token_hash"]) == 64
        assert saved["role"] == "member"


def test_acceptance_requires_invited_email_and_is_single_use(app, member_world, monkeypatch):
    clear_smtp_environment(monkeypatch)
    world = member_world
    owner = app.test_client()
    owner_headers = authenticate(owner, "invite-owner")
    issued = create_invite(
        owner,
        project_url(world, "/members/invitations"),
        owner_headers,
    )
    assert issued.status_code == 201
    token = invitation_token(issued)

    wrong_user = app.test_client()
    wrong_headers = authenticate(wrong_user, "wrong-user")
    mismatch = wrong_user.post(
        "/workspaces/invitations/accept",
        json={"token": token},
        headers=wrong_headers,
    )
    assert mismatch.status_code == 403
    assert mismatch.json["error"]["code"] == "invitation_email_mismatch"

    invitee = app.test_client()
    invitee_headers = authenticate(invitee, "invitee")
    accepted = invitee.post(
        "/workspaces/invitations/accept",
        json={"token": token},
        headers=invitee_headers,
    )
    assert accepted.status_code == 200
    assert accepted.json["role"] == "member"
    with app.app_context():
        db = get_db()
        assert db.execute(
            "SELECT role FROM workspace_member WHERE workspace_id = ? AND user_id = ?",
            (world["workspace_id"], world["users"]["invitee"]),
        ).fetchone()["role"] == "member"
        assert db.execute(
            "SELECT role FROM project_member WHERE project_id = ? AND user_id = ?",
            (world["project_id"], world["users"]["invitee"]),
        ).fetchone()["role"] == "member"

    reused = invitee.post(
        "/workspaces/invitations/accept",
        json={"token": token},
        headers=invitee_headers,
    )
    assert reused.status_code == 410


def test_expired_invitation_is_not_accepted(app, member_world, monkeypatch):
    clear_smtp_environment(monkeypatch)
    world = member_world
    owner = app.test_client()
    owner_headers = authenticate(owner, "invite-owner")
    issued = create_invite(
        owner,
        workspace_url(world, "/members/invitations"),
        owner_headers,
        "guest@example.com",
    )
    assert issued.status_code == 201
    invitation = issued.json["invitation"]
    token = invitation_token(issued)
    with app.app_context():
        get_db().execute(
            "UPDATE member_invitation SET expires_at = '2000-01-01 00:00:00' WHERE id = ?",
            (invitation["id"],),
        )
        get_db().commit()

    invitee = app.test_client()
    invitee_headers = authenticate(invitee, "invitee")
    expired = invitee.post(
        "/workspaces/invitations/accept",
        json={"token": token},
        headers=invitee_headers,
    )
    assert expired.status_code == 410
    assert expired.json["error"]["code"] == "invitation_invalid_or_expired"


def test_pending_invites_can_be_listed_and_revoked(app, member_world, monkeypatch):
    clear_smtp_environment(monkeypatch)
    world = member_world
    owner = app.test_client()
    headers = authenticate(owner, "invite-owner")
    url = workspace_url(world, "/members/invitations")
    issued = create_invite(owner, url, headers, "new@example.com")
    assert issued.status_code == 201
    listing = owner.get(url)
    assert listing.status_code == 200
    assert [item["email"] for item in listing.json["invitations"]] == ["new@example.com"]

    invitation_id = issued.json["invitation"]["id"]
    revoked = owner.delete(f"{url}/{invitation_id}", headers=headers)
    assert revoked.status_code == 200
    assert owner.get(url).json["invitations"] == []

    invitee = app.test_client()
    invitee_headers = authenticate(invitee, "invitee")
    rejected = invitee.post(
        "/workspaces/invitations/accept",
        json={"token": invitation_token(issued)},
        headers=invitee_headers,
    )
    assert rejected.status_code == 410


def test_workspace_invitation_resend_rotates_token_and_preserves_member_role(
    app, member_world, monkeypatch
):
    clear_smtp_environment(monkeypatch)
    world = member_world
    owner = app.test_client()
    owner_headers = authenticate(owner, "invite-owner")
    invitations_url = workspace_url(world, "/members/invitations")
    issued = create_invite(owner, invitations_url, owner_headers)
    assert issued.status_code == 201
    original = issued.json["invitation"]
    original_token = invitation_token(issued)

    resent = owner.post(
        f"{invitations_url}/{original['id']}/resend",
        headers=owner_headers,
    )
    assert resent.status_code == 200, resent.json
    replacement = resent.json["invitation"]
    assert replacement["id"] != original["id"]
    assert replacement["replaces_invitation_id"] == original["id"]
    assert replacement["email"] == "guest@example.com"
    assert replacement["role"] == "member"
    assert replacement["email_status"] == "not_configured"
    replacement_token = invitation_token(resent)

    invitee = app.test_client()
    invitee_headers = authenticate(invitee, "invitee")
    stale = invitee.post(
        "/workspaces/invitations/accept",
        json={"token": original_token},
        headers=invitee_headers,
    )
    assert stale.status_code == 410
    accepted = invitee.post(
        "/workspaces/invitations/accept",
        json={"token": replacement_token},
        headers=invitee_headers,
    )
    assert accepted.status_code == 200
    assert accepted.json["role"] == "member"
    assert owner.get(invitations_url).json["invitations"] == []

    with app.app_context():
        old_record = get_db().execute(
            "SELECT revoked_at FROM member_invitation WHERE id = ?",
            (original["id"],),
        ).fetchone()
        new_record = get_db().execute(
            "SELECT accepted_at, role FROM member_invitation WHERE id = ?",
            (replacement["id"],),
        ).fetchone()
        assert old_record["revoked_at"] is not None
        assert new_record["accepted_at"] is not None
        assert new_record["role"] == "member"


def test_project_invitation_can_be_resent(app, member_world, monkeypatch):
    clear_smtp_environment(monkeypatch)
    world = member_world
    owner = app.test_client()
    headers = authenticate(owner, "invite-owner")
    invitations_url = project_url(world, "/members/invitations")
    issued = create_invite(owner, invitations_url, headers)
    assert issued.status_code == 201
    resent = owner.post(
        f"{invitations_url}/{issued.json['invitation']['id']}/resend",
        headers=headers,
    )
    assert resent.status_code == 200, resent.json
    assert resent.json["invitation"]["role"] == "member"
    assert resent.json["invitation"]["id"] != issued.json["invitation"]["id"]


def test_invitation_email_uses_configured_smtp_and_public_url(
    app, member_world, monkeypatch
):
    clear_smtp_environment(monkeypatch)
    monkeypatch.setenv("PUBLIC_APP_URL", "https://kairo.example")
    monkeypatch.setenv("SMTP_HOST", "smtp.example")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "mailer")
    monkeypatch.setenv("SMTP_PASSWORD", "test-secret")
    monkeypatch.setenv("SMTP_FROM", "Kairo <noreply@kairo.example>")
    monkeypatch.setenv("SMTP_USE_TLS", "true")
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout, **kwargs):
            assert (host, port, timeout) == ("smtp.example", 587, 10)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self, context):
            assert context is not None

        def login(self, username, password):
            assert (username, password) == ("mailer", "test-secret")

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr(
        "app.services.email_service.smtplib.SMTP", FakeSMTP
    )
    owner = app.test_client()
    headers = authenticate(owner, "invite-owner")
    issued = create_invite(
        owner,
        workspace_url(member_world, "/members/invitations"),
        headers,
        "new@example.com",
    )
    assert issued.status_code == 201
    invitation = issued.json["invitation"]
    assert invitation["email_status"] == "sent"
    assert invitation["invite_url"].startswith("https://kairo.example/invite/accept?")
    assert len(sent_messages) == 1
    assert sent_messages[0]["To"] == "new@example.com"
    assert invitation_token(issued) in sent_messages[0].get_content()


def test_non_admin_cannot_resend_invitation(app, member_world, monkeypatch):
    clear_smtp_environment(monkeypatch)
    world = member_world
    owner = app.test_client()
    owner_headers = authenticate(owner, "invite-owner")
    invitations_url = workspace_url(world, "/members/invitations")
    issued = create_invite(owner, invitations_url, owner_headers, "new@example.com")
    assert issued.status_code == 201

    member = app.test_client()
    member_headers = authenticate(member, "invite-member")
    denied = member.post(
        f"{invitations_url}/{issued.json['invitation']['id']}/resend",
        headers=member_headers,
    )
    assert denied.status_code == 403


def test_member_pages_render_both_scope_variants(app, member_world):
    world = member_world
    client = app.test_client()
    directory = client.get("/members")
    assert directory.status_code == 200
    assert b"data-directory-url=\"/workspaces\"" in directory.data

    workspace_page = client.get(workspace_url(world, "/members/page"))
    project_page = client.get(project_url(world, "/members/page"))
    assert workspace_page.status_code == 200
    assert project_page.status_code == 200
    assert b"Danh s\xc3\xa1ch th\xc3\xa0nh vi\xc3\xaAn" in workspace_page.data
    assert b"Th\xc3\xaAm th\xc3\xa0nh vi\xc3\xaan" in project_page.data

    invite_page = client.get("/invite/accept?token=nonsecret-test-token")
    assert invite_page.status_code == 200
    assert invite_page.headers["Cache-Control"] == "no-store"
    assert invite_page.headers["Referrer-Policy"] == "no-referrer"
