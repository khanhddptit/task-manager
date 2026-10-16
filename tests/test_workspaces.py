import sqlite3

import pytest

from app.db import get_db
from app.services.auth_service import register_user
from app.services.workspace_service import create_workspace, list_workspaces


def csrf_token(client):
    response = client.get("/auth/csrf")
    assert response.status_code == 200
    return response.json["csrf_token"]


def post_json(client, path, **data):
    return client.post(path, json=data, headers={"X-CSRFToken": csrf_token(client)})


def login(client, username="demo", password="correct-password"):
    return post_json(client, "/auth/login", username=username, password=password)


def assert_api_error(response, status, code):
    assert response.status_code == status
    assert response.is_json
    assert response.json["error"]["code"] == code
    assert response.headers["Cache-Control"] == "no-store"


def test_create_workspace_adds_owner_membership(app, user_id):
    with app.app_context():
        workspace = create_workspace("  Team  ", "  Description  ", user_id)

        member = get_db().execute(
            "SELECT role FROM workspace_member WHERE workspace_id = ? AND user_id = ?",
            (workspace["id"], user_id),
        ).fetchone()

    assert workspace["name"] == "Team"
    assert workspace["description"] == "Description"
    assert workspace["role"] == "owner"
    assert member["role"] == "owner"


def test_create_workspace_rolls_back_when_owner_membership_fails(app):
    with app.app_context():
        with pytest.raises(sqlite3.IntegrityError):
            create_workspace("Orphan workspace", "", owner_id=999)

        assert get_db().execute(
            "SELECT COUNT(*) FROM workspace WHERE name = ?",
            ("Orphan workspace",),
        ).fetchone()[0] == 0


def test_list_workspaces_only_returns_user_memberships_in_stable_order(app, user_id):
    with app.app_context():
        db = get_db()
        older_id = create_workspace("Older", "", user_id)["id"]
        newer_id = create_workspace("Newer", "", user_id)["id"]
        db.execute(
            "INSERT INTO user (username, password_hash) VALUES (?, ?)",
            ("another", "placeholder"),
        )
        another_user_id = db.execute(
            "SELECT id FROM user WHERE username = ?", ("another",)
        ).fetchone()["id"]
        other_id = create_workspace("Other user's", "", another_user_id)["id"]
        db.commit()

        db.execute(
            "UPDATE workspace SET created_at = '2025-01-01 00:00:00' WHERE id IN (?, ?)",
            (older_id, newer_id),
        )
        db.commit()

        workspaces = list_workspaces(user_id)

    assert [workspace["id"] for workspace in workspaces] == [newer_id, older_id]
    assert all(workspace["id"] != other_id for workspace in workspaces)
    assert {workspace["role"] for workspace in workspaces} == {"owner"}


def test_list_workspaces_returns_empty_list_without_memberships(app):
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO user (username, password_hash) VALUES (?, ?)",
            ("no_workspaces", "placeholder"),
        )
        user_without_workspaces_id = db.execute(
            "SELECT id FROM user WHERE username = ?", ("no_workspaces",)
        ).fetchone()["id"]

        workspaces = list_workspaces(user_without_workspaces_id)

    assert workspaces == []


def test_workspace_endpoints_require_login_and_are_non_cacheable(client):
    assert_api_error(client.get("/workspaces"), 401, "authentication_required")
    assert_api_error(post_json(client, "/workspaces", name="Team"), 401,
                     "authentication_required")


def test_post_workspace_creates_owner_and_returns_workspace(app, client, user_id):
    assert login(client).status_code == 200

    response = post_json(
        client, "/workspaces", name="  Team  ", description="  A team  ",
        owner_id=999,
    )

    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    assert set(response.json) == {"workspace"}
    workspace = response.json["workspace"]
    assert workspace["name"] == "Team"
    assert workspace["description"] == "A team"
    assert workspace["role"] == "owner"
    assert set(workspace) == {
        "id", "name", "description", "created_at", "updated_at", "role",
    }
    with app.app_context():
        member = get_db().execute(
            "SELECT user_id, role FROM workspace_member WHERE workspace_id = ?",
            (workspace["id"],),
        ).fetchone()
    assert member["user_id"] == user_id
    assert member["role"] == "owner"


def test_post_workspace_defaults_description_to_empty(client, user_id):
    assert login(client).status_code == 200

    response = post_json(client, "/workspaces", name="Team")

    assert response.status_code == 201
    assert response.json["workspace"]["description"] == ""


@pytest.mark.parametrize("data,field", [
    ({}, "name"),
    ({"name": None}, "name"),
    ({"name": 12}, "name"),
    ({"name": "   "}, "name"),
    ({"name": "Team", "description": None}, "description"),
    ({"name": "Team", "description": 12}, "description"),
])
def test_post_workspace_validates_fields(client, user_id, data, field):
    assert login(client).status_code == 200

    response = post_json(client, "/workspaces", **data)

    assert_api_error(response, 400, "validation_error")
    assert field in response.json["error"]["fields"]


def test_get_workspace_list_is_scoped_to_logged_in_user(app, client, user_id):
    assert login(client).status_code == 200
    own_workspace = post_json(client, "/workspaces", name="My team").json["workspace"]
    with app.app_context():
        other_user_id = register_user("another", "another-password")
        other_workspace = create_workspace("Other team", "", other_user_id)

    response = client.get("/workspaces")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json == {"workspaces": [own_workspace]}
    assert all(
        item["id"] != other_workspace["id"]
        for item in response.json["workspaces"]
    )
    assert response.json["workspaces"][0]["role"] == "owner"


def test_get_workspace_list_is_empty_for_user_without_workspaces(app, client):
    with app.app_context():
        register_user("empty_user", "another-password")
    assert login(client, "empty_user", "another-password").status_code == 200

    response = client.get("/workspaces")

    assert response.status_code == 200
    assert response.json == {"workspaces": []}


def test_workspace_post_rejects_missing_csrf_token(client, user_id):
    assert login(client).status_code == 200

    response = client.post("/workspaces", json={"name": "Team"})

    assert_api_error(response, 400, "csrf_failed")


@pytest.mark.parametrize("body,content_type,status,code", [
    ("{", "application/json", 400, "bad_request"),
    ("[]", "application/json", 400, "bad_request"),
    ("{}", "text/plain", 415, "unsupported_media_type"),
])
def test_workspace_post_rejects_invalid_json(client, user_id, body, content_type,
                                             status, code):
    assert login(client).status_code == 200
    response = client.post(
        "/workspaces",
        data=body,
        content_type=content_type,
        headers={"X-CSRFToken": csrf_token(client)},
    )

    assert_api_error(response, status, code)


@pytest.mark.parametrize("method,path,status,code", [
    ("post", "/workspaces/missing", 404, "not_found"),
    ("put", "/workspaces", 405, "method_not_allowed"),
])
def test_workspace_api_errors_are_json_and_non_cacheable(client, method, path, status, code):
    response = getattr(client, method)(path)

    assert_api_error(response, status, code)
