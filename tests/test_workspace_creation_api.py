from app.db import get_db


def get_csrf_token(client):
    response = client.get("/auth/csrf")
    assert response.status_code == 200
    return response.json["csrf_token"]


def login(client):
    response = client.post(
        "/auth/login",
        json={"username": "demo", "password": "correct-password"},
        headers={"X-CSRFToken": get_csrf_token(client)},
    )
    assert response.status_code == 200
    return response.json["csrf_token"]


def test_create_workspace_records_authenticated_user(app, client, user_id):
    csrf_token = login(client)

    response = client.post(
        "/workspaces",
        json={
            "name": "Team",
            "description": "",
            "created_by": 999,
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    workspace = response.json["workspace"]
    assert workspace["created_by"] == user_id
    assert workspace["role"] == "owner"
    with app.app_context():
        row = get_db().execute(
            "SELECT created_by FROM workspace WHERE id = ?",
            (workspace["id"],),
        ).fetchone()
    assert row["created_by"] == user_id


def test_create_workspace_requires_authentication(client):
    response = client.post(
        "/workspaces",
        json={"name": "Team"},
        headers={"X-CSRFToken": get_csrf_token(client)},
    )

    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json["error"]["code"] == "authentication_required"


def test_list_workspaces_returns_only_memberships_newest_first(app, client, user_id):
    csrf_token = login(client)
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO workspace (name, created_by) VALUES (?, ?)",
            ("Older workspace", user_id),
        )
        older_id = db.execute(
            "SELECT id FROM workspace WHERE name = ?", ("Older workspace",)
        ).fetchone()["id"]
        db.execute(
            """INSERT INTO workspace_member (workspace_id, user_id, role)
               VALUES (?, ?, ?)""",
            (older_id, user_id, "admin"),
        )
        db.execute(
            "INSERT INTO workspace (name, created_by) VALUES (?, ?)",
            ("Private workspace", user_id),
        )
        db.commit()

    create_response = client.post(
        "/workspaces",
        json={"name": "Newest workspace"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert create_response.status_code == 201

    response = client.get("/workspaces")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    workspaces = response.json["workspaces"]
    assert [workspace["name"] for workspace in workspaces] == [
        "Newest workspace",
        "Older workspace",
    ]
    assert [workspace["role"] for workspace in workspaces] == ["owner", "admin"]


def test_list_workspaces_requires_authentication(client):
    response = client.get("/workspaces")

    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json["error"]["code"] == "authentication_required"


def test_workspace_endpoint_errors_are_json_and_non_cacheable(client):
    response = client.patch("/workspaces")

    assert response.status_code == 405
    assert response.is_json
    assert response.json["error"]["code"] == "method_not_allowed"
    assert response.headers["Cache-Control"] == "no-store"
